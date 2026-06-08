"""Background worker for non-blocking database operations.

Provides :class:`DatabaseWorker`, a :class:`QObject` designed to run on a
dedicated :class:`QThread`.  All database reads and writes execute on the
worker thread so the GUI stays responsive during long queries.
"""

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from core.database import DatabaseConnection, ColumnInfo, quote_identifier
from core.query_executor import QueryExecutor, QueryResult


class DatabaseWorker(QObject):
    """Performs database operations on a background thread.

    Supports multiple concurrent database connections.  Each connection is
    identified by its resolved file path.  Only the *active* connection
    is used for query / data-browser / edit operations.

    Create one, call :meth:`moveToThread`, start the thread, then
    connect signals to its ``request_*`` slots and receive results via
    the ``*_finished`` / ``error`` signals.

    Signals:
        query_finished: Emitted with a :class:`QueryResult` after SQL
            execution.
        data_page_finished: Emitted with ``(table_name, columns, rows,
            total_count)`` after a page load completes.
        edits_committed: Emitted with the table name after UPDATE batch
            + commit.
        row_added: Emitted with the table name after INSERT + commit.
        rows_deleted: Emitted with the table name after DELETE + commit.
        error: Emitted with an error message string.
    """

    query_finished = pyqtSignal(object)
    data_page_finished = pyqtSignal(str, list, list, int)
    edits_committed = pyqtSignal(str)
    row_added = pyqtSignal(str)
    rows_deleted = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connections: dict[str, DatabaseConnection] = {}
        self._active_path: str | None = None

    # ── connection management ──────────────────────────────────────────

    @property
    def _db(self) -> DatabaseConnection:
        if self._active_path is None or self._active_path not in self._connections:
            raise RuntimeError("No active database connection")
        return self._connections[self._active_path]

    def open_database(self, path: str) -> None:
        if path not in self._connections:
            db = DatabaseConnection()
            db.connect(path)
            self._connections[path] = db
        self._active_path = path

    def set_active_database(self, path: str) -> None:
        if path in self._connections:
            self._active_path = path

    def close_database(self, path: str) -> None:
        if path in self._connections:
            self._connections[path].close()
            del self._connections[path]
        if self._active_path == path:
            self._active_path = next(iter(self._connections)) if self._connections else None

    def close_all(self) -> None:
        for db in self._connections.values():
            db.close()
        self._connections.clear()
        self._active_path = None

    # ── query-editor execution ──────────────────────────────────────────

    def request_query(self, sql: str) -> None:
        executor = QueryExecutor(self._db)
        result = executor.execute(sql)
        self.query_finished.emit(result)

    # ── data-browser page loading ───────────────────────────────────────

    def request_data_page(
        self,
        table_name: str,
        page: int,
        page_size: int,
        search: str = "",
    ) -> None:
        where = self._build_filter(table_name, search) if search else ""
        try:
            if where:
                row = self._db.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(table_name)}{where}"
                )
                total = row[0][0] if row else 0
            else:
                total = self._db.table_row_count(table_name)

            offset = page * page_size
            columns, rows = self._db.execute_with_results(
                f"SELECT * FROM {quote_identifier(table_name)}{where}"
                f" LIMIT {page_size} OFFSET {offset}",
            )
            self.data_page_finished.emit(table_name, columns, rows, total)
        except Exception as e:
            self.error.emit(str(e))

    # ── batch commit (inline edits) ─────────────────────────────────────

    def request_commit(
        self,
        table_name: str,
        columns: list[ColumnInfo],
        pending: list[tuple],
    ) -> None:
        pk_cols = [c for c in columns if c.primary_key]
        if not pk_cols:
            return
        pk_name = pk_cols[0].name
        table = quote_identifier(table_name)
        pk_q = quote_identifier(pk_name)
        try:
            for pk_val, col_name, new_val in pending:
                self._db.execute(
                    f"UPDATE {table} SET {quote_identifier(col_name)} = ? WHERE {pk_q} = ?",
                    (new_val, pk_val),
                )
            self._db.commit()
            self.edits_committed.emit(table_name)
        except Exception as e:
            self.error.emit(str(e))

    # ── add row ─────────────────────────────────────────────────────────

    @staticmethod
    def _default_for_col(c: ColumnInfo) -> Any:
        if c.notnull and c.default_value is None:
            t = c.col_type.upper().split("(")[0].strip()
            if t in ("INTEGER", "INT", "SMALLINT", "BIGINT", "TINYINT", "BOOLEAN", "BOOL"):
                return 0
            if t in ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL"):
                return 0.0
            if t == "BLOB":
                return b""
            return ""
        return None

    def request_add_row(
        self,
        table_name: str,
        columns: list[ColumnInfo],
    ) -> None:
        included: list[ColumnInfo] = []
        values: list[Any] = []
        for c in columns:
            if c.default_value is not None:
                continue
            included.append(c)
            values.append(self._default_for_col(c))
        if not included:
            sql = f"INSERT INTO {quote_identifier(table_name)} DEFAULT VALUES"
            params = ()
        else:
            col_list = ", ".join(quote_identifier(c.name) for c in included)
            placeholders = ", ".join("?" for _ in included)
            sql = f"INSERT INTO {quote_identifier(table_name)} ({col_list}) VALUES ({placeholders})"
            params = tuple(values)
        try:
            self._db.execute(sql, params)
            self._db.commit()
            self.row_added.emit(table_name)
        except Exception as e:
            self.error.emit(str(e))

    # ── delete rows ─────────────────────────────────────────────────────

    def request_delete_rows(
        self,
        table_name: str,
        pk_name: str,
        pk_values: list,
    ) -> None:
        table = quote_identifier(table_name)
        pk_q = quote_identifier(pk_name)
        try:
            for pk_val in pk_values:
                self._db.execute(
                    f"DELETE FROM {table} WHERE {pk_q} = ?",
                    (pk_val,),
                )
            self._db.commit()
            self.rows_deleted.emit(table_name)
        except Exception as e:
            self.error.emit(str(e))

    # ── helpers ─────────────────────────────────────────────────────────

    def _build_filter(self, table_name: str, search: str) -> str:
        clauses = []
        for col in self._db.table_schema(table_name):
            escaped = search.replace("'", "''")
            clauses.append(f"{quote_identifier(col.name)} LIKE '%{escaped}%'")
        return " WHERE " + " OR ".join(clauses)
