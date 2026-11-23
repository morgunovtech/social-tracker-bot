"""The one call to the Claude API: is this comment content the group gets
blocked for, and how sure is the model.

Only what the model needs leaves the server: the comment's text, its picture
(or the thumbnail of a video or sticker), the channel's title and two facts
about the author — whether this is their first message in the group and
whether the message is a forward. No user id, no name, no @username.

The answer is a Verdict: a category from CATEGORIES, a confidence 0–100 and
one sentence of reasoning in the chat language. The number is what the model
writes in a JSON field, not a calibrated probability: the owner's ✅/❌ marks
on the cards are what turns it into one (see monitors/comments.py).
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
# Categories the model may answer with. The first five get the group blocked;
# spam is Defensy's job and only reported quietly; ok is the common case.
DANGEROUS = ("drugs", "sexual", "csam", "extremism", "fraud")
CATEGORIES = (*DANGEROUS, "spam", "ok")
# Not a model answer: the API's safety classifier declined to look at the
# message (stop_reason "refusal"). Shown to the owner as a card of its own.
REFUSED = "refused"

# A classification is a short answer; 512 tokens hold the JSON with room.
MAX_TOKENS = 512
# Per-call deadline and retries (the SDK retries 408/409/429/5xx and
# connection errors by itself): a comment is not worth a long wait, and the
# monitor treats a failure as «could not check», never as «fine».
TIMEOUT_S = 40.0
MAX_RETRIES = 2
# The API accepts images up to 5 MB; Telegram photos are far smaller.
IMAGE_MAX_BYTES = 4 * 1024 * 1024
TEXT_MAX_CHARS = 4000

SYSTEM = """You moderate the comment section of a Telegram channel. For every comment you flag, the channel owner gets a card and decides what to do; you never delete anything yourself. Your job is to say whether a comment is content that Telegram or the law would punish the whole group for, and how sure you are.

Categories:
- drugs: selling or advertising narcotics or their precursors: shop names, "write to the PM" offers, prices, delivery slang ("закладка", "клад", "стафф", "меф", "шишки" and the like) in a selling context.
- sexual: pornography, explicit sexual content or sexual services offered or solicited between adults.
- csam: any sexualization of minors, in words or pictures, including requests and hints.
- extremism: terrorism, calls to violence against a group, recruitment, extremist symbols or propaganda.
- fraud: scams: fake giveaways, "double your crypto", phishing links, "earn from home" pyramids, someone posing as the channel owner or admin to collect money or data.
- spam: unsolicited advertising, link farming, bot-written promotion. Unwanted, but not something the group is blocked for.
- ok: everything else — criticism, rude comments, profanity, politics, jokes, off-topic chatter, quotes and discussion ABOUT these topics without the thing itself.

Rules:
- Be conservative. An angry or off-topic comment is ok. A news item or a complaint about drugs is ok; an offer to buy or sell is drugs. A mention of a scam to warn others is ok.
- confidence is 0–100: how sure you are that the category is right AND that the content is really of that kind. For ok it is how sure you are the comment is harmless. Use the whole range; 50 means you cannot tell.
- When a picture is attached, judge the picture and the text together; a harmless caption on a prohibited picture is still prohibited.
- reason: one short sentence in {language}, naming what in the message says so. Do not repeat slurs, links, contacts or prices.

Answer only with the JSON object."""

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "reason": {"type": "string"},
    },
    "required": ["category", "confidence", "reason"],
    "additionalProperties": False,
}

_LANGUAGE_NAMES = {"ru": "Russian", "en": "English"}


@dataclass(frozen=True)
class Verdict:
    category: str
    confidence: int
    reason: str

    @property
    def flagged(self) -> bool:
        """Anything but a confident ok is shown to the owner."""
        return self.category != "ok"

    @property
    def dangerous(self) -> bool:
        return self.category in DANGEROUS


@dataclass(frozen=True)
class Sample:
    """What is sent: the comment as the model sees it."""

    text: str
    channel_title: str
    first_message: bool
    forwarded: bool
    media: str = ""              # photo | video | sticker | animation | document | ''
    image: bytes | None = None   # the picture or the thumbnail, when there is one


def make_client(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key, timeout=TIMEOUT_S, max_retries=MAX_RETRIES)


def _image_media_type(data: bytes) -> str | None:
    """The MIME type from the first bytes: Telegram serves JPEG photos and
    thumbnails, stickers come as WEBP; anything else is left out."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def build_content(sample: Sample) -> list[dict]:
    """The user turn: a few facts, the text and, when there is one, the picture."""
    facts = [f"Channel: {sample.channel_title or '—'}"]
    facts.append("Author: first message in this group" if sample.first_message else "Author: has written here before")
    if sample.forwarded:
        facts.append("The comment is a forwarded message")
    if sample.media:
        facts.append(f"Attachment: {sample.media}" + ("" if sample.image else " (no preview available)"))
    text = " ".join(sample.text.split())[:TEXT_MAX_CHARS]
    body = "\n".join(facts) + "\n\nComment text:\n" + (text if text else "(no text)")
    content: list[dict] = []
    media_type = _image_media_type(sample.image) if sample.image else None
    if sample.image and media_type and len(sample.image) <= IMAGE_MAX_BYTES:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(sample.image).decode("ascii"),
            },
        })
    content.append({"type": "text", "text": body})
    return content


def parse_verdict(response) -> Verdict:
    """The Verdict in a Message; a refusal is a Verdict of its own kind."""
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        explanation = (getattr(details, "explanation", None) or "").strip()
        return Verdict(REFUSED, 0, explanation)
    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)
    category = data["category"]
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}")
    confidence = max(0, min(100, int(data["confidence"])))
    return Verdict(category, confidence, " ".join(str(data.get("reason", "")).split())[:300])


async def classify(client: anthropic.AsyncAnthropic, model: str, sample: Sample, lang: str = "ru") -> Verdict:
    """One classification. Raises the SDK's errors (and ValueError on a
    malformed answer): the caller decides what «could not check» means."""
    response = await client.beta.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM.replace("{language}", _LANGUAGE_NAMES.get(lang, "English")),
        messages=[{"role": "user", "content": build_content(sample)}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        # A policy decline on the first model re-runs the request on a fallback
        # inside the same call; a refusal on the final answer means every model declined.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    verdict = parse_verdict(response)
    logger.info("Comment classified: %s %d%%", verdict.category, verdict.confidence)
    return verdict
