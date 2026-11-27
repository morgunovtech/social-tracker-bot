"""1.13.0: the comment check's Claude key and daily limit from the chat, what
the check costs, and the developer's notices as a monitor that a new install
starts without."""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from conftest import buttons
from telegram.ext import ConversationHandler

from bot import behavior, classifier, connections, handlers, monitors, ui, updates
from bot.classifier import Sample, Usage
from bot.monitors import comments

KEY = "sk-ant-api03-" + "k" * 40
OTHER_KEY = "sk-ant-api03-" + "o" * 40


@pytest.fixture
def keyless(config):
    return dataclasses.replace(config, anthropic_api_key=None)


@pytest.fixture
def ctx(make_context, keyless):
    context = make_context()
    context.bot_data["config"] = keyless
    return context


async def _send(make_update, context, *texts: str):
    start = make_update(callback="cm:key")
    assert await handlers.input_conv_start(start, context) == handlers.AWAITING_INPUT
    assert "console.anthropic.com" in start.callback_query.edits[0]
    update = state = None
    for text in texts:
        update = make_update(text=text)
        state = await handlers.input_conv_value(update, context)
    return update, state


# ── The key ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("raw", "expected"), [
    (KEY, KEY), (f"  {KEY[:20]} {KEY[20:]}\n", KEY),           # spaces a copy brought along
    ("sk-ant-short", None), ("AIza" + "x" * 35, None), ("", None),
])
def test_what_looks_like_a_claude_key(raw, expected):
    assert connections.anthropic_key(raw) == expected


async def test_a_key_that_works_is_kept_secret_and_used_at_once(make_update, ctx, keyless, db, monkeypatch):
    checked = []

    async def check(key, model):
        checked.append((key, model))
        return classifier.KEY_OK

    monkeypatch.setattr(classifier, "check_key", check)
    update, state = await _send(make_update, ctx, KEY)
    assert state == ConversationHandler.END and update.message.deleted
    assert checked == [(KEY, keyless.comments_model)] and keyless.anthropic_api_key == KEY
    assert update.message.replies[0].startswith("✅ Ключ Claude принят")
    assert "🔑 Ключ Claude: задан в чате" in update.message.replies[0]
    assert KEY not in "".join(update.message.replies + update.effective_chat.sent)

    restarted = dataclasses.replace(keyless)
    await connections.restore(restarted, db)
    assert restarted.anthropic_api_key == KEY


@pytest.mark.parametrize(("answer", "said"), [
    (classifier.KEY_REFUSED, "Ключ не принят"),
    (classifier.KEY_NO_ACCESS, "нет доступа"),
    (classifier.KEY_NO_MODEL, "модель claude-opus-5-5 ему недоступна"),
    (classifier.KEY_UNCHECKED, "⚠️ Не смог проверить ключ"),
])
async def test_a_key_that_does_not_work_is_not_kept(make_update, ctx, keyless, monkeypatch, answer, said):
    async def check(key, model):
        return answer

    monkeypatch.setattr(classifier, "check_key", check)
    update, state = await _send(make_update, ctx, KEY)
    assert state == handlers.AWAITING_INPUT and update.message.deleted
    assert said in update.effective_chat.sent[0] and keyless.anthropic_api_key is None


async def test_not_a_key_is_not_even_checked(make_update, ctx, keyless, monkeypatch):
    async def check(key, model):
        raise AssertionError("checked")

    monkeypatch.setattr(classifier, "check_key", check)
    update, state = await _send(make_update, ctx, "hello")
    assert state == handlers.AWAITING_INPUT and "sk-ant-" in update.effective_chat.sent[0]


async def test_a_dash_brings_the_hosting_key_back(make_update, make_context, config, db, monkeypatch):
    async def check(key, model):
        return classifier.KEY_OK

    monkeypatch.setattr(classifier, "check_key", check)
    env_key = config.anthropic_api_key
    context = make_context()
    await _send(make_update, context, OTHER_KEY)
    assert config.anthropic_api_key == OTHER_KEY
    update, state = await _send(make_update, context, "-")
    assert state == ConversationHandler.END and config.anthropic_api_key == env_key
    assert update.message.replies[0].startswith("Убрал ключ, заданный в чате")


async def test_the_key_stays_out_of_the_backup(config, db, tmp_path):
    await connections.save(config, db, anthropic_api_key=KEY)
    path = str(tmp_path / "backup.db")
    await db.snapshot_without_secrets(path)
    with sqlite3.connect(path) as conn:
        kept = dict(conn.execute("SELECT key, value FROM settings WHERE key LIKE 'conn_%'").fetchall())
    assert "conn_anthropic_api_key" not in kept


def test_a_new_key_makes_a_new_client(config, monkeypatch):
    made = []
    monkeypatch.setattr(classifier, "make_client", lambda key: made.append(key) or object())
    watch = comments.Watch()
    with_key = dataclasses.replace(config, anthropic_api_key=KEY)
    first = comments._client(with_key, watch)
    assert comments._client(with_key, watch) is first
    object.__setattr__(with_key, "anthropic_api_key", OTHER_KEY)
    assert comments._client(with_key, watch) is not first and made == [KEY, OTHER_KEY]


async def test_check_key_reads_the_model_and_names_what_failed(monkeypatch):
    import httpx2 as httpx

    def error(cls, status):
        response = httpx.Response(status, request=httpx.Request("GET", "https://api.anthropic.com/v1/models/x"))
        return cls("no", response=response, body=None)

    outcomes = [None, error(classifier.anthropic.AuthenticationError, 401),
                error(classifier.anthropic.PermissionDeniedError, 403), error(classifier.anthropic.NotFoundError, 404),
                error(classifier.anthropic.InternalServerError, 500)]

    class Models:
        async def retrieve(self, model):
            outcome = outcomes.pop(0)
            if outcome is not None:
                raise outcome

    class Client:
        models = Models()
        closed = 0

        async def close(self):
            Client.closed += 1

    monkeypatch.setattr(classifier, "make_client", lambda key: Client())
    answers = [await classifier.check_key(KEY, "claude-opus-5-5") for _ in range(5)]
    assert answers == [classifier.KEY_OK, classifier.KEY_REFUSED, classifier.KEY_NO_ACCESS,
                       classifier.KEY_NO_MODEL, classifier.KEY_UNCHECKED]
    assert Client.closed == 5


# ── What it costs ───────────────────────────────────────────────────────────

def test_prices_and_names():
    assert classifier.cost("claude-opus-5-5", 1_000_000, 0) == 4.0
    assert classifier.cost("claude-opus-5-5", 1000, 300) == pytest.approx(0.01)
    assert classifier.cost("claude-haiku-5-5", 1000, 300) == pytest.approx(0.00025)
    assert classifier.cost("claude-unknown-9", 1000, 300) is None
    assert classifier.model_name("claude-sonnet-5-5") == "Sonnet 5.5" and classifier.model_name("x") == "x"


def _response(model="claude-opus-5-5", iterations=None, **usage):
    fields = {"input_tokens": 900, "output_tokens": 250, "cache_creation_input_tokens": 0,
              "cache_read_input_tokens": 100, "iterations": iterations, **usage}
    return SimpleNamespace(model=model, usage=SimpleNamespace(**fields))


def test_usage_of_a_plain_answer_counts_the_cache_as_input():
    assert classifier.usages(_response()) == [Usage("claude-opus-5-5", 1000, 250)]


def test_usage_of_a_fallback_bills_every_attempt():
    declined = SimpleNamespace(type="message", model="claude-opus-5-5", input_tokens=800, output_tokens=40)
    rescued = SimpleNamespace(type="fallback_message", model="claude-opus-5", input_tokens=800, output_tokens=200)
    assert classifier.usages(_response(model="claude-opus-5", iterations=[declined, rescued])) == [
        Usage("claude-opus-5-5", 800, 40), Usage("claude-opus-5", 800, 200)]


async def test_classify_reports_the_usage_even_when_the_answer_is_cut(monkeypatch):
    heard = []
    response = _response(stop_reason=None)
    response.stop_reason, response.content = "max_tokens", []

    class Messages:
        async def create(self, **kwargs):
            return response

    client = SimpleNamespace(beta=SimpleNamespace(messages=Messages()))

    async def record(usage):
        heard.append(usage)

    sample = Sample(text="hi", channel_title="c", first_message=False, forwarded=False)
    with pytest.raises(ValueError):
        await classifier.classify(client, "claude-opus-5-5", sample, on_usage=record)
    assert heard == [Usage("claude-opus-5-5", 1000, 250)]


async def test_usage_is_summed_per_day_and_model_and_pruned_after_90_days(db):
    today = date(2026, 11, 27)
    await db.add_api_usage("claude-opus-5-5", 1000, 300, today)
    await db.add_api_usage("claude-opus-5-5", 1000, 300, today)
    await db.add_api_usage("claude-opus-5", 500, 100, today - timedelta(days=3))
    await db.add_api_usage("claude-opus-5-5", 1, 1, today - timedelta(days=20))
    assert await db.api_usage(7, today) == [
        {"model": "claude-opus-5-5", "calls": 2, "input_tokens": 2000, "output_tokens": 600},
        {"model": "claude-opus-5", "calls": 1, "input_tokens": 500, "output_tokens": 100},
    ]
    from datetime import UTC, datetime
    removed = await db.prune(datetime(2026, 11, 27, tzinfo=UTC) + timedelta(days=80))
    assert removed["api_usage"] == 1                       # the day 100 days back


async def test_the_screen_says_what_a_week_cost(config, db):
    await db.add_api_usage("claude-opus-5-5", 100_000, 30_000)
    await db.add_api_usage("claude-opus-5-5", 100_000, 30_000)
    text = (await ui.comments_screen(db, config)).text
    assert "Платно: каждый комментарий — запрос к Claude по твоему ключу." in text
    assert "За 7 дней: 2 проверки, ≈ $2,00 (Opus 5.5)." in text          # 200K in × $4 + 60K out × $20
    await db.add_api_usage("claude-future-9", 1500, 500)
    text = (await ui.comments_screen(db, config)).text
    assert "claude-future-9: 1\u00a0500 токенов на входе, 500 на выходе — цену этой модели я не знаю." in text


# ── The daily limit ─────────────────────────────────────────────────────────

async def test_the_limit_buttons_beat_the_variable_and_count_as_the_owners(make_update, make_context, config, db):
    assert await comments.daily_limit(db, config) == config.comments_daily_limit
    before = await behavior.current(db, config)
    update = make_update(callback="cm:lim:1000")
    await handlers.on_callback(update, make_context())
    assert update.callback_query.answers == [{"text": "Лимит: 1000 в сутки", "show_alert": False}]
    assert await comments.daily_limit(db, config) == 1000
    assert buttons(update.callback_query.markups[0])["cm:lim:1000"] == "✅ 1000"
    pending = behavior.Pending()
    behavior._changes(before, await behavior.current(db, config), pending)
    assert pending.lines == []                                  # the owner's own change is not told back

    update = make_update(callback="cm:lim:0")
    await handlers.on_callback(update, make_context())
    assert await comments.daily_limit(db, config) == 0
    assert "Лимит: нет" in update.callback_query.edits[0]


# ── For the developer ───────────────────────────────────────────────────────

async def test_a_new_install_starts_without_the_developers_notices(config, db):
    watching = dataclasses.replace(config, update_watch=True)
    assert not await monitors.is_on(db, watching, monitors.DEV_NOTICES)
    assert not await updates.adopt_dev_notices(db)                 # never ran: nothing to keep
    assert await db.get_setting(monitors.switch_key(monitors.DEV_NOTICES)) is None


async def test_a_bot_that_ran_before_keeps_them_and_is_not_told_of_a_new_check(config, db):
    watching = dataclasses.replace(config, update_watch=True)
    previous = await behavior.current(db, watching)
    del previous[f"monitor:{monitors.DEV_NOTICES}"]               # the snapshot 1.12 wrote
    await db.set_setting(updates.SNAPSHOT_KEY, "{}")
    assert await updates.adopt_dev_notices(db)
    assert await monitors.is_on(db, watching, monitors.DEV_NOTICES)
    assert not await updates.adopt_dev_notices(db)                 # once
    pending = behavior.Pending()
    behavior._changes(previous, await behavior.current(db, watching), pending)
    assert not any("Для разработчика" in line for line in pending.lines)


async def test_update_watch_zero_still_switches_it_all_off(config, db):
    await monitors.set_switch(db, monitors.DEV_NOTICES, True)
    assert not await monitors.is_on(db, dataclasses.replace(config, update_watch=False), monitors.DEV_NOTICES)


async def test_the_deploy_watch_is_silent_while_the_monitor_is_off(bot, config, db, monkeypatch):
    async def failed(session, config):
        raise AssertionError("asked GitHub")

    monkeypatch.setattr(updates, "failed_deploy", failed)
    await updates.run_deploy_watch(bot, dataclasses.replace(config, update_watch=True), db)
    assert bot.messages == []
