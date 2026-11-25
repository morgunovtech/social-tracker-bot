// update.sh against a fake wrangler: what it uploads, what it refuses, and
// that neither the KV id nor the senders reach the terminal or the checkout.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const WORKER = join(dirname(fileURLToPath(import.meta.url)), "..");
const KV_ID = "0123456789abcdef0123456789abcdef";
const SENDERS = "owner@example.com";

const version = ({ senders = SENDERS, events = KV_ID, token = true } = {}) =>
  JSON.stringify({
    resources: {
      bindings: [
        { name: "ALLOWED_SENDERS", type: "plain_text", text: senders },
        { name: "EVENTS", type: "kv_namespace", namespace_id: events },
        ...(token ? [{ name: "TOKEN", type: "secret_text" }] : []),
      ],
    },
  });

const status = (id) => JSON.stringify({ versions: [{ version_id: id, percentage: 100 }] });

// A fake npx / npm / curl first in PATH. `wrangler deploy` saves the config it
// was given and, like the real one, prints the binding with its id.
const NPX = `#!/bin/sh
[ "$1" = "--yes" ] && shift
[ "$1" = "wrangler" ] || exit 9
shift
echo "$*" >>"$FAKE/calls"
case "$1 $2" in
  "deployments status")
    if [ -f "$FAKE/deployed" ]; then cat "$FAKE/status-after.json"; else cat "$FAKE/status-before.json"; fi ;;
  "versions view") cat "$FAKE/version-$3.json" ;;
  "deploy --keep-vars")
    cp wrangler.toml "$FAKE/config.toml"
    echo "env.EVENTS ($(sed -n 's/^id = "\\(.*\\)"$/\\1/p' wrangler.toml))  KV Namespace"
    if [ "\${3:-}" != "--dry-run" ]; then
      : >"$FAKE/deployed"
      echo "  https://socialbot-mail.example.workers.dev"
    fi ;;
  *) exit 9 ;;
esac
`;

function run(args, { before = version(), after = version(), http = "401" } = {}) {
  const fake = mkdtempSync(join(tmpdir(), "update-test-"));
  const put = (name, text, mode) => {
    writeFileSync(join(fake, name), text);
    if (mode) chmodSync(join(fake, name), mode);
  };
  put("npx", NPX, 0o755);
  put("npm", "#!/bin/sh\nexit 0\n", 0o755);
  put("curl", `#!/bin/sh\nprintf '%s' "${http}"\n`, 0o755);
  put("status-before.json", status("v-old"));
  put("status-after.json", status("v-new"));
  put("version-v-old.json", before);
  put("version-v-new.json", after);
  try {
    const result = spawnSync("sh", [join(WORKER, "update.sh"), ...args], {
      env: { ...process.env, PATH: `${fake}:${process.env.PATH}`, FAKE: fake, WORKER_NAME: "", WORKER_URL: "" },
      encoding: "utf8",
    });
    const read = (name) => (existsSync(join(fake, name)) ? readFileSync(join(fake, name), "utf8") : "");
    return {
      code: result.status,
      output: result.stdout + result.stderr,
      calls: read("calls").trim().split("\n"),
      config: read("config.toml"),
    };
  } finally {
    rmSync(fake, { recursive: true, force: true });
  }
}

const deploys = (calls) => calls.filter((c) => c.split(" ")[0] === "deploy");

test("a dry run builds from the deployed worker's id, without [vars], and uploads nothing", () => {
  const template = readFileSync(join(WORKER, "wrangler.toml"), "utf8");
  const { code, output, calls, config } = run([]);
  assert.equal(code, 0, output);
  assert.deepEqual(deploys(calls), ["deploy --keep-vars --dry-run"]);
  assert.match(config, new RegExp(`^id = "${KV_ID}"$`, "m"));
  assert.doesNotMatch(config, /\[vars\]|ALLOWED_SENDERS\s*=|REPLACE_WITH/);
  assert.match(config, /^name = "socialbot-mail"$/m);
  assert.ok(!output.includes(KV_ID) && !output.includes(SENDERS), "the id and the senders stay out of the output");
  assert.match(output, /<EVENTS id>/);
  assert.match(output, /Nothing was uploaded/);
  assert.equal(readFileSync(join(WORKER, "wrangler.toml"), "utf8"), template, "the checkout is untouched");
});

test("--deploy uploads after the dry run and verifies the settings and the 401", () => {
  const { code, output, calls } = run(["--deploy"]);
  assert.equal(code, 0, output);
  assert.deepEqual(deploys(calls), ["deploy --keep-vars --dry-run", "deploy --keep-vars"]);
  assert.match(output, /version v-old → v-new/);
  assert.match(output, /workers\.dev\/events answers 401/);
  assert.ok(!output.includes(KV_ID) && !output.includes(SENDERS));
});

test("a worker deployed with empty ALLOWED_SENDERS, or without TOKEN, is not touched", () => {
  for (const before of [version({ senders: "" }), version({ token: false })]) {
    const { code, output, calls } = run(["--deploy"], { before });
    assert.equal(code, 1);
    assert.match(output, /not set up completely/);
    assert.deepEqual(deploys(calls), []);
  }
});

test("settings that changed in the deploy fail loudly, with the way back", () => {
  for (const after of [version({ senders: "" }), version({ events: "f".repeat(32) })]) {
    const { code, output } = run(["--deploy"], { after });
    assert.equal(code, 1);
    assert.match(output, /settings differ/);
    assert.match(output, /wrangler rollback v-old --name socialbot-mail/);
    assert.ok(!output.includes(SENDERS));
  }
});

test("an endpoint that answers without the token fails the update", () => {
  const { code, output } = run(["--deploy"], { http: "200" });
  assert.equal(code, 1);
  assert.match(output, /answered «200» without the token, expected 401/);
});

test("an unknown argument deploys nothing", () => {
  const { code, calls } = run(["--force"]);
  assert.equal(code, 1);
  assert.deepEqual(calls, [""]);
});
