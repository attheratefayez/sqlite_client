"""Dialog for opening or creating a SQLite database file.

Provides the :class:`ConnectionDialog` with options to browse for an
existing file, create a new database, or select from recently opened files.
"""

import pathlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt

from core.docker_volume import copy_from_volume, DockerError
from ui.docker_volume_dialog import DockerVolumeDialog


class ConnectionDialog(QDialog):
    """A modal dialog for selecting or creating a SQLite database.

    Attributes:
        _selected_path: The file path chosen by the user, or None.
        _docker_source: Tuple of ``(volume_name, remote_path)`` if opened
            from a Docker volume, or None.
    """

    def __init__(self, recent_files: list[str] | None = None, parent=None):
        """Initialize the dialog with optional recent file list.

        Args:
            recent_files: List of file paths to display as recent databases.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Open Database")
        self.resize(500, 400)
        self._selected_path: str | None = None
        self._docker_source: tuple[str, str] | None = None

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

        docker_btn_layout = QHBoxLayout()
        self._docker_btn = QPushButton("From Docker Volume...")
        self._docker_btn.clicked.connect(self._browse_docker_volume)
        docker_btn_layout.addWidget(self._docker_btn)
        docker_btn_layout.addStretch()
        layout.addLayout(docker_btn_layout)

        layout.addWidget(QLabel("Recent databases:"))
        self._recent_list = QListWidget()
        self._recent_list.itemDoubleClicked.connect(self._on_recent_clicked)
        self._populate_recent(recent_files or [])
        layout.addWidget(self._recent_list)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_recent(self, recent_files: list[str]) -> None:
        """Populate the recent files list widget from a list of paths.

        Only paths that currently exist on disk are shown.

        Args:
            recent_files: List of file path strings.
        """
        self._recent_list.clear()
        for path in recent_files:
            p = pathlib.Path(path)
            if p.exists():
                item = QListWidgetItem(f"{p.name}  —  {p.parent}")
                item.setData(Qt.ItemDataRole.UserRole, path)
                self._recent_list.addItem(item)

    def _browse_open(self) -> None:
        """Open a file dialog to select an existing database file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Database", "",
            "SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)"
        )
        if path:
            self._selected_path = path
            self.accept()

    def _browse_create(self) -> None:
        """Open a save dialog to create a new database file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Create Database", "",
            "SQLite Database (*.db);;All Files (*)"
        )
        if path:
            self._selected_path = path
            self.accept()

    def _on_recent_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on a recent file list item.

        Args:
            item: The clicked list widget item.
        """
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._selected_path = path
            self.accept()

    def _browse_docker_volume(self) -> None:
        """Open the Docker volume browser dialog."""
        dlg = DockerVolumeDialog(self)
        if dlg.exec() != DockerVolumeDialog.DialogCode.Accepted:
            return
        if dlg.volume_name and dlg.remote_path:
            try:
                local_path = copy_from_volume(dlg.volume_name, dlg.remote_path)
                self._selected_path = local_path
                self._docker_source = (dlg.volume_name, dlg.remote_path)
                self.accept()
            except DockerError as e:
                QMessageBox.critical(
                    self, "Docker Error",
                    f"Failed to copy database from Docker volume:\n{e}",
                )

    @property
    def selected_path(self) -> str | None:
        """str or None: The file path chosen by the user."""
        return self._selected_path

    @property
    def docker_source(self) -> tuple[str, str] | None:
        """tuple of (volume_name, remote_path) or None if not from Docker."""
        return self._docker_source
