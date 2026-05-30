"""Export dialog for saving query results to file.

Provides :class:`ExportDialog` which lets the user choose between
CSV, JSON, and SQL INSERT formats and write the data to a file.
"""

import io
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QDialogButtonBox, QFileDialog, QMessageBox,
)
from core.export import export_csv, export_json, export_sql_inserts


class ExportDialog(QDialog):
    """A modal dialog for exporting table or query results to a file.

    Supports CSV, JSON, and SQL INSERT output formats.
    """

    def __init__(self, table_name: str, columns: list[str], rows: list[tuple], parent=None):
        """Initialize the export dialog.

        Args:
            table_name: Name of the source table (used in default filename
                and SQL INSERT generation).
            columns: Column names for the data.
            rows: Row data to export.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Export {table_name}")
        self.resize(400, 150)
        self._table_name = table_name
        self._columns = columns
        self._rows = rows

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Export table: <b>{table_name}</b>"))
        layout.addWidget(QLabel(f"Rows: {len(rows)}, Columns: {len(columns)}"))

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["CSV (.csv)", "JSON (.json)", "SQL INSERT (.sql)"])
        format_layout.addWidget(self._format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)

        button_layout = QHBoxLayout()
        self._export_btn = QPushButton("Export...")
        self._export_btn.clicked.connect(self._do_export)
        button_layout.addWidget(self._export_btn)
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _do_export(self) -> None:
        """Perform the export to a user-selected file."""
        fmt = self._format_combo.currentText()
        ext_map = {
            "CSV (.csv)": ".csv",
            "JSON (.json)": ".json",
            "SQL INSERT (.sql)": ".sql",
        }
        ext = ext_map.get(fmt, ".csv")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Export", f"{self._table_name}{ext}",
            f"*{ext}",
        )
        if not path:
            return
        try:
            buf = io.StringIO()
            if fmt == "CSV (.csv)":
                export_csv(self._columns, self._rows, buf)
            elif fmt == "JSON (.json)":
                export_json(self._columns, self._rows, buf)
            elif fmt == "SQL INSERT (.sql)":
                export_sql_inserts(self._table_name, self._columns, self._rows, buf)
            with open(path, "w") as f:
                f.write(buf.getvalue())
            QMessageBox.information(self, "Exported", f"Exported {len(self._rows)} rows to {path}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{e}")
