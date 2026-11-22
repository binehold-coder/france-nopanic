"""SQLite storage. Letter files are never stored — only the model's transcription
and explanation, so follow-up questions and replies work without the image."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    lang TEXT,
    letters_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    sender TEXT,
    original_text TEXT,
    explanation TEXT,
    deadline TEXT,
    deadline_what TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS letters_user ON letters(user_id, id);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    letter_id INTEGER NOT NULL,
    remind_on TEXT NOT NULL,
    deadline TEXT NOT NULL,
    what TEXT,
    sent INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS reminders_due ON reminders(sent, remind_on);
CREATE TABLE IF NOT EXISTS news_batches (
    day TEXT NOT NULL,
    batch INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (day, batch)
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    slot TEXT NOT NULL,
    kind TEXT NOT NULL,
    headline TEXT NOT NULL,
    html TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    message_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS posts_day ON posts(day, slot);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Letter:
    id: int
    user_id: int
    created_at: str
    sender: str | None
    original_text: str | None
    explanation: str | None
    deadline: str | None
    deadline_what: str | None


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    # --- users -------------------------------------------------------------
    async def ensure_user(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, created_at) VALUES (?, ?)", (user_id, _now())
            )
            await db.commit()

    async def get_lang(self, user_id: int) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT lang FROM users WHERE id = ?", (user_id,))
            row = await cur.fetchone()
            return row[0] if row else None

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.ensure_user(user_id)
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET lang = ? WHERE id = ?", (lang, user_id))
            await db.commit()

    async def letters_used(self, user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT letters_used FROM users WHERE id = ?", (user_id,))
            row = await cur.fetchone()
            return row[0] if row else 0

    # --- letters -----------------------------------------------------------
    async def add_letter(
        self,
        user_id: int,
        sender: str | None,
        original_text: str | None,
        explanation: str,
        deadline: str | None,
        deadline_what: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO letters (user_id, created_at, sender, original_text, explanation,"
                " deadline, deadline_what, input_tokens, output_tokens)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, _now(), sender, original_text, explanation, deadline, deadline_what,
                 input_tokens, output_tokens),
            )
            await db.execute(
                "UPDATE users SET letters_used = letters_used + 1 WHERE id = ?", (user_id,)
            )
            await db.commit()
            return cur.lastrowid

    async def get_letter(self, letter_id: int, user_id: int) -> Letter | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id, user_id, created_at, sender, original_text, explanation, deadline,"
                " deadline_what FROM letters WHERE id = ? AND user_id = ?",
                (letter_id, user_id),
            )
            row = await cur.fetchone()
            return Letter(*row) if row else None

    async def last_letter(self, user_id: int) -> Letter | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id, user_id, created_at, sender, original_text, explanation, deadline,"
                " deadline_what FROM letters WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,),
            )
            row = await cur.fetchone()
            return Letter(*row) if row else None

    # --- reminders ---------------------------------------------------------
    async def add_reminders(
        self, user_id: int, letter_id: int, deadline: date, what: str | None, days_before: list[int], today: date
    ) -> list[date]:
        """Schedule reminders N days before the deadline; skips dates already past."""
        planned: list[date] = []
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM reminders WHERE letter_id = ? AND user_id = ? AND sent = 0",
                (letter_id, user_id),
            )
            for n in days_before:
                day = date.fromordinal(deadline.toordinal() - n)
                if day < today:
                    continue
                if day in planned:
                    continue
                planned.append(day)
                await db.execute(
                    "INSERT INTO reminders (user_id, letter_id, remind_on, deadline, what)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (user_id, letter_id, day.isoformat(), deadline.isoformat(), what),
                )
            await db.commit()
        return planned

    async def due_reminders(self, today: date) -> list[tuple[int, int, str, str | None]]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT id, user_id, deadline, what FROM reminders WHERE sent = 0 AND remind_on <= ?",
                (today.isoformat(),),
            )
            return list(await cur.fetchall())

    async def mark_sent(self, reminder_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
            await db.commit()

    # --- channel posts -------------------------------------------------------
    async def batch_done(self, day: str, batch: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT 1 FROM news_batches WHERE day = ? AND batch = ?", (day, batch))
            return await cur.fetchone() is not None

    async def mark_batch(self, day: str, batch: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO news_batches (day, batch, created_at) VALUES (?, ?, ?)",
                             (day, batch, _now()))
            await db.commit()

    async def add_post(self, day: str, slot: str, kind: str, headline: str, html: str, url: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO posts (day, slot, kind, headline, html, url, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (day, slot, kind, headline, html, url, _now()),
            )
            await db.commit()
            return cur.lastrowid

    async def posts_for_day(self, day: str) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM posts WHERE day = ? ORDER BY slot, id", (day,))
            return [dict(r) for r in await cur.fetchall()]

    async def get_post(self, post_id: int) -> dict | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def set_post_status(self, post_id: int, status: str, message_id: int | None = None,
                              only_if: tuple[str, ...] | None = None) -> bool:
        """Change status; with only_if, only from those statuses. True if a row changed."""
        sql = "UPDATE posts SET status = ?, message_id = COALESCE(?, message_id) WHERE id = ?"
        args: list = [status, message_id, post_id]
        if only_if:
            sql += f" AND status IN ({','.join('?' * len(only_if))})"
            args += list(only_if)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(sql, args)
            await db.commit()
            return cur.rowcount > 0

    async def recent_post_urls(self, days: int = 3) -> set[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT url FROM posts WHERE created_at >= datetime('now', ?)", (f"-{days} days",))
            return {r[0] for r in await cur.fetchall()}

    async def cancel_planned_kinds(self, kinds: tuple[str, ...]) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                f"UPDATE posts SET status = 'cancelled' WHERE status IN ('planned', 'previewed')"
                f" AND kind IN ({','.join('?' * len(kinds))})", kinds)
            await db.commit()
            return cur.rowcount

    async def used_guides(self) -> set[str]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT url FROM posts WHERE url LIKE 'guide:%' AND status != 'cancelled'")
            return {r[0][6:] for r in await cur.fetchall()}

    # --- usage / stats -----------------------------------------------------
    async def log_usage(self, user_id: int, kind: str, model: str, inp: int, out: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO usage (user_id, kind, model, input_tokens, output_tokens, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, kind, model, inp, out, _now()),
            )
            await db.commit()

    async def stats(self, free_letters: int = 3) -> dict:
        async with aiosqlite.connect(self.path) as db:
            async def one(sql: str) -> int:
                cur = await db.execute(sql)
                row = await cur.fetchone()
                return int(row[0] or 0)

            return {
                "users": await one("SELECT COUNT(*) FROM users"),
                "letters": await one("SELECT COUNT(*) FROM letters"),
                "letters_today": await one(
                    "SELECT COUNT(*) FROM letters WHERE created_at >= date('now')"
                ),
                "at_limit": await one(f"SELECT COUNT(*) FROM users WHERE letters_used >= {int(free_letters)}"),
                "reminders_pending": await one("SELECT COUNT(*) FROM reminders WHERE sent = 0"),
                "input_tokens": await one("SELECT SUM(input_tokens) FROM usage"),
                "output_tokens": await one("SELECT SUM(output_tokens) FROM usage"),
            }
