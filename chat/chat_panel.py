"""Collapsible chat panel for natural-language database queries."""

import re

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

    @staticmethod
    def _md_to_html(text: str) -> str:
        blocks: list[str] = []

        def _save(m: re.Match) -> str:
            blocks.append(m.group(0))
            return f"\x00{len(blocks) - 1}\x00"

        text = re.sub(r'```.*?```', _save, text, flags=re.DOTALL)
        text = re.sub(r'`[^`]+`', _save, text)
        text = re.sub(r'\*\*(.+?)\*\*', _save, text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', _save, text)

        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        def _restore(m: re.Match) -> str:
            raw = blocks[int(m.group(1))]
            raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            raw = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', raw)
            raw = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', raw)
            raw = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', raw, flags=re.DOTALL)
            raw = re.sub(r'`([^`]+)`', r'<code>\1</code>', raw)
            return raw

        text = re.sub(r'\x00(\d+)\x00', _restore, text)
        text = text.replace('\n', '<br>')
        return text

    def _append_message(self, sender: str, text: str) -> None:
        if sender == "You" and not self._history.document().isEmpty():
            self._history.append("<br>")
        html = self._md_to_html(text)
        self._history.append(f"<b>{sender}:</b> {html}")
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
