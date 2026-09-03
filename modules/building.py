"""Streamlit UI — Building Modeler (Grid System + Column / Slab mapping).

Workflow:
    1. Define the structural grid (X / Y spacings in metres).
    2. Parse into absolute grid-line coordinates and node (column) coords.
    3. Let the user remove specific columns and mark slab panels as voids
       (openings / stairs / shafts).
    4. Draw the CAD-style plan and stash everything in
       ``st.session_state["building_grid"]`` for the automated gravity
       load-takedown that follows.
"""

import html as _html
import math

import streamlit as st

from utils import ui
from utils.boq import estimate_building_boq
from utils.drawing import draw_3d_building, draw_grid_plan, plan_svg_bytes
from utils.project import render_report_expander

COLUMN_MARKS = ["C1", "C2", "C3", "C4", "C5"]

# Building-Model foundation-type configuration options (id, Thai/EN label).
# This is a MODEL configuration list only — it drives no footing design.
FOUNDATION_TYPES = [
    ("spread", "ฐานรากแผ่ (Spread Footing)"),
    ("pile", "ฐานรากเสาเข็ม (Pile Foundation)"),
]


def _fmt_cell(v):
    """Number -> thousands-separated string, trailing zeros trimmed."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if v != v:                                    # NaN
        return "-"
    if abs(v - round(v)) < 1e-9:
        return f"{v:,.0f}"
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def _html_table(headers, rows, *, right_from=1, emphasize_last=False):
    """Render a table as raw HTML — bypasses ``st.dataframe`` / PyArrow.

    ``right_from`` — first column index that is right-aligned (numeric).
    ``emphasize_last`` — bold + shade the final row (grand-total style).
    """
    def _align(k):
        return "right" if k >= right_from else "left"

    head = "".join(
        f'<th style="text-align:{_align(k)};padding:7px 12px;'
        f'border-bottom:2px solid #475569;white-space:nowrap;'
        f'color:#94a3b8;font-weight:600;">'
        f'{_html.escape(str(h))}</th>'
        for k, h in enumerate(headers)
    )
    body = []
    n = len(rows)
    for ri, row in enumerate(rows):
        last = emphasize_last and ri == n - 1
        row_bg = "#1e3a5f" if last else ("#172033" if ri % 2 else "#0f172a")
        txt = "#f8fafc" if last else "#e2e8f0"
        cells = "".join(
            f'<td style="text-align:{_align(k)};padding:6px 12px;'
            f'border-bottom:1px solid #334155;background:{row_bg};'
            f'color:{txt};{"font-weight:700;" if last else ""}">'
            f'{_html.escape(_fmt_cell(c))}</td>'
            for k, c in enumerate(row)
        )
        body.append(f'<tr>{cells}</tr>')
    st.markdown(
        '<table style="border-collapse:collapse;width:100%;'
        'font-size:0.92rem;margin:0.25rem 0 0.5rem;">'
        f'<thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>',
        unsafe_allow_html=True,
    )


def _parse_spacings(text, fallback):
    """``'4.0, 5.0, 4.0'`` -> ``[0.0, 4.0, 9.0, 13.0]``.

    Comma / semicolon / whitespace separated.  Non-positive or unparseable
    tokens are dropped; an empty result falls back to ``fallback``.
    """
    spacings = []
    for tok in str(text).replace(";", ",").replace("\n", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            val = float(tok)
        except ValueError:
            continue
        if val > 0.0:
            spacings.append(val)
    if not spacings:
        spacings = [float(v) for v in fallback]
    coords = [0.0]
    for s in spacings:
        coords.append(round(coords[-1] + s, 6))
    return coords, spacings


def _grid_label_x(i):
    """0 -> 'A', 1 -> 'B', ... 25 -> 'Z', 26 -> 'AA' ..."""
    s = ""
    i += 1
    while i > 0:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


def _column_labels(nx, ny):
    """Column labels aligned with ``nodes`` (row-major: outer y, inner x)."""
    return [f"{_grid_label_x(i)}-{j + 1}"
            for j in range(ny) for i in range(nx)]


def _panel_items(nx, ny):
    """``(label, (i, j))`` for every panel between consecutive grid lines.

    Panel ``(i, j)`` spans ``x[i]..x[i+1]`` and ``y[j]..y[j+1]``.
    """
    out = []
    for j in range(max(ny - 1, 0)):
        for i in range(max(nx - 1, 0)):
            label = (f"Panel {_grid_label_x(i)}-{_grid_label_x(i + 1)} "
                     f"/ {j + 1}-{j + 2}")
            out.append((label, (i, j)))
    return out


def _calculate_column_loads(x_coords, y_coords, active_columns, void_panels,
                            wu_kgf_m2, col_labels=None):
    """Automated gravity load takedown (tributary-area method).

    Every solid panel ``(i, j)`` gives one quarter of its area to each of
    its four corner nodes.  Void panels contribute nothing.  Quarter-areas
    landing on a removed column are dropped (simplified column takedown).

    Returns ``{(x, y): {"grid": label, "trib_area_m2": A,
    "Pu_kgf": A * Wu}}`` for every active column, keyed by the node coord
    rounded to 3 dp.
    """
    xs = [float(v) for v in x_coords]
    ys = [float(v) for v in y_coords]
    nx, ny = len(xs), len(ys)
    voids = {(int(i), int(j)) for i, j in (void_panels or [])}
    active = {(round(float(px), 3), round(float(py), 3))
              for px, py in active_columns}

    trib = {key: 0.0 for key in active}
    for i in range(nx - 1):
        for j in range(ny - 1):
            if (i, j) in voids:
                continue
            quarter = (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) / 4.0
            for cx, cy in ((xs[i], ys[j]), (xs[i + 1], ys[j]),
                           (xs[i], ys[j + 1]), (xs[i + 1], ys[j + 1])):
                key = (round(cx, 3), round(cy, 3))
                if key in trib:
                    trib[key] += quarter

    label_of = {}
    if col_labels is not None:
        nodes = [(x, y) for y in ys for x in xs]
        for (x, y), lab in zip(nodes, col_labels):
            label_of[(round(x, 3), round(y, 3))] = lab

    wu = float(wu_kgf_m2)
    return {
        key: {
            "grid": label_of.get(key, f"{key[0]:.2f},{key[1]:.2f}"),
            "trib_area_m2": area,
            "Pu_kgf": area * wu,
        }
        for key, area in trib.items()
    }


def _auto_group_columns(column_loads):
    """AI pre-analysis — cluster columns into marks by ``Pu`` magnitude.

    A column within 75 % of the peak load is ``C1`` (heavy), 45–75 % is
    ``C2`` (medium) and anything lighter is ``C3``.  When every column
    carries a similar load the grid naturally collapses to a single mark.

    Returns ``{grid_label: mark}``.
    """
    items = [(info["grid"], float(info["Pu_kgf"]))
             for info in column_loads.values()]
    if not items:
        return {}
    pmax = max(pu for _, pu in items) or 1.0
    marks = {}
    for grid, pu in items:
        ratio = pu / pmax
        if ratio >= 0.75:
            marks[grid] = "C1"
        elif ratio >= 0.45:
            marks[grid] = "C2"
        else:
            marks[grid] = "C3"
    return marks


def _building_levels(n_floors, floor_heights):
    """Storey-level / elevation geometry for the Building Model.

    ``n_floors``      : number of storeys above ground (integer, >= 1)
    ``floor_heights`` : per-storey heights in metres, floor 1 first

    Returns ``(levels, total_height_m)``:
      * ``levels`` — list of ``{"floor": n, "height": h, "elevation": e}``
        where ``elevation`` is the level of the top of storey ``n``
        (cumulative sum of the storey heights, ground = 0.00 m)
      * ``total_height_m`` — sum of every storey height

    Raises ``ValueError`` (Thai message) for an invalid storey count or a
    non-positive storey height.  This is model-geometry / level data only
    — it performs NO load, tributary or structural calculation.
    """
    n = int(n_floors)
    if n < 1:
        raise ValueError("จำนวนชั้นต้องไม่น้อยกว่า 1 ชั้น")
    heights = [float(h) for h in floor_heights]
    if len(heights) != n:
        raise ValueError("จำนวนความสูงชั้นไม่ตรงกับจำนวนชั้น")
    if any(not (h > 0.0) for h in heights):
        raise ValueError("ความสูงชั้นต้องมากกว่า 0 m")
    levels = []
    elevation = 0.0
    for i, h in enumerate(heights, start=1):
        elevation += h
        levels.append({"floor": i, "height": h, "elevation": elevation})
    return levels, elevation


def _building_level_stack(n_floors, floor_heights, foundation_elev=0.0):
    """Full ordered Building-Model level stack — the single source of truth.

    Reuses ``_building_levels`` for the storey elevations (no duplicated
    elevation formula) and prepends the two non-storey reference levels:

        Foundation  -> a model reference datum, NOT counted as a storey
        Level 0     -> ground, elevation 0.00 m
        Floor 1..N  -> one entry per storey, with its own height / elevation

    ``foundation_elev`` is a user reference level (m, may be negative);
    it does NOT feed any footing design.  Returns ``(stack, total_height_m)``
    where each entry is::

        {"id", "name", "floor_number", "height", "elevation",
         "z_bottom", "z_top", "kind"}      kind in reference|datum|floor
    """
    geo, total = _building_levels(n_floors, floor_heights)
    fe = float(foundation_elev)
    stack = [
        {"id": "foundation", "name": "ฐานราก (Foundation)",
         "floor_number": None, "height": None, "elevation": fe,
         "z_bottom": fe, "z_top": 0.0, "kind": "reference"},
        {"id": "level_0", "name": "ระดับพื้นดิน (Level 0)",
         "floor_number": 0, "height": None, "elevation": 0.0,
         "z_bottom": 0.0, "z_top": 0.0, "kind": "datum"},
    ]
    z_bottom = 0.0
    for lv in geo:
        stack.append({
            "id": "floor_%d" % lv["floor"],
            "name": "ชั้น %d" % lv["floor"],
            "floor_number": lv["floor"],
            "height": lv["height"],
            "elevation": lv["elevation"],
            "z_bottom": z_bottom,
            "z_top": lv["elevation"],
            "kind": "floor",
        })
        z_bottom = lv["elevation"]
    return stack, total


def _floor_view_options(level_stack):
    """2D Floor-View dropdown options: Foundation + every storey (no Level 0).

    Returns a list of ``(level_id, level_name)`` in display order.
    """
    return [(lv["id"], lv["name"]) for lv in level_stack
            if lv["kind"] in ("reference", "floor")]


def _resolve_selected_level(level_stack, selected_id, fallback_id="floor_1"):
    """Return the level dict for ``selected_id``; fall back to ``fallback_id``
    (default 'floor_1'), then the first selectable option, then ``None``.

    This is pure UI-view resolution — it never mutates the stack or any
    project / storey data.
    """
    by_id = {lv["id"]: lv for lv in level_stack}
    if selected_id in by_id:
        return by_id[selected_id]
    if fallback_id in by_id:
        return by_id[fallback_id]
    opts = _floor_view_options(level_stack)
    return by_id[opts[0][0]] if opts else None


def _column_size(width_m, length_m):
    """Default column cross-section for the Building Model, in METRES.

    ``width_m``  -> the column dimension along the model **X** axis
    ``length_m`` -> the column dimension along the model **Y** axis
    (fixed mapping — the axes are never swapped)

    Returns ``{"width_m": w, "length_m": l}``.  Raises ``ValueError``
    (Thai) for a non-positive dimension.  This is model GEOMETRY /
    presentation only — it is NEVER fed to any column, footing or other
    structural design calculation.
    """
    w = float(width_m)
    l = float(length_m)
    if not (w > 0.0):
        raise ValueError("ความกว้างเสาต้องมากกว่า 0 m")
    if not (l > 0.0):
        raise ValueError("ความยาวเสาต้องมากกว่า 0 m")
    return {"width_m": w, "length_m": l}


def _column_rectangle(cx, cy, width_m, length_m):
    """True-scale plan rectangle of a column centred on ``(cx, cy)``.

    ``width_m`` is the X extent, ``length_m`` the Y extent (consistent
    with ``_column_size`` — no axis swap).  Returns
    ``(xmin, xmax, ymin, ymax)`` in model coordinates (metres), so the
    2D renderer can draw an actual rectangle rather than a fixed glyph.
    """
    w = float(width_m)
    l = float(length_m)
    return (cx - w / 2.0, cx + w / 2.0, cy - l / 2.0, cy + l / 2.0)


def _beam_size(width_m, depth_m):
    """Default beam cross-section for the Building Model, in METRES.

    ``width_m`` -> horizontal beam width (the dimension seen in a 2D plan)
    ``depth_m`` -> vertical beam depth (into the page in plan; for 3D)

    Returns ``{"width_m": w, "depth_m": d}``.  Raises ``ValueError`` (Thai)
    for a non-positive dimension.  Model GEOMETRY / presentation only — it
    is NEVER fed to any beam / structural design calculation.
    """
    w = float(width_m)
    d = float(depth_m)
    if not (w > 0.0):
        raise ValueError("ความกว้างคานต้องมากกว่า 0 m")
    if not (d > 0.0):
        raise ValueError("ความลึกคานต้องมากกว่า 0 m")
    return {"width_m": w, "depth_m": d}


def _beam_rectangle(x1, y1, x2, y2, width_m):
    """Plan polygon of a beam whose centreline runs ``(x1,y1)->(x2,y2)``.

    Offsets the centreline by ``± width_m / 2`` perpendicular to itself and
    returns the four ``(x, y)`` corners in MODEL coordinates (metres), so
    the renderer draws an actual rectangle — the beam width is real
    geometry, never a renderer line-width.  Works for horizontal, vertical
    or any skew axis-aligned segment.
    """
    w = float(width_m)
    dx = float(x2) - float(x1)
    dy = float(y2) - float(y1)
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return [(float(x1), float(y1))] * 4
    nx, ny = -dy / length, dx / length          # unit perpendicular
    hx, hy = nx * w / 2.0, ny * w / 2.0
    return [(x1 + hx, y1 + hy), (x2 + hx, y2 + hy),
            (x2 - hx, y2 - hy), (x1 - hx, y1 - hy)]


def _generate_beams(x_coords, y_coords, active_columns):
    """Grid-line beams between ADJACENT columns that BOTH exist.

    A beam segment is created along a grid line only where the two end
    nodes are both active columns — no beam is placed without a supporting
    column at each end.  Returns a list of
    ``{"id", "axis", "start": (x, y), "end": (x, y)}`` (axis 'x' or 'y').
    Shared geometry: the same set applies to every storey (the model has
    no per-floor grid differences).
    """
    xs = [float(v) for v in x_coords]
    ys = [float(v) for v in y_coords]
    active = {(round(float(px), 3), round(float(py), 3))
              for px, py in (active_columns or [])}

    def _on(gx, gy):
        return (round(gx, 3), round(gy, 3)) in active

    beams = []
    for j, gy in enumerate(ys):
        for i in range(len(xs) - 1):
            if _on(xs[i], gy) and _on(xs[i + 1], gy):
                beams.append({"id": "bx_%d_%d" % (i, j), "axis": "x",
                              "start": (xs[i], gy), "end": (xs[i + 1], gy)})
    for i, gx in enumerate(xs):
        for j in range(len(ys) - 1):
            if _on(gx, ys[j]) and _on(gx, ys[j + 1]):
                beams.append({"id": "by_%d_%d" % (i, j), "axis": "y",
                              "start": (gx, ys[j]), "end": (gx, ys[j + 1])})
    return beams


# --- Additional (non-grid) beams — Column -> Column, model geometry only ---
def _active_column_centers(nodes, col_labels, active_columns):
    """``{grid label: (x, y)}`` for every ACTIVE column.

    The column picker + geometry source of truth for Additional Beams —
    reads the existing column model, builds no duplicate list.
    """
    active = {(round(float(px), 3), round(float(py), 3))
              for px, py in (active_columns or [])}
    out = {}
    for (x, y), lab in zip(nodes, col_labels):
        if (round(x, 3), round(y, 3)) in active:
            out[lab] = (float(x), float(y))
    return out


def _beam_pair_key(a, b):
    """Undirected key for a column-pair beam — ``C01->C05`` == ``C05->C01``."""
    return tuple(sorted((str(a), str(b))))


def _validate_additional_beam(start_label, end_label, start_level_id,
                              end_level_id, existing_keys):
    """Validate a proposed Column -> Column additional beam.

    Returns ``(ok: bool, message: str)``.  Model-geometry validation only —
    no structural check is performed.
    """
    if start_label == end_label:
        return False, "จุดเริ่มต้นและจุดสิ้นสุดต้องเป็นคนละเสา"
    if start_level_id != end_level_id:
        return False, ("คานเพิ่มเติมในเวอร์ชันนี้ต้องเชื่อมเสาที่อยู่ชั้น"
                       "เดียวกัน")
    if _beam_pair_key(start_label, end_label) in set(existing_keys):
        return False, "มีคานระหว่างเสาคู่นี้อยู่แล้ว"
    return True, ""


def _next_additional_beam_id(existing_beams):
    """``'AB-01'``, ``'AB-02'`` … — never collides with the automatic beam
    ids (``bx_*`` / ``by_*``); keeps ids already assigned."""
    used = 0
    for b in (existing_beams or []):
        _id = str(b.get("id", ""))
        if _id.startswith("AB-"):
            try:
                used = max(used, int(_id[3:]))
            except ValueError:
                pass
    return "AB-%02d" % (used + 1)


def _additional_beam_polys(additional_beams, center_map, level_id,
                           beam_width_m):
    """True-scale plan polygons for the additional beams on ``level_id``
    whose BOTH endpoints are current active columns.

    Reuses ``_beam_rectangle`` — the beam width is real model geometry.
    """
    polys = []
    for b in (additional_beams or []):
        if b.get("level_id") != level_id:
            continue
        s = center_map.get(b.get("start_label"))
        e = center_map.get(b.get("end_label"))
        if s is None or e is None:
            continue
        polys.append(_beam_rectangle(
            s[0], s[1], e[0], e[1],
            float(b.get("width_m", beam_width_m))))
    return polys


def _prune_additional_beams(additional_beams, valid_level_ids, valid_labels):
    """Keep only additional beams on a still-existing floor whose endpoints
    are still active columns.  Returns ``(kept, n_dropped)`` — called when
    the floor count or the column set changes so nothing dangles / crashes.
    """
    kept, dropped = [], 0
    lv = set(valid_level_ids)
    lab = set(valid_labels)
    for b in (additional_beams or []):
        if (b.get("level_id") in lv and b.get("start_label") in lab
                and b.get("end_label") in lab):
            kept.append(b)
        else:
            dropped += 1
    return kept, dropped


def render_building_model():
    ui.breadcrumb("Model", "Building")
    ui.page_header("Building Model",
                   "Structural Building Model & Grid Configuration")
    st.caption(
        "กำหนดระยะเส้นกริดในทิศ X และ Y (เมตร) โปรแกรมจะแปลงเป็นพิกัดสัมบูรณ์ "
        "สร้างตำแหน่งเสาทุกจุดตัดของเส้นกริด ปรับแต่งเสา/ช่องเปิด และวาดผังอาคาร "
        "— เป็นฐานสำหรับการถ่ายน้ำหนักบรรทุกในแนวดิ่งอัตโนมัติ"
    )

    # ==================================================================
    # PART 1 — INPUT  (model configuration only — no engineering design)
    # ==================================================================
    st.markdown("### INPUT")

    # ---- 1. GRID CONFIGURATION --------------------------------------
    with ui.section_card("1. GRID CONFIGURATION — ตั้งค่าเส้นกริด"):
        c1, c2 = st.columns(2)
        with c1:
            x_txt = st.text_input(
                "ระยะเส้นกริดทิศ X (เมตร, คั่นด้วยจุลภาค)",
                value="4.0, 5.0, 4.0", key="bm_x_txt",
                help="เช่น '4.0, 5.0, 4.0'  →  เส้นกริด X ที่ 0, 4, 9, 13 m",
            )
        with c2:
            y_txt = st.text_input(
                "ระยะเส้นกริดทิศ Y (เมตร, คั่นด้วยจุลภาค)",
                value="4.0, 4.0", key="bm_y_txt",
                help="เช่น '4.0, 4.0'  →  เส้นกริด Y ที่ 0, 4, 8 m",
            )
        marker = st.radio(
            "สัญลักษณ์ตำแหน่งเสา (Column marker)",
            ["สี่เหลี่ยม (Square)", "วงกลม (Circle)"],
            horizontal=True, key="bm_marker",
        )

    x_coords, x_sp = _parse_spacings(x_txt, [4.0, 5.0, 4.0])
    y_coords, y_sp = _parse_spacings(y_txt, [4.0, 4.0])
    nx, ny = len(x_coords), len(y_coords)

    # node coordinates for every grid intersection (row-major: y outer)
    nodes = [(x, y) for y in y_coords for x in x_coords]
    col_labels = _column_labels(nx, ny)
    panel_items = _panel_items(nx, ny)
    panel_labels = [lab for lab, _ in panel_items]
    panel_idx = {lab: ij for lab, ij in panel_items}

    # ---- 2. BUILDING LEVELS (geometry / level data only) ----------
    with ui.section_card("2. BUILDING LEVELS — ข้อมูลชั้นอาคาร"):
        n_floors = int(st.number_input(
            "จำนวนชั้น (Number of Floors)", min_value=1, value=3, step=1,
            key="bm_n_floors",
            help="จำนวนชั้นเหนือระดับพื้นดิน — ใช้สร้างเรขาคณิต/ระดับชั้นของ"
                 "แบบจำลองอาคาร (ยังไม่นำไปคำนวณน้ำหนักบรรทุก)",
        ))
        floor_heights = []
        for _row0 in range(0, n_floors, 3):
            _rcols = st.columns(3)
            for _k, _i in enumerate(range(_row0, min(_row0 + 3, n_floors))):
                with _rcols[_k]:
                    _fh = st.number_input(
                        f"ชั้น {_i + 1} — ความสูงชั้น (m)",
                        min_value=0.1,
                        value=3.50 if _i == 0 else 3.20,
                        step=0.1, format="%.2f", key=f"bm_fh_{_i + 1}",
                    )
                floor_heights.append(float(_fh))

        _fnd_elev = float(st.number_input(
            "ระดับอ้างอิงฐานราก (Foundation reference level, m)",
            value=0.00, step=0.10, format="%.2f", key="bm_fnd_elev",
            help="ระดับอ้างอิงของฐานรากเทียบระดับพื้นดิน (0.00 m) — เป็นระดับ"
                 "อ้างอิงของแบบจำลองเท่านั้น ไม่ใช่ความลึกที่ออกแบบแล้ว · "
                 "การออกแบบฐานรากอยู่ที่ ออกแบบชิ้นส่วน → ฐานราก",
        ))

        try:
            _stack, _total_h = _building_level_stack(
                n_floors, floor_heights, foundation_elev=_fnd_elev)
            _levels = [{"floor": lv["floor_number"], "height": lv["height"],
                        "elevation": lv["elevation"]}
                       for lv in _stack if lv["kind"] == "floor"]
            _level_err = None
        except ValueError as _exc:
            _stack, _levels, _total_h, _level_err = [], [], 0.0, str(_exc)

        if _level_err:
            st.error(f"❌ {_level_err}")
        else:
            _html_table(
                ["ระดับ (Level)", "ชั้น", "ความสูงชั้น (m)",
                 "ระดับพื้น (Elevation, m)"],
                [[lv["name"],
                  "" if lv["floor_number"] in (None, 0)
                  else lv["floor_number"],
                  "" if lv["height"] is None else f"{lv['height']:.2f}",
                  f"{lv['elevation']:+.2f}"] for lv in _stack],
                right_from=2,
            )
            st.markdown(
                "**ความสูงอาคารรวม (Total Building Height) ≈ "
                f"{_total_h:.2f} m**"
            )
            st.caption(
                "ฐานราก = ระดับอ้างอิง แยกจากจำนวนชั้นของอาคาร · ระดับพื้นดิน "
                "(Level 0) = 0.00 m · ระดับพื้นแต่ละชั้น = ผลรวมความสูงของชั้น"
                "ที่อยู่ด้านล่าง — เป็นข้อมูลเรขาคณิต/ระดับสำหรับแบบจำลอง 3 มิติ "
                "ไม่ใช้ในการคำนวณน้ำหนักบรรทุกหรือออกแบบฐานราก"
            )

    _levels_state = {
        "number_of_floors": int(n_floors),
        "floor_heights": [lv["height"] for lv in _levels],
        "floor_elevations": [lv["elevation"] for lv in _levels],
        "total_height_m": float(_total_h),
        "levels": _levels,
        "foundation_elevation_m": float(_fnd_elev),
        "level_stack": _stack,
    }
    if _level_err:
        _levels_state["error"] = _level_err

    # ---- 3. FOOTING — foundation type (model configuration only) --
    _fnd_name = dict(FOUNDATION_TYPES)
    with ui.section_card("3. FOOTING — ฐานราก"):
        foundation_type = st.selectbox(
            "ชนิดฐานราก (Foundation Type)",
            [i for i, _ in FOUNDATION_TYPES],
            format_func=lambda i: _fnd_name.get(i, i),
            key="bm_foundation_type",
        )
        st.caption(
            f"Foundation Type: **{_fnd_name[foundation_type]}** · "
            "เป็นการกำหนดชนิดฐานรากของแบบจำลองเท่านั้น — ยังไม่มีการคำนวณ"
            "ขนาดฐานราก กำลังแบกทานดิน จำนวนเสาเข็ม หรือเหล็กเสริม "
            "(การออกแบบฐานรากอยู่ที่ ออกแบบชิ้นส่วน → ฐานราก)"
        )

    # ---- 4. COLUMNS — size + placement (model geometry only) ------
    with ui.section_card("4. COLUMNS — เสา"):
        _cs1, _cs2 = st.columns(2)
        with _cs1:
            _col_w = float(st.number_input(
                "ความกว้างเสา — แกน X (m)", min_value=0.05, value=0.30,
                step=0.05, format="%.2f", key="bm_col_w",
                help="ความกว้างหน้าตัดเสาในทิศ X (เมตร) — ใช้วาดผัง 2D/3D "
                     "ตามมาตราส่วนจริง ไม่ใช้ในการออกแบบเสา",
            ))
        with _cs2:
            _col_l = float(st.number_input(
                "ความยาวเสา — แกน Y (m)", min_value=0.05, value=0.40,
                step=0.05, format="%.2f", key="bm_col_l",
                help="ความยาวหน้าตัดเสาในทิศ Y (เมตร) — แยกจากความกว้าง "
                     "(รองรับเสารูปสี่เหลี่ยมผืนผ้า)",
            ))
        try:
            _col_size = _column_size(_col_w, _col_l)
            _col_size_err = None
        except ValueError as _exc:
            _col_size = {"width_m": 0.30, "length_m": 0.30}
            _col_size_err = str(_exc)
        if _col_size_err:
            st.error(f"❌ {_col_size_err}")
        else:
            st.caption(
                "ขนาดหน้าตัดเสาเริ่มต้นของแบบจำลอง = "
                f"{_col_size['width_m']:.2f} × {_col_size['length_m']:.2f} m "
                f"({_col_size['width_m'] * 1000:.0f} × "
                f"{_col_size['length_m'] * 1000:.0f} mm) · width → X, "
                "length → Y — เป็นเรขาคณิตของแบบจำลอง ไม่ใช่การออกแบบเสา"
            )
        removed = st.multiselect(
            "ลบเสา (Remove Columns)", col_labels, key="bm_removed_cols",
            help="เลือกหมายเลขเสาที่ต้องการลบออกจากผัง",
        )

    # column set — used by section 5 (Additional Beams) and downstream
    removed_set = set(removed)
    active_columns = [
        (x, y) for (x, y), lab in zip(nodes, col_labels)
        if lab not in removed_set
    ]
    _center_map = _active_column_centers(nodes, col_labels, active_columns)
    _floor_lv_opts = [(lid, lname)
                      for lid, lname in _floor_view_options(_stack)
                      if lid != "foundation"]           # V1: no beam at Foundation
    _floor_lv_ids = [lid for lid, _ in _floor_lv_opts]
    _floor_lv_name = dict(_floor_lv_opts)

    # ---- 5. BEAM — size + layout (model geometry only) ----------
    with ui.section_card("5. BEAM — คาน"):
        st.markdown("**Beam Size — ขนาดหน้าตัดคาน**")
        _bs1, _bs2 = st.columns(2)
        with _bs1:
            _beam_w = float(st.number_input(
                "ความกว้างคาน (Beam Width, m)", min_value=0.05, value=0.25,
                step=0.05, format="%.2f", key="bm_beam_w",
                help="ความกว้างคานในแนวราบ — เห็นในผัง 2D ตามมาตราส่วนจริง "
                     "ไม่ใช้ในการออกแบบคาน",
            ))
        with _bs2:
            _beam_d = float(st.number_input(
                "ความลึกคาน (Beam Depth, m)", min_value=0.05, value=0.50,
                step=0.05, format="%.2f", key="bm_beam_d",
                help="ความลึกคานในแนวดิ่ง — เก็บไว้สำหรับแบบจำลอง 3 มิติ "
                     "(แยกจากความกว้าง)",
            ))
        try:
            _beam_sz = _beam_size(_beam_w, _beam_d)
            _beam_err = None
        except ValueError as _exc:
            _beam_sz = {"width_m": 0.25, "depth_m": 0.50}
            _beam_err = str(_exc)
        if _beam_err:
            st.error(f"❌ {_beam_err}")
        else:
            st.caption(
                "ขนาดคานเริ่มต้นของแบบจำลอง = "
                f"{_beam_sz['width_m']:.2f} × {_beam_sz['depth_m']:.2f} m "
                f"({_beam_sz['width_m'] * 1000:.0f} × "
                f"{_beam_sz['depth_m'] * 1000:.0f} mm)"
            )

        st.markdown("**Automatic Beams — คานอัตโนมัติจากเส้นกริด/เสา**")
        st.caption(
            "สร้างอัตโนมัติตามแนวเส้นกริดระหว่างเสาที่มีอยู่ทั้งสองปลาย — "
            "พฤติกรรมเดิม ไม่เปลี่ยนแปลง"
        )

        # keep the additional-beam list valid when floors / columns change
        _ab_state = st.session_state.setdefault("bm_additional_beams", [])
        _ab_state[:], _ab_dropped = _prune_additional_beams(
            _ab_state, _floor_lv_ids, list(_center_map.keys()))
        if _ab_dropped:
            st.warning(
                f"⚠️ ลบคานเพิ่มเติมที่อ้างถึงชั้น/เสาที่ไม่มีแล้ว "
                f"{_ab_dropped} เส้น"
            )

        st.markdown(
            "**Additional Beams — คานเพิ่มเติม (ไม่ต้องอยู่บนเส้นกริด)**"
        )
        st.caption(
            "เพิ่มคานเชื่อมเสา → เสา โดยไม่ต้องสร้างเส้นกริดใหม่ · "
            "เวอร์ชันนี้รองรับ Column → Column ในชั้นเดียวกัน · "
            "เส้นกริดไม่เปลี่ยนแปลง"
        )
        _ab_labels = sorted(_center_map.keys())
        if len(_ab_labels) < 2 or not _floor_lv_ids:
            st.info(
                "ต้องมีเสาที่ใช้งานอย่างน้อย 2 ต้น และมีชั้นอย่างน้อย 1 ชั้น "
                "จึงจะเพิ่มคานเพิ่มเติมได้"
            )
        else:
            _af1, _af2, _af3, _af4 = st.columns([1.3, 1.3, 1.3, 1.0])
            with _af1:
                _ab_lv = st.selectbox(
                    "ชั้น (Level)", _floor_lv_ids,
                    format_func=lambda i: _floor_lv_name.get(i, i),
                    key="bm_ab_lv")
            with _af2:
                _ab_s = st.selectbox("จุดเริ่มต้น (Column)", _ab_labels,
                                     key="bm_ab_start")
            with _af3:
                _ab_e = st.selectbox(
                    "จุดสิ้นสุด (Column)", _ab_labels,
                    index=min(1, len(_ab_labels) - 1), key="bm_ab_end")
            with _af4:
                st.write("")
                _ab_add = st.button("+ เพิ่มคาน", key="bm_ab_add",
                                    use_container_width=True)
            if _ab_add:
                _keys = [_beam_pair_key(b["start_label"], b["end_label"])
                         for b in _ab_state if b["level_id"] == _ab_lv]
                _ok, _msg = _validate_additional_beam(
                    _ab_s, _ab_e, _ab_lv, _ab_lv, _keys)
                if _ok:
                    _ab_state.append({
                        "id": _next_additional_beam_id(_ab_state),
                        "start_label": _ab_s, "end_label": _ab_e,
                        "level_id": _ab_lv,
                        "width_m": float(_beam_sz["width_m"]),
                        "depth_m": float(_beam_sz["depth_m"]),
                    })
                    st.rerun()
                else:
                    st.warning(f"⚠️ {_msg}")

            if _ab_state:
                _dh = st.columns([1.1, 1.9, 1.6, 0.8])
                _dh[0].markdown("**ID**")
                _dh[1].markdown("**เสา → เสา**")
                _dh[2].markdown("**ชั้น**")
                _dh[3].markdown("**ลบ**")
                for _b in list(_ab_state):
                    _rc = st.columns([1.1, 1.9, 1.6, 0.8])
                    _rc[0].write(_b["id"])
                    _rc[1].write(f"{_b['start_label']} → {_b['end_label']}")
                    _rc[2].write(_floor_lv_name.get(_b["level_id"],
                                                   _b["level_id"]))
                    if _rc[3].button("ลบ", key=f"bm_ab_del_{_b['id']}"):
                        _ab_state[:] = [x for x in _ab_state
                                        if x["id"] != _b["id"]]
                        st.rerun()
            else:
                st.caption("ยังไม่มีคานเพิ่มเติม")

    # ---- 6. SLABS — thickness + loads + voids (model config) -----
    with ui.section_card("6. SLABS — พื้น"):
        s1, s2, s3 = st.columns(3)
        with s1:
            slab_t = st.number_input(
                "ความหนาพื้น t (ซม.)", min_value=5.0, value=12.0, step=1.0,
                key="bm_slab_t",
            )
        with s2:
            slab_sdl = st.number_input(
                "SDL (kgf/m²)", min_value=0.0, value=150.0, step=10.0,
                key="bm_slab_sdl",
            )
        with s3:
            slab_ll = st.number_input(
                "LL (kgf/m²)", min_value=0.0, value=250.0, step=10.0,
                key="bm_slab_ll",
            )
        voids = st.multiselect(
            "ช่องเปิด/บันได (Voids)", panel_labels, key="bm_voids",
            help="เลือกแผงพื้นที่เป็นช่องเปิด บันได หรือช่องท่องานระบบ",
        )
        st.caption(
            f"ความหนาพื้น {slab_t:.0f} cm ({slab_t * 10.0:.0f} mm) · "
            "SDL / LL ใช้ในการถ่ายน้ำหนักบรรทุกในแนวดิ่งเท่านั้น"
        )

    # ---- derived model geometry (computation order preserved) ----
    # (removed_set / active_columns / _center_map computed after section 4)
    void_panels = [panel_idx[v] for v in voids if v in panel_idx]

    # automatic (grid-line) beams — unchanged behaviour
    _gen_beams = _generate_beams(x_coords, y_coords, active_columns)
    _gen_polys = [
        _beam_rectangle(bm["start"][0], bm["start"][1],
                        bm["end"][0], bm["end"][1], _beam_sz["width_m"])
        for bm in _gen_beams
    ]
    # additional (non-grid) beams — pruned live list from session state
    _add_beams = list(st.session_state.get("bm_additional_beams", []))
    _lv_elev = {lv["id"]: lv["elevation"]
                for lv in _stack if lv["kind"] == "floor"}

    # ==================================================================
    # PART 2 — MODEL / VISUALIZATION  (all read from the state above)
    # ==================================================================
    st.markdown("### MODEL")

    Wu = 1.2 * (slab_t / 100.0 * 2400.0 + slab_sdl) + 1.6 * slab_ll
    # ---- automated gravity load takedown (unchanged formula) -----
    column_loads = _calculate_column_loads(
        x_coords, y_coords, active_columns, void_panels, Wu, col_labels,
    )

    # 2D floor-view selection state — the selectbox widget itself is
    # rendered in section 8; here we only RESOLVE the current selection so
    # the summary can show it (reading state never mutates the model)
    _view_opts = _floor_view_options(_stack) or [("floor_1", "ชั้น 1")]
    _view_ids = [oid for oid, _ in _view_opts]
    _view_name = dict(_view_opts)
    if st.session_state.get("bm_2d_level") not in _view_ids:
        st.session_state["bm_2d_level"] = (
            "floor_1" if "floor_1" in _view_ids else _view_ids[0])
    _sel_id = st.session_state["bm_2d_level"]
    _sel_level = _resolve_selected_level(_stack, _sel_id)
    _sel_name = _sel_level["name"] if _sel_level else ""
    _sel_elev = _sel_level["elevation"] if _sel_level else 0.0

    # ---- 7. MODEL SUMMARY (READ-ONLY — from building_grid state) --
    st.markdown("#### 7. MODEL SUMMARY")
    with st.container(border=True):
        sc1, sc2 = st.columns([1, 3])
        with sc1:
            st.markdown("**STATUS**")
            ui.status_badge("info", "MODEL GENERATED")
        with sc2:
            st.caption("แบบจำลองเส้นกริดถูกสร้างจากค่าที่ป้อน — ยังไม่มีการ"
                       "วิเคราะห์โครงสร้าง (ถ่ายน้ำหนักในแนวดิ่งด้วยวิธี"
                       "พื้นที่รับน้ำหนักเท่านั้น)")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            ui.kpi("เส้นกริด X × Y", f"{nx} × {ny}")
        with m2:
            ui.kpi("จำนวนชั้น", f"{n_floors}")
        with m3:
            ui.kpi("ความสูงอาคารรวม", f"{_total_h:.2f} m")
        with m4:
            ui.kpi("ชนิดฐานราก",
                   _fnd_name[foundation_type].split(" (")[0])
        m5, m6, m7, m8 = st.columns(4)
        with m5:
            ui.kpi("ขนาดเสา", f"{_col_size['width_m'] * 1000:.0f}×"
                   f"{_col_size['length_m'] * 1000:.0f} mm")
        with m6:
            ui.kpi("ขนาดคาน", f"{_beam_sz['width_m'] * 1000:.0f}×"
                   f"{_beam_sz['depth_m'] * 1000:.0f} mm")
        with m7:
            ui.kpi("ความหนาพื้น", f"{slab_t * 10.0:.0f} mm")
        with m8:
            ui.kpi("ชั้นที่แสดง (2D)", f"{_sel_name} ({_sel_elev:+.2f} m)")
        m9, m10, m11, m12 = st.columns(4)
        with m9:
            ui.kpi("เสาที่ใช้งาน (Active)",
                   f"{len(active_columns)} / {len(nodes)}")
        with m10:
            ui.kpi("คานอัตโนมัติ (Auto)", f"{len(_gen_beams)}")
        with m11:
            ui.kpi("คานเพิ่มเติม (Additional)", f"{len(_add_beams)}")
        with m12:
            ui.kpi("คานรวม (Total)", f"{len(_gen_beams) + len(_add_beams)}")
        m13, m14 = st.columns(4)[:2]
        with m13:
            ui.kpi("ช่องเปิด (Voids)",
                   f"{len(void_panels)} / {len(panel_labels)}")
        with m14:
            ui.kpi("ขนาดอาคารรวม",
                   f"{x_coords[-1]:.2f} × {y_coords[-1]:.2f} m")

    st.markdown(
        "**พิกัดเส้นกริด X (m):** "
        + ", ".join(f"{v:.2f}" for v in x_coords)
        + "  \n**พิกัดเส้นกริด Y (m):** "
        + ", ".join(f"{v:.2f}" for v in y_coords)
        + f"  \n**น้ำหนักบรรทุกพื้นประลัย Wu ≈ {Wu:,.0f} kgf/m²**  "
        f"(1.2·(t·2400 + SDL) + 1.6·LL)"
    )

    # ---- 8. 2D FLOOR PLAN ------------------------------------------
    st.markdown("#### 8. 2D FLOOR PLAN")

    _fv1, _fv2 = st.columns([2, 3])
    with _fv1:
        _sel_id = st.selectbox(
            "แสดงแปลนชั้น (2D Floor View)", _view_ids,
            format_func=lambda i: _view_name.get(i, i),
            key="bm_2d_level",
        )
    _sel_level = _resolve_selected_level(_stack, _sel_id)
    _sel_name = _sel_level["name"] if _sel_level else ""
    _sel_elev = _sel_level["elevation"] if _sel_level else 0.0
    with _fv2:
        if _sel_level is not None:
            st.caption(
                f"แสดงชั้น: **{_sel_name}**  ·  "
                f"Elevation: **{_sel_elev:+.2f} m**"
            )

    st.markdown(
        f"**2D FLOOR PLAN** · {_sel_name} · Elevation {_sel_elev:+.2f} m"
    )
    _is_fnd = bool(_sel_level and _sel_level["kind"] == "reference")
    # Foundation view: no beams (no fabricated foundation geometry)
    _plan_polys = None if _is_fnd else _gen_polys
    # additional beams: only those on the currently selected storey
    _extra_polys = ([] if _is_fnd or _sel_level is None
                    else _additional_beam_polys(
                        _add_beams, _center_map, _sel_level["id"],
                        _beam_sz["width_m"]))
    fig = draw_grid_plan(
        x_coords, y_coords,
        marker="circle" if str(marker).startswith("วง") else "square",
        active_columns=active_columns, void_panels=void_panels,
        column_loads=column_loads,
        column_size=_col_size, level_label=_sel_name,
        beam_polys=_plan_polys, extra_beam_polys=_extra_polys,
    )
    # keep the on-screen drawing to a moderate width — geometry / scale
    # are unchanged, only the displayed image is smaller
    _plcol, _ = st.columns([5, 3])
    with _plcol:
        st.pyplot(fig, use_container_width=True)
        try:
            _svg = plan_svg_bytes(fig)
            st.download_button(
                "⬇️ ดาวน์โหลดผัง 2D (SVG เวกเตอร์ — ซูมได้คมชัด)",
                data=_svg, file_name="building_floor_plan.svg",
                mime="image/svg+xml", key="bm_plan_svg",
            )
        except Exception:  # pragma: no cover - export must not break page
            pass
    if _sel_level is not None and _sel_level["kind"] == "reference":
        st.caption(
            "มุมมองระดับฐานราก (Foundation) — แสดงผังเส้นกริดและขอบเขตอาคาร"
            "ที่ระดับอ้างอิงฐานราก · แบบจำลองนี้ยังไม่มีเรขาคณิตฐานรากจริง "
            "(การออกแบบฐานรากอยู่ที่ ออกแบบชิ้นส่วน → ฐานราก)"
        )
    else:
        st.caption(
            f"ผังเส้นกริด เสา คาน แผ่นพื้น และแรงถ่ายลงเสา — "
            f"{(_sel_level or {}).get('name', '')} · "
            f"เสา {_col_size['width_m']:.2f}×{_col_size['length_m']:.2f} m · "
            f"คานอัตโนมัติ {len(_gen_polys)} · คานเพิ่มเติมชั้นนี้ "
            f"{len(_extra_polys)} · กว้าง {_beam_sz['width_m']:.2f} m "
            "(มาตราส่วนจริง · เส้นกริดใช้ร่วมกันทุกชั้น ไม่มีการเพิ่มเส้นกริด)"
        )

    # ---- 9. 3D MODEL --------------------------------------------
    st.markdown("#### 9. 3D MODEL")
    with st.expander("🧊 โมเดลอาคาร 3 มิติ (3D Viewer)", expanded=False):
        _elevs3d = list(_levels_state.get("floor_elevations") or [])
        _lbls3d = (["ระดับพื้นดิน (Level 0)"]
                   + [f"ชั้น {lv['floor']}" for lv in _levels])
        # additional beams -> 3D line segments at their storey elevation
        _ab_3d = []
        for _b in _add_beams:
            _s = _center_map.get(_b.get("start_label"))
            _e = _center_map.get(_b.get("end_label"))
            _z = _lv_elev.get(_b.get("level_id"))
            if _s is not None and _e is not None and _z is not None:
                _ab_3d.append((_s[0], _s[1], _e[0], _e[1], float(_z)))
        try:
            if _elevs3d:
                fig_3d = draw_3d_building(
                    active_columns, void_panels, x_coords, y_coords,
                    floor_elevations=_elevs3d,
                    foundation_elev=_levels_state.get("foundation_elevation_m"),
                    level_labels=_lbls3d, column_size=_col_size,
                    extra_beams=_ab_3d,
                )
                _cap3d = (
                    f"{n_floors} ชั้น · ความสูงอาคารรวม "
                    f"{_levels_state['total_height_m']:.2f} m · แบ่งระดับที่ "
                    + ", ".join(f"{e:.2f}" for e in _elevs3d)
                    + f" m · คานเพิ่มเติม {len(_ab_3d)} เส้น"
                    + " — ลากเมาส์เพื่อหมุน / สกรอลล์เพื่อซูม"
                )
            else:
                fig_3d = draw_3d_building(
                    active_columns, void_panels, x_coords, y_coords,
                    floor_height_m=float(
                        st.session_state.get("bm_boq_fh", 3.0)),
                )
                _cap3d = "ลากเมาส์เพื่อหมุน / สกรอลล์เพื่อซูม"
            st.plotly_chart(fig_3d, use_container_width=True)
            st.caption(_cap3d)
        except ImportError:
            st.warning(
                "ยังไม่ได้ติดตั้งไลบรารี Plotly — ติดตั้งด้วยคำสั่ง "
                "`pip install plotly` แล้วรีสตาร์ทแอป"
            )

    # ---- MODEL DATA & ESTIMATES (existing functionality — kept) --
    st.markdown("#### MODEL DATA & ESTIMATES")
    with st.expander("📊 วิเคราะห์แรงถ่ายลงเสา (Column Load Takedown)",
                     expanded=True):
        load_rows = []
        tot = 0.0
        for (x, y), lab in zip(nodes, col_labels):
            info = column_loads.get((round(x, 3), round(y, 3)))
            if info is None:
                continue
            tot += info["Pu_kgf"]
            load_rows.append([
                lab,
                round(info["trib_area_m2"], 3),
                round(info["Pu_kgf"], 0),
            ])
        _html_table(
            ["ตำแหน่งเสา (Grid)", "พื้นที่รับน้ำหนัก (m²)",
             "แรงตามแนวแกน Pu (kgf)"],
            load_rows, right_from=1,
        )
        st.caption(
            f"ผลรวมแรงถ่ายลงเสาทั้งหมด ≈ {tot:,.0f} kgf ({tot / 1000.0:,.1f} t) "
            f"· วิธีพื้นที่รับน้ำหนัก (Tributary Area Method)"
        )

    # ---- automated column grouping (AI pre-analysis) -------------
    ai_marks = _auto_group_columns(column_loads)
    design_groups = {}
    with st.expander("🏷️ จัดกลุ่มเบอร์เสา (Column Grouping)", expanded=True):
        st.caption(
            "AI แนะนำเบอร์เสาเบื้องต้นตามขนาดของ Pu — "
            "ปรับ 'เบอร์เสา (Mark)' ของแต่ละแถวได้ตามต้องการ"
        )
        grp_src = []                      # (grid_label, Pu_kgf, ai_mark)
        for (x, y), lab in zip(nodes, col_labels):
            info = column_loads.get((round(x, 3), round(y, 3)))
            if info is None:
                continue
            grp_src.append((lab, round(float(info["Pu_kgf"]), 0),
                            ai_marks.get(lab, "C1")))

        if grp_src:
            hc = st.columns([1.1, 1.6, 1.3])
            hc[0].markdown("**Grid**")
            hc[1].markdown("**Pu (kgf)**")
            hc[2].markdown("**เบอร์เสา (Mark)**")

            selected = {}
            for lab, pu, ai in grp_src:
                rc = st.columns([1.1, 1.6, 1.3])
                rc[0].write(lab)
                rc[1].write(f"{pu:,.0f}")
                idx = COLUMN_MARKS.index(ai) if ai in COLUMN_MARKS else 0
                selected[lab] = rc[2].selectbox(
                    "เบอร์เสา (Mark)", COLUMN_MARKS, index=idx,
                    key=f"bm_mark_{lab}", label_visibility="collapsed",
                )

            gov = {}                       # mark -> [grid, max_pu]
            for lab, pu, _ai in grp_src:
                mark = selected[lab]
                if mark not in gov or pu > gov[mark][1]:
                    gov[mark] = [lab, pu]
            summary_rows = sorted(
                ([m, g, round(p, 0)] for m, (g, p) in gov.items()),
                key=lambda r: -r[2],
            )

            st.markdown(
                "**สรุปแรงควบคุมการออกแบบต่อเบอร์เสา "
                "(Governing Load per Mark)**"
            )
            _html_table(["Mark", "Governing Grid", "Max Pu (kgf)"],
                        summary_rows, right_from=2)
            design_groups = {
                r[0]: {"governing_grid": r[1], "Pu_kgf": r[2]}
                for r in summary_rows
            }
            st.info(
                "➡️ เปิดเมนู **เสา (Column)** เพื่อออกแบบหน้าตัดตามมาตรฐาน "
                "ACI 318M-08 (P-M Interaction) — ในหน้านั้นเลือกเบอร์เสา "
                "แล้วโปรแกรมจะเติมค่า Pu ให้อัตโนมัติ"
            )
        else:
            st.info("ยังไม่มีเสาให้จัดกลุ่ม")

    st.session_state["column_design_groups"] = design_groups

    with st.expander("ตารางพิกัดเสา (Node Coordinates)", expanded=False):
        node_rows = [
            [lab, round(x, 3), round(y, 3),
             "ลบออก" if lab in removed_set else "ใช้งาน"]
            for (x, y), lab in zip(nodes, col_labels)
        ]
        _html_table(["เส้นกริด (Grid)", "x (m)", "y (m)", "สถานะ"],
                    node_rows, right_from=1)

    # ---- 3. stash for the automated load takedown ----------------
    st.session_state["building_grid"] = {
        "x_coords": x_coords,
        "y_coords": y_coords,
        "x_spacings": x_sp,
        "y_spacings": y_sp,
        "nodes": nodes,
        "column_labels": col_labels,
        "panel_labels": panel_labels,
        "active_columns": active_columns,
        "removed_columns": list(removed),
        "void_panels": void_panels,
        "void_panel_labels": list(voids),
        "column_loads": {
            info["grid"]: {
                "xy": list(key),
                "trib_area_m2": info["trib_area_m2"],
                "Pu_kgf": info["Pu_kgf"],
            }
            for key, info in column_loads.items()
        },
        "slab": {
            "t_cm": float(slab_t),
            "sdl_kgf_m2": float(slab_sdl),
            "ll_kgf_m2": float(slab_ll),
            "wu_kgf_m2": float(Wu),
        },
        "levels": _levels_state,
        "column_size": {
            "width_m": float(_col_size["width_m"]),
            "length_m": float(_col_size["length_m"]),
        },
        "beam_size": {
            "width_m": float(_beam_sz["width_m"]),
            "depth_m": float(_beam_sz["depth_m"]),
        },
        "beams": [
            {"id": bm["id"], "axis": bm["axis"],
             "start": [float(bm["start"][0]), float(bm["start"][1])],
             "end": [float(bm["end"][0]), float(bm["end"][1])]}
            for bm in _gen_beams
        ],
        "additional_beams": [
            {"id": b["id"], "start_label": b["start_label"],
             "end_label": b["end_label"], "level_id": b["level_id"],
             "width_m": float(b.get("width_m", _beam_sz["width_m"])),
             "depth_m": float(b.get("depth_m", _beam_sz["depth_m"])),
             "start": list(_center_map.get(b["start_label"], (0.0, 0.0))),
             "end": list(_center_map.get(b["end_label"], (0.0, 0.0)))}
            for b in _add_beams
        ],
        "foundation_type": foundation_type,
    }

    # ---- 4. building-wide BOQ estimate ---------------------------
    with st.expander("📊 ถอดปริมาณวัสดุโครงสร้าง (BOQ Estimate)",
                     expanded=False):
        b1, b2, b3 = st.columns(3)
        with b1:
            fh_m = st.number_input("ความสูงชั้น (m)", min_value=2.0,
                                   value=3.0, step=0.1, key="bm_boq_fh")
        with b2:
            col_b = st.number_input("หน้าตัดเสาเฉลี่ย b (cm)", min_value=15.0,
                                    value=20.0, step=1.0, key="bm_boq_cb")
            beam_b = st.number_input("หน้าตัดคานเฉลี่ย b (cm)", min_value=15.0,
                                     value=20.0, step=1.0, key="bm_boq_bb")
        with b3:
            col_h = st.number_input("หน้าตัดเสาเฉลี่ย h (cm)", min_value=15.0,
                                    value=20.0, step=1.0, key="bm_boq_ch")
            beam_h = st.number_input("หน้าตัดคานเฉลี่ย h (cm)", min_value=20.0,
                                     value=40.0, step=1.0, key="bm_boq_bh")
        st.caption(
            f"ความหนาพื้น t = {slab_t:.0f} cm (จากหัวข้อ INPUT → 6. SLABS) · "
            f"ความลึกคานสุทธิใต้พื้น = {max(beam_h - slab_t, 0):.0f} cm"
        )

        if st.button("คำนวณ BOQ", key="bm_boq_run"):
            st.session_state["bm_boq_result"] = estimate_building_boq(
                active_columns, void_panels, x_coords, y_coords,
                floor_height_m=fh_m, col_b=col_b, col_h=col_h,
                beam_b=beam_b, beam_h=beam_h, slab_t=slab_t,
            )

        boq = st.session_state.get("bm_boq_result")
        if boq:
            tot = boq["total"]
            k1, k2, k3 = st.columns(3)
            k1.metric("ปริมาตรคอนกรีตรวม (ลบ.ม.)",
                      f"{tot['concrete_m3']:,.2f}")
            k2.metric("พื้นที่ไม้แบบรวม (ตร.ม.)",
                      f"{tot['formwork_m2']:,.1f}")
            k3.metric("เหล็กเสริมโดยประมาณรวม (กก.)",
                      f"{tot['rebar_kg']:,.0f}")
            _boq_tbl = boq["table"]
            _boq_head = list(_boq_tbl[0].keys()) if _boq_tbl else []
            _html_table(
                _boq_head,
                [[r.get(h) for h in _boq_head] for r in _boq_tbl],
                right_from=1, emphasize_last=True,
            )
            st.caption(
                f"จำนวนเสา {boq['columns']['count']} ต้น · "
                f"ความยาวคานรวม {boq['beams']['length_m']:,.1f} m · "
                f"พื้นที่พื้นตัน {boq['slab']['area_m2']:,.1f} m² — "
                "อัตราส่วนเหล็กเสริม เสา 150 / คาน 120 / พื้น 90 กก./ลบ.ม. "
                "(ค่าประมาณเบื้องต้นสำหรับงบประมาณ)"
            )
            st.session_state["building_grid"]["boq"] = boq
        else:
            st.info("กรอกขนาดหน้าตัดแล้วกดปุ่ม 'คำนวณ BOQ'")

    # ---- Building Model PDF report (model + BOQ, status = MODEL) --
    st.markdown("#### BUILDING MODEL REPORT (PDF)")
    total_solid_area = boq["slab"]["area_m2"] if boq else 0.0
    _all_add_polys = [
        _beam_rectangle(*_center_map.get(b["start_label"], (0.0, 0.0)),
                        *_center_map.get(b["end_label"], (0.0, 0.0)),
                        float(b.get("width_m", _beam_sz["width_m"])))
        for b in _add_beams
        if b["start_label"] in _center_map and b["end_label"] in _center_map
    ]
    report_fig = draw_grid_plan(
        x_coords, y_coords,
        marker="circle" if str(marker).startswith("วง") else "square",
        active_columns=active_columns, void_panels=void_panels,
        column_loads=column_loads, column_size=_col_size,
        beam_polys=_gen_polys, extra_beam_polys=_all_add_polys,
    )
    render_report_expander(
        key="bm_report",
        filename="building_model_boq_report.pdf",
        title="รายงานแบบจำลองอาคารและประมาณราคา "
              "(Building Model & BOQ Report)",
        params=[
            ("ระบบเส้นกริด X × Y (Grid lines)", f"{nx} × {ny}"),
            ("ขนาดอาคารรวม (Overall size)",
             f"{x_coords[-1]:.2f} × {y_coords[-1]:.2f}", "m"),
            ("จำนวนเสาที่ใช้งาน (Active columns)",
             len(active_columns), "ต้น", 0),
            ("จำนวนช่องเปิด (Voids)", len(void_panels), "แผง", 0),
            ("ความสูงชั้น (Floor height)", fh_m, "m", 2),
            ("จำนวนชั้น (Number of floors)", n_floors, "ชั้น", 0),
            ("ความสูงอาคารรวม (Total building height)",
             _levels_state["total_height_m"], "m", 2),
            ("หน้าตัดเสาเฉลี่ย (Column b × h)",
             f"{col_b:.0f} × {col_h:.0f}", "cm"),
            ("หน้าตัดคานเฉลี่ย (Beam b × h)",
             f"{beam_b:.0f} × {beam_h:.0f}", "cm"),
            ("ความหนาพื้น (Slab thickness)", slab_t, "cm", 0),
            ("น้ำหนักบรรทุกพื้นประลัย (Wu)", Wu, "kgf/m²", 0),
            ("พื้นที่พื้นตันรวม (Total solid area)",
             total_solid_area, "m²", 1),
        ],
        figures=[("ผังแรงถ่ายลงเสา (Column Load Map)", report_fig)],
        boq_dataframe=(boq["table"] if boq else None),
        # Presentation only: the Building Model is a grid + gravity-takedown +
        # BOQ output, NOT a structural design check.  "MODEL" makes the PDF
        # verdict read "MODEL GENERATED" instead of a design "PASS".
        status="MODEL",
        summary="ประมาณการปริมาณวัสดุโครงสร้าง (คอนกรีต ไม้แบบ เหล็กเสริม) "
                "จากแบบจำลองเส้นกริด ด้วยวิธีพื้นที่รับน้ำหนัก — "
                "สำหรับงบประมาณเบื้องต้นเท่านั้น",
    )

    # ==================================================================
    # PART 3 — OUTPUT  (member design results — NOT model configuration)
    # ==================================================================
    st.markdown("### OUTPUT")
    st.caption(
        "ผลการออกแบบสมาชิกตามมาตรฐาน ACI 318M-08 — ทำที่เมนู ออกแบบชิ้นส่วน "
        "(Member Design) ของแต่ละประเภท · Building Model กำหนดเฉพาะเรขาคณิต/"
        "การจัดวาง ไม่ได้ออกแบบสมาชิก · ค่าในส่วนนี้เป็นแบบอ่านอย่างเดียว"
    )

    with st.expander("1. FOOTING — ฐานราก", expanded=False):
        st.markdown(
            f"**ชนิดฐานราก (แบบจำลอง):** {_fnd_name[foundation_type]}"
        )
        st.info(
            "ยังไม่มีผลการออกแบบฐานราก — Building Model มีเพียงชนิดฐานราก "
            "ยังไม่มีขนาด กำลังแบกทานดิน จำนวนเสาเข็ม หรือเหล็กเสริม · "
            "ออกแบบที่ ออกแบบชิ้นส่วน → ฐานราก"
        )

    with st.expander("2. COLUMNS — เสา", expanded=False):
        if design_groups:
            st.markdown("**เบอร์เสาที่จัดกลุ่มไว้ (จาก Building Model):**")
            _html_table(
                ["Mark", "Governing Grid", "Max Pu (kgf)"],
                [[m, d["governing_grid"], f"{d['Pu_kgf']:,.0f}"]
                 for m, d in design_groups.items()],
                right_from=2,
            )
        st.info(
            "ยังไม่มีผลการออกแบบเสา — ขนาดเสาในส่วน INPUT เป็นเรขาคณิตของ"
            "แบบจำลอง · การออกแบบ P-M interaction / เหล็กเสริม ทำที่ "
            "ออกแบบชิ้นส่วน → เสา"
        )

    with st.expander("3. BEAM — คาน", expanded=False):
        st.markdown(
            f"**คานในแบบจำลอง:** อัตโนมัติ {len(_gen_beams)} · "
            f"เพิ่มเติม {len(_add_beams)} · "
            f"รวม {len(_gen_beams) + len(_add_beams)} เส้น "
            f"(ขนาด {_beam_sz['width_m'] * 1000:.0f}×"
            f"{_beam_sz['depth_m'] * 1000:.0f} mm)"
        )
        if isinstance(st.session_state.get("_beam_summary"), dict):
            st.markdown(
                "**มีการเปิดหน้าออกแบบคานแล้ว** — ดูผล/สถานะได้ที่ "
                "ออกแบบชิ้นส่วน → คาน (Building Model ไม่แสดง/ไม่คำนวณผลซ้ำ)"
            )
        st.info(
            "ยังไม่มีผลการออกแบบคานในหน้านี้ — ขนาด/ตำแหน่งคานในส่วน INPUT "
            "เป็นเรขาคณิตของแบบจำลอง · การออกแบบ Mu / Vu / As / เหล็กปลอก "
            "ทำที่ ออกแบบชิ้นส่วน → คาน"
        )

    with st.expander("4. SLABS — พื้น", expanded=False):
        st.markdown(
            f"**ความหนาพื้น (แบบจำลอง):** {slab_t:.0f} cm "
            f"({slab_t * 10.0:.0f} mm)"
        )
        st.info(
            "ยังไม่มีผลการออกแบบพื้น — ความหนาพื้นเป็นข้อมูลแบบจำลอง/"
            "การถ่ายน้ำหนัก · การออกแบบการดัด/เหล็กเสริม ทำที่ "
            "ออกแบบชิ้นส่วน → พื้น"
        )

    with st.expander("5. STAIR — บันได", expanded=False):
        st.info(
            "ยังไม่มีผลการออกแบบบันได — Building Model ยังไม่มีเรขาคณิตบันได · "
            "การออกแบบบันได ทำที่ ออกแบบชิ้นส่วน → บันได"
        )
