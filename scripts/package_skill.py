"""Pack the setup skill for claude.ai's «Upload a skill»: a zip whose root is
the skill's folder (install-social-tracker/SKILL.md, references/…), as
claude.ai's help asks. Attached to each GitHub Release by hand:

    python3 scripts/package_skill.py            # → dist/install-social-tracker.zip
    gh release upload vX.Y.Z dist/install-social-tracker.zip
"""

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "social-tracker-setup" / "skills" / "install-social-tracker"


def package(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{SKILL.name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SKILL.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                archive.write(path, f"{SKILL.name}/{path.relative_to(SKILL).as_posix()}")
    return target


if __name__ == "__main__":
    print(package(ROOT / "dist"))
