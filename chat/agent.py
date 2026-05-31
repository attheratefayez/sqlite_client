"""Chat agent classes for natural-language database interaction."""

from __future__ import annotations

import re

from chat.chat_store import ChatStore
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CHAT_MODEL = "HuggingFaceH4/zephyr-7b-beta"
DEFAULT_SQL_MODEL = "HuggingFaceH4/zephyr-7b-beta"
DEFAULT_ROUTER_MODEL = "microsoft/Phi-3-mini-4k-instruct"

MODEL_NOT_SUPPORTED_HINT = (
    "The model '{model}' is not available on the HuggingFace Inference API. "
    "Try one of these:\n"
    "  - HuggingFaceH4/zephyr-7b-beta\n"
    "  - microsoft/Phi-3-mini-4k-instruct\n"
    "  - mistralai/Mistral-7B-Instruct-v0.3\n"
    "  - google/gemma-2-2b-it"
)

CHAT_SYSTEM_PROMPT = """\
You are a helpful assistant. Be conversational and friendly.
Keep responses clear and concise.
Do NOT use emojis or any emoticons. Plain text only."""

SQL_SYSTEM_PROMPT = """\
You are a helpful assistant with access to a SQLite database.

To answer questions about the data:
1. Write a SQLite query that answers the question
2. Wrap it in a ```sql code block
3. I will run the query and show you the results
4. Then you will answer the user in plain language

Rules:
- Be conversational and friendly.
- Do NOT use emojis or any emoticons. Plain text only."""

SQL_SCHEMA_HINT = "\n\nHere is the database schema for reference:\n{schema}"

ANSWER_PROMPT = """\
I ran your SQL query and got these results:

{results}

Now answer the user's original question in plain language, based on these results."""

ROUTER_SYSTEM_PROMPT = """\
Classify the user's message as "chat" or "sql".

"sql" = asking about database data, tables, records, counts, or
        anything that requires a SQL query to answer.
"chat" = greetings, how-are-you, jokes, opinions, general conversation.

Reply with exactly one word: "chat" or "sql"."""


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_llm(model: str):
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

    endpoint = HuggingFaceEndpoint(
        model=model,
        max_new_tokens=1024,
        temperature=0.1,
        timeout=120,
    )
    return ChatHuggingFace(llm=endpoint)


# ------------------------------------------------------------------
# Base class
# ------------------------------------------------------------------

class ChatAgent:
    """Abstract base for a chat agent that answers user questions."""

    def answer(self, message: str) -> str:
        raise NotImplementedError

    def set_database_path(self, path: str | None) -> None:
        pass

    def set_model(self, model: str) -> None:
        pass

    def get_history(self) -> list[tuple[str, str]]:
        return []

    def close_store(self) -> None:
        pass


class DemoAgent(ChatAgent):
    """Placeholder agent that always replies ``"not yet implemented"``."""

    def answer(self, message: str) -> str:
        return "not yet implemented"


# ------------------------------------------------------------------
# Router agent
# ------------------------------------------------------------------

class RouterAgent:
    """Classifies a user message as ``"chat"`` or ``"sql"``.

    Uses a keyword fast-path first.  If the message contains table/field
    names or DB-related terms it returns ``"sql"`` immediately.  Only
    ambiguous messages are sent to the LLM classifier.
    """

    _SQL_KEYWORDS = frozenset({
        "table", "tables", "database", "databases",
        "employee", "employees", "customer", "customers",
        "order", "orders", "product", "products",
        "user", "users", "record", "records",
        "row", "rows", "column", "columns",
        "schema", "data", "query", "queries",
        "select", "insert", "update", "delete",
        "count", "sum", "avg", "total",
    })

    def __init__(self, model: str = DEFAULT_ROUTER_MODEL):
        self._model = model
        self._llm: object | None = None
        self._error: str | None = None
        self._setup()

    def _setup(self) -> None:
        self._llm = None
        self._error = None
        try:
            self._llm = _make_llm(self._model)
        except Exception as exc:
            self._error = f"Router init failed: {exc}"

    def set_model(self, model: str) -> None:
        self._model = model
        self._setup()

    def classify(self, message: str) -> str:
        msg_lower = message.lower()

        if any(kw in msg_lower for kw in self._SQL_KEYWORDS):
            return "sql"

        if self._llm is None:
            return "chat"
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            response = self._llm.invoke([
                SystemMessage(content=ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=message),
            ])
            result = response.content.strip().lower()
            return "sql" if "sql" in result else "chat"
        except Exception:
            return "chat"


# ------------------------------------------------------------------
# General chat agent (no database awareness)
# ------------------------------------------------------------------

class GeneralChatAgent(ChatAgent):
    """Plain conversational agent.  No database context."""

    def __init__(self, model: str = DEFAULT_CHAT_MODEL):
        self._model = model
        self._llm: object | None = None
        self._error: str | None = None
        self._setup()

    def set_model(self, model: str) -> None:
        self._model = model
        self._setup()

    def _setup(self) -> None:
        self._llm = None
        self._error = None
        try:
            self._llm = _make_llm(self._model)
        except Exception as exc:
            self._error = f"Chat agent init failed: {exc}"

    def answer(self, message: str) -> str:
        if self._llm is None:
            return "Chat agent is not available.\n" + (self._error or "")
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            response = self._llm.invoke([
                SystemMessage(content=CHAT_SYSTEM_PROMPT),
                HumanMessage(content=message),
            ])
            return response.content.strip()
        except Exception as exc:
            return f"Chat agent error: {exc}"


# ------------------------------------------------------------------
# SQL agent (two-stage DB question answerer)
# ------------------------------------------------------------------

class SqlAgent(ChatAgent):
    """Answers database questions via a two-stage SQL pipeline.

    Stage 1 — Ask the LLM to write a SQL query (optionally wrapped in
    a `````sql```` block).
    Stage 2 — Execute the SQL, then re-prompt the LLM to answer in
    plain language based on the results.

    Does **not** persist messages — the caller (``RouterChatAgent``) is
    responsible for that.
    """

    def __init__(
        self,
        db_path: str | None = None,
        model: str = DEFAULT_SQL_MODEL,
    ):
        self._db_path = db_path
        self._model = model
        self._llm: object | None = None
        self._sql_db = None
        self._error: str | None = None
        self._setup()

    def set_database_path(self, path: str | None) -> None:
        self._db_path = path
        self._setup()

    def set_model(self, model: str) -> None:
        self._model = model
        self._setup()

    def _setup(self) -> None:
        self._llm = None
        self._sql_db = None
        self._error = None

        if self._db_path is None:
            return

        try:
            from langchain_community.utilities import SQLDatabase

            self._sql_db = SQLDatabase.from_uri(f"sqlite:///{self._db_path}")
            self._llm = _make_llm(self._model)
        except Exception as exc:
            msg = str(exc)
            if "not supported" in msg.lower() or "model_not_supported" in msg:
                hint = MODEL_NOT_SUPPORTED_HINT.format(model=self._model)
                self._error = f"Failed to initialise: {msg}\n\n{hint}"
            else:
                self._error = (
                    f"Failed to initialise: {msg}\n\nMake sure you have "
                    "internet access. For higher rate limits, set the "
                    "HUGGINGFACEHUB_API_TOKEN environment variable."
                )

    def answer(self, message: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        if self._llm is None or self._sql_db is None:
            return self._build_no_db_reply()

        prompt = SQL_SYSTEM_PROMPT
        if self._sql_db is not None:
            prompt += SQL_SCHEMA_HINT.format(schema=self._sql_db.table_info)

        stage1_msgs = [SystemMessage(content=prompt), HumanMessage(content=message)]

        try:
            response = self._llm.invoke(stage1_msgs)
            reply = response.content.strip()
        except Exception as exc:
            return f"Error: {exc}"

        sql = self._extract_sql(reply)
        if not sql:
            return reply

        try:
            results = self._sql_db.run(sql)
        except Exception as exc:
            results = f"Error running query: {exc}"

        stage2_msgs = stage1_msgs.copy()
        stage2_msgs.append(AIMessage(content=reply))
        stage2_msgs.append(
            HumanMessage(content=ANSWER_PROMPT.format(results=results))
        )

        try:
            response = self._llm.invoke(stage2_msgs)
            return response.content.strip()
        except Exception as exc:
            return f"Error: {exc}"

    @staticmethod
    def _extract_sql(text: str) -> str | None:
        m = re.search(r"```sql\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def _build_no_db_reply(self) -> str:
        if self._db_path is None:
            return "No database is currently open. Open a database first."
        return "SQL agent is not available.\n" + (self._error or "Unknown error.")


# ------------------------------------------------------------------
# Router-based top-level agent
# ------------------------------------------------------------------

class RouterChatAgent(ChatAgent):
    """Top-level agent that routes messages to the appropriate sub-agent.

    Owns the conversation store and persistence.  Delegates
    conversation to ``GeneralChatAgent`` and database questions to
    ``SqlAgent`` after classification by ``RouterAgent``.
    """

    def __init__(
        self,
        chat_model: str = DEFAULT_CHAT_MODEL,
        sql_model: str = DEFAULT_SQL_MODEL,
        router_model: str = DEFAULT_ROUTER_MODEL,
        db_path: str | None = None,
        chat_store_path: str | None = None,
    ):
        self._db_path = db_path
        self._store = ChatStore(chat_store_path)
        self._conversation_id = self._store.create_conversation()

        self._router = RouterAgent(router_model)
        self._chat_agent = GeneralChatAgent(chat_model)
        self._sql_agent = SqlAgent(db_path, sql_model)

    # -- sub-agent accessors (for worker to forward model changes) ----------

    @property
    def router(self) -> RouterAgent:
        return self._router

    @property
    def chat_agent(self) -> GeneralChatAgent:
        return self._chat_agent

    @property
    def sql_agent(self) -> SqlAgent:
        return self._sql_agent

    # -- ChatAgent interface -----------------------------------------------

    def answer(self, message: str) -> str:
        self._store.add_message(self._conversation_id, "user", message)

        category = self._router.classify(message)

        try:
            if category == "sql":
                reply = self._sql_agent.answer(message)
            else:
                reply = self._chat_agent.answer(message)
        except Exception as exc:
            reply = f"Error: {exc}"

        self._store.add_message(self._conversation_id, "assistant", reply)
        return reply

    def set_database_path(self, path: str | None) -> None:
        self._db_path = path
        self._sql_agent.set_database_path(path)

    def get_history(self) -> list[tuple[str, str]]:
        msgs = self._store.get_messages(self._conversation_id)
        return [(m["role"], m["content"]) for m in msgs]

    def close_store(self) -> None:
        self._store.close()

    def set_models(
        self,
        chat_model: str | None = None,
        sql_model: str | None = None,
        router_model: str | None = None,
    ) -> None:
        if chat_model is not None:
            self._chat_agent.set_model(chat_model)
        if sql_model is not None:
            self._sql_agent.set_model(sql_model)
        if router_model is not None:
            self._router.set_model(router_model)
