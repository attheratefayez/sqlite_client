"""Chat agent classes for natural-language database interaction.

Provides :class:`ChatAgent`, :class:`DemoAgent`, and
:class:`LangChainAgent` backed by HuggingFace + LangChain.
"""

from __future__ import annotations

import re

from chat.chat_store import ChatStore
from dotenv import load_dotenv

load_dotenv()


SQL_PROMPT = """\
You are a SQLite expert. Given the following database schema, write a SQLite query to answer the user's question.
Schema:
{schema}
Question: {question}
Answer with ONLY the SQLite query, no explanation:"""


class ChatAgent:
    """Abstract base for a chat agent that answers user questions."""

    def answer(self, message: str) -> str:
        raise NotImplementedError

    def set_database_path(self, path: str | None) -> None:
        pass

    def get_history(self) -> list[tuple[str, str]]:
        return []

    def close_store(self) -> None:
        pass


class DemoAgent(ChatAgent):
    """Placeholder agent that always replies ``"not yet implemented"``."""

    def answer(self, message: str) -> str:
        return "not yet implemented"


class LangChainAgent(ChatAgent):
    """Chat agent backed by HuggingFace + LangChain SQL toolkit.

    Generates SQL via :class:`~langchain_huggingface.HuggingFaceEndpoint`,
    executes it against the user's database, and persists every
    conversation in a local ``chat/chat_history.db`` file.
    """

    def __init__(
        self,
        db_path: str | None = None,
        model: str = "Qwen/Qwen3.5-4B",
        chat_store_path: str | None = None,
    ):
        self._db_path = db_path
        self._model = model
        self._llm = None
        self._sql_db = None
        self._setup_error: str | None = None
        self._store = ChatStore(chat_store_path)
        self._conversation_id = self._store.create_conversation()
        self._setup_if_possible()

    def set_database_path(self, path: str | None) -> None:
        self._db_path = path
        self._setup_if_possible()

    def _setup_if_possible(self) -> None:
        self._llm = None
        self._sql_db = None
        self._setup_error = None

        if self._db_path is None:
            return

        try:
            from langchain_community.utilities import SQLDatabase
            from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

            self._sql_db = SQLDatabase.from_uri(f"sqlite:///{self._db_path}")
            endpoint = HuggingFaceEndpoint(
                model=self._model,
                max_new_tokens=1024,
                temperature=0.1,
                timeout=120,
            )
            self._llm = ChatHuggingFace(llm=endpoint)
        except Exception as exc:
            self._setup_error = (
                f"Failed to initialise: {exc}\n\nMake sure you have "
                "internet access. For higher rate limits, set the "
                "HUGGINGFACEHUB_API_TOKEN environment variable."
            )

    def get_history(self) -> list[tuple[str, str]]:
        msgs = self._store.get_messages(self._conversation_id)
        return [(m["role"], m["content"]) for m in msgs]

    def close_store(self) -> None:
        self._store.close()

    def answer(self, message: str) -> str:
        self._store.add_message(self._conversation_id, "user", message)

        if self._llm is None or self._sql_db is None:
            reply = self._build_no_llm_reply()
            self._store.add_message(self._conversation_id, "assistant", reply)
            return reply

        try:
            schema = self._sql_db.table_info
            prompt = SQL_PROMPT.format(schema=schema, question=message)
            from langchain_core.messages import HumanMessage
            response = self._llm.invoke([HumanMessage(content=prompt)])
            raw = response.content
            sql = self._extract_sql(raw)

            result = self._sql_db.run(sql)
            reply = f"**Query:** `{sql}`\n\n```\n{result}\n```"
        except Exception as exc:
            reply = f"**Error:** {exc}"

        self._store.add_message(self._conversation_id, "assistant", reply)
        return reply

    @staticmethod
    def _extract_sql(text: str) -> str:
        match = re.search(r"```(?:sql)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        lines = text.strip().splitlines()
        sql_lines = []
        for line in lines:
            stripped = line.strip()
            if re.match(
                r"^(SELECT|WITH|INSERT|UPDATE|DELETE|PRAGMA|CREATE|ALTER|DROP)\b",
                stripped,
                re.IGNORECASE,
            ):
                sql_lines.append(stripped)
        if sql_lines:
            return " ".join(sql_lines)
        return text.strip()

    def _build_no_llm_reply(self) -> str:
        if self._db_path is None:
            return "No database is currently open. Open a database first."
        return "Cannot connect to the LLM.\n" + (
            self._setup_error or "Unknown setup error."
        )
