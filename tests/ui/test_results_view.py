import pytest
from PyQt6.QtCore import Qt
from core.query_executor import QueryResult
from ui.results_view import ResultsView, ResultTableModel


@pytest.fixture
def results_view(qtbot):
    widget = ResultsView()
    qtbot.addWidget(widget)
    return widget


class TestResultTableModel:
    def test_row_count(self):
        result = QueryResult(columns=["id", "name"], rows=[(1, "Alice"), (2, "Bob")])
        model = ResultTableModel(result)
        assert model.rowCount() == 2

    def test_column_count(self):
        result = QueryResult(columns=["id", "name"], rows=[(1, "Alice")])
        model = ResultTableModel(result)
        assert model.columnCount() == 2

    def test_data(self):
        result = QueryResult(columns=["id"], rows=[(42,)])
        model = ResultTableModel(result)
        idx = model.index(0, 0)
        assert model.data(idx) == "42"

    def test_data_null(self):
        result = QueryResult(columns=["val"], rows=[(None,)])
        model = ResultTableModel(result)
        idx = model.index(0, 0)
        assert model.data(idx) == "NULL"

    def test_header_data(self):
        result = QueryResult(columns=["id", "name"], rows=[])
        model = ResultTableModel(result)
        assert model.headerData(0, Qt.Orientation.Horizontal) == "id"
        assert model.headerData(1, Qt.Orientation.Horizontal) == "name"


class TestResultsView:
    def test_show_result(self, results_view):
        result = QueryResult(columns=["x"], rows=[(1,), (2,)])
        results_view.show_result(result)
        assert results_view._table_view.model() is not None

    def test_show_error(self, results_view):
        result = QueryResult(error="some error")
        results_view.show_result(result)
        assert "Error" in results_view._info_label.text()
        assert "red" in results_view._info_label.styleSheet()
        assert results_view._table_view.model() is None

    def test_clear(self, results_view):
        result = QueryResult(columns=["x"], rows=[(1,)])
        results_view.show_result(result)
        results_view.clear()
        assert results_view._table_view.model() is None
        assert results_view._info_label.text() == ""

    def test_info_label_shows_row_count(self, results_view):
        result = QueryResult(columns=["x"], rows=[(1,), (2,), (3,)], row_count=3, is_select=True)
        results_view.show_result(result)
        assert "3 row(s)" in results_view._info_label.text()

    def test_info_label_shows_duration(self, results_view):
        result = QueryResult(columns=["x"], rows=[(1,)], duration_ms=12.5, is_select=True)
        results_view.show_result(result)
        assert "12.5" in results_view._info_label.text()
