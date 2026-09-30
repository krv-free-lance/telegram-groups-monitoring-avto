from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.classifier import Category
from app.db import DEDUP_WINDOW_SEC, Database
from app.notify import format_lead, message_link
from app.userbot import Monitor


@pytest.fixture
async def db(tmp_path):
    d = Database(tmp_path / "t.sqlite3")
    await d.connect()
    yield d
    await d.close()


def test_links():
    assert message_link(-1001234567890, 5, "spb_gruz") == "https://t.me/spb_gruz/5"
    assert message_link(-1001234567890, 5, None) == "https://t.me/c/1234567890/5"


def test_format_escapes_and_localizes():
    date = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
    s = format_lead(Category.SELL, "<b>щебень</b>", "Группа & Co", date, "https://t.me/x/1", "Europe/Moscow")
    assert "30.09.2026 12:00" in s
    assert "&lt;b&gt;щебень" in s and "Группа &amp; Co" in s


async def test_dedup(db):
    assert await db.add_lead(-1, 1, "sell", "Продам  щебень", "l", now=1000)
    assert await db.add_lead(-2, 7, "sell", "продам щебень", "l", now=2000) is None  # cross-post
    assert await db.add_lead(-1, 1, "sell", "other", "l", now=3000) is None  # same message
    assert await db.add_lead(-3, 1, "sell", "Продам щебень", "l", now=1000 + DEDUP_WINDOW_SEC + 1)


async def test_stats(db):
    a = await db.add_lead(-1, 1, "buy", "a", "l")
    await db.add_lead(-1, 2, "buy", "b", "l")
    await db.set_status(a, "yes")
    assert await db.stats() == [("buy", 2, 1, 0)]


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))


def fake_event(chat_id, msg_id, text):
    chat = SimpleNamespace(username="spb_gruz", title="Грузы СПб")

    async def get_chat():
        return chat

    return SimpleNamespace(
        chat_id=chat_id, id=msg_id, raw_text=text,
        date=datetime(2026, 9, 30, tzinfo=timezone.utc), get_chat=get_chat,
    )


async def test_monitor_flow(db):
    bot = FakeBot()
    m = Monitor(client=None, bot=bot, db=db, owner_id=42, tz="Europe/Moscow")
    m.chat_ids = {-100}
    await m.on_message(fake_event(-100, 1, "Нужен самосвал в Мурино"))
    await m.on_message(fake_event(-100, 2, "Всем привет"))           # not a lead
    await m.on_message(fake_event(-999, 3, "Нужен самосвал, Пушкин"))  # not monitored
    await m.on_message(fake_event(-100, 4, "нужен самосвал в мурино"))  # duplicate
    assert len(bot.sent) == 1
    owner, text, kw = bot.sent[0]
    assert owner == 42 and "https://t.me/spb_gruz/1" in text
    assert kw["reply_markup"].inline_keyboard[0][0].callback_data.startswith("lead:")

    m.paused = True
    await m.on_message(fake_event(-100, 5, "Куплю вторичный щебень"))
    assert len(bot.sent) == 1
