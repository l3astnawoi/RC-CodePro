"""Streamlit UI — Footing design (ACI 318M-08). Thai UI, tabbed interface.

Tabs
----
1. ฐานรากแผ่          — shallow foundations (Isolated Footing implemented;
                        Wall / 2C / Combined / Strap: under construction)
2. ฐานเสาเข็ม          — pile caps (F2 and F4 implemented; F1 / F3 / F5-F9:
                        under construction)
3. ฐานเสาเข็มเยื้องศูนย์ — eccentric pile caps (under construction)

UI units (all tabs use the same boundary conversions):
    axial loads      -> kgf           (x 9.80665/1000 -> kN)
    section sizes    -> cm            (x 10       -> mm)
    strengths f'c/fy -> ksc           (x 0.0980665 -> MPa)
    soil bearing q_a -> ตัน/ตารางเมตร (x 9.80665 -> kN/m2)
The ACI calculation core works in mm / kN / N / N·mm / MPa; results are
converted back to MKS (kgf, kgf-m, cm, cm²) for display and reports.
"""

import math

import streamlit as st

from utils.aci_318m import phi, rebars
from utils.drawing import draw_footing_plan, draw_pile_cap_plan
from utils.project import get_project_info
from reports.pdf_generator import (
    generate_footing_report,
    generate_pile_cap_report,
    FONT_AVAILABLE,
    font_status_message,
)

LAMBDA = 1.0             # normal-weight concrete
ALPHA_S = 40.0           # interior column (ACI 318M-08 11.11.2.1)
CM = 10.0               # cm -> mm
TON_TO_KN = 9.80665     # metric ton -> kN
KGF_TO_KN = 9.80665 / 1000.0     # kgf -> kN
KN_TO_KGF = 1000.0 / 9.80665     # kN -> kgf  (also kN.m -> kgf-m)
KSC_TO_MPA = 0.0980665  # ksc (kgf/cm^2) -> MPa (N/mm^2)
CONC_UW_KGF = 2400.0    # concrete unit weight — EXACT MKS value (kgf/m^3).
                        # Self-weight is computed with this literal 2400 so
                        # manual checks reproduce the printed formula exactly;
                        # it is NOT 24 kN/m^3 round-tripped through 9.80665.

PASS_TXT = "✅ ผ่านมาตรฐาน (PASS)"
FAIL_TXT = "❌ ไม่ผ่าน (FAIL)"

UNDER_CONSTRUCTION = "กำลังอยู่ระหว่างการพัฒนา (Under Construction)"


def _temp_steel_ratio(fy):
    """Shrinkage & temperature reinforcement ratio (ACI 318M-08 7.12.2.1)."""
    if fy <= 350.0:
        return 0.0020
    if fy <= 420.0:
        return 0.0018
    return max(0.0018 * 420.0 / fy, 0.0014)


def _flexure_as(Mu_Nmm, b_mm, d_mm, fc, fy):
    """Singly-reinforced, tension-controlled required As (mm2) for a strip of
    width ``b_mm`` and effective depth ``d_mm``.

    Returns ``(As_req_mm2, Rn_MPa, rho, feasible)``; ``As_req`` is ``inf`` and
    ``feasible`` is ``False`` when the section is too shallow.
    """
    if d_mm <= 0.0 or b_mm <= 0.0:
        return float("inf"), 0.0, None, False
    phi_f = phi["flexure"]
    Rn = Mu_Nmm / (phi_f * b_mm * d_mm ** 2)              # MPa
    disc = 1.0 - 2.0 * Rn / (0.85 * fc)
    if disc < 0.0:
        return float("inf"), Rn, None, False
    rho = (0.85 * fc / fy) * (1.0 - math.sqrt(disc))
    return rho * b_mm * d_mm, Rn, rho, True


# ===========================================================================
# Entry point — tabbed interface
# ===========================================================================


def render_footing_module():
    st.title("การออกแบบฐานราก")
    st.caption("ฐานรากแผ่ · ฐานเสาเข็ม · ฐานเสาเข็มเยื้องศูนย์ — ตามมาตรฐาน "
               "ACI 318M-08 (หน่วยเมตริก)")

    tabs = st.tabs(["ฐานรากแผ่", "ฐานเสาเข็ม", "ฐานเสาเข็มเยื้องศูนย์"])

    with tabs[0]:
        _tab_shallow()
    with tabs[1]:
        _tab_pile()
    with tabs[2]:
        _tab_eccentric()


# ===========================================================================
# Tab 1 — ฐานรากแผ่ (shallow foundations)
# ===========================================================================


def _tab_shallow():
    ftype = st.selectbox(
        "ประเภทฐานราก",
        [
            "Isolated Footing (ฐานรากเดี่ยว)",
            "Wall Footing (ฐานผนัง)",
            "2C Footing (ฐานเสา 2 ต้น)",
            "Combined Footing (ฐานรากร่วม)",
            "Strap Footing (ฐานคานเชื่อม)",
        ],
        key="shallow_type",
    )

    if ftype == "Isolated Footing (ฐานรากเดี่ยว)":
        _render_isolated_footing()
    else:
        st.info(UNDER_CONSTRUCTION)


def _render_isolated_footing():
    # ------------------------------------------------------------------
    # Inputs
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        P_DL_kgf = st.number_input("น้ำหนักบรรทุกคงที่จากเสา P_DL (kgf)",
                                   min_value=0.0, value=70000.0, step=100.0)
        B_m = st.number_input("ความกว้างฐานราก B (m)", min_value=0.5,
                              value=2.20, step=0.05, format="%.2f")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d")
    with c2:
        P_LL_kgf = st.number_input("น้ำหนักบรรทุกจรจากเสา P_LL (kgf)",
                                   min_value=0.0, value=25000.0, step=100.0)
        L_m = st.number_input("ความยาวฐานราก L (m)", min_value=0.5,
                              value=2.20, step=0.05, format="%.2f")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d")
    with c3:
        q_a_ton = st.number_input("กำลังแบกทานดินที่ยอมให้ qa (ตัน/ตารางเมตร)",
                                  min_value=5.0, value=25.0, step=1.0,
                                  format="%.2f")
        h_cm = st.number_input("ความหนาฐานราก h (cm)", min_value=25.0,
                               value=55.0, step=1.0, format="%.1f")
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=4.0,
                                      value=7.5, step=0.5, format="%.1f")

    # ------------------------------------------------------------------
    # Column shape — rectangular (cx x cy) or circular (Dc); a circular
    # column is designed as an equivalent square, ACI 318M-08 15.3:
    #   c_eq = Dc * sqrt(pi)/2   (same cross-sectional area)
    # ------------------------------------------------------------------
    st.markdown("**รูปร่างเสา (Column Shape)**")
    col_shape = st.radio("รูปร่างเสา",
                         ["Rectangular (สี่เหลี่ยม)", "Circular (กลม)"],
                         horizontal=True, label_visibility="collapsed")
    is_circular = col_shape.startswith("Circular")
    sc1, sc2 = st.columns(2)
    if is_circular:
        with sc1:
            Dc_cm = st.number_input("เส้นผ่านศูนย์กลางเสา Dc (cm)",
                                    min_value=15.0, value=40.0, step=1.0,
                                    format="%.1f")
        c_eq_cm = Dc_cm * (math.sqrt(math.pi) / 2.0)
        cx_cm = cy_cm = c_eq_cm
        with sc2:
            st.caption(f"เทียบเท่าสี่เหลี่ยมจัตุรัส c_eq = Dc·√π/2 = "
                       f"{c_eq_cm:,.2f} cm")
    else:
        Dc_cm = None
        with sc1:
            cx_cm = st.number_input("ความกว้างเสา cx (cm)", min_value=15.0,
                                    value=40.0, step=1.0, format="%.1f")
        with sc2:
            cy_cm = st.number_input("ความยาวเสา cy (cm)", min_value=15.0,
                                    value=40.0, step=1.0, format="%.1f")

    # Unit conversions -> ACI calculation core (mm, MPa, kN, kN/m2)
    P_DL = P_DL_kgf * KGF_TO_KN                        # kN
    P_LL = P_LL_kgf * KGF_TO_KN                        # kN
    B = B_m * 1000.0
    L = L_m * 1000.0
    h = h_cm * CM
    cx = cx_cm * CM                                    # column dim // X (mm)
    cy = cy_cm * CM                                    # column dim // Y (mm)
    Dc = (Dc_cm * CM) if Dc_cm is not None else None
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA
    q_a_kPa = q_a_ton * TON_TO_KN                      # kN/m²

    # ------------------------------------------------------------------
    # Reinforcement — separate mats for the long and the short direction.
    # The long-direction bars carry the larger moment and sit in the bottom
    # layer; the short-direction bars rest on top of them.
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม (แยกทิศทาง)")
    _bar_opts = list(rebars.keys())
    rl1, rl2 = st.columns(2)
    with rl1:
        size_long = st.selectbox("เหล็กด้านยาว — ขนาด (Long Direction)",
                                 _bar_opts, index=_bar_opts.index("DB16"),
                                 key="if_size_long")
    with rl2:
        qty_long = int(st.number_input("เหล็กด้านยาว — จำนวนเส้น",
                                       min_value=2, value=12, step=1,
                                       key="if_qty_long"))
    rs1, rs2 = st.columns(2)
    with rs1:
        size_short = st.selectbox("เหล็กด้านสั้น — ขนาด (Short Direction)",
                                  _bar_opts, index=_bar_opts.index("DB16"),
                                  key="if_size_short")
    with rs2:
        qty_short = int(st.number_input("เหล็กด้านสั้น — จำนวนเส้น",
                                        min_value=2, value=12, step=1,
                                        key="if_qty_short"))

    area_long = rebars[size_long]
    area_short = rebars[size_short]
    db_long = float(size_long[2:])
    db_short = float(size_short[2:])

    # ------------------------------------------------------------------
    # Geometry guards
    # ------------------------------------------------------------------
    if B <= cx or L <= cy:
        st.error("ขนาดฐานราก B และ L ต้องมากกว่าขนาดเสา (cx, cy)")
        return

    d_long = h - covering - db_long           # bottom layer (long-dir bars)
    d_short = d_long - db_long                # short-dir bars sit on top
    d_avg = 0.5 * (d_long + d_short)          # for punching (two-way)
    if d_short <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบความหนา ระยะหุ้ม "
                 "หรือขนาดเหล็กเสริม")
        return

    # ------------------------------------------------------------------
    # 1. Loads — self-weight, factored total, net factored pressure
    # ------------------------------------------------------------------
    area_m2 = B_m * L_m

    # --- Exact MKS load quantities (what the report / UI must print) ---------
    Wf_kgf = area_m2 * (h_cm / 100.0) * CONC_UW_KGF    # kgf — B·L·h·2400 exactly
    Total_DL_kgf = P_DL_kgf + Wf_kgf                   # kgf
    Pu_kgf = 1.2 * Total_DL_kgf + 1.6 * P_LL_kgf       # kgf
    q_service_kgf = (P_DL_kgf + P_LL_kgf + Wf_kgf) / area_m2   # kgf/m²
    qu_net_kgf = (1.2 * P_DL_kgf + 1.6 * P_LL_kgf) / area_m2   # kgf/m² (self-wt cancels)

    # --- SI mirror for the ACI 318M-08 calculation core only ---------------
    Wf = Wf_kgf * KGF_TO_KN                            # kN
    Total_DL = Total_DL_kgf * KGF_TO_KN                # kN
    Pu = Pu_kgf * KGF_TO_KN                            # kN — total factored (soil/piles)
    qu_net_kPa = qu_net_kgf * KGF_TO_KN                # kN/m² — net (self-wt cancels)

    # Service soil-bearing check (self-weight included on the demand side)
    q_service_kPa = q_service_kgf * KGF_TO_KN          # kN/m²
    bearing_ok = q_service_kPa <= q_a_kPa

    # Net factored pressure in N/mm^2 for the internal-force maths
    qu = qu_net_kPa * 1.0e-3                           # N/mm^2 (= MPa)

    long_dim = max(B, L)                               # mm — governing cantilever
    short_dim = min(B, L)                              # mm — resisting strip width

    # column dimension parallel to each footing direction
    if B >= L:                                         # long_dim = B (X)
        c_long, c_short = cx, cy
    else:                                              # long_dim = L (Y)
        c_long, c_short = cy, cx

    # ------------------------------------------------------------------
    # Prominent display of the computed loads
    # ------------------------------------------------------------------
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric("น้ำหนักฐานรากเอง Wf", f"{Wf_kgf:,.0f} kgf")
    with mc2:
        st.metric("แรงประลัยรวม Pu (รวม Wf)", f"{Pu_kgf:,.0f} kgf")
    with mc3:
        st.metric("หน่วยแรงประลัยสุทธิ qu,net", f"{qu_net_kgf:,.0f} kgf/m²")
    st.info(
        f"Wf = B·L·h·2400 = {B_m:.2f}·{L_m:.2f}·{h_cm / 100.0:.3f}·2400 = "
        f"{Wf_kgf:,.1f} kgf  |  "
        f"Total DL = P_DL + Wf = {Total_DL_kgf:,.1f} kgf  |  "
        f"Pu = 1.2·Total DL + 1.6·P_LL = {Pu_kgf:,.1f} kgf  |  "
        f"qu,net = (1.2·P_DL + 1.6·P_LL)/(B·L) = "
        f"{qu_net_kgf:,.1f} kgf/m²"
    )

    # ------------------------------------------------------------------
    # 2. Two-way (punching) shear — critical section d/2 from column face
    #    (uses the average effective depth of the two bar layers)
    # ------------------------------------------------------------------
    bo = 2.0 * (cx + d_avg) + 2.0 * (cy + d_avg)       # mm — critical perimeter
    punch_area = max(B * L - (cx + d_avg) * (cy + d_avg), 0.0)  # mm² outside
    Vup = qu * punch_area                              # N
    beta_c = max(cx, cy) / min(cx, cy)                 # column long/short ratio
    vc1 = 0.17 * (1.0 + 2.0 / beta_c) * LAMBDA * math.sqrt(fc)
    vc2 = 0.083 * (ALPHA_S * d_avg / bo + 2.0) * LAMBDA * math.sqrt(fc)
    vc3 = 0.33 * LAMBDA * math.sqrt(fc)
    vc_punch = min(vc1, vc2, vc3)                      # MPa
    Vc_punch = vc_punch * bo * d_avg                   # N
    phiVc_punch = phi["shear"] * Vc_punch             # N
    punch_ok = Vup <= phiVc_punch

    # ------------------------------------------------------------------
    # 3. One-way (beam) shear — checked in BOTH directions, section d
    #    from the column face.
    # ------------------------------------------------------------------
    #  long-direction bars span `long_dim`, spread over width `short_dim`
    av_long = max((long_dim - c_long) / 2.0 - d_long, 0.0)
    Vu_long = qu * short_dim * av_long                            # N
    Vc_v_long = 0.17 * LAMBDA * math.sqrt(fc) * short_dim * d_long
    phiVc_v_long = phi["shear"] * Vc_v_long                       # N
    beam_long_ok = Vu_long <= phiVc_v_long

    av_short = max((short_dim - c_short) / 2.0 - d_short, 0.0)
    Vu_short = qu * long_dim * av_short                           # N
    Vc_v_short = 0.17 * LAMBDA * math.sqrt(fc) * long_dim * d_short
    phiVc_v_short = phi["shear"] * Vc_v_short                     # N
    beam_short_ok = Vu_short <= phiVc_v_short

    # ------------------------------------------------------------------
    # 4. Flexure — moment at the column face, computed independently for
    #    each direction (ACI 318M-08 15.4).
    # ------------------------------------------------------------------
    Lc_long = (long_dim - c_long) / 2.0                # mm cantilever (long dir)
    Lc_short = (short_dim - c_short) / 2.0             # mm cantilever (short dir)
    Mu_long = qu * short_dim * Lc_long ** 2 / 2.0      # N·mm over width short_dim
    Mu_short = qu * long_dim * Lc_short ** 2 / 2.0     # N·mm over width long_dim

    As_req_long, Rn_long, rho_long, feas_long = _flexure_as(
        Mu_long, short_dim, d_long, fc, fy)
    As_req_short, Rn_short, rho_short, feas_short = _flexure_as(
        Mu_short, long_dim, d_short, fc, fy)

    # ------------------------------------------------------------------
    # 5. Minimum steel + provided steel, per direction
    # ------------------------------------------------------------------
    temp_ratio = _temp_steel_ratio(fy)
    As_min_long = temp_ratio * short_dim * h           # mm² over width short_dim
    As_min_short = temp_ratio * long_dim * h           # mm² over width long_dim

    # provided As directly from the bar count; actual spacing back-computed
    #   long-dir bars are distributed across the SHORT footing dimension
    #   short-dir bars are distributed across the LONG footing dimension
    n_long, n_short = qty_long, qty_short
    As_prov_long = n_long * area_long
    As_prov_short = n_short * area_short
    s_long = ((short_dim - 2.0 * covering) / (n_long - 1)
              if n_long > 1 else short_dim - 2.0 * covering)     # mm
    s_short = ((long_dim - 2.0 * covering) / (n_short - 1)
               if n_short > 1 else long_dim - 2.0 * covering)    # mm
    s_max = min(3.0 * h, 450.0)                                  # ACI max spacing
    sp_long_ok = s_long <= s_max
    sp_short_ok = s_short <= s_max

    As_des_long = (max(As_req_long, As_min_long) if feas_long
                   else float("inf"))
    As_des_short = (max(As_req_short, As_min_short) if feas_short
                    else float("inf"))

    flex_long_ok = feas_long and As_prov_long >= As_req_long
    flex_short_ok = feas_short and As_prov_short >= As_req_short
    asmin_long_ok = As_prov_long >= As_min_long
    asmin_short_ok = As_prov_short >= As_min_short
    feasible = feas_long and feas_short

    passed = (bearing_ok and beam_long_ok and beam_short_ok and punch_ok
              and flex_long_ok and flex_short_ok
              and asmin_long_ok and asmin_short_ok
              and sp_long_ok and sp_short_ok)

    def _s0(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| น้ำหนักบรรทุกคงที่จากเสา P_DL | {P_DL_kgf:,.0f} kgf |
| น้ำหนักบรรทุกจรจากเสา P_LL | {P_LL_kgf:,.0f} kgf |
| น้ำหนักฐานรากเอง Wf = B·L·h·2400 | **{Wf_kgf:,.1f} kgf** |
| น้ำหนักบรรทุกคงที่รวม Total DL = P_DL + Wf | {Total_DL_kgf:,.1f} kgf |
| แรงประลัยรวม Pu = 1.2·Total DL + 1.6·P_LL | **{Pu_kgf:,.1f} kgf** |
| ความลึกประสิทธิผล ด้านยาว d_long = h − covering − db_long | **{d_long / CM:,.2f} cm** |
| ความลึกประสิทธิผล ด้านสั้น d_short = d_long − db_long | **{d_short / CM:,.2f} cm** |
| หน้าตัดเสา | {("กลม Ø" + format(Dc / CM, ",.1f") + " cm → c_eq = " + format(cx / CM, ",.2f") + " cm (ACI 15.3)") if is_circular else ("สี่เหลี่ยม " + format(cx / CM, ",.1f") + " × " + format(cy / CM, ",.1f") + " cm")} |
| พื้นที่ฐานรากในแปลน B·L | {area_m2:,.3f} m² |
| หน่วยแรงดินที่เกิดขึ้น (ใช้งาน) q = (P_DL+P_LL+Wf)/(B·L) | **{q_service_kgf:,.1f} kgf/m²** |
| หน่วยแรงดินที่ยอมให้ qa | {q_a_ton * 1000.0:,.0f} kgf/m² ({q_a_ton:,.2f} ตัน/ตร.ม.) |
| หน่วยแรงประลัยสุทธิ qu,net = (1.2·P_DL+1.6·P_LL)/(B·L) | **{qu_net_kgf:,.1f} kgf/m²** |
"""
    )

    st.markdown("**แรงเฉือนทะลุ (สองทาง)** — หน้าตัดวิกฤตที่ระยะ d/2 จากผิวเสา "
                "(ใช้ qu,net)")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| เส้นรอบรูปวิกฤต b₀ = 2(cx+d) + 2(cy+d) | {bo:,.0f} mm |
| Vu,punch = qu,net·(B·L − (cx+d)(cy+d)) | {Vup / 1000.0 * KN_TO_KGF:,.0f} kgf |
| β_c = ด้านยาว/ด้านสั้น ของเสา | {beta_c:,.2f} |
| vc = min(0.17(1+2/β_c), 0.083(α_s·d/b₀+2), 0.33)·√f'c | {vc_punch / KSC_TO_MPA:,.1f} ksc |
| φVc = 0.75·vc·b₀·d (d = d_avg) | **{phiVc_punch / 1000.0 * KN_TO_KGF:,.0f} kgf** |
"""
    )

    st.markdown("**แรงเฉือนคาน (ทางเดียว)** — ตรวจสอบทั้งสองทิศทาง ที่ระยะ d "
                "จากผิวเสา (ใช้ qu,net)")
    st.markdown(
        f"""
| รายการ | ด้านยาว (Long) | ด้านสั้น (Short) |
|---|---|---|
| ระยะยื่นเลยหน้าตัด av = (ด้าน − c_เสา)/2 − d | {av_long / CM:,.2f} cm | {av_short / CM:,.2f} cm |
| Vu,beam = qu,net·(กว้างต้าน)·av | {Vu_long / 1000.0 * KN_TO_KGF:,.0f} kgf | {Vu_short / 1000.0 * KN_TO_KGF:,.0f} kgf |
| φVc = 0.75·0.17·√f'c·(กว้างต้าน)·d | {phiVc_v_long / 1000.0 * KN_TO_KGF:,.0f} kgf | {phiVc_v_short / 1000.0 * KN_TO_KGF:,.0f} kgf |
| สถานะ | {_s0(beam_long_ok)} | {_s0(beam_short_ok)} |
"""
    )

    st.markdown("**การดัด (ACI 15.4)** — โมเมนต์ที่ผิวเสา แยกสองทิศทาง (ใช้ qu,net)")
    st.markdown(
        f"""
| รายการ | ด้านยาว (Long) | ด้านสั้น (Short) |
|---|---|---|
| ความยาวยื่น Lc = (ด้าน − c_เสา)/2 | {Lc_long / CM:,.2f} cm | {Lc_short / CM:,.2f} cm |
| Mu = qu,net·(กว้างต้าน)·Lc²/2 | {Mu_long / 1.0e6 * KN_TO_KGF:,.0f} kgf-m | {Mu_short / 1.0e6 * KN_TO_KGF:,.0f} kgf-m |
| Rn = Mu / (φ·b·d²) | {(Rn_long / KSC_TO_MPA):,.1f} ksc | {(Rn_short / KSC_TO_MPA):,.1f} ksc |
| As ที่ต้องการ (การดัด) | {('%.2f' % (As_req_long / 100.0)) if feas_long else '—'} cm² | {('%.2f' % (As_req_short / 100.0)) if feas_short else '—'} cm² |
| As,min = ratio·b·h (ratio = {temp_ratio:.4f}) | {As_min_long / 100.0:,.2f} cm² | {As_min_short / 100.0:,.2f} cm² |
| As ที่ต้องการที่ควบคุม | **{('%.2f' % (As_des_long / 100.0)) if feas_long else '—'} cm²** | **{('%.2f' % (As_des_short / 100.0)) if feas_short else '—'} cm²** |
| เหล็กที่จัดให้ | **{n_long} - {size_long}** (S = {s_long / CM:,.1f} cm) | **{n_short} - {size_short}** (S = {s_short / CM:,.1f} cm) |
| As ที่จัดให้ = จำนวน × พื้นที่เส้น | **{As_prov_long / 100.0:,.2f} cm²** | **{As_prov_short / 100.0:,.2f} cm²** |
| ระยะเรียงสูงสุด s_max = min(3h, 450 mm) = {s_max / CM:,.1f} cm | {_s0(sp_long_ok)} | {_s0(sp_short_ok)} |
"""
    )
    if not feasible:
        st.error("ฐานรากบางเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว "
                 "(1 − 2Rn/0.85f'c < 0) — เพิ่ม h หรือ f'c")

    # ------------------------------------------------------------------
    # Checks summary
    # ------------------------------------------------------------------
    st.subheader("การตรวจสอบการออกแบบ")

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    _al = f"{As_req_long / 100.0:,.2f}" if feas_long else "—"
    _as_ = f"{As_req_short / 100.0:,.2f}" if feas_short else "—"
    st.markdown(
        f"""
| การตรวจสอบ | แรงที่กระทำ | กำลังต้านทาน / ขีดจำกัด | สถานะ |
|---|---|---|---|
| กำลังแบกทานดิน (ใช้งาน) | q = {q_service_kgf:,.1f} kgf/m² | qa = {q_a_ton * 1000.0:,.0f} kgf/m² | {_s(bearing_ok)} |
| แรงเฉือนทะลุ (สองทาง) | Vu = {Vup / 1000.0 * KN_TO_KGF:,.0f} kgf | φVc = {phiVc_punch / 1000.0 * KN_TO_KGF:,.0f} kgf | {_s(punch_ok)} |
| แรงเฉือนคาน — ด้านยาว | Vu = {Vu_long / 1000.0 * KN_TO_KGF:,.0f} kgf | φVc = {phiVc_v_long / 1000.0 * KN_TO_KGF:,.0f} kgf | {_s(beam_long_ok)} |
| แรงเฉือนคาน — ด้านสั้น | Vu = {Vu_short / 1000.0 * KN_TO_KGF:,.0f} kgf | φVc = {phiVc_v_short / 1000.0 * KN_TO_KGF:,.0f} kgf | {_s(beam_short_ok)} |
| การดัด — ด้านยาว | As,req = {_al} cm² | As,prov = {As_prov_long / 100.0:,.2f} cm² | {_s(flex_long_ok)} |
| การดัด — ด้านสั้น | As,req = {_as_} cm² | As,prov = {As_prov_short / 100.0:,.2f} cm² | {_s(flex_short_ok)} |
| เหล็กขั้นต่ำ — ด้านยาว | As,min = {As_min_long / 100.0:,.2f} cm² | As,prov = {As_prov_long / 100.0:,.2f} cm² | {_s(asmin_long_ok)} |
| เหล็กขั้นต่ำ — ด้านสั้น | As,min = {As_min_short / 100.0:,.2f} cm² | As,prov = {As_prov_short / 100.0:,.2f} cm² | {_s(asmin_short_ok)} |
| ระยะเรียง — ด้านยาว | S = {s_long / CM:,.1f} cm | s_max = {s_max / CM:,.1f} cm | {_s(sp_long_ok)} |
| ระยะเรียง — ด้านสั้น | S = {s_short / CM:,.1f} cm | s_max = {s_max / CM:,.1f} cm | {_s(sp_short_ok)} |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing — plan + elevation (B, L, h, cx, cy in mm)
    # ------------------------------------------------------------------
    # Map long/short mats onto the drawing's X (vertical grid) and Y
    # (horizontal grid) directions.
    if L >= B:                       # long dimension is L (Y) -> long bars run // Y
        qty_v, qty_h = n_long, n_short       # vertical lines // Y, horizontal // X
        size_v, size_h = size_long, size_short
    else:                           # long dimension is B (X) -> long bars run // X
        qty_v, qty_h = n_short, n_long
        size_v, size_h = size_short, size_long

    section_img = None
    try:
        section_img = draw_footing_plan(
            B, L, h, cx, cy, covering, size_v, qty_v, qty_h,
            col_shape="circ" if is_circular else "rect", Dc_mm=Dc,
            bar_size_y=size_h)
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    if passed:
        st.success(
            f"{PASS_TXT} — ผ่านทุกการตรวจสอบ: กำลังแบกทานดิน แรงเฉือนทะลุ "
            f"แรงเฉือนคาน (ยาว/สั้น) และการดัด (ยาว/สั้น)"
        )

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_footing_report(
            {
                "P_DL_kgf": P_DL_kgf, "P_LL_kgf": P_LL_kgf,
                "Wf_kgf": Wf_kgf, "Total_DL_kgf": Total_DL_kgf,
                "Pu_kgf": Pu_kgf,
                "q_a_kgf": q_a_ton * 1000.0, "B_m": B_m, "L_m": L_m,
                "col_shape": "circ" if is_circular else "rect",
                "cx": cx, "cy": cy, "Dc": Dc,
                "h": h, "covering": covering, "fc": fc, "fy": fy,
                "project": get_project_info(),
            },
            {
                "d_long": d_long, "d_short": d_short, "d_avg": d_avg,
                "q_service_kgf": q_service_kgf,
                "qu_net_kgf": qu_net_kgf,
                "Vup_kN": Vup / 1000.0,
                "phiVc_punch_kN": phiVc_punch / 1000.0,
                # long / short one-way shear
                "Vu_long_kN": Vu_long / 1000.0,
                "phiVc_long_kN": phiVc_v_long / 1000.0,
                "Vu_short_kN": Vu_short / 1000.0,
                "phiVc_short_kN": phiVc_v_short / 1000.0,
                # long / short flexure
                "Mu_long_kNm": Mu_long / 1.0e6,
                "Mu_short_kNm": Mu_short / 1.0e6,
                "As_req_long": As_req_long if feas_long else None,
                "As_req_short": As_req_short if feas_short else None,
                "As_min_long": As_min_long, "As_min_short": As_min_short,
                "As_prov_long": As_prov_long, "As_prov_short": As_prov_short,
                "size_long": size_long, "n_long": n_long,
                "s_long_cm": s_long / CM,
                "size_short": size_short, "n_short": n_short,
                "s_short_cm": s_short / CM,
                "s_max_cm": s_max / CM,
                "bearing_ok": bearing_ok,
                "punch_ok": punch_ok,
                "beam_long_ok": beam_long_ok, "beam_short_ok": beam_short_ok,
                "flex_long_ok": flex_long_ok, "flex_short_ok": flex_short_ok,
                "asmin_long_ok": asmin_long_ok, "asmin_short_ok": asmin_short_ok,
                "sp_long_ok": sp_long_ok, "sp_short_ok": sp_short_ok,
                "section_img": section_img,
                "status": "PASS",
            },
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="footing_design_report.pdf",
            mime="application/pdf",
        )
    else:
        failed = []
        if not bearing_ok:
            failed.append(
                f"กำลังแบกทานดิน (q = {q_service_kgf:,.1f} > "
                f"qa = {q_a_ton * 1000.0:,.0f} kgf/m²)"
            )
        if not punch_ok:
            failed.append(
                f"แรงเฉือนสองทาง (Vu = {Vup / 1000.0 * KN_TO_KGF:,.0f} > "
                f"φVc = {phiVc_punch / 1000.0 * KN_TO_KGF:,.0f} kgf)"
            )
        if not beam_long_ok:
            failed.append("แรงเฉือนคานด้านยาว")
        if not beam_short_ok:
            failed.append("แรงเฉือนคานด้านสั้น")
        if not (feas_long and feas_short):
            failed.append("หน้าตัดบางเกินไปสำหรับการดัด — เพิ่ม h หรือ f'c")
        if feas_long and not flex_long_ok:
            failed.append(
                f"การดัดด้านยาว (As,prov = {As_prov_long / 100.0:,.2f} < "
                f"As,req = {As_req_long / 100.0:,.2f} cm²)")
        if feas_short and not flex_short_ok:
            failed.append(
                f"การดัดด้านสั้น (As,prov = {As_prov_short / 100.0:,.2f} < "
                f"As,req = {As_req_short / 100.0:,.2f} cm²)")
        if not asmin_long_ok:
            failed.append("เหล็กขั้นต่ำด้านยาว")
        if not asmin_short_ok:
            failed.append("เหล็กขั้นต่ำด้านสั้น")
        if not sp_long_ok:
            failed.append(f"ระยะเรียงด้านยาว S = {s_long / CM:,.1f} > "
                          f"s_max = {s_max / CM:,.1f} cm (เพิ่มจำนวนเส้น)")
        if not sp_short_ok:
            failed.append(f"ระยะเรียงด้านสั้น S = {s_short / CM:,.1f} > "
                          f"s_max = {s_max / CM:,.1f} cm (เพิ่มจำนวนเส้น)")
        st.error(f"{FAIL_TXT} — " + "; ".join(failed))


# ===========================================================================
# Tab 2 — ฐานเสาเข็ม (pile caps)
# ===========================================================================


PILE_LABELS = {k: f"F{k} Pile Cap ({k} ต้น)" for k in range(1, 10)}


def _tab_pile():
    choice = st.selectbox(
        "ประเภทฐานเสาเข็ม",
        list(PILE_LABELS.values()),
        index=1,                       # default F2
        key="pile_type",
    )
    n = next(k for k, v in PILE_LABELS.items() if v == choice)
    _render_pile_cap(n, f"pc{n}")


def _pile_coords(n, S):
    """Pile-centre coordinates (mm) relative to the column centre (0, 0),
    for a group of ``n`` piles at centre-to-centre spacing ``S``."""
    r3 = math.sqrt(3.0)
    if n == 1:
        return [(0.0, 0.0)]
    if n == 2:                                    # row along the length (Y)
        return [(0.0, -S / 2.0), (0.0, S / 2.0)]
    if n == 3:                                    # equilateral triangle
        return [(0.0, S / r3),
                (S / 2.0, -S / (2.0 * r3)),
                (-S / 2.0, -S / (2.0 * r3))]
    if n == 4:                                    # 2 x 2 corners
        return [(-S / 2.0, -S / 2.0), (S / 2.0, -S / 2.0),
                (S / 2.0, S / 2.0), (-S / 2.0, S / 2.0)]
    if n == 5:                                    # 4 corners + centre
        return [(0.0, 0.0),
                (S / 2.0, S / 2.0), (S / 2.0, -S / 2.0),
                (-S / 2.0, S / 2.0), (-S / 2.0, -S / 2.0)]
    if n == 6:                                    # 2 columns x 3 rows
        return [(-S / 2.0, S), (S / 2.0, S),
                (-S / 2.0, 0.0), (S / 2.0, 0.0),
                (-S / 2.0, -S), (S / 2.0, -S)]
    if n == 7:                                    # hexagon + centre
        pts = [(0.0, 0.0)]
        for i in range(6):
            ang = math.radians(60.0 * i)
            pts.append((S * math.cos(ang), S * math.sin(ang)))
        return pts
    if n == 8:                                    # 3 x 3 grid without centre
        return [(0.0, S), (0.0, -S), (S, 0.0), (-S, 0.0),
                (S, S), (S, -S), (-S, S), (-S, -S)]
    if n == 9:                                    # full 3 x 3 grid
        return [(0.0, S), (0.0, -S), (S, 0.0), (-S, 0.0),
                (S, S), (S, -S), (-S, S), (-S, -S), (0.0, 0.0)]
    # fallback: single centred row
    return [((i - (n - 1) / 2.0) * S, 0.0) for i in range(n)]


def _render_pile_cap(n_piles, kp, is_eccentric=False):
    """Structured (preliminary) design flow for an F1-F9 pile cap.

    n_piles      : 1..9 (layout from ``_pile_coords``)
    kp           : widget-key prefix so the tabs can coexist
    is_eccentric : True for the F1E-F9E tab — exposes ex / ey inputs and
                   distributes the pile reactions elastically.
    """
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        P_DL_kgf = st.number_input("น้ำหนักบรรทุกคงที่จากเสา P_DL (kgf)",
                                   min_value=0.0, value=60000.0, step=100.0,
                                   format="%.0f", key=f"{kp}_PDL")
        P_LL_kgf = st.number_input("น้ำหนักบรรทุกจรจากเสา P_LL (kgf)",
                                   min_value=0.0, value=25000.0, step=100.0,
                                   format="%.0f", key=f"{kp}_PLL")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d", key=f"{kp}_fc")
    with c2:
        pile_cap_kgf = st.number_input(
            "กำลังรับน้ำหนักปลอดภัยของเสาเข็ม (kgf/ต้น)", min_value=1000.0,
            value=60000.0, step=1000.0, format="%.0f", key=f"{kp}_pcap")
        pile_shape = st.selectbox(
            "รูปร่างเสาเข็ม (Pile Shape)",
            ["Square (สี่เหลี่ยม)", "Circular (กลม)", "Hexagonal (หกเหลี่ยม)",
             "I-Section (รูปตัวไอ)"],
            key=f"{kp}_pshape")
        pile_size_cm = st.number_input(
            "ขนาดเสาเข็ม D_pile — กว้าง/เส้นผ่านศูนย์กลาง/ระยะกึ่งกลางด้าน (cm)",
            min_value=15.0, value=30.0, step=0.01, format="%.2f",
            key=f"{kp}_pile")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d", key=f"{kp}_fy")
    with c3:
        c_cm = st.number_input("ขนาดเสาสี่เหลี่ยมจัตุรัส c (cm)", min_value=15.0,
                               value=40.0, step=0.01, format="%.2f", key=f"{kp}_c")
        h_cm = st.number_input("ความหนาฐานราก h (cm)", min_value=30.0,
                               value=60.0, step=0.01, format="%.2f", key=f"{kp}_h")
        covering_cm = st.number_input("ระยะหุ้มคอนกรีตด้านข้าง (cm)",
                                      min_value=5.0, value=7.5, step=0.01,
                                      format="%.2f", key=f"{kp}_cov")
        pile_embed_cm = st.number_input(
            "ระยะฝังเข็ม (Pile Embedment) (cm)", min_value=2.5, value=10.0,
            step=1.0, format="%.1f", key=f"{kp}_emb")

    # Column eccentricity from the pile-group centroid (available on both tabs)
    e1, e2 = st.columns(2)
    with e1:
        ex_cm = st.number_input("ระยะเยื้องศูนย์ของเสา ex (cm)",
                                value=15.0 if is_eccentric else 0.0,
                                step=1.0, format="%.2f", key=f"{kp}_ex")
    with e2:
        ey_cm = st.number_input("ระยะเยื้องศูนย์ของเสา ey (cm)",
                                value=0.0, step=1.0, format="%.2f",
                                key=f"{kp}_ey")

    # ------------------------------------------------------------------
    # Cap plan size — automatic (pile layout + edge distance) or manual.
    # The preview below only seeds the manual inputs; the binding auto
    # size is recomputed further down from the real pile coordinates.
    # ------------------------------------------------------------------
    _S_prev = 3.0 * pile_size_cm
    _edge_prev = 0.5 * pile_size_cm + max(covering_cm, 15.0)
    _bp_prev = _pile_coords(n_piles, _S_prev)
    _pxs = [p[0] for p in _bp_prev]
    _pys = [p[1] for p in _bp_prev]
    if n_piles == 1:
        _autoW_cm = _autoL_cm = max(c_cm + 30.0, 2.0 * _edge_prev)
    else:
        _autoW_cm = max((max(_pxs) - min(_pxs)) + 2.0 * _edge_prev, c_cm + 20.0)
        _autoL_cm = max((max(_pys) - min(_pys)) + 2.0 * _edge_prev, c_cm + 20.0)

    st.markdown("**ขนาดฐานราก (Footing / Cap Size)**")
    mcap0, mcap1, mcap2 = st.columns([1.3, 1, 1])
    with mcap0:
        manual_cap = st.checkbox("กำหนดขนาดเอง (Manual)", value=False,
                                 key=f"{kp}_mancap")
    with mcap1:
        cap_W_cm_in = st.number_input(
            "ความกว้างฐานราก B (cm)", min_value=30.0,
            value=float(round(_autoW_cm, 1)), step=5.0, format="%.1f",
            key=f"{kp}_capw", disabled=not manual_cap)
    with mcap2:
        cap_L_cm_in = st.number_input(
            "ความยาวฐานราก L (cm)", min_value=30.0,
            value=float(round(_autoL_cm, 1)), step=5.0, format="%.1f",
            key=f"{kp}_capl", disabled=not manual_cap)
    if not manual_cap:
        st.caption(f"ขนาดอัตโนมัติ ≈ {_autoW_cm:,.0f} × {_autoL_cm:,.0f} cm "
                   "— ติ๊ก «กำหนดขนาดเอง» เพื่อปรับแก้")

    _shape_key = ("square" if pile_shape.startswith("Square")
                  else "hex" if pile_shape.startswith("Hex")
                  else "isec" if pile_shape.startswith("I-")
                  else "circ")
    pile_shape_th = pile_shape.split(" (")[-1].rstrip(")")

    st.subheader("เหล็กเสริม (แยกทิศทาง)")
    _bopts = list(rebars.keys())
    _rl1, _rl2 = st.columns(2)
    with _rl1:
        size_long = st.selectbox("เหล็กด้านยาว — ขนาด (Long Direction)",
                                 _bopts, index=_bopts.index("DB16"),
                                 key=f"{kp}_szl")
    with _rl2:
        qty_long = int(st.number_input("เหล็กด้านยาว — จำนวนเส้น",
                                       min_value=2, value=12, step=1,
                                       key=f"{kp}_qtyl"))
    _rs1, _rs2 = st.columns(2)
    with _rs1:
        size_short = st.selectbox("เหล็กด้านสั้น — ขนาด (Short Direction)",
                                  _bopts, index=_bopts.index("DB16"),
                                  key=f"{kp}_szs")
    with _rs2:
        qty_short = int(st.number_input("เหล็กด้านสั้น — จำนวนเส้น",
                                        min_value=2, value=12, step=1,
                                        key=f"{kp}_qtys"))

    # ---- Unit conversions -> ACI calculation core ----
    P_DL = P_DL_kgf * KGF_TO_KN              # kN
    P_LL = P_LL_kgf * KGF_TO_KN              # kN
    pile_cap_kN = pile_cap_kgf * KGF_TO_KN   # kN
    Dp = pile_size_cm * CM                   # mm
    c = c_cm * CM                            # mm
    h = h_cm * CM                            # mm
    covering = covering_cm * CM              # mm (side cover to outer bars)
    pile_embed = pile_embed_cm * CM          # mm (pile penetration into cap)
    fc = fc_ksc * KSC_TO_MPA                 # MPa
    fy = fy_ksc * KSC_TO_MPA                 # MPa
    ex_mm = ex_cm * CM                       # mm
    ey_mm = ey_cm * CM                       # mm

    area_long = rebars[size_long]
    area_short = rebars[size_short]
    db_long = float(size_long[2:])
    db_short = float(size_short[2:])

    # The bottom mat rests on the embedded pile head, so the effective cover
    # to the bottom bars is the pile-embedment length (ACI-style).
    d_long = h - pile_embed - db_long / 2.0   # bottom layer (long-dir bars)
    d_short = d_long - db_long                # short-dir bars sit on top
    d_avg = 0.5 * (d_long + d_short)          # for punching (two-way)
    if d_short <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบความหนา ระยะฝังเข็ม "
                 "หรือขนาดเหล็กเสริม")
        return

    # ------------------------------------------------------------------
    # 1. Factored NET column load (no self-weight) — drives the cap design
    #    moments / shears.  Eccentricity moments about each axis:
    #      Muy = Pu,net * (ex/100)   (bending about Y, pairs with x_i)
    #      Mux = Pu,net * (ey/100)   (bending about X, pairs with y_i)
    # ------------------------------------------------------------------
    Pu_net_kgf = 1.2 * P_DL_kgf + 1.6 * P_LL_kgf       # kgf
    Pu_net = Pu_net_kgf * KGF_TO_KN                    # kN
    Pu_net_N = Pu_net * 1000.0                         # N
    Muy_kgfm = Pu_net_kgf * (ex_cm / 100.0)           # kgf-m
    Mux_kgfm = Pu_net_kgf * (ey_cm / 100.0)           # kgf-m

    # ------------------------------------------------------------------
    # 2. Pile layout, spacing, edge distance, elastic reaction rule
    # ------------------------------------------------------------------
    S = 3.0 * Dp                                       # mm centre-to-centre
    edge = 0.5 * Dp + max(covering, 150.0)             # pile centre -> cap edge
    base_piles_c = _pile_coords(n_piles, S)
    sum_x2 = sum(px * px for (px, py) in base_piles_c)
    sum_y2 = sum(py * py for (px, py) in base_piles_c)

    def _elastic_reactions(axial, ecc_load):
        """Per-pile reaction  = axial/n + (ecc_load*ex)*x/Σx²
        + (ecc_load*ey)*y/Σy².  `axial` may carry the (concentric) cap
        self-weight; only `ecc_load` — the column load — produces moments.
        Unit-agnostic: output shares the unit of `axial` / `ecc_load`."""
        my = ecc_load * ex_mm
        mx = ecc_load * ey_mm
        out = []
        for (px, py) in base_piles_c:
            r = axial / n_piles
            if sum_x2 > 0.0:
                r += my * px / sum_x2
            if sum_y2 > 0.0:
                r += mx * py / sum_y2
            out.append(r)
        return out

    # factored NET per-pile reactions — used for all cap shear / flexure
    Ru_list_N = _elastic_reactions(Pu_net_N, Pu_net_N)   # N / pile
    Ru_N = Pu_net_N / n_piles                            # N — group average
    Ru_max_N = max(Ru_list_N)                            # N — governing pile

    # ------------------------------------------------------------------
    # 3. Cap plan dimensions (+ column shifted by (ex, ey))
    # ------------------------------------------------------------------
    piles_c_col = [(px - ex_mm, py - ey_mm) for (px, py) in base_piles_c]
    piles_eval = list(zip(piles_c_col, Ru_list_N))     # (coord, Ru_i[N])

    if ex_mm or ey_mm:
        xs = [x for (x, y) in piles_c_col]
        ys = [y for (x, y) in piles_c_col]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cap_W = max((max_x - min_x) + 2.0 * edge, c + 200.0)
        cap_L = max((max_y - min_y) + 2.0 * edge, c + 200.0)
        piles_xy = [(x - min_x + edge, y - min_y + edge)
                    for (x, y) in piles_c_col]
        col_pos = (0.0 - min_x + edge, 0.0 - min_y + edge)
    else:
        xs = [px for (px, _py) in base_piles_c]
        ys = [py for (_px, py) in base_piles_c]
        if n_piles == 1:
            cap_W = cap_L = max(c + 300.0, 2.0 * edge)
        else:
            cap_W = (max(xs) - min(xs)) + 2.0 * edge
            cap_L = (max(ys) - min(ys)) + 2.0 * edge
        cap_W = max(cap_W, c + 200.0)
        cap_L = max(cap_L, c + 200.0)
        piles_xy = [(cap_W / 2.0 + px, cap_L / 2.0 + py)
                    for (px, py) in base_piles_c]
        col_pos = None

    # ---- manual cap-size override: keep the pile group / column centred,
    #      grow or shrink the slab symmetrically about it ----
    if manual_cap:
        new_W = cap_W_cm_in * CM
        new_L = cap_L_cm_in * CM
        dW = (new_W - cap_W) / 2.0
        dL = (new_L - cap_L) / 2.0
        piles_xy = [(x + dW, y + dL) for (x, y) in piles_xy]
        if col_pos is not None:
            col_pos = (col_pos[0] + dW, col_pos[1] + dL)
        cap_W, cap_L = new_W, new_L
        _out = [i + 1 for i, (x, y) in enumerate(piles_xy)
                if x < 0.0 or x > cap_W or y < 0.0 or y > cap_L]
        if _out:
            st.warning("⚠️ ขนาดฐานรากที่กำหนดเล็กเกินไป — เสาเข็มต้นที่ "
                       + ", ".join(map(str, _out))
                       + " อยู่นอกขอบฐานราก โปรดเพิ่มขนาด")

    # map the long / short reinforcement mats onto the cap X / Y directions
    long_is_x = cap_W >= cap_L
    if long_is_x:
        size_x, size_y = size_long, size_short
        area_x, area_y = area_long, area_short
    else:
        size_x, size_y = size_short, size_long
        area_x, area_y = area_short, area_long

    # ------------------------------------------------------------------
    # 4. Cap self-weight + SERVICE total pile reactions (capacity check)
    # ------------------------------------------------------------------
    cap_area_m2 = (cap_W / 1000.0) * (cap_L / 1000.0)
    Wf_kgf = cap_area_m2 * (h_cm / 100.0) * CONC_UW_KGF   # kgf (exact 2400)
    Wf_pp_kgf = Wf_kgf / n_piles                          # kgf per pile
    P_col_serv_kgf = P_DL_kgf + P_LL_kgf                  # kgf (eccentric part)
    P_serv_tot_kgf = P_col_serv_kgf + Wf_kgf              # kgf (+ self-weight)

    R_tot_list_kgf = _elastic_reactions(P_serv_tot_kgf, P_col_serv_kgf)
    R_max_kgf = max(R_tot_list_kgf)                       # kgf/pile — governing
    R_min_kgf = min(R_tot_list_kgf)                       # kgf/pile — uplift check
    reaction_ok = R_max_kgf <= pile_cap_kgf
    uplift_ok = R_min_kgf >= 0.0

    R_serv_kgf = P_serv_tot_kgf / n_piles                 # kgf/pile — group average

    # single-pile punching perimeter depends on the pile shape (ACI 15.5)
    if _shape_key == "square" or _shape_key == "isec":
        bo_pile = 4.0 * (Dp + d_avg)
        pile_perim_txt = "4·(D_pile + d)"
    elif _shape_key == "hex":
        bo_pile = 3.464 * Dp + math.pi * d_avg
        pile_perim_txt = "3.464·D_pile + π·d"
    else:                                                 # circular
        bo_pile = math.pi * (Dp + d_avg)
        pile_perim_txt = "π·(D_pile + d)"

    # ------------------------------------------------------------------
    # 5. Two-way (punching) shear around the column — section at d/2
    #    Vu = Pu,net − Σ(actual Ru_i of piles inside the perimeter).
    # ------------------------------------------------------------------
    half = c / 2.0 + d_avg / 2.0
    n_inside = sum(1 for ((px, py), _ru) in piles_eval
                   if abs(px) <= half and abs(py) <= half)
    Vup = Pu_net_N - sum(ru for ((px, py), ru) in piles_eval
                         if abs(px) <= half and abs(py) <= half)   # N
    bo = 4.0 * (c + d_avg)                             # mm
    vc1 = 0.17 * (1.0 + 2.0 / 1.0) * LAMBDA * math.sqrt(fc)
    vc2 = 0.083 * (ALPHA_S * d_avg / bo + 2.0) * LAMBDA * math.sqrt(fc)
    vc3 = 0.33 * LAMBDA * math.sqrt(fc)
    vc_punch = min(vc1, vc2, vc3)                      # MPa
    phiVc_punch = phi["shear"] * vc_punch * bo * d_avg  # N
    punch_ok = Vup <= phiVc_punch

    # 5b. Punching of one pile head through the cap (governing pile).
    phiVc_pile = phi["shear"] * 0.33 * LAMBDA * math.sqrt(fc) * bo_pile * d_avg
    pile_punch_ok = Ru_max_N <= phiVc_pile

    # ------------------------------------------------------------------
    # 5-6. One-way shear + flexure — computed independently for the X and
    #      the Y axis by summing the actual Ru_i of the piles beyond each
    #      critical section, then mapped to the long / short mats.
    # ------------------------------------------------------------------
    face = c / 2.0

    def _side(sign, axis, d_dir):
        """(moment_at_face[N.mm], shear_beyond_d[N], n_beyond_d, n_beyond_face)."""
        sec = face + d_dir
        m = v = 0.0
        n_d = n_face = 0
        for ((px, py), ru) in piles_eval:
            coord = sign * (px if axis == 0 else py)
            if coord > sec + 1.0e-6:
                v += ru
                n_d += 1
            arm = coord - face
            if arm > 1.0e-6:
                m += ru * arm
                n_face += 1
        return m, v, n_d, n_face

    d_x = d_long if long_is_x else d_short
    d_y = d_short if long_is_x else d_long
    x_sides = [_side(s, 0, d_x) for s in (1.0, -1.0)]
    y_sides = [_side(s, 1, d_y) for s in (1.0, -1.0)]
    gx_m = max(x_sides, key=lambda e: e[0])
    gx_v = max(x_sides, key=lambda e: e[1])
    gy_m = max(y_sides, key=lambda e: e[0])
    gy_v = max(y_sides, key=lambda e: e[1])
    Mu_x, Vu_x, n_beyond_x = gx_m[0], gx_v[1], gx_v[2]
    Mu_y, Vu_y, n_beyond_y = gy_m[0], gy_v[1], gy_v[2]

    # long / short direction (long bars resist the larger cap span)
    if long_is_x:
        Mu_long, Vu_long, d_bar_long, bw_long = Mu_x, Vu_x, d_long, cap_L
        Mu_short, Vu_short, d_bar_short, bw_short = Mu_y, Vu_y, d_short, cap_W
        n_bl, n_bs = n_beyond_x, n_beyond_y
    else:
        Mu_long, Vu_long, d_bar_long, bw_long = Mu_y, Vu_y, d_long, cap_W
        Mu_short, Vu_short, d_bar_short, bw_short = Mu_x, Vu_x, d_short, cap_L
        n_bl, n_bs = n_beyond_y, n_beyond_x

    phiVc_long = (phi["shear"] * 0.17 * LAMBDA * math.sqrt(fc)
                  * bw_long * d_bar_long)
    phiVc_short = (phi["shear"] * 0.17 * LAMBDA * math.sqrt(fc)
                   * bw_short * d_bar_short)
    beam_long_ok = Vu_long <= phiVc_long
    beam_short_ok = Vu_short <= phiVc_short

    As_req_long, Rn_long, rho_long, feas_long = _flexure_as(
        Mu_long, bw_long, d_bar_long, fc, fy)
    As_req_short, Rn_short, rho_short, feas_short = _flexure_as(
        Mu_short, bw_short, d_bar_short, fc, fy)

    temp_ratio = _temp_steel_ratio(fy)
    As_min_long = temp_ratio * bw_long * h
    As_min_short = temp_ratio * bw_short * h

    # provided As directly from the bar count; actual spacing back-computed
    #   long-dir bars are distributed across the SHORT cap dimension (bw_long)
    #   short-dir bars are distributed across the LONG cap dimension (bw_short)
    n_long, n_short = qty_long, qty_short
    As_prov_long = n_long * area_long
    As_prov_short = n_short * area_short
    s_long = ((bw_long - 2.0 * covering) / (n_long - 1)
              if n_long > 1 else bw_long - 2.0 * covering)     # mm
    s_short = ((bw_short - 2.0 * covering) / (n_short - 1)
               if n_short > 1 else bw_short - 2.0 * covering)  # mm
    s_max = min(3.0 * h, 450.0)                                # ACI max spacing
    sp_long_ok = s_long <= s_max
    sp_short_ok = s_short <= s_max

    As_des_long = (max(As_req_long, As_min_long) if feas_long
                   else float("inf"))
    As_des_short = (max(As_req_short, As_min_short) if feas_short
                    else float("inf"))
    flex_long_ok = feas_long and As_prov_long >= As_req_long
    flex_short_ok = feas_short and As_prov_short >= As_req_short
    asmin_long_ok = As_prov_long >= As_min_long
    asmin_short_ok = As_prov_short >= As_min_short
    feasible = feas_long and feas_short

    # spacing / size mapped to the cap X / Y for the drawing + report
    s_x, s_y = (s_long, s_short) if long_is_x else (s_short, s_long)
    n_x, n_y = (n_long, n_short) if long_is_x else (n_short, n_long)
    bar_sx_cm = s_x / CM
    bar_sy_cm = s_y / CM

    passed = (reaction_ok and uplift_ok and punch_ok and pile_punch_ok
              and beam_long_ok and beam_short_ok
              and flex_long_ok and flex_short_ok
              and asmin_long_ok and asmin_short_ok
              and sp_long_ok and sp_short_ok)

    def _s0(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    if not uplift_ok:
        st.warning(f"⚠️ เกิดแรงถอน (uplift) ที่เสาเข็ม — Rmin = "
                   f"{R_min_kgf:,.0f} kgf/ต้น < 0 : ตรวจสอบระยะเยื้องศูนย์ "
                   f"หรือเพิ่มจำนวน/ระยะเสาเข็ม")
    if not reaction_ok:
        st.warning(f"⚠️ แรงในเสาเข็มสูงสุด Rmax,total = {R_max_kgf:,.0f} "
                   f"kgf/ต้น เกินกำลังรับปลอดภัย {pile_cap_kgf:,.0f} kgf/ต้น")

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    ecc_rows = ""
    if ex_mm or ey_mm:
        ecc_rows = (
            f"| ระยะเยื้องศูนย์ ex , ey | {ex_cm:,.2f} , {ey_cm:,.2f} cm |\n"
            f"| โมเมนต์เยื้องศูนย์ Muy = Pu,net·(ex/100) | "
            f"{Muy_kgfm:,.0f} kgf-m |\n"
            f"| โมเมนต์เยื้องศูนย์ Mux = Pu,net·(ey/100) | "
            f"{Mux_kgfm:,.0f} kgf-m |\n")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| จำนวนเสาเข็ม | {n_piles} ต้น |
| รูปร่างเสาเข็ม / ขนาด D_pile | {pile_shape_th} / {pile_size_cm:,.1f} cm |
| น้ำหนักบรรทุกประลัยสุทธิ Pu,net = 1.2 P_DL + 1.6 P_LL | **{Pu_net_kgf:,.0f} kgf** |
| น้ำหนักฐานรากเอง Wf = พื้นที่·h·2400 | {Wf_kgf:,.0f} kgf ({Wf_pp_kgf:,.0f} kgf/ต้น) |
{ecc_rows}| แรงเฉลี่ยต่อเสาเข็ม (ใช้งาน รวม Wf) R = ΣP/n | {R_serv_kgf:,.0f} kgf/ต้น |
| แรงในเสาเข็มสูงสุด (ใช้งาน รวม Wf) Rmax,total | **{R_max_kgf:,.0f} kgf/ต้น** |
| แรงในเสาเข็มต่ำสุด (ใช้งาน รวม Wf) Rmin,total | {R_min_kgf:,.0f} kgf/ต้น |
| แรงในเสาเข็มสูงสุด (ประลัยสุทธิ) Ru,max | {Ru_max_N / 1000.0 * KN_TO_KGF:,.0f} kgf/ต้น |
| กำลังรับปลอดภัยของเสาเข็ม | {pile_cap_kgf:,.0f} kgf/ต้น |
| ระยะห่างเสาเข็ม S = 3·Dp | {S / CM:,.2f} cm |
| ระยะขอบ (ศูนย์กลางเข็มถึงขอบ) | {edge / CM:,.2f} cm |
| ขนาดฐานราก (กว้าง × ยาว) | {cap_W / CM:,.0f} × {cap_L / CM:,.0f} cm |
| ความลึกประสิทธิผล ด้านยาว d_long / ด้านสั้น d_short | **{d_long / CM:,.2f} / {d_short / CM:,.2f} cm** |
"""
    )

    st.markdown("**แรงเฉือนทะลุ (สองทาง)** — รอบเสา ที่ระยะ d/2 (ใช้ d_avg)")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| เส้นรอบรูปวิกฤต b₀ = 4(c + d_avg) | {bo:,.0f} mm |
| เสาเข็มในเขตวิกฤต | {n_inside} ต้น |
| Vu = Pu,net − ΣRu,i(ใน) | {Vup / 1000.0 * KN_TO_KGF:,.0f} kgf |
| φVc = 0.75·vc·b₀·d_avg | **{phiVc_punch / 1000.0 * KN_TO_KGF:,.0f} kgf** |
| แรงเฉือนทะลุหัวเข็ม Ru,max | {Ru_max_N / 1000.0 * KN_TO_KGF:,.0f} kgf |
| b₀,เข็ม ({pile_shape_th}) = {pile_perim_txt} | {bo_pile:,.0f} mm |
| φVc (หัวเข็ม) = 0.75·0.33·√f'c·b₀,เข็ม·d_avg | **{phiVc_pile / 1000.0 * KN_TO_KGF:,.0f} kgf** |
"""
    )

    st.markdown("**แรงเฉือนคาน (ทางเดียว)** — ที่ระยะ d จากผิวเสา แยกสองทิศทาง")
    st.markdown(
        f"""
| รายการ | ด้านยาว (Long) | ด้านสั้น (Short) |
|---|---|---|
| เสาเข็มเลยหน้าตัด | {n_bl} ต้น | {n_bs} ต้น |
| Vu = Σ Ru,i | {Vu_long / 1000.0 * KN_TO_KGF:,.0f} kgf | {Vu_short / 1000.0 * KN_TO_KGF:,.0f} kgf |
| φVc = 0.75·0.17·√f'c·bw·d | {phiVc_long / 1000.0 * KN_TO_KGF:,.0f} kgf | {phiVc_short / 1000.0 * KN_TO_KGF:,.0f} kgf |
| สถานะ | {_s0(beam_long_ok)} | {_s0(beam_short_ok)} |
"""
    )

    st.markdown("**การดัด** — โมเมนต์ที่ผิวเสา แยกสองทิศทาง (Σ Ru,i · แขน)")
    st.markdown(
        f"""
| รายการ | ด้านยาว (Long) | ด้านสั้น (Short) |
|---|---|---|
| Mu = Σ Ru,i·(ระยะจากผิวเสา) | {Mu_long / 1.0e6 * KN_TO_KGF:,.0f} kgf-m | {Mu_short / 1.0e6 * KN_TO_KGF:,.0f} kgf-m |
| Rn = Mu / (φ·b·d²) | {(Rn_long / KSC_TO_MPA):,.1f} ksc | {(Rn_short / KSC_TO_MPA):,.1f} ksc |
| As ที่ต้องการ (การดัด) | {('%.2f' % (As_req_long / 100.0)) if feas_long else '—'} cm² | {('%.2f' % (As_req_short / 100.0)) if feas_short else '—'} cm² |
| As,min = ratio·b·h (ratio = {temp_ratio:.4f}) | {As_min_long / 100.0:,.2f} cm² | {As_min_short / 100.0:,.2f} cm² |
| As ที่ต้องการที่ควบคุม | **{('%.2f' % (As_des_long / 100.0)) if feas_long else '—'} cm²** | **{('%.2f' % (As_des_short / 100.0)) if feas_short else '—'} cm²** |
| เหล็กที่จัดให้ | **{n_long} - {size_long}** (S = {s_long / CM:,.1f} cm) | **{n_short} - {size_short}** (S = {s_short / CM:,.1f} cm) |
| As ที่จัดให้ = จำนวน × พื้นที่เส้น | **{As_prov_long / 100.0:,.2f} cm²** | **{As_prov_short / 100.0:,.2f} cm²** |
| ระยะเรียงสูงสุด s_max = min(3h, 450 mm) = {s_max / CM:,.1f} cm | {_s0(sp_long_ok)} | {_s0(sp_short_ok)} |
"""
    )
    if not feasible:
        st.error("หน้าตัดบางเกินไปสำหรับการดัด (1 − 2Rn/0.85f'c < 0) — "
                 "เพิ่ม h หรือ f'c")

    # ------------------------------------------------------------------
    # Checks summary
    # ------------------------------------------------------------------
    st.subheader("การตรวจสอบการออกแบบ")

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    _al = f"{As_req_long / 100.0:,.2f}" if feas_long else "—"
    _as_ = f"{As_req_short / 100.0:,.2f}" if feas_short else "—"
    st.markdown(
        f"""
| การตรวจสอบ | แรงที่กระทำ | กำลังต้านทาน / ขีดจำกัด | สถานะ |
|---|---|---|---|
| แรงในเสาเข็มสูงสุด ≤ กำลังปลอดภัย | Rmax,total = {R_max_kgf:,.0f} kgf/ต้น | {pile_cap_kgf:,.0f} kgf/ต้น | {_s(reaction_ok)} |
| ไม่มีแรงถอน (Rmin ≥ 0) | Rmin,total = {R_min_kgf:,.0f} kgf/ต้น | ≥ 0 | {_s(uplift_ok)} |
| แรงเฉือนทะลุ (สองทาง) | Vu = {Vup / 1000.0 * KN_TO_KGF:,.0f} kgf | φVc = {phiVc_punch / 1000.0 * KN_TO_KGF:,.0f} kgf | {_s(punch_ok)} |
| แรงเฉือนทะลุหัวเข็ม | Ru = {Ru_N / 1000.0 * KN_TO_KGF:,.0f} kgf | φVc = {phiVc_pile / 1000.0 * KN_TO_KGF:,.0f} kgf | {_s(pile_punch_ok)} |
| แรงเฉือนคาน — ด้านยาว | Vu = {Vu_long / 1000.0 * KN_TO_KGF:,.0f} kgf | φVc = {phiVc_long / 1000.0 * KN_TO_KGF:,.0f} kgf | {_s(beam_long_ok)} |
| แรงเฉือนคาน — ด้านสั้น | Vu = {Vu_short / 1000.0 * KN_TO_KGF:,.0f} kgf | φVc = {phiVc_short / 1000.0 * KN_TO_KGF:,.0f} kgf | {_s(beam_short_ok)} |
| การดัด — ด้านยาว | As,req = {_al} cm² | As,prov = {As_prov_long / 100.0:,.2f} cm² | {_s(flex_long_ok)} |
| การดัด — ด้านสั้น | As,req = {_as_} cm² | As,prov = {As_prov_short / 100.0:,.2f} cm² | {_s(flex_short_ok)} |
| เหล็กขั้นต่ำ — ด้านยาว | As,min = {As_min_long / 100.0:,.2f} cm² | As,prov = {As_prov_long / 100.0:,.2f} cm² | {_s(asmin_long_ok)} |
| เหล็กขั้นต่ำ — ด้านสั้น | As,min = {As_min_short / 100.0:,.2f} cm² | As,prov = {As_prov_short / 100.0:,.2f} cm² | {_s(asmin_short_ok)} |
| ระยะเรียง — ด้านยาว | S = {s_long / CM:,.1f} cm | s_max = {s_max / CM:,.1f} cm | {_s(sp_long_ok)} |
| ระยะเรียง — ด้านสั้น | S = {s_short / CM:,.1f} cm | s_max = {s_max / CM:,.1f} cm | {_s(sp_short_ok)} |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing — plan view
    # ------------------------------------------------------------------
    # drawing grid counts: vertical lines = Y-running bars (across W) -> n_y;
    # horizontal lines = X-running bars (across L) -> n_x
    qv, qh = n_y, n_x
    # 2-pile cap -> cut the Side View along the pile line (the longer axis)
    side_axis = "y" if (n_piles == 2 and cap_L >= cap_W) else "x"

    section_img = None
    try:
        section_img = draw_pile_cap_plan(
            cap_W, cap_L, h, c, Dp, piles_xy, covering, size_y, qv,
            col_pos=col_pos, qty_y=qh, spacing_mm=S, pile_shape=_shape_key,
            bar_size_y=size_x, side_axis=side_axis, pile_embed_mm=pile_embed,
            pile_cap_kgf=pile_cap_kgf, pile_shape_th=pile_shape_th)
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    if passed:
        st.success(f"{PASS_TXT} — ผ่านทุกการตรวจสอบสำหรับฐานเสาเข็ม {n_piles} ต้น")

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_pile_cap_report(
            {
                "P_serv_kgf": P_serv_tot_kgf, "Pu_net_kgf": Pu_net_kgf,
                "pile_cap_kgf": pile_cap_kgf, "n_piles": n_piles,
                "pile_shape": pile_shape_th, "pile_perim_txt": pile_perim_txt,
                "Dp": Dp, "c": c, "h": h, "covering": covering,
                "pile_embed_cm": pile_embed_cm,
                "manual_cap": bool(manual_cap),
                "fc": fc, "fy": fy,
                "ex_cm": ex_cm, "ey_cm": ey_cm,
                "Muy_kgfm": Muy_kgfm, "Mux_kgfm": Mux_kgfm,
                "project": get_project_info(),
            },
            {
                "d_long": d_long, "d_short": d_short, "d_avg": d_avg,
                "R_serv_kgf": R_serv_kgf,
                "R_max_kgf": R_max_kgf,
                "R_min_kgf": R_min_kgf,
                "Ru_avg_kgf": Ru_N / 1000.0 * KN_TO_KGF,
                "Ru_max_kgf": Ru_max_N / 1000.0 * KN_TO_KGF,
                "S": S,
                "edge": edge,
                "cap_W": cap_W,
                "cap_L": cap_L,
                "n_inside": n_inside,
                "Vup_kN": Vup / 1000.0,
                "phiVc_punch_kN": phiVc_punch / 1000.0,
                "phiVc_pile_kN": phiVc_pile / 1000.0,
                # long / short one-way shear
                "Vu_long_kN": Vu_long / 1000.0,
                "phiVc_long_kN": phiVc_long / 1000.0,
                "Vu_short_kN": Vu_short / 1000.0,
                "phiVc_short_kN": phiVc_short / 1000.0,
                # long / short flexure
                "Mu_long_kNm": Mu_long / 1.0e6,
                "Mu_short_kNm": Mu_short / 1.0e6,
                "As_req_long": As_req_long if feas_long else None,
                "As_req_short": As_req_short if feas_short else None,
                "As_min_long": As_min_long, "As_min_short": As_min_short,
                "As_prov_long": As_prov_long, "As_prov_short": As_prov_short,
                "size_long": size_long, "n_long": n_long,
                "s_long_cm": s_long / CM,
                "size_short": size_short, "n_short": n_short,
                "s_short_cm": s_short / CM,
                "s_max_cm": s_max / CM,
                "sp_long_ok": sp_long_ok, "sp_short_ok": sp_short_ok,
                "reaction_ok": reaction_ok,
                "uplift_ok": uplift_ok,
                "punch_ok": punch_ok,
                "pile_punch_ok": pile_punch_ok,
                "beam_long_ok": beam_long_ok, "beam_short_ok": beam_short_ok,
                "flex_long_ok": flex_long_ok, "flex_short_ok": flex_short_ok,
                "asmin_long_ok": asmin_long_ok, "asmin_short_ok": asmin_short_ok,
                "section_img": section_img,
                "status": "PASS",
            },
        )
        tag = f"F{n_piles}E" if is_eccentric else f"F{n_piles}"
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name=f"pile_cap_{tag}_report.pdf",
            mime="application/pdf",
        )
    else:
        st.error(f"{FAIL_TXT} — มีรายการที่ไม่ผ่าน โปรดตรวจสอบตารางด้านบน")
    st.caption("หมายเหตุ: โมดูลฐานเสาเข็มเป็นการคำนวณเบื้องต้นตาม ACI 318M-08")


# ===========================================================================
# Tab 3 — ฐานเสาเข็มเยื้องศูนย์ (eccentric pile caps)
# ===========================================================================


ECC_LABELS = {k: f"F{k}E Pile Cap ({k} ต้น)" for k in range(1, 10)}


def _tab_eccentric():
    choice = st.selectbox(
        "ประเภทฐานเสาเข็มเยื้องศูนย์",
        list(ECC_LABELS.values()),
        index=1,                       # default F2E
        key="ecc_type",
    )
    n = next(k for k, v in ECC_LABELS.items() if v == choice)
    _render_pile_cap(n, f"pce{n}", is_eccentric=True)


if __name__ == "__main__":
    render_footing_module()
