"""Main application window for the SQLite Client."""

import pathlib

from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QTabWidget, QApplication,
    QStatusBar, QMessageBox, QLabel, QDockWidget, QFontDialog,
    QTreeWidget, QTreeWidgetItem, QMenu,
)
from PyQt6.QtCore import Qt, QSettings, QThread, pyqtSignal, QTimer, QFileSystemWatcher
from PyQt6.QtGui import QAction, QFont

from core.database import DatabaseConnection
from core.docker_volume import (
    copy_to_volume, copy_from_volume, cleanup_local,
    DockerError, DockerVolumeInfo, get_volume_file_stat,
)
from core.worker import DatabaseWorker
from ui.query_editor import QueryEditorWidget
from ui.connection_dialog import ConnectionDialog
from ui.data_browser import DataBrowser, TableTab
from chat.chat_panel import ChatPanel
from chat.worker import ChatWorker
from chat.agent import (
    RouterChatAgent,
    DEFAULT_CHAT_MODEL,
    DEFAULT_SQL_MODEL,
)
from resources.style import THEMES


RECENT_FILES_MAX = 10


class MainWindow(QMainWindow):
    """Main application window coordinating all UI components."""

    _open_worker_db = pyqtSignal(str)
    _set_active_worker_db = pyqtSignal(str)
    _close_worker_db = pyqtSignal(str)
    _chat_set_db = pyqtSignal(str)
    _chat_set_models = pyqtSignal(str, str)
    _chat_load_history = pyqtSignal()
    _chat_close_store = pyqtSignal()

    def __init__(self):
        """Initialize the main window, menus, UI layout, and status bar."""
        super().__init__()
        self._databases: dict[str, DatabaseConnection] = {}
        self._active_path: str | None = None
        self._docker_sources: dict[str, DockerVolumeInfo] = {}
        self._fs_watcher = QFileSystemWatcher(self)
        self._fs_watcher.fileChanged.connect(self._on_db_file_changed)
        self._refresh_debounce = QTimer(self)
        self._refresh_debounce.setSingleShot(True)
        self._refresh_debounce.setInterval(500)
        self._refresh_debounce.timeout.connect(self._do_refresh_all)
        self._docker_poll_timer = QTimer(self)
        self._docker_poll_timer.setInterval(30000)
        self._docker_poll_timer.timeout.connect(self._on_docker_poll)
        self.setWindowTitle("SQLite Client")
        self.resize(1200, 800)

        self._settings = QSettings("sqlite-client", "sqlite-client")

        self._worker_thread = QThread()
        self._worker = DatabaseWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.start()

        self._open_worker_db.connect(self._worker.open_database)
        self._set_active_worker_db.connect(self._worker.set_active_database)
        self._close_worker_db.connect(self._worker.close_database)

        self._chat_model = self._settings.value(
            "chat_model", DEFAULT_CHAT_MODEL, type=str
        )
        self._sql_model = self._settings.value(
            "sql_model", DEFAULT_SQL_MODEL, type=str
        )
        self._chat_thread = QThread()
        self._chat_worker = ChatWorker(
            RouterChatAgent(
                chat_model=self._chat_model,
                sql_model=self._sql_model,
            )
        )
        self._chat_worker.moveToThread(self._chat_thread)
        self._chat_thread.start()

        self._chat_set_db.connect(self._chat_worker.set_database_path)
        self._chat_set_models.connect(self._chat_worker.set_models)
        self._chat_load_history.connect(self._chat_worker.load_history)
        self._chat_close_store.connect(self._chat_worker.close_store)

        self._setup_menu()
        self._setup_ui()
        self._setup_chat_dock()
        self._setup_status_bar()
        self._apply_saved_font()
        self._apply_saved_theme()

        self._chat_worker.history_loaded.connect(self._chat_panel.load_history)

        self._load_last_database()
        if not self._active_path:
            QTimer.singleShot(0, lambda: self._chat_set_db.emit(""))

    @property
    def _active_db(self) -> DatabaseConnection | None:
        if self._active_path and self._active_path in self._databases:
            return self._databases[self._active_path]
        return None

    def _setup_menu(self):
        """Construct the menu bar with File, View, and Help menus."""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        self._open_action = QAction("&Open Database...", self)
        self._open_action.setShortcut("Ctrl+O")
        self._open_action.triggered.connect(self._on_open_database)
        file_menu.addAction(self._open_action)

        self._close_action = QAction("&Close Active Database", self)
        self._close_action.setShortcut("Ctrl+W")
        self._close_action.triggered.connect(self._on_close_database)
        self._close_action.setEnabled(False)
        file_menu.addAction(self._close_action)

        file_menu.addSeparator()

        self._quit_action = QAction("&Quit", self)
        self._quit_action.setShortcut("Ctrl+Q")
        self._quit_action.triggered.connect(self.close)
        file_menu.addAction(self._quit_action)

        view_menu = menubar.addMenu("&View")
        self._font_action = QAction("&Font...", self)
        self._font_action.triggered.connect(self._on_choose_font)
        view_menu.addAction(self._font_action)
        view_menu.addSeparator()
        self._dark_mode_action = QAction("&Dark Mode", self)
        self._dark_mode_action.setCheckable(True)
        self._dark_mode_action.setChecked(
            self._settings.value("dark_mode", False, type=bool)
        )
        self._dark_mode_action.triggered.connect(self._on_toggle_theme)
        view_menu.addAction(self._dark_mode_action)
        view_menu.addSeparator()
        self._chat_action = QAction("&Chat", self)
        self._chat_action.setCheckable(True)
        self._chat_action.setChecked(True)
        self._chat_action.triggered.connect(self._on_toggle_chat)
        view_menu.addAction(self._chat_action)

        self._chat_model_action = QAction("Chat &Models...", self)
        self._chat_model_action.triggered.connect(self._on_configure_models)
        view_menu.addAction(self._chat_model_action)

        view_menu.addSeparator()
        self._er_action = QAction("ER &Diagram", self)
        self._er_action.setEnabled(False)
        self._er_action.triggered.connect(self._on_er_diagram)
        view_menu.addAction(self._er_action)

        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _setup_ui(self):
        """Build the central widget layout with schema tabs and tab area."""
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(self._splitter)

        self._schema_tree = QTreeWidget()
        self._schema_tree.setHeaderHidden(True)
        self._schema_tree.itemClicked.connect(self._on_schema_tree_clicked)
        self._schema_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._schema_tree.customContextMenuRequested.connect(self._on_schema_tree_context)
        self._splitter.addWidget(self._schema_tree)

        self._right_tabs = QTabWidget()
        self._right_tabs.setTabsClosable(True)
        self._right_tabs.tabCloseRequested.connect(self._on_right_tab_close)

        self._query_editor = QueryEditorWidget()
        self._query_editor.execute_query_requested.connect(
            self._worker.request_query
        )
        self._worker.query_finished.connect(
            self._query_editor._on_query_result
        )
        self._worker.edits_committed.connect(self._on_edits_committed)
        self._right_tabs.addTab(self._query_editor, "Query")

        self._splitter.addWidget(self._right_tabs)

        self._splitter.setSizes([250, 950])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

    def _setup_chat_dock(self):
        """Create the collapsible chat dock widget on the right side."""
        self._chat_dock = QDockWidget("Chat", self)
        self._chat_dock.setObjectName("chat_dock")
        self._chat_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self._chat_panel = ChatPanel()
        self._chat_dock.setWidget(self._chat_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._chat_dock)

        self._chat_panel.message_sent.connect(self._chat_worker.send_message)
        self._chat_panel.clear_requested.connect(self._chat_worker.clear_history)
        self._chat_worker.response_received.connect(
            self._chat_panel.append_reply
        )
        self._chat_dock.visibilityChanged.connect(self._chat_action.setChecked)

    def _on_toggle_chat(self, visible: bool) -> None:
        self._chat_dock.setVisible(visible)

    def _on_configure_models(self) -> None:
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("Chat Model Settings")
        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        chat_edit = QLineEdit(self._chat_model)
        chat_edit.setPlaceholderText("e.g. HuggingFaceH4/zephyr-7b-beta")
        form.addRow("Chat model:", chat_edit)

        sql_edit = QLineEdit(self._sql_model)
        sql_edit.setPlaceholderText("e.g. HuggingFaceH4/zephyr-7b-beta")
        form.addRow("SQL model:", sql_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        chat = chat_edit.text().strip()
        sql = sql_edit.text().strip()

        if not chat or not sql:
            return

        self._chat_model = chat
        self._sql_model = sql
        self._settings.setValue("chat_model", chat)
        self._settings.setValue("sql_model", sql)
        self._chat_set_models.emit(chat, sql)

    def _setup_status_bar(self):
        """Create the status bar with a connection state label."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("No database open")
        self._status_bar.addPermanentWidget(self._status_label)

    def _recent_files(self) -> list[str]:
        return self._settings.value("recent_files", [])

    def _add_recent_file(self, path: str) -> None:
        files = self._recent_files()
        if path in files:
            files.remove(path)
        files.insert(0, path)
        self._settings.setValue("recent_files", files[:RECENT_FILES_MAX])

    def _add_schema_tab(self, path: str) -> None:
        db_name = pathlib.Path(path).stem
        root = QTreeWidgetItem(self._schema_tree, [db_name])
        root.setData(0, Qt.ItemDataRole.UserRole, ("db_root", path))
        font = root.font(0)
        font.setBold(True)
        root.setFont(0, font)
        root.setExpanded(True)

        tables_node = QTreeWidgetItem(root, ["Tables"])
        tables_node.setData(0, Qt.ItemDataRole.UserRole, ("tables_node", path))
        tables_font = tables_node.font(0)
        tables_font.setBold(True)
        tables_node.setFont(0, tables_font)
        tables_node.setExpanded(True)

        db = self._databases.get(path)
        if db:
            for table_name in db.tables():
                item = QTreeWidgetItem(tables_node, [table_name])
                item.setData(0, Qt.ItemDataRole.UserRole, ("table", path, table_name))
                columns = db.table_schema(table_name)
                for col in columns:
                    col_text = f"{col.name}  {col.col_type}"
                    if col.primary_key:
                        col_text += " PK"
                    if col.notnull:
                        col_text += " NOT NULL"
                    if col.default_value is not None:
                        col_text += f" DEFAULT {col.default_value}"
                    col_item = QTreeWidgetItem(item, [col_text])
                    col_item.setData(0, Qt.ItemDataRole.UserRole, ("column", path, table_name, col.name))

            views_node = QTreeWidgetItem(root, ["Views"])
            views_node.setData(0, Qt.ItemDataRole.UserRole, ("views_node", path))
            views_node.setFont(0, tables_font)
            for view_name in db.views():
                item = QTreeWidgetItem(views_node, [view_name])
                item.setData(0, Qt.ItemDataRole.UserRole, ("view", path, view_name))

        self._schema_tree.setCurrentItem(root)

    def _connect_database(self, path: str, docker_source: tuple[str, str] | None = None) -> bool:
        try:
            db = DatabaseConnection()
            db.connect(path)
            self._databases[path] = db
            self._active_path = path
            self._add_schema_tab(path)
            self._open_worker_db.emit(path)
            self._chat_set_db.emit(path)
            self._query_editor.set_connected(True)
            self._close_action.setEnabled(True)
            self._er_action.setEnabled(True)
            self._start_watching(path)
            if docker_source is not None:
                vol, rpath = docker_source
                stat = get_volume_file_stat(vol, rpath)
                mtime, size = stat if stat else (0, 0)
                self._docker_sources[path] = DockerVolumeInfo(
                    volume_name=vol, remote_path=rpath, local_path=path,
                    last_mtime=mtime, last_size=size,
                )
                self._docker_poll_timer.start()
                self._status_label.setText(f"Connected: {vol}/{rpath}")
            else:
                self._add_recent_file(path)
                self._settings.setValue("last_database", path)
                self._settings.setValue("last_docker_source", "")
                self._status_label.setText(f"Connected: {path}")
            return True
        except Exception as e:
            self._databases.pop(path, None)
            self._schema_browsers.pop(path, None)
            QMessageBox.critical(self, "Error", f"Failed to open database:\n{e}")
            return False

    def _on_open_database(self):
        dlg = ConnectionDialog(recent_files=self._recent_files(), parent=self)
        if dlg.exec() != ConnectionDialog.DialogCode.Accepted:
            return
        path = dlg.selected_path
        if path:
            self._connect_database(path, docker_source=dlg.docker_source)

    def _load_last_database(self) -> None:
        path = self._settings.value("last_database", "")
        if not path or not pathlib.Path(path).exists():
            return
        docker_source_raw = self._settings.value("last_docker_source", "")
        if docker_source_raw:
            return
        try:
            self._connect_database(path)
        except Exception:
            pass

    def _start_watching(self, path: str) -> None:
        self._fs_watcher.addPath(path)
        wal_path = path + "-wal"
        if pathlib.Path(wal_path).exists():
            self._fs_watcher.addPath(wal_path)

    def _stop_watching(self, path: str | None = None) -> None:
        if path:
            self._fs_watcher.removePath(path)
            wal_path = path + "-wal"
            if pathlib.Path(wal_path).exists():
                self._fs_watcher.removePath(wal_path)
        else:
            paths = list(self._fs_watcher.files())
            if paths:
                self._fs_watcher.removePaths(paths)

    def _on_db_file_changed(self, path: str) -> None:
        self._refresh_debounce.start()

    def _do_refresh_all(self) -> None:
        for i in range(self._schema_tree.topLevelItemCount()):
            root = self._schema_tree.topLevelItem(i)
            data = root.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple) and data[0] == "db_root":
                path = data[1]
                self._rebuild_db_tree(path, root)
        for i in range(self._right_tabs.count()):
            w = self._right_tabs.widget(i)
            if hasattr(w, 'refresh'):
                w.refresh()

    def _rebuild_db_tree(self, path: str, root: QTreeWidgetItem) -> None:
        """Rebuild the tables/views children under a database root item."""
        db = self._databases.get(path)
        if not db or not db.is_connected:
            return
        while root.childCount() > 0:
            root.removeChild(root.child(0))

        tables_node = QTreeWidgetItem(root, ["Tables"])
        tables_node.setData(0, Qt.ItemDataRole.UserRole, ("tables_node", path))
        tables_font = tables_node.font(0)
        tables_font.setBold(True)
        tables_node.setFont(0, tables_font)
        tables_node.setExpanded(True)

        for table_name in db.tables():
            item = QTreeWidgetItem(tables_node, [table_name])
            item.setData(0, Qt.ItemDataRole.UserRole, ("table", path, table_name))
            columns = db.table_schema(table_name)
            for col in columns:
                col_text = f"{col.name}  {col.col_type}"
                if col.primary_key:
                    col_text += " PK"
                if col.notnull:
                    col_text += " NOT NULL"
                if col.default_value is not None:
                    col_text += f" DEFAULT {col.default_value}"
                col_item = QTreeWidgetItem(item, [col_text])
                col_item.setData(0, Qt.ItemDataRole.UserRole, ("column", path, table_name, col.name))

        views_node = QTreeWidgetItem(root, ["Views"])
        views_node.setData(0, Qt.ItemDataRole.UserRole, ("views_node", path))
        views_node.setFont(0, tables_font)
        for view_name in db.views():
            item = QTreeWidgetItem(views_node, [view_name])
            item.setData(0, Qt.ItemDataRole.UserRole, ("view", path, view_name))

    def _on_docker_poll(self):
        for local_path, info in list(self._docker_sources.items()):
            try:
                stat = get_volume_file_stat(info.volume_name, info.remote_path)
                if stat is None:
                    continue
                mtime, size = stat
                if mtime == info.last_mtime and size == info.last_size:
                    continue
                info.last_mtime = mtime
                info.last_size = size
                self._stop_watching(local_path)
                db = self._databases.get(local_path)
                if db:
                    db.close()
                self._close_worker_db.emit(local_path)
                copy_from_volume(info.volume_name, info.remote_path)
                if local_path in self._databases:
                    self._databases[local_path].connect(local_path)
                self._start_watching(local_path)
                self._open_worker_db.emit(local_path)
                if self._active_path == local_path:
                    self._set_active_worker_db.emit(local_path)
                self._do_refresh_all()
            except DockerError as e:
                self._status_label.setText(f"Docker poll error: {e}")
            except Exception as e:
                self._status_label.setText(f"Poll error: {e}")

    def _on_schema_tree_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple):
            return
        kind = data[0]
        if kind == "table":
            path, table_name = data[1], data[2]
            self._active_path = path
            self._on_table_selected(path, table_name)
        elif kind == "view":
            path, view_name = data[1], data[2]
            self._on_view_selected(path, view_name)
        elif kind == "db_root":
            path = data[1]
            self._active_path = path
            self._set_active_worker_db.emit(path)
            self._chat_set_db.emit(path)
            db_label = self._docker_sources[path].volume_name if path in self._docker_sources else path
            self._status_label.setText(f"Active: {db_label}")
            self._close_action.setEnabled(True)

    def _on_schema_tree_context(self, pos):
        item = self._schema_tree.itemAt(pos)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple):
            return
        path = None
        if data[0] in ("db_root", "tables_node", "views_node"):
            path = data[1]
        elif data[0] in ("table", "view"):
            path = data[1]
        elif data[0] == "column":
            path = data[2]
        if path is None:
            return

        menu = QMenu(self)
        close_act = menu.addAction(f"Close {pathlib.Path(path).stem}")
        close_act.triggered.connect(lambda: self._close_database_by_path(path))
        if data[0] == "table":
            menu.addSeparator()
            er_act = menu.addAction(f"ER Diagram — {data[2]}")
            er_act.triggered.connect(lambda: self._on_er_diagram_for_table(path, data[2]))
        menu.exec(self._schema_tree.mapToGlobal(pos))

    def _close_database_by_path(self, path: str) -> None:
        was_active = path == self._active_path
        self._stop_watching(path)
        self._docker_sources.pop(path, None)
        self._close_worker_db.emit(path)
        db = self._databases.pop(path, None)
        if db:
            db.close()
        for i in range(self._schema_tree.topLevelItemCount()):
            root = self._schema_tree.topLevelItem(i)
            data = root.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, tuple) and data[0] == "db_root" and data[1] == path:
                self._schema_tree.takeTopLevelItem(i)
                break
        for i in range(self._right_tabs.count() - 1, 0, -1):
            w = self._right_tabs.widget(i)
            if w is not self._query_editor:
                self._right_tabs.removeTab(i)
        if was_active:
            if self._databases:
                first_path = next(iter(self._databases))
                self._active_path = first_path
                self._set_active_worker_db.emit(first_path)
                self._chat_set_db.emit(first_path)
            else:
                self._active_path = None
                self._query_editor.set_connected(False)
                self._close_action.setEnabled(False)
                self._er_action.setEnabled(False)
                self._status_label.setText("No database open")
                self._chat_set_db.emit("")
        if not self._docker_sources:
            self._docker_poll_timer.stop()

    def _on_close_database(self):
        if self._active_path:
            self._close_database_by_path(self._active_path)

    def _sync_docker_back(self) -> None:
        path = self._active_path
        if not path or path not in self._docker_sources:
            return
        info = self._docker_sources[path]
        db = self._active_db
        if not db:
            return
        try:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            copy_to_volume(info.volume_name, info.remote_path, info.local_path)
        except Exception as e:
            QMessageBox.critical(
                self, "Docker Sync Error",
                f"Failed to save back to Docker volume:\n{e}\n\n"
                f"Your changes are still in: {info.local_path}",
            )

    def _maybe_sync_docker_back(self) -> None:
        for path, info in list(self._docker_sources.items()):
            reply = QMessageBox.question(
                self, "Sync to Docker Volume",
                f"Save changes back to Docker volume?\n\n{info.volume_name}/{info.remote_path}",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                pass
            elif reply == QMessageBox.StandardButton.Yes:
                old_path = self._active_path
                self._active_path = path
                self._sync_docker_back()
                self._active_path = old_path
            cleanup_local(info.volume_name, info.local_path)
            self._docker_sources.pop(path, None)
        self._docker_poll_timer.stop()

    def _on_edits_committed(self, table_name: str) -> None:
        self._sync_docker_back()

    def _on_er_diagram(self):
        from ui.er_dialog import ErDialog
        db = self._active_db
        if db:
            dlg = ErDialog(self, db_conn=db)
            dlg.exec()

    def _on_er_diagram_for_table(self, db_path: str, table_name: str):
        from ui.er_dialog import ErDialog
        db = self._databases.get(db_path)
        if db:
            dlg = ErDialog(self, db_conn=db, table_name=table_name)
            dlg.exec()

    def _on_table_selected(self, db_path: str, table_name: str) -> None:
        self._open_data_browser(db_path, table_name)

    def _on_view_selected(self, db_path: str, view_name: str) -> None:
        tab = self._query_editor.add_tab()
        tab.editor.setPlainText(f"SELECT * FROM \"{view_name}\"\n")

    def _open_data_browser(self, db_path: str, table_name: str) -> None:
        for i in range(self._right_tabs.count()):
            w = self._right_tabs.widget(i)
            if hasattr(w, '_table_name') and w._table_name == table_name:
                self._right_tabs.setCurrentIndex(i)
                return
        db = self._databases.get(db_path)
        if not db:
            return
        columns = db.table_schema(table_name)
        total_count = db.table_row_count(table_name)
        ddl = db.table_create_sql(table_name) or ""
        tab = TableTab(self._worker, table_name, columns, total_count, ddl)
        idx = self._right_tabs.addTab(tab, table_name)
        self._right_tabs.setCurrentIndex(idx)

    def _on_right_tab_close(self, index: int) -> None:
        w = self._right_tabs.widget(index)
        if w is self._query_editor:
            return
        self._right_tabs.removeTab(index)

    def _set_theme(self, dark: bool) -> None:
        app = QApplication.instance()
        if not app:
            return
        ss = THEMES["dark" if dark else "light"]
        font = app.font()
        font_rule = f"font-family: '{font.family()}'; font-size: {font.pointSize()}pt;"
        ss = f"* {{{font_rule}}}\n\n{ss}"
        app.setStyleSheet(ss)

    def _apply_saved_theme(self) -> None:
        dark = self._settings.value("dark_mode", False, type=bool)
        self._dark_mode_action.setChecked(dark)
        self._set_theme(dark)

    def _on_toggle_theme(self) -> None:
        dark = self._dark_mode_action.isChecked()
        self._set_theme(dark)
        self._settings.setValue("dark_mode", dark)

    def _on_choose_font(self) -> None:
        current = QFont(
            self._settings.value("font_family", "", type=str) or QApplication.font().family(),
            self._settings.value("font_size", 10, type=int),
        )
        font, ok = QFontDialog.getFont(current, self, "Choose Application Font")
        if not ok:
            return
        self._settings.setValue("font_family", font.family())
        self._settings.setValue("font_size", font.pointSize())
        app = QApplication.instance()
        app.setFont(font)
        dark = self._settings.value("dark_mode", False, type=bool)
        self._set_theme(dark)

    def _apply_saved_font(self) -> None:
        family = self._settings.value("font_family", "", type=str)
        size = self._settings.value("font_size", 0, type=int)
        if not family or not size:
            return
        app = QApplication.instance()
        font = QFont(family, size)
        app.setFont(font)

    def _on_about(self):
        QMessageBox.about(
            self,
            "About SQLite Client",
            "SQLite Client v0.1.0\n\nA PyQt6-based SQLite database browser.",
        )

    def closeEvent(self, event):
        self._stop_watching()
        self._docker_poll_timer.stop()
        self._maybe_sync_docker_back()
        self._worker.close_all()
        self._worker_thread.quit()
        self._worker_thread.wait(3000)
        self._chat_close_store.emit()
        self._chat_thread.quit()
        self._chat_thread.wait(3000)
        for db in self._databases.values():
            db.close()
        self._databases.clear()
        super().closeEvent(event)
