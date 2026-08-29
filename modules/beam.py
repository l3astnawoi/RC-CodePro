"""Streamlit UI — RC beam flexural design to ACI 318M-08. Thai UI, cm / cm² display.

Singly-reinforced rectangular section: required tension steel vs. provided.
UI inputs are in cm; converted to mm internally for the ACI calculations.
"""

import math

import streamlit as st

from utils.aci_318m import phi, rebars, get_beta1, calc_As_min
from utils.drawing import draw_rc_section
from utils.project import get_project_info
from reports.pdf_generator import generate_beam_report, FONT_AVAILABLE, font_status_message

STIRRUP_DIA = 10.0        # mm, assumed closed stirrups
CM = 10.0                # cm -> mm
KSC_TO_MPA = 0.0980665   # ksc (kgf/cm^2) -> MPa (N/mm^2)

PASS_TXT = "✅ ผ่านมาตรฐาน (PASS)"
FAIL_TXT = "❌ ไม่ผ่าน (FAIL)"


def _required_as(Mu_kNm, b, d, fc, fy):
    """Required tension steel area (mm^2) for a singly-reinforced,
    tension-controlled rectangular section.

    Returns (As_req, Rn, rho, feasible).
    """
    phi_f = phi["flexure"]
    Mu = Mu_kNm * 1.0e6                        # kN-m -> N-mm
    Rn = Mu / (phi_f * b * d ** 2)             # MPa
    disc = 1.0 - 2.0 * Rn / (0.85 * fc)
    if disc < 0.0:
        return None, Rn, None, False
    rho = (0.85 * fc / fy) * (1.0 - math.sqrt(disc))
    return rho * b * d, Rn, rho, True


def render_beam_module():
    st.title("การออกแบบคาน")
    st.caption("การดัด — หน้าตัดสี่เหลี่ยมเสริมเหล็กรับแรงดึงอย่างเดียว "
               "ตามมาตรฐาน ACI 318M-08 (หน่วยเมตริก)")

    # ------------------------------------------------------------------
    # Inputs  (section dimensions in cm)
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        Mu = st.number_input("โมเมนต์ประลัย Mu (kN·m)", min_value=0.0,
                             value=150.0, step=5.0)
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d")
    with c2:
        b_cm = st.number_input("ความกว้างหน้าตัด b (cm)", min_value=10.0,
                               value=30.0, step=0.01, format="%.2f")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d")
    with c3:
        h_cm = st.number_input("ความลึกหน้าตัด h (cm)", min_value=15.0,
                               value=55.0, step=0.01, format="%.2f")
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=2.0,
                                      value=4.0, step=0.01, format="%.2f")

    # cm -> mm and ksc -> MPa for the ACI calculation core
    b = b_cm * CM
    h = h_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA

    # ------------------------------------------------------------------
    # Reinforcement selection
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม")
    r1, r2 = st.columns(2)
    with r1:
        rebar_size = st.selectbox("ขนาดเหล็กเสริม", list(rebars.keys()),
                                  index=list(rebars).index("DB20"))
    with r2:
        qty = st.selectbox("จำนวนเส้น", list(range(2, 13)), index=1)

    rebar_dia = float(rebar_size.replace("DB", ""))
    bar_area = rebars[rebar_size]

    # ------------------------------------------------------------------
    # Effective depth  d = h - covering - stirrup - rebar_dia/2   (mm)
    # ------------------------------------------------------------------
    d = h - covering - STIRRUP_DIA - rebar_dia / 2.0
    if d <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบระยะหุ้ม ความลึกหน้าตัด "
                 "หรือขนาดเหล็กเสริม")
        return

    As_req, Rn, rho, feasible = _required_as(Mu, b, d, fc, fy)
    As_min = calc_As_min(fc, fy, b, d)
    beta1 = get_beta1(fc)
    As_prov = qty * bar_area

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| β1  (`get_beta1(fc)`) | {beta1:.4f} |
| φ (การดัด) | {phi['flexure']:.2f} |
| เส้นผ่านศูนย์กลางเหล็กหลัก | {rebar_dia:.1f} mm |
| ความลึกประสิทธิผล d = h − covering − Ø_ปลอก − Ø_หลัก/2 | **{d / CM:,.2f} cm** |
| Mu | {Mu * 1e6:,.0f} N·mm |
| Rn = Mu / (φ·b·d²) | {Rn:,.4f} MPa |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing (b, h, covering are already in mm)
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_rc_section(b, h, covering, rebar_dia, qty,
                                      section_type="beam")
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    if not feasible:
        st.error(
            "หน้าตัดเล็กเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว "
            "(1 − 2·Rn/(0.85·f'c) < 0) — เพิ่ม b, h หรือ f'c"
        )
        st.markdown(
            f"As,min = **{As_min / 100.0:,.2f} cm²**  ·  "
            f"As ที่จัดให้ = {qty} × {rebar_size} = **{As_prov / 100.0:,.2f} cm²**"
        )
        st.error(f"{FAIL_TXT} — หน้าตัดไม่เพียงพอสำหรับการดัด")
        return

    As_design = max(As_req, As_min)
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| ρ = 0.85·f'c/fy · (1 − √(1 − 2·Rn/0.85·f'c)) | {rho:.5f} |
| **As ที่ต้องการ** = ρ·b·d | **{As_req / 100.0:,.2f} cm²** |
| As,min = max(0.25√f'c/fy, 1.4/fy)·b·d | {As_min / 100.0:,.2f} cm² |
| As ที่ต้องการที่ควบคุม = max(As, As,min) | **{As_design / 100.0:,.2f} cm²** |
| พื้นที่เหล็ก 1 เส้น, {rebar_size} (Ø {rebar_dia:.1f} mm) | {bar_area / 100.0:,.2f} cm² |
| **As ที่จัดให้** = {qty} × {bar_area / 100.0:,.2f} | **{As_prov / 100.0:,.2f} cm²** |
"""
    )

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    ok_req = As_prov >= As_req
    ok_min = As_prov >= As_min

    if ok_req and ok_min:
        st.success(
            f"{PASS_TXT} — As ที่จัดให้ = {As_prov / 100.0:,.2f} cm² ≥ "
            f"As ที่ต้องการที่ควบคุม = {As_design / 100.0:,.2f} cm² "
            f"(As,required = {As_req / 100.0:,.2f} cm², "
            f"As,min = {As_min / 100.0:,.2f} cm²)"
        )

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_beam_report(
            {
                "Mu": Mu,
                "b": b,
                "h": h,
                "fc": fc,
                "fy": fy,
                "covering": covering,
                "project": get_project_info(),
            },
            {
                "d": d,
                "As_req": As_req,
                "As_min": As_min,
                "rebar_size": rebar_size,
                "qty": qty,
                "As_prov": As_prov,
                "section_img": section_img,
                "status": "PASS",
            },
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="beam_design_report.pdf",
            mime="application/pdf",
        )
    else:
        reasons = []
        if not ok_req:
            reasons.append(
                f"As ที่จัดให้ < As,required "
                f"({As_prov / 100.0:,.2f} < {As_req / 100.0:,.2f} cm²)"
            )
        if not ok_min:
            reasons.append(
                f"As ที่จัดให้ < As,min "
                f"({As_prov / 100.0:,.2f} < {As_min / 100.0:,.2f} cm²)"
            )
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


# Backwards-compatible alias
render = render_beam_module


if __name__ == "__main__":
    render_beam_module()
