"""Chat agent classes for natural-language database interaction."""

from __future__ import annotations

import json
import re

from chat.chat_store import ChatStore
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "HuggingFaceH4/zephyr-7b-beta"

MODEL_NOT_SUPPORTED_HINT = (
    "The model '{model}' is not available on the HuggingFace Inference API. "
    "Try one of these:\n"
    "  - HuggingFaceH4/zephyr-7b-beta\n"
    "  - microsoft/Phi-3-mini-4k-instruct\n"
    "  - mistralai/Mistral-7B-Instruct-v0.3\n"
    "  - google/gemma-2-2b-it\n\n"
    "You can change the model via View > Chat Model..."
)

SYSTEM_PROMPT = """\
You are a helpful assistant that can chat naturally AND use database tools when needed.

AVAILABLE TOOLS:

get_schema — Returns the full database schema (tables, columns, types).
  No arguments needed. Use this when you need to understand the database structure.

run_sql — Executes a SQL query and returns the results.
  Args: { "query": "your SQL here" }
  Use this to answer questions about the data in the database.

HOW TO USE TOOLS:
When the user asks a question that requires database information:
1. First call get_schema if you don't know the schema
2. Then call run_sql with an appropriate SQL query
3. Use the results to answer naturally

To call a tool, include this in your response:
ACTION: tool_name
ACTION_INPUT: {"arg": "value"}

The tool result will be shown to you. Then continue the conversation.
If you don't need any tools, just respond normally.

RULES:
- Be conversational and friendly.
- If the question is about the database, use the tools.
- If the question is general (hello, how are you, tell me a joke, etc.),
  just answer naturally without tools.
- Keep responses clear and concise.
- Use the tool results to provide accurate, data-driven answers."""

MAX_REACT_STEPS = 6


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


class LangChainAgent(ChatAgent):
    """Conversational chat agent with database tool access.

    Uses a ReAct loop to decide when to query the database via tools
    (``get_schema``, ``run_sql``) and when to answer naturally.
    Conversations are persisted in ``chat/chat_history.db``.
    """

    def __init__(
        self,
        db_path: str | None = None,
        model: str = DEFAULT_MODEL,
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

    def set_model(self, model: str) -> None:
        self._model = model
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
            msg = str(exc)
            if "not supported" in msg.lower() or "model_not_supported" in msg:
                hint = MODEL_NOT_SUPPORTED_HINT.format(model=self._model)
                self._setup_error = f"Failed to initialise: {msg}\n\n{hint}"
            else:
                self._setup_error = (
                    f"Failed to initialise: {msg}\n\nMake sure you have "
                    "internet access. For higher rate limits, set the "
                    "HUGGINGFACEHUB_API_TOKEN environment variable."
                )

    def get_history(self) -> list[tuple[str, str]]:
        msgs = self._store.get_messages(self._conversation_id)
        return [(m["role"], m["content"]) for m in msgs]

    def close_store(self) -> None:
        self._store.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer(self, message: str) -> str:
        self._store.add_message(self._conversation_id, "user", message)

        if self._llm is None or self._sql_db is None:
            reply = self._build_no_llm_reply()
            self._store.add_message(self._conversation_id, "assistant", reply)
            return reply

        try:
            reply = self._run_react_loop(message)
        except Exception as exc:
            reply = f"**Error:** {exc}"

        self._store.add_message(self._conversation_id, "assistant", reply)
        return reply

    # ------------------------------------------------------------------
    # ReAct loop
    # ------------------------------------------------------------------

    def _run_react_loop(self, message: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        # Include recent conversation history (up to 6 most recent messages)
        history = self._store.get_messages(self._conversation_id)
        for h in history[-6:]:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                messages.append(AIMessage(content=h["content"]))

        for step in range(MAX_REACT_STEPS):
            response = self._llm.invoke(messages)
            reply = response.content.strip()

            action = self._parse_action(reply)
            if action is None:
                return reply

            messages.append(AIMessage(content=reply))
            tool_name = action["name"]
            tool_args = action.get("args", {})

            try:
                result = self._run_tool(tool_name, tool_args)
            except Exception as exc:
                result = f"Error executing {tool_name}: {exc}"

            messages.append(
                HumanMessage(content=f"Tool result ({tool_name}):\n{result}")
            )

        return "I'm sorry, I couldn't complete that request in the allowed number of steps."

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    TOOL_SCHEMA = {
        "get_schema": {
            "description": "Get the database schema",
            "handler": "_tool_get_schema",
        },
        "run_sql": {
            "description": "Execute a SQL query",
            "handler": "_tool_run_sql",
        },
    }

    def _run_tool(self, name: str, args: dict) -> str:
        tool = self.TOOL_SCHEMA.get(name)
        if tool is None:
            return f"Unknown tool: {name}. Available: {', '.join(self.TOOL_SCHEMA)}"
        handler = getattr(self, tool["handler"])
        return handler(args)

    def _tool_get_schema(self, args: dict) -> str:
        if self._sql_db is None:
            return "No database is open."
        return self._sql_db.table_info

    def _tool_run_sql(self, args: dict) -> str:
        if self._sql_db is None:
            return "No database is open."
        sql = args.get("query", "")
        if not sql:
            return "No SQL query provided."
        return self._sql_db.run(sql)

    # ------------------------------------------------------------------
    # Action parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_action(text: str) -> dict | None:
        m = re.search(
            r"ACTION:\s*(\w+)(?:\s*\nACTION_INPUT:\s*(\{.*\}|[^\n]*))?",
            text,
            re.DOTALL,
        )
        if m:
            name = m.group(1)
            args_raw = m.group(2)
            if args_raw:
                try:
                    args = json.loads(args_raw)
                except json.JSONDecodeError:
                    args = {"query": args_raw.strip()}
            else:
                args = {}
            return {"name": name, "args": args}
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_no_llm_reply(self) -> str:
        if self._db_path is None:
            return "No database is currently open. Open a database first."
        return "Cannot connect to the LLM.\n" + (
            self._setup_error or "Unknown setup error."
        )
