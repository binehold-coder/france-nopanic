"""Answers in the channel's comments (the linked discussion group).

The bot answers only real questions about the post or a practical topic, briefly, in the
commenter's language. Thanks, emotions, arguments, politics and trolling get no answer.
Replies appear under the bot's name (the Bot API cannot post as the channel).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import date

from aiogram import Bot, F, Router
from aiogram.types import Message

from .llm import json_call

log = logging.getLogger(__name__)

PER_USER_PER_HOUR = 3
PER_DAY = 60

SYSTEM = """\
You answer comments under posts of the Telegram channel «Франція без паніки» for Ukrainians and \
Russian speakers living in France. You speak as the channel's assistant.

Decide whether to reply. Reply ONLY if the comment asks a question or shows a misunderstanding \
about the post or a practical topic of life in France (documents, CAF, health insurance, taxes, \
work, residence, temporary protection, transport, prices). Do NOT reply to: thanks, emotions, \
jokes, opinions, arguments between people, politics, war, insults, spam, advertising, or anything \
off-topic. When in doubt — do not reply.

If you reply:
- Same language as the comment (Ukrainian or Russian; French if the comment is in French).
- 1–3 short sentences, friendly and calm, plain text, no Markdown.
- Sound like a helpful person who lives in France, not like an official: simple words, no \
bureaucratic phrases, no «шановний».
- Use only facts from the post or well-established general rules. Never invent dates, sums or \
conditions; if not sure, say where to check (service-public.fr, the organisation's site, \
France Services).
- No personal legal advice. If the person has their own letter or case, suggest sending the \
letter to @france_nopanic_bot for an explanation; for refusals, OQTF, court — a lawyer or Point-justice.
Return JSON: {"reply": true/false, "text": "..."}.
"""

SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "boolean"}, "text": {"type": "string"}},
    "required": ["reply", "text"],
    "additionalProperties": False,
}


class Limits:
    def __init__(self) -> None:
        self.user_hits: dict[int, deque[float]] = defaultdict(deque)
        self.day = date.today()
        self.day_count = 0

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        if date.today() != self.day:
            self.day, self.day_count = date.today(), 0
        hits = self.user_hits[user_id]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= PER_USER_PER_HOUR or self.day_count >= PER_DAY:
            return False
        hits.append(now)
        self.day_count += 1
        return True


def context_of(message: Message, bot_id: int) -> str | None:
    """Text the comment refers to: the channel post, or the bot's own earlier answer."""
    parent = message.reply_to_message
    if parent is None:
        return None
    text = parent.text or parent.caption or ""
    if parent.is_automatic_forward:
        return f"Channel post:\n{text}"
    if parent.from_user and parent.from_user.id == bot_id:
        return f"Your earlier answer in this thread:\n{text}"
    return None  # a reply to another commenter — stay out of people's conversations


def build_comments_router(app) -> Router:
    r = Router()
    limits = Limits()

    @r.message(F.chat.type.in_({"group", "supergroup"}), F.text)
    async def on_comment(message: Message, bot: Bot) -> None:
        if not app.discussion_id or message.chat.id != app.discussion_id:
            return
        if message.is_automatic_forward or not message.from_user or message.from_user.is_bot:
            return
        if message.sender_chat:  # posted as a channel/anonymous admin
            return
        me = await bot.me()
        ctx = context_of(message, me.id)
        if ctx is None or not app.llm.enabled or len(message.text) < 8:
            return
        if not limits.allow(message.from_user.id):
            return
        try:
            data, resp = await json_call(
                app.llm.client, app.cfg.chat_model, SYSTEM,
                f"{ctx}\n\nComment:\n{message.text[:1500]}", SCHEMA, 600,
            )
            await app.db.log_usage(message.from_user.id, "comment", app.cfg.chat_model,
                                   resp.usage.input_tokens, resp.usage.output_tokens)
        except Exception:
            log.exception("comment answer failed")
            return
        text = str(data.get("text") or "").strip()
        if data.get("reply") and text:
            await message.reply(text[:1500])

    return r
