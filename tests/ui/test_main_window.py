import pytest
import tempfile
import pathlib
from PyQt6.QtCore import Qt
from core.database import DatabaseConnection
from ui.main_window import MainWindow
from ui.query_editor import QueryEditorWidget
from ui.schema_browser import SchemaBrowser


@pytest.fixture
def sample_db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = DatabaseConnection()
    conn.connect(tmp.name)
    conn.execute_script("""
        CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT);
        INSERT INTO test VALUES (1, 'hello');
    """)
    conn.commit()
    conn.close()
    yield tmp.name
    pathlib.Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    win.show()
    qtbot.addWidget(win)
    return win


class TestMainWindow:
    def test_initial_state(self, window):
        assert window.windowTitle() == "SQLite Client"
        assert window._close_action.isEnabled() is False
        assert "No database open" in window._status_label.text()

    def test_open_database(self, window, qtbot, sample_db_path):
        window._db.connect(sample_db_path)
        window._schema_browser.set_database(window._db)
        window._query_editor.set_database(window._db)
        window._close_action.setEnabled(True)
        window._status_label.setText(f"Connected: {window._db.path}")

        assert window._db.is_connected
        assert window._close_action.isEnabled()
        assert "Connected" in window._status_label.text()

    def test_close_database(self, window, qtbot, sample_db_path):
        window._db.connect(sample_db_path)
        window._schema_browser.set_database(window._db)
        window._close_action.setEnabled(True)

        window._on_close_database()
        assert not window._db.is_connected
        assert not window._close_action.isEnabled()
        assert "No database open" in window._status_label.text()

    def test_close_event_closes_db(self, window, qtbot, sample_db_path):
        window._db.connect(sample_db_path)
        assert window._db.is_connected
        window.close()
        assert not window._db.is_connected

    def test_query_editor_exists(self, window):
        assert isinstance(window._query_editor, QueryEditorWidget)

    def test_schema_browser_exists(self, window):
        assert isinstance(window._schema_browser, SchemaBrowser)
