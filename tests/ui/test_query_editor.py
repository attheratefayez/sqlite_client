import pytest
from PyQt6.QtCore import Qt
from ui.query_editor import QueryEditorWidget, QueryTab


@pytest.fixture
def query_editor(qtbot):
    widget = QueryEditorWidget()
    qtbot.addWidget(widget)
    return widget


class TestQueryEditor:
    def test_initial_tab_exists(self, query_editor):
        assert query_editor._tabs.count() >= 1

    def test_add_tab_increases_count(self, query_editor):
        count = query_editor._tabs.count()
        query_editor.add_tab()
        assert query_editor._tabs.count() == count + 1

    def test_tab_counter_increments(self, query_editor):
        c1 = query_editor._tab_counter
        query_editor.add_tab()
        assert query_editor._tab_counter == c1 + 1

    def test_close_tab_with_multiple_tabs(self, query_editor):
        query_editor.add_tab()
        count = query_editor._tabs.count()
        query_editor._close_tab(0)
        assert query_editor._tabs.count() == count - 1

    def test_cannot_close_last_tab(self, query_editor):
        query_editor._close_tab(0)
        assert query_editor._tabs.count() >= 1

    def test_current_tab_returns_query_tab(self, query_editor):
        tab = query_editor.current_tab()
        assert isinstance(tab, QueryTab)

    def test_current_tab_has_editor(self, query_editor):
        tab = query_editor.current_tab()
        assert tab.editor is not None

    def test_execute_signal_from_editor(self, query_editor, qtbot):
        tab = query_editor.current_tab()
        signals = []
        tab.execute_requested.connect(signals.append)
        tab.editor.setPlainText("SELECT 1")
        tab._on_execute()
        assert signals == ["SELECT 1"]

    def test_ctrl_enter_triggers_execute(self, query_editor, qtbot):
        tab = query_editor.current_tab()
        signals = []
        tab.execute_requested.connect(signals.append)
        tab.editor.setPlainText("SELECT 2")
        qtbot.keyClick(tab.editor, Qt.Key.Key_Return, modifier=Qt.KeyboardModifier.ControlModifier)
        assert signals == ["SELECT 2"]
