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
        "LINKEDIN_STALE_DAYS", "REPORT_HOUR", "REPORT_HOUR_UTC", "REPORT_MINUTE", "REPORT_DOW", "REPORT_TZ", "DB_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    config = Config.from_env()
    assert (config.report_hour, config.report_minute, config.report_dow, config.report_tz) == (8, 0, "sat", "UTC")
    assert config.linkedin_stale_days == 7 and config.db_path == "data/followers.db"
    assert config.quiet_if_no_change is False


def test_report_hour_under_its_old_name(monkeypatch):
    monkeypatch.delenv("REPORT_HOUR")
    monkeypatch.setenv("REPORT_HOUR_UTC", "6")
    assert Config.from_env().report_hour == 6


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
