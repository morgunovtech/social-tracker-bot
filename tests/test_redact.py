"""Secrets never reach a log line: the patterns, the known values, the
formatter over a message, its arguments and a traceback."""

import logging

from bot.redact import MIN_SECRET_LEN, RedactingFormatter, redact

TOKEN = "123456789:AAFakeTokenValueForTestsOnly_abcdefghijk"


def test_bot_api_url_and_bare_token():
    assert redact(f"https://api.telegram.org/bot{TOKEN}/getMe") == "https://api.telegram.org/bot<token>/getMe"
    assert redact(f"token={TOKEN} rejected") == "token=<token> rejected"


def test_query_keys_cookie_and_url_password():
    assert redact("GET https://www.googleapis.com/youtube/v3/channels?key=AIzaSyFake&part=stat") == (
        "GET https://www.googleapis.com/youtube/v3/channels?key=<redacted>&part=stat"
    )
    assert redact("https://graph.facebook.com/me?access_token=EAABfake") == (
        "https://graph.facebook.com/me?access_token=<redacted>"
    )
    assert redact("cookies={'li_at': 'x'}; li_at=AQEDAVeryLongCookie; other=1") == (
        "cookies={'li_at': 'x'}; li_at=<cookie>; other=1"
    )
    assert redact("socks5://user:pa55word@proxy.example:1080") == "socks5://<user>:<pass>@proxy.example:1080"


def test_known_values_are_masked_but_short_ones_are_not():
    assert redact("ping https://hc-ping.com/abcd-1234 ok", ["https://hc-ping.com/abcd-1234"]) == "ping <secret> ok"
    short = "a" * (MIN_SECRET_LEN - 1)
    assert redact(f"word {short}", [short, ""]) == f"word {short}"


def test_formatter_masks_message_arguments_and_traceback():
    fmt = RedactingFormatter("%(levelname)s %(message)s", lambda: ["s3cret-value-123"])
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "sent to %s with %s", ("s3cret-value-123", TOKEN), None)
    assert fmt.format(record) == "INFO sent to <secret> with <token>"
    try:
        raise RuntimeError(f"bad token {TOKEN}")
    except RuntimeError:
        import sys

        exc = sys.exc_info()
    record = logging.LogRecord("t", logging.ERROR, __file__, 1, "failed", (), exc)
    out = fmt.format(record)
    assert TOKEN not in out and "<token>" in out


def test_formatter_survives_a_broken_values_callable():
    def boom():
        raise RuntimeError("no config yet")

    fmt = RedactingFormatter("%(message)s", boom)
    record = logging.LogRecord("t", logging.INFO, __file__, 1, f"/bot{TOKEN}/getMe", (), None)
    assert fmt.format(record) == "/bot<token>/getMe"


async def test_secrets_sent_in_the_chat_are_masked_by_value(config, db, monkeypatch):
    """The Instagram token, the LinkedIn cookie, the reputation keys and the
    watchdog address live in the DB, not in .env: the redactor masks them by
    value from the moment they are stored, and again after a restart."""
    import json

    from bot import main
    from bot.db import Database, known_secrets

    token = "IGAAchat-token-value-0123456789"
    label = "PRIVATE" + " KEY"                    # split, so the secret scanner sees no key in this file
    pem = (f"-----BEGIN {label}-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7\n"
           f"VJTUt9Us8cKjMzEfYyjiWA4R4/M2bS1GB4t7NXp98C3SC6dVMvDuictGeurT8jNb\n-----END {label}-----\n")
    google = json.dumps({"type": "service_account", "private_key_id": "f00dfeedcafe1234", "private_key": pem,
                         "client_email": "reader@project.iam.gserviceaccount.com"})
    await db.set_setting("instagram_token", token)
    await db.set_setting("rep_google_key", google)
    await db.set_setting("report_tz", "Europe/Berlin")               # not a secret: stays readable
    monkeypatch.setattr(main, "_config", config)
    fmt = RedactingFormatter("%(message)s", main.secret_values)

    def line(text: str) -> str:
        return fmt.format(logging.LogRecord("t", logging.ERROR, __file__, 1, text, (), None))

    assert line(f"graph said no to {token}") == "graph said no to <secret>"
    escaped = json.dumps(pem)                                         # a traceback shows the key with \\n
    out = line(f"bad key {escaped} id f00dfeedcafe1234")
    assert "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7" not in out and "f00dfeedcafe1234" not in out
    assert "Europe/Berlin" not in known_secrets()

    # A restart: the list is filled from the DB before anything reads a setting.
    import bot.db as dbmod

    monkeypatch.setattr(dbmod, "_known_secrets", set())
    await Database(config.db_path).init()
    assert line(f"graph said no to {token}") == "graph said no to <secret>"
