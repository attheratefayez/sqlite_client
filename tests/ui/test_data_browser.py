import pytest
import tempfile
import pathlib
import time
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import QApplication
from core.database import DatabaseConnection, ColumnInfo
from core.worker import DatabaseWorker
from ui.data_browser import DataBrowser, DataTableModel


def _wait_for_model(widget, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if widget._model.rowCount() > 0:
            return
        time.sleep(0.005)
    raise TimeoutError("Timed out waiting for model data")


@pytest.fixture
def sample_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = DatabaseConnection()
    conn.connect(tmp.name)
    conn.execute_script("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER DEFAULT 0
        );
        INSERT INTO users (name, age) VALUES ('Alice', 30);
        INSERT INTO users (name, age) VALUES ('Bob', 25);
        INSERT INTO users (name, age) VALUES ('Charlie', 35);
    """)
    conn.commit()
    yield conn
    conn.close()
    pathlib.Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def browser(qtbot, sample_db):
    columns = sample_db.table_schema("users")
    total_count = sample_db.table_row_count("users")
    worker = DatabaseWorker()
    worker._db.connect(sample_db.path)
    thread = QThread()
    worker.moveToThread(thread)
    thread.start()
    widget = DataBrowser(worker, "users", columns, total_count)
    qtbot.addWidget(widget)
    _wait_for_model(widget)
    yield widget
    thread.quit()
    thread.wait(3000)
    worker.close_database()


class TestDataTableModel:
    def test_row_count(self):
        columns = []
        rows = [(1, "a"), (2, "b")]
        model = DataTableModel(columns, rows)
        assert model.rowCount() == 2

    def test_column_count_with_checkbox(self):
        columns = [ColumnInfo(0, "id", "INT", False, None, True)]
        model = DataTableModel(columns, [])
        assert model.columnCount() == 2

    def test_checkbox_column(self):
        columns = [ColumnInfo(0, "id", "INT", False, None, True)]
        model = DataTableModel(columns, [(1,)])
        idx = model.index(0, 0)
        assert model.data(idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked

    def test_checkbox_toggle(self):
        columns = [ColumnInfo(0, "id", "INT", False, None, True)]
        model = DataTableModel(columns, [(1,)])
        idx = model.index(0, 0)
        model.setData(idx, Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole)
        assert 0 in model.checked_rows

    def test_select_all(self):
        columns = [ColumnInfo(0, "id", "INT", False, None, True)]
        model = DataTableModel(columns, [(1,), (2,)])
        model.select_all(True)
        assert model.checked_rows == {0, 1}
        model.select_all(False)
        assert model.checked_rows == set()

    def test_data_display(self):
        columns = [ColumnInfo(0, "id", "INT", False, None, True)]
        model = DataTableModel(columns, [(42,)])
        idx = model.index(0, 1)
        assert model.data(idx) == "42"

    def test_data_null_display(self):
        columns = [ColumnInfo(0, "val", "TEXT", False, None, False)]
        model = DataTableModel(columns, [(None,)])
        idx = model.index(0, 1)
        assert model.data(idx) == "NULL"

    def test_header(self):
        col_info = ColumnInfo(0, "my_col", "TEXT", False, None, False)
        model = DataTableModel([col_info], [])
        assert model.headerData(1, Qt.Orientation.Horizontal) == "my_col"
        assert model.headerData(0, Qt.Orientation.Horizontal) == ""


class TestDataBrowser:
    def test_initial_load(self, browser):
        assert browser._model is not None
        assert browser._model.rowCount() == 3

    def test_title_contains_table_name(self, browser):
        assert browser._table_name == "users"

    def _wait_for_pending_cleared(self, browser, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            QApplication.processEvents()
            if len(browser._pending_edits) == 0 and not browser._commit_btn.isEnabled():
                return
            time.sleep(0.005)

    def _wait_for_row_count(self, browser, expected, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            QApplication.processEvents()
            if browser._model.rowCount() == expected:
                return
            time.sleep(0.005)
        raise TimeoutError(
            f"Expected row count {expected}, got {browser._model.rowCount()}"
        )

    def test_next_page(self, browser, qtbot):
        browser._page_size = 2
        browser._page = 0
        browser._request_page()
        self._wait_for_row_count(browser, 2)
        assert browser._model.rowCount() == 2
        browser._next_page()
        self._wait_for_row_count(browser, 1)
        assert browser._model.rowCount() == 1

    def test_prev_page(self, browser, qtbot):
        browser._page_size = 2
        browser._page = 1
        browser._request_page()
        self._wait_for_row_count(browser, 1)
        assert browser._model.rowCount() == 1
        browser._page = 0
        browser._request_page()
        self._wait_for_row_count(browser, 2)
        assert browser._model.rowCount() == 2

    def test_page_size_change(self, browser, qtbot):
        browser._page_size = 2
        browser._page = 0
        browser._request_page()
        self._wait_for_row_count(browser, 2)
        assert browser._page_size == 2
        assert browser._model.rowCount() == 2

    def test_select_all_checkbox(self, browser, qtbot):
        browser._select_all_cb.setChecked(True)
        assert browser._model.checked_rows == {0, 1, 2}
        browser._select_all_cb.setChecked(False)
        assert browser._model.checked_rows == set()

    def test_delete_selected_none(self, browser):
        assert len(browser._model.checked_rows) == 0

    def test_delete_selected_with_rows(self, browser, qtbot):
        browser._model.select_all(True)
        assert len(browser._model.checked_rows) == 3

    def test_edit_stores_pending_not_committed(self, browser, qtbot):
        browser.record_edit(0, 0)
        assert len(browser._pending_edits) == 1
        assert browser._commit_btn.isEnabled()

    def test_commit_persists_changes(self, browser, qtbot, sample_db):
        browser._model.setData(browser._model.index(0, 2), "AliceEdited", Qt.ItemDataRole.EditRole)
        assert len(browser._pending_edits) == 1
        browser._commit_changes()
        self._wait_for_pending_cleared(browser)
        assert len(browser._pending_edits) == 0
        assert not browser._commit_btn.isEnabled()

        current = sample_db.execute("SELECT name FROM users WHERE id=1")[0][0]
        assert current == "AliceEdited"

    def test_pending_cleared_on_page_load(self, browser, qtbot):
        browser.record_edit(0, 0)
        assert len(browser._pending_edits) == 1
        browser._request_page()
        self._wait_for_pending_cleared(browser)
        assert len(browser._pending_edits) == 0
        assert not browser._commit_btn.isEnabled()

    def test_same_cell_replaces_pending(self, browser, qtbot):
        browser._model.setData(browser._model.index(0, 2), "First", Qt.ItemDataRole.EditRole)
        assert len(browser._pending_edits) == 1
        assert list(browser._pending_edits.values())[0] == "First"

        browser._model.setData(browser._model.index(0, 2), "Second", Qt.ItemDataRole.EditRole)
        assert len(browser._pending_edits) == 1
        assert list(browser._pending_edits.values())[0] == "Second"

    def test_commit_empty_is_noop(self, browser, qtbot):
        assert len(browser._pending_edits) == 0
        browser._commit_changes()
        assert len(browser._pending_edits) == 0

    def test_discard_pending_edits(self, browser, qtbot):
        browser.record_edit(0, 0)
        assert len(browser._pending_edits) == 1
        browser._discard_pending_edits()
        assert len(browser._pending_edits) == 0
        assert not browser._commit_btn.isEnabled()

    def test_edit_without_pk_does_not_store(self, browser, qtbot, sample_db):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        conn = DatabaseConnection()
        conn.connect(tmp.name)
        conn.execute_script("""
            CREATE TABLE notes (content TEXT);
            INSERT INTO notes VALUES ('hello');
        """)
        conn.commit()
        columns = conn.table_schema("notes")
        total_count = conn.table_row_count("notes")
        worker = DatabaseWorker()
        worker._db.connect(conn.path)
        thread = QThread()
        worker.moveToThread(thread)
        thread.start()
        b = DataBrowser(worker, "notes", columns, total_count)
        qtbot.addWidget(b)
        _wait_for_model(b)
        b.record_edit(0, 0)
        assert len(b._pending_edits) == 0
        thread.quit()
        thread.wait(3000)
        worker.close_database()
        conn.close()
        pathlib.Path(tmp.name).unlink(missing_ok=True)


class TestDatabaseWorkerAddRow:
    """Tests for DatabaseWorker request_add_row and _default_for_col."""

    @pytest.fixture
    def worker(self):
        w = DatabaseWorker()
        yield w

    def test_default_for_col_notnull_text(self, worker):
        c = ColumnInfo(0, "name", "TEXT", True, None, False)
        assert worker._default_for_col(c) == ""

    def test_default_for_col_notnull_int(self, worker):
        c = ColumnInfo(0, "age", "INTEGER", True, None, False)
        assert worker._default_for_col(c) == 0

    def test_default_for_col_notnull_real(self, worker):
        c = ColumnInfo(0, "score", "REAL", True, None, False)
        assert worker._default_for_col(c) == 0.0

    def test_default_for_col_notnull_bool(self, worker):
        c = ColumnInfo(0, "active", "BOOLEAN", True, None, False)
        assert worker._default_for_col(c) == 0

    def test_default_for_col_notnull_blob(self, worker):
        c = ColumnInfo(0, "data", "BLOB", True, None, False)
        assert worker._default_for_col(c) == b""

    def test_default_for_col_nullable(self, worker):
        c = ColumnInfo(0, "nickname", "TEXT", False, None, False)
        assert worker._default_for_col(c) is None

    def test_default_for_col_with_default(self, worker):
        c = ColumnInfo(0, "created", "DATETIME", False, "CURRENT_TIMESTAMP", False)
        assert worker._default_for_col(c) is None

    def test_default_for_col_notnull_with_default(self, worker):
        c = ColumnInfo(0, "role", "TEXT", True, "'user'", False)
        assert worker._default_for_col(c) is None

    def test_default_for_col_varchar_with_parens(self, worker):
        c = ColumnInfo(0, "email", "VARCHAR(100)", True, None, False)
        assert worker._default_for_col(c) == ""

    def test_request_add_row_with_defaults(self, worker, tmp_path):
        db_path = str(tmp_path / "test.db")
        worker._db.connect(db_path)
        worker._db.execute_script("""
            CREATE TABLE t (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER DEFAULT 0
            );
        """)
        worker._db.commit()

        from core.database import ColumnInfo
        cols = [
            ColumnInfo(0, "id", "INTEGER", False, None, True),
            ColumnInfo(1, "name", "TEXT", True, None, False),
            ColumnInfo(2, "age", "INTEGER", False, "0", False),
        ]
        worker.request_add_row("t", cols)
        rows = worker._db.execute("SELECT * FROM t")
        assert len(rows) == 1
        assert rows[0][1] == ""  # name defaulted to ''
        assert rows[0][2] == 0   # age defaulted by SQLite

    def test_request_add_row_double_insert(self, worker, tmp_path):
        db_path = str(tmp_path / "test.db")
        worker._db.connect(db_path)
        worker._db.execute_script("""
            CREATE TABLE t (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL
            );
        """)
        worker._db.commit()

        from core.database import ColumnInfo
        cols = [
            ColumnInfo(0, "id", "INTEGER", False, None, True),
            ColumnInfo(1, "label", "TEXT", True, None, False),
        ]
        worker.request_add_row("t", cols)
        worker.request_add_row("t", cols)
        rows = worker._db.execute("SELECT * FROM t")
        assert len(rows) == 2
