"""Tree widget for browsing database schema objects.

Provides a :class:`SchemaBrowser` widget that displays tables and views
in a tree structure, with column details shown as child items.
"""

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu
from PyQt6.QtCore import pyqtSignal, Qt
from core.database import DatabaseConnection


class SchemaBrowser(QTreeWidget):
    """A tree widget that displays database tables, views, and their columns.

    Signals:
        table_selected: Emitted with the table name when a table item is clicked.
        view_selected: Emitted with the view name when a view item is clicked.
    """

    table_selected = pyqtSignal(str)
    view_selected = pyqtSignal(str)
    er_diagram_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize the schema browser widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._db: DatabaseConnection | None = None
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.itemClicked.connect(self._on_item_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_database(self, db: DatabaseConnection | None) -> None:
        """Set the database connection and refresh the tree.

        Passing None clears the tree.

        Args:
            db: A DatabaseConnection instance, or None to clear.
        """
        self._db = db
        self.clear()
        if db is None:
            return
        self._refresh()

    def _refresh(self) -> None:
        """Rebuild the tree from the current database schema."""
        if self._db is None:
            return
        self.clear()

        tables_root = QTreeWidgetItem(self, ["Tables"])
        tables_root.setData(0, Qt.ItemDataRole.UserRole, "tables_root")
        tables_root.setExpanded(True)
        font = tables_root.font(0)
        font.setBold(True)
        tables_root.setFont(0, font)

        for table_name in self._db.tables():
            table_item = QTreeWidgetItem(tables_root, [table_name])
            table_item.setData(0, Qt.ItemDataRole.UserRole, ("table", table_name))
            columns = self._db.table_schema(table_name)
            for col in columns:
                col_text = f"{col.name}  {col.col_type}"
                if col.primary_key:
                    col_text += " PK"
                if col.notnull:
                    col_text += " NOT NULL"
                if col.default_value is not None:
                    col_text += f" DEFAULT {col.default_value}"
                col_item = QTreeWidgetItem(table_item, [col_text])
                col_item.setData(0, Qt.ItemDataRole.UserRole, ("column", table_name, col.name))

        views_root = QTreeWidgetItem(self, ["Views"])
        views_root.setData(0, Qt.ItemDataRole.UserRole, "views_root")
        views_root.setExpanded(True)
        views_root.setFont(0, font)

        for view_name in self._db.views():
            view_item = QTreeWidgetItem(views_root, [view_name])
            view_item.setData(0, Qt.ItemDataRole.UserRole, ("view", view_name))

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple) or data[0] != "table":
            return
        table_name = data[1]
        menu = QMenu(self)
        action = menu.addAction(f"Show ER Diagram — {table_name}")
        action.triggered.connect(lambda: self.er_diagram_requested.emit(table_name))
        menu.exec(self.mapToGlobal(pos))

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle item clicks and emit the appropriate signal.

        Args:
            item: The clicked tree widget item.
            column: The column index that was clicked.
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(data, tuple):
            kind = data[0]
            if kind == "table":
                self.table_selected.emit(data[1])
            elif kind == "view":
                self.view_selected.emit(data[1])
