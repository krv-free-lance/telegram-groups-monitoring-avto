from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    api_id: int
    api_hash: str
    bot_token: str
    owner_id: int
    timezone: str = "Europe/Moscow"
    data_dir: Path = Path("data")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bot.sqlite3"

    @property
    def session_path(self) -> Path:
        return self.data_dir / "userbot"
