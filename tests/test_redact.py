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
