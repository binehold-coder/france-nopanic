from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as N
from zoneinfo import ZoneInfo

from nopanic import news
from nopanic.channel import Channel
from nopanic.db import Database

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def item(i, title=None, hours=1, url=None):
    return news.Item("Src", "france", title or f"Title {i}", f"Summary {i}", url or f"https://x/{i}",
                     NOW - timedelta(hours=hours))


def test_fresh_unique_filters():
    items = [item(1), item(2, title="Title 1"), item(3, hours=30), item(4, url="https://x/seen"), item(5)]
    out = news.fresh_unique(items, {"https://x/seen"}, NOW)
    assert [i.url for i in out] == ["https://x/1", "https://x/5"] or [i.url for i in out] == ["https://x/5", "https://x/1"]


def test_render_escapes():
    d = news.Draft("practical", 3, "🔥", "Пожежа <b>", "Текст & ще", "Le Monde", 'https://x/?a=1&b="2"')
    h = news.render(d)
    assert "&lt;b&gt;" in h and "&amp; ще" in h and "&quot;" in h


async def test_write_posts_bar_and_light():
    async def create(**kw):
        import json
        return N(content=[N(type="text", text=json.dumps({"posts": [
            {"item": 1, "kind": "practical", "importance": 3, "emoji": "🚆", "headline": "A", "body": "B"},
            {"item": 99, "kind": "practical", "importance": 5, "emoji": "x", "headline": "X", "body": "Y"},
            {"item": 2, "kind": "ukrainians", "importance": 5, "emoji": "🇺🇦", "headline": "U", "body": "U"},
            {"item": 3, "kind": "major_world", "importance": 4, "emoji": "🌍", "headline": "W", "body": "W"},
            {"item": 4, "kind": "practical", "importance": 2, "emoji": "·", "headline": "low", "body": "low"},
            {"item": 5, "kind": "light", "importance": 1, "emoji": "😊", "headline": "L", "body": "L"},
        ]}))], usage=N(input_tokens=10, output_tokens=5))
    client = N(messages=N(create=create))
    items = [item(i) for i in range(1, 6)]
    news_d, light, i, o = await news.write_posts(client, "m", items, 3, True, [])
    assert [d.headline for d in news_d] == ["U", "A"]  # by importance; world<5 and low importance rejected
    assert light.headline == "L" and light.url == "https://x/5"
    news_d, light, i, o = await news.write_posts(client, "m", items, 1, False, [])
    assert [d.headline for d in news_d] == ["U"] and light is None


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat, text, **kw):
        self.sent.append((chat, text))
        return N(message_id=len(self.sent))


async def test_channel_preview_publish_and_veto(tmp_path):
    db = Database(str(tmp_path / "c.db"))
    await db.init()
    tz = ZoneInfo("Europe/Paris")
    app = N(db=db, tz=tz, cfg=N(owner_ids={1}, channel="@ch"), llm=N(client=None))
    bot = FakeBot()
    ch = Channel(app, bot, 30, "m")
    day = "2026-11-22"
    a = await db.add_post(day, "18:30", "france", "A", "<b>A</b>", "https://x/a")
    b = await db.add_post(day, "20:00", "world", "B", "<b>B</b>", "https://x/b")
    await db.mark_batch(day, 0)
    await db.mark_batch(day, 1)

    ch.now = lambda: datetime(2026, 11, 22, 18, 5, tzinfo=tz)
    await ch.tick()
    assert (await db.get_post(a))["status"] == "previewed" and len(bot.sent) == 1 and bot.sent[0][0] == 1

    assert (await ch.cancel(b))[0] is True
    ch.now = lambda: datetime(2026, 11, 22, 18, 31, tzinfo=tz)
    await ch.tick()
    assert (await db.get_post(a))["status"] == "published"
    assert (await db.get_post(b))["status"] == "cancelled"
    assert [c for c, _ in bot.sent].count("@ch") == 1
    assert (await ch.publish(a)) == (False, "published")  # no double publish


async def test_fill_minimum_with_guides(tmp_path, monkeypatch):
    gdir = tmp_path / "content" / "guides"
    gdir.mkdir(parents=True)
    (gdir / "a-vitale.md").write_text("emoji: 🪪\ntitle: Carte Vitale\nstatus: approved\n---\nТекст\n🔗 https://ameli.fr/x", encoding="utf-8")
    (gdir / "b-draft.md").write_text("title: Чернетка\nstatus: draft\n---\nТекст", encoding="utf-8")
    (gdir / "c-bank.md").write_text("title: Банк\nstatus: approved\n---\nТекст", encoding="utf-8")
    monkeypatch.setenv("CONTENT_DIR", str(tmp_path / "content"))
    db = Database(str(tmp_path / "g.db"))
    await db.init()
    app = N(db=db, tz=ZoneInfo("Europe/Paris"), cfg=N(owner_ids={1}, channel="@ch"), llm=N(client=None))
    bot = FakeBot()
    ch = Channel(app, bot, 30, "m")
    day = "2026-11-23"
    await db.add_post(day, "09:00", "practical", "N", "<b>N</b>", "https://x/n")
    await ch.fill_minimum(day, ["15:30", "18:00"])
    posts = await db.posts_for_day(day)
    assert [(p["slot"], p["kind"]) for p in posts] == [("09:00", "practical"), ("15:30", "guide")]
    assert "Carte Vitale" in posts[1]["html"] and 'href="https://ameli.fr/x"' in posts[1]["html"]
    await ch.fill_minimum("2026-11-24", ["15:30", "18:00"])
    nxt = await db.posts_for_day("2026-11-24")
    assert [p["url"] for p in nxt] == ["guide:c-bank"]  # a-vitale already used, drafts skipped; bank now empty


async def test_stale_posts_expire(tmp_path):
    db = Database(str(tmp_path / "s.db"))
    await db.init()
    tz = ZoneInfo("Europe/Paris")
    app = N(db=db, tz=tz, cfg=N(owner_ids={1}, channel="@ch"), llm=N(client=None))
    bot = FakeBot()
    ch = Channel(app, bot, 30, "m")
    day = "2026-11-22"
    old = await db.add_post(day, "09:00", "practical", "Old", "x", "https://x/o")
    legacy = await db.add_post(day, "22:00", "france", "Legacy", "x", "https://x/l")
    await db.mark_batch(day, 0)
    await db.mark_batch(day, 1)
    assert await db.cancel_planned_kinds(("france", "world")) == 1
    ch.now = lambda: datetime(2026, 11, 22, 18, 40, tzinfo=tz)
    await ch.tick()
    assert (await db.get_post(old))["status"] == "expired"
    assert (await db.get_post(legacy))["status"] == "cancelled"
    assert bot.sent == []
