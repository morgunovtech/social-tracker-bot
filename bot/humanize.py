"""Human language for what the monitors say about a problem (BOT_PRINCIPLES §3).

Every alert has one shape, top to bottom, the same as TofsDevOps'
services/humanize.py:

    🟠 YouTube: не удаётся собрать данные 2 дн. подряд      ← headline: icon · what · what happened
    В отчёте у YouTube — последнее собранное число. Обычно  ← what it means, what it usually is
    это …
    Что делать:                                             ← two or three steps
    • …
    Тех.: …                                                 ← the technical line last

and a recovery is one message that says how long it lasted, counted from
the first failed check of the series: «✅ Почтовый воркер снова отвечает.
Молчал 40 мин (14:03–14:43). Ничего делать не нужно.»

The monitors keep the facts (bot/monitors/); this module holds the words.
Pure functions: the dictionary is Russian (the lookup key of bot/i18n.py)
and is rendered in the chat language when an alert is built.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.i18n import t


@dataclass(frozen=True)
class Explanation:
    meaning: str             # what it means for the person, for the account
    cause: str               # what it usually is
    steps: tuple[str, ...]   # what to do


_E = Explanation
EXPLANATIONS: dict[str, Explanation] = {
    # bot/monitors/followers.py
    "follower_drop": _E(
        "Подписчиков стало заметно меньше за сутки — больше, чем обычные отписки.",
        "отписки после поста или рекламы, чистка удалённых аккаунтов самой сетью, реже — уход ботов после накрутки",
        ("Посмотреть 📈 Динамику: разовое это падение или тренд.",
         "Сравнить с последними постами — после чего ушли."),
    ),
    "follower_spike": _E(
        "Подписчиков пришло во много раз больше обычного.",
        "репост в большом канале или удачный пост; реже — нагнанные боты: накрутку, которой ты не заказывал, "
        "сеть может наказать",
        ("Если был репост или реклама — всё в порядке.",
         "Если нет — посмотреть, через какую ссылку пришли (📣 Канал) и похожи ли имена на ботов."),
    ),
    # bot/monitors/collection.py
    "run_failed": _E(
        "Числа за эти дни не записаны: не было ни отчёта, ни проверок, которые идут вместе со сбором.",
        "сбой базы или диска на сервере, ошибка в новой версии бота, нет сети у сервера",
        ("Посмотреть логи бота (на Railway — Deployments → View logs).",
         "Если бот недавно обновлялся — откатить деплой и написать в issues."),
    ),
    "linkedin_baseline": _E(
        "Автосбор LinkedIn работает, но первое число нужно сверить: на странице профиля есть и счётчики других "
        "профилей.",
        "так всегда бывает с первым числом по cookie",
        ("Открыть свой профиль LinkedIn и сверить число подписчиков.",
         "Совпадает — подтвердить командой из заголовка; нет — ввести верное: /linkedin <число>."),
    ),
    "cookie_expired": _E(
        "Число LinkedIn больше не собирается само — в отчёте останется последнее.",
        "cookie живёт около года, а выход из LinkedIn в браузере или смена пароля обрывает его раньше",
        ("Войти на linkedin.com и скопировать cookie li_at (DevTools → Application → Cookies).",
         "Прислать его: 🔌 Подключения → 💼 LinkedIn → «🔑 Прислать cookie» или /setcookie. "
         "Или вводить число вручную."),
    ),
    "token_rejected": _E(
        "Число Instagram и проверка профиля остановились.",
        "истёк срок токена, заданный в настройках приложения Meta, или Meta его отозвала: удалили приложение "
        "или тестировщика; реже — сбой у Meta",
        ("developers.facebook.com → приложение → API setup with Unified login → Generate token.",
         "Прислать его: 🔌 Подключения → 📸 Instagram → «🔑 Прислать токен» или /igtoken."),
    ),
    "token_expiring": _E(
        "Через несколько дней Instagram перестанет принимать токен — число и проверка профиля остановятся.",
        "срок токена, заданный в настройках приложения Meta (бывает 60 дней); продлить такой токен без секрета "
        "приложения бот не может",
        ("developers.facebook.com → приложение → API setup with Unified login → Generate token.",
         "Прислать его: 🔌 Подключения → 📸 Instagram → «🔑 Прислать токен» или /igtoken."),
    ),
    "token_missing": _E(
        "Instagram подключён в .env, но число не собирается: токена нет.",
        "токен ещё не присылали или он не пережил восстановление из бэкапа — бэкап делается без секретов",
        ("developers.facebook.com → приложение → API setup with Unified login → Generate token.",
         "Прислать его: 🔌 Подключения → 📸 Instagram → «🔑 Прислать токен» или /igtoken."),
    ),
    "collection_failing": _E(
        "В отчёте — последнее собранное число, свежих нет.",
        "сеть отвечает ошибкой или поменяла страницу или API; у YouTube — кончилась квота ключа или ключ отключён",
        ("Открыть 🔌 Подключения — там видно, чего ждёт сеть.",
         "Не прошло само за пару дней — посмотреть логи бота."),
    ),
    # bot/monitors/profile.py
    "profile_hijack": _E(
        "Так выглядит угон: новый хозяин меняет админов и ссылки, удаляет видео. Если это сделал ты — всё в порядке.",
        "ты сам или другой админ; угон — после фишинговой ссылки, утёкшего пароля или чужого сеанса",
        ("Если это не ты — сменить пароль и завершить чужие сеансы.",
         "Проверить список админов и убрать лишних; включить 2FA (🛡 Безопасность)."),
    ),
    "profile_change": _E(
        "Профиль изменился. С такой правки начинается и обычное обновление, и угон.",
        "ты сам или другой админ",
        ("Если это ты — ничего делать не нужно.",
         "Если нет — сменить пароль, завершить чужие сеансы и проверить админов."),
    ),
    "profile_unreachable": _E(
        "Я не вижу профиль — ни числа, ни его изменений. Угонщик первым делом убирает чужих админов, и меня тоже.",
        "канал удалили, скрыли или сделали приватным, бота убрали из админов или отключили ключ; реже — сбой сети",
        ("Открыть канал: на месте ли он и его админы.",
         "Если бота убрали из админов — вернуть его (особые права не нужны)."),
    ),
    # bot/monitors/links.py
    "link_broken": _E(
        "Кто нажмёт эту ссылку в профиле, попадёт на ошибку, а не к тебе.",
        "страницу удалили или переименовали, домен переехал или истёк, сайт лежит",
        ("Открыть ссылку самому: может, сайт лежит прямо сейчас.",
         "Если адрес сменился — поправить описание в профиле."),
    ),
    # bot/monitors/mail.py
    "mail_silent": _E(
        "Пока воркер молчит, о новом входе или смене пароля я не узнаю.",
        "сменился токен воркера, воркер удалён или не задеплоен, сбой Cloudflare",
        ("Проверить адрес и токен воркера — у бота (🔌 Подключения → ✉️ Письма безопасности) и у воркера они одни.",
         "Обновить воркер: sh mail-worker/update.sh, потом с --deploy (mail-worker/README.md)."),
    ),
    # bot/mailbox.py
    "mailbox_auth": _E(
        "Пока ящик не пускает, письма о новом входе или смене пароля лежат в нём непрочитанными — я о них не знаю.",
        "отозванный или удалённый пароль приложения; Gmail отзывает их сам при смене пароля аккаунта; у Яндекса — "
        "выключенный доступ почтовых программ",
        ("Создать новый пароль приложения для этого ящика и прислать его: 🔌 Подключения → ✉️ Письма безопасности → "
         "«📮 Отдельный ящик».",
         "Яндекс: проверить, что в настройках почты разрешены почтовые программы (IMAP)."),
    ),
    "mailbox_silent": _E(
        "Письма не теряются — они ждут в ящике, и я прочитаю их, когда сервер ответит.",
        "сбой у почтового сервиса или у хостинга бота",
        ("Ничего делать не нужно, если это ненадолго.",
         "Если так весь день — проверить, открывается ли ящик в браузере."),
    ),
    # bot/monitors/outgoing.py
    "push_site": _E(
        "На сайте застыли последние принятые цифры — посетители видят старое число.",
        "сменился SOCIALBOT_INGEST_TOKEN у бота или секрет у сайта, переехал адрес приёма, сайт лежит или не "
        "задеплоился",
        ("Сверить SOCIALBOT_INGEST_TOKEN у бота и секрет сайта — они должны совпадать; новый секрет сайт на "
         "Cloudflare Pages подхватывает только после нового деплоя (Retry deployment).",
         "Проверить SITE_INGEST_URL: после переезда домена адрес приёма мог смениться."),
    ),
    "push_tofs": _E(
        "На главном экране TofsDevOps застыли строки по сетям: он показывает прошлое состояние.",
        "TofsDevOps обновился и не принимает формат, адрес heartbeat удалён или сменился, TofsDevOps не работает",
        ("Открыть ⏱ Сторож и нажать «🔄 Проверить снова».",
         "Если heartbeat в TofsDevOps удалён — создать новый и прислать ссылку здесь."),
    ),
    "push_watchdog": _E(
        "Сторож не слышит меня: скоро он напишет, что я пропал, хотя я работаю, — а если check удалён, не напишет "
        "ничего, когда я правда остановлюсь.",
        "check удалён или поставлен на паузу, ссылка скопирована не целиком, сбой у сервиса сторожа",
        ("Открыть ⏱ Сторож и нажать «🔄 Проверить снова».",
         "Если check удалён — создать новый на healthchecks.io и прислать ссылку."),
    ),
    # bot/monitors/comments.py
    "comments_down": _E(
        "Новые комментарии сейчас никто не смотрит — опасный я пропущу.",
        "кончился баланс API, ключ отозван, или сбой у Anthropic",
        ("Проверить баланс и ключ на console.anthropic.com.",
         "Если всё в порядке — подождать: я напишу, когда проверка снова заработает."),
    ),
    "comments_limit": _E(
        "До конца суток (UTC) новые комментарии не проверяю.",
        "волна спама или очень живое обсуждение",
        ("Посмотреть группу обсуждения: нет ли волны спама.",
         "Поднять лимит — кнопкой на экране 💬 Комментарии (там же — «без лимита»)."),
    ),
}


def explanation(key: str | Explanation) -> Explanation:
    """EXPLANATIONS[key] — or an Explanation of a monitor's own (a mail kind) —
    in the chat language."""
    e = EXPLANATIONS[key] if isinstance(key, str) else key
    return Explanation(t(e.meaning), t(e.cause), tuple(t(step) for step in e.steps))


def tech(*parts: object) -> str:
    """The technical line, last and short: «Тех.: HTTP 500 · 6 опросов подряд»."""
    bits = [str(p) for p in parts if p not in (None, "")]
    return t("Тех.: {details}").format(details=" · ".join(bits)) if bits else ""


def alert(headline: str | Iterable[str], key: str | Explanation, *details: object) -> str:
    """The alert in its one shape. headline — the first line, or several
    lines of one check (the worst first); details — the technical line."""
    head = headline if isinstance(headline, str) else "\n".join(headline)
    e = explanation(key)
    parts = [
        head,
        t("{meaning} Обычно это {cause}.").format(meaning=e.meaning, cause=e.cause),
        t("Что делать:") + "\n" + "\n".join(f"• {step}" for step in e.steps),
    ]
    line = tech(*details)
    if line:
        parts.append(line)
    return "\n\n".join(parts)


def headline(text: str) -> str:
    """The first line of an alert — what a digest or a list shows."""
    return text.split("\n", 1)[0]


# ── Phrases kept for later ─────────────────────────────────────────────────
#
# A line the bot stores and shows again days later (the security log,
# bot/security_log.py) is stored before translation, so it reads in the chat
# language of the day it is shown, not of the day it was written: the Russian
# template — the lookup key of bot/i18n.py — and its values, as JSON:
#
#     {"key": "{icon} {platform}: {field} — «{before}» → «{after}»",
#      "params": {"icon": "🟠", "platform": "Telegram",
#                 "field": {"key": "доступ бота к списку админов"},
#                 "before": {"key": "нет"}, "after": {"key": "есть"}}}
#
# A value that is a phrase itself ({"key": …}) is the bot's own word and is
# translated too; a plain value (a channel title, an admin's name, a number)
# is shown as it was.

Phrase = dict


def phrase(key: str, **params: object) -> Phrase:
    """A Russian template and its values, before translation."""
    return {"key": key, "params": params} if params else {"key": key}


def render(value: Phrase | object) -> str:
    """A phrase in the chat language; a plain value as it is."""
    if not isinstance(value, dict):
        return str(value)
    text = t(str(value.get("key", "")))
    params = value.get("params")
    if not isinstance(params, dict) or not params:
        return text
    try:
        return text.format(**{name: render(v) for name, v in params.items()})
    except (KeyError, IndexError, ValueError):
        return text     # a template from another version that names other values


def dump(value: Phrase) -> str:
    return json.dumps(value, ensure_ascii=False)


def load(raw: str | None) -> Phrase | None:
    """The phrase a stored row holds; None for a row of finished text."""
    if not raw or not raw.startswith("{"):
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("key"), str) else None


# ── Durations and recoveries ───────────────────────────────────────────────

def fmt_duration(minutes: float) -> str:
    """The one duration formatter: «12 мин» · «3 ч 5 мин» · «2 дн. 3 ч»."""
    m = max(1, round(minutes))
    if m < 60:
        return t("{m} мин").format(m=m)
    if m < 24 * 60:
        h, rest = divmod(m, 60)
        return t("{h} ч {m} мин").format(h=h, m=rest) if rest else t("{h} ч").format(h=h)
    d, rest = divmod(m, 24 * 60)
    h = rest // 60
    return t("{d} дн. {h} ч").format(d=d, h=h) if h else t("{d} дн.").format(d=d)


def _clock(at: datetime, tz: ZoneInfo, long: bool) -> str:
    return at.astimezone(tz).strftime("%d.%m %H:%M" if long else "%H:%M")


def span(since: datetime, until: datetime, tz: ZoneInfo) -> str:
    """«40 мин (14:03–14:43)»; dates in the brackets once it is a day or longer."""
    minutes = (until - since).total_seconds() / 60
    long = minutes >= 24 * 60 or since.astimezone(tz).date() != until.astimezone(tz).date()
    return f"{fmt_duration(minutes)} ({_clock(since, tz, long)}–{_clock(until, tz, long)})"


def lasted(
    since: datetime | None, last_failed: datetime | None, now: datetime, tz: ZoneInfo,
    every: timedelta | None = None,
) -> str:
    """How long a problem lasted, from the first failed check of the series to
    the check that saw it fixed. When the checks stopped in between for much
    longer than they run (the bot itself was down), the end is known only from
    below — said so. '' when the start is unknown."""
    if since is None:
        return ""
    if every is not None and last_failed is not None and now - last_failed > 3 * every:
        return t("не меньше {span}; когда именно наладилось — не знаю: с {from_} до {to} я не проверял").format(
            span=span(since, last_failed, tz), from_=_clock(last_failed, tz, False), to=_clock(now, tz, False)
        )
    return span(since, now, tz)


def recovery(head: str, how_long: str, verb: str = "Не работал") -> str:
    """«✅ … снова отвечает. Молчал 40 мин (14:03–14:43). Ничего делать не нужно.»
    verb — «Молчал», «Не читался», «Не собирались»… in Russian, translated here."""
    lines = [f"{head}."]
    if how_long:
        lines.append(t("{verb} {how_long}.").format(verb=t(verb), how_long=how_long))
    lines.append(t("Ничего делать не нужно."))
    return " ".join(lines)
