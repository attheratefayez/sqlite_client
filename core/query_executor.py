from dataclasses import dataclass, field
from typing import Any
from core.database import DatabaseConnection


@dataclass
class QueryResult:
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    error: str | None = None
    row_count: int = 0
    duration_ms: float = 0.0
    is_select: bool = False

    def __post_init__(self) -> None:
        if self.row_count == 0 and self.rows:
            self.row_count = len(self.rows)

    @property
    def success(self) -> bool:
        return self.error is None


def is_select_statement(sql: str) -> bool:
    stripped = sql.strip().upper()
    return any(
        stripped.startswith(kw)
        for kw in ["SELECT", "PRAGMA", "EXPLAIN", "WITH"]
    )


class QueryExecutor:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def execute(self, sql: str) -> QueryResult:
        import time
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

    def execute_many(self, statements: list[str]) -> list[QueryResult]:
        results = []
        for sql in statements:
            if sql.strip():
                results.append(self.execute(sql))
        return results
