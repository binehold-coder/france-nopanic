"""Evergreen guides that fill the channel on days without enough useful news.

Each guide is a file content/guides/<slug>.md:

    emoji: 🪪
    title: Як отримати carte Vitale
    status: approved
    ---
    Text of the post (plain text, Ukrainian).
    🔗 https://www.ameli.fr/...   (optional source line)

Only approved guides are published — Женя approves each one after reading it, either by
`status: approved` in the file or with the ✅ button under /guides in the bot (stored in the DB,
which wins over the file, so a ✅/🚫 in the bot always has the last word).
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Guide:
    slug: str
    emoji: str
    title: str
    body: str
    approved: bool


def content_dir() -> Path:
    return Path(os.environ.get("CONTENT_DIR") or Path.cwd() / "content")


def parse(slug: str, text: str) -> Guide | None:
    if "\n---\n" not in text:
        return None
    head, body = text.split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    if not meta.get("title") or not body.strip():
        return None
    return Guide(slug, meta.get("emoji", "📘"), meta["title"], body.strip(), meta.get("status") == "approved")


def load_all(directory: Path | None = None) -> list[Guide]:
    d = (directory or content_dir()) / "guides"
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.md")):
        g = parse(f.stem, f.read_text(encoding="utf-8"))
        if g:
            out.append(g)
    return out


def render(g: Guide) -> str:
    e = html.escape
    lines = []
    for line in g.body.splitlines():
        s = line.strip()
        if s.startswith("🔗 http"):
            url = s[2:].strip()
            lines.append(f'🔗 <a href="{e(url, quote=True)}">Джерело</a>')
        else:
            lines.append(e(line))
    return f"{e(g.emoji)} <b>{e(g.title)}</b>\n\n" + "\n".join(lines)


def is_approved(g: Guide, reviews: dict[str, str]) -> bool:
    decision = reviews.get(g.slug)
    if decision is not None:
        return decision == "approved"
    return g.approved
