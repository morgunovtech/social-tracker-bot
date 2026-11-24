import pytest

from bot.config import Config, normalize_dow, normalize_tz


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("sat", "sat"),
        (" Sat ", "sat"),
        ("daily", "*"),
        ("all", "*"),
        ("*", "*"),
        ("mon,thu", "mon,thu"),
        ("mon, thu", "mon,thu"),
        ("MON-FRI", "mon-fri"),
        ("fri-mon", "fri-mon"),
    ],
)
def test_normalize_dow(raw, expected):
    assert normalize_dow(raw) == expected


@pytest.mark.parametrize("raw", ["", "saturday", "mon-xyz", "mon-wed,fri", ",", "1"])
def test_normalize_dow_rejects(raw):
    with pytest.raises(ValueError):
        normalize_dow(raw)


def test_report_dow_from_env_is_normalized(monkeypatch):
    # 'daily' used to be stored as-is and then never matched a report day.
    monkeypatch.setenv("REPORT_DOW", "daily")
    assert Config.from_env().report_dow == "*"


def test_invalid_report_dow_fails_fast(monkeypatch):
    monkeypatch.setenv("REPORT_DOW", "mon-wed,fri")
    with pytest.raises(RuntimeError, match="REPORT_DOW"):
        Config.from_env()


def test_missing_required_variable(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN")
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        Config.from_env()


def test_defaults(monkeypatch):
    for name in (
        "LINKEDIN_STALE_DAYS", "REPORT_HOUR", "REPORT_HOUR_UTC", "REPORT_MINUTE", "REPORT_DOW", "REPORT_TZ", "TIMEZONE",
        "DB_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    config = Config.from_env()
    # The zone follows the chat language: Russian (the default) — Moscow.
    assert (config.report_hour, config.report_minute, config.report_dow, config.report_tz) == (
        8, 0, "sat", "Europe/Moscow",
    )
    assert config.linkedin_stale_days == 7 and config.db_path == "data/followers.db"
    assert config.quiet_if_no_change is False


@pytest.mark.parametrize(
    ("name", "value"),
    [("REPORT_HOUR", "25"), ("REPORT_MINUTE", "60"), ("LINKEDIN_STALE_DAYS", "0"), ("REPORT_HOUR", "eight"),
     ("COMMENTS_DAILY_LIMIT", "-1")],
)
def test_whole_number_variables_fail_fast_with_their_name(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        Config.from_env()


def test_empty_whole_number_variables_mean_the_default(monkeypatch):
    # Every optional variable in .env.example is left empty; these used to crash int("").
    for name in ("REPORT_HOUR", "REPORT_MINUTE", "LINKEDIN_STALE_DAYS", "COMMENTS_DAILY_LIMIT"):
        monkeypatch.setenv(name, "")
    config = Config.from_env()
    assert (config.report_hour, config.report_minute, config.linkedin_stale_days) == (8, 0, 7)
    assert config.comments_daily_limit == 300
    monkeypatch.setenv("COMMENTS_DAILY_LIMIT", "0")
    assert Config.from_env().comments_daily_limit == 0


def test_report_hour_under_its_old_name(monkeypatch):
    monkeypatch.delenv("REPORT_HOUR")
    monkeypatch.setenv("REPORT_HOUR_UTC", "6")
    assert Config.from_env().report_hour == 6


@pytest.mark.parametrize(("lang", "zone"), [("", "Europe/Moscow"), ("ru", "Europe/Moscow"), ("en", "UTC")])
def test_default_zone_follows_the_language(monkeypatch, lang, zone):
    monkeypatch.setenv("REPORT_TZ", "")
    monkeypatch.setenv("BOT_LANG", lang)
    assert Config.from_env().report_tz == zone


def test_timezone_wins_and_report_tz_is_its_alias(monkeypatch):
    monkeypatch.setenv("BOT_LANG", "en")
    monkeypatch.setenv("REPORT_TZ", "Asia/Almaty")             # the name before 1.5.0 still works
    assert Config.from_env().report_tz == "Asia/Almaty"
    monkeypatch.setenv("TIMEZONE", "europe/berlin")
    assert Config.from_env().report_tz == "Europe/Berlin"
    monkeypatch.setenv("TIMEZONE", "Mars/Olympus")
    with pytest.raises(RuntimeError, match="TIMEZONE"):
        Config.from_env()


@pytest.mark.parametrize(("raw", "expected"), [("europe/moscow", "Europe/Moscow"), (" UTC ", "UTC")])
def test_report_tz_is_normalized(monkeypatch, raw, expected):
    monkeypatch.setenv("REPORT_TZ", raw)
    assert Config.from_env().report_tz == expected


@pytest.mark.parametrize("raw", ["Mars/Olympus", "MSK", "Europe", "../etc/passwd"])
def test_invalid_report_tz_fails_fast(monkeypatch, raw):
    monkeypatch.setenv("REPORT_TZ", raw)
    with pytest.raises(RuntimeError, match="REPORT_TZ"):
        Config.from_env()
    with pytest.raises(ValueError):
        normalize_tz(raw)


def test_platforms_are_optional(monkeypatch):
    for name in ("TELEGRAM_CHANNEL_ID", "YOUTUBE_API_KEY", "LINKEDIN_PROFILE_URL"):
        monkeypatch.setenv(name, "")
    config = Config.from_env()
    assert config.enabled_platforms == []
    assert config.site_ingest_url is None              # no author's site as a default

    monkeypatch.setenv("YOUTUBE_API_KEY", "key")       # channel id is still set by conftest
    monkeypatch.setenv("LINKEDIN_PROFILE_URL", "https://www.linkedin.com/in/x/")
    assert Config.from_env().enabled_platforms == ["youtube", "linkedin"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://hc-ping.com/abc", "https://hc-ping.com/abc"),
        # The whole line as TofsDevOps shows it under ⏰ Контроль задач:
        ("&& curl -fsS https://tofs.example/api/heartbeat/s3cr3t/socialtracker",
         "https://tofs.example/api/heartbeat/s3cr3t/socialtracker"),
        ("'https://hc-ping.com/abc'", "https://hc-ping.com/abc"),
        ("", None),
        ("not a url", None),
    ],
)
def test_healthcheck_url_is_extracted(monkeypatch, raw, expected):
    monkeypatch.setenv("HEALTHCHECK_URL", raw)
    assert Config.from_env().healthcheck_url == expected


def test_security_mail_settings(monkeypatch):
    config = Config.from_env()
    assert config.security_mail_url is None and config.security_mail_token is None
    monkeypatch.setenv("SECURITY_MAIL_URL", "https://socialbot-mail.example.workers.dev/")
    monkeypatch.setenv("SECURITY_MAIL_TOKEN", "t")
    assert Config.from_env().security_mail_url == "https://socialbot-mail.example.workers.dev"


def test_admin_chat_id_is_optional(monkeypatch):
    # The first /start claims the bot; the variable only pins the owner.
    monkeypatch.delenv("ADMIN_CHAT_ID")
    assert Config.from_env().admin_chat_id is None
    monkeypatch.setenv("ADMIN_CHAT_ID", " 42 ")
    assert Config.from_env().admin_chat_id == 42
    monkeypatch.setenv("ADMIN_CHAT_ID", "me")
    with pytest.raises(RuntimeError, match="ADMIN_CHAT_ID"):
        Config.from_env()


@pytest.mark.parametrize("raw", ["your_telegram_bot_token", "123456", "123456: abc", "abc:def"])
def test_a_placeholder_token_stops_with_what_to_do(monkeypatch, raw):
    monkeypatch.setenv("BOT_TOKEN", raw)
    with pytest.raises(RuntimeError, match="not a bot token yet") as error:
        Config.from_env()
    assert raw not in str(error.value) or raw == "123456"     # the value itself is never repeated


def test_a_real_looking_token_passes(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", " 123456:ABC-def_ghi ")
    assert Config.from_env().bot_token == "123456:ABC-def_ghi"


def test_main_stops_with_one_readable_line(monkeypatch, caplog):
    """A wrong setting ends the start with one log line, no traceback; a token
    Telegram refuses is not printed (python-telegram-bot puts it in its error)."""
    from telegram.error import InvalidToken

    from bot import main

    monkeypatch.setenv("BOT_TOKEN", "your_telegram_bot_token")
    with pytest.raises(SystemExit) as stop:
        main.main()
    assert stop.value.code == 1 and "not a bot token yet" in caplog.text

    secret = "123456:REAL-TOKEN-WITH-A-TYPO"
    monkeypatch.setenv("BOT_TOKEN", secret)

    class App:
        def run_polling(self, **kwargs):
            raise InvalidToken(f"The token `{secret}` was rejected by the server.")

    monkeypatch.setattr(main, "build_application", lambda config, db: App())
    monkeypatch.setattr(main, "Database", lambda path: object())
    caplog.clear()
    with pytest.raises(SystemExit) as stop:
        main.main()
    assert stop.value.code == 1
    assert "Telegram refused BOT_TOKEN" in caplog.text and secret not in caplog.text
