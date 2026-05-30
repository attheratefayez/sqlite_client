import sqlite3
import pathlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnInfo:
    cid: int
    name: str
    col_type: str
    notnull: bool
    default_value: Any
    primary_key: bool


@dataclass
class ForeignKeyInfo:
    id: int
    seq: int
    table: str
    from_col: str
    to_col: str
    on_update: str
    on_delete: str
    match: str


@dataclass
class IndexInfo:
    name: str
    unique: bool
    columns: list[str]


@dataclass
class TableRowCount:
    table_name: str
    row_count: int


class DatabaseError(Exception):
    pass


class DatabaseConnection:
    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._path: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    @property
    def path(self) -> str | None:
        return self._path

    def connect(self, path: str) -> None:
        resolved = pathlib.Path(path).resolve()
        self._conn = sqlite3.connect(str(resolved))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._path = str(resolved)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._path = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DatabaseError("No database connection open")
        return self._conn

    def tables(self) -> list[str]:
        conn = self._require_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def views(self) -> list[str]:
        conn = self._require_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def indexes(self, table_name: str) -> list[IndexInfo]:
        conn = self._require_connection()
        index_list = conn.execute(
            f"PRAGMA index_list({self._quote(table_name)})"
        ).fetchall()
        result: list[IndexInfo] = []
        for idx in index_list:
            name = idx[1]
            unique = bool(idx[2])
            col_rows = conn.execute(
                f"PRAGMA index_info({self._quote(name)})"
            ).fetchall()
            columns = [row[2] for row in col_rows]
            result.append(IndexInfo(name=name, unique=unique, columns=columns))
        return result

    def table_schema(self, table_name: str) -> list[ColumnInfo]:
        conn = self._require_connection()
        rows = conn.execute(f"PRAGMA table_info({self._quote(table_name)})").fetchall()
        return [
            ColumnInfo(
                cid=row[0],
                name=row[1],
                col_type=row[2],
                notnull=bool(row[3]),
                default_value=row[4],
                primary_key=bool(row[5]),
            )
            for row in rows
        ]

    def foreign_keys(self, table_name: str) -> list[ForeignKeyInfo]:
        conn = self._require_connection()
        rows = conn.execute(
            f"PRAGMA foreign_key_list({self._quote(table_name)})"
        ).fetchall()
        return [
            ForeignKeyInfo(
                id=row[0],
                seq=row[1],
                table=row[2],
                from_col=row[3],
                to_col=row[4],
                on_update=row[5],
                on_delete=row[6],
                match=row[7],
            )
            for row in rows
        ]

    def table_row_count(self, table_name: str) -> int:
        conn = self._require_connection()
        row = conn.execute(
            f"SELECT COUNT(*) FROM {self._quote(table_name)}"
        ).fetchone()
        return row[0] if row else 0

    def execute(self, sql: str) -> list[tuple[str]]:
        conn = self._require_connection()
        cursor = conn.execute(sql)
        if cursor.description:
            return cursor.fetchall()
        return []

    def execute_with_results(self, sql: str) -> tuple[list[str], list[tuple]]:
        conn = self._require_connection()
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows

    def execute_script(self, sql: str) -> None:
        conn = self._require_connection()
        conn.executescript(sql)

    def commit(self) -> None:
        conn = self._require_connection()
        conn.commit()

    def rollback(self) -> None:
        conn = self._require_connection()
        conn.rollback()

    @staticmethod
    def _quote(name: str) -> str:
        return f'"{name}"'
