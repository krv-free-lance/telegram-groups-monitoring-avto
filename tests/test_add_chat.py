import pytest
from telethon.errors import InviteRequestSentError, UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest, JoinChannelRequest
from telethon.tl.types import Channel

import app.userbot as userbot
from app.db import Database
from app.userbot import Monitor


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(userbot, "JOIN_CHECK_DELAY_SEC", 0)


@pytest.fixture
async def db(tmp_path):
    d = Database(tmp_path / "t.sqlite3")
    await d.connect()
    yield d
    await d.close()


def make_channel():
    return Channel(id=123, title="САМОСВАЛЫ СПб", photo=None, date=None, username="samosval_spb", megagroup=True)


class FakeClient:
    def __init__(self, member=True, join_error=None):
        self.member, self.join_error = member, join_error

    async def get_entity(self, ref):
        return make_channel()

    async def get_peer_id(self, entity):
        return -100123

    async def __call__(self, request):
        if isinstance(request, JoinChannelRequest) and self.join_error:
            raise self.join_error
        if isinstance(request, GetParticipantRequest) and not self.member:
            raise UserNotParticipantError(request)


async def test_add_ok(db):
    m = Monitor(FakeClient(), None, db, 1, "Europe/Moscow")
    assert await m.add_chat("@samosval_spb") == "САМОСВАЛЫ СПб"
    assert -100123 in m.chat_ids and await db.chat_ids() == {-100123}


async def test_add_kicked_by_captcha(db):
    m = Monitor(FakeClient(member=False), None, db, 1, "Europe/Moscow")
    with pytest.raises(ValueError, match="капч"):
        await m.add_chat("https://t.me/samosval_spb")
    assert await db.chat_ids() == set()


async def test_add_join_request(db):
    m = Monitor(FakeClient(join_error=InviteRequestSentError(None)), None, db, 1, "Europe/Moscow")
    with pytest.raises(ValueError, match="по заявке"):
        await m.add_chat("@samosval_spb")
    assert await db.chat_ids() == set()
