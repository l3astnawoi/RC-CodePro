"""Project information — single source of truth for the whole app.

The values live in ``st.session_state`` under the keys ``proj_name`` /
``proj_location`` / ``proj_engineer`` / ``proj_date``.  They are edited on
the **Project page** (:func:`render_project_page`) and read by any design
module when it builds a PDF report (:func:`get_project_info`).

STEP 3: the editable panel moved out of the sidebar onto its own page so
there is exactly one place to change these values.  The session-state key
names are unchanged.
"""

import datetime

import streamlit as st

DEFAULTS = {
    "proj_name": "บ้านพักอาศัย 2 ชั้น",
    "proj_location": "-",
    "proj_engineer": "-",
}

DESIGN_CODE = "ACI 318M-08"
DESIGN_UNITS = "MKS (cm · kgf · ksc)"


def ensure_project_state():
    """Seed the persistent project keys from the defaults if they are not
    set yet.  Idempotent — safe to call on every rerun.  These keys are
    plain state (not widget keys) so Streamlit never garbage-collects them
    when the Project page is not on screen."""
    st.session_state.setdefault("proj_name", DEFAULTS["proj_name"])
    st.session_state.setdefault("proj_location", DEFAULTS["proj_location"])
    st.session_state.setdefault("proj_engineer", DEFAULTS["proj_engineer"])
    st.session_state.setdefault("proj_date", datetime.date.today())


def render_project_page():
    """PROJECT / Project Information page — the one place to edit project data."""
    from utils import ui

    ensure_project_state()
    ui.page_header(
        "Project Information",
        "การตั้งค่าโครงการและพารามิเตอร์การออกแบบ "
        "(Project configuration & design settings)",
        crumbs=("โครงการ (Project)", "ข้อมูลโครงการ (Project Information)"),
    )

    _raw_date = st.session_state["proj_date"]
    if not hasattr(_raw_date, "isoformat"):
        _raw_date = datetime.date.today()

    with st.container(border=True):
        st.html('<div class="rc-card-title">Project Information</div>')
        # No widget keys on purpose: the persistent state lives under the
        # plain keys proj_name / proj_location / proj_engineer / proj_date,
        # which survive page navigation.  The form widgets are pre-filled
        # from those keys and their submitted return values are written back
        # on save.
        with st.form("project_info_form", border=False):
            name = st.text_input(
                "ชื่อโครงการ (Project Name)",
                value=str(st.session_state["proj_name"]))
            c1, c2 = st.columns(2)
            with c1:
                location = st.text_input(
                    "สถานที่ก่อสร้าง (Location)",
                    value=str(st.session_state["proj_location"]))
            with c2:
                engineer = st.text_input(
                    "วิศวกรผู้ออกแบบ (Engineer)",
                    value=str(st.session_state["proj_engineer"]))
            date_val = st.date_input("วันที่ (Date)", value=_raw_date)

            saved = st.form_submit_button(
                "บันทึกข้อมูลโครงการ (Save Project Information)",
                type="primary")

        if saved:
            st.session_state["proj_name"] = name
            st.session_state["proj_location"] = location
            st.session_state["proj_engineer"] = engineer
            st.session_state["proj_date"] = date_val
            # rerun so the sidebar card + top header (rendered before the
            # page body) pick up the new values on the same interaction
            if hasattr(st, "toast"):
                st.toast("บันทึกข้อมูลโครงการแล้ว (saved)", icon="✅")
            st.rerun()

    info = get_project_info()
    ui.project_summary(
        [
            ("Project", info["project_name"]),
            ("Engineer", info["engineer"]),
            ("Location", info["location"]),
            ("Date", info["date"]),
            ("Design code", DESIGN_CODE),
            ("Units", DESIGN_UNITS),
        ],
        title="PROJECT SUMMARY",
    )


def get_project_info():
    """Return a plain ``dict`` of the current project info for the PDF header.

    Keys: ``project_name``, ``location``, ``engineer``, ``date`` (ISO string).
    Safe to call outside a Streamlit run — falls back to the defaults.
    """
    try:
        state = st.session_state
    except Exception:  # pragma: no cover - not in a Streamlit context
        state = {}

    raw_date = state.get("proj_date") if hasattr(state, "get") else None
    if hasattr(raw_date, "isoformat"):
        date_str = raw_date.isoformat()
    elif raw_date:
        date_str = str(raw_date)
    else:
        date_str = datetime.date.today().isoformat()

    def _g(key):
        try:
            return state.get(key, DEFAULTS.get(key, "-"))
        except Exception:
            return DEFAULTS.get(key, "-")

    return {
        "project_name": _g("proj_name"),
        "location": _g("proj_location"),
        "engineer": _g("proj_engineer"),
        "date": date_str,
    }


def render_report_expander(*, key, filename, title, params, checks=None,
                           figures=None, status=None, summary=None,
                           boq_dataframe=None):
    """Standard bottom-of-page report block shared by every design module.

    Renders an expander '📄 ออกรายงานรายการคำนวณ (Generate Report)' with
    Project Name / Engineer Name text inputs and a ``st.download_button``
    that builds the PDF via ``reports.pdf_generator.build_report``.

    key      : unique per module (widget-key prefix)
    filename : downloaded file name, e.g. "beam_report.pdf"
    title    : report title line
    params   : list of (label, value[, unit[, nd]])
    checks   : list of (name, demand, capacity, ok)
    figures  : Matplotlib Figure / BytesIO / list thereof (Section 3)
    status   : bool | "PASS" | "FAIL" (defaults to AND of the checks)
    summary  : optional one-line conclusion sentence
    boq_dataframe : optional Pandas DataFrame / list-of-rows rendered as a
                    "BOQ Estimate" table at the end of the PDF (Section 4)
    """
    from reports.pdf_generator import (build_report, FONT_AVAILABLE,
                                       font_status_message)

    with st.expander("📄 ออกรายงานรายการคำนวณ (Generate Report)",
                     expanded=False):
        cc1, cc2 = st.columns(2)
        with cc1:
            pname = st.text_input(
                "ชื่อโครงการ (Project Name)",
                value=str(st.session_state.get("proj_name",
                                               DEFAULTS["proj_name"])),
                key=f"{key}_rep_pname")
        with cc2:
            peng = st.text_input(
                "วิศวกรผู้ออกแบบ (Engineer Name)",
                value=str(st.session_state.get("proj_engineer",
                                               DEFAULTS["proj_engineer"])),
                key=f"{key}_rep_eng")

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        # Build the PDF only when the engineer asks for it — not on every
        # page rerun.  The bytes are cached in session_state so the download
        # button can serve them without rebuilding.
        _pdf_key = f"{key}_rep_pdf"
        if st.button("🛠️  สร้างรายงาน PDF (Generate PDF Report)",
                     key=f"{key}_rep_gen", type="primary"):
            try:
                with st.spinner("กำลังสร้างรายงาน… (Generating report…)"):
                    st.session_state[_pdf_key] = build_report(
                        title=title, project_name=pname, engineer=peng,
                        location=str(st.session_state.get("proj_location",
                                                          "-")),
                        params=params, checks=checks, figures=figures,
                        status=status, summary=summary,
                        boq_dataframe=boq_dataframe)
            except Exception as exc:  # pragma: no cover
                st.session_state.pop(_pdf_key, None)
                st.error("❌ สร้างรายงานไม่สำเร็จ — โปรดตรวจสอบข้อมูลนำเข้า "
                         "แล้วลองอีกครั้ง (Report generation failed)")
                st.caption(f"รายละเอียดสำหรับผู้พัฒนา: {exc}")

        _pdf_bytes = st.session_state.get(_pdf_key)
        if _pdf_bytes:
            st.success("✅ รายงานพร้อมแล้ว (Report ready)")
            st.download_button(
                "⬇️  ดาวน์โหลดรายงาน (.pdf)", data=_pdf_bytes,
                file_name=filename, mime="application/pdf",
                key=f"{key}_rep_dl")
        else:
            st.caption("กดปุ่ม «สร้างรายงาน PDF» เพื่อสร้างไฟล์รายงาน")
