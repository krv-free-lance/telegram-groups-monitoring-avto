import time
from types import SimpleNamespace

import pytest

from app.db import Database
from app.main import ensure_authorized
from app.userbot import Monitor


@pytest.fixture
async def db(tmp_path):
    d = Database(tmp_path / "t.sqlite3")
    await d.connect()
    yield d
    await d.close()


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


class FakeClient:
    def __init__(self, authorized=True):
        self.authorized = authorized
        self.connected = False

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return self.authorized

    async def get_me(self):
        return SimpleNamespace(first_name="Иван", last_name=None, username="reader", phone="79990000000")


async def test_lead_counts_split_day(db):
    now = int(time.time())
    await db.add_lead(-1, 1, "truck", "нужен самосвал", "l1", now=now - 2 * 86400)
    await db.add_lead(-1, 2, "truck", "нужны машины", "l2", now=now - 60)
    assert await db.lead_counts(now) == (2, 1)


async def test_status_text_reports_state(db):
    m = Monitor(FakeClient(), FakeBot(), db, owner_id=1, tz="Europe/Moscow")
    m.started_at = 1_000_000.0
    text = await m.status_text(now=1_000_000.0 + 3700)
    assert "🟢 Работает" in text
    assert "@reader" in text
    assert "Групп в мониторинге: 0 — добавьте" in text
    assert "с момента запуска не было" in text
    assert "1 ч 1 мин назад" in text
    m.paused, m.last_event_at, m.chat_ids = True, 1_000_000.0 + 3600, {-100}
    text = await m.status_text(now=1_000_000.0 + 3700)
    assert "На паузе" in text and "1 мин назад" in text and "Групп в мониторинге: 1" in text


async def test_dead_session_tells_owner_instead_of_prompting():
    bot = FakeBot()
    assert not await ensure_authorized(FakeClient(authorized=False), bot, owner_id=42)
    assert bot.sent and bot.sent[0][0] == 42 and "app.login" in bot.sent[0][1]


async def test_live_session_is_silent():
    bot = FakeBot()
    assert await ensure_authorized(FakeClient(authorized=True), bot, owner_id=42)
    assert bot.sent == []
