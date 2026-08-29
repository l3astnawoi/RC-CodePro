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
