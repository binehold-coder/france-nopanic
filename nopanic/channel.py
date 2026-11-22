"""Channel scheduler: generates news batches, previews them to the owner, publishes on time."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions

from . import news

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(minutes=15)

L = {
    "preview": {"uk": "🕒 О {slot} вийде в канал:", "ru": "🕒 В {slot} выйдет в канал:", "fr": "🕒 Publication à {slot} :"},
    "veto": {"uk": "❌ Не публікувати", "ru": "❌ Не публиковать", "fr": "❌ Ne pas publier"},
    "now": {"uk": "✅ Зараз", "ru": "✅ Сейчас", "fr": "✅ Maintenant"},
    "cancelled": {"uk": "❌ Скасовано — в канал не піде.", "ru": "❌ Отменено — в канал не пойдёт.", "fr": "❌ Annulé."},
    "published": {"uk": "✅ Опубліковано.", "ru": "✅ Опубликовано.", "fr": "✅ Publié."},
    "too_late": {"uk": "Цей пост уже {status}.", "ru": "Этот пост уже {status}.", "fr": "Déjà {status}."},
    "gen_failed": {
        "uk": "⚠️ Не вдалося підготувати новини ({err}). Спробую ще раз через 15 хв.",
        "ru": "⚠️ Не получилось подготовить новости ({err}). Попробую ещё раз через 15 мин.",
        "fr": "⚠️ Échec de préparation des actus ({err}). Nouvel essai dans 15 min.",
    },
    "pub_failed": {"uk": "⚠️ Пост не опубліковано: {err}", "ru": "⚠️ Пост не опубликован: {err}", "fr": "⚠️ Non publié : {err}"},
}

CTA = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="📩 Незрозумілий лист? Поясню", url="https://t.me/france_nopanic_bot?start=channel"),
]])


def tr(key: str, lang: str, **kw) -> str:
    s = L[key].get(lang) or L[key]["uk"]
    return s.format(**kw) if kw else s


class Channel:
    def __init__(self, app, bot: Bot, preview_minutes: int, model: str):
        self.app = app
        self.bot = bot
        self.preview = timedelta(minutes=preview_minutes)
        self.model = model
        self.attempts: dict[tuple[str, int], tuple[int, datetime]] = {}

    @property
    def db(self):
        return self.app.db

    def now(self) -> datetime:
        return datetime.now(self.app.tz)

    def slot_dt(self, day: str, slot: str) -> datetime:
        return datetime.fromisoformat(f"{day}T{slot}:00").replace(tzinfo=self.app.tz)

    async def owner_langs(self) -> list[tuple[int, str]]:
        return [(uid, await self.db.get_lang(uid) or "uk") for uid in sorted(self.app.cfg.owner_ids)]

    async def notify_owners(self, key: str, **kw) -> None:
        for uid, lang in await self.owner_langs():
            try:
                await self.bot.send_message(uid, tr(key, lang, **kw))
            except Exception:
                log.warning("notify %s failed", uid, exc_info=True)

    # --- generation ------------------------------------------------------------
    async def generate(self, day: str, slots: list[tuple[str, str]]) -> int:
        items, status = await news.fetch_all()
        broken = [u for u, s in status.items() if not s.startswith("ok")]
        if broken:
            log.info("feeds without items: %s", broken)
        seen = await self.db.recent_post_urls()
        fresh = news.fresh_unique(items, seen, datetime.now(timezone.utc))
        if not fresh:
            raise RuntimeError("no fresh news items")
        covered = [p["headline"] for p in await self.db.posts_for_day(day)]
        drafts, inp, out = await news.write_posts(
            self.app.llm.client, self.model, fresh, [k for _, k in slots], covered
        )
        await self.db.log_usage(0, "news", self.model, inp, out)
        for (slot, kind), d in zip(slots, drafts):
            await self.db.add_post(day, slot, kind, d.headline, news.render(d), d.url)
        log.info("news batch for %s: %d/%d posts from %d items", day, min(len(drafts), len(slots)), len(slots), len(fresh))
        return min(len(drafts), len(slots))

    async def maybe_generate(self, now: datetime) -> None:
        day = now.date().isoformat()
        hhmm = now.strftime("%H:%M")
        soon = (now + timedelta(minutes=2)).strftime("%H:%M")
        for idx, (gen_at, slots) in enumerate(news.BATCHES):
            if hhmm < gen_at or await self.db.batch_done(day, idx):
                continue
            remaining = [(t, k) for t, k in slots if t > soon]
            if not remaining:
                await self.db.mark_batch(day, idx)
                continue
            n, last = self.attempts.get((day, idx), (0, now - RETRY_AFTER))
            if n >= MAX_ATTEMPTS or now - last < RETRY_AFTER:
                continue
            self.attempts[(day, idx)] = (n + 1, now)
            try:
                await self.generate(day, remaining)
                await self.db.mark_batch(day, idx)
            except Exception as e:  # noqa: BLE001
                log.exception("news batch %s/%s failed", day, idx)
                await self.notify_owners("gen_failed", err=type(e).__name__)
                if n + 1 >= MAX_ATTEMPTS:
                    await self.db.mark_batch(day, idx)

    # --- preview / publish -------------------------------------------------------
    async def send_preview(self, post: dict) -> None:
        for uid, lang in await self.owner_langs():
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=tr("veto", lang), callback_data=f"npc:{post['id']}"),
                InlineKeyboardButton(text=tr("now", lang), callback_data=f"npn:{post['id']}"),
            ]])
            try:
                await self.bot.send_message(
                    uid, tr("preview", lang, slot=post["slot"]) + "\n\n" + post["html"],
                    parse_mode=ParseMode.HTML, reply_markup=kb,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception:
                log.warning("preview %s to %s failed", post["id"], uid, exc_info=True)

    async def publish(self, post_id: int) -> tuple[bool, str]:
        post = await self.db.get_post(post_id)
        if not post:
            return False, "missing"
        # claim the post first so a button press and the scheduler never publish twice
        if not await self.db.set_post_status(post_id, "publishing", only_if=("planned", "previewed")):
            return False, post["status"]
        try:
            msg = await self.bot.send_message(
                self.app.cfg.channel, post["html"], parse_mode=ParseMode.HTML, reply_markup=CTA,
                link_preview_options=LinkPreviewOptions(prefer_small_media=True),
            )
        except Exception as e:  # noqa: BLE001
            log.exception("publish %s failed", post_id)
            await self.db.set_post_status(post_id, "failed")
            await self.notify_owners("pub_failed", err=str(e)[:200])
            return False, "failed"
        await self.db.set_post_status(post_id, "published", message_id=msg.message_id)
        return True, "published"

    async def cancel(self, post_id: int) -> tuple[bool, str]:
        ok = await self.db.set_post_status(post_id, "cancelled", only_if=("planned", "previewed"))
        if ok:
            return True, "cancelled"
        post = await self.db.get_post(post_id)
        return False, post["status"] if post else "missing"

    async def tick(self) -> None:
        now = self.now()
        await self.maybe_generate(now)
        day = now.date().isoformat()
        for post in await self.db.posts_for_day(day):
            at = self.slot_dt(day, post["slot"])
            if post["status"] == "planned" and now >= at - self.preview and now < at:
                if await self.db.set_post_status(post["id"], "previewed", only_if=("planned",)):
                    await self.send_preview(post)
            if post["status"] in ("planned", "previewed") and now >= at:
                await self.publish(post["id"])

    async def loop(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("channel loop error")
            await asyncio.sleep(60)
