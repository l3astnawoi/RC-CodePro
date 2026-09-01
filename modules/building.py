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

import streamlit as st

from utils.boq import estimate_building_boq
from utils.drawing import draw_3d_building, draw_grid_plan
from utils.project import render_report_expander

COLUMN_MARKS = ["C1", "C2", "C3", "C4", "C5"]


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


def render_building_model():
    st.title("จำลองอาคาร — ระบบเส้นกริด (Building Model — Grid System)")
    st.caption(
        "กำหนดระยะเส้นกริดในทิศ X และ Y (เมตร) โปรแกรมจะแปลงเป็นพิกัดสัมบูรณ์ "
        "สร้างตำแหน่งเสาทุกจุดตัดของเส้นกริด ปรับแต่งเสา/ช่องเปิด และวาดผังอาคาร "
        "— เป็นฐานสำหรับการถ่ายน้ำหนักบรรทุกในแนวดิ่งอัตโนมัติ"
    )

    # ---- 1. grid setup ------------------------------------------------
    with st.expander("ตั้งค่าเส้นกริด (Grid Setup)", expanded=True):
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

    # ---- 2. column / slab mapping ----------------------------------
    with st.expander("🏗️ ปรับแต่งเสาและแผ่นพื้น (Columns & Slabs)",
                     expanded=True):
        removed = st.multiselect(
            "ลบเสา (Remove Columns)", col_labels, key="bm_removed_cols",
            help="เลือกหมายเลขเสาที่ต้องการลบออกจากผัง",
        )

        st.markdown("**คุณสมบัติแผ่นพื้นรวม (Global Slab Properties)**")
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

    removed_set = set(removed)
    active_columns = [
        (x, y) for (x, y), lab in zip(nodes, col_labels)
        if lab not in removed_set
    ]
    void_panels = [panel_idx[v] for v in voids if v in panel_idx]

    # ---- summary ---------------------------------------------------
    st.subheader("สรุปโครงข่ายเส้นกริด")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("เส้นกริด X × Y", f"{nx} × {ny}")
    m2.metric("เสาที่ใช้งาน (Active)", f"{len(active_columns)} / {len(nodes)}")
    m3.metric("ช่องเปิด (Voids)", f"{len(void_panels)} / {len(panel_labels)}")
    m4.metric("ขนาดอาคารรวม", f"{x_coords[-1]:.2f} × {y_coords[-1]:.2f} m")

    Wu = 1.2 * (slab_t / 100.0 * 2400.0 + slab_sdl) + 1.6 * slab_ll
    st.markdown(
        "**พิกัดเส้นกริด X (m):** "
        + ", ".join(f"{v:.2f}" for v in x_coords)
        + "  \n**พิกัดเส้นกริด Y (m):** "
        + ", ".join(f"{v:.2f}" for v in y_coords)
        + f"  \n**น้ำหนักบรรทุกพื้นประลัย Wu ≈ {Wu:,.0f} kgf/m²**  "
        f"(1.2·(t·2400 + SDL) + 1.6·LL)"
    )

    # ---- automated gravity load takedown -------------------------
    column_loads = _calculate_column_loads(
        x_coords, y_coords, active_columns, void_panels, Wu, col_labels,
    )

    fig = draw_grid_plan(
        x_coords, y_coords,
        marker="circle" if str(marker).startswith("วง") else "square",
        active_columns=active_columns, void_panels=void_panels,
        column_loads=column_loads,
    )
    st.pyplot(fig, use_container_width=True)
    st.caption("ผังเส้นกริด เสา แผ่นพื้น และแรงถ่ายลงเสา (Column Load Map)")

    with st.expander("🧊 โมเดลอาคาร 3 มิติ (3D Viewer)", expanded=False):
        fh_3d = float(st.session_state.get("bm_boq_fh", 3.0))
        try:
            fig_3d = draw_3d_building(
                active_columns, void_panels, x_coords, y_coords,
                floor_height_m=fh_3d,
            )
            st.plotly_chart(fig_3d, use_container_width=True)
            st.caption(
                f"ความสูงชั้น {fh_3d:.2f} m — ลากเมาส์เพื่อหมุน / สกรอลล์เพื่อซูม "
                "(ปรับความสูงได้ในหัวข้อ BOQ Estimate)"
            )
        except ImportError:
            st.warning(
                "ยังไม่ได้ติดตั้งไลบรารี Plotly — ติดตั้งด้วยคำสั่ง "
                "`pip install plotly` แล้วรีสตาร์ทแอป"
            )

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
            f"ความหนาพื้น t = {slab_t:.0f} cm (จากหัวข้อ Columns & Slabs) · "
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

    # ---- 5. combined analysis + BOQ PDF report ------------------
    total_solid_area = boq["slab"]["area_m2"] if boq else 0.0
    report_fig = draw_grid_plan(
        x_coords, y_coords,
        marker="circle" if str(marker).startswith("วง") else "square",
        active_columns=active_columns, void_panels=void_panels,
        column_loads=column_loads,
    )
    render_report_expander(
        key="bm_report",
        filename="building_analysis_boq_report.pdf",
        title="รายงานวิเคราะห์โครงสร้างอาคารและประมาณราคา "
              "(Building Analysis & BOQ Report)",
        params=[
            ("ระบบเส้นกริด X × Y (Grid lines)", f"{nx} × {ny}"),
            ("ขนาดอาคารรวม (Overall size)",
             f"{x_coords[-1]:.2f} × {y_coords[-1]:.2f}", "m"),
            ("จำนวนเสาที่ใช้งาน (Active columns)",
             len(active_columns), "ต้น", 0),
            ("จำนวนช่องเปิด (Voids)", len(void_panels), "แผง", 0),
            ("ความสูงชั้น (Floor height)", fh_m, "m", 2),
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
        status="PASS",
        summary="ประมาณการปริมาณวัสดุโครงสร้าง (คอนกรีต ไม้แบบ เหล็กเสริม) "
                "จากแบบจำลองเส้นกริด ด้วยวิธีพื้นที่รับน้ำหนัก — "
                "สำหรับงบประมาณเบื้องต้นเท่านั้น",
    )
