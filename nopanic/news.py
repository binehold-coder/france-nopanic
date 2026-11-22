"""News pipeline for the channel: RSS → model picks and rewrites → preview to owner → publish.

Two batches a day keep posts fresh. Each slot has a kind: france / world / light.
The model sees only RSS titles and summaries and must not add facts beyond them.
"""

from __future__ import annotations

import asyncio
import calendar
import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp
import feedparser

from .feeds import FEEDS

log = logging.getLogger(__name__)

# (generation time, [(slot time, kind), ...]) — local time
BATCHES: list[tuple[str, list[tuple[str, str]]]] = [
    ("07:00", [("08:00", "france"), ("09:30", "world"), ("11:00", "france"),
               ("12:30", "world"), ("14:00", "france")]),
    ("14:30", [("15:30", "france"), ("17:00", "world"), ("18:30", "france"),
               ("20:00", "world"), ("21:30", "light")]),
]

MAX_ITEMS = 140
UA = "Mozilla/5.0 (compatible; FranceNoPanicBot/1.0; +https://t.me/france_nopanic)"


@dataclass
class Item:
    source: str
    kind: str
    title: str
    summary: str
    url: str
    published: datetime | None


@dataclass
class Draft:
    kind: str
    emoji: str
    headline: str
    body: str
    source: str
    url: str


def _clean(text: str, limit: int) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    return None


async def _fetch_one(session: aiohttp.ClientSession, name: str, kind: str, url: str) -> tuple[list[Item], str]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return [], f"HTTP {resp.status}"
            raw = await resp.read()
    except Exception as e:  # noqa: BLE001
        return [], type(e).__name__
    parsed = feedparser.parse(raw)
    items = []
    for e in parsed.entries:
        link = (e.get("link") or "").strip()
        title = _clean(e.get("title", ""), 200)
        if not link.startswith("http") or not title:
            continue
        source = name
        src = e.get("source")
        if src and getattr(src, "get", None) and src.get("title"):  # Google News: real publisher
            source = _clean(src.get("title"), 60)
            if title.endswith(" - " + source):
                title = title[: -len(source) - 3]
        summary = _clean(e.get("summary", ""), 400)
        if name == "Google News":
            summary = ""  # Google News summaries just repeat the title as HTML links
        items.append(Item(source, kind, title, summary, link, _published(e)))
    return items, f"ok ({len(items)})" if items else "empty"


async def fetch_all(feeds=FEEDS) -> tuple[list[Item], dict[str, str]]:
    async with aiohttp.ClientSession(headers={"User-Agent": UA}) as session:
        results = await asyncio.gather(*(_fetch_one(session, n, k, u) for n, k, u in feeds))
    status = {u: s for (_, _, u), (_, s) in zip(feeds, results)}
    items = [it for its, _ in results for it in its]
    return items, status


def fresh_unique(items: list[Item], seen: set[str], now: datetime, hours: int = 20) -> list[Item]:
    """Recent, not yet used, one per URL and per near-identical title; newest first."""
    cutoff = now - timedelta(hours=hours)
    out: list[Item] = []
    urls: set[str] = set()
    titles: set[str] = set()
    for it in sorted(items, key=lambda i: i.published or now, reverse=True):
        if it.url in seen or it.url in urls:
            continue
        if it.published and it.published < cutoff:
            continue
        key = re.sub(r"\W+", "", it.title.lower())[:60]
        if key in titles:
            continue
        urls.add(it.url)
        titles.add(key)
        out.append(it)
    return out[:MAX_ITEMS]


NEWS_SYSTEM = """\
You are the editor of the Telegram channel «Франція без паніки» for Ukrainians and Russian \
speakers living in France. You receive a numbered list of fresh news items (title + short \
summary + source). Pick items for the requested slots and write short posts in Ukrainian.

Slot kinds:
- france: news from France that people living here care about or find interesting: daily life, \
prices, transport, strikes, weather alerts, safety, incidents (fires, accidents), society, \
culture, sport, science, notable visits. Not only politics. Prefer variety.
- world: Europe and the world — major events, Ukraine-related news, EU decisions, notable stories.
- light: the last post of the day — funny, kind, curious or heartwarming. No tragedies.

Rules:
- Use ONLY facts present in the item's title and summary. Never add numbers, names, causes or \
consequences that are not there. If an item is too vague to write 2 sentences, pick another.
- Write in your own words in natural Ukrainian; never copy sentences from the source.
- Neutral tone, no opinions, no clickbait, no graphic details of violence.
- Do not pick two items about the same story. Avoid repeating topics already covered today.
- headline: up to 90 characters, no period at the end. body: 2–3 sentences, up to 350 characters.
- emoji: one fitting emoji for the post.
Return JSON with one post per slot, in the slot order given.
"""

NEWS_SCHEMA = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "integer", "description": "Number of the chosen item."},
                    "kind": {"type": "string", "enum": ["france", "world", "light"]},
                    "emoji": {"type": "string"},
                    "headline": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["item", "kind", "emoji", "headline", "body"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["posts"],
    "additionalProperties": False,
}


def items_prompt(items: list[Item], kinds: list[str], covered: list[str]) -> str:
    lines = [f"Slots to fill, in order: {', '.join(kinds)}."]
    if covered:
        lines.append("Already posted today (do not repeat these stories): " + " | ".join(covered))
    lines.append("\nItems:")
    for i, it in enumerate(items, 1):
        lines.append(f"[{i}] ({it.kind}, {it.source}) {it.title} — {it.summary}")
    return "\n".join(lines)


async def write_posts(client, model: str, items: list[Item], kinds: list[str], covered: list[str]) -> tuple[list[Draft], int, int]:
    from .llm import json_call

    data, resp = await json_call(client, model, NEWS_SYSTEM, items_prompt(items, kinds, covered), NEWS_SCHEMA, 4000)
    raw: list[dict] = list(data.get("posts") or [])
    drafts: list[Draft] = []
    used: set[int] = set()
    for p in raw:
        try:
            idx = int(p["item"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 1 <= idx <= len(items) or idx in used:
            continue  # the model may only point at items we gave it
        used.add(idx)
        it = items[idx - 1]
        headline = str(p.get("headline") or "").strip()
        body = str(p.get("body") or "").strip()
        if not headline or not body:
            continue
        drafts.append(Draft(str(p.get("kind") or "france"), str(p.get("emoji") or "📰")[:4],
                            headline[:120], body[:600], it.source, it.url))
    return drafts, resp.usage.input_tokens, resp.usage.output_tokens


def render(d: Draft) -> str:
    e = html.escape
    return (f"{e(d.emoji)} <b>{e(d.headline)}</b>\n\n{e(d.body)}\n\n"
            f"🔗 <a href=\"{e(d.url, quote=True)}\">{e(d.source)}</a>")


async def _check() -> None:
    items, status = await fetch_all()
    for (name, kind, url) in FEEDS:
        print(f"{status[url]:>10}  {kind:8}  {name:12}  {url[:110]}")
    for it in items:
        if it.kind in ("official", "ua"):
            print(f"   · [{it.kind}] {it.source}: {it.title[:110]}")
    print(f"Всего записей: {len(items)}")


if __name__ == "__main__":
    asyncio.run(_check())
