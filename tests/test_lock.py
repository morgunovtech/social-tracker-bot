"""requirements.txt is the lock compiled from requirements.in: every pin in
the .in file appears in the lock at the same version, and every line of the
lock carries a hash — the image installs it with --require-hashes."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s\;]+)")


def _pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text().splitlines():
        m = PIN.match(line.strip())
        if m:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def test_the_lock_is_compiled_from_requirements_in():
    wanted = _pins(ROOT / "requirements.in")
    locked = _pins(ROOT / "requirements.txt")
    assert wanted, "requirements.in has no pins"
    for name, version in wanted.items():
        assert locked.get(name) == version, f"{name}=={version} from requirements.in is not in the lock"


def test_every_locked_package_has_a_hash():
    text = (ROOT / "requirements.txt").read_text()
    for name in _pins(ROOT / "requirements.txt"):
        block = text[text.index(f"{name}==") if f"{name}==" in text else text.lower().index(f"{name}==") :]
        assert "--hash=sha256:" in block.split("\n\n")[0], f"{name} has no hash"
