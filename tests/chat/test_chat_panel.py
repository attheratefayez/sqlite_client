"""Tests for the ChatPanel widget."""

from PyQt6.QtCore import Qt
from chat.chat_panel import ChatPanel


class TestChatPanel:
    def test_initial_state(self, qtbot):
        panel = ChatPanel()
        qtbot.addWidget(panel)
        assert panel._input.toPlainText() == ""
        assert panel._history.toPlainText() == ""

    def test_append_reply_shows_in_history(self, qtbot):
        panel = ChatPanel()
        qtbot.addWidget(panel)
        panel.append_reply("hello", "world")
        assert "world" in panel._history.toPlainText()

    def test_send_emits_signal(self, qtbot):
        panel = ChatPanel()
        qtbot.addWidget(panel)
        with qtbot.waitSignal(panel.message_sent, timeout=1000) as blocker:
            panel._input.setPlainText("test message")
            panel._on_send()
        assert blocker.args == ["test message"]

    def test_enter_key_triggers_send(self, qtbot):
        panel = ChatPanel()
        qtbot.addWidget(panel)
        panel._input.setPlainText("enter msg")
        with qtbot.waitSignal(panel.message_sent, timeout=1000) as blocker:
            from PyQt6.QtTest import QTest
            QTest.keyClick(panel._input, Qt.Key.Key_Return)
        assert blocker.args == ["enter msg"]
