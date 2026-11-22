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

# (generation time, [(window start, window end, kind), ...]) — local time. Each day every slot gets
# a random minute inside its window (stable for the day), so posts don't look machine-timed.
# "news" slots are filled only by items that pass the usefulness bar; empty ones stay empty unless
# the day is below MIN_DAILY_NEWS, then a guide from the bank fills them. "light" = one kind/funny post.
WINDOWS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("07:00", [("08:00", "09:00", "news"), ("12:00", "13:00", "news")]),
    ("14:30", [("15:00", "16:00", "news"), ("18:00", "19:00", "news"), ("20:00", "21:00", "light")]),
]


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def slots_for_day(day: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """BATCHES for a given day: windows turned into concrete HH:MM, same result for the same day."""
    import random

    out = []
    for bi, (gen_at, windows) in enumerate(WINDOWS):
        slots = []
        for wi, (start, end, kind) in enumerate(windows):
            rnd = random.Random(f"{day}:{bi}:{wi}")
            m = rnd.randint(_minutes(start), _minutes(end) - 1)
            slots.append((f"{m // 60:02d}:{m % 60:02d}", kind))
        out.append((gen_at, slots))
    return out


MIN_DAILY_NEWS = 2
MIN_IMPORTANCE = 3          # practical / ukrainians
WORLD_IMPORTANCE = 5        # major_world: only exceptional events

MAX_ITEMS = 200
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
    kind: str          # practical / ukrainians / major_world / light
    importance: int
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
    """Recent, not yet used, one per URL and per near-identical title.
    Official and Ukrainian sources first (they publish rarely, so they get a 48h window)."""
    out: list[Item] = []
    urls: set[str] = set()
    titles: set[str] = set()
    priority = {"official": 0, "ua": 1, "france": 2, "light": 3, "world": 4}
    ordered = sorted(items, key=lambda i: (priority.get(i.kind, 5), -(i.published or now).timestamp()))
    for it in ordered:
        window = timedelta(hours=48 if it.kind in ("official", "ua") else hours)
        if it.url in seen or it.url in urls:
            continue
        if it.published and it.published < now - window:
            continue
        key = re.sub(r"\W+", "", it.title.lower())[:60]
        if key in titles:
            continue
        urls.add(it.url)
        titles.add(key)
        out.append(it)
    return out[:MAX_ITEMS]


NEWS_SYSTEM = """\
You are the editor of the Telegram channel «Франція без паніки» for Ukrainians (and Russian \
speakers) who live in France. The channel publishes only what is USEFUL to them. You receive a \
numbered list of fresh items (source kind, publisher, title, short summary).

Pick items for these categories:
- practical: France-wide changes that affect daily life, money or paperwork of a foreign resident: \
CAF and benefits, Assurance Maladie / ameli / CPAM, taxes and declarations, France Travail, \
préfecture / ANEF / titres de séjour / naturalisation, new rules and "ce qui change" from a date, \
prices and tariffs (energy, transport, rent rules, banking), nationwide strikes in transport, \
red/orange weather alerts, school calendar and procedures.
- ukrainians: ONLY what concerns Ukrainians living abroad: temporary protection status, residence \
after 2027/2028, documents and passports, consular services, military registration / mobilisation \
rules for those abroad, payments and aid, programmes for Ukrainians in France or the EU. \
NOT war events, strikes on cities, front-line news, politics in Ukraine. \
Rules of OTHER EU countries (Austria, Poland, Germany…) — only if it is an EU-wide decision or \
directly changes things for Ukrainians in France; otherwise reject. France first.
- major_world: ONLY an exceptional global event (new war, pandemic, huge disaster, something that \
changes life in Europe). Ordinary politics, elections, diplomacy, crime — never.
- light: one funny, kind, heart-warming or curious story (best from France). No tragedy, no politics.

Reject: local incidents, crime, court cases, demonstrations, sport, celebrities, opinion pieces, \
ordinary politics and parliament debates (unless a rule was actually adopted), advertising, \
foreign news not about the EU/France, anything only relevant to companies or rich investors.

importance (1–5): how much a typical Ukrainian family in France needs to know it. \
5 = must act or affects almost everyone; 3 = useful to many; 1–2 = marginal (reject those).

Voice: write like a person who has lived in France for years and explains news to friends — \
not like a ministry and not like a news agency. Address readers as «ви», warmly. Short sentences. \
Start from what changes for the reader, not from who announced it. Explain French terms in plain \
words. No bureaucratic Ukrainian («здійснити», «надати», «у разі», «відповідно до», «з метою», \
«набуває чинності» → say it simply). A light touch of humour is welcome in light posts and \
sometimes elsewhere; never about tragedies. Make the TONE lively — never invent facts for it.

Writing rules (Ukrainian, natural, own words — never copy sentences):
- Use ONLY facts in the item's title and summary. Never add dates, sums, conditions or names \
that are not there. If the item is too vague for 2 solid sentences, skip it.
- headline: up to 90 characters, no final period; like a person would say it to a friend, \
not a press-release title.
- body: 2–3 sentences, up to 380 characters; when relevant end with what it means in practice \
in plain words (e.g. "Що це означає для вас: ..." or just a natural closing sentence — vary it).
- emoji: one fitting emoji.
- Never two posts about the same story; do not repeat stories already posted today.
- It is fine — and expected — to return FEWER posts than asked, or none, if nothing is useful.
Return JSON.
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
                    "kind": {"type": "string", "enum": ["practical", "ukrainians", "major_world", "light"]},
                    "importance": {"type": "integer"},
                    "emoji": {"type": "string"},
                    "headline": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["item", "kind", "importance", "emoji", "headline", "body"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["posts"],
    "additionalProperties": False,
}


def items_prompt(items: list[Item], news_slots: int, want_light: bool, covered: list[str]) -> str:
    ask = f"Return at most {news_slots} useful posts (practical / ukrainians / major_world)"
    ask += " and exactly one light post." if want_light else ". No light post this time."
    lines = [ask]
    if covered:
        lines.append("Already posted today (do not repeat these stories): " + " | ".join(covered))
    lines.append("\nItems:")
    for i, it in enumerate(items, 1):
        summary = f" — {it.summary}" if it.summary else ""
        lines.append(f"[{i}] ({it.kind}, {it.source}) {it.title}{summary}")
    return "\n".join(lines)


def accept(d: Draft) -> bool:
    if d.kind == "light":
        return True
    if d.kind == "major_world":
        return d.importance >= WORLD_IMPORTANCE
    return d.kind in ("practical", "ukrainians") and d.importance >= MIN_IMPORTANCE


async def write_posts(client, model: str, items: list[Item], news_slots: int, want_light: bool,
                      covered: list[str]) -> tuple[list[Draft], Draft | None, int, int]:
    """Returns (news drafts that pass the bar, most important first; light draft or None; tokens)."""
    from .llm import json_call

    data, resp = await json_call(client, model, NEWS_SYSTEM,
                                 items_prompt(items, news_slots, want_light, covered), NEWS_SCHEMA, 4000)
    raw: list[dict] = list(data.get("posts") or [])
    drafts: list[Draft] = []
    used: set[int] = set()
    for p in raw:
        try:
            idx = int(p["item"])
            importance = int(p.get("importance") or 0)
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
        drafts.append(Draft(str(p.get("kind") or ""), importance, str(p.get("emoji") or "📌")[:4],
                            headline[:120], body[:600], it.source, it.url))
    light = next((d for d in drafts if d.kind == "light"), None) if want_light else None
    news = sorted((d for d in drafts if d.kind != "light" and accept(d)), key=lambda d: -d.importance)
    return news[:news_slots], light, resp.usage.input_tokens, resp.usage.output_tokens


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


async def _dry() -> None:
    import os

    import anthropic

    items, _ = await fetch_all()
    fresh = fresh_unique(items, set(), datetime.now(timezone.utc))
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("NEWS_MODEL", "claude-sonnet-5-5")
    drafts, light, inp, out = await write_posts(client, model, fresh, 4, True, [])
    print(f"{len(fresh)} items -> {len(drafts)} useful, light: {bool(light)}; tokens in {inp} out {out}")
    for d in drafts + ([light] if light else []):
        print(f"\n[{d.kind}, {d.importance}] {d.source} {d.url}\n{d.emoji} {d.headline}\n{d.body}")


if __name__ == "__main__":
    import sys

    asyncio.run(_dry() if sys.argv[1:] == ["dry"] else _check())
