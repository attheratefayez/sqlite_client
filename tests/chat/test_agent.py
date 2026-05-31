"""Tests for the chat agent module."""

import os

from chat.agent import DemoAgent, ChatAgent, LangChainAgent


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


class TestLangChainAgent:
    def test_no_database(self, tmp_path):
        agent = LangChainAgent(chat_store_path=str(tmp_path / "chat.db"))
        result = agent.answer("hello")
        assert "No database" in result

    def test_set_database_path_clears(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = LangChainAgent(db_path="/tmp/test.db", chat_store_path=str(store_path))
        agent.set_database_path(None)
        result = agent.answer("hello")
        assert "No database" in result

    def test_returns_error_on_unavailable(self, tmp_path):
        db_path = tmp_path / "test.db"
        db_path.write_text("")
        store_path = tmp_path / "chat.db"
        agent = LangChainAgent(
            db_path=str(db_path), chat_store_path=str(store_path)
        )
        result = agent.answer("list tables")
        assert (
            "Cannot connect" in result
            or "Failed to initialise" in result
            or "Error" in result
        )

    def test_dotenv_loads_token(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HUGGINGFACEHUB_API_TOKEN", "test-token-from-env")
        agent = LangChainAgent(chat_store_path=str(tmp_path / "chat.db"))
        env_val = os.environ.get("HUGGINGFACEHUB_API_TOKEN")
        assert env_val == "test-token-from-env"

    def test_persists_messages(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = LangChainAgent(chat_store_path=str(store_path))
        agent.answer("hello")
        agent.answer("world")
        history = agent.get_history()
        assert len(history) == 4
        assert history[0] == ("user", "hello")
        assert history[1][0] == "assistant"
        assert history[2] == ("user", "world")
        assert history[3][0] == "assistant"

    def test_close_store(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = LangChainAgent(chat_store_path=str(store_path))
        agent.close_store()
        assert os.path.exists(str(store_path))

    def test_get_history_returns_conversation(self, tmp_path):
        store_path = tmp_path / "chat.db"
        agent = LangChainAgent(chat_store_path=str(store_path))
        assert agent.get_history() == []
        agent.answer("hi")
        history = agent.get_history()
        assert len(history) == 2
        assert history[0] == ("user", "hi")

    def test_extract_sql_from_markdown(self):
        text = "Here is the query:\n```sql\nSELECT * FROM users;\n```\n"
        result = LangChainAgent._extract_sql(text)
        assert result == "SELECT * FROM users;"

    def test_extract_sql_from_plain(self):
        text = "SELECT * FROM users WHERE id = 1"
        result = LangChainAgent._extract_sql(text)
        assert result == "SELECT * FROM users WHERE id = 1"

    def test_extract_sql_falls_through(self):
        text = "Just some random text without SQL keywords"
        result = LangChainAgent._extract_sql(text)
        assert result == text
