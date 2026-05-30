"""Query editor widget with multi-tab support and syntax highlighting.

Provides :class:`SqlEditWidget` (a plain text editor with
Ctrl+Enter execution), :class:`QueryTab` (a split editor + results
container), and :class:`QueryEditorWidget` (a multi-tab manager).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton, QHBoxLayout,
    QTabWidget, QLabel, QSplitter, QTableView, QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ui.syntax_highlight import SqlHighlighter
from ui.results_view import ResultsView
from core.database import DatabaseConnection
from core.query_executor import QueryExecutor, QueryResult


class SqlEditWidget(QPlainTextEdit):
    """A monospace SQL editor that emits a signal on Ctrl+Enter.

    Signals:
        execute_requested: Emitted with the editor text when
            Ctrl+Enter is pressed.
    """

    execute_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize the editor with a monospace font and syntax highlighter.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        font = QFont("Monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(40)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._highlighter = SqlHighlighter(self.document())

    def keyPressEvent(self, event):
        """Intercept Ctrl+Enter to emit execute_requested.

        Args:
            event: The key press event.
        """
        if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.execute_requested.emit(self.toPlainText())
            return
        super().keyPressEvent(event)


class QueryTab(QWidget):
    """A single query tab containing an editor and a results view.

    Signals:
        execute_requested: Emitted with SQL text when execution is triggered.
    """

    execute_requested = pyqtSignal(str)

    def __init__(self, title: str = "Query", parent=None):
        """Initialize the tab with a splitter layout.

        Args:
            title: Tab title (unused, kept for compatibility).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._splitter = QSplitter(Qt.Orientation.Vertical)

        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        self.editor = SqlEditWidget()
        self.editor.execute_requested.connect(self._on_execute)

        self._button_layout = QHBoxLayout()
        self._execute_btn = QPushButton("▶ Execute (Ctrl+Enter)")
        self._execute_btn.clicked.connect(self._on_execute_clicked)
        self._button_layout.addWidget(self._execute_btn)
        self._button_layout.addStretch()

        editor_layout.addLayout(self._button_layout)
        editor_layout.addWidget(self.editor)

        self.results = ResultsView()

        self._splitter.addWidget(editor_container)
        self._splitter.addWidget(self.results)
        self._splitter.setSizes([300, 400])

        layout.addWidget(self._splitter)

    def _on_execute(self, sql: str = "") -> None:
        """Emit execute_requested with the SQL text.

        Args:
            sql: SQL text, or empty to use the editor content.
        """
        sql = sql or self.editor.toPlainText()
        if sql.strip():
            self.execute_requested.emit(sql)

    def _on_execute_clicked(self) -> None:
        """Handle the Execute button click."""
        self._on_execute()

    def set_executor(self, executor: QueryExecutor) -> None:
        """Set the query executor for running statements.

        Args:
            executor: A QueryExecutor instance.
        """
        self._executor = executor

    def show_query_result(self, result: QueryResult) -> None:
        """Display a QueryResult in the results view.

        Args:
            result: The result to display.
        """
        self.results.show_result(result)


class QueryEditorWidget(QWidget):
    """Multi-tab query editor with a shared executor.

    Manages multiple :class:`QueryTab` instances and routes SQL
    execution through a single :class:`QueryExecutor`.
    """

    def __init__(self, parent=None):
        """Initialize the editor with one default tab.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._executor: QueryExecutor | None = None
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

    def set_database(self, db: DatabaseConnection | None) -> None:
        """Set the database connection used by all query tabs.

        Args:
            db: A DatabaseConnection, or None to clear.
        """
        if db is not None:
            self._executor = QueryExecutor(db)
        else:
            self._executor = None

    def add_tab(self) -> QueryTab:
        """Add a new query tab.

        Returns:
            The newly created QueryTab.
        """
        self._tab_counter += 1
        tab = QueryTab()
        tab.execute_requested.connect(self._on_tab_execute)
        self._tabs.addTab(tab, f"Query {self._tab_counter}")
        self._tabs.setCurrentWidget(tab)
        return tab

    def current_tab(self) -> QueryTab | None:
        """Return the currently visible query tab, or None.

        Returns:
            The active QueryTab, or None.
        """
        widget = self._tabs.currentWidget()
        return widget if isinstance(widget, QueryTab) else None

    def _close_tab(self, index: int) -> None:
        """Close the tab at the given index, keeping at least one.

        Args:
            index: Index of the tab to close.
        """
        if self._tabs.count() > 1:
            self._tabs.removeTab(index)

    def _on_tab_execute(self, sql: str) -> None:
        """Execute SQL in the active tab and display results.

        Args:
            sql: SQL statement to execute.
        """
        if self._executor is None:
            tab = self.current_tab()
            if tab:
                err = QueryResult(error="No database connection")
                tab.show_query_result(err)
            return
        result = self._executor.execute(sql)
        tab = self.current_tab()
        if tab:
            tab.show_query_result(result)
