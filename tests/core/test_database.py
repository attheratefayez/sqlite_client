import pytest
import tempfile
import pathlib
from core.database import DatabaseConnection, DatabaseError, ColumnInfo, ForeignKeyInfo, IndexInfo


@pytest.fixture
def db():
    conn = DatabaseConnection()
    yield conn
    if conn.is_connected:
        conn.close()


@pytest.fixture
def sample_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = DatabaseConnection()
    conn.connect(tmp.name)
    conn.execute_script("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            age INTEGER DEFAULT 0
        );
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE VIEW active_users AS SELECT * FROM users WHERE age >= 18;
        CREATE INDEX idx_users_email ON users(email);
        INSERT INTO users (name, email, age) VALUES ('Alice', 'alice@test.com', 30);
        INSERT INTO users (name, email, age) VALUES ('Bob', 'bob@test.com', 25);
    """)
    conn.commit()
    yield conn
    conn.close()
    pathlib.Path(tmp.name).unlink(missing_ok=True)


class TestDatabaseConnection:
    def test_connect_and_close(self, db):
        assert not db.is_connected
        assert db.path is None
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db.connect(db_path)
        assert db.is_connected
        assert db.path is not None
        db.close()
        assert not db.is_connected
        assert db.path is None
        pathlib.Path(db_path).unlink(missing_ok=True)

    def test_create_new_database(self, db):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db.connect(db_path)
        db.execute("CREATE TABLE test (id INTEGER)")
        assert db.tables() == ["test"]
        db.close()
        pathlib.Path(db_path).unlink(missing_ok=True)

    def test_tables(self, sample_db):
        tables = sample_db.tables()
        assert "users" in tables
        assert "posts" in tables
        assert "sqlite_sequence" not in tables

    def test_views(self, sample_db):
        views = sample_db.views()
        assert "active_users" in views

    def test_table_schema(self, sample_db):
        columns = sample_db.table_schema("users")
        assert len(columns) == 4
        assert columns[0] == ColumnInfo(cid=0, name="id", col_type="INTEGER", notnull=False, default_value=None, primary_key=True)
        assert columns[1] == ColumnInfo(cid=1, name="name", col_type="TEXT", notnull=True, default_value=None, primary_key=False)
        assert columns[2] == ColumnInfo(cid=2, name="email", col_type="TEXT", notnull=False, default_value=None, primary_key=False)
        assert columns[3] == ColumnInfo(cid=3, name="age", col_type="INTEGER", notnull=False, default_value="0", primary_key=False)

    def test_foreign_keys(self, sample_db):
        fks = sample_db.foreign_keys("posts")
        assert len(fks) == 1
        assert fks[0].table == "users"
        assert fks[0].from_col == "user_id"
        assert fks[0].to_col == "id"
        assert fks[0].on_delete == "CASCADE"

    def test_indexes(self, sample_db):
        indexes = sample_db.indexes("users")
        names = [idx.name for idx in indexes]
        assert "idx_users_email" in names
        for idx in indexes:
            if idx.name == "idx_users_email":
                assert idx.columns == ["email"]
                assert not idx.unique

    def test_table_row_count(self, sample_db):
        assert sample_db.table_row_count("users") == 2
        assert sample_db.table_row_count("posts") == 0

    def test_execute(self, sample_db):
        rows = sample_db.execute("SELECT name FROM users ORDER BY name")
        assert rows == [("Alice",), ("Bob",)]

    def test_execute_with_results(self, sample_db):
        columns, rows = sample_db.execute_with_results("SELECT name, age FROM users ORDER BY name")
        assert columns == ["name", "age"]
        assert rows == [("Alice", 30), ("Bob", 25)]

    def test_execute_script(self, db):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db.connect(db_path)
        db.execute_script("CREATE TABLE foo (x INT); INSERT INTO foo VALUES (1);")
        assert db.table_row_count("foo") == 1
        db.close()
        pathlib.Path(db_path).unlink(missing_ok=True)

    def test_commit_and_rollback(self, sample_db):
        sample_db.execute("INSERT INTO users (name) VALUES ('Charlie')")
        sample_db.rollback()
        assert sample_db.table_row_count("users") == 2
        sample_db.execute("INSERT INTO users (name) VALUES ('Charlie')")
        sample_db.commit()
        assert sample_db.table_row_count("users") == 3

    def test_error_when_not_connected(self, db):
        with pytest.raises(DatabaseError, match="No database connection open"):
            db.tables()

    def test_error_with_invalid_path(self, db):
        with pytest.raises(Exception):
            db.connect("/nonexistent/dir/test.db")
