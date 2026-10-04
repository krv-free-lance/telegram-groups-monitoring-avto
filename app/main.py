import asyncio
import logging
from html import escape

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from telethon import TelegramClient

from app.bot import build_router
from app.config import Settings
from app.db import Database
from app.proxy import telethon_proxy_kwargs
from app.userbot import Monitor

log = logging.getLogger(__name__)

# Session is gone: a restart won't help, a human has to log in (python -m app.login).
# The systemd unit doesn't restart on this code (RestartPreventExitStatus).
AUTH_REQUIRED_EXIT = 2


async def tell_owner(bot: Bot, owner_id: int, text: str) -> None:
    """Best effort: a failed notification must not take the service down."""
    try:
        await bot.send_message(owner_id, text, parse_mode="HTML")
    except Exception:
        log.exception("Не удалось написать владельцу")


async def ensure_authorized(client: TelegramClient, bot: Bot, owner_id: int) -> bool:
    """Connect without prompting. client.start() would wait for a phone number on stdin —
    under a service with no terminal that is a silent hang, not an error."""
    await client.connect()
    if await client.is_user_authorized():
        return True
    log.error("Сессия аккаунта-читателя недействительна — нужен вход: python -m app.login")
    await tell_owner(
        bot,
        owner_id,
        "⚠️ Мониторинг остановлен: сессия аккаунта, который читает группы, недействительна "
        "(Telegram завершил её). Нужен вход на сервере: <code>python -m app.login</code>, "
        "затем перезапуск службы.",
    )
    return False


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
    if not await ensure_authorized(client, bot, settings.owner_id):
        await db.close()
        await bot.session.close()
        await client.disconnect()
        raise SystemExit(AUTH_REQUIRED_EXIT)

    monitor = Monitor(client, bot, db, settings.owner_id, settings.timezone)
    await monitor.start()
    # Every start is visible: a crash loop shows up as repeated messages, not as silence
    await tell_owner(
        bot,
        settings.owner_id,
        f"✅ Мониторинг запущен. Читает аккаунт: {escape(await monitor.account_name())}. "
        f"Групп: {len(monitor.chat_ids)}. Состояние в любой момент — /status",
    )

    dp = Dispatcher()
    dp.include_router(build_router(db, monitor, settings.owner_id))
    try:
        await asyncio.gather(dp.start_polling(bot), client.run_until_disconnected())
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
