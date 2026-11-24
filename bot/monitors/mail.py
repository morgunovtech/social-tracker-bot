"""Security emails: new sign-ins, password, email, phone and 2FA changes, new
keys and tokens, login codes.

The user forwards the security notifications of their accounts (a mail
filter on the sender) to the mail-worker address; the worker keeps them
until the bot fetches and acknowledges them. Classification lives here:
the worker only stores sender, subject and the start of the text.

The accounts are the social networks and the infrastructure that holds the
products and the domain — GitHub, Cloudflare, Railway, Proton, Microsoft
(Bing), Yandex. Every sender and every phrase below was taken from a real
mail or the service's own documentation, never guessed: a rule that matches
nothing is silence that looks like safety.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import aiohttp
from telegram import Bot

from bot import humanize, notifier
from bot.callbacks import SECURITY
from bot.config import Config
from bot.db import Database, parse_utc, utcnow
from bot.i18n import t
from bot.monitors import HIJACK, defang, hygiene, level_icon
from bot.notifier import Priority

logger = logging.getLogger(__name__)

# 288 polls a day: each is a KV list, and Cloudflare's free plan allows 1,000 lists a day.
POLL_INTERVAL = timedelta(minutes=5)
# Consecutive failed polls before the worker is reported unreachable (~30 min).
UNREACHABLE_AFTER = 6
SUBJECT_LEN = 150
# Only the start of the body is searched: footers say "if this wasn't you,
# reset your password" under every kind of notice.
BODY_HEAD = 600

# Sender (a whole address, or a domain matched as a suffix) -> display name
# and the connector whose checklist a password change updates (None: an
# account without a connector). A whole address comes before its domain:
# Search Console and Bing Webmaster write from google.com and microsoft.com.
# Seen in real mail (2026-11-24): noreply@github.com, noreply@notify.cloudflare.com,
# hello@notify.railway.app, no-reply@verify.proton.me, no-reply@mail.proton.me,
# account-security-noreply@accountprotection.microsoft.com, bingwb@microsoft.com,
# noreply@id.yandex.ru, sc-noreply@google.com. From the services' own pages:
# noreply@notify.cloudflare.com («all email notifications from Cloudflare»),
# devnull@webmaster.yandex.ru (Yandex.Webmaster's notifications).
SENDERS: tuple[tuple[str, str, str | None], ...] = (
    ("sc-noreply@google.com", "Search Console", None),
    ("bingwb@microsoft.com", "Bing Webmaster", None),
    ("google.com", "Google", "youtube"),
    ("youtube.com", "YouTube", "youtube"),
    ("linkedin.com", "LinkedIn", "linkedin"),
    ("telegram.org", "Telegram", "telegram"),
    ("instagram.com", "Instagram", "instagram"),
    ("facebookmail.com", "Facebook", None),
    ("tiktok.com", "TikTok", None),
    ("x.com", "X", None),
    ("twitter.com", "X", None),
    ("github.com", "GitHub", None),
    ("cloudflare.com", "Cloudflare", None),
    ("railway.app", "Railway", None),
    ("proton.me", "Proton", None),
    ("microsoft.com", "Microsoft", None),
    ("webmaster.yandex.ru", "Yandex Webmaster", None),
    ("yandex.ru", "Yandex", None),
)

RECOVERY = {
    "Google": "https://g.co/recover",
    "YouTube": "https://g.co/recover",
    "Instagram": "https://www.instagram.com/hacked/",
    "Facebook": "https://www.facebook.com/hacked",
}

GMAIL_FORWARDING = "forwarding-noreply@google.com"
FORWARDING_HEAD = "📬 Gmail просит подтвердить пересылку писем на адрес бота."


@dataclass(frozen=True)
class Kind:
    id: str
    level: str   # "critical" — a hijack sign, rings; "warning" — waits for the digest
    title: str   # what happened, for the headline
    meaning: str
    cause: str   # what it usually is
    advice: str  # what to do
    words: tuple[str, ...]


KINDS: tuple[Kind, ...] = (
    Kind(
        "password_reset", "critical", "запрошен сброс пароля",
        "Кто-то попросил сбросить пароль аккаунта.",
        "ты сам; если нет — кто-то знает твою почту или логин и пробует войти",
        "Если сброс запросил кто-то другой — значит, пробуют войти. Пароль цел, проверь, что 2FA включена.",
        ("password reset", "reset your password", "сброс пароля", "восстановление пароля"),
    ),
    Kind(
        "password_changed", "critical", "пароль изменён",
        "Пароль аккаунта сменили.",
        "ты сам; если нет — аккаунт уже уводят",
        "Если это не ты — восстанавливай доступ немедленно и заверши все сеансы.",
        ("password changed", "password was changed", "password has been changed", "changed your password",
         "пароль изменен", "пароль был изменен", "изменили пароль",
         "изменение пароля",                                # Microsoft: «Изменение пароля учетной записи Майкрософт»
         "password has changed", "password was reset"),     # GitHub: «Your password has changed», «…was reset»
    ),
    Kind(
        "email_changed", "critical", "изменена почта аккаунта",
        "Сменили почту, на которую приходят входы и сброс пароля.",
        "ты сам; если нет — это главный шаг угона: дальше пароль сбросят на чужую почту",
        "Если это не ты — аккаунт уводят: восстанавливай доступ немедленно.",
        ("email address changed", "email was changed", "email address has been changed", "changed your email",
         "адрес электронной почты изменен", "изменен адрес электронной почты", "почта изменена",
         "email address was added"),                        # GitHub: «An email address was added to your account.»
    ),
    Kind(
        "phone_changed", "critical", "изменён телефон аккаунта",
        "Сменили номер телефона, на который приходят коды входа и восстановления.",
        "ты сам — новый номер; если нет — угонщик забирает восстановление себе",
        "Если это не ты — восстанавливай доступ немедленно: с чужим номером пароль сбросят без тебя.",
        # Yandex ID: «The phone number linked to your Yandex account has been changed».
        ("phone number linked", "phone number has been changed", "номер телефона изменен",
         "изменен номер телефона"),
    ),
    Kind(
        "2fa_changed", "critical", "изменена двухфакторная защита",
        "Двухфакторную защиту выключили или сменили.",
        "ты сам; если нет — угонщик убирает второй ключ",
        "Если это не ты — верни 2FA и смени пароль.",
        ("2-step verification", "two-step verification", "two-factor", "двухэтапн", "двухфакторн",
         "passkey"),                                        # GitHub: «A passkey was removed from your account»
    ),
    Kind(
        "new_owner", "critical", "у сайта новый владелец в поиске",
        "У сайта появился ещё один подтверждённый владелец в панели поисковика: он может убрать страницы из "
        "поиска, поменять настройки и видеть статистику.",
        "ты сам — подтвердил сайт заново или другим способом, подключил сервис; если нет — у кого-то есть доступ "
        "к DNS или файлам сайта",
        "Если это не ты — удали чужого владельца в настройках ресурса (Search Console: Настройки → Пользователи "
        "и разрешения) и убери его код подтверждения — запись DNS или файл, иначе права вернутся.",
        # Search Console: «New owner for example.com», «У сайта example.com появился новый владелец», and the
        # message id WNC-627102 in the body of every language (support.google.com/webmasters/answer/140528).
        # Yandex.Webmaster names the notification «Делегирование прав на управление сайтом» (its help pages);
        # no sample of the mail itself yet. Bing Webmaster: no public sample — not matched.
        ("new owner for", "появился новый владелец", "wnc-627102", "делегирование прав"),
    ),
    Kind(
        "new_key", "critical", "добавлен ключ, токен или приложение",
        "В аккаунт добавили новый способ входить без пароля: токен, ключ, пароль приложения или стороннее "
        "приложение с доступом.",
        "ты сам — для бота, деплоя или нового сервиса; если нет — угонщик закрепляется: такой ключ переживёт "
        "смену пароля",
        "Если это не ты — отзови ключ или приложение в настройках безопасности аккаунта, потом смени пароль.",
        # GitHub: «A personal access token (classic) has been added to your account», «A third-party OAuth
        # application has been added…»; Yandex ID: «Вы создали пароль для приложения…», «Вы привязали аккаунт…».
        ("added to your account", "пароль для приложения", "привязали аккаунт"),
    ),
    Kind(
        "new_login", "critical", "новый вход в аккаунт",
        "В аккаунт вошли с нового устройства или из нового места.",
        "ты сам — новый телефон, браузер или VPN",
        "Если это не ты — смени пароль и заверши чужие сеансы.",
        ("new sign-in", "new login", "signed in", "logged in", "new device", "sign-in attempt",
         "login attempt", "новый вход", "выполнен вход", "вход в аккаунт", "новое устройство",
         "попытка входа",
         "review this sign in",                             # GitHub: «Please review this sign in»
         "accessed from a new ip",                          # Cloudflare: «…has been accessed from a new IP address»
         "unusual sign-in", "действия при входе"),          # Microsoft: «Необычные действия при входе…»
    ),
    Kind(
        "login_code", "warning", "пришёл код входа",
        "Сервис прислал код для входа.",
        "ты сам входишь; если нет — кто-то знает пароль и упёрся в код",
        "Если код запрашивал не ты — кто-то знает твой пароль: смени его.",
        ("verification code", "login code", "security code", "confirmation code", "one-time code",
         "instagram code", "код подтверждения", "код для входа", "код безопасности", "одноразовый код",
         "verify your device"),                             # GitHub: a sign-in from a new device, by code
    ),
    Kind(
        "security_alert", "warning", "оповещение безопасности",
        "Сервис заметил в аккаунте что-то необычное.",
        "новый вход, смена настроек или подозрительная активность",
        "Проверь недавнюю активность в аккаунте.",
        ("security alert", "suspicious", "unusual activity", "оповещение системы безопасности",
         "оповещение о безопасности",                       # Microsoft: «Оповещение о безопасности учетной записи…»
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
        address = address.strip(" <>").lower()
        domain = address.rsplit("@", 1)[-1]
        for suffix, display, platform_id in SENDERS:
            if "@" in suffix:
                if address == suffix:
                    return display, platform_id
            elif domain == suffix or domain.endswith("." + suffix):
                return display, platform_id
    # An unknown sender is anyone's text: its domain must not be a link.
    return defang(mail.sender.rsplit("@", 1)[-1].strip(" <>").lower()) or "?", None


def kind_of(mail: Mail) -> Kind | None:
    """The subject decides; when it only says "security alert", the body may be specific."""
    subject = _FWD_PREFIX.sub("", mail.subject)
    kind = _match(subject, KINDS)
    if kind is None or kind is GENERIC:
        kind = _match(mail.text[:BODY_HEAD], _BODY_KINDS) or kind
    return kind


def _subject(text: str) -> humanize.Phrase | str:
    """The subject as quoted in an alert. Anyone who learns the worker's
    address can write it, so its links are defanged; no subject is the bot's
    own «(без темы)», translated where it is shown."""
    text = " ".join(_FWD_PREFIX.sub("", text).split())
    if not text:
        return humanize.phrase("(без темы)")
    return defang(text if len(text) <= SUBJECT_LEN else text[: SUBJECT_LEN - 1] + "…")


def _snippet(text: str) -> str:
    return humanize.render(_subject(text))


def _forwarding_notice(mail: Mail) -> str:
    """Gmail sends a confirmation to a new forwarding address: relay its code.

    Only the code, never the mail's link: the code is typed into Gmail's own
    settings, so a forged "confirmation" can't turn the bot into a phishing relay.
    """
    code = _CODE.search(mail.subject)
    lines = [t(FORWARDING_HEAD)]
    if code:
        lines.append(
            t("Код подтверждения: {code} — введи его в Gmail: Настройки → Пересылка.").format(code=code.group(1))
        )
    else:
        lines.append(t("Кода в теме не нашёл: «{subject}»").format(subject=_snippet(mail.subject)))
    lines.append(t("Потом создай фильтр по отправителям уведомлений безопасности — см. mail-worker/README.md."))
    return "\n".join(lines)


def _sender_domain(mail: Mail) -> str:
    return defang(mail.sender.rsplit("@", 1)[-1].strip(" <>").lower()) or "?"


def headline(mail: Mail) -> humanize.Phrase:
    """The first line of the mail's alert before translation — what the
    security log keeps (bot/security_log.py)."""
    if mail.sender.lower() == GMAIL_FORWARDING:
        return humanize.phrase(FORWARDING_HEAD)
    network, _ = sender_of(mail)
    kind = kind_of(mail)
    if kind is None:
        return humanize.phrase("ℹ️ Письмо без признаков тревоги: {network} — «{subject}»", network=network,
                               subject=_subject(mail.subject))
    # A hijack sign says so in its headline; the icon alone is only «act now».
    if kind.level == "critical":
        return humanize.phrase("{icon} {network}: {hijack} — {title}", icon=level_icon(kind.level), network=network,
                               hijack=humanize.phrase(HIJACK), title=humanize.phrase(kind.title))
    return humanize.phrase("{icon} {network}: {title}", icon=level_icon(kind.level), network=network,
                           title=humanize.phrase(kind.title))


def describe(mail: Mail) -> tuple[str, Kind | None, str, str | None]:
    """(alert text, kind, network, connector id) for one mail: the headline
    and the quoted subject, what it means, what it usually is, what to do
    (with the network's recovery page for a hijack sign), the sender last."""
    if mail.sender.lower() == GMAIL_FORWARDING:
        return _forwarding_notice(mail), None, "Gmail", None
    network, platform_id = sender_of(mail)
    kind = kind_of(mail)
    head = humanize.render(headline(mail))
    if kind is None:
        return head, None, network, platform_id
    subject = _snippet(mail.subject)
    steps = [kind.advice]
    if kind.level == "critical" and network in RECOVERY:
        steps.append(t("Восстановление доступа: {url}").format(url=RECOVERY[network]))
    text = humanize.alert(
        [head, t("«{subject}»").format(subject=subject)],
        humanize.Explanation(kind.meaning, kind.cause, tuple(steps)),
        t("письмо от {domain}").format(domain=_sender_domain(mail)),
    )
    return text, kind, network, platform_id


async def _fetch(session: aiohttp.ClientSession, config: Config) -> tuple[list[dict] | None, str]:
    """(events, '') — or (None, why not, for the technical line)."""
    try:
        async with session.get(
            f"{config.security_mail_url}/events",
            headers={"Authorization": f"Bearer {config.security_mail_token}"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                logger.warning("Mail worker returned HTTP %s", resp.status)
                return None, f"HTTP {resp.status}"
            return (await resp.json())["events"], ""
    except Exception as e:
        logger.warning("Mail worker poll failed", exc_info=True)
        return None, type(e).__name__


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


def _when(raw: str | None) -> datetime | None:
    try:
        return parse_utc(raw) if raw else None
    except ValueError:
        return None


async def _track_reachability(bot: Bot, config: Config, db: Database, error: str | None) -> None:
    """error — None when the worker answered. The silence is alerted once, at
    the UNREACHABLE_AFTER-th failed poll; the answer after it says how long
    the worker was silent, from the first failed poll of the series."""
    fails = int(await db.get_setting("mail_fail_streak") or "0")
    now = utcnow()
    if error is None:
        if fails:
            await db.set_setting("mail_fail_streak", "0")
        if fails >= UNREACHABLE_AFTER:
            how_long = humanize.lasted(
                _when(await db.get_setting("mail_fail_since")), _when(await db.get_setting("mail_fail_last")),
                now, await notifier.owner_tz(db, config), POLL_INTERVAL,
            )
            # After a 🔴 silence the return rings too (BOT_PRINCIPLES §1).
            await notifier.send(
                bot, config, db, humanize.recovery(t("✅ Почтовый воркер снова отвечает"), how_long, "Молчал"),
                Priority.CRITICAL, monitor="mail",
            )
        return
    if fails == 0:
        await db.set_setting("mail_fail_since", now.isoformat())
    await db.set_setting("mail_fail_last", now.isoformat())
    fails += 1
    await db.set_setting("mail_fail_streak", str(fails))
    if fails == UNREACHABLE_AFTER:
        # 🔴: while the worker is silent, a new sign-in or a changed password
        # reaches nobody — the one thing this monitor is for.
        await notifier.send(
            bot, config, db,
            humanize.alert(
                t("🔴 Почтовый воркер не отвечает ~30 мин — письма безопасности не доходят"), "mail_silent",
                error, t("{n} опросов подряд, раз в 5 мин").format(n=fails),
            ),
            Priority.CRITICAL,
            monitor="mail",
        )


async def check(bot: Bot, config: Config, db: Database, session: aiohttp.ClientSession) -> int:
    """Fetch new mail, alert on each, acknowledge what was handled; returns alerts sent.

    A mail is acknowledged only after its alert went out, so a failed send is
    retried on the next poll; the security log's uid keeps a mail whose ack
    was lost from being alerted twice.
    """
    events, error = await _fetch(session, config)
    await _track_reachability(bot, config, db, None if events is not None else error or "?")
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
            text += "\n" + t("✍️ Дата смены пароля отмечена в чек-листе /security.")
        # A critical kind (a new sign-in, a changed password) rings through quiet
        # hours and /mute; a login code or an unrecognised mail waits for the digest.
        priority = Priority.CRITICAL if kind is not None and kind.level == "critical" else Priority.NORMAL
        try:
            await notifier.send(bot, config, db, text, priority, no_preview=True, actions=(SECURITY,), monitor="mail")
        except Exception:
            logger.exception("Mail alert send failed — will retry on the next poll")
            continue
        sent += 1
        handled.append(mail.id)
        # Every handled mail is logged, so none is alerted twice; "info" ones
        # (unrecognized, Gmail's confirmation) stay out of /security's events.
        # The log keeps the headline before translation (bot/security_log.py).
        await db.add_event(uid, network, kind.id if kind else "info", humanize.dump(headline(mail)))
        if kind is not None and kind.id == "password_changed" and platform_id:
            await hygiene.mark_password_changed(db, platform_id, utcnow().date())

    if handled:
        await _ack(session, config, handled)
    return sent
