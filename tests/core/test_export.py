import io
import json
from core.export import export_csv, export_json, export_sql_inserts


class TestExportCSV:
    def test_basic(self):
        buf = io.StringIO()
        export_csv(["id", "name"], [(1, "Alice"), (2, "Bob")], buf)
        output = buf.getvalue()
        assert "id,name" in output
        assert "1,Alice" in output
        assert "2,Bob" in output

    def test_empty_rows(self):
        buf = io.StringIO()
        export_csv(["id"], [], buf)
        output = buf.getvalue()
        assert "id" in output

    def test_null_values(self):
        buf = io.StringIO()
        export_csv(["val"], [(None,)], buf)
        output = buf.getvalue()
        assert "val" in output


class TestExportJSON:
    def test_basic(self):
        buf = io.StringIO()
        export_json(["id", "name"], [(1, "Alice"), (2, "Bob")], buf)
        data = json.loads(buf.getvalue())
        assert len(data) == 2
        assert data[0]["id"] == 1
        assert data[0]["name"] == "Alice"
        assert data[1]["id"] == 2
        assert data[1]["name"] == "Bob"

    def test_empty_rows(self):
        buf = io.StringIO()
        export_json(["id"], [], buf)
        assert buf.getvalue() == "[]"

    def test_null_values(self):
        buf = io.StringIO()
        export_json(["val"], [(None,)], buf)
        data = json.loads(buf.getvalue())
        assert data[0]["val"] is None


class TestExportSQL:
    def test_basic(self):
        buf = io.StringIO()
        export_sql_inserts("users", ["id", "name"], [(1, "Alice"), (2, "Bob")], buf)
        output = buf.getvalue()
        assert 'INSERT INTO "users" ("id", "name")' in output
        assert "VALUES (1, 'Alice')" in output
        assert "VALUES (2, 'Bob')" in output

    def test_null_values(self):
        buf = io.StringIO()
        export_sql_inserts("t", ["val"], [(None,)], buf)
        assert "NULL" in buf.getvalue()

    def test_escape_quotes(self):
        buf = io.StringIO()
        export_sql_inserts("t", ["name"], [("it's",)], buf)
        assert "it''s" in buf.getvalue()
