"""The documents a new owner reads say what the code does: links lead
somewhere, screens and buttons are named as the bot names them, the Russian
and English twins have the same sections, no example looks like a real
token, and `cp .env.example .env` changes nothing but the token.

Ported from TofsDevOps (tests/test_docs.py) and adapted: here the docs come
in RU/EN pairs (X.md / X.en.md; README.md is English, README.ru.md Russian)."""

import ast
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted([
    ROOT / "README.md", ROOT / "README.ru.md", ROOT / "SECURITY.md", ROOT / "CONTRIBUTING.md",
    *ROOT.glob("docs/*.md"), *ROOT.glob("docs/connect/*.md"), *ROOT.glob("mail-worker/README*.md"),
])
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
QUOTED = re.compile(r"«([^«»\n]{2,60})»")


def _slug(heading: str) -> str:
    """GitHub's anchor: lower case, letters/digits/space/-/_ kept, spaces → -."""
    kept = (ch for ch in heading.strip().lower()
            if ch in " -_" or unicodedata.category(ch)[0] in "LN")
    return "".join(kept).replace(" ", "-")


def _anchors(md: Path) -> set[str]:
    found, seen, in_code = set(), {}, False
    for line in md.read_text("utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code and (m := re.match(r"^#{1,6}\s+(.*)$", line)):
            s = _slug(re.sub(r"[`*_]|\[([^\]]*)\]\([^)]*\)", r"\1", m.group(1)))
            found.add(s if s not in seen else f"{s}-{seen[s]}")
            seen[s] = seen.get(s, 0) + 1
    return found


def _lines(md: Path):
    """(number, line) outside code blocks."""
    in_code = False
    for no, line in enumerate(md.read_text("utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            yield no, line


def test_relative_links_in_the_docs_lead_somewhere():
    broken = []
    for md in DOCS:
        for no, line in _lines(md):
            for target in LINK.findall(line):
                if re.match(r"^[a-z]+://|^mailto:", target):
                    continue
                path, _, frag = target.partition("#")
                dest = (md.parent / path).resolve() if path else md
                if not dest.exists():
                    broken.append(f"{md.relative_to(ROOT)}:{no}: {target} — no such file")
                elif frag and dest.suffix == ".md" and frag not in _anchors(dest):
                    broken.append(f"{md.relative_to(ROOT)}:{no}: {target} — no such heading")
    assert broken == [], "\n".join(broken)


def _bot_texts() -> str:
    """Every string the code can show, Russian and English (docstrings are not shown)."""
    texts = []
    for py in (ROOT / "bot").glob("**/*.py"):
        tree = ast.parse(py.read_text("utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        texts += [n.value for n in ast.walk(tree)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
    # Buttons put together at run time: «➕ YouTube», «✏️ Telegram», «🔑 Google» / «🔑 Яндекс».
    from bot import reputation
    from bot.locales.en import STRINGS
    from bot.platforms import PLATFORMS
    texts += [f"{sign} {p.label}" for p in PLATFORMS for sign in ("➕", "✏️")]
    texts += [f"🔑 {label}" for s in reputation.SOURCES for label in (s.label, STRINGS.get(s.label, s.label))]
    joined = "\n".join(texts)
    return joined + "\n" + re.sub(r"</?[bi]>", "", joined)     # «📤 <b>Отправки</b>» reads «📤 Отправки»


def _starts_with_emoji(text: str) -> bool:
    return bool(text) and unicodedata.category(text[0]) == "So"


# Quoted with an emoji, but not a screen or a button of this bot: examples of
# what the bot writes, the old keyboard, another bot's screens.
NOT_A_BUTTON = re.compile(
    r"^(✅|🔴|🟠|⚠️|ℹ️|⏳|🔄 Бот обновился|🔄 The bot has been updated|📬|🎯|📈 Всего|📊)"
    r"|\d"                                               # a sample line with numbers
)


def test_docs_name_screens_and_buttons_as_the_bot_does():
    """A screen or a button quoted with its emoji — «🔌 Подключения»,
    «📮 Отдельный ящик (просто)» — must be something the bot shows, in Russian
    or English; otherwise the guide sends people looking for nothing."""
    shown = _bot_texts()
    missing = []
    for md in DOCS:
        for no, line in _lines(md):
            for quoted in QUOTED.findall(line):
                name = quoted.strip()
                if not _starts_with_emoji(name) or NOT_A_BUTTON.search(name):
                    continue
                if name not in shown:
                    missing.append(f"{md.relative_to(ROOT)}:{no}: «{name}»")
    assert missing == [], "\n".join(missing)


def test_docs_hold_no_token_shaped_strings():
    """A realistic example token trips every secret scanner of every fork."""
    shaped = re.compile(r"\b[0-9]{8,10}:[A-Za-z0-9_-]{35}\b|sk-ant-[A-Za-z0-9_-]{20,}")
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in [*DOCS, ROOT / ".env.example"]
            for n, line in enumerate(p.read_text("utf-8").splitlines(), 1) if shaped.search(line)]
    assert hits == []


def _pairs() -> list[tuple[Path, Path]]:
    pairs = [(ROOT / "README.ru.md", ROOT / "README.md"), (ROOT / "mail-worker/README.ru.md", ROOT / "mail-worker/README.md")]
    for en in [*ROOT.glob("docs/*.en.md"), *ROOT.glob("docs/connect/*.en.md")]:
        pairs.append((en.with_name(en.name.replace(".en.md", ".md")), en))
    return pairs


def _sections(md: Path) -> int:
    return sum(1 for _, line in _lines(md) if re.match(r"^##\s", line))


def test_every_russian_page_has_an_english_twin_with_the_same_sections():
    for ru in [*ROOT.glob("docs/*.md"), *ROOT.glob("docs/connect/*.md")]:
        if ru.name.endswith(".en.md") or ru.name == "RAILWAY_TEMPLATE.md":
            continue
        assert ru.with_name(ru.name.replace(".md", ".en.md")).exists(), f"{ru.relative_to(ROOT)} has no .en.md"
    differ = [f"{ru.relative_to(ROOT)} {_sections(ru)} vs {en.relative_to(ROOT)} {_sections(en)}"
              for ru, en in _pairs() if ru.exists() and en.exists() and _sections(ru) != _sections(en)]
    assert differ == [], "\n".join(differ)


_CONFIG_DUMP = (
    "import dataclasses, json, sys\n"
    "import dotenv\n"
    "dotenv.load_dotenv = lambda *a, **k: False   # never read a real .env\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from bot.config import Config\n"
    "c = Config.from_env()\n"
    "print(json.dumps({f.name: getattr(c, f.name) for f in dataclasses.fields(Config)}, default=str))\n")


def _config_with(env: dict[str, str]) -> dict:
    """The config a fresh process builds from exactly these variables (the
    test process itself runs with tests/conftest.py's values)."""
    base = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "HOME", "LANG")}
    base |= {"PYTHONDONTWRITEBYTECODE": "1", "BOT_TOKEN": "123456:fake"}
    out = subprocess.run([sys.executable, "-c", _CONFIG_DUMP, str(ROOT)], env={**base, **env},
                         capture_output=True, text=True, check=True, timeout=60)
    return json.loads(out.stdout)


def test_env_example_changes_nothing_but_the_token():
    """`cp .env.example .env` must give the same bot as no .env at all
    (Railway, the one-field template): the template shows the defaults, it
    does not choose new ones."""
    example = {k: v or "" for k, v in dotenv_values(ROOT / ".env.example").items()}
    example["BOT_TOKEN"] = "123456:fake"
    bare, templated = _config_with({}), _config_with(example)
    differ = {k: (bare[k], templated[k]) for k in bare if bare[k] != templated[k]}
    assert differ == {}, differ                       # field: (no .env, cp .env.example .env)
