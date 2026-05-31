"""ER diagram generation using Pillow.

Provides schema collection from a ``DatabaseConnection`` and rendering
to a PNG image using Pillow (PIL).  Tables are laid out in left-to-right
layers based on foreign-key dependencies.
"""

from __future__ import annotations

import math
import pathlib
import tempfile
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

HEADER_BG = "#0d47a1"
HEADER_FG = "white"
COLUMN_BG = "#fafafa"
COLUMN_BG_ALT = "#f0f0f0"
BORDER_COLOR = "#9e9e9e"
FK_COLOR = "#1565c0"
PK_COLOR = "#e65100"
TEXT_COLOR = "#333"

COLUMN_HEIGHT = 22
HEADER_HEIGHT = 30
PADDING_X = 12
TABLE_MARGIN_X = 50
TABLE_MARGIN_Y = 40
LAYER_GAP = 100
CANVAS_PAD = 40


@dataclass
class ErColumn:
    name: str
    col_type: str
    is_pk: bool
    is_fk: bool


@dataclass
class ErForeignKey:
    from_table: str
    from_col: str
    to_table: str
    to_col: str


@dataclass
class ErTable:
    name: str
    columns: list[ErColumn]
    foreign_keys: list[ErForeignKey]
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


def collect_schema(
    db_conn: Any,
    table_name: str | None = None,
) -> list[ErTable]:
    """Collect database schema into ``ErTable`` structures.

    Args:
        db_conn: A ``DatabaseConnection`` instance.
        table_name: If given, only this table plus tables it directly
            references (FK outward) and tables that reference it
            (FK inward) are included.  If ``None``, all tables are
            included.

    Returns:
        List of ``ErTable`` objects.
    """
    all_tables = db_conn.tables()

    if table_name:
        target_tables = {table_name}
        for fk in db_conn.foreign_keys(table_name):
            target_tables.add(fk.table)
        for t in all_tables:
            for fk in db_conn.foreign_keys(t):
                if fk.table == table_name:
                    target_tables.add(t)
        tables_to_include = sorted(target_tables)
    else:
        tables_to_include = all_tables

    all_fks: dict[str, list[ErForeignKey]] = {}
    for t in all_tables:
        fks = []
        for fk in db_conn.foreign_keys(t):
            fks.append(ErForeignKey(
                from_table=t,
                from_col=fk.from_col,
                to_table=fk.table,
                to_col=fk.to_col,
            ))
        all_fks[t] = fks

    result = []
    for t in tables_to_include:
        cols = db_conn.table_schema(t)
        pk_names = {c.name for c in cols if c.primary_key}
        fk_cols = {fk.from_col for fk in all_fks.get(t, [])}

        er_cols = [
            ErColumn(
                name=c.name,
                col_type=c.col_type,
                is_pk=c.name in pk_names,
                is_fk=c.name in fk_cols,
            )
            for c in cols
        ]

        result.append(ErTable(
            name=t,
            columns=er_cols,
            foreign_keys=[fk for fk in all_fks.get(t, [])
                          if fk.to_table in tables_to_include],
        ))

    return result


def _layout_tables(tables: list[ErTable]) -> list[ErTable]:
    """Assign positions to tables using layered left-to-right layout.

    Tables with no FK dependencies are placed in the leftmost layer;
    each subsequent layer holds tables that depend only on already-placed
    tables.
    """
    if not tables:
        return tables

    table_map = {t.name: t for t in tables}

    deps: dict[str, set[str]] = {t.name: set() for t in tables}
    for t in tables:
        for fk in t.foreign_keys:
            if fk.to_table in table_map:
                deps[t.name].add(fk.to_table)

    remaining = set(table_map)
    layers: list[list[str]] = []

    while remaining:
        layer = {n for n in remaining if not (deps[n] & remaining)}
        if not layer:
            layer = {remaining.pop()}
        layers.append(sorted(layer))
        remaining -= layer

    font = ImageFont.truetype(FONT_PATH, 10)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, 10)

    for t in tables:
        col_widths = []
        for c in t.columns:
            label = f"PK {c.name}  {c.col_type}" if c.is_fk else \
                    f"PK {c.name}  {c.col_type}" if c.is_pk else \
                    f"   {c.name}  {c.col_type}"
            col_widths.append(int(font.getlength(label)))
        max_col = max(col_widths) if col_widths else 0
        name_w = int(font_bold.getlength(t.name))
        t.width = max(max_col, name_w) + 2 * PADDING_X + 4
        t.height = HEADER_HEIGHT + len(t.columns) * COLUMN_HEIGHT + 4

    x = TABLE_MARGIN_X
    for layer in layers:
        y = TABLE_MARGIN_Y
        layer_w = 0
        for name in layer:
            t = table_map[name]
            t.x = x
            t.y = y
            y += t.height + TABLE_MARGIN_Y
            layer_w = max(layer_w, t.width)
        x += layer_w + LAYER_GAP

    return tables


def _draw_arrow_head(draw: ImageDraw, x: float, y: float, angle: float, size: int = 6):
    ax = x - size * math.cos(angle)
    ay = y - size * math.sin(angle)
    draw.polygon([
        (x, y),
        (ax - size * 0.35 * math.sin(angle), ay + size * 0.35 * math.cos(angle)),
        (ax + size * 0.35 * math.sin(angle), ay - size * 0.35 * math.cos(angle)),
    ], fill=FK_COLOR)


def render_er_diagram(tables: list[ErTable], output_path: str) -> str:
    """Render a list of ``ErTable`` objects to a PNG image.

    Args:
        tables: Tables to render (result of ``collect_schema``).
        output_path: Path where the PNG file will be written.

    Returns:
        ``output_path`` on success.
    """
    tables = _layout_tables(tables)

    if not tables:
        img = Image.new("RGB", (400, 200), "white")
        draw = ImageDraw.Draw(img)
        draw.text((150, 90), "No tables in database", fill="#666")
        img.save(output_path)
        return output_path

    max_x = max(t.x + t.width for t in tables) + CANVAS_PAD
    max_y = max(t.y + t.height for t in tables) + CANVAS_PAD

    img = Image.new("RGB", (max_x, max_y), "white")
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(FONT_PATH, 10)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, 10)
    font_small = ImageFont.truetype(FONT_PATH, 9)

    table_map = {t.name: t for t in tables}

    # Build column centre-point map
    col_pt: dict[tuple[str, str], tuple[int, int]] = {}
    for t in tables:
        yc = t.y + HEADER_HEIGHT + COLUMN_HEIGHT // 2
        for c in t.columns:
            col_pt[(t.name, c.name)] = (t.x, yc)
            yc += COLUMN_HEIGHT

    # Collect edges between tables in this diagram
    edges: list[tuple[int, int, int, int]] = []
    for t in tables:
        for fk in t.foreign_keys:
            src = (fk.from_table, fk.from_col)
            dst = (fk.to_table, fk.to_col)
            if src in col_pt and dst in col_pt:
                sx, sy = col_pt[src]
                dx, dy = col_pt[dst]
                src_w = table_map[fk.from_table].width
                dst_w = table_map[fk.to_table].width
                # Start from right edge of source, end at left edge of target
                start_x = sx + src_w
                end_x = dx
                edges.append((start_x, sy, end_x, dy))

    for sx, sy, ex, ey in edges:
        draw.line([(sx, sy), (ex, ey)], fill=FK_COLOR, width=1)
        angle = math.atan2(ey - sy, ex - sx)
        _draw_arrow_head(draw, ex, ey, angle)

    # Draw table boxes on top
    for t in tables:
        draw.rounded_rectangle(
            [(t.x, t.y), (t.x + t.width, t.y + HEADER_HEIGHT)],
            radius=4, fill=HEADER_BG,
        )
        draw.text((t.x + PADDING_X, t.y + 6), t.name, fill=HEADER_FG, font=font_bold)

        y_offset = t.y + HEADER_HEIGHT
        for i, c in enumerate(t.columns):
            bg = COLUMN_BG_ALT if i % 2 else COLUMN_BG
            draw.rectangle(
                [(t.x, y_offset), (t.x + t.width, y_offset + COLUMN_HEIGHT)],
                fill=bg,
            )

            px = t.x + 4
            if c.is_pk:
                draw.text((px, y_offset + 4), "PK", fill=PK_COLOR, font=font_bold)
            elif c.is_fk:
                draw.text((px, y_offset + 4), "FK", fill=FK_COLOR, font=font_bold)

            label_x = t.x + 28
            draw.text(
                (label_x, y_offset + 4),
                f"{c.name}  {c.col_type}",
                fill=TEXT_COLOR, font=font_small,
            )
            y_offset += COLUMN_HEIGHT

        draw.rounded_rectangle(
            [(t.x, t.y), (t.x + t.width, t.y + t.height)],
            radius=4, outline=BORDER_COLOR, width=1,
        )

    img.save(output_path)
    return output_path


def generate_er_png(
    db_conn: Any,
    table_name: str | None = None,
    output_path: str | None = None,
) -> str:
    """High-level helper: collect schema and render ER diagram to PNG.

    Args:
        db_conn: A ``DatabaseConnection`` instance.
        table_name: Optional table name for scoped diagram.
        output_path: Destination path.  If omitted, a temp file is created.

    Returns:
        Absolute path to the rendered PNG.
    """
    tables = collect_schema(db_conn, table_name)
    if output_path is None:
        suffix = f"er_{table_name}.png" if table_name else "er_global.png"
        output_path = str(pathlib.Path(tempfile.gettempdir()) / suffix)
    return render_er_diagram(tables, output_path)
