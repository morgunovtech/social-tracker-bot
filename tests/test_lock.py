"""requirements.txt is the lock compiled from requirements.in, and
requirements-dev.txt the one compiled from requirements-dev.in: every pin in
the .in file appears in its lock at the same version, and every line of a
lock carries a hash — the image and CI install them with --require-hashes."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s\;]+)")


def _pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text().splitlines():
        m = PIN.match(line.strip())
        if m:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


LOCKS = pytest.mark.parametrize("stem", ["requirements", "requirements-dev"])


@LOCKS
def test_the_lock_is_compiled_from_requirements_in(stem):
    wanted = _pins(ROOT / f"{stem}.in")
    locked = _pins(ROOT / f"{stem}.txt")
    assert wanted, f"{stem}.in has no pins"
    for name, version in wanted.items():
        assert locked.get(name) == version, f"{name}=={version} from {stem}.in is not in the lock"


@LOCKS
def test_every_locked_package_has_a_hash(stem):
    text = (ROOT / f"{stem}.txt").read_text()
    for name in _pins(ROOT / f"{stem}.txt"):
        block = text[text.index(f"{name}==") if f"{name}==" in text else text.lower().index(f"{name}==") :]
        assert "--hash=sha256:" in block.split("\n\n")[0], f"{name} has no hash"
