"""Settings from environment (.env on the server, loaded by systemd)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _ids(raw: str) -> frozenset[int]:
    return frozenset(int(x) for x in raw.replace(" ", "").split(",") if x.isdigit())


@dataclass(frozen=True)
class Config:
    bot_token: str
    anthropic_api_key: str
    owner_ids: frozenset[int]
    # "owner" — the bot answers only owners (testing); "public" — everyone.
    access_mode: str = "owner"
    channel: str = "@france_nopanic"
    database_path: str = "data/nopanic.db"
    letter_model: str = "claude-sonnet-5-5"
    chat_model: str = "claude-haiku-5-5"
    free_letters: int = 3
    timezone: str = "Europe/Paris"
    reminder_hour: int = 10
    news_enabled: bool = False
    news_model: str = "claude-sonnet-5-5"
    preview_minutes: int = 30

    @property
    def is_public(self) -> bool:
        return self.access_mode == "public"

    def is_owner(self, user_id: int) -> bool:
        return user_id in self.owner_ids


def load() -> Config:
    env = os.environ
    token = env.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is empty — check /opt/france_nopanic/.env")
    return Config(
        bot_token=token,
        anthropic_api_key=env.get("ANTHROPIC_API_KEY", "").strip(),
        owner_ids=_ids(env.get("OWNER_IDS", "")),
        access_mode=env.get("ACCESS_MODE", "owner").strip() or "owner",
        channel=env.get("CHANNEL", "@france_nopanic").strip() or "@france_nopanic",
        database_path=env.get("DATABASE_PATH", "data/nopanic.db"),
        letter_model=env.get("LETTER_MODEL", "claude-sonnet-5-5"),
        chat_model=env.get("CHAT_MODEL", "claude-haiku-5-5"),
        free_letters=int(env.get("FREE_LETTERS", "3") or 3),
        timezone=env.get("TIMEZONE", "Europe/Paris"),
        reminder_hour=int(env.get("REMINDER_HOUR", "10") or 10),
        news_enabled=env.get("NEWS_ENABLED", "0").strip() in ("1", "true", "yes"),
        news_model=env.get("NEWS_MODEL", "claude-sonnet-5-5"),
        preview_minutes=int(env.get("NEWS_PREVIEW_MIN", "30") or 30),
    )
