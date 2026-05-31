"""Dialog for displaying an ER diagram PNG with a save option."""

from __future__ import annotations

import pathlib
import shutil
import tempfile

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QScrollArea, QLabel, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from core.database import DatabaseConnection
from core.er_diagram import generate_er_png


class ErDialog(QDialog):
    """Modal dialog that displays an entity-relationship diagram.

    Shows a scrollable PNG rendered by Pillow.  Provides a **Save**
    button to export the image to a user-chosen location.
    """

    def __init__(
        self,
        parent: object = None,
        db_conn: DatabaseConnection | None = None,
        table_name: str | None = None,
    ):
        super().__init__(parent)
        self._db_conn = db_conn
        self._table_name = table_name
        self._png_path: str | None = None

        self.setWindowTitle(
            f"ER Diagram — {table_name}" if table_name else "ER Diagram — All Tables"
        )
        self.resize(800, 600)

        self._setup_ui()
        self._render_diagram()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(self._image_label)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._save_btn = QPushButton("Save As…")
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _render_diagram(self):
        if self._db_conn is None or not self._db_conn.is_connected:
            self._image_label.setText("No database connected.")
            return

        try:
            self._png_path = generate_er_png(
                self._db_conn,
                table_name=self._table_name,
            )
            pixmap = QPixmap(self._png_path)
            if pixmap.isNull():
                self._image_label.setText("Failed to render diagram.")
                return
            self._image_label.setPixmap(pixmap)
        except Exception as exc:
            self._image_label.setText(f"Error: {exc}")

    def _on_save(self):
        if not self._png_path:
            return
        default_name = (
            f"er_{self._table_name}.png"
            if self._table_name
            else "er_diagram.png"
        )
        dst, _ = QFileDialog.getSaveFileName(
            self,
            "Save ER Diagram",
            default_name,
            "PNG Images (*.png)",
        )
        if not dst:
            return
        try:
            shutil.copy2(self._png_path, dst)
            QMessageBox.information(self, "Saved", f"Diagram saved to:\n{dst}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{exc}")
