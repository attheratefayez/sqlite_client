"""Tests for the report generation tool."""

import pathlib

from chat.report_tool import (
    ReportResult,
    generate_report,
    results_to_markdown_table,
    slugify,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Employee Salary") == "Employee_Salary"

    def test_special_chars_removed(self):
        assert slugify("Report: Sales (Q1)") == "Report_Sales_Q1"

    def test_leading_trailing_spaces(self):
        assert slugify("  Title  ") == "Title"

    def test_empty_string(self):
        assert slugify("") == ""


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
    def test_saves_md_and_pdf(self, tmp_path):
        md = "# Test Report\n\nSome content."
        result = generate_report(md, output_dir=str(tmp_path))
        md_path = pathlib.Path(result.md_path)
        pdf_path = pathlib.Path(result.pdf_path)
        assert md_path.exists()
        assert pdf_path.exists()
        assert md_path.suffix == ".md"
        assert pdf_path.suffix == ".pdf"
        assert "Test Report" in md_path.read_text()

    def test_title_extracted_for_filename(self, tmp_path):
        md = "# Employee Salary Summary\n\nData here."
        result = generate_report(md, output_dir=str(tmp_path))
        path = pathlib.Path(result.md_path)
        assert "Employee_Salary_Summary" in path.stem

    def test_title_missing_falls_back_to_timestamp(self, tmp_path):
        md = "No title heading here."
        result = generate_report(md, output_dir=str(tmp_path))
        path = pathlib.Path(result.md_path)
        assert path.stem.startswith("report_")

    def test_timestamp_suffix_prevents_overwrite(self, tmp_path):
        md = "# Same Title\n\nContent."
        r1 = generate_report(md, output_dir=str(tmp_path))
        r2 = generate_report(md, output_dir=str(tmp_path))
        assert r1.md_path != r2.md_path
        assert r1.pdf_path != r2.pdf_path

    def test_pdf_is_valid(self, tmp_path):
        md = "# PDF Test\n\nBody text."
        result = generate_report(md, output_dir=str(tmp_path))
        pdf_data = pathlib.Path(result.pdf_path).read_bytes()
        assert pdf_data.startswith(b"%PDF")

    def test_returns_report_result(self, tmp_path):
        md = "# Hello\n\nWorld."
        result = generate_report(md, output_dir=str(tmp_path))
        assert isinstance(result, ReportResult)
        assert result.md_path.endswith(".md")
        assert result.pdf_path.endswith(".pdf")

    def test_creates_output_dir(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        md = "# Nested\n\nContent."
        result = generate_report(md, output_dir=str(nested))
        assert pathlib.Path(result.md_path).exists()
