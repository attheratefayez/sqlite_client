"""SQLite-backed persistence for chat conversations."""

from __future__ import annotations

import sqlite3
import pathlib


class ChatStore:
    """Persists conversations and messages in a local SQLite database.

    The database file defaults to ``chat/chat_history.db``.
    """

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(pathlib.Path(__file__).parent / "chat_history.db")
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'Chat',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
        """)
        self._conn.commit()

    def create_conversation(self, title: str = "Chat") -> int:
        cur = self._conn.execute(
            "INSERT INTO conversations (title) VALUES (?)", (title,)
        )
        self._conn.commit()
        return cur.lastrowid

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        self._conn.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_messages(self, conversation_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in rows]

    def get_conversations(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, title, created_at, updated_at "
            "FROM conversations ORDER BY id DESC"
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]}
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
