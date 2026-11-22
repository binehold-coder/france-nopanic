"""Entry point: python -m nopanic"""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot
from aiogram.types import BotCommand

from . import config
from .bot import App, build_dispatcher, discussion_loop, reminder_loop
from .channel import Channel
from .db import Database
from .llm import LLM


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config.load()
    os.makedirs(os.path.dirname(cfg.database_path) or ".", exist_ok=True)
    db = Database(cfg.database_path)
    await db.init()
    llm = LLM(cfg.anthropic_api_key, cfg.letter_model, cfg.chat_model)
    app = App(cfg, db, llm)

    bot = Bot(cfg.bot_token)
    me = await bot.get_me()
    logging.info(
        "Started @%s, mode=%s, owners=%s, llm=%s", me.username, cfg.access_mode,
        sorted(cfg.owner_ids), "on" if llm.enabled else "OFF (no ANTHROPIC_API_KEY)",
    )
    await bot.set_my_commands([
        BotCommand(command="start", description="Почати / Начать"),
        BotCommand(command="lang", description="Мова / Язык / Langue"),
    ])
    await bot.delete_webhook(drop_pending_updates=False)
    asyncio.create_task(reminder_loop(app, bot))
    asyncio.create_task(discussion_loop(app, bot))
    if cfg.news_enabled and llm.enabled:
        app.channel = Channel(app, bot, cfg.preview_minutes, cfg.news_model)
        asyncio.create_task(app.channel.loop())
        logging.info("News for %s: on (preview %s min, model %s)", cfg.channel, cfg.preview_minutes, cfg.news_model)
    else:
        logging.info("News: off")
    await build_dispatcher(app).start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
