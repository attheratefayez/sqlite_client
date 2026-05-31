"""Chat agent classes for natural-language database interaction."""

from __future__ import annotations

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
You are a helpful assistant with access to a SQLite database.

To answer questions about the data:
1. Write a SQLite query that answers the question
2. Wrap it in a ```sql code block
3. I will run the query and show you the results
4. Then you will answer the user in plain language

If the question is general (hello, how are you, etc.), just answer naturally.

Rules:
- Be conversational and friendly.
- Do NOT use emojis or any emoticons. Plain text only."""

SCHEMA_HINT = (
    "\n\nHere is the database schema for reference:\n{schema}"
)

ANSWER_PROMPT = """\
I ran your SQL query and got these results:

{results}

Now answer the user's original question in plain language, based on these results."""


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

    Uses a two-stage approach:
    1. Ask the LLM to answer naturally, optionally writing SQL in a
       `````sql```` code block.
    2. If SQL is present, execute it and re-prompt the LLM to produce
       the final answer based on the query results.

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
            reply = self._answer_question(message)
        except Exception as exc:
            reply = f"Error: {exc}"

        self._store.add_message(self._conversation_id, "assistant", reply)
        return reply

    # ------------------------------------------------------------------
    # Two-stage question answering
    # ------------------------------------------------------------------

    def _answer_question(self, message: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        # --- Stage 1: get the model's response (with optional SQL) ---
        stage1_msgs = [SystemMessage(content=self._build_system_prompt())]

        history = self._store.get_messages(self._conversation_id)
        for h in history[-6:]:
            if h["role"] == "user":
                stage1_msgs.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                stage1_msgs.append(AIMessage(content=h["content"]))

        response = self._llm.invoke(stage1_msgs)
        reply = response.content.strip()

        # --- Stage 2: execute any SQL and re-prompt if needed ---
        sql = self._extract_sql(reply)
        if sql:
            try:
                results = self._sql_db.run(sql)
            except Exception as exc:
                results = f"Error running query: {exc}"

            stage2_msgs = stage1_msgs.copy()
            stage2_msgs.append(AIMessage(content=reply))
            stage2_msgs.append(
                HumanMessage(content=ANSWER_PROMPT.format(results=results))
            )

            response = self._llm.invoke(stage2_msgs)
            reply = response.content.strip()

        return reply

    # ------------------------------------------------------------------
    # SQL extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_sql(text: str) -> str | None:
        m = re.search(r"```sql\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        prompt = SYSTEM_PROMPT
        if self._sql_db is not None:
            prompt += SCHEMA_HINT.format(schema=self._sql_db.table_info)
        return prompt

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_no_llm_reply(self) -> str:
        if self._db_path is None:
            return "No database is currently open. Open a database first."
        return "Cannot connect to the LLM.\n" + (
            self._setup_error or "Unknown setup error."
        )
