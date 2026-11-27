"""One release number: bot.__version__ (⚙️ Настройки), pyproject.toml and the
top entry of CHANGELOG.md say the same."""

import re
import tomllib
from pathlib import Path

from bot import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_the_version_is_the_same_everywhere():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    top = re.search(r"^## (\d+\.\d+\.\d+) — ", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.MULTILINE)
    assert top is not None
    assert __version__ == project == top.group(1)
