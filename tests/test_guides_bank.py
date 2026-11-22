"""Every file in content/guides must parse and fit into one Telegram message."""

from pathlib import Path

from nopanic import guides

ROOT = Path(__file__).resolve().parent.parent / "content"


def test_all_guide_files_parse_and_fit():
    files = sorted((ROOT / "guides").glob("*.md"))
    loaded = guides.load_all(ROOT)
    assert len(loaded) == len(files), "some guide files failed to parse"
    for g in loaded:
        text = guides.render(g)
        assert len(text) < 4096, f"{g.slug} is too long for Telegram"
        assert '<a href="http' in text, f"{g.slug} has no source link"


def test_callback_data_fits_telegram_limit():
    for g in guides.load_all(ROOT):
        assert len(f"gda:{g.slug}".encode()) <= 64, g.slug


def test_bot_decision_wins_and_is_tied_to_text():
    g = guides.Guide("x", "📘", "T", "body", approved=False)
    d = g.digest
    assert not guides.is_approved(g, {})
    assert guides.is_approved(g, {"x": ("approved", d)})
    assert not guides.is_approved(g, {"x": ("approved", "old")})  # text changed → back to review
    g.approved = True
    assert guides.is_approved(g, {})
    assert not guides.is_approved(g, {"x": ("rejected", d)})


def test_guide_reviews_roundtrip(tmp_path):
    import asyncio

    import aiosqlite

    from nopanic.db import Database

    async def run():
        path = str(tmp_path / "t.db")
        async with aiosqlite.connect(path) as raw:  # table as created by the previous version
            await raw.execute("CREATE TABLE guide_reviews (slug TEXT PRIMARY KEY, status TEXT NOT NULL,"
                              " reviewed_at TEXT NOT NULL)")
            await raw.execute("INSERT INTO guide_reviews VALUES ('old', 'approved', 'x')")
            await raw.commit()
        db = Database(path)
        await db.init()
        await db.set_guide_review("a", "approved", "d1")
        await db.set_guide_review("a", "rejected", "d2")
        return await db.guide_reviews()

    assert asyncio.run(run()) == {"old": ("approved", ""), "a": ("rejected", "d2")}


def test_months():
    assert guides.parse_months("3-8") == frozenset(range(3, 9))
    assert guides.parse_months("11-2") == frozenset({11, 12, 1, 2})
    assert guides.parse_months("4, 5") == frozenset({4, 5})
    assert guides.parse_months("") is None
    assert guides.parse_months("13") is None
    g = guides.Guide("s", "🎒", "T", "b", True, guides.parse_months("3-8"))
    assert guides.in_season(g, 4) and not guides.in_season(g, 11)
    by_slug = {x.slug: x for x in guides.load_all(ROOT)}
    assert not guides.in_season(by_slug["shkola"], 11)
    assert guides.in_season(by_slug["nomery-ekstrenykh"], 11)
