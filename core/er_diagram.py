"""ER diagram generation using Pillow.

Provides schema collection from a ``DatabaseConnection`` and rendering
to a PNG image using Pillow (PIL).  Tables are grouped into connected
components (clusters of tables linked by foreign keys) and each
component is laid out independently with a layered left-to-right
arrangement.  Edges are rendered as smooth bezier curves with column-name
labels.
"""

from __future__ import annotations

import math
import pathlib
import tempfile
from collections import deque
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

COLUMN_HEIGHT = 20
HEADER_HEIGHT = 28
PADDING_X = 10
CANVAS_PAD = 40
COMPONENT_GAP = 60
LAYER_GAP = 70
TABLE_GAP = 16


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


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _find_components(tables: list[ErTable]) -> list[list[str]]:
    """Group table names into connected components via the FK graph."""
    names = {t.name for t in tables}
    adj: dict[str, set[str]] = {t.name: set() for t in tables}
    for t in tables:
        for fk in t.foreign_keys:
            if fk.to_table in names:
                adj[t.name].add(fk.to_table)
                adj[fk.to_table].add(t.name)

    visited: set[str] = set()
    components: list[list[str]] = []
    for t in tables:
        if t.name in visited:
            continue
        comp: list[str] = []
        q = deque([t.name])
        while q:
            n = q.popleft()
            if n in visited:
                continue
            visited.add(n)
            comp.append(n)
            q.extend(adj[n] - visited)
        components.append(comp)
    return components


def _table_width(t: ErTable, font, font_bold) -> int:
    cw = []
    for c in t.columns:
        lbl = f"PK {c.name}  {c.col_type}" if c.is_pk else \
              f"FK {c.name}  {c.col_type}" if c.is_fk else \
              f"   {c.name}  {c.col_type}"
        cw.append(int(font.getlength(lbl)))
    mc = max(cw) if cw else 0
    nw = int(font_bold.getlength(t.name))
    return max(mc, nw) + 2 * PADDING_X + 4


def _barycenter_y(
    name: str,
    deps: dict[str, set[str]],
    table_map: dict[str, ErTable],
    unplaced: set[str],
) -> float:
    nb = deps.get(name, set()) - unplaced
    if not nb:
        return 0.0
    return sum(table_map[n].y + table_map[n].height / 2 for n in nb) / len(nb)


def _layout_component(
    names: list[str],
    table_map: dict[str, ErTable],
    deps: dict[str, set[str]],
    start_x: int,
) -> int:
    """Layered left-to-right layout for a single component.

    Returns the x-coordinate of the component's right edge.
    """
    unplaced = set(names)
    layers: list[list[str]] = []

    while unplaced:
        layer = {n for n in unplaced if not (deps.get(n, set()) & unplaced)}
        if not layer:
            layer = {unplaced.pop()}
        ordered = sorted(
            layer,
            key=lambda n: _barycenter_y(n, deps, table_map, unplaced),
        )
        layers.append(ordered)
        unplaced -= layer

    x = start_x
    for layer in layers:
        y = CANVAS_PAD
        layer_w = 0
        for name in layer:
            t = table_map[name]
            t.x = x
            t.y = y
            y += t.height + TABLE_GAP
            layer_w = max(layer_w, t.width)
        x += layer_w + LAYER_GAP

    return x


def _layout_tables(tables: list[ErTable]) -> list[ErTable]:
    if not tables:
        return tables

    font = ImageFont.truetype(FONT_PATH, 10)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, 10)

    for t in tables:
        t.width = _table_width(t, font, font_bold)
        t.height = HEADER_HEIGHT + len(t.columns) * COLUMN_HEIGHT + 4

    table_map = {t.name: t for t in tables}

    deps: dict[str, set[str]] = {}
    for t in tables:
        s = set()
        for fk in t.foreign_keys:
            if fk.to_table in table_map:
                s.add(fk.to_table)
        deps[t.name] = s

    components = _find_components(tables)
    x = CANVAS_PAD
    for comp in components:
        if len(comp) == 1:
            t = table_map[comp[0]]
            t.x = x
            t.y = CANVAS_PAD
            x = t.x + t.width + COMPONENT_GAP
        else:
            x = _layout_component(comp, table_map, deps, x)
            x += COMPONENT_GAP

    return tables


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _cubic_bezier(p0, p1, p2, p3, steps=30):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        pts.append((int(x), int(y)))
    return pts


def _arrow_head(draw: ImageDraw, x: float, y: float, angle: float, size: int = 5):
    ax = x - size * math.cos(angle)
    ay = y - size * math.sin(angle)
    draw.polygon([
        (x, y),
        (ax - size * 0.35 * math.sin(angle), ay + size * 0.35 * math.cos(angle)),
        (ax + size * 0.35 * math.sin(angle), ay - size * 0.35 * math.cos(angle)),
    ], fill=FK_COLOR)


def render_er_diagram(tables: list[ErTable], output_path: str) -> str:
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
    font_tiny = ImageFont.truetype(FONT_PATH, 7)

    table_map = {t.name: t for t in tables}

    # Collect edges
    pair_count: dict[tuple[str, str], int] = {}
    edges: list[tuple[float, float, float, float, str, str]] = []
    for t in tables:
        for fk in t.foreign_keys:
            if fk.to_table not in table_map:
                continue
            key = (fk.from_table, fk.to_table)
            off = pair_count.get(key, 0)
            pair_count[key] = off + 1

            src = table_map[fk.from_table]
            dst = table_map[fk.to_table]

            src_y = src.y + src.height / 2 + off * 8 - 4
            dst_y = dst.y + dst.height / 2 + off * 8 - 4

            sx = src.x + src.width
            sy = src_y
            ex = dst.x
            ey = dst_y

            edges.append((sx, sy, ex, ey, fk.from_col, fk.to_col))

    # Draw edges
    for sx, sy, ex, ey, fc, tc in edges:
        gap = abs(ex - sx)
        if gap < 10:
            gap = 10
        cp1 = (sx + gap * 0.3, sy)
        cp2 = (ex - gap * 0.3, ey)
        pts = _cubic_bezier((sx, sy), cp1, cp2, (ex, ey))
        draw.line(pts, fill=FK_COLOR, width=1)
        angle = math.atan2(ey - sy, ex - sx)
        _arrow_head(draw, ex, ey, angle)

        mid = len(pts) // 2
        label = f"{fc} → {tc}"
        lw = int(font_tiny.getlength(label)) + 4
        lx = pts[mid][0] - lw // 2
        ly = pts[mid][1] - 8
        draw.rectangle(
            [(lx, ly - 1), (lx + lw, ly + 8)],
            fill="white", outline=FK_COLOR,
        )
        draw.text((lx + 2, ly), label, fill=FK_COLOR, font=font_tiny)

    # Draw tables
    for t in tables:
        draw.rounded_rectangle(
            [(t.x, t.y), (t.x + t.width, t.y + HEADER_HEIGHT)],
            radius=4, fill=HEADER_BG,
        )
        draw.text(
            (t.x + PADDING_X, t.y + 5),
            t.name, fill=HEADER_FG, font=font_bold,
        )

        yo = t.y + HEADER_HEIGHT
        for i, c in enumerate(t.columns):
            bg = COLUMN_BG_ALT if i % 2 else COLUMN_BG
            draw.rectangle(
                [(t.x, yo), (t.x + t.width, yo + COLUMN_HEIGHT)],
                fill=bg,
            )

            px = t.x + 3
            if c.is_pk:
                draw.text((px, yo + 2), "PK", fill=PK_COLOR, font=font_bold)
            elif c.is_fk:
                draw.text((px, yo + 2), "FK", fill=FK_COLOR, font=font_bold)

            draw.text(
                (t.x + 22, yo + 2),
                f"{c.name}  {c.col_type}",
                fill=TEXT_COLOR, font=font_small,
            )
            yo += COLUMN_HEIGHT

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
    tables = collect_schema(db_conn, table_name)
    if output_path is None:
        suffix = f"er_{table_name}.png" if table_name else "er_global.png"
        output_path = str(pathlib.Path(tempfile.gettempdir()) / suffix)
    return render_er_diagram(tables, output_path)
