"""RC CodePro — RC structure design to ACI 318M-08 (Thai UI, MKS units).

Dashboard-style shell: a branded icon navigation rail (``st.navigation`` +
``st.logo``) on the left, the project-info panel in the sidebar, and each
design module rendered as its own page.
"""

import streamlit as st

from utils.project import render_project_info_sidebar

APP_TITLE = "RC CodePro"
CODE_REFERENCE = "ACI 318M-08"
LOGO = "assets/logo.svg"


def _home():
    st.title("RC CodePro")
    st.subheader(f"การออกแบบคอนกรีตเสริมเหล็กตามมาตรฐาน {CODE_REFERENCE}")
    st.write(
        "ยินดีต้อนรับ! เครื่องมือนี้ช่วยออกแบบชิ้นส่วนโครงสร้างคอนกรีตเสริมเหล็ก "
        "ให้เป็นไปตามมาตรฐาน ACI 318M-08 (หน่วยเมตริก) — เลือกโมดูลจากแถบเมนู"
        "ด้านซ้าย"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container(border=True):
            st.markdown("#### 🏢 จำลองอาคาร")
            st.caption("ระบบเส้นกริด · ถ่ายน้ำหนักลงเสา · จัดกลุ่มเบอร์เสา · "
                       "ถอดปริมาณวัสดุ (BOQ) · โมเดล 3 มิติ")
    with c2:
        with st.container(border=True):
            st.markdown("#### 🏗️ ออกแบบชิ้นส่วน")
            st.caption("คาน (วิเคราะห์ + ออกแบบ) · เสา (P–M) · พื้น · ฐานราก · "
                       "บันได — ครบทั้งการดัด แรงเฉือน และการจัดเหล็ก")
    with c3:
        with st.container(border=True):
            st.markdown("#### 📄 รายงาน")
            st.caption("ออกรายการคำนวณ PDF ภาษาไทย พร้อมภาพ CAD และตาราง "
                       "Demand / Capacity ในทุกโมดูล")


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

    pages = {
        "ทั่วไป": [
            st.Page(_home, title="หน้าหลัก", icon=":material/home:",
                    url_path="home", default=True),
        ],
        "ออกแบบชิ้นส่วน (Member Design)": [
            st.Page(_beam, title="คาน (Beam)",
                    icon=":material/horizontal_rule:", url_path="beam"),
            st.Page(_column, title="เสา (Column)",
                    icon=":material/view_column:", url_path="column"),
            st.Page(_slab, title="พื้น (Slab)",
                    icon=":material/grid_on:", url_path="slab"),
            st.Page(_footing, title="ฐานราก (Footing)",
                    icon=":material/foundation:", url_path="footing"),
            st.Page(_stair, title="บันได (Stair)",
                    icon=":material/stairs:", url_path="stair"),
        ],
        "แบบจำลองอาคาร (Building Model)": [
            st.Page(_building, title="จำลองอาคาร (Building)",
                    icon=":material/apartment:", url_path="building"),
        ],
    }

    pg = st.navigation(pages, expanded=True)

    with st.sidebar:
        render_project_info_sidebar()
        st.caption(f"{APP_TITLE} · {CODE_REFERENCE} · หน่วยเมตริก (MKS)")

    pg.run()


if __name__ == "__main__":
    main()
