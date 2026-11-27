"""1.14.0: security emails from a separate mailbox over IMAP, and the
mail-worker connected from the chat. The IMAP server is a fake
imaplib.IMAP4_SSL: the tests never touch the network."""

from __future__ import annotations

import dataclasses
import imaplib
import time
from email.message import EmailMessage

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from conftest import buttons
from telegram.ext import ConversationHandler

from bot import connections, handlers, mailbox, monitors, ui
from bot.monitors import mail

ADDRESS = "my.alerts.bot@gmail.com"
PASSWORD = "abcdefghijklmnop"
TOP_AR = "mx.google.com; dkim=pass header.i=@github.com header.s=pf2023 header.b=AbCd; spf=pass smtp.mailfrom=github.com"


def make_mail(sender="noreply@github.com", subject="[GitHub] Please review this sign in", text="Someone signed in",
              results: list[str] | None = None, html: str | None = None) -> bytes:
    msg = EmailMessage()
    for value in (results if results is not None else [TOP_AR]):
        msg["Authentication-Results"] = value
    msg["From"] = f"GitHub <{sender}>"
    msg["To"] = ADDRESS
    msg["Subject"] = subject
    if html is not None:
        msg.set_content(html, subtype="html")
    else:
        msg.set_content(text)
    return msg.as_bytes()


class Server:
    """What the fake IMAP server holds: the box, its password, its state."""

    def __init__(self):
        self.validity = 7
        self.mails: dict[int, bytes] = {}
        self.seen: set[int] = set()
        self.password = PASSWORD
        self.down: set[str] = set()       # hosts that do not answer
        self.logins: list[tuple[str, str, str]] = []

    def add(self, uid: int, raw: bytes) -> None:
        self.mails[uid] = raw


class FakeIMAP:
    server: Server

    def __init__(self, host, port, timeout=None):
        if host in self.server.down:
            raise OSError("connection refused")
        self.host = host

    def login(self, user, password):
        self.server.logins.append((self.host, user, password))
        if password != self.server.password:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials (Failure)")
        return "OK", [b"Logged in"]

    def select(self, name, readonly=False):
        return "OK", [str(len(self.server.mails)).encode()]

    def status(self, name, items):
        top = max(self.server.mails, default=0)
        return "OK", [f'"INBOX" (UIDNEXT {top + 1} UIDVALIDITY {self.server.validity})'.encode()]

    def uid(self, command, *args):
        if command == "SEARCH":
            low = int(args[1].split()[1].split(":")[0])
            found = [u for u in sorted(self.server.mails) if u >= low]
            if not found and self.server.mails:       # RFC 3501: «n:*» always includes the newest
                found = [max(self.server.mails)]
            return "OK", [" ".join(map(str, found)).encode()]
        if command == "FETCH":
            uid = int(args[0])
            raw = self.server.mails[uid]
            return "OK", [(f"{uid} (UID {uid} BODY[] {{{len(raw)}}}".encode(), raw), b")"]
        if command == "STORE":
            self.server.seen |= {int(u) for u in args[0].split(",")}
            return "OK", []
        raise AssertionError(command)

    def logout(self):
        return "BYE", []


@pytest.fixture
def server(monkeypatch):
    srv = Server()
    FakeIMAP.server = srv
    monkeypatch.setattr(mailbox.imaplib, "IMAP4_SSL", FakeIMAP)
    return srv


@pytest.fixture
def box_config(config):
    return dataclasses.replace(config, mailbox_address=ADDRESS, mailbox_password=PASSWORD,
                               security_mail_url=None, security_mail_token=None)


# ── The address and the server ──────────────────────────────────────────────

@pytest.mark.parametrize(("raw", "expected"), [
    ("  My.Alerts@Gmail.com ", "my.alerts@gmail.com"), ("me@yandex.ru", "me@yandex.ru"),
    ("not an address", None), ("me@", None), ("@gmail.com", None),
])
def test_addresses(raw, expected):
    assert mailbox.address(raw) == expected


def test_servers_and_logins():
    assert mailbox.servers_for("a@gmail.com") == ("imap.gmail.com",)
    assert mailbox.servers_for("a@ya.ru") == ("imap.yandex.ru", "imap.ya.ru")
    assert mailbox.servers_for("a@mail.ru") is None
    assert mailbox.login_name("me@yandex.ru") == "me" and mailbox.login_name(ADDRESS) == ADDRESS
    assert mailbox.app_password("abcd efgh ijkl mnop") == PASSWORD


def test_probe_reads_where_the_box_ends(server):
    server.add(41, make_mail())
    assert mailbox.probe(ADDRESS, PASSWORD) == (7, 41)
    with pytest.raises(mailbox.MailboxError) as refused:
        mailbox.probe(ADDRESS, "wrong")
    assert refused.value.kind == mailbox.AUTH
    server.down.add("imap.gmail.com")
    with pytest.raises(mailbox.MailboxError) as silent:
        mailbox.probe(ADDRESS, PASSWORD)
    assert silent.value.kind == mailbox.NETWORK


def test_yandex_tries_its_second_host_and_signs_in_by_the_login(server):
    server.down.add("imap.yandex.ru")
    assert mailbox.probe("me@yandex.ru", PASSWORD) == (7, 0)
    assert server.logins == [("imap.ya.ru", "me", PASSWORD)]


# ── Is the mail real ─────────────────────────────────────────────────────────

def _msg(**kwargs):
    return mailbox.parse(make_mail(**kwargs))


def test_a_genuine_mail_passes():
    assert mailbox.authentic(_msg())


@pytest.mark.parametrize("results", [
    [],                                                                          # no Authentication-Results at all
    ["mx.google.com; dkim=fail header.i=@github.com; spf=pass"],                 # the signature did not verify
    ["mx.google.com; dkim=pass header.d=evil.example; spf=pass"],                # signed, but by someone else
    ["mx.google.com; dkim=pass header.d=com"],                                   # a bare top level is no domain
    # The provider's own header is the top one; a «pass» further down came with the mail.
    ["mx.google.com; dkim=none; spf=softfail", "mx.google.com; dkim=pass header.i=@github.com"],
])
def test_a_forged_mail_does_not(results):
    assert not mailbox.authentic(_msg(results=results))


def test_a_parent_or_sub_domain_signature_counts():
    assert mailbox.authentic(_msg(sender="security@mail.instagram.com",
                                  results=["mx.google.com; dkim=pass header.d=instagram.com"]))
    assert mailbox.authentic(_msg(sender="noreply@github.com",
                                  results=["mx.yandex.ru; dkim=pass header.d=mail.github.com"]))


def test_only_known_senders_are_read():
    assert mailbox.known_sender("noreply@github.com") and mailbox.known_sender("security@mail.instagram.com")
    assert mailbox.known_sender(mail.GMAIL_FORWARDING)
    assert not mailbox.known_sender("friend@gmail.com") and not mailbox.known_sender("news@example.com")


def test_the_text_is_plain_or_html_made_plain():
    assert mailbox.body_text(_msg(text="New sign-in on Windows")) == "New sign-in on Windows\n"
    html = "<style>p{color:red}</style><p>New&nbsp;sign-in</p><script>x()</script><div>from Windows</div>"
    assert mailbox.body_text(_msg(html=html)) == "New sign-in\nfrom Windows"


def test_html_with_thousands_of_unclosed_styles_is_fast():
    started = time.monotonic()
    mailbox.html_to_text("<style" * 20_000 + "<p>end</p>")
    assert time.monotonic() - started < 1.0


# ── The poll ─────────────────────────────────────────────────────────────────

async def test_the_first_poll_only_marks_where_reading_starts(bot, box_config, db, server):
    server.add(1, make_mail())
    assert await mailbox.check(bot, box_config, db) == 0 and bot.messages == []
    assert await db.get_setting(mailbox.UID_KEY) == "7:1"


async def test_new_mail_is_alerted_once_in_order_and_marked_read(bot, box_config, db, server):
    await mailbox.start_at(db, 7, 1)
    server.add(5, make_mail(subject="Your password has changed"))
    server.add(3, make_mail())
    server.add(4, make_mail(sender="friend@gmail.com", subject="hi",
                            results=["mx.google.com; dkim=pass header.d=gmail.com"]))
    server.add(6, make_mail(results=["mx.google.com; dkim=fail header.i=@github.com"]))
    assert await mailbox.check(bot, box_config, db) == 2
    assert "новый вход" in bot.messages[0] and "пароль изменён" in bot.messages[1]    # UID 3, then 5
    assert server.seen == {3, 5}                       # a stranger's and a forged mail stay unread for the owner
    assert await db.get_setting(mailbox.UID_KEY) == "7:6"
    assert await mailbox.check(bot, box_config, db) == 0 and len(bot.messages) == 2


async def test_a_mail_whose_alert_did_not_go_out_is_read_again(bot, box_config, db, server, monkeypatch):
    await mailbox.start_at(db, 7, 1)
    server.add(2, make_mail())

    async def down(*args, **kwargs):
        raise RuntimeError("Telegram is down")

    monkeypatch.setattr(mail.notifier, "send", down)
    assert await mailbox.check(bot, box_config, db) == 0
    assert await db.get_setting(mailbox.UID_KEY) == "7:1" and server.seen == set()
    monkeypatch.undo()
    FakeIMAP.server = server
    monkeypatch.setattr(mailbox.imaplib, "IMAP4_SSL", FakeIMAP)
    assert await mailbox.check(bot, box_config, db) == 1 and server.seen == {2}


async def test_a_new_uidvalidity_starts_over_without_alerting_the_past(bot, box_config, db, server):
    await mailbox.start_at(db, 3, 1)
    server.add(2, make_mail())
    assert await mailbox.check(bot, box_config, db) == 0
    assert await db.get_setting(mailbox.UID_KEY) == "7:2"


async def test_gmails_forwarding_confirmation_is_relayed(bot, box_config, db, server):
    await mailbox.start_at(db, 7, 0)
    server.add(1, make_mail(
        sender=mail.GMAIL_FORWARDING, subject="Gmail Forwarding Confirmation",
        text="Click https://mail.google.com/mail/vf-%5BABC%5D-xyz to confirm",
        results=["mx.google.com; dkim=pass header.i=@google.com"]))
    assert await mailbox.check(bot, box_config, db) == 1
    assert "Gmail просит подтвердить пересылку" in bot.messages[0]


async def test_a_refused_password_is_told_once_and_its_return_once(bot, box_config, db, server):
    await mailbox.start_at(db, 7, 0)
    server.password = "revoked"
    for _ in range(4):
        await mailbox.check(bot, box_config, db)
    assert len(bot.messages) == 1 and bot.messages[0].startswith("🟠 Ящик my.alerts.bot@gmail.com не принимает")
    assert "создать новый пароль приложения" in bot.messages[0].lower()
    assert await db.get_setting(mailbox.ERROR_KEY) == mailbox.AUTH
    server.password = PASSWORD
    await mailbox.check(bot, box_config, db)
    await mailbox.check(bot, box_config, db)
    assert len(bot.messages) == 2 and bot.messages[1].startswith("✅ Ящик my.alerts.bot@gmail.com снова принимает")


async def test_a_silent_server_is_could_not_check_once(bot, box_config, db, server):
    await mailbox.start_at(db, 7, 0)
    server.down.add("imap.gmail.com")
    for _ in range(mailbox.UNREACHABLE_AFTER + 2):
        await mailbox.check(bot, box_config, db)
    assert len(bot.messages) == 1 and bot.messages[0].startswith("⚠️ Не смог проверить ящик")
    assert bot.silent == [True]                        # ⚠️ is not a problem level: it never rings
    server.down.clear()
    await mailbox.check(bot, box_config, db)
    assert bot.messages[1].startswith("✅ Ящик my.alerts.bot@gmail.com снова отвечает")


async def test_the_monitor_works_with_the_mailbox_alone(config, box_config):
    assert monitors.BY_ID["mail"].requires(box_config)
    assert not monitors.BY_ID["mail"].requires(dataclasses.replace(box_config, mailbox_password=None))


# ── From the chat ────────────────────────────────────────────────────────────

@pytest.fixture
def ctx(make_context, config):
    bare = dataclasses.replace(config, security_mail_url=None, security_mail_token=None)
    context = make_context()
    context.bot_data["config"] = bare
    return context


async def _send(make_update, context, entry, *texts):
    start = make_update(callback=entry)
    assert await handlers.input_conv_start(start, context) == handlers.AWAITING_INPUT
    updates = []
    state = None
    for text in texts:
        update = make_update(text=text)
        state = await handlers.input_conv_value(update, context)
        updates.append(update)
    return updates, state


async def test_a_mailbox_is_connected_in_two_steps_and_the_password_leaves_the_chat(make_update, ctx, db, server):
    server.add(12, make_mail())
    cfg = ctx.bot_data["config"]
    (address, password), state = await _send(make_update, ctx, "mail:box", ADDRESS, "abcd efgh ijkl mnop")
    assert "Шаг 2 из 2" in address.effective_chat.sent[0] and not address.message.deleted
    assert state == ConversationHandler.END and password.message.deleted
    assert (cfg.mailbox_address, cfg.mailbox_password) == (ADDRESS, PASSWORD)
    assert await db.get_setting(mailbox.UID_KEY) == "7:12"            # the mail already there is the past
    assert password.message.replies[0].startswith("✅ Ящик my.alerts.bot@gmail.com подключён")
    assert PASSWORD not in "".join(password.message.replies + password.effective_chat.sent)


async def test_a_wrong_password_keeps_the_step_open(make_update, ctx, server):
    (_, password), state = await _send(make_update, ctx, "mail:box", "me@yandex.ru", "wrong")
    assert state == handlers.AWAITING_INPUT and password.message.deleted
    assert "не принял пароль" in password.effective_chat.sent[0] and "Яндекс" in password.effective_chat.sent[0]
    assert ctx.bot_data["config"].mailbox_password is None


async def test_a_provider_the_bot_cannot_read_is_said_plainly(make_update, ctx, server):
    (address,), state = await _send(make_update, ctx, "mail:box", "me@mail.ru")
    assert state == handlers.AWAITING_INPUT and "только Gmail и Яндекс" in address.effective_chat.sent[0]


async def test_a_dash_disconnects_the_mailbox(make_update, ctx, db, server):
    await _send(make_update, ctx, "mail:box", ADDRESS, PASSWORD)
    (dash,), state = await _send(make_update, ctx, "mail:box", "-")
    cfg = ctx.bot_data["config"]
    assert state == ConversationHandler.END and cfg.mailbox_address is None and cfg.mailbox_password is None
    assert await db.get_setting(mailbox.UID_KEY) == ""


async def test_the_mailbox_password_stays_out_of_the_backup(config, db, tmp_path):
    import sqlite3
    await connections.save(config, db, mailbox_address=ADDRESS, mailbox_password=PASSWORD)
    path = str(tmp_path / "backup.db")
    await db.snapshot_without_secrets(path)
    with sqlite3.connect(path) as conn:
        kept = dict(conn.execute("SELECT key, value FROM settings WHERE key LIKE 'conn_%'").fetchall())
    assert kept == {"conn_mailbox_address": ADDRESS}


async def test_a_worker_is_connected_with_a_live_check(make_update, ctx, monkeypatch):
    asked = []

    async def answers(url, token):
        asked.append((url, token))
        return "ok" if token == "s3cret" else "token"

    monkeypatch.setattr(handlers, "_worker_answers", answers)
    url = "https://socialbot-mail.me.workers.dev"
    cfg = ctx.bot_data["config"]
    (_, wrong), state = await _send(make_update, ctx, "mail:wk", url + "/", "nope")
    assert state == handlers.AWAITING_INPUT and wrong.message.deleted and "не принял токен" in wrong.effective_chat.sent[0]
    assert cfg.security_mail_url is None                                # nothing kept until the pair works
    (_, good), state = await _send(make_update, ctx, "mail:wk", url, "s3cret")
    assert state == ConversationHandler.END and good.message.deleted
    assert (cfg.security_mail_url, cfg.security_mail_token) == (url, "s3cret") and asked[-1] == (url, "s3cret")
    assert monitors.BY_ID["mail"].requires(cfg)


async def test_worker_answers_reads_the_status():
    state = {"token": "s3cret"}

    async def events(request):
        if request.headers.get("Authorization") != f"Bearer {state['token']}":
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response({"events": []})

    app = web.Application()
    app.router.add_get("/events", events)
    server = TestServer(app)
    await server.start_server()
    url = str(server.make_url("")).rstrip("/")
    try:
        assert await handlers._worker_answers(url, "s3cret") == "ok"
        assert await handlers._worker_answers(url, "nope") == "token"
    finally:
        await server.close()
    assert await handlers._worker_answers(url, "s3cret") == "unreachable"


async def test_the_screen_shows_both_ways_and_the_state(config, box_config, db):
    screen = await ui.mail_screen(db, dataclasses.replace(config, security_mail_url=None, security_mail_token=None))
    keys = buttons(screen.keyboard)
    assert keys["mail:box"] == "📮 Отдельный ящик (просто)"
    assert keys["mail:wk"] == "☁️ Свой воркер на Cloudflare (для продвинутых)"
    await db.set_setting(mailbox.ERROR_KEY, mailbox.AUTH)
    text = (await ui.mail_screen(db, box_config)).text
    assert "📮 Ящик: my.alerts.bot@gmail.com — 🟠 не принимает пароль приложения" in text
