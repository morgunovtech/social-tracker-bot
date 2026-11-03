import dataclasses

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

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
    assert text.startswith("🚨 Google: новый вход в аккаунт\n«New sign-in on Windows»")
    assert "https://g.co/recover" in text and platform_id == "youtube"


def test_unrecognized_mail_is_reported_plainly():
    text, kind, *_ = describe(_mail("news@linkedin.com", "5 people viewed your profile"))
    assert kind is None and text.startswith("📨 Письмо без признаков тревоги: LinkedIn")


def test_gmail_forwarding_confirmation_is_relayed():
    m = _mail(
        "forwarding-noreply@google.com", "(#867530912) Gmail Forwarding Confirmation - Receive Mail from me@gmail.com",
        "To allow forwarding click https://mail-settings.google.com/mail/vf-abc123 ...",
    )
    text, kind, *_ = describe(m)
    assert kind is None and "867530912" in text and "https://mail-settings.google.com/mail/vf-abc123" in text


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
    assert bot.messages[0].startswith("🚨 LinkedIn: пароль изменён") and "/security" in bot.messages[0]
    assert await db.get_setting("hygiene_linkedin_pwd") == utcnow().date().isoformat()
    (event,) = await db.recent_events()
    assert event["kind"] == "password_changed"

    worker["acked"].clear()                                  # the ack got lost: the worker re-delivers
    assert await _check(bot, mail_config, db) == 0
    assert len(bot.messages) == 1 and worker["acked"] == ["evt:1"]


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
    worker["status"] = 200
    await _check(bot, mail_config, db)
    assert bot.messages[-1] == "✅ Почтовый воркер снова отвечает"


async def test_malformed_event_is_skipped(bot, mail_config, db, worker):
    worker["events"] += [{"from": "x"}, {"id": "evt:2", "from": "noreply@telegram.org", "subject": "Your login code"}]
    assert await _check(bot, mail_config, db) == 1
    assert worker["acked"] == ["evt:2"]
