"""Security emails: new sign-ins, password, email and 2FA changes, login codes.

The user forwards the security notifications of their accounts (a mail
filter on the sender) to the mail-worker address; the worker keeps them
until the bot fetches and acknowledges them. Classification lives here:
the worker only stores sender, subject and the start of the text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import timedelta

import aiohttp
from telegram import Bot

from bot.config import Config
from bot.db import Database, utcnow
from bot.monitors import NO_PREVIEW, hygiene

logger = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(minutes=2)
# Consecutive failed polls before the worker is reported unreachable (~30 min).
UNREACHABLE_AFTER = 15
SUBJECT_LEN = 150
# Only the start of the body is searched: footers say "if this wasn't you,
# reset your password" under every kind of notice.
BODY_HEAD = 600

# Sender domain (suffix match) -> display name and the connector whose
# checklist a password change updates (None: a network without a connector).
SENDERS: tuple[tuple[str, str, str | None], ...] = (
    ("google.com", "Google", "youtube"),
    ("youtube.com", "YouTube", "youtube"),
    ("linkedin.com", "LinkedIn", "linkedin"),
    ("telegram.org", "Telegram", "telegram"),
    ("instagram.com", "Instagram", None),
    ("facebookmail.com", "Facebook", None),
    ("tiktok.com", "TikTok", None),
    ("x.com", "X", None),
    ("twitter.com", "X", None),
)

RECOVERY = {
    "Google": "https://g.co/recover",
    "YouTube": "https://g.co/recover",
    "Instagram": "https://www.instagram.com/hacked/",
    "Facebook": "https://www.facebook.com/hacked",
}

GMAIL_FORWARDING = "forwarding-noreply@google.com"


@dataclass(frozen=True)
class Kind:
    id: str
    icon: str
    title: str
    advice: str
    words: tuple[str, ...]


KINDS: tuple[Kind, ...] = (
    Kind(
        "password_reset", "🚨", "запрошен сброс пароля",
        "Если сброс запрашивал не ты — кто-то пробует войти. Пароль цел, проверь, что 2FA включена.",
        ("password reset", "reset your password", "сброс пароля", "восстановление пароля"),
    ),
    Kind(
        "password_changed", "🚨", "пароль изменён",
        "Если это не ты — восстанавливай доступ немедленно и заверши все сеансы.",
        ("password changed", "password was changed", "password has been changed", "changed your password",
         "пароль изменен", "пароль был изменен", "изменили пароль"),
    ),
    Kind(
        "email_changed", "🚨", "изменена почта аккаунта",
        "Если это не ты — аккаунт уводят: восстанавливай доступ немедленно.",
        ("email address changed", "email was changed", "email address has been changed", "changed your email",
         "адрес электронной почты изменен", "изменен адрес электронной почты", "почта изменена"),
    ),
    Kind(
        "2fa_changed", "🚨", "изменена двухфакторная защита",
        "Если это не ты — верни 2FA и смени пароль.",
        ("2-step verification", "two-step verification", "two-factor", "двухэтапн", "двухфакторн"),
    ),
    Kind(
        "new_login", "🚨", "новый вход в аккаунт",
        "Если это не ты — смени пароль и заверши чужие сеансы.",
        ("new sign-in", "new login", "signed in", "logged in", "new device", "sign-in attempt",
         "login attempt", "новый вход", "выполнен вход", "вход в аккаунт", "новое устройство",
         "попытка входа"),
    ),
    Kind(
        "login_code", "🟠", "пришёл код входа",
        "Если ты не входил — кто-то знает твой пароль: смени его.",
        ("verification code", "login code", "security code", "confirmation code", "one-time code",
         "instagram code", "код подтверждения", "код для входа", "код безопасности", "одноразовый код"),
    ),
    Kind(
        "security_alert", "🟠", "оповещение безопасности",
        "Проверь недавнюю активность в аккаунте.",
        ("security alert", "suspicious", "unusual activity", "оповещение системы безопасности",
         "подозрительн", "необычн"),
    ),
)
GENERIC = KINDS[-1]
# In the body only the specific kinds count: "reset your password" is a footer.
_BODY_KINDS = tuple(k for k in KINDS if k.id not in ("password_reset", "security_alert"))

_FORWARDED_FROM = re.compile(r"(?:^|\n)\s*(?:From|От|De|Von):[^\n]*?([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", re.IGNORECASE)
_FWD_PREFIX = re.compile(r"^\s*(?:(?:fwd?|пересл\.?)\s*:\s*)+", re.IGNORECASE)
_CODE = re.compile(r"\(#(\d+)\)")


@dataclass(frozen=True)
class Mail:
    id: str
    sender: str
    subject: str
    text: str

    @classmethod
    def from_json(cls, raw: dict) -> Mail:
        return cls(
            id=str(raw["id"]),
            sender=str(raw.get("from") or ""),
            subject=str(raw.get("subject") or ""),
            text=str(raw.get("text") or ""),
        )


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


def _match(text: str, kinds: tuple[Kind, ...]) -> Kind | None:
    text = _normalize(text)
    return next((k for k in kinds if any(w in text for w in k.words)), None)


def sender_of(mail: Mail) -> tuple[str, str | None]:
    """(display name, connector id) of the network that sent the notice.

    A hand-forwarded mail comes from the user's own mailbox: the original
    sender is then taken from the forwarded header in the body.
    """
    candidates = [mail.sender] + _FORWARDED_FROM.findall(mail.text[:2000])
    for address in candidates:
        domain = address.rsplit("@", 1)[-1].strip(" <>").lower()
        for suffix, display, platform_id in SENDERS:
            if domain == suffix or domain.endswith("." + suffix):
                return display, platform_id
    return mail.sender.rsplit("@", 1)[-1].strip(" <>").lower() or "?", None


def kind_of(mail: Mail) -> Kind | None:
    """The subject decides; when it only says "security alert", the body may be specific."""
    subject = _FWD_PREFIX.sub("", mail.subject)
    kind = _match(subject, KINDS)
    if kind is None or kind is GENERIC:
        kind = _match(mail.text[:BODY_HEAD], _BODY_KINDS) or kind
    return kind


def _snippet(text: str) -> str:
    text = " ".join(_FWD_PREFIX.sub("", text).split()) or "(без темы)"
    return text if len(text) <= SUBJECT_LEN else text[: SUBJECT_LEN - 1] + "…"


def _forwarding_notice(mail: Mail) -> str:
    """Gmail sends a confirmation to a new forwarding address: relay its code.

    Only the code, never the mail's link: the code is typed into Gmail's own
    settings, so a forged "confirmation" can't turn the bot into a phishing relay.
    """
    code = _CODE.search(mail.subject)
    lines = ["📬 Gmail просит подтвердить пересылку писем на адрес бота."]
    if code:
        lines.append(f"Код подтверждения: {code.group(1)} — введи его в Gmail: Настройки → Пересылка.")
    else:
        lines.append(f"Кода в теме не нашёл: «{_snippet(mail.subject)}»")
    lines.append("Потом создай фильтр по отправителям уведомлений безопасности — см. mail-worker/README.md.")
    return "\n".join(lines)


def describe(mail: Mail) -> tuple[str, Kind | None, str, str | None]:
    """(alert text, kind, network, connector id) for one mail."""
    if mail.sender.lower() == GMAIL_FORWARDING:
        return _forwarding_notice(mail), None, "Gmail", None
    network, platform_id = sender_of(mail)
    kind = kind_of(mail)
    subject = _snippet(mail.subject)
    if kind is None:
        return f"📨 Письмо без признаков тревоги: {network} — «{subject}»", None, network, platform_id
    text = f"{kind.icon} {network}: {kind.title}\n«{subject}»\n{kind.advice}"
    if kind.icon == "🚨" and network in RECOVERY:
        text += f"\nВосстановление доступа: {RECOVERY[network]}"
    return text, kind, network, platform_id


async def _fetch(session: aiohttp.ClientSession, config: Config) -> list[dict] | None:
    try:
        async with session.get(
            f"{config.security_mail_url}/events",
            headers={"Authorization": f"Bearer {config.security_mail_token}"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                logger.warning("Mail worker returned HTTP %s", resp.status)
                return None
            return (await resp.json())["events"]
    except Exception:
        logger.warning("Mail worker poll failed", exc_info=True)
        return None


async def _ack(session: aiohttp.ClientSession, config: Config, ids: list[str]) -> None:
    try:
        async with session.post(
            f"{config.security_mail_url}/events/ack",
            json={"ids": ids},
            headers={"Authorization": f"Bearer {config.security_mail_token}"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                logger.warning("Mail worker ack returned HTTP %s", resp.status)
    except Exception:
        # Not fatal: the next poll gets them again and the uid dedup skips them.
        logger.warning("Mail worker ack failed", exc_info=True)


async def _track_reachability(bot: Bot, config: Config, db: Database, reachable: bool) -> None:
    fails = int(await db.get_setting("mail_fail_streak") or "0")
    if reachable:
        if fails:
            await db.set_setting("mail_fail_streak", "0")
        if fails >= UNREACHABLE_AFTER:
            await bot.send_message(chat_id=config.admin_chat_id, text="✅ Почтовый воркер снова отвечает")
        return
    fails += 1
    await db.set_setting("mail_fail_streak", str(fails))
    if fails == UNREACHABLE_AFTER:
        await bot.send_message(
            chat_id=config.admin_chat_id,
            text=(
                "🔴 Почтовый воркер не отвечает ~30 мин — письма безопасности не доходят. "
                "Проверь SECURITY_MAIL_URL, SECURITY_MAIL_TOKEN и деплой воркера."
            ),
        )


async def check(bot: Bot, config: Config, db: Database, session: aiohttp.ClientSession) -> int:
    """Fetch new mail, alert on each, acknowledge what was handled; returns alerts sent.

    A mail is acknowledged only after its alert went out, so a failed send is
    retried on the next poll; the security log's uid keeps a mail whose ack
    was lost from being alerted twice.
    """
    events = await _fetch(session, config)
    await _track_reachability(bot, config, db, events is not None)
    if not events:
        return 0

    handled: list[str] = []
    sent = 0
    for raw in events:
        try:
            mail = Mail.from_json(raw)
        except (KeyError, TypeError):
            logger.warning("Malformed mail event skipped: %r", raw)
            continue
        uid = f"mail:{mail.id}"
        if await db.has_event(uid):
            handled.append(mail.id)
            continue
        text, kind, network, platform_id = describe(mail)
        if kind is not None and kind.id == "password_changed" and platform_id:
            text += "\n✍️ Дату смены пароля отметил в чек-листе /security."
        try:
            await bot.send_message(chat_id=config.admin_chat_id, text=text, link_preview_options=NO_PREVIEW)
        except Exception:
            logger.exception("Mail alert send failed — will retry on the next poll")
            continue
        sent += 1
        handled.append(mail.id)
        if kind is not None:
            await db.add_event(uid, network, kind.id, text)
            if kind.id == "password_changed" and platform_id:
                await hygiene.mark_password_changed(db, platform_id, utcnow().date())

    if handled:
        await _ack(session, config, handled)
    return sent
