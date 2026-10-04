"""One-off message to the owner through this project's bot: python -m app.alert "text"

Used by the systemd unit tg-monitor-failed.service (OnFailure of tg-monitor) — the service itself
is down at that point, so it can't report its own crash loop.
"""
import asyncio
import sys

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import Settings


async def main(text: str) -> None:
    settings = Settings()
    session = AiohttpSession(proxy=settings.proxy_url) if settings.proxy_url else None
    bot = Bot(settings.bot_token, session=session)
    try:
        await bot.send_message(settings.owner_id, text)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "tg-monitor: сообщение без текста"))
