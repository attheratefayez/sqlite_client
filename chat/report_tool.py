"""Report generation utilities for the chat agent."""

from __future__ import annotations

import pathlib
from datetime import datetime

REPORTS_DIR = pathlib.Path("reports")


def results_to_markdown_table(columns: list[str], rows: list[tuple]) -> str:
    """Convert query results to a markdown table string."""
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        vals = [str(v) if v is not None else "NULL" for v in row]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def generate_report(
    content: str,
    title: str = "Query Report",
    filename: str | None = None,
) -> str:
    """Save markdown content as a report file.

    Args:
        content: Markdown body content (e.g. a table).
        title: Report title displayed at the top.
        filename: Optional filename (e.g. 'employees.md').
                  Auto-generated if omitted.

    Returns:
        Absolute path to the saved report file.
    """
    report_dir = REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{ts}.md"
    if not filename.endswith(".md"):
        filename += ".md"

    header = (
        f"# {title}\n\n"
        f"_Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n"
        "---\n\n"
    )

    path = report_dir / filename
    path.write_text(header + content, encoding="utf-8")
    return str(path.resolve())
