import hashlib
import time
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id  INTEGER PRIMARY KEY,
    title    TEXT NOT NULL,
    username TEXT
);
CREATE TABLE IF NOT EXISTS leads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    msg_id     INTEGER NOT NULL,
    text_hash  TEXT NOT NULL,
    category   TEXT NOT NULL,
    text       TEXT NOT NULL,
    link       TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    status     TEXT,
    UNIQUE (chat_id, msg_id)
);
CREATE INDEX IF NOT EXISTS leads_hash ON leads (text_hash, created_at);
"""

# The same ad is often cross-posted to several groups; don't notify twice within this window.
DEDUP_WINDOW_SEC = 24 * 3600


def text_hash(text: str) -> str:
    norm = " ".join(text.lower().split())
    return hashlib.sha1(norm.encode()).hexdigest()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    # --- chats ---
    async def add_chat(self, chat_id: int, title: str, username: str | None) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO chats (chat_id, title, username) VALUES (?, ?, ?)",
            (chat_id, title, username),
        )
        await self.conn.commit()

    async def remove_chat(self, chat_id: int) -> bool:
        cur = await self.conn.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
        await self.conn.commit()
        return cur.rowcount > 0

    async def list_chats(self) -> list[tuple[int, str, str | None]]:
        async with self.conn.execute("SELECT chat_id, title, username FROM chats ORDER BY title") as cur:
            return list(await cur.fetchall())

    async def chat_ids(self) -> set[int]:
        return {row[0] for row in await self.list_chats()}

    # --- leads ---
    async def add_lead(
        self, chat_id: int, msg_id: int, category: str, text: str, link: str, now: int | None = None
    ) -> int | None:
        """Save a lead. Returns its id, or None if it's a duplicate."""
        now = now or int(time.time())
        h = text_hash(text)
        async with self.conn.execute(
            "SELECT 1 FROM leads WHERE text_hash = ? AND created_at > ?", (h, now - DEDUP_WINDOW_SEC)
        ) as cur:
            if await cur.fetchone():
                return None
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO leads (chat_id, msg_id, text_hash, category, text, link, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chat_id, msg_id, h, category, text, link, now),
        )
        await self.conn.commit()
        return cur.lastrowid if cur.rowcount else None

    async def set_status(self, lead_id: int, status: str) -> None:
        await self.conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
        await self.conn.commit()

    async def stats(self) -> list[tuple[str, int, int, int]]:
        """Per category: total, interesting, not interesting."""
        async with self.conn.execute(
            "SELECT category, COUNT(*),"
            " SUM(status = 'yes'), SUM(status = 'no')"
            " FROM leads GROUP BY category ORDER BY category"
        ) as cur:
            return [(c, t, y or 0, n or 0) for c, t, y, n in await cur.fetchall()]
