"""Security emails from a separate mailbox over IMAP (1.14.0).

The mail-worker needs a domain of one's own on Cloudflare and wrangler; a
mailbox everyone has. The owner makes a separate box for the bot (Gmail or
Yandex), forwards the security notifications of the main one there with a
filter, and gives the bot the address and an app password. Every
mail.POLL_INTERVAL the bot reads what arrived after the last mail it saw (by
UID), keeps only what the box's provider vouched for — the top
Authentication-Results header says dkim=pass for the domain of From — and
only from the senders mail.py knows, hands it to mail.describe like the
worker's mail, and marks it read. Everything else stays unread in the box.

Only the standard library: imaplib in a thread, email for parsing.
"""

from __future__ import annotations

import asyncio
import email
import email.policy
import email.utils
import html
import imaplib
import logging
import re
from dataclasses import dataclass, field
from email.message import EmailMessage

from telegram import Bot

from bot import connections, humanize, notifier
from bot.callbacks import MAIL
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import t
from bot.monitors import mail
from bot.notifier import Priority

logger = logging.getLogger(__name__)

# The providers the bot knows, by the address's domain; Yandex names a second
# host for connections from outside Russia (its help pages), tried after the first.
SERVERS: dict[str, tuple[str, ...]] = {
    "gmail.com": ("imap.gmail.com",),
    "googlemail.com": ("imap.gmail.com",),
    "yandex.ru": ("imap.yandex.ru", "imap.ya.ru"),
    "ya.ru": ("imap.yandex.ru", "imap.ya.ru"),
    "yandex.com": ("imap.yandex.ru", "imap.ya.ru"),
}
PORT = 993
TIMEOUT_S = 30
MAX_PER_POLL = 50            # a flood waits for the next poll instead of one long session
TEXT_MAX = 4000              # what the worker keeps of a mail, and what mail.py reads
HTML_MAX = 200_000           # a mail's HTML is cut before it is turned into text
# Failed polls before the owner hears: a refused password twice (a single
# refusal can be the provider's hiccup), a silent server for ~30 minutes.
AUTH_AFTER = 2
UNREACHABLE_AFTER = mail.UNREACHABLE_AFTER

# Settings: where the reading stopped («<uidvalidity>:<uid>»), the last poll and its error.
UID_KEY = "mailbox_uid"
CHECKED_KEY = "mailbox_checked_at"
ERROR_KEY = "mailbox_error"
AUTH_STREAK, NET_STREAK = "mailbox_auth_fail_streak", "mailbox_net_fail_streak"
NET_SINCE, NET_LAST = "mailbox_net_fail_since", "mailbox_net_fail_last"
AUTH_ALERTED = "mailbox_auth_fail_alerted"

AUTH, NETWORK = "auth", "network"

_ADDRESS = re.compile(r"^[a-z0-9._%+-]+@([a-z0-9-]+(?:\.[a-z0-9-]+)+)$")


class MailboxError(Exception):
    """kind: AUTH — the box refused the password; NETWORK — the server did not answer."""

    def __init__(self, kind: str, detail: str = "") -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


@dataclass
class Batch:
    """What one poll found: the box's UIDVALIDITY, the newest UID in it, and
    the new mails (uid, raw bytes), oldest first."""

    validity: int
    top: int
    mails: list[tuple[int, bytes]] = field(default_factory=list)


def address(raw: str) -> str | None:
    """The address in lower case when it looks like one."""
    value = raw.strip().lower()
    return value if _ADDRESS.match(value) else None


def servers_for(addr: str) -> tuple[str, ...] | None:
    return SERVERS.get(addr.rsplit("@", 1)[-1])


def is_yandex(addr: str) -> bool:
    return (servers_for(addr) or ("",))[0] == "imap.yandex.ru"


def login_name(addr: str) -> str:
    """Yandex signs in by the part before @ (its help pages); Gmail by the whole address."""
    return addr.split("@", 1)[0] if is_yandex(addr) else addr


def app_password(raw: str) -> str:
    """The app password without the spaces Gmail shows it with."""
    return "".join(raw.split())


# ── IMAP (blocking: run in a thread) ────────────────────────────────────────

def _logout(conn: imaplib.IMAP4) -> None:
    try:
        conn.logout()
    except Exception:
        pass


def _connect(addr: str, password: str) -> imaplib.IMAP4_SSL:
    last: Exception | None = None
    for host in servers_for(addr) or ():
        try:
            conn = imaplib.IMAP4_SSL(host, PORT, timeout=TIMEOUT_S)
        except (OSError, imaplib.IMAP4.error) as e:
            last = e
            continue
        try:
            conn.login(login_name(addr), password)
        except imaplib.IMAP4.error as e:
            _logout(conn)
            raise MailboxError(AUTH, str(e)[:120]) from e
        except OSError as e:
            _logout(conn)
            raise MailboxError(NETWORK, type(e).__name__) from e
        return conn
    raise MailboxError(NETWORK, type(last).__name__ if last else "no server")


_STATUS = re.compile(rb"UIDNEXT (\d+)|UIDVALIDITY (\d+)")


def _status(conn: imaplib.IMAP4) -> tuple[int, int]:
    """(UIDVALIDITY, the newest UID) of INBOX, from STATUS: no message is read."""
    typ, data = conn.status("INBOX", "(UIDNEXT UIDVALIDITY)")
    if typ != "OK" or not data or not data[0]:
        raise MailboxError(NETWORK, "STATUS")
    found = {"next": 0, "validity": 0}
    for m in _STATUS.finditer(data[0] if isinstance(data[0], bytes) else bytes(data[0])):
        if m.group(1):
            found["next"] = int(m.group(1))
        if m.group(2):
            found["validity"] = int(m.group(2))
    return found["validity"], max(0, found["next"] - 1)


def probe(addr: str, password: str) -> tuple[int, int]:
    """Sign in and look at INBOX: (UIDVALIDITY, the newest UID) — where the
    reading starts, so the mail that is already there is never alerted."""
    conn = _connect(addr, password)
    try:
        typ, _ = conn.select("INBOX", readonly=True)
        if typ != "OK":
            raise MailboxError(AUTH, "SELECT INBOX")
        return _status(conn)
    except OSError as e:
        raise MailboxError(NETWORK, type(e).__name__) from e
    finally:
        _logout(conn)


def fetch(addr: str, password: str, validity: int | None, after: int | None) -> Batch:
    """The mails of INBOX with a UID above `after`, read without marking them
    (BODY.PEEK). A box whose UIDVALIDITY changed — or a first poll — starts
    from its newest mail: what is already there is not alerted."""
    conn = _connect(addr, password)
    try:
        typ, _ = conn.select("INBOX")
        if typ != "OK":
            raise MailboxError(AUTH, "SELECT INBOX")
        now_validity, top = _status(conn)
        batch = Batch(now_validity, top)
        if after is None or validity != now_validity or top <= after:
            return batch
        # «n:*» returns the newest mail even when its UID is below n: filtered here.
        typ, data = conn.uid("SEARCH", None, f"UID {after + 1}:*")
        if typ != "OK":
            raise MailboxError(NETWORK, "SEARCH")
        uids = sorted(int(x) for x in (data[0] or b"").split() if int(x) > after)[:MAX_PER_POLL]
        for uid in uids:
            typ, parts = conn.uid("FETCH", str(uid), "(BODY.PEEK[])")
            raw = next((p[1] for p in parts or () if isinstance(p, tuple) and len(p) > 1), None)
            if typ == "OK" and raw:
                batch.mails.append((uid, raw))
        return batch
    except OSError as e:
        raise MailboxError(NETWORK, type(e).__name__) from e
    finally:
        _logout(conn)


def mark_seen(addr: str, password: str, uids: list[int]) -> None:
    """Flag what was alerted as read, so the box shows what the bot left for its owner."""
    if not uids:
        return
    conn = _connect(addr, password)
    try:
        if conn.select("INBOX")[0] == "OK":
            conn.uid("STORE", ",".join(map(str, uids)), "+FLAGS", "(\\Seen)")
    except OSError as e:
        raise MailboxError(NETWORK, type(e).__name__) from e
    finally:
        _logout(conn)


# ── One mail ────────────────────────────────────────────────────────────────

def parse(raw: bytes) -> EmailMessage:
    return email.message_from_bytes(raw, policy=email.policy.default)


def from_address(msg: EmailMessage) -> str:
    return email.utils.parseaddr(str(msg.get("From", "")))[1].strip().lower()


_DKIM_PASS = re.compile(r"^\s*dkim\s*=\s*pass\b", re.IGNORECASE)
_DKIM_DOMAIN = re.compile(r"\bheader\.(?:d|i)\s*=\s*\"?([^\s;\"]+)", re.IGNORECASE)


def _related(signed: str, sender: str) -> bool:
    """The DKIM domain is the sender's domain, its parent or its subdomain —
    and the shorter of the two is a real domain, not a bare top level."""
    if signed == sender:
        return True
    shorter, longer = sorted((signed, sender), key=len)
    return "." in shorter and longer.endswith("." + shorter)


def authentic(msg: EmailMessage) -> bool:
    """The box's own provider checked the signature: its Authentication-Results
    — the topmost one, the one added last — has dkim=pass for the From
    domain. Headers further down came with the mail and prove nothing; SPF is
    not asked for, it fails on every forward."""
    results = msg.get_all("Authentication-Results") or []
    if not results:
        return False
    sender = from_address(msg).rsplit("@", 1)[-1]
    if not sender:
        return False
    for method in str(results[0]).split(";"):
        if not _DKIM_PASS.match(method):
            continue
        for found in _DKIM_DOMAIN.findall(method):
            if _related(found.rsplit("@", 1)[-1].lower().rstrip("."), sender):
                return True
    return False


def known_sender(addr: str) -> bool:
    """A sender mail.py reads security notices from, or Gmail's forwarding
    confirmation; anything else in the box is not the bot's business."""
    if addr == mail.GMAIL_FORWARDING:
        return True
    domain = addr.rsplit("@", 1)[-1]
    for suffix, _, _ in mail.SENDERS:
        if ("@" in suffix and addr == suffix) or (
            "@" not in suffix and (domain == suffix or domain.endswith("." + suffix))
        ):
            return True
    return False


_OPENER = re.compile(r"<(?:(style)|script)", re.IGNORECASE)
_CLOSERS = {"style": re.compile(r"</style>", re.IGNORECASE), "script": re.compile(r"</script>", re.IGNORECASE)}


def _strip_style_and_script(text: str) -> str:
    """<style>…</style> and <script>…</script> out, in one pass — the
    mail-worker's stripStyleAndScript: a name whose closing tag is not found
    once is not looked for again (1.10.2: the old pattern took seconds on a
    mail with thousands of unclosed «<style»)."""
    closers = dict(_CLOSERS)
    out: list[str] = []
    start = pos = 0
    while closers:
        opened = _OPENER.search(text, pos)
        if opened is None:
            break
        name = "style" if opened.group(1) else "script"
        closer = closers.get(name)
        if closer is None:
            pos = opened.end()
            continue
        closed = closer.search(text, opened.end())
        if closed is None:
            del closers[name]
            pos = opened.end()
            continue
        out += [text[start:opened.start()], " "]
        start = pos = closed.end()
    out.append(text[start:])
    return "".join(out)


_BREAK = re.compile(r"<br\s*/?>|</(?:p|div|tr|li|h\d)>", re.IGNORECASE)
_TAG = re.compile(r"<[^<>]+>")
_SPACES = re.compile(r"[ \t ]+")
_LINE_EDGES = re.compile(r" ?\n ?")       # after _SPACES a run of spaces is one space
_BLANK_LINES = re.compile(r"\n{2,}")


def html_to_text(markup: str) -> str:
    """The mail-worker's htmlToText: tags out, line breaks kept, entities decoded."""
    text = _TAG.sub(" ", _BREAK.sub("\n", _strip_style_and_script(markup[:HTML_MAX])))
    text = _LINE_EDGES.sub("\n", _SPACES.sub(" ", html.unescape(text)))
    return _BLANK_LINES.sub("\n", text).strip()


def body_text(msg: EmailMessage) -> str:
    """The plain text part, else the HTML one turned into text; the start of it."""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        content = part.get_content()
    except (LookupError, ValueError):
        payload = part.get_payload(decode=True) or b""
        content = payload.decode("utf-8", errors="replace")
    if not isinstance(content, str):
        return ""
    if part.get_content_type() == "text/html":
        content = html_to_text(content)
    return content[:TEXT_MAX]


def to_mail(validity: int, uid: int, msg: EmailMessage) -> mail.Mail:
    return mail.Mail(
        id=f"imap:{validity}:{uid}",
        sender=from_address(msg),
        subject=" ".join(str(msg.get("Subject", "")).split()),
        text=body_text(msg),
    )


# ── The poll ────────────────────────────────────────────────────────────────

def connected(config: Config) -> bool:
    return bool(config.mailbox_address and config.mailbox_password)


async def start_at(db: Database, validity: int, top: int) -> None:
    """Where the reading starts: the mail already in the box is the owner's past."""
    await db.set_setting(UID_KEY, f"{validity}:{top}")


async def _position(db: Database) -> tuple[int | None, int | None]:
    raw = await db.get_setting(UID_KEY) or ""
    validity, _, uid = raw.partition(":")
    if validity.isdigit() and uid.isdigit():
        return int(validity), int(uid)
    return None, None


def _when(raw: str | None):
    try:
        return parse_utc(raw) if raw else None
    except ValueError:
        return None


async def _track(bot: Bot, config: Config, db: Database, error: MailboxError | None) -> None:
    """One 🟠 when the box keeps refusing the password and one ✅ when it takes
    one again; one ⚠️ when the server stays silent ~30 minutes and one line
    when it answers (the mail waits in the box meanwhile, nothing is lost)."""
    now = utcnow()
    await db.set_setting(CHECKED_KEY, now.isoformat())
    await db.set_setting(ERROR_KEY, error.kind if error else "")
    addr = config.mailbox_address or ""
    auth_fails = int(await db.get_setting(AUTH_STREAK) or "0")
    net_fails = int(await db.get_setting(NET_STREAK) or "0")

    if error is None or error.kind != AUTH:
        if auth_fails:
            await db.set_setting(AUTH_STREAK, "0")
        if error is None and await db.get_setting(AUTH_ALERTED) == "1":
            await db.set_setting(AUTH_ALERTED, "")
            await notifier.send(bot, config, db, humanize.recovery(
                t("✅ Ящик {address} снова принимает пароль приложения").format(address=addr), ""),
                Priority.NORMAL, monitor="mail")
    if error is None or error.kind != NETWORK:
        if net_fails:
            await db.set_setting(NET_STREAK, "0")
        if error is None and net_fails >= UNREACHABLE_AFTER:
            how_long = humanize.lasted(_when(await db.get_setting(NET_SINCE)), _when(await db.get_setting(NET_LAST)),
                                       now, await notifier.owner_tz(db, config), mail.POLL_INTERVAL)
            await notifier.send(bot, config, db, humanize.recovery(
                t("✅ Ящик {address} снова отвечает, письма прочитаны").format(address=addr), how_long, "Не отвечал"),
                Priority.NORMAL, monitor="mail")
    if error is None:
        return

    if error.kind == AUTH:
        auth_fails += 1
        await db.set_setting(AUTH_STREAK, str(auth_fails))
        if auth_fails == AUTH_AFTER and await db.get_setting(AUTH_ALERTED) != "1":
            await db.set_setting(AUTH_ALERTED, "1")
            await notifier.send(bot, config, db, humanize.alert(
                t("🟠 Ящик {address} не принимает пароль приложения — письма безопасности не читаются").format(
                    address=addr),
                "mailbox_auth", error.detail or AUTH),
                Priority.NORMAL, actions=(MAIL,), monitor="mail")
        return
    if net_fails == 0:
        await db.set_setting(NET_SINCE, now.isoformat())
    await db.set_setting(NET_LAST, now.isoformat())
    net_fails += 1
    await db.set_setting(NET_STREAK, str(net_fails))
    if net_fails == UNREACHABLE_AFTER:
        await notifier.send(bot, config, db, humanize.alert(
            t("⚠️ Не смог проверить ящик {address} ~30 мин: сервер не отвечает").format(address=addr),
            "mailbox_silent", error.detail, t("{n} опросов подряд, раз в 5 мин").format(n=net_fails)),
            Priority.NORMAL, actions=(MAIL,), monitor="mail")


async def check(bot: Bot, config: Config, db: Database) -> int:
    """One poll of the separate mailbox; returns the alerts sent."""
    addr, password = config.mailbox_address or "", config.mailbox_password or ""
    validity, after = await _position(db)
    try:
        batch = await asyncio.to_thread(fetch, addr, password, validity, after)
    except MailboxError as e:
        logger.warning("Mailbox poll failed: %s", e.kind)
        await _track(bot, config, db, e)
        return 0
    await _track(bot, config, db, None)
    if after is None or validity != batch.validity:
        await start_at(db, batch.validity, batch.top)
        return 0

    trusted: list[tuple[int, mail.Mail]] = []
    last = after
    for uid, raw in batch.mails:
        last = max(last, uid)
        try:
            msg = parse(raw)
        except Exception:
            logger.warning("Mailbox: unreadable mail %s skipped", uid)
            continue
        sender = from_address(msg)
        if not known_sender(sender):
            logger.info("Mailbox: mail %s from an unknown sender left unread", uid)
            continue
        if not authentic(msg):
            logger.warning("Mailbox: mail %s claims %s without a provider-checked DKIM — skipped", uid, sender)
            continue
        trusted.append((uid, to_mail(batch.validity, uid, msg)))

    sent, handled = await mail.handle(bot, config, db, [m for _, m in trusted])
    # A mail whose alert did not go out is read again next time: the position
    # stops before the first of them.
    pending = [uid for uid, m in trusted if m.id not in handled]
    if pending:
        last = min(pending) - 1
    await start_at(db, batch.validity, last)
    seen = [uid for uid, m in trusted if m.id in handled]
    try:
        await asyncio.to_thread(mark_seen, addr, password, seen)
    except MailboxError as e:
        logger.warning("Mailbox: could not mark %d mail(s) read: %s", len(seen), e.kind)
    return sent


async def disconnect(config: Config, db: Database) -> None:
    """Forget the mailbox set in the chat, where its reading stopped and its state."""
    await connections.remove(config, db, "mailbox_address", "mailbox_password")
    for key in (UID_KEY, CHECKED_KEY, ERROR_KEY, AUTH_STREAK, NET_STREAK, AUTH_ALERTED):
        await db.set_setting(key, "")
