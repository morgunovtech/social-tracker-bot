#!/bin/sh
# Update an already deployed mail-worker without losing its settings.
#
#   sh mail-worker/update.sh            # dry run: builds and checks, uploads nothing
#   sh mail-worker/update.sh --deploy   # the same, then deploys and verifies
#
# wrangler.toml in the repository is a template: the KV id is a placeholder
# and ALLOWED_SENDERS is empty, your real values live only on Cloudflare. A
# plain `npx wrangler deploy` from a checkout fails on the placeholder — or,
# once the id is pasted in, replaces ALLOWED_SENDERS with the empty list, and
# the worker then rejects every mail. This script deploys the committed code
# (HEAD) from a temporary copy instead: the EVENTS id is read from the
# deployed worker itself, the [vars] block is left out and --keep-vars keeps
# what Cloudflare has. Nothing is written to the checkout; the id and the
# senders are never printed.
#
# Needs git, node, npm and a logged-in wrangler (`npx wrangler login`).
# WORKER_NAME — the worker's name on Cloudflare, if it is not the `name`
# from wrangler.toml. WORKER_URL — its address, if the deploy does not print
# a workers.dev one (a custom domain).
set -eu

say() { printf '%s\n' "$*"; }
# --yes: output is captured below, a «may I install wrangler?» question would hang unseen.
wrangler() { npx --yes wrangler "$@"; }
die() { say "✗ $*" >&2; exit 1; }

DEPLOY=0
case "${1:-}" in
  "") ;;
  --deploy) DEPLOY=1 ;;
  *) die "Usage: sh update.sh [--deploy]" ;;
esac
[ $# -le 1 ] || die "Usage: sh update.sh [--deploy]"

for tool in git node npm npx; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is not installed."
done

HERE=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
trap 'exit 130' INT TERM
mkdir "$TMP/src"

# 1. A clean copy of the committed worker: no local edits, no node_modules.
git -C "$HERE" archive --format=tar HEAD | tar -xf - -C "$TMP/src"
[ -f "$TMP/src/wrangler.toml" ] || die "No wrangler.toml in the committed mail-worker."
say "Source: $(git -C "$HERE" log -1 --format='%h %s')"
if [ -n "$(git -C "$HERE" status --porcelain -- .)" ]; then
  say "⚠️ mail-worker/ has uncommitted changes; they are NOT part of this update."
fi

NAME=${WORKER_NAME:-$(sed -n 's/^name *= *"\(.*\)" *$/\1/p' "$TMP/src/wrangler.toml" | head -n 1)}
[ -n "$NAME" ] || die "No worker name: set WORKER_NAME."

cd "$TMP/src"
npm ci --ignore-scripts --no-audit --no-fund >"$TMP/npm.log" 2>&1 \
  || { cat "$TMP/npm.log" >&2; die "npm ci failed."; }

# The bindings of the version that serves 100% of the traffic → a JSON file.
# stdout: that version's id.
snapshot() {
  wrangler deployments status --name "$NAME" --json >"$TMP/status.json" 2>"$TMP/err.log" \
    || { cat "$TMP/err.log" >&2; die "Cannot read the deployment of «$NAME». Is it deployed (the README's Setup), and is wrangler logged in?"; }
  version=$(node -e '
    const v = (JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).versions || []);
    if (v.length === 1 && v[0].percentage === 100) console.log(v[0].version_id);
  ' "$TMP/status.json")
  [ -n "$version" ] || die "«$NAME» is in a gradual deployment (not one version at 100%). Finish or roll it back first."
  wrangler versions view "$version" --name "$NAME" --json >"$1" 2>"$TMP/err.log" \
    || { cat "$TMP/err.log" >&2; die "Cannot read version $version of «$NAME»."; }
  say "$version"
}

# What must survive the update, checked without printing a value.
#   bindings check FILE          → exit 1 with the reason if a setting is missing
#   bindings id FILE             → the EVENTS namespace id (for the temporary config only)
#   bindings same BEFORE AFTER   → exit 1 with the reason if a setting changed
bindings() {
  node -e '
    const fs = require("fs");
    const [mode, a, b] = process.argv.slice(1);
    const read = (file) => {
      const list = JSON.parse(fs.readFileSync(file, "utf8")).resources?.bindings || [];
      const one = (name, type) => list.find((x) => x.name === name && x.type === type);
      return {
        senders: one("ALLOWED_SENDERS", "plain_text")?.text ?? "",
        events: one("EVENTS", "kv_namespace")?.namespace_id ?? "",
        token: Boolean(one("TOKEN", "secret_text")),
      };
    };
    const missing = (s) => [
      s.senders.trim() ? "" : "ALLOWED_SENDERS is empty or missing (the worker rejects every mail)",
      s.events ? "" : "the EVENTS KV binding is missing",
      s.token ? "" : "the TOKEN secret is missing",
    ].filter(Boolean);
    const first = read(a);
    let problems = missing(first);
    if (mode === "id") {
      if (!/^[0-9a-f]{32}$/.test(first.events)) process.exit(1);
      console.log(first.events);
    } else if (mode === "same") {
      const second = read(b);
      problems = missing(second);
      if (second.senders !== first.senders) problems.push("ALLOWED_SENDERS changed");
      if (second.events !== first.events) problems.push("EVENTS points at another KV namespace");
    }
    if (problems.length) {
      console.log(problems.join("; "));
      process.exit(1);
    }
  ' "$@"
}

# 2. What the deployed worker has now.
BEFORE=$(snapshot "$TMP/before.json")
problem=$(bindings check "$TMP/before.json") \
  || die "The deployed worker is not set up completely: $problem. Fix it first (Cloudflare → Workers → $NAME → Settings → Variables and Secrets, or the README's Setup), then run this again."
say "✓ Deployed now: version $BEFORE — ALLOWED_SENDERS is set, EVENTS and TOKEN are bound."

# 3. The temporary config: the real EVENTS id in, the [vars] block out.
EVENTS_ID=$(bindings id "$TMP/before.json") || die "The EVENTS binding of «$NAME» has no usable namespace id."
EVENTS_ID="$EVENTS_ID" node -e '
  const fs = require("fs");
  const placeholder = "REPLACE_WITH_KV_NAMESPACE_ID";
  const lines = fs.readFileSync("wrangler.toml", "utf8").split("\n");
  const out = [];
  let inVars = false;
  let replaced = 0;
  for (const line of lines) {
    const table = /^\s*\[/.test(line);
    if (table) inVars = /^\s*\[vars\]\s*(#.*)?$/.test(line);
    if (inVars) continue;
    if (line.includes(placeholder)) replaced += 1;
    out.push(line.replace(placeholder, process.env.EVENTS_ID));
  }
  if (replaced !== 1) {
    console.error("wrangler.toml: expected the placeholder " + placeholder + " exactly once.");
    process.exit(1);
  }
  if (out.some((l) => /^\s*(\[vars\]|ALLOWED_SENDERS\s*=|vars\s*=|vars\.)/.test(l))) {
    console.error("wrangler.toml: a vars entry survived outside the [vars] block.");
    process.exit(1);
  }
  fs.writeFileSync("wrangler.toml", out.join("\n"));
' || die "Could not prepare the temporary wrangler.toml."

# wrangler lists the bindings it uploads; the id stays out of the terminal.
wrangler_deploy() {
  status=0
  wrangler deploy --keep-vars "$@" >"$TMP/deploy.log" 2>&1 || status=$?
  sed "s/$EVENTS_ID/<EVENTS id>/g" "$TMP/deploy.log"
  return "$status"
}

# 4. Build and check, upload nothing.
say ""
say "— wrangler deploy --dry-run --keep-vars"
wrangler_deploy --dry-run || die "The dry run failed; nothing was uploaded."

if [ "$DEPLOY" -ne 1 ]; then
  say ""
  say "✓ Dry run passed. Nothing was uploaded; to deploy: sh mail-worker/update.sh --deploy"
  exit 0
fi

# 5. Deploy, then compare what Cloudflare has with what it had.
say ""
say "— wrangler deploy --keep-vars"
wrangler_deploy || die "The deploy failed. Check what serves now: npx wrangler deployments status --name $NAME"

UNDO="To go back: npx wrangler rollback $BEFORE --name $NAME"
AFTER=$(snapshot "$TMP/after.json")
[ "$AFTER" != "$BEFORE" ] || die "The deploy reported success, but version $BEFORE still serves."
problem=$(bindings same "$TMP/before.json" "$TMP/after.json") \
  || die "Version $AFTER is live, but its settings differ: $problem. $UNDO"
say ""
say "✓ Deployed: version $BEFORE → $AFTER. ALLOWED_SENDERS and EVENTS are unchanged, TOKEN is bound."

# 6. The worker answers, and still refuses a request without the token.
URL=${WORKER_URL:-$(grep -Eo 'https://[A-Za-z0-9.-]+\.workers\.dev' "$TMP/deploy.log" | head -n 1 || true)}
if [ -z "$URL" ]; then
  say "⚠️ No workers.dev address in the deploy output: check by hand that <worker URL>/events answers 401 without the token (or run again with WORKER_URL=…)."
elif ! command -v curl >/dev/null 2>&1; then
  say "⚠️ curl is not installed: check by hand that $URL/events answers 401 without the token."
else
  code=$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$URL/events" || true)
  [ "$code" = "401" ] \
    || die "$URL/events answered «$code» without the token, expected 401. $UNDO"
  say "✓ $URL/events answers 401 without the token."
fi
say "The bot picks up mail on its next poll (every 5 minutes); nothing to restart."
