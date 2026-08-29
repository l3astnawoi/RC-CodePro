"""Streamlit UI — Footing design (ACI 318M-08). Thai UI, tabbed interface.

Tabs
----
1. ฐานรากแผ่          — shallow foundations (Isolated Footing implemented;
                        Wall / 2C / Combined / Strap: under construction)
2. ฐานเสาเข็ม          — pile caps (F2 and F4 implemented; F1 / F3 / F5-F9:
                        under construction)
3. ฐานเสาเข็มเยื้องศูนย์ — eccentric pile caps (under construction)

UI units (all tabs use the same boundary conversions):
    axial loads      -> ตัน           (x 9.80665 -> kN)
    section sizes    -> cm            (x 10       -> mm)
    strengths f'c/fy -> ksc           (x 0.0980665 -> MPa)
    soil bearing q_a -> ตัน/ตารางเมตร (x 9.80665 -> kN/m2)
The ACI calculation core works in mm / kN / N / N·mm / MPa.
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
KSC_TO_MPA = 0.0980665  # ksc (kgf/cm^2) -> MPa (N/mm^2)

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
        P_ton = st.number_input("น้ำหนักบรรทุกตามแนวแกนใช้งาน P (ตัน)",
                                min_value=0.0, value=90.0, step=0.01,
                                format="%.2f")
        c_cm = st.number_input("ขนาดเสาสี่เหลี่ยมจัตุรัส c (cm)", min_value=15.0,
                               value=40.0, step=0.01, format="%.2f")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d")
    with c2:
        Pu_ton = st.number_input("น้ำหนักบรรทุกตามแนวแกนประลัย Pu (ตัน)",
                                 min_value=0.0, value=125.0, step=0.01,
                                 format="%.2f")
        B_cm = st.number_input("ความกว้างฐานราก B (cm, สี่เหลี่ยมจัตุรัส)",
                               min_value=50.0, value=240.0, step=0.01,
                               format="%.2f")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d")
    with c3:
        q_a_ton = st.number_input("กำลังแบกทานดินที่ยอมให้ qa (ตัน/ตารางเมตร)",
                                  min_value=5.0, value=20.0, step=1.0,
                                  format="%.2f")
        h_cm = st.number_input("ความหนาฐานราก h (cm)", min_value=25.0,
                               value=55.0, step=0.01, format="%.2f")
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=4.0,
                                      value=7.5, step=0.01, format="%.2f")

    # Unit conversions -> ACI calculation core (kN, kN/m2, mm, MPa)
    P = P_ton * TON_TO_KN
    Pu = Pu_ton * TON_TO_KN
    q_a = q_a_ton * TON_TO_KN
    c = c_cm * CM
    B = B_cm * CM
    h = h_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA

    # ------------------------------------------------------------------
    # Reinforcement
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม (ต่อทิศทาง)")
    r1, r2 = st.columns(2)
    with r1:
        main_size = st.selectbox("ขนาดเหล็กเสริมหลัก", list(rebars.keys()),
                                 index=list(rebars).index("DB16"))
    with r2:
        qty = st.selectbox("จำนวนเส้น (ต่อทิศทาง)",
                           list(range(5, 41)), index=5)

    bar_area = rebars[main_size]
    db = float(main_size.replace("DB", ""))
    As_prov = qty * bar_area

    # ------------------------------------------------------------------
    # Geometry guards
    # ------------------------------------------------------------------
    if B <= c:
        st.error("ความกว้างฐานราก B ต้องมากกว่าขนาดเสา c")
        return

    d = h - covering - db
    if d <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบความหนา ระยะหุ้ม "
                 "หรือขนาดเหล็กเสริม")
        return

    # ------------------------------------------------------------------
    # 1. Soil bearing  (service loads)
    # ------------------------------------------------------------------
    B_m = B / 1000.0
    q_applied = P / (B_m ** 2)                         # kN/m²
    bearing_ok = q_applied <= q_a

    # Net factored soil pressure for structural checks
    Pu_N = Pu * 1000.0
    qu = Pu_N / (B * B)                                # N/mm² (= MPa)
    qu_kPa = qu * 1.0e6 / 1.0e3                        # kN/m²  (= qu * 1000)

    # ------------------------------------------------------------------
    # 2. Two-way (punching) shear — critical section d/2 from column face
    # ------------------------------------------------------------------
    bo = 4.0 * (c + d)                                 # mm
    Ap_in = min((c + d) ** 2, B * B)                   # mm² inside perimeter
    Vup = qu * (B * B - Ap_in)                         # N
    beta_c = 1.0                                       # square column
    vc1 = 0.17 * (1.0 + 2.0 / beta_c) * LAMBDA * math.sqrt(fc)
    vc2 = 0.083 * (ALPHA_S * d / bo + 2.0) * LAMBDA * math.sqrt(fc)
    vc3 = 0.33 * LAMBDA * math.sqrt(fc)
    vc_punch = min(vc1, vc2, vc3)                      # MPa
    Vc_punch = vc_punch * bo * d                       # N
    phiVc_punch = phi["shear"] * Vc_punch             # N
    punch_ok = Vup <= phiVc_punch

    # ------------------------------------------------------------------
    # 3. One-way (beam) shear — critical section d from column face
    # ------------------------------------------------------------------
    av = (B - c) / 2.0 - d                             # mm cantilever beyond section
    av = max(av, 0.0)
    Vub = qu * B * av                                  # N
    Vc_beam = 0.17 * LAMBDA * math.sqrt(fc) * B * d    # N
    phiVc_beam = phi["shear"] * Vc_beam               # N
    beam_ok = Vub <= phiVc_beam

    # ------------------------------------------------------------------
    # 4. Flexure — moment at column face
    # ------------------------------------------------------------------
    Lc = (B - c) / 2.0                                 # mm cantilever
    Mu_f = qu * B * Lc ** 2 / 2.0                      # N·mm  (full width strip)
    phi_f = phi["flexure"]
    Rn = Mu_f / (phi_f * B * d ** 2)                   # MPa
    disc = 1.0 - 2.0 * Rn / (0.85 * fc)
    feasible = disc >= 0.0
    if feasible:
        rho = (0.85 * fc / fy) * (1.0 - math.sqrt(disc))
        As_req = rho * B * d                           # mm² (each direction)
    else:
        rho = None
        As_req = float("inf")

    # ------------------------------------------------------------------
    # 5. Minimum steel (shrinkage / temperature on gross section)
    # ------------------------------------------------------------------
    temp_ratio = _temp_steel_ratio(fy)
    As_min = temp_ratio * B * h                        # mm²
    As_design = max(As_req, As_min) if feasible else float("inf")

    flexure_ok = feasible and As_prov >= As_req
    as_min_ok = As_prov >= As_min

    passed = (bearing_ok and beam_ok and punch_ok
              and flexure_ok and as_min_ok)

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| น้ำหนักบรรทุกใช้งาน P | {P_ton:,.2f} ตัน ({P:,.1f} kN) |
| น้ำหนักบรรทุกประลัย Pu | {Pu_ton:,.2f} ตัน ({Pu:,.1f} kN) |
| ความลึกประสิทธิผล d = h − covering − db | **{d / CM:,.2f} cm** |
| พื้นที่ฐานรากในแปลน B² | {B_m ** 2:,.3f} m² |
| หน่วยแรงดินที่เกิดขึ้น (ใช้งาน) q = P / B² | **{q_applied / TON_TO_KN:,.2f} ตัน/ตร.ม.** |
| หน่วยแรงดินที่ยอมให้ qa | {q_a_ton:,.2f} ตัน/ตร.ม. |
| หน่วยแรงดินประลัยสุทธิ qu = Pu / B² | {qu_kPa:,.1f} kN/m² |
"""
    )

    st.markdown("**แรงเฉือนทะลุ (สองทาง)** — หน้าตัดวิกฤตที่ระยะ d/2 จากผิวเสา")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| เส้นรอบรูปวิกฤต b₀ = 4(c + d) | {bo:,.0f} mm |
| Vu,punch = qu·(B² − (c+d)²) | {Vup / 1000.0:,.1f} kN |
| vc = min(0.17(1+2/β), 0.083(α_s·d/b₀+2), 0.33)·√f'c | {vc_punch:,.3f} MPa |
| φVc = 0.75·vc·b₀·d | **{phiVc_punch / 1000.0:,.1f} kN** |
"""
    )

    st.markdown("**แรงเฉือนคาน (ทางเดียว)** — หน้าตัดวิกฤตที่ระยะ d จากผิวเสา")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| ระยะยื่นเลยหน้าตัด av = (B−c)/2 − d | {av / CM:,.2f} cm |
| Vu,beam = qu·B·av | {Vub / 1000.0:,.1f} kN |
| Vc = 0.17·√f'c·B·d | {Vc_beam / 1000.0:,.1f} kN |
| φVc = 0.75·Vc | **{phiVc_beam / 1000.0:,.1f} kN** |
"""
    )

    st.markdown("**การดัด** — โมเมนต์ที่ผิวเสา")
    if feasible:
        st.markdown(
            f"""
| รายการ | ค่า |
|---|---|
| ความยาวยื่น Lc = (B − c)/2 | {Lc / CM:,.2f} cm |
| Mu = qu·B·Lc²/2 | {Mu_f / 1.0e6:,.2f} kN·m |
| Rn = Mu / (φ·B·d²) | {Rn:,.4f} MPa |
| ρ | {rho:.5f} |
| As ที่ต้องการ (การดัด) | **{As_req / 100.0:,.2f} cm²** |
| อัตราส่วนเหล็กกันร้าว/อุณหภูมิ (fy = {fy_ksc:,.0f} ksc) | {temp_ratio:.4f} |
| As,min = ratio·B·h | {As_min / 100.0:,.2f} cm² |
| As ที่ต้องการที่ควบคุม | **{As_design / 100.0:,.2f} cm²** |
| As ที่จัดให้ = {qty} × {main_size} ({bar_area / 100.0:,.2f} cm²) | **{As_prov / 100.0:,.2f} cm²** |
"""
        )
    else:
        st.error("ฐานรากบางเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว "
                 "(1 − 2Rn/0.85f'c < 0) — เพิ่ม h หรือ f'c")

    # ------------------------------------------------------------------
    # Checks summary
    # ------------------------------------------------------------------
    st.subheader("การตรวจสอบการออกแบบ")

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    as_req_cell = f"{As_req / 100.0:,.2f}" if feasible else "—"
    st.markdown(
        f"""
| การตรวจสอบ | แรงที่กระทำ | กำลังต้านทาน / ขีดจำกัด | สถานะ |
|---|---|---|---|
| กำลังแบกทานดิน (ใช้งาน) | q = {q_applied / TON_TO_KN:,.2f} ตัน/ตร.ม. | qa = {q_a_ton:,.2f} ตัน/ตร.ม. | {_s(bearing_ok)} |
| แรงเฉือนคาน (ทางเดียว) | Vu = {Vub / 1000.0:,.1f} kN | φVc = {phiVc_beam / 1000.0:,.1f} kN | {_s(beam_ok)} |
| แรงเฉือนทะลุ (สองทาง) | Vu = {Vup / 1000.0:,.1f} kN | φVc = {phiVc_punch / 1000.0:,.1f} kN | {_s(punch_ok)} |
| การดัด | As,req = {as_req_cell} cm² | As,prov = {As_prov / 100.0:,.2f} cm² | {_s(flexure_ok)} |
| เหล็กเสริมขั้นต่ำ | As,min = {As_min / 100.0:,.2f} cm² | As,prov = {As_prov / 100.0:,.2f} cm² | {_s(as_min_ok)} |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing — plan view (B, c, covering are already in mm)
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_footing_plan(B, c, covering, qty)
        st.image(section_img, caption="รายละเอียดหน้าตัด (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    if passed:
        st.success(
            f"{PASS_TXT} — ผ่านทุกการตรวจสอบ: กำลังแบกทานดิน แรงเฉือนทางเดียว "
            f"แรงเฉือนสองทาง การดัด และเหล็กเสริมขั้นต่ำ"
        )

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_footing_report(
            {
                "P": P, "Pu": Pu, "q_a": q_a, "c": c, "B": B, "h": h,
                "covering": covering, "fc": fc, "fy": fy,
                "project": get_project_info(),
            },
            {
                "d": d,
                "q_applied": q_applied,
                "q_a": q_a,
                "qu_kPa": qu_kPa,
                "Vup_kN": Vup / 1000.0,
                "phiVc_punch_kN": phiVc_punch / 1000.0,
                "Vub_kN": Vub / 1000.0,
                "phiVc_beam_kN": phiVc_beam / 1000.0,
                "Mu_face": Mu_f / 1.0e6,
                "As_req": As_req,
                "As_min": As_min,
                "main_size": main_size,
                "qty": qty,
                "As_prov": As_prov,
                "bearing_ok": bearing_ok,
                "beam_ok": beam_ok,
                "punch_ok": punch_ok,
                "flexure_ok": flexure_ok,
                "as_min_ok": as_min_ok,
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
                f"กำลังแบกทานดิน (q = {q_applied / TON_TO_KN:,.2f} > "
                f"qa = {q_a_ton:,.2f} ตัน/ตร.ม.)"
            )
        if not beam_ok:
            failed.append(
                f"แรงเฉือนทางเดียว (Vu = {Vub / 1000.0:,.1f} > "
                f"φVc = {phiVc_beam / 1000.0:,.1f} kN)"
            )
        if not punch_ok:
            failed.append(
                f"แรงเฉือนสองทาง (Vu = {Vup / 1000.0:,.1f} > "
                f"φVc = {phiVc_punch / 1000.0:,.1f} kN)"
            )
        if not flexure_ok:
            if feasible:
                failed.append(
                    f"การดัด (As,prov = {As_prov / 100.0:,.2f} < "
                    f"As,req = {As_req / 100.0:,.2f} cm²)"
                )
            else:
                failed.append("การดัด (หน้าตัดบางเกินไปสำหรับการเสริมเหล็กรับแรงดึงอย่างเดียว)")
        if not as_min_ok:
            failed.append(
                f"เหล็กเสริมขั้นต่ำ (As,prov = {As_prov / 100.0:,.2f} < "
                f"As,min = {As_min / 100.0:,.2f} cm²)"
            )
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
        P_ton = st.number_input("น้ำหนักบรรทุกตามแนวแกนใช้งาน P (ตัน)",
                                min_value=0.0, value=80.0, step=0.01,
                                format="%.2f", key=f"{kp}_P")
        pile_cap_ton = st.number_input("กำลังรับน้ำหนักปลอดภัยของเสาเข็ม (ตัน/ต้น)",
                                       min_value=1.0, value=50.0, step=1.0,
                                       format="%.2f", key=f"{kp}_pcap")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d", key=f"{kp}_fc")
    with c2:
        Pu_ton = st.number_input("น้ำหนักบรรทุกตามแนวแกนประลัย Pu (ตัน)",
                                 min_value=0.0, value=105.0, step=0.01,
                                 format="%.2f", key=f"{kp}_Pu")
        pile_size_cm = st.number_input("ขนาด/เส้นผ่านศูนย์กลางเสาเข็ม (cm)",
                                       min_value=15.0, value=30.0, step=0.01,
                                       format="%.2f", key=f"{kp}_pile")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d", key=f"{kp}_fy")
    with c3:
        c_cm = st.number_input("ขนาดเสาสี่เหลี่ยมจัตุรัส c (cm)", min_value=15.0,
                               value=40.0, step=0.01, format="%.2f", key=f"{kp}_c")
        h_cm = st.number_input("ความหนาฐานราก h (cm)", min_value=30.0,
                               value=60.0, step=0.01, format="%.2f", key=f"{kp}_h")
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=5.0,
                                      value=7.5, step=0.01, format="%.2f",
                                      key=f"{kp}_cov")

    ex_cm = ey_cm = 0.0
    if is_eccentric:
        e1, e2 = st.columns(2)
        with e1:
            ex_cm = st.number_input("ระยะเยื้องศูนย์ของเสา ex (cm)",
                                    value=0.0, step=1.0, format="%.2f",
                                    key=f"{kp}_ex")
        with e2:
            ey_cm = st.number_input("ระยะเยื้องศูนย์ของเสา ey (cm)",
                                    value=0.0, step=1.0, format="%.2f",
                                    key=f"{kp}_ey")

    st.subheader("เหล็กเสริม (ต่อทิศทาง)")
    r1, r2 = st.columns(2)
    with r1:
        main_size = st.selectbox("ขนาดเหล็กเสริมหลัก", list(rebars.keys()),
                                 index=list(rebars).index("DB16"),
                                 key=f"{kp}_bar")
    with r2:
        qty = st.selectbox("จำนวนเส้น (ต่อทิศทาง)", list(range(5, 41)),
                           index=7, key=f"{kp}_qty")

    # ---- Unit conversions -> ACI calculation core ----
    P = P_ton * TON_TO_KN                    # kN
    Pu = Pu_ton * TON_TO_KN                  # kN
    pile_cap_kN = pile_cap_ton * TON_TO_KN   # kN
    Dp = pile_size_cm * CM                   # mm
    c = c_cm * CM                            # mm
    h = h_cm * CM                            # mm
    covering = covering_cm * CM              # mm
    fc = fc_ksc * KSC_TO_MPA                 # MPa
    fy = fy_ksc * KSC_TO_MPA                 # MPa
    ex_mm = ex_cm * CM                       # mm
    ey_mm = ey_cm * CM                       # mm

    bar_area = rebars[main_size]
    db = float(main_size.replace("DB", ""))
    As_prov = qty * bar_area

    d = h - covering - db                    # mm
    if d <= 0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบความหนา ระยะหุ้ม "
                 "หรือขนาดเหล็กเสริม")
        return

    Pu_N = Pu * 1000.0                                 # N

    # ------------------------------------------------------------------
    # 1. Pile spacing (3 x pile size) and edge distance
    # ------------------------------------------------------------------
    S = 3.0 * Dp                                       # mm centre-to-centre
    edge = 0.5 * Dp + max(covering, 150.0)             # pile centre -> cap edge

    # ------------------------------------------------------------------
    # 2. Base pile coordinates (relative to the pile-group centroid)
    #    and elastic reaction distribution for column eccentricity.
    # ------------------------------------------------------------------
    base_piles_c = _pile_coords(n_piles, S)
    sum_x2 = sum(px * px for (px, py) in base_piles_c)
    sum_y2 = sum(py * py for (px, py) in base_piles_c)

    def _reactions(load):
        """Per-pile reaction for a total axial `load`
        (R = load/n + load·e·coord / Σcoord²)."""
        out = []
        for (px, py) in base_piles_c:
            r = load / n_piles
            if sum_x2 > 0.0:
                r += load * ex_mm * px / sum_x2
            if sum_y2 > 0.0:
                r += load * ey_mm * py / sum_y2
            out.append(r)
        return out

    R_list = _reactions(P)                             # kN / pile (service)
    Ru_list_N = _reactions(Pu_N)                       # N  / pile (factored)

    R_serv = P / n_piles                               # kN — group average
    R_max = max(R_list)                                # kN — governing pile
    reaction_ok = R_max <= pile_cap_kN

    Ru_N = Pu_N / n_piles                              # N — group average
    Ru_max_N = max(Ru_list_N)                          # N — governing pile

    # ------------------------------------------------------------------
    # 3. Coordinates relative to the (eccentric) column at (0, 0)
    #    + dynamic cap plan dimensions
    # ------------------------------------------------------------------
    piles_c_col = [(px - ex_mm, py - ey_mm) for (px, py) in base_piles_c]
    piles_eval = list(zip(piles_c_col, Ru_list_N))     # (coord, Ru_i[N])

    if is_eccentric:
        xs = [x for (x, y) in piles_c_col]
        ys = [y for (x, y) in piles_c_col]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cap_W = max((max_x - min_x) + 2.0 * edge, c + 200.0)
        cap_L = max((max_y - min_y) + 2.0 * edge, c + 200.0)
        col_center_x = 0.0 - min_x + edge
        col_center_y = 0.0 - min_y + edge
        piles_xy = [(x - min_x + edge, y - min_y + edge)
                    for (x, y) in piles_c_col]
        col_pos = (col_center_x, col_center_y)
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

    # ------------------------------------------------------------------
    # 4. Two-way (punching) shear around the column — section at d/2
    #    Relief = factored reaction of every pile inside the perimeter.
    # ------------------------------------------------------------------
    half = c / 2.0 + d / 2.0
    n_inside = sum(1 for ((px, py), _ru) in piles_eval
                   if abs(px) <= half and abs(py) <= half)
    Vup = Pu_N - sum(ru for ((px, py), ru) in piles_eval
                     if abs(px) <= half and abs(py) <= half)   # N
    bo = 4.0 * (c + d)                                 # mm
    vc1 = 0.17 * (1.0 + 2.0 / 1.0) * LAMBDA * math.sqrt(fc)
    vc2 = 0.083 * (ALPHA_S * d / bo + 2.0) * LAMBDA * math.sqrt(fc)
    vc3 = 0.33 * LAMBDA * math.sqrt(fc)
    vc_punch = min(vc1, vc2, vc3)                      # MPa
    phiVc_punch = phi["shear"] * vc_punch * bo * d     # N
    punch_ok = Vup <= phiVc_punch

    # 4b. Punching of one pile head through the cap (governing pile)
    bo_pile = math.pi * (Dp + d)                       # mm
    phiVc_pile = phi["shear"] * 0.33 * LAMBDA * math.sqrt(fc) * bo_pile * d
    pile_punch_ok = Ru_max_N <= phiVc_pile

    # ------------------------------------------------------------------
    # 5-6. One-way shear + flexure — evaluate each of the four sides with
    #      the specific Ru_i of every pile; take the governing side (max
    #      shear force / max moment about the column face).
    # ------------------------------------------------------------------
    face = c / 2.0
    sec_beam = c / 2.0 + d

    def _side(sign, axis):
        """(moment_at_face[N.mm], shear_beyond_d[N], n_beyond_d, n_beyond_face)."""
        m = 0.0
        v = 0.0
        n_d = 0
        n_face = 0
        for ((px, py), ru) in piles_eval:
            coord = sign * (px if axis == 0 else py)
            if coord > sec_beam + 1.0e-6:
                v += ru
                n_d += 1
            arm = coord - face
            if arm > 1.0e-6:
                m += ru * arm
                n_face += 1
        return m, v, n_d, n_face

    sides = [_side(s, a) for a in (0, 1) for s in (1.0, -1.0)]
    gov_m = max(sides, key=lambda e: e[0])            # governing moment side
    gov_v = max(sides, key=lambda e: e[1])            # governing shear side
    Mu_f = gov_m[0]                                    # N·mm
    n_flex = gov_m[3]
    Vub = gov_v[1]                                     # N
    n_beyond = gov_v[2]

    # Conservative effective width (perpendicular dimension)
    b_eff = min(cap_W, cap_L)                          # mm
    bw = b_eff
    phiVc_beam = phi["shear"] * 0.17 * LAMBDA * math.sqrt(fc) * bw * d
    beam_ok = Vub <= phiVc_beam

    phi_f = phi["flexure"]
    bflex = b_eff                                      # mm
    if Mu_f > 0.0:
        Rn = Mu_f / (phi_f * bflex * d ** 2)
        disc = 1.0 - 2.0 * Rn / (0.85 * fc)
    else:
        Rn = 0.0
        disc = 1.0
    feasible = disc >= 0.0
    if feasible and Mu_f > 0.0:
        rho = (0.85 * fc / fy) * (1.0 - math.sqrt(disc))
        As_req = rho * bflex * d
    else:
        rho = 0.0
        As_req = 0.0 if feasible else float("inf")

    temp_ratio = _temp_steel_ratio(fy)
    As_min = temp_ratio * bflex * h
    As_design = max(As_req, As_min) if feasible else float("inf")

    flexure_ok = feasible and As_prov >= As_req
    as_min_ok = As_prov >= As_min

    passed = (reaction_ok and punch_ok and pile_punch_ok
              and beam_ok and flexure_ok and as_min_ok)

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    ecc_rows = ""
    if is_eccentric and (ex_mm or ey_mm):
        ecc_rows = (f"| ระยะเยื้องศูนย์ ex, ey | {ex_cm:,.2f} , {ey_cm:,.2f} cm |\n"
                    f"| แรงในเสาเข็มสูงสุด Rmax = P/n + P·e·x/Σx² | "
                    f"**{R_max / TON_TO_KN:,.2f} ตัน/ต้น** |\n")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| จำนวนเสาเข็ม | {n_piles} ต้น |
| แรงในเสาเข็มเฉลี่ย (ใช้งาน) R = P / n | {R_serv / TON_TO_KN:,.2f} ตัน/ต้น |
| แรงในเสาเข็มสูงสุด (ใช้งาน) Rmax | **{R_max / TON_TO_KN:,.2f} ตัน/ต้น** |
| แรงในเสาเข็มสูงสุด (ประลัย) Ru,max | {Ru_max_N / 1000.0:,.1f} kN/ต้น |
{ecc_rows}| กำลังรับปลอดภัยของเสาเข็ม | {pile_cap_ton:,.2f} ตัน/ต้น |
| ระยะห่างเสาเข็ม S = 3·Dp | {S / CM:,.2f} cm |
| ระยะขอบ (ศูนย์กลางเข็มถึงขอบ) | {edge / CM:,.2f} cm |
| ขนาดฐานราก (กว้าง × ยาว) | {cap_W / CM:,.0f} × {cap_L / CM:,.0f} cm |
| ความลึกประสิทธิผล d = h − covering − db | **{d / CM:,.2f} cm** |
"""
    )

    st.markdown("**แรงเฉือนทะลุ (สองทาง)** — รอบเสา ที่ระยะ d/2")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| เส้นรอบรูปวิกฤต b₀ = 4(c + d) | {bo:,.0f} mm |
| เสาเข็มในเขตวิกฤต | {n_inside} ต้น |
| Vu = Pu − ΣRu(ใน) | {Vup / 1000.0:,.1f} kN |
| φVc = 0.75·vc·b₀·d | **{phiVc_punch / 1000.0:,.1f} kN** |
| แรงเฉือนทะลุหัวเข็ม Ru,max | {Ru_max_N / 1000.0:,.1f} kN |
| φVc (หัวเข็ม) = 0.75·0.33·√f'c·π(Dp+d)·d | **{phiVc_pile / 1000.0:,.1f} kN** |
"""
    )

    st.markdown("**แรงเฉือนคาน (ทางเดียว)** — ที่ระยะ d จากผิวเสา")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| เสาเข็มเลยหน้าตัด | {n_beyond} ต้น |
| Vu = n·Ru | {Vub / 1000.0:,.1f} kN |
| φVc = 0.75·0.17·√f'c·bw·d | **{phiVc_beam / 1000.0:,.1f} kN** |
"""
    )

    st.markdown("**การดัด** — โมเมนต์ที่ผิวเสา")
    if feasible:
        st.markdown(
            f"""
| รายการ | ค่า |
|---|---|
| Mu = ΣRu·(ระยะจากผิวเสา) | {Mu_f / 1.0e6:,.2f} kN·m |
| Rn = Mu / (φ·b·d²) | {Rn:,.4f} MPa |
| ρ | {rho:.5f} |
| As ที่ต้องการ (การดัด) | **{As_req / 100.0:,.2f} cm²** |
| As,min = ratio·b·h | {As_min / 100.0:,.2f} cm² |
| As ที่ต้องการที่ควบคุม | **{As_design / 100.0:,.2f} cm²** |
| As ที่จัดให้ = {qty} × {main_size} ({bar_area / 100.0:,.2f} cm²) | **{As_prov / 100.0:,.2f} cm²** |
"""
        )
    else:
        st.error("หน้าตัดบางเกินไปสำหรับการดัด (1 − 2Rn/0.85f'c < 0) — "
                 "เพิ่ม h หรือ f'c")

    # ------------------------------------------------------------------
    # Checks summary
    # ------------------------------------------------------------------
    st.subheader("การตรวจสอบการออกแบบ")

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    as_req_cell = f"{As_req / 100.0:,.2f}" if feasible else "—"
    st.markdown(
        f"""
| การตรวจสอบ | แรงที่กระทำ | กำลังต้านทาน / ขีดจำกัด | สถานะ |
|---|---|---|---|
| แรงในเสาเข็มสูงสุด ≤ กำลังปลอดภัย | Rmax = {R_max / TON_TO_KN:,.2f} ตัน/ต้น | {pile_cap_ton:,.2f} ตัน/ต้น | {_s(reaction_ok)} |
| แรงเฉือนทะลุ (สองทาง) | Vu = {Vup / 1000.0:,.1f} kN | φVc = {phiVc_punch / 1000.0:,.1f} kN | {_s(punch_ok)} |
| แรงเฉือนทะลุหัวเข็ม | Ru = {Ru_N / 1000.0:,.1f} kN | φVc = {phiVc_pile / 1000.0:,.1f} kN | {_s(pile_punch_ok)} |
| แรงเฉือนคาน (ทางเดียว) | Vu = {Vub / 1000.0:,.1f} kN | φVc = {phiVc_beam / 1000.0:,.1f} kN | {_s(beam_ok)} |
| การดัด | As,req = {as_req_cell} cm² | As,prov = {As_prov / 100.0:,.2f} cm² | {_s(flexure_ok)} |
| เหล็กเสริมขั้นต่ำ | As,min = {As_min / 100.0:,.2f} cm² | As,prov = {As_prov / 100.0:,.2f} cm² | {_s(as_min_ok)} |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing — plan view
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_pile_cap_plan(cap_W, cap_L, c, Dp, piles_xy,
                                         col_pos=col_pos)
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
                "P": P, "Pu": Pu, "pile_cap": pile_cap_kN, "n_piles": n_piles,
                "Dp": Dp, "c": c, "h": h, "covering": covering,
                "fc": fc, "fy": fy,
                "ex": ex_mm, "ey": ey_mm,
                "project": get_project_info(),
            },
            {
                "d": d,
                "R_serv": R_serv,
                "R_max": R_max,
                "Ru_kN": Ru_N / 1000.0,
                "Ru_max_kN": Ru_max_N / 1000.0,
                "S": S,
                "edge": edge,
                "cap_W": cap_W,
                "cap_L": cap_L,
                "n_inside": n_inside,
                "Vup_kN": Vup / 1000.0,
                "phiVc_punch_kN": phiVc_punch / 1000.0,
                "phiVc_pile_kN": phiVc_pile / 1000.0,
                "n_beyond": n_beyond,
                "Vub_kN": Vub / 1000.0,
                "phiVc_beam_kN": phiVc_beam / 1000.0,
                "Mu_face": Mu_f / 1.0e6,
                "As_req": As_req if feasible else None,
                "As_min": As_min,
                "main_size": main_size,
                "qty": qty,
                "As_prov": As_prov,
                "reaction_ok": reaction_ok,
                "punch_ok": punch_ok,
                "pile_punch_ok": pile_punch_ok,
                "beam_ok": beam_ok,
                "flexure_ok": flexure_ok,
                "as_min_ok": as_min_ok,
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
