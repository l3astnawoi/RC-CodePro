"""Streamlit UI — RC straight stair design to ACI 318M-08. Thai UI, cm / cm².

Straight flight designed as a simply-supported one-way slab spanning the
horizontal projection L (metres), on a 1 m wide strip.

UI units: span L in m (3 decimals); tread / riser / waist / covering in cm
(converted to mm internally); steel areas reported in cm² per metre.
"""

import math

import streamlit as st

from utils.aci_318m import phi, rebars
from utils.drawing import draw_slab_strip
from utils.project import get_project_info
from reports.pdf_generator import generate_stair_report, FONT_AVAILABLE, font_status_message

STRIP_WIDTH = 1000.0        # mm
CONC_DENSITY = 24.0         # kN/m3
CM = 10.0                   # cm -> mm
KSC_TO_MPA = 0.0980665      # ksc (kgf/cm^2) -> MPa (N/mm^2)

PASS_TXT = "✅ ผ่านมาตรฐาน (PASS)"
FAIL_TXT = "❌ ไม่ผ่าน (FAIL)"


def _temp_steel_ratio(fy):
    """Shrinkage & temperature reinforcement ratio (ACI 318M-08 7.12.2.1)."""
    if fy <= 350.0:
        return 0.0020
    if fy <= 420.0:
        return 0.0018
    return max(0.0018 * 420.0 / fy, 0.0014)


def _required_as_flexure(Mu_kNm, b, d, fc, fy):
    """Singly-reinforced tension-controlled required As (mm2 per strip)."""
    phi_f = phi["flexure"]
    Mu = Mu_kNm * 1.0e6                        # kN.m/m -> N.mm per metre
    Rn = Mu / (phi_f * b * d ** 2)             # MPa
    disc = 1.0 - 2.0 * Rn / (0.85 * fc)
    if disc < 0.0:
        return None, Rn, None, False
    rho = (0.85 * fc / fy) * (1.0 - math.sqrt(disc))
    return rho * b * d, Rn, rho, True


def render_stair_module():
    st.title("การออกแบบบันได")
    st.caption("บันไดพาดตรง — พื้นทางเดียวรับแรงแบบช่วงเดี่ยว แถบกว้าง 1 ม. "
               "ตามมาตรฐาน ACI 318M-08 (หน่วยเมตริก)")

    b = STRIP_WIDTH          # mm (internal)
    b_cm = b / CM            # cm (display)

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        L = st.number_input("ช่วงพาดในแนวราบ L (m)", min_value=1.0,
                            value=3.0, step=0.001, format="%.3f")
        t_cm = st.number_input("ความหนาท้องบันได t (cm)", min_value=8.0,
                               value=15.0, step=0.01, format="%.2f")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d")
    with c2:
        T_cm = st.number_input("ลูกนอน T (cm)", min_value=20.0,
                               value=25.0, step=0.01, format="%.2f")
        SDL = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม (kN/m²)", min_value=0.0,
                              value=1.5, step=0.5)
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d")
    with c3:
        R_cm = st.number_input("ลูกตั้ง R (cm)", min_value=10.0,
                               value=17.5, step=0.01, format="%.2f")
        LL = st.number_input("น้ำหนักบรรทุกจร LL (kN/m²)", min_value=0.0,
                             value=3.0, step=0.5)
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.5,
                                      value=2.0, step=0.01, format="%.2f")

    st.number_input("ความกว้างแถบออกแบบ b (cm)", value=b_cm, disabled=True,
                    step=0.01, format="%.2f", help="กำหนดคงที่ที่แถบกว้าง 1 ม.")

    # cm -> mm and ksc -> MPa for the ACI calculation core (L already in metres)
    t = t_cm * CM
    T = T_cm * CM
    R = R_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA

    # ------------------------------------------------------------------
    # Reinforcement
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม")
    m1, m2 = st.columns(2)
    with m1:
        main_size = st.selectbox("ขนาดเหล็กเสริมหลัก", list(rebars.keys()),
                                 index=list(rebars).index("DB12"))
        main_spacing = st.number_input("ระยะเรียงเหล็กเสริมหลัก (mm)", min_value=50.0,
                                       max_value=450.0, value=150.0, step=10.0)
    with m2:
        temp_size = st.selectbox("ขนาดเหล็กเสริมกันร้าว", list(rebars.keys()),
                                 index=list(rebars).index("DB12"))
        temp_spacing = st.number_input("ระยะเรียงเหล็กเสริมกันร้าว (mm)",
                                       min_value=50.0, max_value=450.0,
                                       value=250.0, step=10.0)

    main_area = rebars[main_size]
    temp_area = rebars[temp_size]
    main_dia = float(main_size.replace("DB", ""))
    temp_dia = float(temp_size.replace("DB", ""))

    # ------------------------------------------------------------------
    # Geometry & loads
    # ------------------------------------------------------------------
    theta = math.atan(R / T)                                     # rad
    SW = CONC_DENSITY * ((t / 1000.0) / math.cos(theta) + (R / 2000.0))  # kN/m²
    DL = SW + SDL                                                # kN/m²
    wu = 1.2 * DL + 1.6 * LL                                     # kN/m (1 m strip)
    Mu = wu * L ** 2 / 8.0                                       # kN·m/m

    # ------------------------------------------------------------------
    # Effective depth (mm)
    # ------------------------------------------------------------------
    d = t - covering - main_dia / 2.0
    if d <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบระยะหุ้ม ความหนาท้องบันได "
                 "หรือขนาดเหล็กเสริม")
        return

    # ------------------------------------------------------------------
    # Required steel
    # ------------------------------------------------------------------
    As_req, Rn, rho, feasible = _required_as_flexure(Mu, b, d, fc, fy)
    temp_ratio = _temp_steel_ratio(fy)
    As_min = temp_ratio * b * t

    As_prov_main = main_area * (b / main_spacing)
    As_prov_temp = temp_area * (b / temp_spacing)

    max_sp_main = min(3.0 * t, 450.0)
    max_sp_temp = min(5.0 * t, 450.0)
    sp_main_ok = main_spacing <= max_sp_main
    sp_temp_ok = temp_spacing <= max_sp_temp

    # ------------------------------------------------------------------
    # Load analysis
    # ------------------------------------------------------------------
    st.subheader("การวิเคราะห์น้ำหนักบรรทุก")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| มุมลาดเอียง θ = atan(R/T) | {math.degrees(theta):,.2f}° |
| น้ำหนักตัวเอง SW = 24·(t/cosθ + R/2) | {SW:,.3f} kN/m² |
| น้ำหนักบรรทุกคงที่รวม DL = SW + SDL | {DL:,.3f} kN/m² |
| น้ำหนักบรรทุกประลัย wu = 1.2·DL + 1.6·LL | **{wu:,.3f} kN/m** |
| โมเมนต์ประลัย Mu = wu·L²/8 | **{Mu:,.3f} kN·m/m** |
"""
    )

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| เส้นผ่านศูนย์กลางเหล็กหลัก Ø | {main_dia:.1f} mm |
| ความลึกประสิทธิผล d = t − covering − Ø/2 | **{d / CM:,.2f} cm** |
| φ (การดัด) | {phi['flexure']:.2f} |
| Rn = Mu / (φ·b·d²) | {Rn:,.4f} MPa |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing — 1 m strip cross-section (t, covering, spacings in mm)
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_slab_strip(t, covering, main_dia, temp_dia,
                                      main_spacing, temp_spacing)
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    if not feasible:
        st.error("ท้องบันไดบางเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว "
                 "(1 − 2·Rn/(0.85·f'c) < 0) — เพิ่ม t หรือ f'c")
        st.markdown(
            f"เหล็กกันร้าว/อุณหภูมิ As,min = **{As_min / 100.0:,.2f} cm²/m**  ·  "
            f"As หลักที่จัดให้ = **{As_prov_main / 100.0:,.2f} cm²/m**"
        )
        st.error(f"{FAIL_TXT} — ท้องบันไดไม่เพียงพอสำหรับการดัด")
        return

    As_design = max(As_req, As_min)
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| ρ = 0.85·f'c/fy · (1 − √(1 − 2·Rn/0.85·f'c)) | {rho:.5f} |
| As ที่ต้องการ (การดัด) = ρ·b·d | **{As_req / 100.0:,.2f} cm²/m** |
| อัตราส่วนเหล็กกันร้าว/อุณหภูมิ (fy = {fy_ksc:,.0f} ksc) | {temp_ratio:.4f} |
| As,min = ratio · b · t | {As_min / 100.0:,.2f} cm²/m |
| As หลักที่ต้องการที่ควบคุม = max(การดัด, As,min) | **{As_design / 100.0:,.2f} cm²/m** |
| หลัก: {main_size} @ {main_spacing:,.0f} mm → {main_area / 100.0:,.2f} cm² × (1000/s) | **{As_prov_main / 100.0:,.2f} cm²/m** |
| ระยะเรียงสูงสุด (หลัก) = min(3t, 450) | {max_sp_main:,.0f} mm |
| กันร้าว: {temp_size} @ {temp_spacing:,.0f} mm → {temp_area / 100.0:,.2f} cm² × (1000/s) | **{As_prov_temp / 100.0:,.2f} cm²/m** |
| ระยะเรียงสูงสุด (กันร้าว) = min(5t, 450) | {max_sp_temp:,.0f} mm |
"""
    )

    # ------------------------------------------------------------------
    # Design checks
    # ------------------------------------------------------------------
    st.subheader("การตรวจสอบการออกแบบ")
    as_req_ok = As_prov_main >= As_req
    as_min_ok = As_prov_main >= As_min
    temp_min_ok = As_prov_temp >= As_min
    passed = as_req_ok and as_min_ok and temp_min_ok and sp_main_ok and sp_temp_ok

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    st.markdown(
        f"""
| การตรวจสอบ | แรงที่กระทำ | กำลังต้านทาน / ขีดจำกัด | สถานะ |
|---|---|---|---|
| As หลัก ≥ ที่ต้องการ | As,prov = {As_prov_main / 100.0:,.2f} cm²/m | As,req = {As_req / 100.0:,.2f} cm²/m | {_s(as_req_ok)} |
| As หลัก ≥ As,min | As,prov = {As_prov_main / 100.0:,.2f} cm²/m | As,min = {As_min / 100.0:,.2f} cm²/m | {_s(as_min_ok)} |
| As กันร้าว ≥ As,min | As,prov = {As_prov_temp / 100.0:,.2f} cm²/m | As,min = {As_min / 100.0:,.2f} cm²/m | {_s(temp_min_ok)} |
| ระยะเรียงหลัก ≤ ขีดจำกัด | s = {main_spacing:,.0f} mm | {max_sp_main:,.0f} mm | {_s(sp_main_ok)} |
| ระยะเรียงกันร้าว ≤ ขีดจำกัด | s = {temp_spacing:,.0f} mm | {max_sp_temp:,.0f} mm | {_s(sp_temp_ok)} |
"""
    )

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    if passed:
        st.success(
            f"{PASS_TXT} — As หลักที่จัดให้ = {As_prov_main / 100.0:,.2f} cm²/m ≥ "
            f"ที่ต้องการที่ควบคุม {As_design / 100.0:,.2f} cm²/m; "
            f"ระยะเรียงอยู่ในเกณฑ์ทั้งหมด"
        )

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_stair_report(
            {
                "L": L, "T": T, "R": R, "t": t, "SDL": SDL, "LL": LL,
                "covering": covering, "fc": fc, "fy": fy, "b": b,
                "project": get_project_info(),
            },
            {
                "theta_deg": math.degrees(theta), "SW": SW, "DL": DL,
                "wu": wu, "Mu": Mu, "d": d,
                "As_req": As_req, "As_min": As_min,
                "main_size": main_size, "main_spacing": main_spacing,
                "As_prov_main": As_prov_main, "max_sp_main": max_sp_main,
                "temp_size": temp_size, "temp_spacing": temp_spacing,
                "As_prov_temp": As_prov_temp, "max_sp_temp": max_sp_temp,
                "section_img": section_img,
                "status": "PASS",
            },
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="stair_design_report.pdf",
            mime="application/pdf",
        )
    else:
        reasons = []
        if not as_req_ok:
            reasons.append(
                f"As หลัก {As_prov_main / 100.0:,.2f} < "
                f"ที่ต้องการ {As_req / 100.0:,.2f} cm²/m"
            )
        if not as_min_ok:
            reasons.append(
                f"As หลัก {As_prov_main / 100.0:,.2f} < "
                f"As,min {As_min / 100.0:,.2f} cm²/m"
            )
        if not temp_min_ok:
            reasons.append(
                f"As กันร้าว {As_prov_temp / 100.0:,.2f} < "
                f"As,min {As_min / 100.0:,.2f} cm²/m"
            )
        if not sp_main_ok:
            reasons.append(
                f"ระยะเรียงหลัก {main_spacing:,.0f} > สูงสุด {max_sp_main:,.0f} mm"
            )
        if not sp_temp_ok:
            reasons.append(
                f"ระยะเรียงกันร้าว {temp_spacing:,.0f} > สูงสุด {max_sp_temp:,.0f} mm"
            )
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


if __name__ == "__main__":
    render_stair_module()
