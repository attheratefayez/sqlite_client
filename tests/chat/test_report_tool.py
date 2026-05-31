"""Tests for the report generation tool."""

import pathlib
import tempfile

from chat.report_tool import generate_report, results_to_markdown_table


class TestResultsToMarkdownTable:
    def test_basic_table(self):
        columns = ["Name", "Age"]
        rows = [("Alice", 30), ("Bob", 25)]
        result = results_to_markdown_table(columns, rows)
        expected = (
            "| Name | Age |\n"
            "| --- | --- |\n"
            "| Alice | 30 |\n"
            "| Bob | 25 |"
        )
        assert result == expected

    def test_empty_columns(self):
        assert results_to_markdown_table([], []) == "|  |\n|  |"

    def test_empty_rows(self):
        assert results_to_markdown_table(["Col"], []) == "| Col |\n| --- |"

    def test_null_values(self):
        columns = ["Name", "Email"]
        rows = [("Alice", None)]
        result = results_to_markdown_table(columns, rows)
        assert "NULL" in result

    def test_special_chars(self):
        columns = ["Name"]
        rows = [("John <Doe>",)]
        result = results_to_markdown_table(columns, rows)
        assert "John <Doe>" in result


class TestGenerateReport:
    def test_saves_to_reports_dir(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            result = generate_report(
                content="| Col |\n| --- |\n| val |",
                title="Test Report",
            )
            path = pathlib.Path(result)
            assert path.exists()
            assert path.suffix == ".md"
            assert "Test Report" in path.read_text()

    def test_custom_filename(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            result = generate_report(
                content="data",
                filename="my_report.md",
            )
            path = pathlib.Path(result)
            assert path.name == "my_report.md"

    def test_auto_adds_md_extension(self, tmp_path):
        with tempfile.TemporaryDirectory() as d:
            result = generate_report(
                content="data",
                filename="my_report",
            )
            path = pathlib.Path(result)
            assert path.suffix == ".md"

    def test_content_includes_title(self):
        with tempfile.TemporaryDirectory() as d:
            result = generate_report(
                content="| A | B |\n| --- | --- |",
                title="My Query",
            )
            text = pathlib.Path(result).read_text()
            assert "# My Query" in text
            assert "Generated on" in text
            assert "| A | B |" in text

    def test_generates_filename_when_not_provided(self):
        with tempfile.TemporaryDirectory() as d:
            result = generate_report(content="test")
            path = pathlib.Path(result)
            assert path.name.startswith("report_")
            assert path.suffix == ".md"
