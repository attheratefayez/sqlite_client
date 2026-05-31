"""Tests for the ChatWorker."""

from PyQt6.QtCore import QThread
from chat.worker import ChatWorker
from chat.agent import DemoAgent, RouterChatAgent


class TestChatWorker:
    def test_send_message_emits_response(self, qtbot):
        agent = DemoAgent()
        worker = ChatWorker(agent)
        thread = QThread()
        worker.moveToThread(thread)
        thread.start()

        with qtbot.waitSignal(worker.response_received, timeout=5000) as blocker:
            worker.send_message("hello")

        assert blocker.args == ["hello", "not yet implemented"]
        thread.quit()
        thread.wait(3000)

    def test_set_models_propagates(self, qtbot):
        agent = RouterChatAgent()
        worker = ChatWorker(agent)
        thread = QThread()
        worker.moveToThread(thread)
        thread.start()

        worker.set_models(chat_model="c", sql_model="s", router_model="r")
        thread.quit()
        thread.wait(3000)
        assert agent.chat_agent._model == "c"
        assert agent.sql_agent._model == "s"
        assert agent.router._model == "r"

    def test_load_history_emits_signal(self, qtbot):
        agent = DemoAgent()
        worker = ChatWorker(agent)
        thread = QThread()
        worker.moveToThread(thread)
        thread.start()

        with qtbot.waitSignal(worker.history_loaded, timeout=5000) as blocker:
            worker.load_history()

        assert blocker.args[0] == []
        thread.quit()
        thread.wait(3000)

    def test_set_database_path(self, qtbot):
        class TrackingAgent:
            def __init__(self):
                self.path = None
            def answer(self, msg):
                return ""
            def set_database_path(self, path):
                self.path = path
            def get_history(self):
                return []
            def close_store(self):
                pass

        agent = TrackingAgent()
        worker = ChatWorker(agent)
        thread = QThread()
        worker.moveToThread(thread)
        thread.start()

        worker.set_database_path("/some/db.sqlite")
        thread.quit()
        thread.wait(3000)
        assert agent.path == "/some/db.sqlite"
