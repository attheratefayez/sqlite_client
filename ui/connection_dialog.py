import pathlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt


RECENT_FILES_SETTINGS_KEY = "recent_databases"


class ConnectionDialog(QDialog):
    def __init__(self, recent_files: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Database")
        self.resize(500, 400)
        self._selected_path: str | None = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Open existing database:"))

        btn_layout = QHBoxLayout()
        self._open_btn = QPushButton("Browse for Database...")
        self._open_btn.clicked.connect(self._browse_open)
        btn_layout.addWidget(self._open_btn)

        self._new_btn = QPushButton("Create New Database...")
        self._new_btn.clicked.connect(self._browse_create)
        btn_layout.addWidget(self._new_btn)
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("Recent databases:"))
        self._recent_list = QListWidget()
        self._recent_list.itemDoubleClicked.connect(self._on_recent_clicked)
        self._populate_recent(recent_files or [])
        layout.addWidget(self._recent_list)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_recent(self, recent_files: list[str]) -> None:
        self._recent_list.clear()
        for path in recent_files:
            p = pathlib.Path(path)
            if p.exists():
                item = QListWidgetItem(f"{p.name}  —  {p.parent}")
                item.setData(Qt.ItemDataRole.UserRole, path)
                self._recent_list.addItem(item)

    def _browse_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Database", "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if path:
            self._selected_path = path
            self.accept()

    def _browse_create(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Create Database", "",
            "SQLite Database (*.db);;All Files (*)"
        )
        if path:
            self._selected_path = path
            self.accept()

    def _on_recent_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._selected_path = path
            self.accept()

    @property
    def selected_path(self) -> str | None:
        return self._selected_path
