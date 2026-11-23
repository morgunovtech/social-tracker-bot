"""One real classification against the Claude API — opt-in, never in CI.

The unit tests fake the model, and a request shape the API refuses passes
them: the integer bounds in the output schema did (#49), and so would a
max_tokens cap the thinking uses up. Before a release, one real call:

    LIVE_ANTHROPIC_API_KEY=sk-ant-… pytest -q tests/test_classifier_live.py

A different variable than the bot's own: tests/conftest.py blanks
ANTHROPIC_API_KEY so no fixture ever reaches the real API by accident.
"""

from __future__ import annotations

import os

import pytest

from bot import classifier
from bot.classifier import Sample

KEY = os.environ.get("LIVE_ANTHROPIC_API_KEY", "")

pytestmark = pytest.mark.skipif(not KEY, reason="set LIVE_ANTHROPIC_API_KEY for one real API call")


async def test_a_harmless_comment_is_ok_live():
    sample = Sample("Спасибо, отличный выпуск!", "Тестовый канал", first_message=False, forwarded=False)
    verdict = await classifier.classify(classifier.make_client(KEY), classifier.DEFAULT_MODEL, sample, "ru")
    assert verdict.category == "ok" and 0 <= verdict.confidence <= 100 and verdict.reason
