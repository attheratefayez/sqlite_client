from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QTreeWidgetItem,
    QMenuBar, QMenu, QStatusBar, QMessageBox, QFileDialog, QWidget, QVBoxLayout, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from core.database import DatabaseConnection
from ui.schema_browser import SchemaBrowser


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._db = DatabaseConnection()
        self.setWindowTitle("SQLite Client")
        self.resize(1200, 800)

        self._setup_menu()
        self._setup_ui()
        self._setup_status_bar()

    def _setup_menu(self):
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

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_ui(self):
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(self._splitter)

        self._schema_browser = SchemaBrowser()
        self._schema_browser.table_selected.connect(self._on_table_selected)
        self._schema_browser.view_selected.connect(self._on_view_selected)
        self._splitter.addWidget(self._schema_browser)

        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close)
        self._splitter.addWidget(self._tab_widget)

        self._splitter.setSizes([250, 950])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        self._show_welcome_tab()

    def _setup_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("No database open")
        self._status_bar.addPermanentWidget(self._status_label)

    def _show_welcome_tab(self):
        welcome = QWidget()
        layout = QVBoxLayout(welcome)
        layout.addWidget(QLabel("Open a database to get started."))
        self._tab_widget.addTab(welcome, "Welcome")
        self._tab_widget.setTabsClosable(False)
        self._tab_widget.tabCloseRequested.disconnect()

    def _on_open_database(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Database", "", "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if not path:
            return
        try:
            self._db.close()
            self._db.connect(path)
            self._schema_browser.set_database(self._db)
            self._close_action.setEnabled(True)
            self._status_label.setText(f"Connected: {self._db.path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open database:\n{e}")

    def _on_close_database(self):
        self._db.close()
        self._schema_browser.set_database(None)
        self._close_action.setEnabled(False)
        self._status_label.setText("No database open")

    def _on_table_selected(self, table_name: str) -> None:
        pass

    def _on_view_selected(self, view_name: str) -> None:
        pass

    def _on_about(self):
        QMessageBox.about(self, "About SQLite Client", "SQLite Client v0.1.0\n\nA PyQt6-based SQLite database browser.")

    def _on_tab_close(self, index: int) -> None:
        self._tab_widget.removeTab(index)

    def closeEvent(self, event):
        self._db.close()
        super().closeEvent(event)
