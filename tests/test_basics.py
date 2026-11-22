from datetime import date

from nopanic.bot import parse_user_date
from nopanic.db import Database
from nopanic.llm import parse_deadline
from nopanic.texts import T, split_message, t


def test_split_message_respects_limit():
    text = ("рядок тексту " * 50 + "\n\n") * 20
    parts = split_message(text, 500)
    assert all(len(p) <= 500 for p in parts)
    assert "".join(parts).replace(" ", "").replace("\n", "") == text.replace(" ", "").replace("\n", "")


def test_texts_have_both_languages_and_format():
    for key, table in T.items():
        assert set(table) == {"uk", "ru", "fr"}, key
    assert "3" in t("free_n", "ru", n=3)
    assert t("left", "xx", n=1).startswith("Залишилось")


def test_dates():
    assert parse_user_date("15.12.2026") == date(2026, 12, 15)
    assert parse_user_date("5/1/27") == date(2027, 1, 5)
    assert parse_user_date("31.02.2026") is None
    assert parse_user_date("завтра") is None
    assert parse_deadline("2026-12-15") == date(2026, 12, 15)
    assert parse_deadline(None) is None
    assert parse_deadline("скоро") is None


async def test_db_flow(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    await db.init()
    await db.set_lang(1, "ru")
    assert await db.get_lang(1) == "ru"
    lid = await db.add_letter(1, "CAF", "Bonjour", "Пояснення", "2026-12-15", "envoyer", 100, 50)
    assert await db.letters_used(1) == 1
    assert (await db.last_letter(1)).id == lid
    assert await db.get_letter(lid, 2) is None  # other users can't read it
    days = await db.add_reminders(1, lid, date(2026, 12, 15), "envoyer", [3, 1, 0], date(2026, 12, 13))
    assert days == [date(2026, 12, 14), date(2026, 12, 15)]  # 12.12 already past
    due = await db.due_reminders(date(2026, 12, 14))
    assert len(due) == 1
    await db.mark_sent(due[0][0])
    assert await db.due_reminders(date(2026, 12, 14)) == []
    await db.log_usage(1, "letter", "m", 100, 50)
    s = await db.stats(3)
    assert s["letters"] == 1 and s["input_tokens"] == 100
