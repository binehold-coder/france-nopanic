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


def test_bot_decision_wins_over_file_status():
    g = guides.Guide("x", "📘", "T", "body", approved=False)
    assert not guides.is_approved(g, {})
    assert guides.is_approved(g, {"x": "approved"})
    g.approved = True
    assert guides.is_approved(g, {})
    assert not guides.is_approved(g, {"x": "rejected"})


def test_guide_reviews_roundtrip(tmp_path):
    import asyncio

    from nopanic.db import Database

    async def run():
        db = Database(str(tmp_path / "t.db"))
        await db.init()
        await db.set_guide_review("a", "approved")
        await db.set_guide_review("a", "rejected")
        await db.set_guide_review("b", "approved")
        return await db.guide_reviews()

    assert asyncio.run(run()) == {"a": "rejected", "b": "approved"}
