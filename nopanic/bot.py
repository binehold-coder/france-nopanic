"""Telegram handlers: letters in, explanations out."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .config import Config
from .db import Database
from .llm import IMAGE_TYPES, PDF, LLM, Attachment
from .texts import split_message, t

log = logging.getLogger(__name__)

MAX_FILE_BYTES = 20 * 1024 * 1024  # Bot API download limit
MAX_PAGES = 10
ALBUM_WAIT = 1.5  # seconds to collect all photos of one album
FOLLOWUP_DAYS = 14
REMIND_DAYS_BEFORE = [3, 1, 0]


class App:
    def __init__(self, cfg: Config, db: Database, llm: LLM):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.tz = ZoneInfo(cfg.timezone)
        self.albums: dict[str, list[Message]] = {}
        self.locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.awaiting_date: dict[int, int] = {}  # user_id -> letter_id
        self.channel = None  # set in __main__ when news are enabled

    def today(self) -> date:
        return datetime.now(self.tz).date()

    def allowed(self, user_id: int) -> bool:
        return self.cfg.is_public or self.cfg.is_owner(user_id)

    def unlimited(self, user_id: int) -> bool:
        return self.cfg.is_owner(user_id)


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang:uk"),
        InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang:fr"),
        InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
    ]])


def change_lang_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_change_lang", lang), callback_data="chlang"),
    ]])


def letter_keyboard(letter_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_reply", lang), callback_data=f"reply:{letter_id}")],
        [
            InlineKeyboardButton(text=t("btn_remind", lang), callback_data=f"remind:{letter_id}"),
            InlineKeyboardButton(text=t("btn_ask", lang), callback_data=f"ask:{letter_id}"),
        ],
    ])


DATE_RE = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*$")


def parse_user_date(text: str) -> date | None:
    m = DATE_RE.match(text or "")
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    if y < 100:
        y += 2000
    try:
        return date(y, mth, d)
    except ValueError:
        return None


def format_days(days: list[date], lang: str) -> str:
    return ", ".join(d.strftime("%d.%m") for d in days)


def build_router(app: App) -> Router:
    r = Router()

    async def user_lang(user_id: int) -> str:
        return await app.db.get_lang(user_id) or "uk"

    async def gate(message: Message) -> bool:
        """True if the user may use the bot; otherwise answers and returns False."""
        uid = message.from_user.id
        if app.allowed(uid):
            return True
        await message.answer(t("closed", await user_lang(uid)))
        return False

    async def send_long(message: Message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
        parts = split_message(text)
        for i, part in enumerate(parts):
            await message.answer(part, reply_markup=markup if i == len(parts) - 1 else None,
                                 disable_web_page_preview=True)

    # --- start / language ----------------------------------------------------
    @r.message(CommandStart())
    async def start(message: Message) -> None:
        uid = message.from_user.id
        await app.db.ensure_user(uid)
        if not await gate(message):
            return
        lang = await app.db.get_lang(uid)
        if not lang:
            await message.answer(t("choose_lang", None), reply_markup=lang_keyboard())
            return
        await send_welcome(message, lang)

    async def send_welcome(message: Message, lang: str) -> None:
        free = t("free_n", lang, n=app.cfg.free_letters)
        await message.answer(t("welcome", lang, free=free), reply_markup=change_lang_keyboard(lang))
        await message.answer(t("disclaimer", lang) + "\n" + t("privacy", lang))

    @r.message(Command("lang"))
    async def change_lang(message: Message) -> None:
        if not await gate(message):
            return
        await message.answer(t("choose_lang", None), reply_markup=lang_keyboard())

    @r.callback_query(F.data.startswith("lang:"))
    async def set_lang(cb: CallbackQuery) -> None:
        lang = cb.data.split(":", 1)[1]
        if lang not in ("uk", "ru", "fr"):
            return
        first_time = not await app.db.get_lang(cb.from_user.id)
        await app.db.set_lang(cb.from_user.id, lang)
        await cb.answer()
        await cb.message.edit_text(t("lang_set", lang))
        if first_time and app.allowed(cb.from_user.id):
            await send_welcome(cb.message, lang)

    @r.callback_query(F.data == "chlang")
    async def ask_lang(cb: CallbackQuery) -> None:
        await cb.answer()
        await cb.message.answer(t("choose_lang", None), reply_markup=lang_keyboard())

    # --- owner tools -----------------------------------------------------------
    @r.message(Command("stats"))
    async def stats(message: Message) -> None:
        if not app.cfg.is_owner(message.from_user.id):
            return
        s = await app.db.stats(app.cfg.free_letters)
        ru = await user_lang(message.from_user.id) == "ru"
        L = (lambda r_, u_: r_ if ru else u_)
        await message.answer(
            L("📊 Статистика\n", "📊 Статистика\n")
            + L("Пользователей", "Користувачів") + f": {s['users']}\n"
            + L("Писем всего", "Листів усього") + f": {s['letters']} ("
            + L("сегодня", "сьогодні") + f": {s['letters_today']})\n"
            + L("Дошли до лимита", "Дійшли до ліміту") + f": {s['at_limit']}\n"
            + L("Напоминаний в очереди", "Нагадувань у черзі") + f": {s['reminders_pending']}\n"
            + L("Токены: вход", "Токени: вхід") + f" {s['input_tokens']:,}, "
            + L("выход", "вихід") + f" {s['output_tokens']:,}\n"
            + L("Режим", "Режим") + f": {app.cfg.access_mode}; "
            + L("модели", "моделі") + f": {app.cfg.letter_model} / {app.cfg.chat_model}\n"
            + L("Нейросеть", "Нейромережа") + ": "
            + ("✅" if app.llm.enabled else L("❌ нет ключа", "❌ немає ключа"))
        )

    @r.message(Command("channel_test"))
    async def channel_test(message: Message, bot: Bot) -> None:
        if not app.cfg.is_owner(message.from_user.id):
            return
        ru = await user_lang(message.from_user.id) == "ru"
        try:
            sent = await bot.send_message(app.cfg.channel, "🔧 Тест: бот може публікувати в канал. Цей пост можна видалити.")
            await message.answer(
                f"✅ Пост в {app.cfg.channel} опубликован (id {sent.message_id}). Удали его в канале." if ru else
                f"✅ Пост у {app.cfg.channel} опубліковано (id {sent.message_id}). Видали його в каналі."
            )
        except Exception as e:  # noqa: BLE001 — show the owner exactly what Telegram said
            await message.answer(
                (f"❌ Не получилось опубликовать в {app.cfg.channel}: {e}" if ru else
                 f"❌ Не вийшло опублікувати в {app.cfg.channel}: {e}")
            )

    @r.message(Command("news"))
    async def news_plan(message: Message) -> None:
        if not app.cfg.is_owner(message.from_user.id):
            return
        lang = await user_lang(message.from_user.id)
        day = app.today().isoformat()
        posts = await app.db.posts_for_day(day)
        icons = {"planned": "🕒", "previewed": "👀", "publishing": "⏳", "published": "✅",
                 "cancelled": "❌", "failed": "⚠️", "expired": "⌛"}
        if not posts:
            await message.answer("Сегодня постов пока нет." if lang == "ru" else "Сьогодні постів поки немає.")
            return
        lines = [f"{icons.get(p['status'], '?')} {p['slot']} [{p['kind']}] {p['headline']}" for p in posts]
        await message.answer("\n".join(lines))

    @r.message(Command("news_test"))
    async def news_test(message: Message) -> None:
        if not app.cfg.is_owner(message.from_user.id) or app.channel is None:
            return
        await message.answer("⏳ …")
        try:
            await app.channel.dry_run(message.chat.id)
        except Exception as e:  # noqa: BLE001
            log.exception("news_test failed")
            await message.answer(f"⚠️ {type(e).__name__}: {e}"[:500])

    @r.message(Command("sources"))
    async def sources(message: Message) -> None:
        if not app.cfg.is_owner(message.from_user.id):
            return
        from . import news
        from .feeds import FEEDS
        items, status = await news.fetch_all()
        lines = [f"{'✅' if status[u].startswith('ok') else '❌'} {n} ({k}): {status[u]}" for n, k, u in FEEDS]
        await message.answer("\n".join(lines) + f"\n\nΣ {len(items)}")

    @r.callback_query(F.data.startswith(("npc:", "npn:")))
    async def news_action(cb: CallbackQuery) -> None:
        if not app.cfg.is_owner(cb.from_user.id) or app.channel is None:
            await cb.answer()
            return
        from .channel import tr
        lang = await user_lang(cb.from_user.id)
        action, pid = cb.data.split(":")
        if action == "npc":
            ok, status = await app.channel.cancel(int(pid))
            text = tr("cancelled", lang) if ok else tr("too_late", lang, status=status)
        else:
            ok, status = await app.channel.publish(int(pid))
            text = tr("published", lang) if ok else tr("too_late", lang, status=status)
        await cb.answer(text, show_alert=not ok)
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
            await cb.message.reply(text)
        except Exception:
            pass

    # --- letters ---------------------------------------------------------------
    @r.message(F.photo | F.document)
    async def on_file(message: Message, bot: Bot) -> None:
        uid = message.from_user.id
        if not await gate(message):
            return
        key = f"{uid}:{message.media_group_id or message.message_id}"
        if key in app.albums:
            app.albums[key].append(message)
            return
        app.albums[key] = [message]
        await asyncio.sleep(ALBUM_WAIT if message.media_group_id else 0)
        batch = app.albums.pop(key, [])
        async with app.locks[uid]:
            await process_letter(batch, bot)

    async def process_letter(batch: list[Message], bot: Bot) -> None:
        first = batch[0]
        uid = first.from_user.id
        lang = await user_lang(uid)
        await app.db.ensure_user(uid)
        app.awaiting_date.pop(uid, None)

        if not app.llm.enabled:
            await first.answer(t("not_ready", lang))
            return
        used = await app.db.letters_used(uid)
        if not app.unlimited(uid) and used >= app.cfg.free_letters:
            await first.answer(t("limit", lang, n=app.cfg.free_letters))
            return
        if len(batch) > MAX_PAGES:
            await first.answer(t("too_many", lang, n=MAX_PAGES))
            return

        refs: list[tuple[str, str, int]] = []  # file_id, media_type, size
        for m in batch:
            if m.photo:
                p = m.photo[-1]
                refs.append((p.file_id, "image/jpeg", p.file_size or 0))
            elif m.document:
                mt = (m.document.mime_type or "").lower()
                if mt not in IMAGE_TYPES and mt != PDF:
                    await first.answer(t("bad_file", lang))
                    return
                refs.append((m.document.file_id, mt, m.document.file_size or 0))
        if any(size > MAX_FILE_BYTES for _, _, size in refs):
            await first.answer(t("too_big", lang))
            return

        note = next((m.caption for m in batch if m.caption), None)
        status = await first.answer(t("reading", lang))
        await bot.send_chat_action(first.chat.id, ChatAction.TYPING)
        try:
            attachments = []
            for file_id, mt, _ in refs:
                buf = await bot.download(file_id)
                attachments.append(Attachment(buf.read(), mt))
            result = await app.llm.analyze(attachments, lang, app.today(), note)
        except Exception:
            log.exception("letter analysis failed for user %s", uid)
            await status.edit_text(t("error", lang))
            return
        finally:
            attachments = []  # drop file bytes right away

        letter_id = await app.db.add_letter(
            uid, result.sender, result.original_text, result.explanation,
            result.deadline.isoformat() if result.deadline else None, result.deadline_what,
            result.input_tokens, result.output_tokens,
        )
        await app.db.log_usage(uid, "letter", app.llm.letter_model, result.input_tokens, result.output_tokens)

        footer = "\n\n" + t("disclaimer", lang)
        if not app.unlimited(uid):
            left = max(app.cfg.free_letters - used - 1, 0)
            footer += "\n" + t("left", lang, n=left)
        await status.delete()
        await send_long(first, result.explanation + footer, letter_keyboard(letter_id, lang))

    # --- buttons ---------------------------------------------------------------
    @r.callback_query(F.data.startswith("reply:"))
    async def on_reply(cb: CallbackQuery, bot: Bot) -> None:
        uid = cb.from_user.id
        lang = await user_lang(uid)
        letter = await app.db.get_letter(int(cb.data.split(":")[1]), uid)
        await cb.answer()
        if not letter or not app.allowed(uid):
            return
        if not app.llm.enabled:
            await cb.message.answer(t("not_ready", lang))
            return
        status = await cb.message.answer(t("writing_reply", lang))
        await bot.send_chat_action(cb.message.chat.id, ChatAction.TYPING)
        async with app.locks[uid]:
            try:
                res = await app.llm.reply(letter, None, lang, app.today())
            except Exception:
                log.exception("reply failed for user %s", uid)
                await status.edit_text(t("error", lang))
                return
        await app.db.log_usage(uid, "reply", app.llm.letter_model, res.input_tokens, res.output_tokens)
        await status.delete()
        await send_long(cb.message, res.text + "\n\n" + t("reply_hint", lang))

    @r.callback_query(F.data.startswith("remind:"))
    async def on_remind(cb: CallbackQuery) -> None:
        uid = cb.from_user.id
        lang = await user_lang(uid)
        letter = await app.db.get_letter(int(cb.data.split(":")[1]), uid)
        await cb.answer()
        if not letter or not app.allowed(uid):
            return
        if letter.deadline:
            await schedule(cb.message, uid, letter.id, date.fromisoformat(letter.deadline), letter.deadline_what, lang)
        else:
            app.awaiting_date[uid] = letter.id
            await cb.message.answer(t("ask_date", lang))

    async def schedule(message: Message, uid: int, letter_id: int, deadline: date, what: str | None, lang: str) -> None:
        today = app.today()
        shown = deadline.strftime("%d.%m.%Y")
        if deadline < today:
            await message.answer(t("deadline_past", lang, deadline=shown))
            return
        if deadline == today:
            await message.answer(t("deadline_today", lang, deadline=shown))
            return
        days = await app.db.add_reminders(uid, letter_id, deadline, what, REMIND_DAYS_BEFORE, today)
        await message.answer(t("reminders_set", lang, days=format_days(days, lang), deadline=shown))

    @r.callback_query(F.data.startswith("ask:"))
    async def on_ask(cb: CallbackQuery) -> None:
        await cb.answer()
        await cb.message.answer(t("ask_hint", await user_lang(cb.from_user.id)))

    # --- free text -------------------------------------------------------------
    @r.message(F.text & ~F.text.startswith("/"))
    async def on_text(message: Message, bot: Bot) -> None:
        uid = message.from_user.id
        if not await gate(message):
            return
        lang = await user_lang(uid)

        if uid in app.awaiting_date:
            d = parse_user_date(message.text)
            if not d or d < app.today():
                await message.answer(t("bad_date", lang))
                return
            letter_id = app.awaiting_date.pop(uid)
            letter = await app.db.get_letter(letter_id, uid)
            await schedule(message, uid, letter_id, d, letter.deadline_what if letter else None, lang)
            return

        letter = await app.db.last_letter(uid)
        fresh = letter and (datetime.now().astimezone() - datetime.fromisoformat(letter.created_at)).days <= FOLLOWUP_DAYS
        if not fresh:
            await message.answer(t("send_letter", lang))
            return
        if not app.llm.enabled:
            await message.answer(t("not_ready", lang))
            return
        await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        async with app.locks[uid]:
            try:
                res = await app.llm.followup(letter, message.text[:2000], lang, app.today())
            except Exception:
                log.exception("followup failed for user %s", uid)
                await message.answer(t("error", lang))
                return
        await app.db.log_usage(uid, "followup", app.llm.chat_model, res.input_tokens, res.output_tokens)
        await send_long(message, res.text)

    return r


async def reminder_loop(app: App, bot: Bot) -> None:
    """Every 5 minutes: after REMINDER_HOUR local time, send today's due reminders."""
    while True:
        try:
            now = datetime.now(app.tz)
            if now.hour >= app.cfg.reminder_hour:
                for rid, uid, deadline, what in await app.db.due_reminders(now.date()):
                    lang = await app.db.get_lang(uid) or "uk"
                    shown = date.fromisoformat(deadline).strftime("%d.%m.%Y")
                    text = t("reminder", lang, deadline=shown, what=what or t("reminder_default_what", lang))
                    try:
                        await bot.send_message(uid, text)
                    except Exception:  # user blocked the bot etc.
                        log.warning("reminder %s to %s failed", rid, uid, exc_info=True)
                    await app.db.mark_sent(rid)
        except Exception:
            log.exception("reminder loop error")
        await asyncio.sleep(300)


def build_dispatcher(app: App) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(build_router(app))
    return dp
