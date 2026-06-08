import pytest
import tempfile
import pathlib
from PyQt6.QtCore import QSettings
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
    settings = QSettings("sqlite-client", "sqlite-client")
    saved = {k: settings.value(k) for k in settings.allKeys()}
    settings.clear()
    win = MainWindow()
    win.show()
    qtbot.addWidget(win)
    yield win
    for k, v in saved.items():
        settings.setValue(k, v)


class TestMainWindow:
    def test_initial_state(self, window):
        assert window.windowTitle() == "SQLite Client"
        assert window._close_action.isEnabled() is False
        assert "No database open" in window._status_label.text()

    def test_open_database(self, window, qtbot, sample_db_path):
        window._connect_database(sample_db_path)
        assert window._active_path == sample_db_path
        assert window._active_db is not None
        assert window._active_db.is_connected
        assert window._close_action.isEnabled()
        assert "Connected" in window._status_label.text()

    def test_close_database(self, window, qtbot, sample_db_path):
        window._connect_database(sample_db_path)
        assert window._active_db is not None
        window._on_close_database()
        assert window._active_db is None
        assert not window._close_action.isEnabled()
        assert "No database open" in window._status_label.text()

    def test_close_event_closes_db(self, window, qtbot, sample_db_path):
        window._connect_database(sample_db_path)
        assert window._active_db is not None
        assert window._active_db.is_connected
        path = window._active_path
        window.close()
        assert not window._databases.get(path) or not window._databases[path].is_connected

    def test_query_editor_exists(self, window):
        assert isinstance(window._query_editor, QueryEditorWidget)

    def test_schema_browser_exists(self, window, sample_db_path):
        window._connect_database(sample_db_path)
        assert len(window._schema_browsers) == 1
        browser = list(window._schema_browsers.values())[0]
        assert isinstance(browser, SchemaBrowser)

    def test_right_tabs_has_query_tab(self, window):
        assert window._right_tabs.count() >= 1

    def test_open_data_browser_adds_tab(self, window, sample_db_path, qtbot):
        window._connect_database(sample_db_path)
        window._worker.open_database(sample_db_path)
        count = window._right_tabs.count()
        window._open_data_browser(sample_db_path, "test")
        assert window._right_tabs.count() == count + 1

    def test_open_data_browser_reuses_tab(self, window, sample_db_path, qtbot):
        window._connect_database(sample_db_path)
        window._worker.open_database(sample_db_path)
        window._open_data_browser(sample_db_path, "test")
        count = window._right_tabs.count()
        window._open_data_browser(sample_db_path, "test")
        assert window._right_tabs.count() == count

    def test_right_tab_close_query_tab_blocked(self, window):
        idx = window._right_tabs.indexOf(window._query_editor)
        window._on_right_tab_close(idx)
        assert window._right_tabs.indexOf(window._query_editor) >= 0

    def test_dark_mode_toggle(self, window):
        assert window._dark_mode_action.isCheckable()
        initial = window._dark_mode_action.isChecked()
        window._dark_mode_action.setChecked(not initial)
        window._on_toggle_theme()
        assert window._dark_mode_action.isChecked() is (not initial)
        window._dark_mode_action.setChecked(initial)
        window._on_toggle_theme()
        assert window._dark_mode_action.isChecked() is initial

    def test_dark_mode_menu_item_exists(self, window):
        assert window._dark_mode_action is not None
        assert "Dark" in window._dark_mode_action.text()

    def test_multiple_databases(self, window, qtbot, sample_db_path, tmp_path):
        db2_path = str(tmp_path / "multi_test.db")
        conn = DatabaseConnection()
        conn.connect(db2_path)
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()
        window._connect_database(sample_db_path)
        window._connect_database(db2_path)
        assert len(window._databases) == 2
        assert len(window._schema_browsers) == 2
        assert window._schema_tabs.count() == 2
        assert window._active_path == db2_path
        window._on_close_database()
        assert len(window._databases) == 1
        assert len(window._schema_browsers) == 1
        assert window._schema_tabs.count() == 1
        assert window._active_path == sample_db_path
