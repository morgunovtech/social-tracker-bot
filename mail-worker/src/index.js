// Receives the security notifications the user forwards (Gmail filter →
// this address), keeps sender, subject and the start of the text in KV, and
// hands them to the bot: GET /events, then POST /events/ack to delete them.
// Classification is the bot's job; nothing here is parsed beyond MIME.
import PostalMime from "postal-mime";

const PREFIX = "evt:";
// Mail the bot never picked up is dropped after two weeks.
const KEEP_SECONDS = 14 * 24 * 3600;
const TEXT_LIMIT = 4000;
const BATCH = 50;

export default {
  async email(message, env) {
    const mail = await PostalMime.parse(message.raw);
    if (
      !senderAllowed(message.from, env.ALLOWED_SENDERS) &&
      !isGmailForwardingConfirmation(message.from, mail.from?.address)
    ) {
      // Visible in `npx wrangler tail`: the address to add to ALLOWED_SENDERS.
      console.log(`rejected: envelope sender ${message.from} is not in ALLOWED_SENDERS`);
      message.setReject("Sender not allowed");
      return;
    }
    const event = {
      received_at: new Date().toISOString(),
      // The header From keeps the original sender through Gmail auto-forwarding.
      from: mail.from?.address || message.from,
      subject: mail.subject || "",
      text: (mail.text || htmlToText(mail.html || "")).slice(0, TEXT_LIMIT),
    };
    // Keys sort by arrival time, so a listing returns the oldest mail first.
    const id = `${PREFIX}${String(Date.now()).padStart(13, "0")}:${crypto.randomUUID()}`;
    await env.EVENTS.put(id, JSON.stringify(event), { expirationTtl: KEEP_SECONDS });
  },

  async fetch(request, env) {
    if (!authorized(request, env.TOKEN)) {
      return json({ error: "unauthorized" }, 401);
    }
    const { pathname } = new URL(request.url);

    if (request.method === "GET" && pathname === "/events") {
      const listing = await env.EVENTS.list({ prefix: PREFIX, limit: BATCH });
      const events = [];
      for (const { name } of listing.keys) {
        const value = await env.EVENTS.get(name);
        // KV listings are eventually consistent: a just-deleted key may still be listed.
        if (value) events.push({ id: name, ...JSON.parse(value) });
      }
      return json({ events });
    }

    if (request.method === "POST" && pathname === "/events/ack") {
      const body = await request.json().catch(() => ({}));
      const ids = (Array.isArray(body.ids) ? body.ids : [])
        .filter((id) => typeof id === "string" && id.startsWith(PREFIX))
        .slice(0, BATCH);
      await Promise.all(ids.map((id) => env.EVENTS.delete(id)));
      return json({ deleted: ids.length });
    }

    return json({ error: "not found" }, 404);
  },
};

// Only the user's own mailbox may feed the bot: an empty list allows no one,
// or anyone who learned the address could post "security alerts" to the chat.
// Gmail rewrites the envelope sender of auto-forwarded mail to
// "me+caf_=…@gmail.com": the +tag is dropped before comparing.
export function senderAllowed(envelopeFrom, allowed) {
  const list = (allowed || "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  const [local = "", domain] = String(envelopeFrom || "").toLowerCase().split("@");
  return list.includes(`${local.split("+")[0]}@${domain}`);
}

// Gmail confirms a new forwarding address with a mail from Google itself, not
// from the allowed mailbox: without it forwarding can't be switched on.
export function isGmailForwardingConfirmation(envelopeFrom, headerFrom) {
  const domain = String(envelopeFrom || "").toLowerCase().split("@")[1] || "";
  const fromGoogle = domain === "google.com" || domain.endsWith(".google.com");
  return fromGoogle && String(headerFrom || "").toLowerCase() === "forwarding-noreply@google.com";
}

export function authorized(request, token) {
  if (!token) return false; // never serve mail without a configured secret
  const header = request.headers.get("Authorization") || "";
  return constantTimeEqual(header, `Bearer ${token}`);
}

function constantTimeEqual(a, b) {
  const x = new TextEncoder().encode(a);
  const y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  }
  return diff === 0;
}

export function htmlToText(html) {
  return html
    .replace(/<(style|script)[\s\S]*?<\/\1>/gi, " ")
    .replace(/<br\s*\/?>|<\/(p|div|tr|li|h\d)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/[ \t]+/g, " ")
    .replace(/\n\s*\n+/g, "\n")
    .trim();
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
