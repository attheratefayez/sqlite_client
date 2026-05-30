import pytest
import tempfile
import pathlib
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt
from core.database import DatabaseConnection
from ui.schema_browser import SchemaBrowser


@pytest.fixture
def sample_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = DatabaseConnection()
    conn.connect(tmp.name)
    conn.execute_script("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        );
        CREATE VIEW active_users AS SELECT * FROM users;
        CREATE INDEX idx_name ON users(name);
    """)
    conn.commit()
    yield conn
    conn.close()
    pathlib.Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def browser(qtbot):
    widget = SchemaBrowser()
    qtbot.addWidget(widget)
    return widget


class TestSchemaBrowser:
    def test_empty_when_no_db(self, browser):
        assert browser.topLevelItemCount() == 0

    def test_populates_tables_and_views(self, browser, sample_db, qtbot):
        browser.set_database(sample_db)
        assert browser.topLevelItemCount() == 2

        tables_root = browser.topLevelItem(0)
        assert tables_root.text(0) == "Tables"
        assert tables_root.childCount() >= 1

        table_names = []
        for i in range(tables_root.childCount()):
            table_names.append(tables_root.child(i).text(0))
        assert "users" in table_names

        views_root = browser.topLevelItem(1)
        assert views_root.text(0) == "Views"
        assert views_root.childCount() >= 1

    def test_table_columns_are_children(self, browser, sample_db, qtbot):
        browser.set_database(sample_db)
        tables_root = browser.topLevelItem(0)
        users_item = None
        for i in range(tables_root.childCount()):
            if tables_root.child(i).text(0) == "users":
                users_item = tables_root.child(i)
                break
        assert users_item is not None
        assert users_item.childCount() > 0
        col_texts = []
        for j in range(users_item.childCount()):
            col_texts.append(users_item.child(j).text(0))
        assert any("id" in t and "INTEGER" in t for t in col_texts)
        assert any("name" in t and "TEXT" in t for t in col_texts)
        assert any("email" in t and "TEXT" in t for t in col_texts)

    def test_table_selected_signal(self, browser, sample_db, qtbot):
        browser.set_database(sample_db)
        signals = []
        browser.table_selected.connect(signals.append)
        tables_root = browser.topLevelItem(0)
        users_item = tables_root.child(0)
        browser._on_item_clicked(users_item, 0)
        assert signals == ["users"]

    def test_view_selected_signal(self, browser, sample_db, qtbot):
        browser.set_database(sample_db)
        signals = []
        browser.view_selected.connect(signals.append)
        views_root = browser.topLevelItem(1)
        view_item = views_root.child(0)
        browser._on_item_clicked(view_item, 0)
        assert signals == ["active_users"]

    def test_clear_on_set_database_none(self, browser, sample_db, qtbot):
        browser.set_database(sample_db)
        assert browser.topLevelItemCount() == 2
        browser.set_database(None)
        assert browser.topLevelItemCount() == 0
