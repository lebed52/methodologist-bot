from __future__ import annotations

from pathlib import Path

import aiosqlite


class ConversationStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await database.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, id)"
            )
            await database.commit()

    async def add(self, chat_id: int, role: str, content: str) -> None:
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                "INSERT INTO messages(chat_id, role, content) VALUES (?, ?, ?)",
                (chat_id, role, content),
            )
            await database.commit()

    async def history(self, chat_id: int, limit: int) -> list[dict[str, str]]:
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                """
                SELECT role, content
                FROM messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            )
            rows = await cursor.fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    async def clear(self, chat_id: int) -> None:
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            await database.commit()
