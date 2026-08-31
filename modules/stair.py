"""Streamlit UI — RC straight stair design to ACI 318M-08. Thai UI, cm / cm².

Straight flight designed as a simply-supported one-way slab spanning the
horizontal projection L (metres), on a 1 m wide strip.

UI units: span L in m (3 decimals); tread / riser / waist / covering in cm
(converted to mm internally); steel areas reported in cm² per metre.
"""

import math

import streamlit as st

from utils.aci_318m import phi, rebars, bar_area
from utils.drawing import draw_slab_strip, draw_u_stair_elevation
from utils.project import get_project_info
from reports.pdf_generator import (
    generate_stair_report,
    generate_u_stair_report,
    FONT_AVAILABLE,
    font_status_message,
)

STRIP_WIDTH = 1000.0        # mm
CONC_DENSITY_KGF = 2400.0   # concrete unit weight — EXACT MKS value (kgf/m^3).
                            # Self-weight uses this literal 2400 so hand checks
                            # reproduce the printed formula; NOT 24 kN/m^3
                            # round-tripped through 9.80665.
CM = 10.0                   # cm -> mm
KSC_TO_MPA = 0.0980665      # ksc (kgf/cm^2) -> MPa (N/mm^2)
KGF_TO_KN = 9.80665 / 1000.0   # kgf -> kN  (also kgf/m2 -> kN/m2, kgf-m -> kN.m)
KN_TO_KGF = 1000.0 / 9.80665   # kN  -> kgf
U_STAIR_BARS = ["RB6", "RB9", "DB10", "DB12", "DB16", "DB20", "DB25"]

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


STAIR_TYPES = [
    "Straight Stair (บันไดช่วงตรง)",
    "U Shape Stair (บันไดหักกลับ)",
    "L Shape Stair (บันไดหักฉาก)",
    "Slabless Stair (บันไดพับผ้า)",
    "Free Standing Stair (บันไดชานพักลอย)",
    "Spiral Stair (บันไดเวียน)",
]

UNDER_CONSTRUCTION = "กำลังอยู่ระหว่างการพัฒนา (Under Construction)"


def render_stair_module():
    stair_type = st.selectbox("เลือกประเภทบันได (Stair Type)", STAIR_TYPES,
                              key="stair_type")
    if stair_type == "Straight Stair (บันไดช่วงตรง)":
        _render_straight_stair()
    elif stair_type == "U Shape Stair (บันไดหักกลับ)":
        _render_u_shape_stair()
    else:
        st.info(UNDER_CONSTRUCTION)


def _render_u_shape_stair():
    st.title("การออกแบบบันไดหักกลับ (U-Shape)")
    st.caption("หนึ่งช่วงบันได — พื้นเอียงรับแรงแบบช่วงเดี่ยว พาดจากพื้นถึงชานพัก "
               "แถบกว้าง 1 ม. ตามมาตรฐาน ACI 318M-08")

    b = STRIP_WIDTH   # 1 m per-metre strip

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        T_cm = st.number_input("ลูกนอน T (cm)", min_value=20.0, value=25.0,
                               step=0.5, format="%.1f", key="u_T")
        N = int(st.number_input("จำนวนขั้น N", min_value=1, max_value=30,
                                value=10, step=1, key="u_N"))
        t_cm = st.number_input("ความหนาพื้นบันได t (cm)", min_value=8.0,
                               value=15.0, step=0.5, format="%.1f", key="u_t")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d", key="u_fc")
    with c2:
        R_cm = st.number_input("ลูกตั้ง R (cm)", min_value=10.0, value=17.5,
                               step=0.5, format="%.1f", key="u_R")
        L_land = st.number_input("ความยาวชานพักแนวนอน Lland (m)", min_value=0.5,
                                 value=1.2, step=0.05, format="%.3f", key="u_land")
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.0,
                                      value=2.0, step=0.5, format="%.1f",
                                      key="u_cov")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d", key="u_fy")
    with c3:
        W = st.number_input("ความกว้างบันได W (m)", min_value=0.8, value=1.2,
                            step=0.05, format="%.3f", key="u_W")
        SDL = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม SDL (kgf/m²)",
                              min_value=0.0, value=150.0, step=10.0, key="u_sdl")
        LL = st.number_input("น้ำหนักบรรทุกจร LL (kgf/m²)", min_value=0.0,
                             value=300.0, step=50.0, key="u_ll")

    t = t_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA

    # ------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------
    L_flight = (N * T_cm) / 100.0                       # m
    L = L_flight + L_land                               # m
    theta = math.atan(R_cm / T_cm)                      # rad
    theta_deg = math.degrees(theta)
    t_avg_cm = (t_cm / math.cos(theta)) + (R_cm / 2.0)  # cm

    # ------------------------------------------------------------------
    # Dead loads (kgf/m²) — exact MKS, concrete unit weight literally 2400.
    # Conservatively use the larger (flight) DL over the whole span.
    # ------------------------------------------------------------------
    flight_DL = (t_avg_cm / 100.0) * CONC_DENSITY_KGF + SDL
    landing_DL = (t_cm / 100.0) * CONC_DENSITY_KGF + SDL
    max_DL = max(flight_DL, landing_DL)
    Wu_kg = 1.2 * max_DL + 1.6 * LL                     # kgf/m²
    Wu = Wu_kg * KGF_TO_KN                              # kN/m² (ACI core only)
    Mu = Wu * L ** 2 / 8.0                              # kN·m/m

    # ------------------------------------------------------------------
    # Reinforcement selection
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม")
    m1, m2 = st.columns(2)
    with m1:
        main_size = st.selectbox("ขนาดเหล็กเสริมหลัก", U_STAIR_BARS,
                                 index=U_STAIR_BARS.index("DB12"),
                                 key="u_main_size")
        main_sp_cm = st.number_input("ระยะเรียงเหล็กเสริมหลัก (cm)",
                                     min_value=5.0, max_value=45.0, value=15.0,
                                     step=1.0, format="%.1f", key="u_main_sp")
    with m2:
        temp_size = st.selectbox("ขนาดเหล็กเสริมกันร้าว", U_STAIR_BARS,
                                 index=U_STAIR_BARS.index("RB9"),
                                 key="u_temp_size")
        temp_sp_cm = st.number_input("ระยะเรียงเหล็กเสริมกันร้าว (cm)",
                                     min_value=5.0, max_value=45.0, value=20.0,
                                     step=1.0, format="%.1f", key="u_temp_sp")

    main_area = bar_area(main_size)
    temp_area = bar_area(temp_size)
    main_dia = float(main_size[2:])
    main_sp = main_sp_cm * CM
    temp_sp = temp_sp_cm * CM

    d = t - covering - main_dia / 2.0
    if d <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — เพิ่มความหนาพื้นบันได t")
        return

    As_req, Rn, rho, feasible = _required_as_flexure(Mu, b, d, fc, fy)
    As_min = _temp_steel_ratio(fy) * b * t

    As_prov_main = main_area * (b / main_sp)
    As_prov_temp = temp_area * (b / temp_sp)

    max_sp_main = min(3.0 * t, 450.0)
    max_sp_temp = min(5.0 * t, 450.0)
    sp_main_ok = main_sp <= max_sp_main
    sp_temp_ok = temp_sp <= max_sp_temp

    # ------------------------------------------------------------------
    # Load analysis
    # ------------------------------------------------------------------
    st.subheader("การวิเคราะห์น้ำหนักบรรทุกและโมเมนต์")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| ช่วงพาดส่วนเอียง L_flight = N·T/100 | {L_flight:,.3f} m |
| ช่วงพาดรวม L = L_flight + L_land | **{L:,.3f} m** |
| มุมเอียง θ = atan(R/T) | {theta_deg:,.2f}° |
| ความหนาเฉลี่ยส่วนเอียง t_avg = t/cosθ + R/2 | {t_avg_cm:,.2f} cm |
| น้ำหนักคงที่ส่วนเอียง Flight DL | {flight_DL:,.1f} kgf/m² |
| น้ำหนักคงที่ชานพัก Landing DL | {landing_DL:,.1f} kgf/m² |
| น้ำหนักคงที่ออกแบบ (max) | {max_DL:,.1f} kgf/m² |
| น้ำหนักบรรทุกประลัย Wu = 1.2·max DL + 1.6·LL | {Wu_kg:,.1f} kgf/m² |
| โมเมนต์ประลัย Mu = Wu·L²/8 | **{Mu * KN_TO_KGF:,.0f} kgf-m/m** |
"""
    )

    st.subheader("ขั้นตอนการคำนวณเหล็กเสริม")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| Ø เหล็กหลัก | {main_dia:.1f} mm |
| ความลึกประสิทธิผล d = t − covering − Ø/2 | **{d / CM:,.2f} cm** |
| Rn = Mu/(φ·b·d²) | {Rn / KSC_TO_MPA:,.1f} ksc |
"""
    )

    if not feasible:
        st.error("หน้าตัดบางเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว "
                 "(1 − 2·Rn/(0.85·f'c) < 0) — เพิ่ม t หรือ f'c")
        st.markdown(
            f"As,min = **{As_min / 100.0:,.2f} cm²/m**  ·  As หลักที่จัดให้ = "
            f"**{As_prov_main / 100.0:,.2f} cm²/m**"
        )
        try:
            st.image(draw_u_stair_elevation(
                        T_cm, R_cm, N, L_land, t_cm, span_m=L,
                        main_label=f"เหล็กหลัก {main_size} @ {main_sp_cm:.0f} cm"),
                     caption="รายละเอียดหน้าตัด (Section Detailing)")
        except Exception as exc:  # pragma: no cover
            st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")
        st.error(f"{FAIL_TXT} — หน้าตัดไม่เพียงพอสำหรับการดัด")
        return

    As_design = max(As_req, As_min)
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| ρ = 0.85·f'c/fy · (1 − √(1 − 2·Rn/0.85·f'c)) | {rho:.5f} |
| As ที่ต้องการ (การดัด) = ρ·b·d | **{As_req / 100.0:,.2f} cm²/m** |
| As,min (กันร้าว/อุณหภูมิ) | {As_min / 100.0:,.2f} cm²/m |
| As หลักที่ต้องการที่ควบคุม = max | **{As_design / 100.0:,.2f} cm²/m** |
| หลัก: {main_size} @ {main_sp_cm:.1f} cm | **{As_prov_main / 100.0:,.2f} cm²/m** |
| ระยะเรียงสูงสุด (หลัก) = min(3t, 450) | {max_sp_main / CM:,.1f} cm |
| กันร้าว: {temp_size} @ {temp_sp_cm:.1f} cm | **{As_prov_temp / 100.0:,.2f} cm²/m** |
| ระยะเรียงสูงสุด (กันร้าว) = min(5t, 450) | {max_sp_temp / CM:,.1f} cm |
"""
    )

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    main_req_ok = As_prov_main >= As_req
    main_min_ok = As_prov_main >= As_min
    temp_min_ok = As_prov_temp >= As_min
    passed = (main_req_ok and main_min_ok and temp_min_ok
              and sp_main_ok and sp_temp_ok)

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    st.markdown(
        f"""
| การตรวจสอบ | ที่ต้องการ | ที่จัดให้ | สถานะ |
|---|---|---|---|
| As หลัก ≥ As,required | {As_req / 100.0:,.2f} cm²/m | {As_prov_main / 100.0:,.2f} cm²/m | {_s(main_req_ok)} |
| As หลัก ≥ As,min | {As_min / 100.0:,.2f} cm²/m | {As_prov_main / 100.0:,.2f} cm²/m | {_s(main_min_ok)} |
| As กันร้าว ≥ As,min | {As_min / 100.0:,.2f} cm²/m | {As_prov_temp / 100.0:,.2f} cm²/m | {_s(temp_min_ok)} |
| ระยะเรียงหลัก ≤ ขีดจำกัด | s = {main_sp_cm:.1f} cm | {max_sp_main / CM:,.1f} cm | {_s(sp_main_ok)} |
| ระยะเรียงกันร้าว ≤ ขีดจำกัด | s = {temp_sp_cm:.1f} cm | {max_sp_temp / CM:,.1f} cm | {_s(sp_temp_ok)} |
"""
    )

    # ------------------------------------------------------------------
    # Elevation drawing
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_u_stair_elevation(
            T_cm, R_cm, N, L_land, t_cm, span_m=L,
            main_label=f"เหล็กหลัก {main_size} @ {main_sp_cm:.0f} cm")
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    if passed:
        st.success(f"{PASS_TXT} — ผ่านการตรวจสอบเหล็กเสริมหลักและเหล็กเสริมกันร้าว")

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_u_stair_report(
            {
                "T_cm": T_cm, "R_cm": R_cm, "N": N, "L_land": L_land, "W": W,
                "t": t, "covering": covering,
                "SDL_kgm2": SDL, "LL_kgm2": LL, "fc": fc, "fy": fy,
                "project": get_project_info(),
            },
            {
                "L_flight": L_flight, "L": L, "theta_deg": theta_deg,
                "t_avg_cm": t_avg_cm, "flight_DL": flight_DL,
                "landing_DL": landing_DL, "max_DL": max_DL,
                "Wu_kg": Wu_kg, "Wu_kN": Wu, "Mu": Mu, "d": d,
                "As_req": As_req, "As_min": As_min,
                "main_size": main_size, "main_sp_cm": main_sp_cm,
                "As_prov_main": As_prov_main, "max_sp_main": max_sp_main,
                "temp_size": temp_size, "temp_sp_cm": temp_sp_cm,
                "As_prov_temp": As_prov_temp, "max_sp_temp": max_sp_temp,
                "main_req_ok": main_req_ok, "main_min_ok": main_min_ok,
                "temp_min_ok": temp_min_ok,
                "sp_main_ok": sp_main_ok, "sp_temp_ok": sp_temp_ok,
                "section_img": section_img, "status": "PASS",
            },
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="u_stair_report.pdf",
            mime="application/pdf",
        )
    else:
        reasons = []
        if not main_req_ok:
            reasons.append("As หลัก < ที่ต้องการ")
        if not main_min_ok:
            reasons.append("As หลัก < As,min")
        if not temp_min_ok:
            reasons.append("As กันร้าว < As,min")
        if not sp_main_ok:
            reasons.append(f"ระยะเรียงหลัก > {max_sp_main / CM:.1f} cm")
        if not sp_temp_ok:
            reasons.append(f"ระยะเรียงกันร้าว > {max_sp_temp / CM:.1f} cm")
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


def _render_straight_stair():
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
        SDL_kgf = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม SDL (kgf/m²)",
                                  min_value=0.0, value=150.0, step=10.0)
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d")
    with c3:
        R_cm = st.number_input("ลูกตั้ง R (cm)", min_value=10.0,
                               value=17.5, step=0.01, format="%.2f")
        LL_kgf = st.number_input("น้ำหนักบรรทุกจร LL (kgf/m²)", min_value=0.0,
                                 value=300.0, step=50.0)
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.5,
                                      value=2.0, step=0.01, format="%.2f")

    st.number_input("ความกว้างแถบออกแบบ b (cm)", value=b_cm, disabled=True,
                    step=0.01, format="%.2f", help="กำหนดคงที่ที่แถบกว้าง 1 ม.")

    # MKS -> SI for the ACI calculation core (L already in metres)
    t = t_cm * CM
    T = T_cm * CM
    R = R_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA
    # SDL / LL stay in kgf/m² here; the load block below keeps the dead-load
    # arithmetic in exact MKS and only mirrors the result to SI afterwards.

    # ------------------------------------------------------------------
    # Reinforcement
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม")
    m1, m2 = st.columns(2)
    with m1:
        main_size = st.selectbox("ขนาดเหล็กเสริมหลัก", list(rebars.keys()),
                                 index=list(rebars).index("DB12"))
        main_sp_cm = st.number_input("ระยะเรียงเหล็กเสริมหลัก (cm)", min_value=5.0,
                                     max_value=45.0, value=15.0, step=1.0,
                                     format="%.1f")
    with m2:
        temp_size = st.selectbox("ขนาดเหล็กเสริมกันร้าว", list(rebars.keys()),
                                 index=list(rebars).index("RB9"))
        temp_sp_cm = st.number_input("ระยะเรียงเหล็กเสริมกันร้าว (cm)",
                                     min_value=5.0, max_value=45.0,
                                     value=20.0, step=1.0, format="%.1f")

    main_spacing = main_sp_cm * CM               # cm -> mm
    temp_spacing = temp_sp_cm * CM

    main_area = rebars[main_size]
    temp_area = rebars[temp_size]
    main_dia = float(main_size[2:])
    temp_dia = float(temp_size[2:])

    # ------------------------------------------------------------------
    # Geometry & loads
    # ------------------------------------------------------------------
    theta = math.atan(R / T)                                     # rad
    waist_term = (t / 1000.0) / math.cos(theta) + (R / 2000.0)   # m (equiv. slab thk)

    # --- Exact MKS loads: concrete unit weight is literally 2400 kgf/m³ ----
    SW_kgf = CONC_DENSITY_KGF * waist_term                       # kgf/m²
    DL_kgf = SW_kgf + SDL_kgf                                    # kgf/m²
    wu_kgf = 1.2 * DL_kgf + 1.6 * LL_kgf                         # kgf/m (1 m strip)

    # --- SI mirror for the ACI 318M-08 calculation core only --------------
    SW = SW_kgf * KGF_TO_KN                                      # kN/m²
    DL = DL_kgf * KGF_TO_KN                                      # kN/m²
    wu = wu_kgf * KGF_TO_KN                                      # kN/m (1 m strip)
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
| น้ำหนักตัวเอง SW = 2400·(t/cosθ + R/2) | {SW_kgf:,.1f} kgf/m² |
| น้ำหนักบรรทุกคงที่รวม DL = SW + SDL | {DL_kgf:,.1f} kgf/m² |
| น้ำหนักบรรทุกประลัย wu = 1.2·DL + 1.6·LL | **{wu_kgf:,.1f} kgf/m** |
| โมเมนต์ประลัย Mu = wu·L²/8 | **{Mu * KN_TO_KGF:,.0f} kgf-m/m** |
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
| Rn = Mu / (φ·b·d²) | {Rn / KSC_TO_MPA:,.1f} ksc |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing — 1 m strip cross-section (t, covering, spacings in mm)
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_slab_strip(
            t, covering, main_dia, temp_dia, main_spacing, temp_spacing,
            main_label=f"เหล็กหลัก {main_size} @ {main_sp_cm:.0f} cm",
            temp_label=f"เหล็กกันร้าว {temp_size} @ {temp_sp_cm:.0f} cm",
            span_m=L)
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
| หลัก: {main_size} @ {main_sp_cm:.1f} cm → {main_area / 100.0:,.2f} cm² × (100/s) | **{As_prov_main / 100.0:,.2f} cm²/m** |
| ระยะเรียงสูงสุด (หลัก) = min(3t, 450) | {max_sp_main / CM:,.1f} cm |
| กันร้าว: {temp_size} @ {temp_sp_cm:.1f} cm → {temp_area / 100.0:,.2f} cm² × (100/s) | **{As_prov_temp / 100.0:,.2f} cm²/m** |
| ระยะเรียงสูงสุด (กันร้าว) = min(5t, 450) | {max_sp_temp / CM:,.1f} cm |
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
| ระยะเรียงหลัก ≤ ขีดจำกัด | s = {main_sp_cm:.1f} cm | {max_sp_main / CM:,.1f} cm | {_s(sp_main_ok)} |
| ระยะเรียงกันร้าว ≤ ขีดจำกัด | s = {temp_sp_cm:.1f} cm | {max_sp_temp / CM:,.1f} cm | {_s(sp_temp_ok)} |
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
                "L": L, "T": T, "R": R, "t": t,
                "SDL_kgf": SDL_kgf, "LL_kgf": LL_kgf,
                "covering": covering, "fc": fc, "fy": fy, "b": b,
                "project": get_project_info(),
            },
            {
                "theta_deg": math.degrees(theta),
                "SW_kgf": SW_kgf, "DL_kgf": DL_kgf, "wu_kgf": wu_kgf,
                "Mu": Mu, "d": d,
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
                f"ระยะเรียงหลัก {main_sp_cm:.1f} > สูงสุด {max_sp_main / CM:,.1f} cm"
            )
        if not sp_temp_ok:
            reasons.append(
                f"ระยะเรียงกันร้าว {temp_sp_cm:.1f} > สูงสุด {max_sp_temp / CM:,.1f} cm"
            )
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


if __name__ == "__main__":
    render_stair_module()
