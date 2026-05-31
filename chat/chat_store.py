"""SQLite-backed persistence for chat conversations."""

from __future__ import annotations

import sqlite3
import pathlib


class ChatStore:
    """Persists conversations and messages in a local SQLite database.

    Each conversation can be linked to a specific database via *db_path*.
    Opening the same database again resumes the same conversation.
    A ``db_path`` of ``""`` (empty string) represents the general (no-DB) chat.

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
                db_path TEXT NOT NULL DEFAULT '',
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
        self._migrate()

    def _migrate(self) -> None:
        cursor = self._conn.execute("PRAGMA table_info(conversations)")
        cols = {row[1] for row in cursor.fetchall()}
        if "db_path" not in cols:
            self._conn.execute(
                "ALTER TABLE conversations ADD COLUMN db_path TEXT NOT NULL DEFAULT ''"
            )
            self._conn.commit()
        self._ensure_general_conversation()

    def _ensure_general_conversation(self) -> None:
        cur = self._conn.execute("SELECT id FROM conversations WHERE db_path = ''")
        if not cur.fetchone():
            self._conn.execute(
                "INSERT INTO conversations (title, db_path) VALUES ('General Chat', '')"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Conversation lifecycle
    # ------------------------------------------------------------------

    def get_or_create_conversation(self, db_path: str = "") -> int:
        """Return the conversation ID for *db_path*, creating one if needed.

        The path is resolved to an absolute path so that ``./foo.db`` and
        ``/abs/foo.db`` map to the same conversation.  An empty string
        represents the general (no-database) chat.
        """
        if db_path:
            db_path = str(pathlib.Path(db_path).resolve())
        cur = self._conn.execute(
            "SELECT id FROM conversations WHERE db_path = ?", (db_path,)
        )
        row = cur.fetchone()
        if row:
            return row[0]
        title = "General Chat" if not db_path else f"Chat - {pathlib.Path(db_path).name}"
        cur = self._conn.execute(
            "INSERT INTO conversations (title, db_path) VALUES (?, ?)",
            (title, db_path),
        )
        self._conn.commit()
        return cur.lastrowid

    def create_conversation(self, title: str = "Chat") -> int:
        """Create a new unlinked conversation and return its ID."""
        cur = self._conn.execute(
            "INSERT INTO conversations (title) VALUES (?)", (title,)
        )
        self._conn.commit()
        return cur.lastrowid

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

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

    def clear_conversation(self, conversation_id: int) -> None:
        """Delete all messages in a conversation."""
        self._conn.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
