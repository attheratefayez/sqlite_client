"""Dialog for browsing Docker volumes and selecting a SQLite database.

Provides the :class:`DockerVolumeDialog` which lists available Docker
volumes and lets the user navigate the directory tree within a volume
to pick a ``.db`` / ``.sqlite`` / ``.sqlite3`` file.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QTreeView, QSplitter,
    QMessageBox, QDialogButtonBox, QWidget, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QAbstractItemModel, QModelIndex, QObject
from PyQt6.QtGui import QFont

from core.docker_volume import (
    list_volumes,
    list_directory_tree,
    DockerError,
)


class _VolumeTreeModel(QAbstractItemModel):
    """A tree model built from a list of ``(depth, path, is_dir)`` tuples."""

    def __init__(self, entries: list[tuple[int, str, bool]], parent: QObject | None = None):
        super().__init__(parent)
        self._nodes: list[_Node] = []
        self._build(entries)

    def _build(self, entries: list[tuple[int, str, bool]]) -> None:
        self._nodes = []
        path_map: dict[str, _Node] = {}
        root = _Node(0, "", True, None)
        self._nodes.append(root)
        path_map[""] = root

        for depth, path, is_dir in entries:
            if depth == 0:
                continue
            node = _Node(depth, path, is_dir, path_map.get("/".join(path.split("/")[:-1])))
            path_map[path] = node
            self._nodes.append(node)

    def _node_for_path(self, path: str) -> _Node | None:
        for n in self._nodes:
            if n.path == path:
                return n
        return None

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = parent.internalPointer() if parent.isValid() else self._nodes[0]
        children = [n for n in self._nodes if n.parent is parent_node]
        if 0 <= row < len(children):
            return self.createIndex(row, column, children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: _Node = index.internalPointer()
        if node.parent is None or node.parent is self._nodes[0]:
            return QModelIndex()
        grandparent = node.parent.parent
        if grandparent is None:
            return QModelIndex()
        siblings = [n for n in self._nodes if n.parent is grandparent]
        try:
            row = siblings.index(node.parent)
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, 0, node.parent)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        parent_node = parent.internalPointer() if parent.isValid() else self._nodes[0]
        return len([n for n in self._nodes if n.parent is parent_node])

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node: _Node = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            if node.path == "":
                return "/"
            return node.path.rsplit("/", 1)[-1]
        if role == Qt.ItemDataRole.DecorationRole:
            return None
        if role == Qt.ItemDataRole.UserRole:
            return node.path
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node: _Node = index.internalPointer()
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if node.is_dir:
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        return self.rowCount(parent) > 0

    def _all_db_paths(self) -> list[str]:
        return [
            n.path for n in self._nodes
            if not n.is_dir and any(
                n.path.lower().endswith(e) for e in (".db", ".sqlite", ".sqlite3")
            )
        ]


class _Node:
    __slots__ = ("depth", "path", "is_dir", "parent")

    def __init__(self, depth: int, path: str, is_dir: bool, parent: _Node | None):
        self.depth = depth
        self.path = path
        self.is_dir = is_dir
        self.parent = parent


class DockerVolumeDialog(QDialog):
    """Modal dialog for selecting a SQLite database from a Docker volume.

    Attributes:
        volume_name: The selected Docker volume, or None.
        remote_path: The selected path within the volume, or None.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Open Database from Docker Volume")
        self.resize(700, 500)

        self.volume_name: str | None = None
        self.remote_path: str | None = None

        layout = QVBoxLayout(self)

        # Volume list (left) + tree view (right)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Docker Volumes:"))
        self._volume_list = QListWidget()
        self._volume_list.setMinimumWidth(180)
        self._volume_list.currentItemChanged.connect(self._on_volume_changed)
        left_layout.addWidget(self._volume_list)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._populate_volumes)
        left_layout.addWidget(refresh_btn)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self._status_label = QLabel("Select a Docker volume to browse")
        right_layout.addWidget(self._status_label)
        self._tree_view = QTreeView()
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree_view.selectionModel()
        self._tree_view.clicked.connect(self._on_tree_clicked)
        self._tree_view.setAnimated(True)
        self._tree_view.setIndentation(16)
        right_layout.addWidget(self._tree_view)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self._open_btn = QPushButton("Open")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open)
        btn_layout.addWidget(self._open_btn)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._populate_volumes()

    def _populate_volumes(self) -> None:
        self._volume_list.clear()
        self._tree_view.setModel(None)
        self._status_label.setText("Select a Docker volume to browse")
        self._open_btn.setEnabled(False)
        try:
            volumes = list_volumes()
            if not volumes:
                self._status_label.setText("No Docker volumes found")
                return
            for vol in volumes:
                item = QListWidgetItem(vol)
                self._volume_list.addItem(item)
        except DockerError as e:
            QMessageBox.critical(self, "Docker Error", str(e))

    def _on_volume_changed(self, current: QListWidgetItem, previous) -> None:
        if not current:
            return
        vol = current.text()
        self._status_label.setText(f"Loading {vol}...")
        self._tree_view.setModel(None)
        self._open_btn.setEnabled(False)
        try:
            entries = list_directory_tree(vol)
            model = _VolumeTreeModel(entries, self)
            self._tree_view.setModel(model)
            self._tree_view.expandToDepth(0)
            db_count = len(model._all_db_paths())
            self._status_label.setText(
                f"{vol}  —  {db_count} database file(s)"
            )
        except DockerError as e:
            self._status_label.setText(f"Error: {e}")
        self.volume_name = vol

    def _on_tree_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            self._open_btn.setEnabled(False)
            return
        node_path = index.data(Qt.ItemDataRole.UserRole)
        if node_path:
            is_db = any(
                node_path.lower().endswith(e)
                for e in (".db", ".sqlite", ".sqlite3")
            )
            self._open_btn.setEnabled(is_db)
            if is_db:
                self.remote_path = node_path
                self._status_label.setText(f"Selected: {node_path}")

    def _on_open(self) -> None:
        if self.volume_name and self.remote_path:
            self.accept()
