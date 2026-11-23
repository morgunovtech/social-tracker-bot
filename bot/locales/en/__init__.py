"""English. Russian text → English, split by the area of the bot the
strings belong to; the files are merged here. Keys must match the Russian
source byte for byte, placeholders ({count}, {label}) included."""

from __future__ import annotations

from bot.locales.en import handlers, monitors, reporter, ui

STRINGS: dict[str, str] = {**ui.STRINGS, **handlers.STRINGS, **reporter.STRINGS, **monitors.STRINGS}
# Russian singular → (English singular, English plural).
PLURALS: dict[str, tuple[str, str]] = {**ui.PLURALS, **handlers.PLURALS, **reporter.PLURALS, **monitors.PLURALS}
