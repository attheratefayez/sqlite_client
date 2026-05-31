"""Tests for the chat agent module."""

from chat.agent import (
    DemoAgent,
    ChatAgent,
    RouterAgent,
    GeneralChatAgent,
    SqlAgent,
    RouterChatAgent,
    DEFAULT_CHAT_MODEL,
    DEFAULT_SQL_MODEL,
)


class TestChatAgent:
    def test_abstract_raises(self):
        agent = ChatAgent()
        try:
            agent.answer("hello")
            assert False, "Should have raised"
        except NotImplementedError:
            pass

    def test_abstract_subclass(self):
        class MyAgent(ChatAgent):
            def answer(self, message: str) -> str:
                return f"echo: {message}"

        a = MyAgent()
        assert a.answer("hi") == "echo: hi"

    def test_set_database_path_is_noop_by_default(self):
        agent = ChatAgent()
        agent.set_database_path("/some/path.db")
        agent.set_database_path(None)
        try:
            agent.answer("x")
            assert False
        except NotImplementedError:
            pass

    def test_get_history_default(self):
        agent = ChatAgent()
        assert agent.get_history() == []

    def test_close_store_default(self):
        agent = ChatAgent()
        agent.close_store()


class TestDemoAgent:
    def test_returns_placeholder(self):
        agent = DemoAgent()
        assert agent.answer("anything") == "not yet implemented"

    def test_any_message_returns_same(self):
        agent = DemoAgent()
        for msg in ["", "hello", "SELECT * FROM users"]:
            assert agent.answer(msg) == "not yet implemented"


class TestRouterAgent:
    def test_employee_is_sql(self):
        assert RouterAgent.classify("do we have an employee Nancy?") == "sql"

    def test_table_is_sql(self):
        assert RouterAgent.classify("check the employees table") == "sql"

    def test_hello_is_chat(self):
        assert RouterAgent.classify("hello") == "chat"

    def test_how_are_you_is_chat(self):
        assert RouterAgent.classify("how are you?") == "chat"

    def test_user_records_is_sql(self):
        assert RouterAgent.classify("how many users are there?") == "sql"

    def test_empty_message_is_chat(self):
        assert RouterAgent.classify("") == "chat"


class TestGeneralChatAgent:
    def test_default_model(self):
        agent = GeneralChatAgent()
        assert agent._model == DEFAULT_CHAT_MODEL

    def test_set_model_updates(self):
        agent = GeneralChatAgent()
        agent.set_model("mistralai/Mistral-7B-Instruct-v0.3")
        assert agent._model == "mistralai/Mistral-7B-Instruct-v0.3"

    def test_answer_no_llm(self):
        agent = GeneralChatAgent("nonexistent/model")
        result = agent.answer("hello")
        assert "error" in result.lower()


class TestSqlAgent:
    def test_default_model(self):
        agent = SqlAgent()
        assert agent._model == DEFAULT_SQL_MODEL

    def test_set_model_updates_model(self):
        agent = SqlAgent()
        agent.set_model("mistralai/Mistral-7B-Instruct-v0.3")
        assert agent._model == "mistralai/Mistral-7B-Instruct-v0.3"

    def test_no_database(self):
        agent = SqlAgent()
        result = agent.answer("hello")
        assert "No database" in result

    def test_set_database_path_clears(self, tmp_path):
        agent = SqlAgent(db_path="/tmp/test.db")
        agent.set_database_path(None)
        result = agent.answer("hello")
        assert "No database" in result

    def test_extract_sql_from_markdown(self):
        text = "Here is the query:\n```sql\nSELECT * FROM users;\n```\n"
        result = SqlAgent._extract_sql(text)
        assert result == "SELECT * FROM users;"

    def test_extract_sql_from_text(self):
        text = "Let me check.\n```sql\nSELECT COUNT(*) FROM orders;\n```\nDone."
        result = SqlAgent._extract_sql(text)
        assert result == "SELECT COUNT(*) FROM orders;"

    def test_extract_sql_none(self):
        text = "Hello, how can I help you?"
        result = SqlAgent._extract_sql(text)
        assert result is None


class TestRouterChatAgent:
    def test_default_models(self):
        agent = RouterChatAgent()
        assert agent.chat_agent._model == DEFAULT_CHAT_MODEL
        assert agent.sql_agent._model == DEFAULT_SQL_MODEL

    def test_set_models_updates_sub_agents(self):
        agent = RouterChatAgent()
        agent.set_models(
            chat_model="chat/m",
            sql_model="sql/m",
        )
        assert agent.chat_agent._model == "chat/m"
        assert agent.sql_agent._model == "sql/m"

    def test_partial_set_models(self):
        agent = RouterChatAgent()
        agent.set_models(chat_model="chat/m")
        assert agent.chat_agent._model == "chat/m"
        assert agent.sql_agent._model == DEFAULT_SQL_MODEL

    def test_persists_messages(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = RouterChatAgent(chat_store_path=str(store_path))
        agent.answer("hello")
        agent.answer("world")
        history = agent.get_history()
        assert len(history) == 4
        assert history[0] == ("user", "hello")
        assert history[1][0] == "assistant"
        assert history[2] == ("user", "world")
        assert history[3][0] == "assistant"

    def test_get_history_empty(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = RouterChatAgent(chat_store_path=str(store_path))
        assert agent.get_history() == []

    def test_get_history_after_answer(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = RouterChatAgent(chat_store_path=str(store_path))
        agent.answer("hi")
        history = agent.get_history()
        assert len(history) == 2
        assert history[0] == ("user", "hi")

    def test_close_store(self, tmp_path):
        import os
        store_path = tmp_path / "chat.db"
        agent = RouterChatAgent(chat_store_path=str(store_path))
        agent.close_store()
        assert os.path.exists(str(store_path))

    def test_set_database_path_propagates(self):
        agent = RouterChatAgent()
        assert agent.sql_agent._db_path is None
        agent.set_database_path("/some/db.sqlite")
        assert agent.sql_agent._db_path == "/some/db.sqlite"

    def test_set_database_path_switches_conversation(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = RouterChatAgent(chat_store_path=str(store_path))
        agent.answer("hello")
        first_msgs = agent.get_history()

        agent.set_database_path(str(tmp_path / "other.db"))
        second_msgs = agent.get_history()
        assert second_msgs == []

        agent.answer("world")
        assert len(agent.get_history()) == 2
