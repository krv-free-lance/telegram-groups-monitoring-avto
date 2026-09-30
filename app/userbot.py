import asyncio
import logging
import re

from aiogram import Bot
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetParticipantRequest, JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import InviteRequestSentError, UserAlreadyParticipantError, UserNotParticipantError
from telethon.tl.types import Channel
from telethon.utils import get_display_name

from app.classifier import classify
from app.db import Database
from app.notify import format_lead, lead_keyboard, message_link

log = logging.getLogger(__name__)

# Anti-spam bots in groups often kick newcomers who don't pass a captcha within seconds
JOIN_CHECK_DELAY_SEC = 5

INVITE_RE = re.compile(r"(?:t\.me/(?:\+|joinchat/))([\w-]+)")
PUBLIC_RE = re.compile(r"(?:t\.me/|@)([A-Za-z]\w{3,})")


class Monitor:
    """Listens to monitored chats via a user account and forwards leads to the bot."""

    def __init__(self, client: TelegramClient, bot: Bot, db: Database, owner_id: int, tz: str):
        self.client = client
        self.bot = bot
        self.db = db
        self.owner_id = owner_id
        self.tz = tz
        self.chat_ids: set[int] = set()
        self.paused = False

    async def start(self) -> None:
        self.chat_ids = await self.db.chat_ids()
        self.client.add_event_handler(self.on_message, events.NewMessage())
        log.info("Monitoring %d chats", len(self.chat_ids))

    async def on_message(self, event: events.NewMessage.Event) -> None:
        if self.paused or event.chat_id not in self.chat_ids:
            return
        text = event.raw_text or ""
        match = classify(text)
        if not match:
            return
        chat = await event.get_chat()
        link = message_link(event.chat_id, event.id, getattr(chat, "username", None))
        lead_id = await self.db.add_lead(event.chat_id, event.id, match.category.value, text, link)
        if lead_id is None:
            return  # duplicate
        log.info("Lead %s [%s] %s", lead_id, match.category.value, match.reason)
        await self.bot.send_message(
            self.owner_id,
            format_lead(match.category, text, get_display_name(chat), event.date, link, self.tz),
            reply_markup=lead_keyboard(lead_id),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    async def add_chat(self, ref: str) -> str:
        """Join a chat by @username / t.me link / invite link and start monitoring it."""
        ref = ref.strip()
        try:
            if m := INVITE_RE.search(ref):
                try:
                    updates = await self.client(ImportChatInviteRequest(m.group(1)))
                    entity = updates.chats[0]
                except UserAlreadyParticipantError:
                    entity = await self.client.get_entity(ref)
            elif m := PUBLIC_RE.search(ref):
                entity = await self.client.get_entity(m.group(1))
                await self.client(JoinChannelRequest(entity))
            else:
                raise ValueError("Не понял ссылку. Пример: @spb_samosval или https://t.me/+AbCd…")
        except InviteRequestSentError:
            raise ValueError(
                "Группа принимает участников по заявке. Заявка отправлена — "
                "после одобрения админом повторите /add."
            )
        await asyncio.sleep(JOIN_CHECK_DELAY_SEC)
        if not await self.is_member(entity):
            raise ValueError(
                "Аккаунт вступил, но его сразу удалили из группы — скорее всего, там антиспам-бот "
                "с капчей. Зайдите в группу с этого аккаунта вручную, пройдите проверку и повторите /add."
            )
        chat_id = await self.client.get_peer_id(entity)
        title = get_display_name(entity)
        await self.db.add_chat(chat_id, title, getattr(entity, "username", None))
        self.chat_ids.add(chat_id)
        return title

    async def is_member(self, entity) -> bool:
        if not isinstance(entity, Channel):
            return True  # basic groups: joining via invite is enough
        try:
            await self.client(GetParticipantRequest(entity, "me"))
            return True
        except UserNotParticipantError:
            return False

    async def account_name(self) -> str:
        me = await self.client.get_me()
        name = get_display_name(me)
        return f"{name} (@{me.username})" if me.username else f"{name} (+{me.phone})"

    async def remove_chat(self, chat_id: int) -> bool:
        self.chat_ids.discard(chat_id)
        return await self.db.remove_chat(chat_id)
