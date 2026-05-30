import pytest
import tempfile
import pathlib
from core.database import DatabaseConnection
from core.query_executor import QueryExecutor, QueryResult, is_select_statement


@pytest.fixture
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = DatabaseConnection()
    conn.connect(tmp.name)
    conn.execute_script("""
        CREATE TABLE test (id INTEGER, name TEXT);
        INSERT INTO test VALUES (1, 'Alice');
        INSERT INTO test VALUES (2, 'Bob');
    """)
    conn.commit()
    yield conn
    conn.close()
    pathlib.Path(tmp.name).unlink(missing_ok=True)


@pytest.fixture
def executor(db):
    return QueryExecutor(db)


class TestIsSelectStatement:
    def test_select(self):
        assert is_select_statement("SELECT * FROM users")

    def test_select_lowercase(self):
        assert is_select_statement("select * from users")

    def test_with(self):
        assert is_select_statement("WITH cte AS (SELECT 1) SELECT * FROM cte")

    def test_pragma(self):
        assert is_select_statement("PRAGMA table_info(users)")

    def test_insert(self):
        assert not is_select_statement("INSERT INTO users VALUES (1)")

    def test_update(self):
        assert not is_select_statement("UPDATE users SET name = 'x'")

    def test_delete(self):
        assert not is_select_statement("DELETE FROM users")

    def test_create(self):
        assert not is_select_statement("CREATE TABLE foo (id INT)")

    def test_empty(self):
        assert not is_select_statement("")

    def test_whitespace(self):
        assert not is_select_statement("   ")


class TestQueryExecutor:
    def test_select_query(self, executor):
        result = executor.execute("SELECT * FROM test ORDER BY id")
        assert result.success
        assert result.columns == ["id", "name"]
        assert result.rows == [(1, "Alice"), (2, "Bob")]
        assert result.row_count == 2
        assert result.is_select
        assert result.duration_ms >= 0

    def test_insert_query(self, executor):
        result = executor.execute("INSERT INTO test VALUES (3, 'Charlie')")
        assert result.success
        assert not result.is_select
        assert result.error is None

    def test_invalid_sql(self, executor):
        result = executor.execute("SELECT invalid_sql")
        assert not result.success
        assert result.error is not None

    def test_update_query(self, executor):
        result = executor.execute("UPDATE test SET name = 'Updated' WHERE id = 1")
        assert result.success
        assert not result.is_select

    def test_delete_query(self, executor):
        result = executor.execute("DELETE FROM test WHERE id = 1")
        assert result.success
        assert not result.is_select

    def test_pragma_query(self, executor):
        result = executor.execute("PRAGMA table_info(test)")
        assert result.success
        assert result.is_select
        assert len(result.rows) > 0
