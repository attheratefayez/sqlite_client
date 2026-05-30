from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QLabel,
    QHBoxLayout, QPushButton,
)
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QColor

from core.query_executor import QueryResult


class ResultTableModel(QAbstractTableModel):
    def __init__(self, result: QueryResult, parent=None):
        super().__init__(parent)
        self._columns = result.columns
        self._rows = result.rows

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._rows[index.row()][index.column()]
            if value is None:
                return "NULL"
            return str(value)
        if role == Qt.ItemDataRole.ForegroundRole:
            value = self._rows[index.row()][index.column()]
            if value is None:
                return QColor("#808080")
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._columns[section]
            return str(section + 1)
        return None

    @property
    def columns(self) -> list[str]:
        return self._columns

    @property
    def rows(self) -> list[tuple]:
        return self._rows


class ResultsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._info_layout = QHBoxLayout()
        self._info_layout.setContentsMargins(0, 0, 0, 0)

        self._info_label = QLabel("")
        self._info_layout.addWidget(self._info_label)
        self._info_layout.addStretch()

        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._export)
        self._export_btn.setVisible(False)
        self._info_layout.addWidget(self._export_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._info_layout)

        self._table_view = QTableView()
        self._table_view.setAlternatingRowColors(True)
        self._table_view.horizontalHeader().setStretchLastSection(True)
        self._table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        layout.addWidget(self._table_view)

        self._result: QueryResult | None = None

    def show_result(self, result: QueryResult) -> None:
        self._result = result
        if result.error:
            self._info_label.setText(f"Error: {result.error}")
            self._info_label.setStyleSheet("color: red;")
            self._table_view.setModel(None)
            self._export_btn.setVisible(False)
            return

        self._info_label.setStyleSheet("")
        model = ResultTableModel(result)
        self._table_view.setModel(model)
        self._table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        info_parts = []
        if result.row_count > 0:
            info_parts.append(f"{result.row_count} row(s)")
        elif not result.is_select:
            info_parts.append("Query executed successfully")
        info_parts.append(f"{result.duration_ms} ms")
        self._info_label.setText(" | ".join(info_parts))
        self._export_btn.setVisible(result.row_count > 0)

    def clear(self) -> None:
        self._table_view.setModel(None)
        self._info_label.setText("")
        self._export_btn.setVisible(False)

    def _export(self) -> None:
        if self._result is None:
            return
        from ui.export_dialog import ExportDialog
        dlg = ExportDialog("query", self._result.columns, self._result.rows, self)
        dlg.exec()
