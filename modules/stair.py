"""Streamlit UI — RC straight stair design to ACI 318M-08. Thai UI, cm / cm².

Straight flight designed as a simply-supported one-way slab spanning the
horizontal projection L (metres), on a 1 m wide strip.

UI units: span L in m (3 decimals); tread / riser / waist / covering in cm
(converted to mm internally); steel areas reported in cm² per metre.
"""

import math

import streamlit as st

from utils import ui
from utils.aci_318m import phi, rebars, bar_area, rho_max_flexure
from utils.drawing import (draw_slab_strip, draw_u_stair_elevation,
                           draw_stair_elevation, fig_to_png_buf)
from utils.project import get_project_info, render_report_expander
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


STAIR_BAR_SIZES = ["RB9", "DB10", "DB12", "DB16", "DB20"]


def _as_flexure_ksc(Mu_kgfm, b_cm, d_cm, fc_ksc, fy_ksc):
    """Singly-reinforced As (cm2) for a strip ``b_cm`` wide, MKS units.
    Returns (As_cm2, feasible)."""
    if d_cm <= 0.0 or Mu_kgfm <= 0.0:
        return 0.0, True
    Rn = (Mu_kgfm * 100.0) / (phi["flexure"] * b_cm * d_cm ** 2)   # ksc
    disc = 1.0 - 2.0 * Rn / (0.85 * fc_ksc)
    if disc < 0.0:
        return None, False
    rho = (0.85 * fc_ksc / fy_ksc) * (1.0 - math.sqrt(disc))
    return rho * b_cm * d_cm, True


def _spacing_for(Ab_cm2, As_req_cm2, s_max_cm):
    """Bar spacing (cm, rounded down to 2.5 cm) delivering ``As_req`` per
    metre with a bar of area ``Ab``; capped at ``s_max``.  (S_cm, As_prov)."""
    if As_req_cm2 <= 1.0e-9:
        S = s_max_cm
    else:
        S_req = Ab_cm2 * 100.0 / As_req_cm2
        S = min(math.floor(S_req / 2.5) * 2.5, s_max_cm)
        S = max(S, 2.5)
    return S, Ab_cm2 * 100.0 / S


def _beta1_ksc(fc_ksc):
    """Stress-block factor beta1 for f'c in ksc (ACI 318M-08 10.2.7.3, MKS
    form): 0.85 up to 280 ksc, then -0.05 per 70 ksc, floor 0.65."""
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def _rho_max_ksc(fc_ksc, fy_ksc):
    """Tension-controlled (net tensile strain 0.005) maximum reinforcement
    ratio, MKS (ACI 318M-08 10.3.4).  As_max = rho_max * b * d; a section
    with As > As_max has eps_t < 0.005 (and, when eps_t < 0.004, is not a
    permitted flexural member per 10.3.5)."""
    return (0.85 * _beta1_ksc(fc_ksc) * fc_ksc / fy_ksc
            * 0.003 / (0.003 + 0.005))


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
    ui.breadcrumb("Member Design", "Stair")
    ui.page_header("Stair Design",
                   "Reinforced Concrete Stair Design — ACI 318M-08")
    stair_type = st.selectbox("เลือกประเภทบันได (Stair Type)", STAIR_TYPES,
                              key="stair_type")
    if stair_type == "Straight Stair (บันไดช่วงตรง)":
        _render_straight_stair()
    elif stair_type == "U Shape Stair (บันไดหักกลับ)":
        _render_u_shape_stair()
    else:
        st.info(UNDER_CONSTRUCTION)


def _render_u_shape_stair():
    st.caption("หนึ่งช่วงบันได — พื้นเอียงรับแรงแบบช่วงเดี่ยว พาดจากพื้นถึงชานพัก "
               "แถบกว้าง 1 ม. ตามมาตรฐาน ACI 318M-08")

    b = STRIP_WIDTH   # 1 m per-metre strip

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.markdown("#### MEMBER INPUT")
    with ui.section_card("GEOMETRY · MATERIAL · LOADS — ข้อมูลป้อนเข้า"):
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
            L_land = st.number_input("ความยาวชานพักแนวนอน Lland (m)",
                                     min_value=0.5, value=1.2, step=0.05,
                                     format="%.3f", key="u_land")
            covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.0,
                                          value=2.0, step=0.5, format="%.1f",
                                          key="u_cov")
            fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)",
                                     min_value=2800, value=4000, step=100,
                                     format="%d", key="u_fy")
        with c3:
            W = st.number_input("ความกว้างบันได W (m)", min_value=0.8, value=1.2,
                                step=0.05, format="%.3f", key="u_W")
            SDL = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม SDL (kgf/m²)",
                                  min_value=0.0, value=150.0, step=10.0,
                                  key="u_sdl")
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
    with ui.section_card("REINFORCEMENT — เหล็กเสริม"):
        m1, m2 = st.columns(2)
        with m1:
            main_size = st.selectbox("ขนาดเหล็กเสริมหลัก", U_STAIR_BARS,
                                     index=U_STAIR_BARS.index("DB12"),
                                     key="u_main_size")
            main_sp_cm = st.number_input("ระยะเรียงเหล็กเสริมหลัก (cm)",
                                         min_value=5.0, max_value=45.0,
                                         value=15.0, step=1.0, format="%.1f",
                                         key="u_main_sp")
        with m2:
            temp_size = st.selectbox("ขนาดเหล็กเสริมกันร้าว", U_STAIR_BARS,
                                     index=U_STAIR_BARS.index("RB9"),
                                     key="u_temp_size")
            temp_sp_cm = st.number_input("ระยะเรียงเหล็กเสริมกันร้าว (cm)",
                                         min_value=5.0, max_value=45.0,
                                         value=20.0, step=1.0, format="%.1f",
                                         key="u_temp_sp")

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
    # Load analysis + reinforcement steps (collapsed)
    # ------------------------------------------------------------------
    st.markdown("#### DETAILED CALCULATION — การวิเคราะห์และการคำนวณ")
    with st.expander("รายละเอียดการคำนวณทีละขั้น (Detailed calculation)",
                     expanded=False):
        st.markdown("**การวิเคราะห์น้ำหนักบรรทุกและโมเมนต์**")
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

        st.markdown("**ขั้นตอนการคำนวณเหล็กเสริม**")
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
    st.markdown("#### REINFORCEMENT / DETAIL — รายละเอียดเหล็กเสริม")
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
    # Verdict booleans (unchanged logic / order)
    # ------------------------------------------------------------------
    main_req_ok = As_prov_main >= As_req
    main_min_ok = As_prov_main >= As_min
    temp_min_ok = As_prov_temp >= As_min
    # Tension-controlled / maximum-steel limit (ACI 318M-08 10.3.4; eps_t
    # >= 0.004 mandatory for a flexural member, 10.3.5).  As_req is sized
    # with a fixed phi = 0.90 (in _required_as_flexure); the provided main
    # steel must not push the waist past the tension-controlled limit.
    As_max_main = rho_max_flexure(fc, fy) * b * d          # mm^2 / m
    ductile_ok = As_prov_main <= As_max_main
    passed = (main_req_ok and main_min_ok and temp_min_ok
              and sp_main_ok and sp_temp_ok and ductile_ok)

    # ==================================================================
    # DESIGN SUMMARY  (reads the existing verdict + already-computed
    # values only — no recomputation)
    # ==================================================================
    st.markdown("#### DESIGN SUMMARY")
    with st.container(border=True):
        ss1, ss2 = st.columns([1, 3])
        with ss1:
            st.markdown("**STATUS**")
            ui.status_badge("pass" if passed else "fail",
                            "PASS" if passed else "FAIL")
        with ss2:
            st.caption(f"บันไดหักกลับ (U-Shape) — {N} ขั้น · ช่วงพาด "
                       f"{L:,.3f} m · θ {theta_deg:,.1f}° · t {t_cm:,.1f} cm")

        mk1, mk2, mk3, mk4 = st.columns(4)
        with mk1:
            ui.kpi("Mu (kgf-m/m)", f"{Mu * KN_TO_KGF:,.0f}")
        with mk2:
            ui.kpi("As หลักควบคุม (cm²/m)", f"{As_design / 100.0:,.2f}")
        with mk3:
            ui.kpi("เหล็กหลัก", f"{main_size} @ {main_sp_cm:.0f}")
        with mk4:
            ui.kpi("เหล็กกันร้าว", f"{temp_size} @ {temp_sp_cm:.0f}")

        _sb = st.columns(5)
        for _c, (_lab, _ok) in zip(_sb, [
                ("As หลัก: req ≤ As ≤ max", main_req_ok and ductile_ok),
                ("As หลัก ≥ min", main_min_ok),
                ("As กันร้าว ≥ min", temp_min_ok),
                ("ระยะเรียงหลัก", sp_main_ok),
                ("ระยะเรียงกันร้าว", sp_temp_ok)]):
            with _c:
                st.caption(_lab)
                ui.status_badge(bool(_ok))

    # ==================================================================
    # DESIGN CHECKS  (existing check rows — same demand / capacity /
    # status booleans, rendered as an engineering table)
    # ==================================================================
    st.markdown("#### DESIGN CHECKS — ผลการตรวจสอบ")
    checks = [
        ("As หลัก ≥ As,required", f"{As_req / 100.0:,.2f} cm²/m",
         f"{As_prov_main / 100.0:,.2f} cm²/m", main_req_ok),
        ("As หลัก ≥ As,min", f"{As_min / 100.0:,.2f} cm²/m",
         f"{As_prov_main / 100.0:,.2f} cm²/m", main_min_ok),
        ("As กันร้าว ≥ As,min", f"{As_min / 100.0:,.2f} cm²/m",
         f"{As_prov_temp / 100.0:,.2f} cm²/m", temp_min_ok),
        ("ระยะเรียงหลัก ≤ ขีดจำกัด", f"s = {main_sp_cm:.1f} cm",
         f"{max_sp_main / CM:,.1f} cm", sp_main_ok),
        ("ระยะเรียงกันร้าว ≤ ขีดจำกัด", f"s = {temp_sp_cm:.1f} cm",
         f"{max_sp_temp / CM:,.1f} cm", sp_temp_ok),
        ("เหล็กหลัก ≤ As,max (tension-controlled, ACI 10.3.4)",
         f"{As_prov_main / 100.0:,.2f} cm²/m",
         f"{As_max_main / 100.0:,.2f} cm²/m", ductile_ok),
    ]
    ui.engineering_table(
        ["การตรวจสอบ", "ที่ต้องการ", "ที่จัดให้", "สถานะ"],
        [[name, dem, cap, "ผ่าน (PASS)" if ok else "ไม่ผ่าน (FAIL)"]
         for name, dem, cap, ok in checks],
        right_from=1,
    )

    # ------------------------------------------------------------------
    # Elevation drawing
    # ------------------------------------------------------------------
    st.markdown("#### DRAWING / DETAIL — รายละเอียดหน้าตัด")
    section_img = None
    try:
        section_img = draw_u_stair_elevation(
            T_cm, R_cm, N, L_land, t_cm, span_m=L,
            main_label=f"เหล็กหลัก {main_size} @ {main_sp_cm:.0f} cm")
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    st.markdown("#### VERDICT — ผลการตรวจสอบ")
    if passed:
        st.success(f"{PASS_TXT} — ผ่านการตรวจสอบเหล็กเสริมหลักและเหล็กเสริมกันร้าว")

        st.markdown("#### OUTPUT / REPORT — รายงานการคำนวณ")
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
        if not ductile_ok:
            reasons.append(f"As หลัก > As,max — ไม่เป็น tension-controlled "
                           f"({As_prov_main / 100.0:,.2f} > "
                           f"{As_max_main / 100.0:,.2f} cm²/m)")
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
    st.caption("ออกแบบเป็นพื้นทางเดียวเอียง (inclined one-way slab) แถบกว้าง "
               "1 เมตร ตามมาตรฐาน ACI 318M-08 — หน่วยเมตริก "
               "(cm, kgf, kgf-m, ksc, kgf/m²)")

    b = 100.0        # cm — a 1 m wide strip

    st.markdown("#### MEMBER INPUT")

    # ------------------------------------------------------------------
    # 1. Geometry
    # ------------------------------------------------------------------
    with ui.section_card("GEOMETRY — รูปเรขาคณิต"):
        g1, g2, g3, g4 = st.columns(4)
        with g1:
            R_cm = st.number_input("ลูกตั้ง R (cm)", min_value=10.0, value=17.5,
                                   step=0.5, format="%.1f", key="st_R")
        with g2:
            T_cm = st.number_input("ลูกนอน T (cm)", min_value=20.0, value=25.0,
                                   step=0.5, format="%.1f", key="st_T")
        with g3:
            N = int(st.number_input("จำนวนขั้น N", min_value=3, value=12,
                                    step=1, key="st_N"))
        with g4:
            W_m = st.number_input("ความกว้างบันได W (m)", min_value=0.8,
                                  value=1.20, step=0.05, format="%.2f",
                                  key="st_W")

    # ------------------------------------------------------------------
    # 2. Section & Material
    # ------------------------------------------------------------------
    with ui.section_card("SECTION & MATERIAL — หน้าตัดและวัสดุ"):
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            t_cm = st.number_input("ความหนาท้องบันได t (cm)", min_value=8.0,
                                   value=15.0, step=0.5, format="%.1f",
                                   key="st_t")
        with s2:
            cov_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.5,
                                     value=2.0, step=0.5, format="%.1f",
                                     key="st_cov")
        with s3:
            fc_ksc = st.number_input("f'c (ksc)", min_value=180, value=240,
                                     step=10, format="%d", key="st_fc")
        with s4:
            fy_ksc = st.number_input("fy (ksc)", min_value=2400, value=4000,
                                     step=100, format="%d", key="st_fy")

    # ------------------------------------------------------------------
    # 3. Loads
    # ------------------------------------------------------------------
    with ui.section_card("LOADS — แรงกระทำ"):
        l1, l2 = st.columns(2)
        with l1:
            SDL = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม SDL (kgf/m²)",
                                  min_value=0.0, value=150.0, step=10.0,
                                  key="st_sdl")
        with l2:
            LL = st.number_input("น้ำหนักบรรทุกจร LL (kgf/m²)", min_value=0.0,
                                 value=300.0, step=50.0, key="st_ll")

    # ------------------------------------------------------------------
    # 4. Reinforcement
    # ------------------------------------------------------------------
    with ui.section_card("REINFORCEMENT — เหล็กเสริม"):
        r1, r2 = st.columns(2)
        with r1:
            main_size = st.selectbox("เหล็กเสริมหลัก (ตามยาว) — ขนาด",
                                     STAIR_BAR_SIZES,
                                     index=STAIR_BAR_SIZES.index("DB12"),
                                     key="st_msz")
        with r2:
            temp_size = st.selectbox("เหล็กกันร้าว (ตามขวาง) — ขนาด",
                                     STAIR_BAR_SIZES,
                                     index=STAIR_BAR_SIZES.index("DB10"),
                                     key="st_tsz")

    # ---- MKS working values ----------------------------------------
    R, T, t, cov = float(R_cm), float(T_cm), float(t_cm), float(cov_cm)
    fc, fy = float(fc_ksc), float(fy_ksc)
    db_main = float(main_size[2:]) / 10.0        # cm
    Ab_main = bar_area(main_size) / 100.0        # cm2 per bar
    Ab_temp = bar_area(temp_size) / 100.0

    # ---- Geometry -----------------------------------------------
    Lx = (N * T) / 100.0                         # m — horizontal span
    theta = math.atan2(R, T)                     # rad
    cos_th = math.cos(theta)

    # ---- Loads per horizontal square metre (kgf/m²) ------------
    DL_waist = (t / 100.0) * CONC_DENSITY_KGF / cos_th   # waist slab (sloped)
    DL_steps = ((R / 100.0) / 2.0) * CONC_DENSITY_KGF    # triangular steps
    DL = DL_waist + DL_steps + SDL
    Wu = 1.2 * DL + 1.6 * LL                     # kgf/m²  (= kgf/m on 1 m strip)
    Mu = Wu * Lx ** 2 / 8.0                      # kgf-m per 1 m strip

    # ---- Effective depth (cm) ---------------------------------
    d = t - cov - db_main / 2.0
    if d <= 0.0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — เพิ่ม t หรือลดระยะหุ้ม / ขนาดเหล็ก")
        return

    # ---- Flexural + temperature steel ------------------------
    As_req, feas = _as_flexure_ksc(Mu, b, d, fc, fy)
    if not feas:
        st.error("ท้องบันไดบางเกินไปสำหรับการดัด — เพิ่ม t หรือ f'c")
        return
    temp_ratio = _temp_steel_ratio(fy * KSC_TO_MPA)
    As_temp_min = temp_ratio * b * t             # cm2 / m
    As_main = max(As_req or 0.0, As_temp_min)

    # Tension-controlled / maximum-steel limit (ACI 318M-08 10.3.4;
    # eps_t >= 0.004 is mandatory for a flexural member per 10.3.5).
    # As_main above is sized with a fixed phi = 0.90 (in _as_flexure_ksc),
    # valid ONLY while the waist stays tension-controlled (As <= As_max).
    As_max_main = _rho_max_ksc(fc, fy) * b * d
    ductile_ok = As_main <= As_max_main

    s_max_main = min(3.0 * t, 45.0)              # ACI 13.3.2 / 10.5.4
    s_max_temp = min(5.0 * t, 45.0)             # ACI 7.12.2.2
    S_main, Asp_main = _spacing_for(Ab_main, As_main, s_max_main)
    S_temp, Asp_temp = _spacing_for(Ab_temp, As_temp_min, s_max_temp)

    main_ok = 7.5 <= S_main <= s_max_main
    temp_ok = 7.5 <= S_temp <= s_max_temp
    passed = main_ok and temp_ok and ductile_ok

    # ==================================================================
    # DESIGN SUMMARY  (reads the existing verdict + already-computed
    # values only — no recomputation)
    # ==================================================================
    st.markdown("#### DESIGN SUMMARY")
    with st.container(border=True):
        ss1, ss2 = st.columns([1, 3])
        with ss1:
            st.markdown("**STATUS**")
            ui.status_badge("pass" if passed else "fail",
                            "PASS" if passed else "FAIL")
        with ss2:
            st.caption(f"บันไดช่วงตรง — {N} ขั้น · ช่วงพาดแนวราบ Lx {Lx:,.2f} m "
                       f"· θ {math.degrees(theta):,.1f}° · t {t:,.1f} cm")

        mk1, mk2, mk3, mk4 = st.columns(4)
        with mk1:
            ui.kpi("Mu (kgf-m)", f"{Mu:,.0f}")
        with mk2:
            ui.kpi("As หลักควบคุม (cm²/m)", f"{As_main:,.2f}")
        with mk3:
            ui.kpi(f"เหล็กหลัก — {main_size}",
                   f"@ {S_main:,.1f} / {s_max_main:,.1f} cm")
        with mk4:
            ui.kpi(f"เหล็กกันร้าว — {temp_size}",
                   f"@ {S_temp:,.1f} / {s_max_temp:,.1f} cm")

        sb1, sb2 = st.columns(2)
        with sb1:
            st.caption(f"ระยะเรียงเหล็กหลัก — {main_size} "
                       f"(S {S_main:,.1f} / s_max {s_max_main:,.1f} cm)")
            ui.status_badge(bool(main_ok))
        with sb2:
            st.caption(f"ระยะเรียงเหล็กกันร้าว — {temp_size} "
                       f"(S {S_temp:,.1f} / s_max {s_max_temp:,.1f} cm)")
            ui.status_badge(bool(temp_ok))

    # ==================================================================
    # DESIGN CHECKS  (existing check tuples — one source, rendered here
    # and passed unchanged to the PDF report)
    # ==================================================================
    st.markdown("#### DESIGN CHECKS — ผลการตรวจสอบ")
    checks = [
        ("ระยะเรียงเหล็กหลัก (S ≤ min(3t,45))", f"{S_main:.1f} cm",
         f"{s_max_main:.1f} cm", main_ok),
        ("ระยะเรียงเหล็กกันร้าว (S ≤ min(5t,45))", f"{S_temp:.1f} cm",
         f"{s_max_temp:.1f} cm", temp_ok),
        ("As เหล็กหลักที่จัดให้ ≥ ที่ต้องการ",
         f"{Asp_main:.2f} cm²/m", f"{As_main:.2f} cm²/m",
         Asp_main >= As_main - 1e-6),
        ("เหล็กหลัก ≤ As,max (tension-controlled, ACI 10.3.4)",
         f"{As_main:.2f} cm²/m", f"{As_max_main:.2f} cm²/m", ductile_ok),
    ]
    ui.engineering_table(
        ["รายการตรวจสอบ", "Demand", "Capacity", "สถานะ"],
        [[name, dem, cap, "ผ่าน (PASS)" if ok else "ไม่ผ่าน (FAIL)"]
         for name, dem, cap, ok in checks],
        right_from=1,
    )
    if not ductile_ok:
        st.warning("เหล็กหลัก > As,max — ท้องบันไดบางเกินไป/รับโมเมนต์มากเกินไป "
                   "(ไม่เป็น tension-controlled ตาม ACI 318M-08 10.3.4/10.3.5) "
                   "— เพิ่มความหนาท้องบันได t")

    # ==================================================================
    # DETAILED CALCULATION  (existing breakdown tables, collapsed)
    # ==================================================================
    st.markdown("#### DETAILED CALCULATION — การวิเคราะห์และการคำนวณ")
    with st.expander("รายละเอียดการคำนวณทีละขั้น (Detailed calculation)",
                     expanded=False):
        st.markdown("**การวิเคราะห์น้ำหนักบรรทุก**")
        st.markdown(
            f"""
| รายการ | ค่า |
|---|---|
| ช่วงพาดในแนวราบ Lx = N·T/100 = {N}·{T:.1f}/100 | **{Lx:,.2f} m** |
| มุมลาดเอียง θ = arctan(R/T) | {math.degrees(theta):,.2f}° |
| DL ท้องบันได = (t/100)·2400 / cosθ | {DL_waist:,.1f} kgf/m² |
| DL ขั้นบันได = (R/100 / 2)·2400 | {DL_steps:,.1f} kgf/m² |
| DL รวม = ท้องบันได + ขั้นบันได + SDL | **{DL:,.1f} kgf/m²** |
| น้ำหนักบรรทุกประลัย Wu = 1.2·DL + 1.6·LL | **{Wu:,.1f} kgf/m²** |
| โมเมนต์ประลัย Mu = Wu·Lx²/8 (ต่อแถบ 1 ม.) | **{Mu:,.0f} kgf-m** |
"""
        )

        st.markdown("**ขั้นตอนการคำนวณ**")
        st.markdown(
            f"""
| รายการ | ค่า |
|---|---|
| ความลึกประสิทธิผล d = t − covering − Ø_หลัก/2 | **{d:,.2f} cm** |
| As เหล็กหลักที่ต้องการ (การดัด) | {(As_req or 0.0):,.2f} cm²/m |
| อัตราส่วนเหล็กกันร้าว/อุณหภูมิ | {temp_ratio:.4f} |
| As,temp = ratio·b·t | **{As_temp_min:,.2f} cm²/m** |
| As เหล็กหลักควบคุม = max(การดัด, As,temp) | **{As_main:,.2f} cm²/m** |
| ระยะเรียงสูงสุด — เหล็กหลัก min(3t, 45) | {s_max_main:,.1f} cm |
| ระยะเรียงสูงสุด — เหล็กกันร้าว min(5t, 45) | {s_max_temp:,.1f} cm |
| ระยะเรียงที่จัดให้ — เหล็กหลัก ({main_size}) | **{S_main:,.1f} cm** (As≈{Asp_main:,.2f} cm²/m) |
| ระยะเรียงที่จัดให้ — เหล็กกันร้าว ({temp_size}) | **{S_temp:,.1f} cm** (As≈{Asp_temp:,.2f} cm²/m) |
"""
        )

    # ==================================================================
    # DRAWING / DETAIL  — CAD side elevation
    # ==================================================================
    st.markdown("#### DRAWING / DETAIL — รูปด้านบันได")
    section_img = None
    try:
        fig = draw_stair_elevation(
            R_cm=R, T_cm=T, N=N, t_cm=t, covering_cm=cov,
            main_label=f"Main: {main_size} @ {S_main:.0f} cm",
            temp_label=f"Temp: {temp_size} @ {S_temp:.0f} cm")
        st.pyplot(fig, use_container_width=True)
        st.caption("รูปด้านบันได (Stair Side Elevation)")
        section_img = fig_to_png_buf(fig)
    except Exception as exc:  # pragma: no cover
        st.warning(f"ไม่สามารถสร้างภาพรูปด้านได้: {exc}")

    # ==================================================================
    # VERDICT  (existing logic, existing text)
    # ==================================================================
    st.markdown("#### VERDICT — ผลการตรวจสอบรวม")
    if passed:
        st.success(f"{PASS_TXT} — ระยะเรียงเหล็กหลักและเหล็กกันร้าวผ่านเกณฑ์ "
                   f"ACI 318M-08")
    else:
        fails = []
        if not main_ok:
            fails.append(f"ระยะเรียงเหล็กหลัก S = {S_main:,.1f} cm "
                         f"(เกณฑ์ 7.5–{s_max_main:,.1f} cm)")
        if not temp_ok:
            fails.append(f"ระยะเรียงเหล็กกันร้าว S = {S_temp:,.1f} cm "
                         f"(เกณฑ์ 7.5–{s_max_temp:,.1f} cm)")
        if not ductile_ok:
            fails.append(f"เหล็กหลัก As = {As_main:,.2f} > As,max = "
                         f"{As_max_main:,.2f} cm²/m — ไม่เป็น tension-"
                         f"controlled (ACI 10.3.4/10.3.5)")
        st.error(f"{FAIL_TXT} — " + "; ".join(fails))

    # ==================================================================
    # OUTPUT / REPORT
    # ==================================================================
    st.markdown("#### OUTPUT / REPORT — รายงานการคำนวณ")
    render_report_expander(
        key="stair_straight", filename="stair_design_report.pdf",
        title="การออกแบบบันไดคอนกรีตเสริมเหล็ก (ACI 318M-08)",
        params=[
            ("ลูกตั้ง R", R, "cm", 1), ("ลูกนอน T", T, "cm", 1),
            ("จำนวนขั้น N", f"{N} ขั้น"),
            ("ความกว้างบันได W", W_m, "m", 2),
            ("ช่วงพาดในแนวราบ Lx = N·T", Lx, "m", 2),
            ("มุมลาดเอียง θ", math.degrees(theta), "องศา", 2),
            ("ความหนาท้องบันได t", t, "cm", 1),
            ("ระยะหุ้มคอนกรีต", cov, "cm", 1),
            ("f'c", fc, "ksc", 0), ("fy", fy, "ksc", 0),
            ("SDL", SDL, "kgf/m²", 0), ("LL", LL, "kgf/m²", 0),
            ("DL รวม", DL, "kgf/m²", 1),
            ("น้ำหนักบรรทุกประลัย Wu", Wu, "kgf/m²", 1),
            ("โมเมนต์ประลัย Mu = Wu·Lx²/8", Mu, "kgf-m", 0),
            ("เหล็กเสริมหลัก", f"{main_size} @ {S_main:.1f} cm"),
            ("เหล็กกันร้าว", f"{temp_size} @ {S_temp:.1f} cm"),
        ],
        checks=checks,
        figures=[("รูปด้านบันได (Side Elevation)", section_img)],
        status=passed,
        summary=("ระยะเรียงเหล็กหลักและเหล็กกันร้าวผ่านเกณฑ์ ACI 318M-08"
                 if passed else "มีรายการไม่ผ่าน — โปรดตรวจสอบตารางการตรวจสอบ"))


if __name__ == "__main__":
    render_stair_module()
