import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from telethon import TelegramClient

from app.bot import build_router
from app.config import Settings
from app.db import Database
from app.proxy import telethon_proxy_kwargs
from app.userbot import Monitor


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    db = Database(settings.db_path)
    await db.connect()

    # Bot API goes over HTTPS; MTProxy is not supported there, only socks/http proxy_url
    session = AiohttpSession(proxy=settings.proxy_url) if settings.proxy_url else None
    bot = Bot(settings.bot_token, session=session)
    client = TelegramClient(
        str(settings.session_path),
        settings.api_id,
        settings.api_hash,
        **telethon_proxy_kwargs(settings.proxy_url, settings.mtproxy),
    )
    # First run asks for phone and login code in the console, then the session is saved.
    await client.start()

    monitor = Monitor(client, bot, db, settings.owner_id, settings.timezone)
    await monitor.start()

    dp = Dispatcher()
    dp.include_router(build_router(db, monitor, settings.owner_id))
    try:
        await asyncio.gather(dp.start_polling(bot), client.run_until_disconnected())
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
