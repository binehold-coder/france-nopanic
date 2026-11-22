"""Anthropic calls. Documents go to the model straight from memory and are never written to disk."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date

import anthropic

from . import prompts
from .db import Letter

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
        resp = await self.client.messages.create(
            model=self.letter_model,
            max_tokens=4000,
            system=prompts.analysis_system(lang, today.isoformat()),
            messages=[{"role": "user", "content": content}],
            tools=[prompts.LETTER_TOOL],
            tool_choice={"type": "tool", "name": "letter_analysis"},
        )
        data: dict = {}
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                data = dict(block.input)
                break
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
