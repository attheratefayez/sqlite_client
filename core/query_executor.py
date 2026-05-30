"""Query execution and result modelling for the SQLite client.

Provides :class:`QueryResult` for encapsulating execution outcomes and
:class:`QueryExecutor` for running SQL statements against a database.
"""

import time
from dataclasses import dataclass, field
from core.database import DatabaseConnection


@dataclass
class QueryResult:
    """Encapsulates the result of a single SQL statement execution.

    Attributes:
        columns: Column names returned by the query.
        rows: Result rows as tuples of values.
        error: Error message string if execution failed, or None.
        row_count: Number of rows in *rows* (auto-populated if zero).
        duration_ms: Execution time in milliseconds.
        is_select: True if the statement is a SELECT-like query.
    """
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    error: str | None = None
    row_count: int = 0
    duration_ms: float = 0.0
    is_select: bool = False

    def __post_init__(self) -> None:
        """Auto-populate row_count from rows if not already set."""
        if self.row_count == 0 and self.rows:
            self.row_count = len(self.rows)

    @property
    def success(self) -> bool:
        """bool: True if no error occurred during execution."""
        return self.error is None


def is_select_statement(sql: str) -> bool:
    """Determine whether a SQL statement is a SELECT-like query.

    Matches statements starting with SELECT, PRAGMA, EXPLAIN, or WITH.

    Args:
        sql: SQL statement text.

    Returns:
        True if the statement is considered a SELECT-like query.
    """
    stripped = sql.strip().upper()
    return any(
        stripped.startswith(kw)
        for kw in ["SELECT", "PRAGMA", "EXPLAIN", "WITH"]
    )


class QueryExecutor:
    """Executes SQL statements against a DatabaseConnection.

    Wraps the low-level connection API and returns :class:`QueryResult`
    objects that capture both successful results and errors.

    Attributes:
        _db: The DatabaseConnection used for execution.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        """Initialize the executor with a database connection.

        Args:
            db: An active DatabaseConnection instance.
        """
        self._db = db

    def execute(self, sql: str) -> QueryResult:
        """Execute a single SQL statement and return the result.

        Measures execution duration and captures exceptions as
        :attr:`QueryResult.error`.

        Args:
            sql: SQL statement to execute.

        Returns:
            A QueryResult with columns, rows, duration, and error state.
        """
        result = QueryResult()
        result.is_select = is_select_statement(sql)
        try:
            start = time.time()
            columns, rows = self._db.execute_with_results(sql)
            end = time.time()
            result.columns = columns
            result.rows = rows
            result.row_count = len(rows)
            result.duration_ms = round((end - start) * 1000, 1)
        except Exception as e:
            result.error = str(e)
        return result


