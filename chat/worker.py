"""Background worker for non-blocking chat agent execution."""

from PyQt6.QtCore import QObject, pyqtSignal

from chat.agent import ChatAgent


class ChatWorker(QObject):
    """Processes chat messages on a background thread.

    Signals:
        response_received: Emitted with ``(user_message, bot_reply)``.
        history_loaded: Emitted with a ``list[(role, content)]``.
    """

    response_received = pyqtSignal(str, str)
    history_loaded = pyqtSignal(list)

    def __init__(self, agent: ChatAgent, parent=None):
        super().__init__(parent)
        self._agent = agent

    def send_message(self, message: str) -> None:
        reply = self._agent.answer(message)
        self.response_received.emit(message, reply)

    def set_agent(self, agent: ChatAgent) -> None:
        self._agent = agent

    def set_database_path(self, path: str) -> None:
        self._agent.set_database_path(path if path else None)

    def load_history(self) -> None:
        self.history_loaded.emit(self._agent.get_history())

    def close_store(self) -> None:
        self._agent.close_store()
