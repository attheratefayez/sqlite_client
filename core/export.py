import csv
import json
import io
from typing import Any


def export_csv(columns: list[str], rows: list[tuple], output: io.StringIO) -> None:
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)


def export_json(columns: list[str], rows: list[tuple], output: io.StringIO) -> None:
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(dict(zip(columns, row)))
    json.dump(result, output, indent=2, default=str)


def export_sql_inserts(
    table_name: str, columns: list[str], rows: list[tuple], output: io.StringIO
) -> None:
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
