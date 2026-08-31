"""Streamlit UI — RC one-way slab design to ACI 318M-08. Thai UI, cm / cm².

Design of a 1 m wide strip. UI dimensions in cm (converted to mm for the
ACI core); steel areas reported in cm² per metre.
"""

import math

import streamlit as st

from utils.aci_318m import phi, rebars, bar_area
from utils.drawing import draw_slab_strip, draw_twoway_slab_plan
from utils.project import get_project_info
from reports.pdf_generator import (
    generate_slab_report,
    generate_twoway_slab_report,
    FONT_AVAILABLE,
    font_status_message,
)

STRIP_WIDTH = 1000.0     # mm
CM = 10.0                # cm -> mm
KSC_TO_MPA = 0.0980665   # ksc (kgf/cm^2) -> MPa (N/mm^2)
KGF_TO_KN = 9.80665 / 1000.0   # kgf/m^2 -> kN/m^2  (also kgf -> kN, kgf-m -> kN.m)
KN_TO_KGF = 1000.0 / 9.80665   # kN -> kgf  (also kN.m -> kgf-m)
CONC_DENSITY_KG = 2400.0       # kg/m^3
DB_DESIGN = 9.0                # mm, assumed bar dia for two-way design phase
TWOWAY_BAR_SIZES = ["DB10", "DB12"]

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


SLAB_TYPES = [
    "One-way Slab (พื้นทางเดียว)",
    "Two-way Slab (พื้นสองทาง)",
    "Cantilever Slab (พื้นยื่น)",
    "Slab on Ground (พื้นบนดิน)",
    "Slab on Piles (พื้นบนเสาเข็ม)",
    "3-Edge Slab (พื้นสามขอบ)",
]

UNDER_CONSTRUCTION = "กำลังอยู่ระหว่างการพัฒนา (Under Construction)"


def render_slab_module():
    slab_type = st.selectbox("เลือกประเภทพื้น (Slab Type)", SLAB_TYPES,
                             key="slab_type")
    if slab_type == "One-way Slab (พื้นทางเดียว)":
        _render_one_way_slab()
    elif slab_type == "Two-way Slab (พื้นสองทาง)":
        _render_two_way_slab()
    else:
        st.info(UNDER_CONSTRUCTION)


def _render_two_way_slab():
    st.title("การออกแบบพื้นสองทาง")
    st.caption("พื้นสองทางแบบช่วงเดี่ยว (simply supported) — โมเมนต์โดยประมาณ "
               "ด้วยวิธี Rankine-Grashoff ตามมาตรฐาน ACI 318M-08")

    b = STRIP_WIDTH   # 1 m per-metre strip

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        Lx = st.number_input("ช่วงสั้น Lx (m)", min_value=1.0, value=4.0,
                             step=0.001, format="%.3f", key="tw_Lx")
        t_cm = st.number_input("ความหนาพื้น t (cm)", min_value=8.0, value=12.0,
                               step=0.01, format="%.2f", key="tw_t")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d", key="tw_fc")
    with c2:
        Ly = st.number_input("ช่วงยาว Ly (m)", min_value=1.0, value=5.0,
                             step=0.001, format="%.3f", key="tw_Ly")
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.0,
                                      value=2.0, step=0.01, format="%.2f",
                                      key="tw_cov")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d", key="tw_fy")
    with c3:
        SDL = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม SDL (kgf/m²)",
                              min_value=0.0, value=150.0, step=10.0, key="tw_sdl")
        LL = st.number_input("น้ำหนักบรรทุกจร LL (kgf/m²)", min_value=0.0,
                             value=300.0, step=50.0, key="tw_ll")

    # cm -> mm, ksc -> MPa
    t = t_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA

    # ------------------------------------------------------------------
    # Aspect ratio m = Lx / Ly
    # ------------------------------------------------------------------
    if Ly < Lx:
        st.warning("Lx ควรเป็นช่วงที่สั้นกว่า Ly — โปรดตรวจสอบค่าช่วงพาด")
    m_ratio = Lx / Ly
    if m_ratio < 0.5:
        st.warning(
            f"อัตราส่วน m = Lx/Ly = {m_ratio:.3f} < 0.50 — พฤติกรรมใกล้เคียง"
            f"พื้นทางเดียว (One-way) สามารถคำนวณต่อได้ แต่แนะนำให้ออกแบบเป็น"
            f"พื้นทางเดียว"
        )

    # ------------------------------------------------------------------
    # Loads  (kg/m² -> kN/m²)
    # ------------------------------------------------------------------
    sw_kg = (t / 1000.0) * CONC_DENSITY_KG          # kg/m²
    DL_kg = sw_kg + SDL                             # kg/m²
    Wu_kg = 1.2 * DL_kg + 1.6 * LL                  # kg/m²
    Wu = Wu_kg * KGF_TO_KN                          # kN/m²

    # ------------------------------------------------------------------
    # Simplified moments — Rankine-Grashoff (simply supported)
    # ------------------------------------------------------------------
    denom = Lx ** 4 + Ly ** 4
    Mux = Wu * Lx ** 2 * (Ly ** 4 / denom) / 8.0    # kN·m/m (short span)
    Muy = Wu * Ly ** 2 * (Lx ** 4 / denom) / 8.0    # kN·m/m (long span)

    # ------------------------------------------------------------------
    # Effective depths (mm) — db = 9 mm assumed for the design phase
    # ------------------------------------------------------------------
    dx = t - covering - DB_DESIGN / 2.0
    dy = dx - DB_DESIGN
    if dy <= 0:
        st.error("ความลึกประสิทธิผล dy ≤ 0 — เพิ่มความหนาพื้น t")
        return

    # ------------------------------------------------------------------
    # Required steel per metre width (same flexure check as one-way)
    # ------------------------------------------------------------------
    As_x, Rn_x, rho_x, feas_x = _required_as_flexure(Mux, b, dx, fc, fy)
    As_y, Rn_y, rho_y, feas_y = _required_as_flexure(Muy, b, dy, fc, fy)
    temp_ratio = _temp_steel_ratio(fy)
    As_min = temp_ratio * b * t
    feasible = feas_x and feas_y

    # ------------------------------------------------------------------
    # Reinforcement selection (X = short span, Y = long span)
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม")
    r1, r2 = st.columns(2)
    with r1:
        size_x = st.selectbox("ขนาดเหล็ก ทิศทางสั้น (X)", TWOWAY_BAR_SIZES,
                              key="tw_size_x")
        sp_x_cm = st.number_input("ระยะเรียง ทิศทางสั้น (X) (cm)", min_value=5.0,
                                  max_value=45.0, value=15.0, step=1.0,
                                  format="%.1f", key="tw_sp_x")
    with r2:
        size_y = st.selectbox("ขนาดเหล็ก ทิศทางยาว (Y)", TWOWAY_BAR_SIZES,
                              key="tw_size_y")
        sp_y_cm = st.number_input("ระยะเรียง ทิศทางยาว (Y) (cm)", min_value=5.0,
                                  max_value=45.0, value=20.0, step=1.0,
                                  format="%.1f", key="tw_sp_y")

    area_x = bar_area(size_x)
    area_y = bar_area(size_y)
    sp_x = sp_x_cm * CM
    sp_y = sp_y_cm * CM
    As_prov_x = area_x * (b / sp_x)
    As_prov_y = area_y * (b / sp_y)

    max_sp = min(2.0 * t, 450.0)          # ACI 318M-08 13.3.2 (two-way)
    sp_x_ok = sp_x <= max_sp
    sp_y_ok = sp_y <= max_sp

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| อัตราส่วน m = Lx / Ly | {m_ratio:.3f} |
| น้ำหนักตัวเอง SW = t · 2400 | {sw_kg:,.1f} kgf/m² |
| น้ำหนักบรรทุกคงที่รวม DL = SW + SDL | {DL_kg:,.1f} kgf/m² |
| น้ำหนักบรรทุกประลัย Wu = 1.2·DL + 1.6·LL | {Wu_kg:,.1f} kgf/m² |
| โมเมนต์ทิศทางสั้น Mux = Wu·Lx²·Ly⁴/(Lx⁴+Ly⁴)/8 | **{Mux * KN_TO_KGF:,.0f} kgf-m/m** |
| โมเมนต์ทิศทางยาว Muy = Wu·Ly²·Lx⁴/(Lx⁴+Ly⁴)/8 | **{Muy * KN_TO_KGF:,.0f} kgf-m/m** |
| dₙ (สมมติสำหรับออกแบบ) | {DB_DESIGN:.1f} mm |
| ความลึกประสิทธิผล dx = t − covering − dₙ/2 | **{dx / CM:,.2f} cm** |
| ความลึกประสิทธิผล dy = dx − dₙ | **{dy / CM:,.2f} cm** |
"""
    )

    if not feasible:
        st.error("หน้าตัดบางเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว "
                 "(1 − 2·Rn/(0.85·f'c) < 0) — เพิ่มความหนา t หรือ f'c")

    ax_cell = f"{As_x / 100.0:,.2f}" if feas_x else "—"
    ay_cell = f"{As_y / 100.0:,.2f}" if feas_y else "—"
    st.markdown(
        f"""
| รายการ | ทิศทางสั้น (X) | ทิศทางยาว (Y) |
|---|---|---|
| Rn = Mu/(φ·b·d²) (ksc) | {Rn_x / KSC_TO_MPA:,.1f} | {Rn_y / KSC_TO_MPA:,.1f} |
| As ที่ต้องการ (การดัด) (cm²/m) | {ax_cell} | {ay_cell} |
| As,min (cm²/m) | {As_min / 100.0:,.2f} | {As_min / 100.0:,.2f} |
| เหล็กที่จัดให้ | {size_x} @ {sp_x_cm:.1f} cm | {size_y} @ {sp_y_cm:.1f} cm |
| As ที่จัดให้ (cm²/m) | **{As_prov_x / 100.0:,.2f}** | **{As_prov_y / 100.0:,.2f}** |
| ระยะเรียงสูงสุด min(2t, 450) (cm) | {max_sp / CM:,.1f} | {max_sp / CM:,.1f} |
"""
    )

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    x_req_ok = feas_x and As_prov_x >= As_x
    x_min_ok = As_prov_x >= As_min
    y_req_ok = feas_y and As_prov_y >= As_y
    y_min_ok = As_prov_y >= As_min
    passed = (x_req_ok and x_min_ok and y_req_ok and y_min_ok
              and sp_x_ok and sp_y_ok)

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    st.markdown(
        f"""
| การตรวจสอบ | ที่ต้องการ | ที่จัดให้ | สถานะ |
|---|---|---|---|
| As,x ≥ As,required | {ax_cell} cm²/m | {As_prov_x / 100.0:,.2f} cm²/m | {_s(x_req_ok)} |
| As,x ≥ As,min | {As_min / 100.0:,.2f} cm²/m | {As_prov_x / 100.0:,.2f} cm²/m | {_s(x_min_ok)} |
| As,y ≥ As,required | {ay_cell} cm²/m | {As_prov_y / 100.0:,.2f} cm²/m | {_s(y_req_ok)} |
| As,y ≥ As,min | {As_min / 100.0:,.2f} cm²/m | {As_prov_y / 100.0:,.2f} cm²/m | {_s(y_min_ok)} |
| ระยะเรียง X ≤ ขีดจำกัด | s = {sp_x_cm:.1f} cm | {max_sp / CM:,.1f} cm | {_s(sp_x_ok)} |
| ระยะเรียง Y ≤ ขีดจำกัด | s = {sp_y_cm:.1f} cm | {max_sp / CM:,.1f} cm | {_s(sp_y_ok)} |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing — plan view
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_twoway_slab_plan(Lx, Ly, t, covering,
                                            size_x, sp_x, size_y, sp_y)
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    if passed:
        st.success(f"{PASS_TXT} — ผ่านการตรวจสอบทั้งทิศทางสั้นและทิศทางยาว")

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_twoway_slab_report(
            {
                "Lx": Lx, "Ly": Ly, "t": t, "covering": covering,
                "SDL_kgm2": SDL, "LL_kgm2": LL, "fc": fc, "fy": fy,
                "project": get_project_info(),
            },
            {
                "m_ratio": m_ratio, "sw_kg": sw_kg, "DL_kg": DL_kg,
                "Wu_kg": Wu_kg, "Wu_kN": Wu, "db": DB_DESIGN,
                "Mux": Mux, "Muy": Muy, "dx": dx, "dy": dy,
                "As_x": As_x if feas_x else None,
                "As_y": As_y if feas_y else None,
                "As_min": As_min,
                "size_x": size_x, "sp_x_cm": sp_x_cm, "As_prov_x": As_prov_x,
                "size_y": size_y, "sp_y_cm": sp_y_cm, "As_prov_y": As_prov_y,
                "max_sp": max_sp,
                "x_req_ok": x_req_ok, "x_min_ok": x_min_ok,
                "y_req_ok": y_req_ok, "y_min_ok": y_min_ok,
                "sp_x_ok": sp_x_ok, "sp_y_ok": sp_y_ok,
                "section_img": section_img, "status": "PASS",
            },
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="twoway_slab_report.pdf",
            mime="application/pdf",
        )
    else:
        reasons = []
        if not x_req_ok:
            reasons.append("As,x < ที่ต้องการ")
        if not x_min_ok:
            reasons.append("As,x < As,min")
        if not y_req_ok:
            reasons.append("As,y < ที่ต้องการ")
        if not y_min_ok:
            reasons.append("As,y < As,min")
        if not sp_x_ok:
            reasons.append(f"ระยะเรียง X > {max_sp / CM:.1f} cm")
        if not sp_y_ok:
            reasons.append(f"ระยะเรียง Y > {max_sp / CM:.1f} cm")
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


def _render_one_way_slab():
    st.title("การออกแบบพื้นทางเดียว")
    st.caption("แถบออกแบบกว้าง 1 ม. — การดัด และเหล็กเสริมกันร้าว/อุณหภูมิ "
               "ตามมาตรฐาน ACI 318M-08 (หน่วยเมตริก)")

    b = STRIP_WIDTH          # mm (internal)
    b_cm = b / CM            # cm (display)

    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        Mu_kgfm = st.number_input("โมเมนต์ประลัย Mu (kgf-m/m)", min_value=0.0,
                                  value=2500.0, step=50.0)
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d")
    with c2:
        t_cm = st.number_input("ความหนาพื้น t (cm)", min_value=8.0,
                               value=20.0, step=0.01, format="%.2f")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d")
    with c3:
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.5,
                                      value=2.0, step=0.01, format="%.2f")
        st.number_input("ความกว้างแถบออกแบบ b (cm)", value=b_cm, disabled=True,
                        step=0.01, format="%.2f", help="กำหนดคงที่ที่แถบกว้าง 1 ม.")

    # MKS -> SI for the ACI calculation core
    t = t_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA
    Mu = Mu_kgfm * KGF_TO_KN                     # kgf-m/m -> kN.m/m

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
                                     value=15.0, step=1.0, format="%.1f")

    main_spacing = main_sp_cm * CM               # cm -> mm
    temp_spacing = temp_sp_cm * CM

    main_area = rebars[main_size]
    temp_area = rebars[temp_size]
    main_dia = float(main_size[2:])
    temp_dia = float(temp_size[2:])

    # ------------------------------------------------------------------
    # Effective depth (mm)
    # ------------------------------------------------------------------
    d = t - covering - main_dia / 2.0
    if d <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบระยะหุ้ม ความหนา "
                 "หรือขนาดเหล็กเสริม")
        return

    # ------------------------------------------------------------------
    # Required steel
    # ------------------------------------------------------------------
    As_req, Rn, rho, feasible = _required_as_flexure(Mu, b, d, fc, fy)
    temp_ratio = _temp_steel_ratio(fy)
    # Shrinkage/temperature steel; also the minimum flexural steel for
    # slabs of uniform thickness (ACI 318M-08 10.5.4).
    As_min = temp_ratio * b * t

    # ------------------------------------------------------------------
    # Provided steel  (bar area * bars per metre)
    # ------------------------------------------------------------------
    As_prov_main = main_area * (b / main_spacing)
    As_prov_temp = temp_area * (b / temp_spacing)

    # ------------------------------------------------------------------
    # Spacing limits (mm)
    # ------------------------------------------------------------------
    max_sp_main = min(3.0 * t, 450.0)
    max_sp_temp = min(5.0 * t, 450.0)
    sp_main_ok = main_spacing <= max_sp_main
    sp_temp_ok = temp_spacing <= max_sp_temp

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| ความกว้างแถบออกแบบ b | {b / CM:,.2f} cm |
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
            temp_label=f"เหล็กกันร้าว {temp_size} @ {temp_sp_cm:.0f} cm")
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    if not feasible:
        st.error("พื้นบางเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว "
                 "(1 − 2·Rn/(0.85·f'c) < 0) — เพิ่ม t หรือ f'c")
        st.markdown(
            f"เหล็กกันร้าว/อุณหภูมิ As,min = **{As_min / 100.0:,.2f} cm²/m**  ·  "
            f"As หลักที่จัดให้ = **{As_prov_main / 100.0:,.2f} cm²/m**"
        )
        st.error(f"{FAIL_TXT} — พื้นไม่เพียงพอสำหรับการดัด")
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
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    as_req_ok = As_prov_main >= As_req
    as_min_ok = As_prov_main >= As_min
    temp_min_ok = As_prov_temp >= As_min
    passed = as_req_ok and as_min_ok and temp_min_ok and sp_main_ok and sp_temp_ok

    reasons = []
    if not as_req_ok:
        reasons.append(
            f"As หลักที่จัดให้ {As_prov_main / 100.0:,.2f} < "
            f"ที่ต้องการ {As_req / 100.0:,.2f} cm²/m"
        )
    if not as_min_ok:
        reasons.append(
            f"As หลักที่จัดให้ {As_prov_main / 100.0:,.2f} < "
            f"As,min {As_min / 100.0:,.2f} cm²/m"
        )
    if not temp_min_ok:
        reasons.append(
            f"As กันร้าวที่จัดให้ {As_prov_temp / 100.0:,.2f} < "
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

    if passed:
        st.success(
            f"{PASS_TXT} — As หลักที่จัดให้ = {As_prov_main / 100.0:,.2f} cm²/m ≥ "
            f"ที่ต้องการที่ควบคุม {As_design / 100.0:,.2f} cm²/m; "
            f"ระยะเรียงอยู่ในเกณฑ์ทั้งหมด"
        )

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_slab_report(
            {
                "Mu": Mu, "t": t, "covering": covering,
                "fc": fc, "fy": fy, "b": b,
                "project": get_project_info(),
            },
            {
                "d": d, "As_req": As_req, "As_min": As_min,
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
            file_name="slab_design_report.pdf",
            mime="application/pdf",
        )
    else:
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


if __name__ == "__main__":
    render_slab_module()
