"""Anthropic calls. Documents go to the model straight from memory and are never written to disk."""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import date

import anthropic

from . import prompts
from .db import Letter

log = logging.getLogger(__name__)

PDF = "application/pdf"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@dataclass
class Attachment:
    data: bytes
    media_type: str


@dataclass
class Analysis:
    sender: str | None
    explanation: str
    original_text: str | None
    deadline: date | None
    deadline_what: str | None
    needs_lawyer: bool
    input_tokens: int
    output_tokens: int


@dataclass
class TextResult:
    text: str
    input_tokens: int
    output_tokens: int


def parse_deadline(raw: object) -> date | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def attachment_block(att: Attachment) -> dict:
    data = base64.standard_b64encode(att.data).decode()
    if att.media_type == PDF:
        return {"type": "document", "source": {"type": "base64", "media_type": PDF, "data": data}}
    return {"type": "image", "source": {"type": "base64", "media_type": att.media_type, "data": data}}


def letter_context(letter: Letter) -> str:
    return (
        f"Letter (French transcription):\n{letter.original_text or '(not available)'}\n\n"
        f"Explanation already given to the user:\n{letter.explanation or ''}"
    )


_structured_ok: bool | None = None  # does the API accept output_config json_schema for us?


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


async def json_call(client, model: str, system: str, content, schema: dict, max_tokens: int):
    """One request that returns a dict matching `schema`, plus the response (for usage).
    Uses structured outputs; if the API refuses them, falls back to 'reply with JSON only'."""
    global _structured_ok
    messages = [{"role": "user", "content": content}]
    if _structured_ok is not False:
        try:
            resp = await client.messages.create(
                model=model, max_tokens=max_tokens, system=system, messages=messages,
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            _structured_ok = True
            return _extract_json(text), resp
        except anthropic.BadRequestError as e:
            if _structured_ok is True:
                raise
            log.warning("structured output refused, falling back to plain JSON: %s", e)
            _structured_ok = False
    resp = await client.messages.create(
        model=model, max_tokens=max_tokens, messages=messages,
        system=system + "\n\nReply with ONLY one JSON object (no prose, no code fences) matching this JSON schema:\n"
        + json.dumps(schema, ensure_ascii=False),
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return _extract_json(text), resp


class LLM:
    def __init__(self, api_key: str, letter_model: str, chat_model: str):
        self.enabled = bool(api_key)
        self.letter_model = letter_model
        self.chat_model = chat_model
        self.client = anthropic.AsyncAnthropic(api_key=api_key or "missing", max_retries=2, timeout=180)

    async def analyze(self, attachments: list[Attachment], lang: str, today: date, note: str | None) -> Analysis:
        content: list[dict] = [attachment_block(a) for a in attachments]
        ask = "Explain this document." if len(attachments) == 1 else (
            f"These {len(attachments)} files are pages of one document. Explain it."
        )
        if note:
            ask += f"\nThe user added: {note}"
        content.append({"type": "text", "text": ask})
        data, resp = await json_call(
            self.client, self.letter_model, prompts.analysis_system(lang, today.isoformat()),
            content, prompts.LETTER_SCHEMA, 4000,
        )
        explanation = str(data.get("explanation") or "").strip()
        if not explanation:
            raise RuntimeError("model returned no explanation")
        return Analysis(
            sender=data.get("sender") or None,
            explanation=explanation,
            original_text=data.get("original_text") or None,
            deadline=parse_deadline(data.get("deadline")),
            deadline_what=data.get("deadline_what") or None,
            needs_lawyer=bool(data.get("needs_lawyer")),
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )

    async def _text(self, model: str, system: str, user: str, max_tokens: int = 2000) -> TextResult:
        resp = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        return TextResult(text, resp.usage.input_tokens, resp.usage.output_tokens)

    async def followup(self, letter: Letter, question: str, lang: str, today: date) -> TextResult:
        return await self._text(
            self.chat_model,
            prompts.followup_system(lang, today.isoformat()),
            f"{letter_context(letter)}\n\nQuestion: {question}",
        )

    async def reply(self, letter: Letter, details: str | None, lang: str, today: date) -> TextResult:
        user = letter_context(letter)
        if details:
            user += f"\n\nDetails from the user for the reply: {details}"
        return await self._text(self.letter_model, prompts.reply_system(lang, today.isoformat()), user, 2500)
