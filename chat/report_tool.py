"""Report generation utilities for the chat agent."""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass
from datetime import datetime

import markdown
from weasyprint import HTML

REPORTS_DIR = pathlib.Path("reports")


@dataclass
class ReportResult:
    md_path: str
    pdf_path: str


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe name."""
    text = text.strip().replace(" ", "_")
    return "".join(c for c in text if c.isalnum() or c in "_-")


def results_to_markdown_table(columns: list[str], rows: list[tuple]) -> str:
    """Convert query results to a markdown table string."""
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        vals = [str(v) if v is not None else "NULL" for v in row]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


_PDF_CSS = """\
@page {
  size: A4;
  margin: 25mm 20mm;
}

body {
  font-family: 'Helvetica', 'Arial', sans-serif;
  font-size: 11pt;
  line-height: 1.6;
  color: #1a1a1a;
}

h1 {
  font-size: 22pt;
  color: #0d47a1;
  margin-top: 0;
  margin-bottom: 6pt;
  padding-bottom: 4pt;
  border-bottom: 2px solid #0d47a1;
}

h2 {
  font-size: 16pt;
  color: #1565c0;
  margin-top: 20pt;
  margin-bottom: 8pt;
  padding-bottom: 2pt;
  border-bottom: 1px solid #bbdefb;
}

h3 {
  font-size: 13pt;
  color: #1976d2;
  margin-top: 14pt;
  margin-bottom: 6pt;
}

p {
  margin: 6pt 0;
  text-align: justify;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 10pt 0;
  font-size: 8pt;
}

th {
  background-color: #0d47a1;
  color: white;
  font-weight: bold;
  padding: 5pt 6pt;
  text-align: left;
  word-break: break-word;
  overflow-wrap: break-word;
}

td {
  padding: 4pt 6pt;
  border: 1px solid #bdbdbd;
  word-break: break-word;
  overflow-wrap: break-word;
}

tr:nth-child(even) td {
  background-color: #f5f5f5;
}

code {
  font-family: 'Courier New', monospace;
  font-size: 10pt;
  background-color: #f5f5f5;
  padding: 1pt 4pt;
  border-radius: 3pt;
}

pre {
  background-color: #263238;
  color: #e0e0e0;
  padding: 10pt;
  border-radius: 4pt;
  overflow-x: auto;
  font-size: 9pt;
}

pre code {
  background-color: transparent;
  color: inherit;
  padding: 0;
}

hr {
  border: none;
  border-top: 1px solid #bdbdbd;
  margin: 16pt 0;
}
"""


def markdown_to_pdf(md_text: str, output_path: str) -> None:
    """Convert markdown text to a professional PDF using WeasyPrint."""
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>{_PDF_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""
    HTML(string=html).write_pdf(output_path)


def generate_report(
    markdown_content: str,
    output_dir: str | pathlib.Path | None = None,
) -> ReportResult:
    """Save a full markdown report as .md and .pdf.

    Extracts the title from the first ``# `` heading for the filename.
    If no title is found, falls back to a timestamp-based name.
    A timestamp suffix is appended to prevent overwrites.

    Args:
        markdown_content: Complete markdown report including the title.
        output_dir: Directory to write files to. Defaults to ``reports/``.

    Returns:
        A ``ReportResult`` with the paths to the saved files.
    """
    report_dir = pathlib.Path(output_dir) if output_dir else REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    title_match = re.search(r"^# (.+)$", markdown_content, re.MULTILINE)
    if title_match:
        stem = slugify(title_match.group(1))
    else:
        stem = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename_stem = f"{stem}_{ts}"
    md_path = report_dir / f"{filename_stem}.md"
    pdf_path = report_dir / f"{filename_stem}.pdf"

    counter = 1
    while md_path.exists() or pdf_path.exists():
        filename_stem = f"{stem}_{ts}_{counter}"
        md_path = report_dir / f"{filename_stem}.md"
        pdf_path = report_dir / f"{filename_stem}.pdf"
        counter += 1

    md_path.write_text(markdown_content, encoding="utf-8")
    markdown_to_pdf(markdown_content, str(pdf_path))

    return ReportResult(md_path=str(md_path.resolve()), pdf_path=str(pdf_path.resolve()))
