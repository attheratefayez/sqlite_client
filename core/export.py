"""Data export utilities for the SQLite client.

Provides functions to serialise query results into CSV, JSON, and SQL
INSERT statement formats.
"""

import csv
import json
import io
from typing import Any


def export_csv(columns: list[str], rows: list[tuple], output: io.StringIO) -> None:
    """Write query results in CSV format.

    The first line written contains the column headers.

    Args:
        columns: Column names to use as the header row.
        rows: Tuples of row values.
        output: Text stream to write the CSV data into.
    """
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)


def export_json(columns: list[str], rows: list[tuple], output: io.StringIO) -> None:
    """Write query results in JSON format.

    Produces an array of objects where each object maps column names to
    row values.

    Args:
        columns: Column names used as object keys.
        rows: Tuples of row values.
        output: Text stream to write the JSON data into.
    """
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(dict(zip(columns, row)))
    json.dump(result, output, indent=2, default=str)


def export_sql_inserts(
    table_name: str, columns: list[str], rows: list[tuple], output: io.StringIO
) -> None:
    """Write query results as SQL INSERT statements.

    Each row is written as a separate ``INSERT INTO ... VALUES (...)``
    statement. String values are properly escaped.

    Args:
        table_name: Target table name for the INSERT statements.
        columns: Column names to include in each INSERT.
        rows: Tuples of row values.
        output: Text stream to write the SQL into.
    """
    col_list = ", ".join(f'"{c}"' for c in columns)
    for row in rows:
        values = []
        for val in row:
            if val is None:
                values.append("NULL")
            elif isinstance(val, (int, float)):
                values.append(str(val))
            else:
                escaped = str(val).replace("'", "''")
                values.append(f"'{escaped}'")
        values_str = ", ".join(values)
        output.write(f"INSERT INTO \"{table_name}\" ({col_list}) VALUES ({values_str});\n")
