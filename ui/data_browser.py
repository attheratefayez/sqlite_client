"""Data browsing widget for viewing and editing table contents.

Provides :class:`DataTableModel` (a QAbstractTableModel) and
:class:`DataBrowser` (a QWidget with pagination, search, and
inline editing capabilities).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QPushButton, QLabel, QSpinBox, QLineEdit, QCheckBox,
    QMessageBox, QSplitter, QTextEdit,
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from core.database import ColumnInfo, quote_identifier
from core.worker import DatabaseWorker
from ui.export_dialog import ExportDialog


class DataTableModel(QAbstractTableModel):
    """Table model for browsing and editing a page of database rows.

    The first column is a checkable selection column. All data columns
    following it are editable.

    Signals:
        data_changed: Emitted with (row, column_index) when a cell is edited.
    """

    data_changed = pyqtSignal(int, int)

    def __init__(self, columns: list[ColumnInfo], rows: list[tuple], parent=None):
        """Initialize the model with column metadata and row data.

        Args:
            columns: Column metadata list from the database schema.
            rows: Tuples of row values for the current page.
            parent: Optional parent object.
        """
        super().__init__(parent)
        self._columns = columns
        self._rows = rows
        self._checked: set[int] = set()

    def rowCount(self, parent=QModelIndex()) -> int:
        """Return the number of rows in the model.

        Args:
            parent: Unused parent index.

        Returns:
            Row count.
        """
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Return the number of columns (selection column + data columns).

        Args:
            parent: Unused parent index.

        Returns:
            Column count.
        """
        return len(self._columns) + 1

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        """Return data for a given index and role.

        Args:
            index: Model index specifying row and column.
            role: The data role to query.

        Returns:
            Data value for the requested role, or None.
        """
        if not index.isValid():
            return None
        col = index.column()
        if col == 0:
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if index.row() in self._checked else Qt.CheckState.Unchecked
            return None
        value = self._rows[index.row()][col - 1]
        if role == Qt.ItemDataRole.DisplayRole:
            if value is None:
                return "NULL"
            return str(value)
        if role == Qt.ItemDataRole.EditRole:
            return "" if value is None else value
        if role == Qt.ItemDataRole.ForegroundRole:
            if value is None:
                return QColor("#808080")
        return None

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole) -> bool:
        """Set data for a given index.

        Supports check-state changes in column 0 and inline edits in data
        columns. Emits :attr:`data_changed` on successful edits.

        Args:
            index: Model index specifying row and column.
            value: New value.
            role: The data role being set.

        Returns:
            True if the data was set successfully.
        """
        if not index.isValid():
            return False
        col = index.column()
        if col == 0 and role == Qt.ItemDataRole.CheckStateRole:
            row = index.row()
            if value == Qt.CheckState.Checked.value:
                self._checked.add(row)
            else:
                self._checked.discard(row)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        if role == Qt.ItemDataRole.EditRole:
            row = index.row()
            col_idx = col - 1
            self._rows[row] = list(self._rows[row])
            self._rows[row][col_idx] = value
            self._rows[row] = tuple(self._rows[row])
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
            self.data_changed.emit(row, col_idx)
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return item flags for the given index.

        Column 0 is checkable; all other columns are editable.

        Args:
            index: Model index.

        Returns:
            Combination of ItemFlags.
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if index.column() == 0:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        """Return header data for a section.

        Args:
            section: Header section index.
            orientation: Horizontal or vertical.
            role: Data role.

        Returns:
            Header string or None.
        """
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section == 0:
                    return ""
                return self._columns[section - 1].name
            return str(section + 1)
        return None

    @property
    def checked_rows(self) -> set[int]:
        """set[int]: Row indices that are currently checked."""
        return self._checked

    def select_all(self, checked: bool) -> None:
        """Check or uncheck all rows.

        Args:
            checked: True to check all rows, False to uncheck all.
        """
        if checked:
            self._checked = set(range(len(self._rows)))
        else:
            self._checked = set()
        top_left = self.index(0, 0)
        bottom_right = self.index(len(self._rows) - 1, 0)
        self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.CheckStateRole])

    def rows_data(self) -> list[tuple]:
        """list[tuple]: The underlying row data."""
        return self._rows

    def columns(self) -> list[ColumnInfo]:
        """list[ColumnInfo]: The column metadata."""
        return self._columns


class DataBrowser(QWidget):
    """A widget for browsing, searching, editing, and deleting table data.

    Provides pagination, full-text search across all columns, inline
    editing, row insertion/deletion, and data export.  All database
    operations run on a background :class:`DatabaseWorker` thread.

    Attributes:
        _table_name: Name of the table being browsed.
    """

    load_page_requested = pyqtSignal(str, int, int, str)
    commit_requested = pyqtSignal(str, list, list)
    add_row_requested = pyqtSignal(str, list)
    delete_requested = pyqtSignal(str, str, list)

    def __init__(
        self,
        worker: DatabaseWorker,
        table_name: str,
        columns: list[ColumnInfo],
        total_count: int,
        parent=None,
    ):
        """Initialize the data browser for a specific table.

        Args:
            worker: Background worker for async database operations.
            table_name: Name of the table to browse.
            columns: Pre-fetched column schema for the table.
            total_count: Pre-fetched total row count.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._worker = worker
        self._table_name = table_name
        self._columns = columns
        self._page = 0
        self._page_size = 100
        self._search: str = ""
        self._total_count = total_count

        self._pending_edits: dict[tuple[Any, str], str] = {}
        self._busy = False
        self._model = DataTableModel(self._columns, [])
        self._setup_ui()

        self._table_view.setModel(self._model)

        self.load_page_requested.connect(worker.request_data_page)
        self.commit_requested.connect(worker.request_commit)
        self.add_row_requested.connect(worker.request_add_row)
        self.delete_requested.connect(worker.request_delete_rows)

        worker.data_page_finished.connect(self._on_data_page_loaded)
        worker.edits_committed.connect(self._on_action_done)
        worker.row_added.connect(self._on_action_done)
        worker.rows_deleted.connect(self._on_action_done)
        worker.error.connect(self._on_worker_error)

        self._request_page()

    def _setup_ui(self):
        """Build the data browser UI layout."""
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel(f"<b>{self._table_name}</b>"))

        self._page_prev = QPushButton("◀ Prev")
        self._page_prev.clicked.connect(self._prev_page)
        top_bar.addWidget(self._page_prev)

        self._page_label = QLabel()
        top_bar.addWidget(self._page_label)

        self._page_next = QPushButton("Next ▶")
        self._page_next.clicked.connect(self._next_page)
        top_bar.addWidget(self._page_next)

        top_bar.addWidget(QLabel("Page size:"))
        self._page_size_spin = QSpinBox()
        self._page_size_spin.setRange(10, 1000)
        self._page_size_spin.setValue(self._page_size)
        self._page_size_spin.setSingleStep(50)
        self._page_size_spin.valueChanged.connect(self._on_page_size_changed)
        top_bar.addWidget(self._page_size_spin)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search...")
        self._search_input.returnPressed.connect(self._on_search)
        top_bar.addWidget(self._search_input)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        top_bar.addWidget(search_btn)

        layout.addLayout(top_bar)

        self._table_view = QTableView()
        self._table_view.setAlternatingRowColors(True)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        layout.addWidget(self._table_view)

        bottom_bar = QHBoxLayout()
        self._select_all_cb = QCheckBox("Select All")
        self._select_all_cb.stateChanged.connect(self._on_select_all)
        bottom_bar.addWidget(self._select_all_cb)

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.clicked.connect(self._delete_selected)
        bottom_bar.addWidget(self._delete_btn)

        self._commit_btn = QPushButton("Commit Changes")
        self._commit_btn.setEnabled(False)
        self._commit_btn.clicked.connect(self._commit_changes)
        bottom_bar.addWidget(self._commit_btn)

        self._total_label = QLabel()
        bottom_bar.addWidget(self._total_label)
        bottom_bar.addStretch()

        self._add_row_btn = QPushButton("+ Add Row")
        self._add_row_btn.clicked.connect(self._add_row)
        bottom_bar.addWidget(self._add_row_btn)

        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._export_data)
        bottom_bar.addWidget(self._export_btn)

        layout.addLayout(bottom_bar)

    def _request_page(self) -> None:
        """Request the current page from the worker thread."""
        self._busy = True
        self._set_controls_enabled(False)
        self.load_page_requested.emit(
            self._table_name, self._page, self._page_size, self._search,
        )

    def _on_data_page_loaded(
        self,
        table_name: str,
        columns: list,
        rows: list[tuple],
        total_count: int,
    ) -> None:
        """Handle a page of data loaded by the worker."""
        if table_name != self._table_name:
            return
        self._total_count = total_count
        self._pending_edits.clear()
        self._commit_btn.setEnabled(False)
        self._model = DataTableModel(self._columns, rows)
        self._model.data_changed.connect(self.record_edit)
        self._table_view.setModel(self._model)
        self._update_nav_labels()
        self._busy = False
        self._set_controls_enabled(True)

    def _update_nav_labels(self) -> None:
        """Refresh pagination labels."""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        self._page_label.setText(f"Page {self._page + 1} of {total_pages}")
        self._total_label.setText(f"Total rows: {self._total_count}")

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enable or disable interactive controls during loading."""
        self._page_prev.setEnabled(enabled and self._page > 0)
        self._page_next.setEnabled(enabled)
        self._page_size_spin.setEnabled(enabled)
        self._search_input.setEnabled(enabled)
        self._delete_btn.setEnabled(enabled)
        self._add_row_btn.setEnabled(enabled)

    def _prev_page(self) -> None:
        """Navigate to the previous page."""
        if self._page > 0 and self._prompt_discard_or_abort() and not self._busy:
            self._page -= 1
            self._request_page()

    def _next_page(self) -> None:
        """Navigate to the next page."""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        if self._page < total_pages - 1 and self._prompt_discard_or_abort() and not self._busy:
            self._page += 1
            self._request_page()

    def _on_page_size_changed(self, value: int) -> None:
        """Handle page size spinbox changes.

        Args:
            value: New page size.
        """
        if self._prompt_discard_or_abort() and not self._busy:
            self._page_size = value
            self._page = 0
            self._request_page()

    def _on_search(self) -> None:
        """Perform a search across all columns and update the data view."""
        if not self._prompt_discard_or_abort() or self._busy:
            return
        self._search = self._search_input.text().strip()
        self._page = 0
        self._request_page()

    def _on_select_all(self, state: int) -> None:
        """Handle the Select All checkbox state change.

        Args:
            state: Qt check state integer.
        """
        if self._model:
            self._model.select_all(state == Qt.CheckState.Checked.value)

    def _delete_selected(self) -> None:
        """Delete all checked rows after confirmation."""
        if not self._model or not self._model.checked_rows:
            QMessageBox.information(self, "Delete", "No rows selected.")
            return
        if not self._prompt_discard_or_abort() or self._busy:
            return
        rows = sorted(self._model.checked_rows, reverse=True)
        pk_cols = [c for c in self._columns if c.primary_key]
        if not pk_cols:
            QMessageBox.warning(self, "Delete", "Table has no primary key.")
            return
        pk_name = pk_cols[0].name
        pk_idx = pk_cols[0].cid
        pk_values = [self._model.rows_data()[r][pk_idx] for r in rows]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {len(rows)} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._busy = True
        self._set_controls_enabled(False)
        self.delete_requested.emit(self._table_name, pk_name, pk_values)

    def _add_row(self) -> None:
        """Insert a new row with all-NULL values into the table."""
        if not self._prompt_discard_or_abort() or self._busy:
            return
        self._busy = True
        self._set_controls_enabled(False)
        self.add_row_requested.emit(self._table_name, self._columns)

    def record_edit(self, row: int, col_idx: int) -> None:
        """Record a pending cell edit without persisting.

        Args:
            row: Row index in the model.
            col_idx: Column index in the model (0-based data column).
        """
        pk_cols = [c for c in self._columns if c.primary_key]
        if not pk_cols:
            return
        pk_idx = pk_cols[0].cid
        pk_val = self._model.rows_data()[row][pk_idx]
        col_name = self._columns[col_idx].name
        new_val = self._model.rows_data()[row][col_idx]
        self._pending_edits[(pk_val, col_name)] = new_val
        self._commit_btn.setEnabled(True)

    def _commit_changes(self) -> None:
        """Persist all pending edits via the worker thread."""
        if not self._pending_edits or self._busy:
            return
        pk_cols = [c for c in self._columns if c.primary_key]
        pk_name = pk_cols[0].name if pk_cols else None
        if pk_name is None:
            return
        pending = [
            (pk_val, col_name, new_val)
            for (pk_val, col_name), new_val in self._pending_edits.items()
        ]
        self._busy = True
        self._commit_btn.setEnabled(False)
        self.commit_requested.emit(self._table_name, self._columns, pending)

    def _discard_pending_edits(self) -> None:
        """Clear pending edits and disable the commit button."""
        self._pending_edits.clear()
        self._commit_btn.setEnabled(False)

    def _prompt_discard_or_abort(self) -> bool:
        """Prompt the user to discard unsaved changes.

        Returns:
            True if it is safe to proceed (no edits or user chose discard),
            False if the user chose to cancel.
        """
        if not self._pending_edits:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False
        self._discard_pending_edits()
        return True

    def _on_action_done(self, table_name: str) -> None:
        """Handle completion of a write action (commit, add, delete)."""
        if table_name != self._table_name:
            return
        self._request_page()

    def _on_worker_error(self, message: str) -> None:
        """Handle an error emitted by the worker."""
        self._busy = False
        self._set_controls_enabled(True)
        QMessageBox.warning(self, "Database Error", message)

    def _export_data(self) -> None:
        """Open the export dialog for the current page of data."""
        columns = [c.name for c in self._columns]
        rows = self._model.rows_data() if self._model else []
        dlg = ExportDialog(self._table_name, columns, rows, self)
        dlg.exec()

    def refresh(self) -> None:
        """Reload the current page without user prompt."""
        if self._busy:
            return
        self._request_page()

    _quote = staticmethod(quote_identifier)


class TableTab(QWidget):
    """A tab with a read-only CREATE TABLE DDL on top and DataBrowser below."""

    def __init__(
        self,
        worker: DatabaseWorker,
        table_name: str,
        columns: list[ColumnInfo],
        total_count: int,
        ddl: str,
        parent=None,
    ):
        super().__init__(parent)
        self._table_name = table_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._ddl_view = QTextEdit()
        self._ddl_view.setPlainText(ddl)
        self._ddl_view.setReadOnly(True)
        font = QFont("monospace")
        font.setPointSize(10)
        self._ddl_view.setFont(font)
        splitter.addWidget(self._ddl_view)

        self._browser = DataBrowser(worker, table_name, columns, total_count)
        splitter.addWidget(self._browser)

        splitter.setSizes([450, 550])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def refresh(self) -> None:
        self._browser.refresh()
