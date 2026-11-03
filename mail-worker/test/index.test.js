import assert from "node:assert/strict";
import { test } from "node:test";

import worker, { htmlToText, senderAllowed } from "../src/index.js";

class MemoryKV {
  constructor() {
    this.store = new Map();
    this.ttl = new Map();
  }
  async put(key, value, options = {}) {
    this.store.set(key, value);
    this.ttl.set(key, options.expirationTtl);
  }
  async get(key) {
    return this.store.get(key) ?? null;
  }
  async delete(key) {
    this.store.delete(key);
  }
  async list({ prefix, limit }) {
    const keys = [...this.store.keys()].filter((k) => k.startsWith(prefix)).sort().slice(0, limit);
    return { keys: keys.map((name) => ({ name })) };
  }
}

function envWith(extra = {}) {
  return { EVENTS: new MemoryKV(), TOKEN: "s3cret", ALLOWED_SENDERS: "me@gmail.com", ...extra };
}

const RAW = [
  "From: Google <no-reply@accounts.google.com>",
  "To: me@gmail.com",
  "Subject: =?UTF-8?B?0J7Qv9C+0LLQtdGJ0LXQvdC40LUg0YHQuNGB0YLQtdC80Ysg0LHQtdC30L7Qv9Cw0YHQvdC+0YHRgtC4?=",
  "Content-Type: text/html; charset=utf-8",
  "",
  "<p>Выполнен вход в аккаунт</p><style>p{}</style><p>с нового устройства &amp; браузера</p>",
].join("\r\n");

function emailMessage(raw, envelopeFrom = "me+caf_=bot=example.com@gmail.com") {
  const rejected = [];
  return {
    from: envelopeFrom,
    raw: new Response(raw).body,
    setReject: (reason) => rejected.push(reason),
    rejected,
  };
}

function request(method, path, { token = "s3cret", body } = {}) {
  return new Request(`https://mail.example${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

test("stores a parsed mail and serves it oldest first", async () => {
  const env = envWith();
  await worker.email(emailMessage(RAW), env);
  await new Promise((resolve) => setTimeout(resolve, 5)); // keys order by millisecond
  await worker.email(emailMessage(RAW.replace("accounts.google.com", "linkedin.com")), env);

  const res = await worker.fetch(request("GET", "/events"), env);
  assert.equal(res.status, 200);
  const { events } = await res.json();
  assert.equal(events.length, 2);
  assert.equal(events[0].from, "no-reply@accounts.google.com");
  assert.equal(events[0].subject, "Оповещение системы безопасности");
  assert.match(events[0].text, /Выполнен вход в аккаунт\s+с нового устройства & браузера/);
  assert.ok(events[0].id < events[1].id);
  assert.equal([...env.EVENTS.ttl.values()][0], 14 * 24 * 3600);
});

test("ack deletes only event keys", async () => {
  const env = envWith();
  await worker.email(emailMessage(RAW), env);
  await env.EVENTS.put("other", "keep");
  const { events } = await (await worker.fetch(request("GET", "/events"), env)).json();

  const res = await worker.fetch(request("POST", "/events/ack", { body: { ids: [events[0].id, "other"] } }), env);
  assert.deepEqual(await res.json(), { deleted: 1 });
  assert.deepEqual([...env.EVENTS.store.keys()], ["other"]);
});

test("requests without the token are refused", async () => {
  const env = envWith();
  assert.equal((await worker.fetch(request("GET", "/events", { token: "wrong" }), env)).status, 401);
  const noSecret = envWith({ TOKEN: "" });
  assert.equal((await worker.fetch(request("GET", "/events", { token: "" }), noSecret)).status, 401);
  assert.equal((await worker.fetch(request("GET", "/nope"), env)).status, 404);
});

test("allowlist matches the forwarding mailbox without its +tag", async () => {
  assert.ok(senderAllowed("me+caf_=bot=example.com@gmail.com", "me@gmail.com"));
  assert.ok(!senderAllowed("anyone@example.com", ""));          // an empty list fails closed
  assert.ok(!senderAllowed("", "me@gmail.com"));
  assert.ok(!senderAllowed("attacker@evil.example", "me@gmail.com, you@proton.me"));

  const env = envWith({ ALLOWED_SENDERS: "me@gmail.com" });
  const message = emailMessage(RAW, "attacker@evil.example");
  await worker.email(message, env);
  assert.deepEqual(message.rejected, ["Sender not allowed"]);
  assert.equal(env.EVENTS.store.size, 0);
});

test("Gmail's forwarding confirmation passes the allowlist, a lookalike doesn't", async () => {
  const confirmation = RAW.replace("Google <no-reply@accounts.google.com>", "forwarding-noreply@google.com");
  const env = envWith({ ALLOWED_SENDERS: "me@gmail.com" });

  await worker.email(emailMessage(confirmation, "bounce-123@bounces.google.com"), env);
  assert.equal(env.EVENTS.store.size, 1);

  const spoofed = emailMessage(confirmation, "forwarding-noreply@google.com.evil.example");
  await worker.email(spoofed, env);
  assert.deepEqual(spoofed.rejected, ["Sender not allowed"]);
});

test("html is reduced to text", () => {
  assert.equal(htmlToText("<div>a<br>b</div><script>x()</script>&lt;c&gt;"), "a\nb\n <c>");
});
