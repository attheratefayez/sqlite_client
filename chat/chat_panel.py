"""Collapsible chat panel for natural-language database queries."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor


class ChatPanel(QWidget):
    """A widget that displays a chat conversation and a message input area.

    Signals:
        message_sent: Emitted with the user's text when Send or Enter is pressed.
    """

    message_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._history = QTextEdit()
        self._history.setReadOnly(True)
        self._history.setPlaceholderText("Chat history…")
        layout.addWidget(self._history)

        input_layout = QHBoxLayout()
        self._input = QTextEdit()
        self._input.setPlaceholderText("Ask about your database…")
        self._input.setMaximumHeight(60)
        self._input.setAcceptRichText(False)
        self._input.installEventFilter(self)
        input_layout.addWidget(self._input)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self._send_btn)

        layout.addLayout(input_layout)

    def load_history(self, messages: list[tuple[str, str]]) -> None:
        self._history.clear()
        for role, content in messages:
            self._append_message(role.capitalize(), content)

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self._append_message("You", text)
        self.message_sent.emit(text)

    def append_reply(self, user_message: str, reply: str) -> None:
        self._append_message("Agent", reply)

    def _append_message(self, sender: str, text: str) -> None:
        self._history.append(f"<b>{sender}:</b> {text}")
        cursor = self._history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._history.setTextCursor(cursor)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            ke = event if isinstance(event, QKeyEvent) else None
            if ke and ke.key() == Qt.Key.Key_Return and ke.modifiers() == Qt.KeyboardModifier.NoModifier:
                self._on_send()
                return True
        return super().eventFilter(obj, event)
