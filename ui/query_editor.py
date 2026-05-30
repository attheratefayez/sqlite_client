from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton, QHBoxLayout,
    QTabWidget, QLabel, QSplitter, QTableView, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction

from ui.syntax_highlight import SqlHighlighter
from core.database import DatabaseConnection


class SqlEditWidget(QPlainTextEdit):
    execute_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(40)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._highlighter = SqlHighlighter(self.document())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.execute_requested.emit(self.toPlainText())
            return
        super().keyPressEvent(event)


class QueryTab(QWidget):
    execute_requested = pyqtSignal(str)

    def __init__(self, title: str = "Query", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.editor = SqlEditWidget()
        self.editor.execute_requested.connect(self._on_execute)

        self._button_layout = QHBoxLayout()
        self._execute_btn = QPushButton("▶ Execute (Ctrl+Enter)")
        self._execute_btn.clicked.connect(self._on_execute_clicked)
        self._button_layout.addWidget(self._execute_btn)
        self._button_layout.addStretch()

        layout.addLayout(self._button_layout)
        layout.addWidget(self.editor)

    def _on_execute(self, sql: str = "") -> None:
        sql = sql or self.editor.toPlainText()
        if sql.strip():
            self.execute_requested.emit(sql)

    def _on_execute_clicked(self) -> None:
        self._on_execute()


class QueryEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._layout.addWidget(self._tabs)

        button_layout = QHBoxLayout()
        self._new_tab_btn = QPushButton("+ New Tab")
        self._new_tab_btn.clicked.connect(self.add_tab)
        button_layout.addWidget(self._new_tab_btn)
        button_layout.addStretch()
        self._layout.addLayout(button_layout)

        self._tab_counter = 0
        self.add_tab()

    def add_tab(self) -> QueryTab:
        self._tab_counter += 1
        tab = QueryTab()
        tab.execute_requested.connect(self._on_tab_execute)
        self._tabs.addTab(tab, f"Query {self._tab_counter}")
        self._tabs.setCurrentWidget(tab)
        return tab

    def current_tab(self) -> QueryTab | None:
        widget = self._tabs.currentWidget()
        return widget if isinstance(widget, QueryTab) else None

    def _close_tab(self, index: int) -> None:
        if self._tabs.count() > 1:
            self._tabs.removeTab(index)

    def _on_tab_execute(self, sql: str) -> None:
        pass
