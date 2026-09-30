from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.classifier import CATEGORY_TITLES, Category

MAX_TEXT = 3000  # Telegram message limit is 4096; leave room for the header


def message_link(chat_id: int, msg_id: int, username: str | None) -> str:
    if username:
        return f"https://t.me/{username}/{msg_id}"
    # Private supergroups/channels: -100XXXXXXXXXX -> XXXXXXXXXX
    internal = str(abs(chat_id))
    if internal.startswith("100"):
        internal = internal[3:]
    return f"https://t.me/c/{internal}/{msg_id}"


def format_lead(
    category: Category, text: str, chat_title: str, date: datetime, link: str, tz: str
) -> str:
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + "…"
    local = date.astimezone(ZoneInfo(tz))
    return (
        f"<b>{CATEGORY_TITLES[category]}</b>\n"
        f"📍 {escape(chat_title)}\n"
        f"🕒 {local:%d.%m.%Y %H:%M}\n\n"
        f"{escape(text)}\n\n"
        f'<a href="{link}">Открыть сообщение</a>'
    )


def lead_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="👍 Интересно", callback_data=f"lead:{lead_id}:yes"),
            InlineKeyboardButton(text="👎 Не интересно", callback_data=f"lead:{lead_id}:no"),
        ]]
    )
