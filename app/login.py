"""Interactive login of the account that reads the groups: python -m app.login

Asks for the phone number, the code from Telegram and the 2FA password if set; the session is saved
to data/userbot.session. The service itself never prompts (see main.ensure_authorized).
"""
import asyncio

from telethon import TelegramClient
from telethon.utils import get_display_name

from app.config import Settings
from app.proxy import telethon_proxy_kwargs


async def main() -> None:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(
        str(settings.session_path),
        settings.api_id,
        settings.api_hash,
        **telethon_proxy_kwargs(settings.proxy_url, settings.mtproxy),
    )
    await client.start()
    me = await client.get_me()
    print(f"Вход выполнен: {get_display_name(me)}" + (f" (@{me.username})" if me.username else ""))
    print("Сессия сохранена. Теперь запустите службу.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
