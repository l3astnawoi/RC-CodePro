"""Streamlit UI — RC one-way slab design to ACI 318M-08. Thai UI, cm / cm².

Design of a 1 m wide strip. UI dimensions in cm (converted to mm for the
ACI core); steel areas reported in cm² per metre.
"""

import math

import streamlit as st

from utils import ui
from utils.aci_318m import phi, rebars, bar_area
from utils.drawing import (draw_slab_strip, draw_twoway_slab_plan,
                           draw_slab_plan, fig_to_png_buf)
from utils.project import get_project_info, render_report_expander
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
    """Slab Design — RC CodePro visual language (same as Beam / Column).

    One-way / two-way classification is automatic from m = Lx/Ly; the page
    exposes only what the module actually computes (flexural steel, minimum
    shrinkage / temperature steel, bar-spacing checks).  Engineering logic
    is unchanged — presentation only.
    """
    ui.breadcrumb("Member Design", "Slab")
    ui.page_header("Slab Design",
                   "One-way / Two-way Slab — Flexure & Bar Spacing (ACI 318M-08)")

    st.markdown("#### SLAB TYPE")
    slab_type = st.selectbox("เลือกประเภทพื้น (Slab Type)", SLAB_TYPES,
                             key="slab_type")
    if slab_type in ("One-way Slab (พื้นทางเดียว)",
                     "Two-way Slab (พื้นสองทาง)"):
        _render_slab_design()
    else:
        st.info(UNDER_CONSTRUCTION)


def _as_flexure_ksc(Mu_kgfm, b_cm, d_cm, fc_ksc, fy_ksc):
    """Singly-reinforced tension-controlled As (cm2) for a strip ``b_cm``
    wide, all inputs in MKS (kgf-m, cm, ksc).  Returns (As_cm2, feasible)."""
    if d_cm <= 0.0 or Mu_kgfm <= 0.0:
        return 0.0, True
    Rn = (Mu_kgfm * 100.0) / (phi["flexure"] * b_cm * d_cm ** 2)   # ksc
    disc = 1.0 - 2.0 * Rn / (0.85 * fc_ksc)
    if disc < 0.0:
        return None, False
    rho = (0.85 * fc_ksc / fy_ksc) * (1.0 - math.sqrt(disc))
    return rho * b_cm * d_cm, True


def _spacing_for(As_bar_cm2, As_req_cm2, s_max_cm):
    """Bar spacing (cm, rounded down to 2.5 cm) that delivers ``As_req`` per
    metre with a bar of area ``As_bar``; capped at ``s_max``.
    Returns (S_cm, As_prov_cm2_per_m)."""
    if As_req_cm2 <= 1.0e-9:
        S = s_max_cm
    else:
        S_req = As_bar_cm2 * 100.0 / As_req_cm2
        S = min(math.floor(S_req / 2.5) * 2.5, s_max_cm)
        S = max(S, 2.5)
    return S, As_bar_cm2 * 100.0 / S


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


SLAB_BAR_SIZES = ["DB10", "DB12", "DB16", "DB20", "DB25"]


def _render_slab_design():
    st.caption("จำแนกประเภทพื้นจากอัตราส่วน m = Lx/Ly, คำนวณโมเมนต์ต่อแถบกว้าง "
               "1 เมตร, เหล็กเสริมหลัก และเหล็กกันร้าว/อุณหภูมิ ตามมาตรฐาน "
               "ACI 318M-08 — หน่วยเมตริก (cm, kgf, kgf-m, ksc, kgf/m²)")

    b = 100.0        # cm — a 1 m wide strip

    st.markdown("#### MEMBER INPUT")

    # ------------------------------------------------------------------
    # 1. Geometry  (widget keys / defaults unchanged)
    # ------------------------------------------------------------------
    with ui.section_card("GEOMETRY — ขนาดพื้น"):
        d1, d2, d3 = st.columns(3)
        with d1:
            Lx = st.number_input("ช่วงสั้น Lx (m)", min_value=0.5, value=4.0,
                                 step=0.05, format="%.2f", key="sd_Lx")
        with d2:
            Ly = st.number_input("ช่วงยาว Ly (m)", min_value=0.5, value=5.0,
                                 step=0.05, format="%.2f", key="sd_Ly")
        with d3:
            t_cm = st.number_input("ความหนาพื้น t (cm)", min_value=8.0,
                                   value=12.0, step=0.5, format="%.1f",
                                   key="sd_t")
    if Ly < Lx:
        Lx, Ly = Ly, Lx
        st.info("สลับค่าให้ Lx เป็นช่วงที่สั้นกว่าโดยอัตโนมัติ")

    # ------------------------------------------------------------------
    # 2. Material  (widget keys / defaults unchanged)
    # ------------------------------------------------------------------
    with ui.section_card("MATERIAL — วัสดุ"):
        s2, s3, s4 = st.columns(3)
        with s2:
            cov_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=1.0,
                                     value=2.0, step=0.5, format="%.1f",
                                     key="sd_cov")
        with s3:
            fc_ksc = st.number_input("f'c (ksc)", min_value=180, value=240,
                                     step=10, format="%d", key="sd_fc")
        with s4:
            fy_ksc = st.number_input("fy (ksc)", min_value=2400, value=4000,
                                     step=100, format="%d", key="sd_fy")

    # ------------------------------------------------------------------
    # 3. Loads  (self-weight auto from 2400 kg/m3)
    # ------------------------------------------------------------------
    with ui.section_card("LOADS — แรงกระทำ"):
        l1, l2 = st.columns(2)
        with l1:
            SDL = st.number_input("น้ำหนักบรรทุกคงที่เพิ่มเติม SDL (kgf/m²)",
                                  min_value=0.0, value=150.0, step=10.0,
                                  key="sd_sdl")
        with l2:
            LL = st.number_input("น้ำหนักบรรทุกจร LL (kgf/m²)", min_value=0.0,
                                 value=300.0, step=50.0, key="sd_ll")

    # ------------------------------------------------------------------
    # 4. Reinforcement
    # ------------------------------------------------------------------
    with ui.section_card("REINFORCEMENT — เหล็กเสริม"):
        r1, r2 = st.columns(2)
        with r1:
            main_size = st.selectbox("เหล็กเสริมหลัก — ขนาด", SLAB_BAR_SIZES,
                                     index=SLAB_BAR_SIZES.index("DB12"),
                                     key="sd_msz")
        with r2:
            temp_size = st.selectbox("เหล็กกันร้าว/อุณหภูมิ — ขนาด",
                                     SLAB_BAR_SIZES,
                                     index=SLAB_BAR_SIZES.index("DB10"),
                                     key="sd_tsz")

    # ---- MKS working values -----------------------------------------
    t, cov = float(t_cm), float(cov_cm)
    fc, fy = float(fc_ksc), float(fy_ksc)
    db_main = float(main_size[2:]) / 10.0      # cm
    db_temp = float(temp_size[2:]) / 10.0      # cm
    Ab_main = bar_area(main_size) / 100.0      # cm2 per bar
    Ab_temp = bar_area(temp_size) / 100.0

    # ---- Type classification :  m = Lx / Ly ------------------------
    m_ratio = Lx / Ly if Ly > 0 else 0.0
    two_way = m_ratio > 0.5
    type_txt = "พื้นสองทาง (Two-Way)" if two_way else "พื้นทางเดียว (One-Way)"

    # ---- Loads : self-weight + factored ---------------------------
    sw = (t / 100.0) * CONC_DENSITY_KG          # kgf/m2  (t in m x 2400)
    DL = sw + SDL
    Wu = 1.2 * DL + 1.6 * LL                    # kgf/m2  (= kgf/m on a 1 m strip)

    # ---- Design moments per 1 m strip (kgf-m) --------------------
    if two_way:
        k = Lx ** 4 + Ly ** 4
        Mux = Wu * Lx ** 2 * (Ly ** 4 / k) / 8.0      # short span
        Muy = Wu * Ly ** 2 * (Lx ** 4 / k) / 8.0      # long span
        Mu_main = max(Mux, Muy)
    else:
        Mux = Wu * Lx ** 2 / 8.0                      # simple-span strip
        Muy = 0.0
        Mu_main = Mux

    # ---- Effective depths (cm) --------------------------------------
    d_x = t - cov - db_main / 2.0                     # short / bottom layer
    d_y = d_x - db_main                               # long / upper layer
    if d_y <= 0.0:
        st.error("ความลึกประสิทธิผลไม่พอ — เพิ่มความหนาพื้น t หรือลดขนาดเหล็ก")
        return

    # ---- Temperature / shrinkage steel  (ACI 318M-08 7.12) --------
    temp_ratio = _temp_steel_ratio(fy * KSC_TO_MPA)
    As_temp_min = temp_ratio * b * t                  # cm2 / m

    # ---- Flexural steel per direction -----------------------------
    As_x_req, feas_x = _as_flexure_ksc(Mux, b, d_x, fc, fy)
    As_y_req, feas_y = _as_flexure_ksc(Muy, b, d_y, fc, fy)
    feasible = feas_x and (feas_y or not two_way)
    if not feasible:
        st.error("หน้าตัดบางเกินไปสำหรับการดัด — เพิ่มความหนาพื้น t หรือ f'c")
        return
    As_x = max(As_x_req or 0.0, As_temp_min)
    As_y = max(As_y_req or 0.0, As_temp_min) if two_way else As_temp_min
    As_main = As_x if (not two_way or As_x >= As_y) else As_y

    # ---- Tension-controlled / maximum-steel limit ------------------
    # ACI 318M-08 10.3.4 (rho_max at eps_t = 0.005); eps_t >= 0.004 is
    # mandatory for a flexural member per 10.3.5.  As_x / As_y above are
    # sized with a fixed phi = 0.90, valid ONLY while the section stays
    # tension-controlled (As <= As_max).
    As_max_x = _rho_max_ksc(fc, fy) * b * d_x
    As_max_y = _rho_max_ksc(fc, fy) * b * d_y
    ductile_x = As_x <= As_max_x
    ductile_y = (not two_way) or (As_y <= As_max_y)

    # ---- Spacing checks ------------------------------------------
    s_max_main = min(3.0 * t, 45.0)                   # ACI 13.3.2 / 10.5.4
    s_max_temp = min(5.0 * t, 45.0)                   # ACI 7.12.2.2
    S_x, Asp_x = _spacing_for(Ab_main, As_x, s_max_main)
    S_y, Asp_y = _spacing_for(Ab_main, As_y, s_max_main) if two_way else (None, None)
    S_temp, Asp_temp = _spacing_for(Ab_temp, As_temp_min, s_max_temp)

    S_main = S_x if (not two_way) else max(S_x, S_y)
    main_ok = (7.5 <= S_x <= s_max_main) and (
        (not two_way) or (7.5 <= S_y <= s_max_main))
    temp_ok = 7.5 <= S_temp <= s_max_temp
    ductile_ok = ductile_x and ductile_y

    passed = main_ok and temp_ok and ductile_ok

    # ==================================================================
    # DESIGN SUMMARY  (reads existing verdict + existing values only)
    # ==================================================================
    st.markdown("#### DESIGN SUMMARY")
    with st.container(border=True):
        ss1, ss2 = st.columns([1, 3])
        with ss1:
            st.markdown("**STATUS**")
            ui.status_badge("pass" if passed else "fail",
                            "PASS" if passed else "FAIL")
        with ss2:
            st.caption(type_txt + ("  (m > 0.5)" if two_way else "  (m ≤ 0.5)"))

        sk1, sk2, sk3, sk4 = st.columns(4)
        with sk1:
            ui.kpi("ประเภทพื้น", type_txt, sub=f"m = {m_ratio:.3f}")
        with sk2:
            ui.kpi("Wu (kgf/m²)", f"{Wu:,.1f}")
        with sk3:
            ui.kpi("Mu ควบคุม (kgf-m)", f"{Mu_main:,.0f}")
        with sk4:
            ui.kpi("As หลัก (cm²/m)", f"{As_main:,.2f}")

        sb1, sb2 = st.columns(2)
        with sb1:
            st.caption(f"ระยะเรียงเหล็กหลัก — {main_size}  "
                       f"(S {S_main:,.1f} / s_max {s_max_main:,.1f} cm)")
            ui.status_badge(bool(main_ok))
        with sb2:
            st.caption(f"ระยะเรียงเหล็กกันร้าว — {temp_size}  "
                       f"(S {S_temp:,.1f} / s_max {s_max_temp:,.1f} cm)")
            ui.status_badge(bool(temp_ok))

    # ==================================================================
    # DESIGN CHECKS  (existing check tuples — one source, rendered here
    # and passed unchanged to the PDF report)
    # ==================================================================
    st.markdown("#### DESIGN CHECKS — ผลการตรวจสอบ")
    _sp_txt = (f"สั้น {S_x:.1f} / ยาว {S_y:.1f} cm" if two_way
               else f"{S_x:.1f} cm")
    _asmax_txt = (f"สั้น {As_x:.2f} / ยาว {As_y:.2f}" if two_way
                  else f"{As_x:.2f}")
    _asmax_cap = (f"สั้น {As_max_x:.2f} / ยาว {As_max_y:.2f} cm²/m" if two_way
                  else f"{As_max_x:.2f} cm²/m")
    checks = [
        ("ระยะเรียงเหล็กหลัก (S ≤ min(3t,45))", _sp_txt,
         f"{s_max_main:.1f} cm", main_ok),
        ("ระยะเรียงเหล็กกันร้าว (S ≤ min(5t,45))", f"{S_temp:.1f} cm",
         f"{s_max_temp:.1f} cm", temp_ok),
        ("เหล็กหลัก ≤ As,max (tension-controlled, ACI 10.3.4)",
         f"{_asmax_txt} cm²/m", _asmax_cap, ductile_ok),
        ("เหล็กกันร้าว/อุณหภูมิขั้นต่ำ As,temp",
         f"{As_temp_min:,.2f} cm²/m", "ρ·b·t", True),
    ]
    ui.engineering_table(
        ["รายการตรวจสอบ", "Demand", "Capacity", "สถานะ"],
        [[name, dem, cap, "ผ่าน (PASS)" if ok else "ไม่ผ่าน (FAIL)"]
         for name, dem, cap, ok in checks],
        right_from=1,
    )
    if not main_ok:
        st.warning("ระยะเรียงชิด/ห่างเกินเกณฑ์ — ปรับขนาดเหล็ก หรือความหนา")
    if not ductile_ok:
        st.warning("เหล็กหลัก > As,max — หน้าตัดบางเกินไป/รับโมเมนต์มากเกินไป "
                   "(ไม่เป็น tension-controlled ตาม ACI 318M-08 10.3.4/10.3.5) "
                   "— เพิ่มความหนาพื้น t")

    # ---- overall verdict (existing logic, existing text) -------------
    if passed:
        st.success(f"{PASS_TXT} — {type_txt}: ระยะเรียงเหล็กหลักและเหล็กกันร้าว"
                   f"ผ่านเกณฑ์ ACI 318M-08")
    else:
        fails = []
        if not main_ok:
            fails.append(f"ระยะเรียงเหล็กหลัก S = {S_main:,.1f} cm "
                         f"(เกณฑ์ 7.5–{s_max_main:,.1f} cm)")
        if not temp_ok:
            fails.append(f"ระยะเรียงเหล็กกันร้าว S = {S_temp:,.1f} cm "
                         f"(เกณฑ์ 7.5–{s_max_temp:,.1f} cm)")
        if not ductile_ok:
            _amx = As_x if not ductile_x else As_y
            _amax = As_max_x if not ductile_x else As_max_y
            fails.append(f"เหล็กหลัก As = {_amx:,.2f} > As,max = {_amax:,.2f} "
                         f"cm²/m — ไม่เป็น tension-controlled (ACI 10.3.4/10.3.5)")
        st.error(f"{FAIL_TXT} — " + "; ".join(fails))

    # ---- step-by-step derivation (existing table, collapsed) --------
    with st.expander("รายละเอียดการคำนวณทีละขั้น (Detailed calculation)",
                     expanded=False):
        _mrow = (f"| โมเมนต์ Mu (ทางสั้น / ทางยาว) | {Mux:,.0f} / {Muy:,.0f} kgf-m |"
                 if two_way else
                 f"| โมเมนต์ Mu = Wu·Lx²/8 (ต่อแถบ 1 ม.) | **{Mux:,.0f} kgf-m** |")
        st.markdown(
            f"""
| รายการ | ค่า |
|---|---|
| อัตราส่วน m = Lx / Ly = {Lx:.2f} / {Ly:.2f} | **{m_ratio:.3f}** → {type_txt} |
| น้ำหนักพื้นเอง sw = (t/100)·2400 | {sw:,.1f} kgf/m² |
| น้ำหนักบรรทุกประลัย Wu = 1.2(sw+SDL) + 1.6·LL | **{Wu:,.1f} kgf/m²** |
{_mrow}
| ความลึกประสิทธิผล d (ทางสั้น / ทางยาว) | {d_x:,.2f} / {d_y:,.2f} cm |
| เหล็กกันร้าว/อุณหภูมิ As,temp = {temp_ratio:.4f}·b·t | **{As_temp_min:,.2f} cm²/ม.** |
| As เหล็กหลักที่ต้องการ (ควบคุมด้วย As,temp) | ทางสั้น {As_x:,.2f} · ทางยาว {As_y:,.2f} cm²/ม. |
| ระยะเรียงสูงสุด — เหล็กหลัก min(3t, 45) | {s_max_main:,.1f} cm |
| ระยะเรียงสูงสุด — เหล็กกันร้าว min(5t, 45) | {s_max_temp:,.1f} cm |
| ระยะเรียงที่จัดให้ — เหล็กหลัก ({main_size}) | ทางสั้น {S_x:,.1f} cm{f' · ทางยาว {S_y:,.1f} cm' if two_way else ''} |
| ระยะเรียงที่จัดให้ — เหล็กกันร้าว ({temp_size}) | {S_temp:,.1f} cm |
"""
        )

    # ==================================================================
    # DRAWING / DETAIL  (drawing engine + geometry unchanged)
    # ==================================================================
    st.markdown("#### DRAWING / DETAIL — แปลนพื้น")
    try:
        if two_way:
            main_lbl = (f"Main-สั้น: {main_size} @ {S_x:.0f} cm  ·  "
                        f"Main-ยาว: {main_size} @ {S_y:.0f} cm")
            temp_lbl = f"Main (ยาว): {main_size} @ {S_y:.0f} cm"
            grid_temp_sp = S_y
        else:
            main_lbl = f"Main: {main_size} @ {S_x:.0f} cm"
            temp_lbl = f"Temp: {temp_size} @ {S_temp:.0f} cm"
            grid_temp_sp = S_temp
        fig = draw_slab_plan(
            Lx, Ly, main_label=main_lbl, main_sp_cm=S_x,
            temp_label=temp_lbl, temp_sp_cm=grid_temp_sp, two_way=two_way)
        st.pyplot(fig, use_container_width=True)
        st.caption("แปลนพื้น + ตะแกรงเหล็กล่าง (Slab Plan — Bottom Reinforcement)")
        section_img = fig_to_png_buf(fig)
    except Exception as exc:  # pragma: no cover
        section_img = None
        st.warning(f"ไม่สามารถสร้างภาพแปลนได้: {exc}")

    # ==================================================================
    # OUTPUT / REPORT  (report engine unchanged)
    # ==================================================================
    st.markdown("#### OUTPUT / REPORT — รายงานการคำนวณ")
    render_report_expander(
        key="slab_design", filename="slab_design_report.pdf",
        title="การออกแบบพื้นคอนกรีตเสริมเหล็ก (ACI 318M-08)",
        params=[
            ("ประเภทพื้น", type_txt), ("m = Lx/Ly", f"{m_ratio:.3f}"),
            ("ช่วงสั้น Lx", Lx, "m", 2), ("ช่วงยาว Ly", Ly, "m", 2),
            ("ความหนาพื้น t", t, "cm", 1), ("ระยะหุ้มคอนกรีต", cov, "cm", 1),
            ("f'c", fc, "ksc", 0), ("fy", fy, "ksc", 0),
            ("น้ำหนักพื้นเอง sw", sw, "kgf/m²", 1),
            ("SDL", SDL, "kgf/m²", 0), ("LL", LL, "kgf/m²", 0),
            ("น้ำหนักบรรทุกประลัย Wu", Wu, "kgf/m²", 1),
            ("โมเมนต์ Mu (สั้น/ยาว)",
             f"{Mux:,.0f}" + (f" / {Muy:,.0f}" if two_way else "") + " kgf-m"),
            ("เหล็กเสริมหลัก", f"{main_size} @ {_sp_txt}"),
            ("เหล็กกันร้าว/อุณหภูมิ", f"{temp_size} @ {S_temp:.1f} cm"),
        ],
        checks=checks,
        figures=[("แปลนพื้น + ตะแกรงเหล็กล่าง (Slab Plan)", section_img)],
        status=passed,
        summary=(f"{type_txt}: ระยะเรียงเหล็กหลักและเหล็กกันร้าวผ่านเกณฑ์"
                 if passed else "มีรายการไม่ผ่าน — โปรดตรวจสอบตารางการตรวจสอบ"))


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
