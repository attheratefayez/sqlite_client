"""Main application window for the SQLite Client."""

import pathlib

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QApplication,
    QStatusBar, QMessageBox, QLabel, QDockWidget,
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction

from core.database import DatabaseConnection
from core.worker import DatabaseWorker
from ui.schema_browser import SchemaBrowser
from ui.query_editor import QueryEditorWidget
from ui.connection_dialog import ConnectionDialog
from ui.data_browser import DataBrowser
from chat.chat_panel import ChatPanel
from chat.worker import ChatWorker
from chat.agent import (
    RouterChatAgent,
    DEFAULT_CHAT_MODEL,
    DEFAULT_SQL_MODEL,
)
from resources.style import THEMES


RECENT_FILES_MAX = 10


class MainWindow(QMainWindow):
    """Main application window coordinating all UI components."""

    _open_worker_db = pyqtSignal(str)
    _close_worker_db = pyqtSignal()
    _chat_set_db = pyqtSignal(str)
    _chat_set_models = pyqtSignal(str, str)
    _chat_load_history = pyqtSignal()

    def __init__(self):
        """Initialize the main window, menus, UI layout, and status bar."""
        super().__init__()
        self._db = DatabaseConnection()
        self.setWindowTitle("SQLite Client")
        self.resize(1200, 800)

        self._settings = QSettings("sqlite-client", "sqlite-client")

        self._worker_thread = QThread()
        self._worker = DatabaseWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.start()

        self._open_worker_db.connect(self._worker.open_database)
        self._close_worker_db.connect(self._worker.close_database)

        self._chat_model = self._settings.value(
            "chat_model", DEFAULT_CHAT_MODEL, type=str
        )
        self._sql_model = self._settings.value(
            "sql_model", DEFAULT_SQL_MODEL, type=str
        )
        self._chat_thread = QThread()
        self._chat_worker = ChatWorker(
            RouterChatAgent(
                chat_model=self._chat_model,
                sql_model=self._sql_model,
            )
        )
        self._chat_worker.moveToThread(self._chat_thread)
        self._chat_thread.start()

        self._chat_set_db.connect(self._chat_worker.set_database_path)
        self._chat_set_models.connect(self._chat_worker.set_models)
        self._chat_load_history.connect(self._chat_worker.load_history)

        self._setup_menu()
        self._setup_ui()
        self._setup_chat_dock()
        self._setup_status_bar()
        self._apply_saved_theme()

        self._chat_worker.history_loaded.connect(self._chat_panel.load_history)

        self._load_last_database()
        if not self._db.is_connected:
            QTimer.singleShot(0, lambda: self._chat_set_db.emit(""))

    def _setup_menu(self):
        """Construct the menu bar with File, View, and Help menus."""
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
        self._dark_mode_action.setChecked(
            self._settings.value("dark_mode", False, type=bool)
        )
        self._dark_mode_action.triggered.connect(self._on_toggle_theme)
        view_menu.addAction(self._dark_mode_action)
        view_menu.addSeparator()
        self._chat_action = QAction("&Chat", self)
        self._chat_action.setCheckable(True)
        self._chat_action.setChecked(True)
        self._chat_action.triggered.connect(self._on_toggle_chat)
        view_menu.addAction(self._chat_action)

        self._chat_model_action = QAction("Chat &Models...", self)
        self._chat_model_action.triggered.connect(self._on_configure_models)
        view_menu.addAction(self._chat_model_action)

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
        self._query_editor.execute_query_requested.connect(
            self._worker.request_query
        )
        self._worker.query_finished.connect(
            self._query_editor._on_query_result
        )
        self._right_tabs.addTab(self._query_editor, "Query")

        self._splitter.addWidget(self._right_tabs)

        self._splitter.setSizes([250, 950])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

    def _setup_chat_dock(self):
        """Create the collapsible chat dock widget on the right side."""
        self._chat_dock = QDockWidget("Chat", self)
        self._chat_dock.setObjectName("chat_dock")
        self._chat_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self._chat_panel = ChatPanel()
        self._chat_dock.setWidget(self._chat_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._chat_dock)

        self._chat_panel.message_sent.connect(self._chat_worker.send_message)
        self._chat_panel.clear_requested.connect(self._chat_worker.clear_history)
        self._chat_worker.response_received.connect(
            self._chat_panel.append_reply
        )
        self._chat_dock.visibilityChanged.connect(self._chat_action.setChecked)

    def _on_toggle_chat(self, visible: bool) -> None:
        self._chat_dock.setVisible(visible)

    def _on_configure_models(self) -> None:
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("Chat Model Settings")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        chat_edit = QLineEdit(self._chat_model)
        chat_edit.setPlaceholderText("e.g. HuggingFaceH4/zephyr-7b-beta")
        form.addRow("Chat model:", chat_edit)

        sql_edit = QLineEdit(self._sql_model)
        sql_edit.setPlaceholderText("e.g. HuggingFaceH4/zephyr-7b-beta")
        form.addRow("SQL model:", sql_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        chat = chat_edit.text().strip()
        sql = sql_edit.text().strip()

        if not chat or not sql:
            return

        self._chat_model = chat
        self._sql_model = sql
        self._settings.setValue("chat_model", chat)
        self._settings.setValue("sql_model", sql)
        self._chat_set_models.emit(chat, sql)

    def _setup_status_bar(self):
        """Create the status bar with a connection state label."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("No database open")
        self._status_bar.addPermanentWidget(self._status_label)

    def _recent_files(self) -> list[str]:
        return self._settings.value("recent_files", [])

    def _add_recent_file(self, path: str) -> None:
        files = self._recent_files()
        if path in files:
            files.remove(path)
        files.insert(0, path)
        self._settings.setValue("recent_files", files[:RECENT_FILES_MAX])

    def _connect_database(self, path: str) -> bool:
        try:
            self._db.close()
            self._db.connect(path)
            self._open_worker_db.emit(path)
            self._chat_set_db.emit(path)
            self._schema_browser.set_database(self._db)
            self._query_editor.set_connected(True)
            self._close_action.setEnabled(True)
            self._add_recent_file(path)
            self._settings.setValue("last_database", path)
            self._status_label.setText(f"Connected: {self._db.path}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open database:\n{e}")
            return False

    def _on_open_database(self):
        dlg = ConnectionDialog(recent_files=self._recent_files(), parent=self)
        if dlg.exec() != ConnectionDialog.DialogCode.Accepted:
            return
        path = dlg.selected_path
        if path:
            self._connect_database(path)

    def _load_last_database(self) -> None:
        path = self._settings.value("last_database", "")
        if not path or not pathlib.Path(path).exists():
            return
        try:
            self._db.connect(path)
            self._open_worker_db.emit(path)
            self._chat_set_db.emit(path)
            self._schema_browser.set_database(self._db)
            self._query_editor.set_connected(True)
            self._close_action.setEnabled(True)
            self._status_label.setText(f"Connected: {self._db.path}")
        except Exception:
            pass

    def _on_close_database(self):
        self._close_worker_db.emit()
        self._chat_set_db.emit("")
        self._db.close()
        self._schema_browser.set_database(None)
        self._query_editor.set_connected(False)
        self._close_action.setEnabled(False)
        self._status_label.setText("No database open")

    def _on_table_selected(self, table_name: str) -> None:
        self._open_data_browser(table_name)

    def _on_view_selected(self, view_name: str) -> None:
        tab = self._query_editor.add_tab()
        tab.editor.setPlainText(f"SELECT * FROM \"{view_name}\"\n")

    def _open_data_browser(self, table_name: str) -> None:
        for i in range(self._right_tabs.count()):
            w = self._right_tabs.widget(i)
            if hasattr(w, '_table_name') and w._table_name == table_name:
                self._right_tabs.setCurrentIndex(i)
                return
        columns = self._db.table_schema(table_name)
        total_count = self._db.table_row_count(table_name)
        browser = DataBrowser(self._worker, table_name, columns, total_count)
        idx = self._right_tabs.addTab(browser, table_name)
        self._right_tabs.setCurrentIndex(idx)

    def _on_right_tab_close(self, index: int) -> None:
        w = self._right_tabs.widget(index)
        if w is self._query_editor:
            return
        self._right_tabs.removeTab(index)

    def _set_theme(self, dark: bool) -> None:
        app = QApplication.instance()
        if app:
            app.setStyleSheet(THEMES["dark" if dark else "light"])

    def _apply_saved_theme(self) -> None:
        dark = self._settings.value("dark_mode", False, type=bool)
        self._dark_mode_action.setChecked(dark)
        self._set_theme(dark)

    def _on_toggle_theme(self) -> None:
        dark = self._dark_mode_action.isChecked()
        self._set_theme(dark)
        self._settings.setValue("dark_mode", dark)

    def _on_about(self):
        QMessageBox.about(
            self,
            "About SQLite Client",
            "SQLite Client v0.1.0\n\nA PyQt6-based SQLite database browser.",
        )

    def closeEvent(self, event):
        self._close_worker_db.emit()
        self._worker_thread.quit()
        self._worker_thread.wait(3000)
        self._chat_worker.close_store()
        self._chat_thread.quit()
        self._chat_thread.wait(3000)
        self._db.close()
        super().closeEvent(event)
