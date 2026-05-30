"""Main application window for the SQLite Client.

Provides the top-level :class:`MainWindow` with menu bar, schema browser,
query editor, status bar, and data browser tab management.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QApplication,
    QMenuBar, QStatusBar, QMessageBox, QWidget, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction

from core.database import DatabaseConnection
from ui.schema_browser import SchemaBrowser
from ui.query_editor import QueryEditorWidget
from ui.connection_dialog import ConnectionDialog
from ui.data_browser import DataBrowser
from resources.style import THEMES


RECENT_FILES_MAX = 10


class MainWindow(QMainWindow):
    """Main application window coordinating all UI components.

    Manages database connections, the schema tree, query tabs, and
    data browser tabs. Persists a list of recently opened files using
    QSettings.
    """

    def __init__(self):
        """Initialize the main window, menus, UI layout, and status bar."""
        super().__init__()
        self._db = DatabaseConnection()
        self.setWindowTitle("SQLite Client")
        self.resize(1200, 800)

        self._settings = QSettings("sqlite-client", "sqlite-client")
        self._setup_menu()
        self._setup_ui()
        self._setup_status_bar()
        self._apply_saved_theme()

    def _setup_menu(self):
        """Construct the menu bar with File and Help menus."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        self._open_action = QAction("&Open Database...", self)
        self._open_action.setShortcut("Ctrl+O")
        self._open_action.triggered.connect(self._on_open_database)
        file_menu.addAction(self._open_action)

        self._close_action = QAction("&Close Database", self)
        self._close_action.setShortcut("Ctrl+W")
        self._close_action.triggered.connect(self._on_close_database)
        self._close_action.setEnabled(False)
        file_menu.addAction(self._close_action)

        file_menu.addSeparator()

        self._quit_action = QAction("&Quit", self)
        self._quit_action.setShortcut("Ctrl+Q")
        self._quit_action.triggered.connect(self.close)
        file_menu.addAction(self._quit_action)

        view_menu = menubar.addMenu("&View")
        self._dark_mode_action = QAction("&Dark Mode", self)
        self._dark_mode_action.setCheckable(True)
        self._dark_mode_action.setChecked(self._settings.value("dark_mode", False, type=bool))
        self._dark_mode_action.triggered.connect(self._on_toggle_theme)
        view_menu.addAction(self._dark_mode_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_ui(self):
        """Build the central widget layout with schema browser and tab area."""
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(self._splitter)

        self._schema_browser = SchemaBrowser()
        self._schema_browser.table_selected.connect(self._on_table_selected)
        self._schema_browser.view_selected.connect(self._on_view_selected)
        self._splitter.addWidget(self._schema_browser)

        self._right_tabs = QTabWidget()
        self._right_tabs.setTabsClosable(True)
        self._right_tabs.tabCloseRequested.connect(self._on_right_tab_close)

        self._query_editor = QueryEditorWidget()
        self._right_tabs.addTab(self._query_editor, "Query")

        self._splitter.addWidget(self._right_tabs)

        self._splitter.setSizes([250, 950])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

    def _setup_status_bar(self):
        """Create the status bar with a connection state label."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("No database open")
        self._status_bar.addPermanentWidget(self._status_label)

    def _recent_files(self) -> list[str]:
        """Return the list of recently opened database file paths.

        Returns:
            List of file path strings from QSettings.
        """
        return self._settings.value("recent_files", [])

    def _add_recent_file(self, path: str) -> None:
        """Add a file path to the top of the recent files list.

        Duplicates are removed and the list is capped at RECENT_FILES_MAX.

        Args:
            path: File path to add.
        """
        files = self._recent_files()
        if path in files:
            files.remove(path)
        files.insert(0, path)
        self._settings.setValue("recent_files", files[:RECENT_FILES_MAX])

    def _on_open_database(self):
        """Show the connection dialog and open the selected database."""
        dlg = ConnectionDialog(recent_files=self._recent_files(), parent=self)
        if dlg.exec() != ConnectionDialog.DialogCode.Accepted:
            return
        path = dlg.selected_path
        if not path:
            return
        try:
            self._db.close()
            self._db.connect(path)
            self._schema_browser.set_database(self._db)
            self._query_editor.set_database(self._db)
            self._close_action.setEnabled(True)
            self._add_recent_file(path)
            self._status_label.setText(f"Connected: {self._db.path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open database:\n{e}")

    def _on_close_database(self):
        """Close the current database and reset all UI components."""
        self._db.close()
        self._schema_browser.set_database(None)
        self._query_editor.set_database(None)
        self._close_action.setEnabled(False)
        self._status_label.setText("No database open")

    def _on_table_selected(self, table_name: str) -> None:
        """Open a data browser tab for the selected table.

        Args:
            table_name: Name of the table to browse.
        """
        self._open_data_browser(table_name)

    def _on_view_selected(self, view_name: str) -> None:
        """Populate a new query tab with a SELECT * statement for the view.

        Args:
            view_name: Name of the view.
        """
        tab = self._query_editor.add_tab()
        tab.editor.setPlainText(f"SELECT * FROM \"{view_name}\"\n")

    def _open_data_browser(self, table_name: str) -> None:
        """Open or switch to a data browser tab for the given table.

        If a tab for the table already exists, it is brought to the front.

        Args:
            table_name: Name of the table to browse.
        """
        for i in range(self._right_tabs.count()):
            w = self._right_tabs.widget(i)
            if hasattr(w, '_table_name') and w._table_name == table_name:
                self._right_tabs.setCurrentIndex(i)
                return
        browser = DataBrowser(self._db, table_name)
        idx = self._right_tabs.addTab(browser, table_name)
        self._right_tabs.setCurrentIndex(idx)

    def _on_right_tab_close(self, index: int) -> None:
        """Close a right-side tab, except the query editor tab.

        Args:
            index: Index of the tab to close.
        """
        w = self._right_tabs.widget(index)
        if w is self._query_editor:
            return
        self._right_tabs.removeTab(index)

    def _apply_saved_theme(self) -> None:
        """Apply the theme from saved settings at startup."""
        dark = self._settings.value("dark_mode", False, type=bool)
        self._dark_mode_action.setChecked(dark)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(THEMES["dark" if dark else "light"])

    def _on_toggle_theme(self) -> None:
        """Toggle between light and dark theme."""
        dark = self._dark_mode_action.isChecked()
        theme = "dark" if dark else "light"
        app = QApplication.instance()
        if app:
            app.setStyleSheet(THEMES[theme])
        self._settings.setValue("dark_mode", dark)

    def _on_about(self):
        """Show the About dialog."""
        QMessageBox.about(self, "About SQLite Client",
                          "SQLite Client v0.1.0\n\nA PyQt6-based SQLite database browser.")

    def closeEvent(self, event):
        """Close the database connection before shutting down.

        Args:
            event: The close event.
        """
        self._db.close()
        super().closeEvent(event)
