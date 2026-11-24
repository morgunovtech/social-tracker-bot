import dataclasses
import re
from datetime import timedelta

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from bot import notifier
from bot.db import utcnow
from bot.monitors import mail
from bot.monitors.mail import Mail, describe, kind_of, sender_of


def _mail(sender, subject, text="", id="evt:1"):
    return Mail(id=id, sender=sender, subject=subject, text=text)


# --- classification ----------------------------------------------------------

@pytest.mark.parametrize(
    ("sender", "subject", "text", "network", "kind"),
    [
        ("no-reply@accounts.google.com", "Security alert",
         "New sign-in to your account\nWe noticed a new sign-in on a Mac device.", "Google", "new_login"),
        ("no-reply@accounts.google.com", "Оповещение системы безопасности",
         "Выполнен вход в аккаунт с нового устройства", "Google", "new_login"),
        ("no-reply@accounts.google.com", "2-Step Verification turned off", "", "Google", "2fa_changed"),
        ("security@mail.instagram.com", "123456 is your Instagram code", "", "Instagram", "login_code"),
        ("security-noreply@linkedin.com", "Your password was changed", "", "LinkedIn", "password_changed"),
        ("security@facebookmail.com", "Пароль изменён", "", "Facebook", "password_changed"),
        ("no-reply@account.tiktok.com", "Password reset request", "", "TikTok", "password_reset"),
        ("info@x.com", "Your email address has been changed", "", "X", "email_changed"),
        ("noreply@telegram.org", "Your login code", "", "Telegram", "login_code"),
        ("no-reply@accounts.google.com", "Security alert", "Unusual activity on your account", "Google",
         "security_alert"),
    ],
)
def test_classification(sender, subject, text, network, kind):
    m = _mail(sender, subject, text)
    assert sender_of(m)[0] == network
    assert kind_of(m).id == kind


# Subjects and senders exactly as they arrived in the owner's mailbox (2026-11-24).
@pytest.mark.parametrize(
    ("sender", "subject", "network", "kind"),
    [
        ("noreply@github.com", "[GitHub] Please review this sign in", "GitHub", "new_login"),
        ("noreply@github.com", "[GitHub] Please verify your device", "GitHub", "login_code"),
        ("noreply@github.com", "[GitHub] A personal access token (classic) has been added to your account",
         "GitHub", "new_key"),
        ("noreply@github.com", "[GitHub] A third-party OAuth application has been added to your account",
         "GitHub", "new_key"),
        ("noreply@github.com", "[GitHub] A third-party GitHub Application has been added to your account",
         "GitHub", "new_key"),
        ("noreply@github.com", "[GitHub] A passkey was removed from your account", "GitHub", "2fa_changed"),
        ("account-security-noreply@accountprotection.microsoft.com",
         "Необычные действия при входе в учетную запись Майкрософт", "Microsoft", "new_login"),
        ("account-security-noreply@accountprotection.microsoft.com",
         "Изменение пароля учетной записи Майкрософт", "Microsoft", "password_changed"),
        ("account-security-noreply@accountprotection.microsoft.com",
         "Код безопасности для учетной записи Майкрософт", "Microsoft", "login_code"),
        ("account-security-noreply@accountprotection.microsoft.com",
         "Оповещение о безопасности учетной записи Майкрософт", "Microsoft", "security_alert"),
        ("noreply@id.yandex.ru", "The phone number linked to your Yandex account has been changed", "Yandex",
         "phone_changed"),
        ("noreply@id.yandex.ru", "Вы создали пароль для приложения в аккаунте min***", "Yandex", "new_key"),
        ("noreply@id.yandex.ru", "Вы привязали аккаунт Mos.ru к аккаунту min***", "Yandex", "new_key"),
    ],
)
def test_infrastructure_accounts(sender, subject, network, kind):
    m = _mail(sender, subject)
    assert sender_of(m) == (network, None)
    assert kind_of(m).id == kind


# Subjects from the services' own pages and published copies (sources in bot/monitors/mail.py).
@pytest.mark.parametrize(
    ("sender", "subject", "text", "network", "kind"),
    [
        ("sc-noreply@google.com", "New owner for https://s.morgunov.tech/", "", "Search Console", "new_owner"),
        ("sc-noreply@google.com", "У сайта https://s.morgunov.tech/ появился новый владелец", "", "Search Console",
         "new_owner"),
        ("sc-noreply@google.com", "Search Console", "… has been added as an owner … Message ID: WNC-627102",
         "Search Console", "new_owner"),
        ("devnull@webmaster.yandex.ru", "Яндекс.Вебмастер", "Делегирование прав на управление сайтом",
         "Yandex Webmaster", "new_owner"),
        ("noreply@notify.cloudflare.com", "Your Cloudflare account has been accessed from a new IP address", "",
         "Cloudflare", "new_login"),
        ("noreply@github.com", "[GitHub] Your password has changed", "", "GitHub", "password_changed"),
        ("noreply@github.com", "[GitHub] Your password was reset", "", "GitHub", "password_changed"),
        ("noreply@github.com", "[GitHub] An email address was added to your account.", "", "GitHub",
         "email_changed"),
        ("noreply@github.com", "[GitHub] A new SSH authentication public key was added to your account", "",
         "GitHub", "new_key"),
        ("noreply@github.com", "[GitHub] Please download your two-factor recovery codes", "", "GitHub",
         "2fa_changed"),
    ],
)
def test_infrastructure_accounts_by_their_docs(sender, subject, text, network, kind):
    m = _mail(sender, subject, text)
    assert sender_of(m)[0] == network
    assert kind_of(m).id == kind


def test_a_new_owner_rings_as_a_hijack_sign():
    text, kind, network, _ = describe(_mail("sc-noreply@google.com", "New owner for https://s.morgunov.tech/"))
    assert text.startswith("🔴 Search Console: похоже на взлом — у сайта новый владелец в поиске")
    assert "Пользователи и разрешения" in text and kind.level == "critical"




@pytest.mark.parametrize(
    ("sender", "subject"),
    [
        # Not a security event: no alert, an ℹ️ at most.
        ("noreply@github.com", "[GitHub] Your personal access token (classic) has expired"),
        ("noreply@github.com", "[GitHub] Your personal access token (classic) is about to expire"),
        ("noreply@notify.cloudflare.com", "[Cloudflare]: Verify Email Routing address"),
        ("hello@notify.railway.app", "All aboard! Welcome to Railway!"),
        ("bingwb@microsoft.com", "Improve the search presence of s.morgunov.tech"),
        ("noreply@id.yandex.ru", "Вы удалили карту 986060****5440 из аккаунта min***"),
    ],
)
def test_routine_mail_of_those_accounts_raises_nothing(sender, subject):
    assert kind_of(_mail(sender, subject)) is None


def test_a_whole_address_wins_over_its_domain():
    assert sender_of(_mail("bingwb@microsoft.com", "x")) == ("Bing Webmaster", None)
    assert sender_of(_mail("sc-noreply@google.com", "x")) == ("Search Console", None)
    assert sender_of(_mail("no-reply@accounts.google.com", "x")) == ("Google", "youtube")
    assert sender_of(_mail("noreply@notify.cloudflare.com", "x"))[0] == "Cloudflare"
    assert sender_of(_mail("no-reply@verify.proton.me", "x"))[0] == "Proton"



def test_footer_advice_does_not_decide_the_kind():
    m = _mail(
        "no-reply@accounts.google.com", "Security alert",
        "A new device signed in to your account. If this wasn't you, reset your password.",
    )
    assert kind_of(m).id == "new_login"


def test_hand_forwarded_mail_takes_the_original_sender():
    m = _mail(
        "me@gmail.com", "Fwd: Your password was changed",
        "---------- Forwarded message ---------\nFrom: LinkedIn <security-noreply@linkedin.com>\nDate: ...",
    )
    assert sender_of(m) == ("LinkedIn", "linkedin")
    text, kind, *_ = describe(m)
    assert kind.id == "password_changed" and "«Your password was changed»" in text


def test_lookalike_domain_is_not_trusted():
    assert sender_of(_mail("security@notgoogle.com", "Security alert"))[1] is None


def test_alert_text_has_advice_and_recovery_link():
    text, kind, network, platform_id = describe(_mail("no-reply@accounts.google.com", "New sign-in on Windows"))
    assert text.startswith("🔴 Google: похоже на взлом — новый вход в аккаунт\n«New sign-in on Windows»")
    assert "https://g.co/recover" in text and platform_id == "youtube"


def test_links_in_the_subject_are_defanged():
    text, *_ = describe(_mail("no-reply@accounts.google.com", "New sign-in: verify at https://evil.example/login"))
    assert "hxxps://evil[.]example/login" in text and "https://evil" not in text
    assert "https://g.co/recover" in text                  # our own recovery link stays clickable


def test_unrecognized_mail_is_reported_plainly():
    text, kind, *_ = describe(_mail("news@linkedin.com", "5 people viewed your profile"))
    assert kind is None and text.startswith("ℹ️ Письмо без признаков тревоги: LinkedIn")


def test_an_unknown_sender_domain_is_not_a_link():
    text, kind, network, _ = describe(_mail("promo@win-prize.example", "Hello"))
    assert network == "win-prize[.]example" and "win-prize.example" not in text


def test_gmail_forwarding_confirmation_is_relayed():
    m = _mail(
        "forwarding-noreply@google.com", "(#867530912) Gmail Forwarding Confirmation - Receive Mail from me@gmail.com",
        "To allow forwarding click https://mail-settings.google.com/mail/vf-abc123 ...",
    )
    text, kind, *_ = describe(m)
    assert kind is None and "867530912" in text
    assert "https://" not in text                         # a forged confirmation can't relay a link


# --- polling the worker ------------------------------------------------------

@pytest.fixture
async def worker():
    """A fake mail-worker: queued events, acks recorded, status switchable."""
    state = {"events": [], "acked": [], "status": 200, "auth": []}

    async def events(request):
        state["auth"].append(request.headers.get("Authorization"))
        if state["status"] != 200:
            return web.json_response({"error": "down"}, status=state["status"])
        return web.json_response({"events": [e for e in state["events"] if e.get("id") not in state["acked"]]})

    async def ack(request):
        state["acked"] += (await request.json())["ids"]
        return web.json_response({"deleted": 1})

    app = web.Application()
    app.router.add_get("/events", events)
    app.router.add_post("/events/ack", ack)
    server = TestServer(app)
    await server.start_server()
    state["url"] = str(server.make_url("")).rstrip("/")
    yield state
    await server.close()


@pytest.fixture
def mail_config(config, worker):
    return dataclasses.replace(config, security_mail_url=worker["url"], security_mail_token="s3cret")


async def _check(bot, cfg, db):
    async with aiohttp.ClientSession() as session:
        return await mail.check(bot, cfg, db, session)


async def test_alert_ack_and_no_duplicate_on_redelivery(bot, mail_config, db, worker):
    worker["events"].append({"id": "evt:1", "from": "security-noreply@linkedin.com",
                             "subject": "Your password was changed", "text": ""})
    assert await _check(bot, mail_config, db) == 1
    assert worker["auth"][0] == "Bearer s3cret" and worker["acked"] == ["evt:1"]
    assert bot.messages[0].startswith("🔴 LinkedIn: похоже на взлом — пароль изменён") and "/security" in bot.messages[0]
    assert await db.get_setting("hygiene_linkedin_pwd") == utcnow().date().isoformat()
    (event,) = await db.recent_events()
    assert event["kind"] == "password_changed"

    worker["acked"].clear()                                  # the ack got lost: the worker re-delivers
    assert await _check(bot, mail_config, db) == 0
    assert len(bot.messages) == 1 and worker["acked"] == ["evt:1"]


async def test_a_sign_in_rings_a_login_code_waits(bot, mail_config, db, worker):
    await notifier.set_mute(db, timedelta(hours=1))
    worker["events"] += [
        {"id": "evt:1", "from": "no-reply@accounts.google.com", "subject": "Security alert",
         "text": "New sign-in on Windows"},
        {"id": "evt:2", "from": "security@mail.instagram.com", "subject": "123456 is your Instagram code", "text": ""},
    ]
    assert await _check(bot, mail_config, db) == 2
    assert bot.silent == [False] and bot.messages[0].startswith("🔴 Google: похоже на взлом — новый вход")
    (held,) = await db.peek_notifications()
    assert held["text"].startswith("🟠 Instagram: пришёл код входа")
    assert sorted(worker["acked"]) == ["evt:1", "evt:2"]              # queued counts as handled


async def test_unrecognized_mail_is_not_realerted_and_stays_out_of_events(bot, mail_config, db, worker):
    worker["events"].append({"id": "evt:1", "from": "news@linkedin.com", "subject": "5 people viewed your profile"})
    assert await _check(bot, mail_config, db) == 1
    worker["acked"].clear()
    assert await _check(bot, mail_config, db) == 0
    assert len(bot.messages) == 1 and await db.recent_events() == []


async def test_failed_send_is_not_acknowledged(bot, mail_config, db, worker):
    worker["events"].append({"id": "evt:1", "from": "no-reply@accounts.google.com", "subject": "New sign-in"})

    async def broken(*args, **kwargs):
        raise RuntimeError("Telegram is down")

    bot.send_message = broken
    assert await _check(bot, mail_config, db) == 0
    assert worker["acked"] == [] and await db.recent_events() == []


async def test_unreachable_worker_alerted_once_then_recovery(bot, mail_config, db, worker):
    worker["status"] = 500
    for _ in range(mail.UNREACHABLE_AFTER + 2):
        await _check(bot, mail_config, db)
    assert len(bot.messages) == 1 and bot.messages[0].startswith("🔴 Почтовый воркер не отвечает")
    # 🔴: while the worker is silent a hijack sign reaches nobody — the alert rings.
    assert bot.silent == [False]
    assert "Что делать:" in bot.messages[0] and "Тех.: HTTP 500 · 6 опросов подряд" in bot.messages[0]
    since = utcnow() - timedelta(minutes=40)
    await db.set_setting("mail_fail_since", since.isoformat())                    # the first failed poll
    worker["status"] = 200
    await _check(bot, mail_config, db)
    # One message with how long it was silent; after a 🔴 silence the return rings too.
    assert re.fullmatch(r"✅ Почтовый воркер снова отвечает\. Молчал 40 мин \(\d\d:\d\d–\d\d:\d\d\)\. "
                        r"Ничего делать не нужно\.", bot.messages[-1]), bot.messages[-1]
    assert bot.silent == [False, False]


async def test_a_return_after_the_bot_itself_was_down_says_so(bot, mail_config, db, worker):
    worker["status"] = 500
    for _ in range(mail.UNREACHABLE_AFTER):
        await _check(bot, mail_config, db)
    now = utcnow()
    await db.set_setting("mail_fail_since", (now - timedelta(hours=5)).isoformat())
    await db.set_setting("mail_fail_last", (now - timedelta(hours=3)).isoformat())   # no polls for three hours
    worker["status"] = 200
    await _check(bot, mail_config, db)
    assert "Молчал не меньше 2 ч" in bot.messages[-1] and "я не проверял" in bot.messages[-1]


async def test_malformed_event_is_skipped(bot, mail_config, db, worker):
    worker["events"] += [{"from": "x"}, {"id": "evt:2", "from": "noreply@telegram.org", "subject": "Your login code"}]
    assert await _check(bot, mail_config, db) == 1
    assert worker["acked"] == ["evt:2"]
