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

COLUMN_HEIGHT = 26
HEADER_HEIGHT = 36
PADDING_X = 14
CANVAS_PAD = 50
COMPONENT_GAP = 80
LAYER_GAP = 90
TABLE_GAP = 20


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

    font = ImageFont.truetype(FONT_PATH, 14)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, 14)

    for t in tables:
        t.width = _table_width(t, font, font_bold)
        t.height = HEADER_HEIGHT + len(t.columns) * COLUMN_HEIGHT + 8

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


def render_er_diagram(
    tables: list[ErTable],
    output_path: str,
    scale: int = 3,
) -> str:
    """Render a list of ``ErTable`` objects to a PNG image.

    Args:
        tables: Tables to render (result of ``collect_schema``).
        output_path: Path where the PNG file will be written.
        scale: Render at ``scale``× resolution then downscale for
            anti-aliasing (default 2).  Higher values give smoother
            edges at the cost of more memory.

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

    S = scale
    max_x = max(t.x + t.width for t in tables) + CANVAS_PAD
    max_y = max(t.y + t.height for t in tables) + CANVAS_PAD

    img = Image.new("RGB", (max_x * S, max_y * S), "white")
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(FONT_PATH, 14 * S)
    font_bold = ImageFont.truetype(FONT_BOLD_PATH, 14 * S)
    font_small = ImageFont.truetype(FONT_PATH, 12 * S)
    font_tiny = ImageFont.truetype(FONT_PATH, 10 * S)

    table_map = {t.name: t for t in tables}

    # Collect edges + precompute bezier curves + label positions
    pair_count: dict[tuple[str, str], int] = {}
    edge_curves: list[list[tuple[float, float]]] = []
    arrow_angles: list[float] = []
    label_info: list[tuple[float, float, float, float, str, str, str, str]] = []
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

            sx = (src.x + src.width) * S
            sy = src_y * S
            ex = dst.x * S
            ey = dst_y * S

            gap = abs(ex - sx)
            if gap < 10 * S:
                gap = 10 * S
            cp1 = (sx + gap * 0.3, sy)
            cp2 = (ex - gap * 0.3, ey)
            pts = _cubic_bezier((sx, sy), cp1, cp2, (ex, ey), steps=30 * S)
            edge_curves.append(pts)
            arrow_angles.append(math.atan2(ey - sy, ex - sx))

            mid = len(pts) // 2
            label_info.append((
                pts[mid][0], pts[mid][1],
                fk.from_table, fk.from_col,
                fk.to_table, fk.to_col,
            ))

    # Draw edge lines + arrow heads (before tables)
    for pts, angle in zip(edge_curves, arrow_angles):
        draw.line(pts, fill=FK_COLOR, width=max(1, S // 2))
        ex2, ey2 = pts[-1]
        _arrow_head(draw, ex2, ey2, angle, size=5 * S)

    # Draw tables
    for t in tables:
        tx = t.x * S
        ty = t.y * S
        tw = t.width * S
        th = t.height * S

        draw.rounded_rectangle(
            [(tx, ty), (tx + tw, ty + HEADER_HEIGHT * S)],
            radius=4 * S, fill=HEADER_BG,
        )
        draw.text(
            (tx + PADDING_X * S, ty + 5 * S),
            t.name, fill=HEADER_FG, font=font_bold,
        )

        yo = ty + HEADER_HEIGHT * S
        row_h = COLUMN_HEIGHT * S
        for i, c in enumerate(t.columns):
            bg = COLUMN_BG_ALT if i % 2 else COLUMN_BG
            draw.rectangle([(tx, yo), (tx + tw, yo + row_h)], fill=bg)

            px = tx + 3 * S
            if c.is_pk:
                draw.text((px, yo + 2 * S), "PK", fill=PK_COLOR, font=font_bold)
            elif c.is_fk:
                draw.text((px, yo + 2 * S), "FK", fill=FK_COLOR, font=font_bold)

            draw.text(
                (tx + 22 * S, yo + 2 * S),
                f"{c.name}  {c.col_type}",
                fill=TEXT_COLOR, font=font_small,
            )
            yo += row_h

        draw.rounded_rectangle(
            [(tx, ty), (tx + tw, ty + th)],
            radius=4 * S, outline=BORDER_COLOR, width=max(1, S // 2),
        )

    # Draw edge labels on top of everything
    for mx, my, ft, fc, tt, tc in label_info:
        label = f"{ft}.{fc} → {tt}.{tc}"
        lw = int(font_tiny.getlength(label)) + 4 * S
        lx = mx - lw // 2
        ly = my - 8 * S
        draw.rectangle(
            [(lx, ly - S), (lx + lw, ly + 8 * S)],
            fill="white", outline=FK_COLOR,
        )
        draw.text((lx + 2 * S, ly), label, fill=FK_COLOR, font=font_tiny)

    if S > 1:
        ow = max_x
        oh = max_y
        img = img.resize((ow, oh), Image.LANCZOS)

    img.save(output_path, dpi=(150, 150))
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
