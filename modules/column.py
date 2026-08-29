"""Streamlit UI — RC short column axial design to ACI 318M-08. Thai UI, cm / cm².

Concentrically loaded short tied / spiral column, simplified strength
(ACI 318M-08 10.3.6):

    phi_Pn = phi * alpha * [ 0.85 f'c (Ag - Ast) + fy Ast ]

Section dimensions are entered in cm and converted to mm for the core
calculations; areas are reported in cm².
"""

import streamlit as st

from utils.aci_318m import phi, rebars
from utils.drawing import draw_rc_section
from utils.project import get_project_info
from reports.pdf_generator import generate_column_report, FONT_AVAILABLE, font_status_message

# Maximum-axial-strength factors (ACI 318M-08 10.3.6)
ALPHA_TIED = 0.80
ALPHA_SPIRAL = 0.85

# Longitudinal steel ratio limits (ACI 318M-08 10.9.1)
RHO_MIN = 0.01
RHO_MAX = 0.08

CM = 10.0                # cm -> mm
KSC_TO_MPA = 0.0980665   # ksc (kgf/cm^2) -> MPa (N/mm^2)

PASS_TXT = "✅ ผ่านมาตรฐาน (PASS)"
FAIL_TXT = "❌ ไม่ผ่าน (FAIL)"

TIED = "ปลอกเดี่ยว"
SPIRAL = "ปลอกเกลียว"


def render_column_module():
    st.title("การออกแบบเสา")
    st.caption("เสาสั้น — กำลังรับแรงตามแนวแกนแบบศูนย์กลาง "
               "ตามมาตรฐาน ACI 318M-08 (หน่วยเมตริก)")

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        Pu = st.number_input("น้ำหนักบรรทุกตามแนวแกนประลัย Pu (kN)", min_value=0.0,
                             value=2500.0, step=50.0)
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d")
    with c2:
        b_cm = st.number_input("ความกว้างหน้าตัด b (cm)", min_value=15.0,
                               value=40.0, step=0.01, format="%.2f")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d")
    with c3:
        h_cm = st.number_input("ความลึกหน้าตัด h (cm)", min_value=15.0,
                               value=40.0, step=0.01, format="%.2f")
        col_type = st.radio("ประเภทเสา", [TIED, SPIRAL], horizontal=True)

    # cm -> mm and ksc -> MPa for the ACI calculation core
    b = b_cm * CM
    h = h_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA

    # ------------------------------------------------------------------
    # Reinforcement
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม")
    r1, r2 = st.columns(2)
    with r1:
        rebar_size = st.selectbox("ขนาดเหล็กเสริมหลัก", list(rebars.keys()),
                                  index=list(rebars).index("DB25"))
    with r2:
        qty = st.selectbox("จำนวนเส้นทั้งหมด", list(range(4, 33)), index=0)

    bar_area = rebars[rebar_size]
    bar_dia = float(rebar_size.replace("DB", ""))
    As = qty * bar_area

    # ------------------------------------------------------------------
    # Section properties & steel ratio
    # ------------------------------------------------------------------
    Ag = b * h
    rho = As / Ag if Ag > 0 else 0.0
    ratio_ok = RHO_MIN <= rho <= RHO_MAX

    # ------------------------------------------------------------------
    # Design axial strength
    # ------------------------------------------------------------------
    if col_type == SPIRAL:
        phi_c = phi["compression_spiral"]
        alpha = ALPHA_SPIRAL
    else:
        phi_c = phi["compression_tied"]
        alpha = ALPHA_TIED

    concrete_term = 0.85 * fc * (Ag - As)          # N
    steel_term = fy * As                           # N
    phi_Pn = phi_c * alpha * (concrete_term + steel_term)   # N
    phi_Pn_kN = phi_Pn / 1000.0

    strength_ok = phi_Pn_kN >= Pu
    passed = strength_ok and ratio_ok

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| พื้นที่หน้าตัดรวม Ag = b · h | {Ag / 100.0:,.2f} cm² |
| เส้นผ่านศูนย์กลางเหล็กหลัก | {bar_dia:.1f} mm |
| พื้นที่เหล็ก 1 เส้น, {rebar_size} | {bar_area / 100.0:,.2f} cm² |
| เหล็กที่จัดให้ Ast = n · Ab = {qty} × {bar_area / 100.0:,.2f} | **{As / 100.0:,.2f} cm²** |
| อัตราส่วนเหล็กเสริม ρ = Ast / Ag | {rho:.4f} |
| ช่วง ρ ที่ยอมให้ | {RHO_MIN:.2f} – {RHO_MAX:.2f} |
| φ ({col_type}) | {phi_c:.2f} |
| ตัวคูณกำลังสูงสุด α | {alpha:.2f} |
| 0.85·f'c·(Ag − Ast) | {concrete_term:,.0f} N |
| fy·Ast | {steel_term:,.0f} N |
| φPn = φ · α · [0.85 f'c (Ag − Ast) + fy Ast] | **{phi_Pn_kN:,.1f} kN** |
| Pu | {Pu:,.1f} kN |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing (b, h are already in mm; covering assumed 40 mm)
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_rc_section(b, h, 40.0, bar_dia, qty,
                                      section_type="column")
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    reasons = []
    if not ratio_ok:
        reasons.append(
            f"อัตราส่วนเหล็กเสริม ρ = {rho:.4f} อยู่นอกช่วง {RHO_MIN:.2f}–{RHO_MAX:.2f}"
        )
    if not strength_ok:
        reasons.append(f"φPn = {phi_Pn_kN:,.1f} kN < Pu = {Pu:,.1f} kN")

    if passed:
        st.success(
            f"{PASS_TXT} — φPn = {phi_Pn_kN:,.1f} kN ≥ Pu = {Pu:,.1f} kN และ "
            f"ρ = {rho:.4f} อยู่ในช่วง {RHO_MIN:.2f}–{RHO_MAX:.2f}"
        )

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_column_report(
            {
                "Pu": Pu,
                "b": b,
                "h": h,
                "fc": fc,
                "fy": fy,
                "col_type": col_type,
                "project": get_project_info(),
            },
            {
                "Ag": Ag,
                "As_prov": As,
                "rho": rho,
                "rho_min": RHO_MIN,
                "rho_max": RHO_MAX,
                "phi_c": phi_c,
                "alpha": alpha,
                "phi_Pn": phi_Pn_kN,
                "Pu": Pu,
                "rebar_size": rebar_size,
                "qty": qty,
                "section_img": section_img,
                "status": "PASS",
            },
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="column_design_report.pdf",
            mime="application/pdf",
        )
    else:
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


if __name__ == "__main__":
    render_column_module()
