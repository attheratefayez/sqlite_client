"""Background worker for non-blocking database operations.

Provides :class:`DatabaseWorker`, a :class:`QObject` designed to run on a
dedicated :class:`QThread`.  All database reads and writes execute on the
worker thread so the GUI stays responsive during long queries.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from core.database import DatabaseConnection, ColumnInfo
from core.query_executor import QueryExecutor, QueryResult


def _quoted(name: str) -> str:
    return f'"{name}"'


class DatabaseWorker(QObject):
    """Performs database operations on a background thread.

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
        self._db = DatabaseConnection()

    # ── lifecycle ────────────────────────────────────────────────────────

    def open_database(self, path: str) -> None:
        self._db.close()
        self._db.connect(path)

    def close_database(self) -> None:
        self._db.close()

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
                    f"SELECT COUNT(*) FROM {_quoted(table_name)}{where}"
                )
                total = row[0][0] if row else 0
            else:
                total = self._db.table_row_count(table_name)

            offset = page * page_size
            columns, rows = self._db.execute_with_results(
                f"SELECT * FROM {_quoted(table_name)}{where}"
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
        table = _quoted(table_name)
        pk_q = _quoted(pk_name)
        try:
            for pk_val, col_name, new_val in pending:
                self._db.execute(
                    f"UPDATE {table} SET {_quoted(col_name)} = ? WHERE {pk_q} = ?",
                    (new_val, pk_val),
                )
            self._db.commit()
            self.edits_committed.emit(table_name)
        except Exception as e:
            self.error.emit(str(e))

    # ── add row ─────────────────────────────────────────────────────────

    def request_add_row(
        self,
        table_name: str,
        columns: list[ColumnInfo],
    ) -> None:
        cols = ", ".join(_quoted(c.name) for c in columns)
        placeholders = ", ".join("?" for _ in columns)
        values = [None for _ in columns]
        try:
            self._db.execute(
                f"INSERT INTO {_quoted(table_name)} ({cols}) VALUES ({placeholders})",
                tuple(values),
            )
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
        table = _quoted(table_name)
        pk_q = _quoted(pk_name)
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
            clauses.append(f"{_quoted(col.name)} LIKE '%{escaped}%'")
        return " WHERE " + " OR ".join(clauses)
