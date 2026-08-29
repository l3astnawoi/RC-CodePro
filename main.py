"""RC Structure Design (ภาษาไทย)

โปรแกรม Streamlit สำหรับการออกแบบโครงสร้างคอนกรีตเสริมเหล็กตามมาตรฐาน
ACI 318M-08 (หน่วยเมตริก)
"""

import streamlit as st

from utils.project import render_project_info_sidebar

APP_TITLE = "การออกแบบโครงสร้างคอนกรีตเสริมเหล็ก"
CODE_REFERENCE = "ACI 318M-08"

# Sidebar labels (Thai) -> renderer key
HOME = "หน้าหลัก"
BEAM = "คาน"
COLUMN = "เสา"
SLAB = "พื้น"
FOOTING = "ฐานราก"
STAIR = "บันได"

MENU_ITEMS = [HOME, BEAM, COLUMN, SLAB, FOOTING, STAIR]


def show_welcome():
    st.title(APP_TITLE)
    st.subheader(f"การออกแบบคอนกรีตเสริมเหล็กตามมาตรฐาน {CODE_REFERENCE}")
    st.write(
        "ยินดีต้อนรับ! เครื่องมือนี้ช่วยในการออกแบบชิ้นส่วนโครงสร้างคอนกรีต"
        "เสริมเหล็กให้เป็นไปตามมาตรฐาน ACI 318M-08 (หน่วยเมตริก)"
    )
    st.markdown(
        """
        **เริ่มต้นใช้งาน**

        เลือกชิ้นส่วนโครงสร้างที่ต้องการออกแบบจากเมนูด้านซ้าย:

        - **คาน** &mdash; การดัด แรงเฉือน และการจัดเหล็กเสริมของคาน คสล.
        - **เสา** &mdash; การตรวจสอบกำลังรับแรงตามแนวแกน
        - **พื้น** &mdash; การออกแบบพื้นทางเดียว
        - **ฐานราก** &mdash; การออกแบบฐานรากเดี่ยว
        - **บันได** &mdash; การออกแบบบันไดพาดทางเดียว
        """
    )
    st.info("เลือกโมดูลจากเมนูด้านซ้ายเพื่อเริ่มต้น")


def show_placeholder(name):
    st.title(name)
    st.write(f"โมดูล **{name}** ยังไม่พร้อมใช้งาน")
    st.caption(f"มาตรฐานอ้างอิง: {CODE_REFERENCE}")


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    st.sidebar.title(APP_TITLE)
    st.sidebar.caption(CODE_REFERENCE)

    render_project_info_sidebar()

    choice = st.sidebar.radio("เมนู", MENU_ITEMS)

    if choice == HOME:
        show_welcome()
    elif choice == BEAM:
        from modules.beam import render_beam_module
        render_beam_module()
    elif choice == COLUMN:
        from modules.column import render_column_module
        render_column_module()
    elif choice == SLAB:
        from modules.slab import render_slab_module
        render_slab_module()
    elif choice == FOOTING:
        from modules.footing import render_footing_module
        render_footing_module()
    elif choice == STAIR:
        from modules.stair import render_stair_module
        render_stair_module()
    else:
        show_placeholder(choice)


if __name__ == "__main__":
    main()
