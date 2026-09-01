"""Project-information header shared by every design module.

The values are held in ``st.session_state`` (keys ``proj_name`` /
``proj_location`` / ``proj_engineer`` / ``proj_date``) so they are set once
in the sidebar and read by any module when it builds a PDF report.
"""

import datetime

import streamlit as st

DEFAULTS = {
    "proj_name": "บ้านพักอาศัย 2 ชั้น",
    "proj_location": "-",
    "proj_engineer": "-",
}


def render_project_info_sidebar():
    """Render the 'ข้อมูลโครงการ (Project Info)' expander in the sidebar."""
    with st.sidebar.expander("ข้อมูลโครงการ (Project Info)", expanded=True):
        st.text_input("ชื่อโครงการ (Project Name)",
                      value=DEFAULTS["proj_name"], key="proj_name")
        st.text_input("สถานที่ก่อสร้าง (Location)",
                      value=DEFAULTS["proj_location"], key="proj_location")
        st.text_input("วิศวกรผู้ออกแบบ (Engineer)",
                      value=DEFAULTS["proj_engineer"], key="proj_engineer")
        st.date_input("วันที่ (Date)",
                      value=datetime.date.today(), key="proj_date")


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
                           figures=None, status=None, summary=None):
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
        try:
            pdf_bytes = build_report(
                title=title, project_name=pname, engineer=peng,
                location=str(st.session_state.get("proj_location", "-")),
                params=params, checks=checks, figures=figures,
                status=status, summary=summary)
            st.download_button(
                "⬇️  ดาวน์โหลดรายงาน (.pdf)", data=pdf_bytes,
                file_name=filename, mime="application/pdf",
                key=f"{key}_rep_dl")
        except Exception as exc:  # pragma: no cover
            st.error(f"สร้างรายงานไม่สำเร็จ: {exc}")
