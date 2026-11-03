"""Knowing about its own updates.

The bot does not upgrade itself inside its container: a change made there
would vanish with the next deploy, and nothing would have tested it. Updates
arrive as Dependabot pull requests (.github/dependabot.yml) that CI tests and
auto-merges; Railway redeploys from main. The bot adds what that pipeline
cannot say on its own:

  * on startup: what changed since the last boot («🔄 Бот обновился:
    aiohttp 3.14.3 → 3.14.4»);
  * hourly: the newest commit on main failed to deploy while the bot still
    runs an older build — then every next update fails the same way;
  * weekly: known vulnerabilities (OSV) in the running packages, and
    Dependabot PRs that wait for a human (major bumps, or a red CI).

A newer version on PyPI is not news: Dependabot brings it on Saturday.
"""

from __future__ import annotations

import json
import logging
import platform
import re
from datetime import UTC, datetime, timedelta
from importlib import metadata

import aiohttp
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Config
from bot.db import Database

logger = logging.getLogger(__name__)

PACKAGES = (
    "python-telegram-bot", "aiohttp", "aiosqlite", "APScheduler",
    "beautifulsoup4", "matplotlib", "python-dotenv",
)
GITHUB_API = "https://api.github.com"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
# A minor/patch PR still open after this long did not auto-merge: CI is red.
STUCK_AFTER = timedelta(days=2)
_TIMEOUT = aiohttp.ClientTimeout(total=30)

SNAPSHOT_KEY = "deps_snapshot"
DEPLOY_ALERTED_KEY = "deploy_failed_alerted"
VULNS_ALERTED_KEY = "vulns_alerted"


class _Unknown(Exception):
    """GitHub did not answer (rate limit on a shared IP, network)."""


def installed_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
    return out


# --- Startup: "what changed since the last boot?" ---------------------------

async def report_startup_changes(bot: Bot, config: Config, db: Database) -> list[str]:
    """Tell the admin when the build, Python or a package changed since the
    last boot. The first boot only takes the snapshot. Returns the lines sent."""
    current = {
        "commit": config.app_commit,
        "python": platform.python_version(),
        "packages": installed_versions(),
    }
    prev_raw = await db.get_setting(SNAPSHOT_KEY)
    await db.set_setting(SNAPSHOT_KEY, json.dumps(current))
    if not prev_raw:
        return []
    try:
        prev = json.loads(prev_raw)
    except ValueError:
        return []

    lines: list[str] = []
    if current["commit"] and prev.get("commit") != current["commit"]:
        old = (prev.get("commit") or "?")[:7]
        lines.append(f"  • сборка {old} → {current['commit'][:7]}")
    if prev.get("python") != current["python"]:
        lines.append(f"  • Python {prev.get('python')} → {current['python']}")
    old_packages = prev.get("packages") or {}
    for name, version in current["packages"].items():
        if old_packages.get(name) and old_packages[name] != version:
            lines.append(f"  • {name} {old_packages[name]} → {version}")
    if lines:
        await bot.send_message(chat_id=config.admin_chat_id, text="🔄 Бот обновился:\n" + "\n".join(lines))
    return lines


# --- GitHub ------------------------------------------------------------------

async def _github(session: aiohttp.ClientSession, config: Config, path: str, **params):
    """GitHub REST: JSON, or None when it did not answer. A token is optional
    for a public repository (it only lifts the rate limit)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "social-tracker-bot"}
    if config.github_token:
        headers["Authorization"] = f"Bearer {config.github_token}"
    try:
        async with session.get(GITHUB_API + path, params=params or None, headers=headers) as resp:
            return await resp.json() if resp.status == 200 else None
    except Exception as e:
        logger.debug("GitHub %s: %s", path, e)
        return None


_BUMP = re.compile(r"bump (\S+) from (\d+)(\S*) to (\d+)(\S*)", re.I)


def is_major_bump(title: str) -> bool:
    """Dependabot title «Bump aiohttp from 3.14.4 to 4.0.0» → major changed."""
    m = _BUMP.search(title)
    return bool(m) and m.group(2) != m.group(4)


def short_bump(title: str) -> str:
    m = _BUMP.search(title)
    return f"{m.group(1)} {m.group(2)}{m.group(3)}→{m.group(4)}{m.group(5)}" if m else title[:60]


# --- Hourly: did the newest version deploy? ---------------------------------

async def failed_deploy(session: aiohttp.ClientSession, config: Config) -> dict | None:
    """{sha, title, url, log} of the newest commit on main when its deploy
    failed while this bot still runs an older build. Raises _Unknown when
    GitHub did not answer."""
    slug, running = config.repo_slug, config.app_commit
    if not slug or not running:
        return None
    head = await _github(session, config, f"/repos/{slug}/commits/main")
    if head is None:
        raise _Unknown
    sha = str(head.get("sha") or "")
    if not sha or sha.startswith(running):
        return None
    deployments = await _github(session, config, f"/repos/{slug}/deployments", sha=sha, per_page="5")
    if deployments is None:
        raise _Unknown
    for deployment in deployments:
        statuses = await _github(
            session, config, f"/repos/{slug}/deployments/{deployment['id']}/statuses", per_page="1"
        )
        if statuses is None:
            raise _Unknown
        if statuses and statuses[0].get("state") in ("failure", "error"):
            title = str((head.get("commit") or {}).get("message") or "").splitlines()[0][:80]
            return {
                "sha": sha[:7],
                "title": title,
                "url": head.get("html_url") or "",
                "log": statuses[0].get("log_url") or statuses[0].get("target_url") or "",
            }
    return None   # deployed, still deploying, or not picked up yet


async def run_deploy_watch(bot: Bot, config: Config, db: Database) -> None:
    """Say once per commit that the newest version did not deploy: the bot
    keeps working on the old build, so nothing else would ever show it."""
    if not config.update_watch:
        return
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            failed = await failed_deploy(session, config)
    except _Unknown:
        return   # could not check — say nothing rather than guess
    if not failed or failed["sha"] == await db.get_setting(DEPLOY_ALERTED_KEY):
        return

    rows = []
    if failed["log"].startswith("https://"):
        rows.append([InlineKeyboardButton("📄 Лог сборки", url=failed["log"])])
    if failed["url"].startswith("https://"):
        rows.append([InlineKeyboardButton("🔗 Что в этой версии", url=failed["url"])])
    try:
        await bot.send_message(
            chat_id=config.admin_chat_id,
            text=(
                "🟠 Новая версия бота не запустилась\n"
                f"Railway не смог выкатить «{failed['title']}» ({failed['sha']}). Я работаю на прежней "
                f"версии ({config.app_commit[:7]}), но и следующие обновления не встанут, пока сборка падает.\n\n"
                "Что делать: открой лог сборки — обычно там видно, какой пакет не поставился. "
                "Быстрый выход — откатить этот коммит в GitHub (Revert)."
            ),
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )
    except Exception:
        logger.exception("Deploy alert send failed")
        return
    await db.set_setting(DEPLOY_ALERTED_KEY, failed["sha"])


# --- Weekly: vulnerabilities and PRs waiting for a human --------------------

async def vulnerabilities(session: aiohttp.ClientSession, versions: dict[str, str]) -> dict[str, list[str]] | None:
    """{package: [ids]}; None when OSV could not be asked — «unknown» must not
    read as «no vulnerabilities»."""
    names = list(versions)
    body = {"queries": [{"package": {"name": n, "ecosystem": "PyPI"}, "version": versions[n]} for n in names]}
    try:
        async with session.post(OSV_BATCH, json=body) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception as e:
        logger.debug("OSV query failed: %s", e)
        return None
    out: dict[str, list[str]] = {}
    for name, result in zip(names, data.get("results", []), strict=False):
        ids = sorted(v["id"] for v in (result or {}).get("vulns", []) if v.get("id"))
        if ids:
            out[name] = ids
    return out


async def waiting_prs(session: aiohttp.ClientSession, config: Config) -> list[dict] | None:
    """Dependabot PRs that wait for a human: major bumps (never auto-merged)
    and minor ones still open after STUCK_AFTER (auto-merge waits for a green
    CI, so the tests failed). None when GitHub did not answer."""
    if not config.repo_slug:
        return []
    data = await _github(session, config, f"/repos/{config.repo_slug}/pulls", state="open", per_page="50")
    if not isinstance(data, list):
        return None
    now = datetime.now(UTC)
    out = []
    for pr in data:
        if not str((pr.get("user") or {}).get("login") or "").startswith("dependabot"):
            continue
        title = str(pr.get("title") or "")
        major = is_major_bump(title)
        try:
            opened = datetime.fromisoformat(str(pr.get("created_at")).replace("Z", "+00:00"))
        except ValueError:
            opened = now
        if major or now - opened > STUCK_AFTER:
            out.append({"number": pr.get("number"), "title": title, "url": pr.get("html_url") or "", "major": major})
    return out


async def run_dependency_watch(bot: Bot, config: Config, db: Database) -> None:
    """Weekly: alert once when vulnerable packages appear (and once when they
    are gone); remind about PRs that wait for a human while they wait."""
    if not config.update_watch:
        return
    versions = installed_versions()
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        vulns = await vulnerabilities(session, versions)
        prs = await waiting_prs(session, config)

    parts: list[str] = []
    new_signature = None   # stored only once the message went out
    if vulns is not None:
        signature = ",".join(sorted(i for ids in vulns.values() for i in ids))
        previous = await db.get_setting(VULNS_ALERTED_KEY) or ""
        if signature != previous:
            new_signature = signature
            if vulns:
                listed = "\n".join(
                    f"  • {name} {versions.get(name, '?')}: {', '.join(ids[:3])}{'…' if len(ids) > 3 else ''}"
                    for name, ids in vulns.items()
                )
                parts.append(
                    "🛡 В пакетах бота нашлись известные уязвимости:\n" + listed + "\n"
                    "Dependabot откроет PR с исправлением; после мержа я напишу, что обновился."
                )
            else:
                parts.append("✅ Уязвимых зависимостей больше нет.")

    for pr in prs or []:
        if pr["major"]:
            parts.append(
                f"🔀 Ждёт твоего решения: {short_bump(pr['title'])} — крупное обновление, само не вливается. "
                f"Прочитай «что поменялось» и нажми Merge: {pr['url']}"
            )
        else:
            parts.append(f"🟠 Обновление не встало само — тесты не прошли: {short_bump(pr['title'])} {pr['url']}")

    if not parts:
        return
    try:
        await bot.send_message(chat_id=config.admin_chat_id, text="\n\n".join(parts))
    except Exception:
        logger.exception("Dependency watch send failed")
        return
    if new_signature is not None:
        await db.set_setting(VULNS_ALERTED_KEY, new_signature)
