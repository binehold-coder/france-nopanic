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
    d = news.Draft("france", "🔥", "Пожежа <b>", "Текст & ще", "Le Monde", 'https://x/?a=1&b="2"')
    h = news.render(d)
    assert "&lt;b&gt;" in h and "&amp; ще" in h and "&quot;" in h


async def test_write_posts_drops_invented_items():
    async def create(**kw):
        return N(content=[N(type="tool_use", input={"posts": [
            {"item": 1, "kind": "france", "emoji": "🚆", "headline": "A", "body": "B"},
            {"item": 99, "kind": "world", "emoji": "🌍", "headline": "X", "body": "Y"},
            {"item": 1, "kind": "world", "emoji": "🌍", "headline": "dup", "body": "dup"},
            {"item": 2, "kind": "light", "emoji": "😊", "headline": "C", "body": "D"},
        ]})], usage=N(input_tokens=10, output_tokens=5))
    client = N(messages=N(create=create))
    drafts, i, o = await news.write_posts(client, "m", [item(1), item(2)], ["france", "world", "light"], [])
    assert [d.headline for d in drafts] == ["A", "C"]
    assert drafts[0].url == "https://x/1"


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
    ch.now = lambda: datetime(2026, 11, 22, 20, 1, tzinfo=tz)
    await ch.tick()
    assert (await db.get_post(a))["status"] == "published"
    assert (await db.get_post(b))["status"] == "cancelled"
    assert [c for c, _ in bot.sent].count("@ch") == 1
    assert (await ch.publish(a)) == (False, "published")  # no double publish
