"""Database connection and schema metadata for SQLite databases.

This module provides data classes for representing database schema objects
(columns, foreign keys, indexes, table row counts) and the DatabaseConnection
class for interacting with SQLite database files.
"""

import sqlite3
import pathlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnInfo:
    """Metadata for a single column in a database table.

    Attributes:
        cid: Column index within the table.
        name: Column name.
        col_type: SQL type name (e.g. INTEGER, TEXT).
        notnull: Whether the column has a NOT NULL constraint.
        default_value: Default value expression, or None.
        primary_key: Whether the column is part of the primary key.
    """
    cid: int
    name: str
    col_type: str
    notnull: bool
    default_value: Any
    primary_key: bool


@dataclass
class ForeignKeyInfo:
    """Metadata for a single foreign key constraint.

    Attributes:
        id: Constraint identifier within the table.
        seq: Sequence number within the constraint.
        table: Referenced table name.
        from_col: Source column name in this table.
        to_col: Target column name in the referenced table.
        on_update: ON UPDATE action (e.g. CASCADE, SET NULL).
        on_delete: ON DELETE action.
        match: MATCH clause value.
    """
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
    """Metadata for a database index.

    Attributes:
        name: Index name.
        unique: Whether the index enforces uniqueness.
        columns: List of column names in the index.
    """
    name: str
    unique: bool
    columns: list[str]


@dataclass
class TableRowCount:
    """Row count for a single database table.

    Attributes:
        table_name: Name of the table.
        row_count: Number of rows in the table.
    """
    table_name: str
    row_count: int


class DatabaseError(Exception):
    """Exception raised for database connection or query errors."""
    pass


class DatabaseConnection:
    """Manages a single SQLite database connection with convenience methods.

    The connection is established lazily via :meth:`connect`. All query
    methods raise :class:`DatabaseError` if no connection is open.

    Attributes:
        _conn: Internal sqlite3 Connection object, or None.
        _path: Resolved file path of the open database, or None.
    """

    def __init__(self) -> None:
        """Initialize a DatabaseConnection with no active connection."""
        self._conn: sqlite3.Connection | None = None
        self._path: str | None = None

    @property
    def is_connected(self) -> bool:
        """bool: True if a database connection is currently open."""
        return self._conn is not None

    @property
    def path(self) -> str | None:
        """str or None: The resolved file path of the open database."""
        return self._path

    def connect(self, path: str) -> None:
        """Open a connection to a SQLite database file.

        Enables WAL journal mode and foreign key enforcement.

        Args:
            path: Filesystem path to the SQLite database file.

        Raises:
            sqlite3.Error: If the file cannot be opened.
        """
        resolved = pathlib.Path(path).resolve()
        self._conn = sqlite3.connect(str(resolved))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._path = str(resolved)

    def close(self) -> None:
        """Close the current database connection, if any."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._path = None

    def _require_connection(self) -> sqlite3.Connection:
        """Return the active connection or raise DatabaseError.

        Returns:
            The active sqlite3.Connection.

        Raises:
            DatabaseError: If no connection is open.
        """
        if self._conn is None:
            raise DatabaseError("No database connection open")
        return self._conn

    def tables(self) -> list[str]:
        """Return the names of all user-defined tables.

        Excludes internal sqlite_% tables. Results are sorted alphabetically.

        Returns:
            List of table names.
        """
        conn = self._require_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def views(self) -> list[str]:
        """Return the names of all views.

        Returns:
            List of view names.
        """
        conn = self._require_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def indexes(self, table_name: str) -> list[IndexInfo]:
        """Return metadata for all indexes on a given table.

        Args:
            table_name: Name of the table.

        Returns:
            List of IndexInfo objects describing each index.
        """
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
        """Return column metadata for a given table.

        Args:
            table_name: Name of the table.

        Returns:
            List of ColumnInfo objects describing each column.
        """
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
        """Return foreign key metadata for a given table.

        Args:
            table_name: Name of the table.

        Returns:
            List of ForeignKeyInfo objects describing each constraint.
        """
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
        """Return the number of rows in a table.

        Args:
            table_name: Name of the table.

        Returns:
            Row count, or 0 if the table is empty or does not exist.
        """
        conn = self._require_connection()
        row = conn.execute(
            f"SELECT COUNT(*) FROM {self._quote(table_name)}"
        ).fetchone()
        return row[0] if row else 0

    def execute(self, sql: str, params: tuple = ()) -> list[tuple[str]]:
        """Execute an arbitrary SQL statement with optional parameters.

        Args:
            sql: SQL statement to execute.
            params: Tuple of parameter values for parameterised queries.

        Returns:
            List of result rows for SELECT-like statements, or an empty list.
        """
        conn = self._require_connection()
        cursor = conn.execute(sql, params)
        if cursor.description:
            return cursor.fetchall()
        return []

    def execute_with_results(self, sql: str, params: tuple = ()) -> tuple[list[str], list[tuple]]:
        """Execute a SQL statement and return column names alongside rows.

        Args:
            sql: SQL statement to execute.
            params: Tuple of parameter values for parameterised queries.

        Returns:
            A tuple ``(columns, rows)`` where *columns* is a list of column
            names and *rows* is the list of result tuples.
        """
        conn = self._require_connection()
        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows

    def execute_script(self, sql: str) -> None:
        """Execute multiple SQL statements separated by semicolons.

        Args:
            sql: SQL script text.
        """
        conn = self._require_connection()
        conn.executescript(sql)

    def commit(self) -> None:
        """Commit the current transaction."""
        conn = self._require_connection()
        conn.commit()

    def rollback(self) -> None:
        """Roll back the current transaction."""
        conn = self._require_connection()
        conn.rollback()

    @staticmethod
    def _quote(name: str) -> str:
        """Return a double-quoted identifier for use in SQL statements.

        Args:
            name: Identifier to quote (table name, column name, etc.).

        Returns:
            Double-quoted identifier string.
        """
        return f'"{name}"'
