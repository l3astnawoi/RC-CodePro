"""RC CodePro — RC structure design to ACI 318M-08 (Thai UI, MKS units).

Application shell: a branded icon navigation rail (``st.navigation`` +
``st.logo``), a slim top header, a read-only project card in the sidebar,
and each design module rendered as its own page.  The Home page is a
read-only Project Control Center — it reads ``st.session_state`` only and
never runs a calculation, builds a figure or generates a report.
"""

import streamlit as st

from utils import ui
from utils.project import (DESIGN_CODE, DESIGN_UNITS, ensure_project_state,
                           get_project_info, render_project_page)

APP_TITLE = "RC CodePro"
CODE_REFERENCE = "ACI 318M-08"
UNITS_LABEL = "MKS"
LOGO = "assets/logo.svg"

# Populated in main() before pg.run(); read by _home() for st.page_link.
_PAGES: dict = {}


# ---------------------------------------------------------------------------
# Home — Project Control Center (read-only dashboard)
# ---------------------------------------------------------------------------
def _module_status_rows():
    """Derive per-module status STRICTLY from existing session_state.

    Presence of a persisted result key => 'Calculated'.  A PASS/FAIL
    verdict is shown only where a real verdict is already stored (Beam).
    Column / Slab / Footing / Stair leave no cross-page result in
    session_state, so they honestly read 'Not calculated'.
    """
    ss = st.session_state
    rows = []

    beam = ss.get("_beam_summary")
    if isinstance(beam, dict):
        verdict = "pass" if beam.get("passed") else "fail"
        verdict_txt = "PASS" if beam.get("passed") else "FAIL"
        note = "Analysis + Design" if "beam_diag" in ss else "Design"
        rows.append(("Beam", True, verdict, verdict_txt, note))
    else:
        rows.append(("Beam", False, None, None, ""))

    for name in ("Column", "Slab", "Footing", "Stair"):
        rows.append((name, False, None, None, ""))

    grid = ss.get("building_grid")
    if isinstance(grid, dict):
        n_nodes = len(grid.get("nodes", []))
        n_active = len(grid.get("active_columns", []))
        boq = "BOQ ✓" if ss.get("bm_boq_result") else "BOQ —"
        grouping = "Grouping ✓" if ss.get("column_design_groups") else "Grouping —"
        rows.append(("Building Model", True, None, None,
                     f"{n_active}/{n_nodes} columns · {boq} · {grouping}"))
    else:
        rows.append(("Building Model", False, None, None, ""))

    return rows


def _home():
    ui.page_header(
        "RC CodePro",
        "Structural Design & Analysis — Project Control Center",
        crumbs=("ภาพรวม (Overview)", "หน้าหลัก (Home)"),
    )

    info = get_project_info()
    status_rows = _module_status_rows()
    n_calculated = sum(1 for r in status_rows if r[1])
    n_attention = sum(1 for r in status_rows if r[1] and r[2] == "fail")
    project_state = "IN PROGRESS" if n_calculated else "NOT STARTED"

    # ---- Project summary + edit link --------------------------------
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        ui.project_summary(
            [
                ("Project", info["project_name"]),
                ("Engineer", info["engineer"]),
                ("Location", info["location"]),
                ("Date", info["date"]),
                ("Design code", DESIGN_CODE),
                ("Units", DESIGN_UNITS),
            ],
            title="PROJECT",
        )
    with sc2:
        with st.container(border=True):
            st.markdown("**DESIGN STANDARD**")
            st.caption(f"{DESIGN_CODE}  ·  {DESIGN_UNITS}")
            if "project" in _PAGES:
                st.page_link(_PAGES["project"], label="Edit Project",
                             icon=":material/edit:")

    # ---- KPI row --------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Design modules", len(status_rows), border=True)
    k2.metric("Calculated", n_calculated, border=True)
    k3.metric("Needs attention", n_attention, border=True)
    k4.metric("Project status", project_state, border=True)

    # ---- Quick design ----------------------------------------
    st.markdown("#### QUICK DESIGN")
    quick = [
        ("beam", "BEAM", "Continuous beam — flexure & shear"),
        ("column", "COLUMN", "Axial + P–M interaction"),
        ("slab", "SLAB", "One-way / two-way slab"),
        ("footing", "FOOTING", "Isolated & pile cap"),
        ("stair", "STAIR", "Straight & U-shape"),
        ("building", "BUILDING MODEL", "Grid · load takedown · BOQ · 3D"),
    ]
    for r in range(0, len(quick), 3):
        cols = st.columns(3)
        for col, (pk, title, sub) in zip(cols, quick[r:r + 3]):
            with col:
                if pk in _PAGES:
                    ui.nav_card(_PAGES[pk], title, sub, open_label="Open")
                else:  # pragma: no cover - defensive
                    with st.container(border=True):
                        st.markdown(f"**{title}**")
                        st.caption(sub)

    # ---- Design status --------------------------------------
    st.markdown("#### DESIGN STATUS")
    with st.container(border=True):
        for name, done, verdict, verdict_txt, note in status_rows:
            c1, c2, c3 = st.columns([2, 2, 4])
            c1.markdown(f"**{name}**")
            if done:
                c2.markdown(":green[● Calculated]")
            else:
                c2.markdown(":gray[○ Not calculated]")
            tail = note
            if verdict:
                badge = ui.status_badge_html(verdict, verdict_txt)
                c3.markdown(
                    f"{badge}&nbsp;&nbsp;<span style='color:var(--rc-text-muted);"
                    f"font-size:.8rem'>{note}</span>",
                    unsafe_allow_html=True)
            elif tail:
                c3.caption(tail)
            else:
                c3.caption("—")
    st.caption(
        "สถานะอ่านจาก session ปัจจุบันเท่านั้น · PASS/FAIL แสดงเฉพาะโมดูลที่มี "
        "ผลตรวจสอบเก็บไว้แล้ว · ไม่มีการสรุปผลรวมทั้งโครงการ"
    )

    # ---- Beam utilisation snapshot (stored values only, no recompute) ----
    beam = st.session_state.get("_beam_summary")
    if isinstance(beam, dict):
        util_rows = [
            ("เหล็กบน −Mu", beam.get("ratio_top")),
            ("เหล็กล่าง +Mu", beam.get("ratio_bot")),
            ("แรงเฉือน Vu", beam.get("ratio_shear")),
        ]
        util_rows = [(lbl, r) for lbl, r in util_rows
                     if isinstance(r, (int, float))]
        if util_rows:
            st.markdown("#### BEAM UTILIZATION (stored)")
            with st.container(border=True):
                for lbl, r in util_rows:
                    ui.utilization(lbl, 0.0, 1.0, ratio=float(r))


def _beam():
    from modules.beam import render_beam_module
    render_beam_module()


def _column():
    from modules.column import render_column_module
    render_column_module()


def _slab():
    from modules.slab import render_slab_module
    render_slab_module()


def _footing():
    from modules.footing import render_footing_module
    render_footing_module()


def _stair():
    from modules.stair import render_stair_module
    render_stair_module()


def _building():
    from modules.building import render_building_model
    render_building_model()


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🏗️", layout="wide")
    st.logo(LOGO, icon_image=LOGO)
    ui.inject_theme()
    ensure_project_state()

    home_pg = st.Page(_home, title="หน้าหลัก (Home)", icon=":material/home:",
                      url_path="home", default=True)
    project_pg = st.Page(render_project_page,
                         title="ข้อมูลโครงการ (Project Information)",
                         icon=":material/folder_open:", url_path="project")
    beam_pg = st.Page(_beam, title="คาน (Beam)",
                      icon=":material/horizontal_rule:", url_path="beam")
    column_pg = st.Page(_column, title="เสา (Column)",
                        icon=":material/view_column:", url_path="column")
    slab_pg = st.Page(_slab, title="พื้น (Slab)",
                      icon=":material/grid_on:", url_path="slab")
    footing_pg = st.Page(_footing, title="ฐานราก (Footing)",
                         icon=":material/foundation:", url_path="footing")
    stair_pg = st.Page(_stair, title="บันได (Stair)",
                       icon=":material/stairs:", url_path="stair")
    building_pg = st.Page(_building, title="จำลองอาคาร (Building Model)",
                          icon=":material/apartment:", url_path="building")

    _PAGES.update(
        home=home_pg, project=project_pg, beam=beam_pg, column=column_pg,
        slab=slab_pg, footing=footing_pg, stair=stair_pg, building=building_pg,
    )

    pages = {
        "ภาพรวม (Overview)": [home_pg],
        "โครงการ (Project)": [project_pg],
        "แบบจำลอง (Model)": [building_pg],
        "ออกแบบชิ้นส่วน (Member Design)": [
            beam_pg, column_pg, slab_pg, footing_pg, stair_pg],
    }

    pg = st.navigation(pages, expanded=True)

    with st.sidebar:
        ui.project_card()
        st.caption(f"{APP_TITLE} · {CODE_REFERENCE} · หน่วยเมตริก ({UNITS_LABEL})")

    try:
        _module_name = pg.title
    except Exception:
        _module_name = ""
    ui.top_header(_module_name,
                  project_name=get_project_info().get("project_name", ""),
                  code=CODE_REFERENCE, units=UNITS_LABEL)

    pg.run()


if __name__ == "__main__":
    main()
