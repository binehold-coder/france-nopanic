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
