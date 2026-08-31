"""Streamlit UI — RC beam flexural design to ACI 318M-08. Thai UI, cm / cm² display.

Singly-reinforced rectangular section: required tension steel vs. provided.
UI inputs are in cm; converted to mm internally for the ACI calculations.
"""

import math

import streamlit as st

from utils.aci_318m import phi, rebars, get_beta1, calc_As_min, bar_area, vc_beam
from utils.drawing import draw_rc_section, draw_beam_3_sect
from utils.project import get_project_info
from reports.pdf_generator import (
    generate_beam_report,
    generate_beam_3_sect_report,
    FONT_AVAILABLE,
    font_status_message,
)

STIRRUP_DIA = 10.0        # mm, assumed closed stirrups
CM = 10.0                # cm -> mm
KSC_TO_MPA = 0.0980665   # ksc (kgf/cm^2) -> MPa (N/mm^2)
KGF_TO_KN = 9.80665 / 1000.0   # kgf -> kN  (also kgf-m -> kN.m)
KN_TO_KGF = 1000.0 / 9.80665   # kN  -> kgf (also kN.m -> kgf-m)
LAMBDA = 1.0             # normal-weight concrete
TOP_BOT_SIZES = [s for s in rebars.keys() if s.startswith("DB")]   # DB12 .. DB32
STIRRUP_SIZES = ["RB9", "RB6", "DB10", "DB12"]

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


BEAM_TYPES = [
    "Beam Section (หน้าตัดคาน)",
    "Beam Span (คาน 1 ช่วง)",
    "Continuous Beam (คานต่อเนื่อง)",
    "Beam 3 Sect (คาน 3 หน้าตัด)",
    "Cantilever Beam (คานยื่น)",
]

UNDER_CONSTRUCTION = "กำลังอยู่ระหว่างการพัฒนา (Under Construction)"


def render_beam_module():
    beam_type = st.selectbox("เลือกประเภทคาน (Beam Type)", BEAM_TYPES,
                             key="beam_type")
    if beam_type == "Beam Section (หน้าตัดคาน)":
        _render_beam_section()
    elif beam_type == "Beam 3 Sect (คาน 3 หน้าตัด)":
        _render_beam_3_sect()
    else:
        st.info(UNDER_CONSTRUCTION)


def _shear_check(Vu_kN, b, d, fc, fy, stirrup_size, s_mm):
    """phiVc + phiVs vs Vu for a 2-leg stirrup at spacing s_mm."""
    Vu = Vu_kN * 1000.0                                # N
    Vc = vc_beam(fc, b, d, LAMBDA)                     # N
    phi_v = phi["shear"]
    phiVc = phi_v * Vc
    Av = 2.0 * bar_area(stirrup_size)                  # 2-leg stirrup, mm²
    Vs = (Av * fy * d / s_mm) if s_mm > 0 else 0.0     # N
    Vs_max = 0.66 * math.sqrt(fc) * b * d              # N  (ACI 318M-08 11.4.7.9)
    phiVs = phi_v * min(Vs, Vs_max)
    phiVn = phiVc + phiVs
    s_max = min(d / 2.0, 600.0)
    if Vs > 0.33 * math.sqrt(fc) * b * d:
        s_max = min(d / 4.0, 300.0)
    ok = (phiVn >= Vu) and (Vs <= Vs_max) and (s_mm <= s_max)
    return {
        "Vu": Vu, "phiVc": phiVc, "Vs": Vs, "Vs_max": Vs_max,
        "phiVs": phiVs, "phiVn": phiVn, "s_max": s_max, "ok": ok,
    }


def _section_calc(sec_in, b, h, covering, fc, fy):
    """Full flexure (top/bottom) + shear check for one beam section."""
    top_dia = float(sec_in["top_size"][2:])
    bot_dia = float(sec_in["bot_size"][2:])
    stir_dia = float(sec_in["stirrup_size"][2:])

    d_top = max(h - covering - stir_dia - top_dia / 2.0, 1.0)
    d_bot = max(h - covering - stir_dia - bot_dia / 2.0, 1.0)

    As_top_req, Rn_top, _rt, feas_top = _required_as(sec_in["Mu_top"], b, d_top, fc, fy)
    As_bot_req, Rn_bot, _rb, feas_bot = _required_as(sec_in["Mu_bot"], b, d_bot, fc, fy)
    As_min = calc_As_min(fc, fy, b, d_bot)

    As_top_prov = sec_in["top_qty"] * bar_area(sec_in["top_size"])
    As_bot_prov = sec_in["bot_qty"] * bar_area(sec_in["bot_size"])

    top_req_ok = feas_top and As_top_prov >= As_top_req
    bot_req_ok = feas_bot and As_bot_prov >= As_bot_req
    top_min_ok = As_top_prov >= As_min
    bot_min_ok = As_bot_prov >= As_min

    sh = _shear_check(sec_in["Vu"], b, d_bot, fc, fy,
                      sec_in["stirrup_size"], sec_in["stirrup_sp_cm"] * CM)

    passed = (top_req_ok and bot_req_ok and top_min_ok and bot_min_ok
              and sh["ok"])

    return {
        "label": sec_in["label"],
        "d_top": d_top, "d_bot": d_bot,
        "As_top_req": As_top_req if feas_top else None,
        "As_bot_req": As_bot_req if feas_bot else None,
        "As_min": As_min,
        "As_top_prov": As_top_prov, "As_bot_prov": As_bot_prov,
        "feas_top": feas_top, "feas_bot": feas_bot,
        "top_req_ok": top_req_ok, "bot_req_ok": bot_req_ok,
        "top_min_ok": top_min_ok, "bot_min_ok": bot_min_ok,
        "Vu_kN": sec_in["Vu"],
        "phiVc_kN": sh["phiVc"] / 1000.0,
        "phiVs_kN": sh["phiVs"] / 1000.0,
        "phiVn_kN": sh["phiVn"] / 1000.0,
        "Vs_max_kN": sh["Vs_max"] / 1000.0,
        "s_max_mm": sh["s_max"],
        "shear_ok": sh["ok"],
        "passed": passed,
        "Mu_top": sec_in["Mu_top"], "Mu_bot": sec_in["Mu_bot"],
        "top_size": sec_in["top_size"], "top_qty": sec_in["top_qty"],
        "bot_size": sec_in["bot_size"], "bot_qty": sec_in["bot_qty"],
        "stirrup_size": sec_in["stirrup_size"],
        "stirrup_sp_cm": sec_in["stirrup_sp_cm"],
        "top_dia": top_dia, "bot_dia": bot_dia, "stir_dia": stir_dia,
    }


def _render_beam_3_sect():
    st.title("การออกแบบคาน 3 หน้าตัด (Beam 3 Sections)")
    st.caption("ตรวจสอบหน้าตัดวิกฤต 3 ตำแหน่ง: ริมซ้าย · กลางช่วง · ริมขวา — "
               "เหล็กบน / เหล็กล่าง และแรงเฉือน ตามมาตรฐาน ACI 318M-08")

    # ------------------------------------------------------------------
    # Global beam properties
    # ------------------------------------------------------------------
    st.subheader("คุณสมบัติคานทั่วไป")
    g1, g2, g3 = st.columns(3)
    with g1:
        b_cm = st.number_input("ความกว้างคาน b (cm)", min_value=15.0, value=30.0,
                               step=0.5, format="%.1f", key="b3_b")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d", key="b3_fc")
    with g2:
        h_cm = st.number_input("ความลึกคาน h (cm)", min_value=25.0, value=50.0,
                               step=0.5, format="%.1f", key="b3_h")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d", key="b3_fy")
    with g3:
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=2.0,
                                      value=4.0, step=0.5, format="%.1f",
                                      key="b3_cov")

    b = b_cm * CM
    h = h_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA

    # ------------------------------------------------------------------
    # Section-specific inputs — 3 columns
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลรายหน้าตัด")
    cols = st.columns(3)
    meta = [
        ("Left Support (ริมซ้าย)", "L",
         dict(mt=9000.0, mb=0.0, vu=12000.0, tq=4, bq=3, ssp=10.0)),
        ("Mid Span (กลางช่วง)", "M",
         dict(mt=0.0, mb=11000.0, vu=3500.0, tq=3, bq=4, ssp=20.0)),
        ("Right Support (ริมขวา)", "R",
         dict(mt=9000.0, mb=0.0, vu=12000.0, tq=4, bq=3, ssp=10.0)),
    ]
    sec_inputs = []
    for col, (label, k, dfl) in zip(cols, meta):
        with col:
            st.markdown(f"**{label}**")
            mt = st.number_input("Mu⁻ เหล็กบน (kgf-m)", min_value=0.0,
                                 value=dfl["mt"], step=100.0, key=f"b3_{k}_mt")
            mb = st.number_input("Mu⁺ เหล็กล่าง (kgf-m)", min_value=0.0,
                                 value=dfl["mb"], step=100.0, key=f"b3_{k}_mb")
            vu = st.number_input("Vu (kgf)", min_value=0.0, value=dfl["vu"],
                                 step=100.0, key=f"b3_{k}_vu")
            ts = st.selectbox("เหล็กบน — ขนาด", TOP_BOT_SIZES, index=1,
                              key=f"b3_{k}_ts")
            tq = int(st.number_input("เหล็กบน — จำนวน", min_value=2, max_value=12,
                                     value=dfl["tq"], step=1, key=f"b3_{k}_tq"))
            bs = st.selectbox("เหล็กล่าง — ขนาด", TOP_BOT_SIZES, index=1,
                              key=f"b3_{k}_bs")
            bq = int(st.number_input("เหล็กล่าง — จำนวน", min_value=2,
                                     max_value=12, value=dfl["bq"], step=1,
                                     key=f"b3_{k}_bq"))
            ss = st.selectbox("เหล็กปลอก — ขนาด", STIRRUP_SIZES, index=0,
                              key=f"b3_{k}_ss")
            ssp = st.number_input("เหล็กปลอก — ระยะเรียง (cm)", min_value=5.0,
                                  max_value=30.0, value=dfl["ssp"], step=1.0,
                                  format="%.1f", key=f"b3_{k}_ssp")
            sec_inputs.append(dict(
                label=label,
                Mu_top=mt * KGF_TO_KN, Mu_bot=mb * KGF_TO_KN, Vu=vu * KGF_TO_KN,
                top_size=ts, top_qty=tq, bot_size=bs, bot_qty=bq,
                stirrup_size=ss, stirrup_sp_cm=ssp,
            ))

    secs = [_section_calc(si, b, h, covering, fc, fy) for si in sec_inputs]

    # ------------------------------------------------------------------
    # Summary verdict table (3 sections x checks)
    # ------------------------------------------------------------------
    st.subheader("สรุปผลการตรวจสอบ 3 หน้าตัด")

    def _s(ok):
        return "✅" if ok else "❌"

    short = [s["label"].split(" (")[0] for s in secs]
    lines = ["| การตรวจสอบ | " + " | ".join(short) + " |",
             "|---|" + "---|" * len(secs)]
    check_rows = [
        ("เหล็กบน ≥ ที่ต้องการ", [s["top_req_ok"] for s in secs]),
        ("เหล็กล่าง ≥ ที่ต้องการ", [s["bot_req_ok"] for s in secs]),
        ("เหล็กบน ≥ As,min", [s["top_min_ok"] for s in secs]),
        ("เหล็กล่าง ≥ As,min", [s["bot_min_ok"] for s in secs]),
        ("แรงเฉือน φVn ≥ Vu", [s["shear_ok"] for s in secs]),
    ]
    for name, oks in check_rows:
        lines.append(f"| {name} | " + " | ".join(_s(o) for o in oks) + " |")
    lines.append("| **สรุปหน้าตัด** | "
                 + " | ".join(f"**{_s(s['passed'])}**" for s in secs) + " |")
    st.markdown("\n".join(lines))

    # ------------------------------------------------------------------
    # Per-section detail
    # ------------------------------------------------------------------
    for s in secs:
        with st.expander(s["label"], expanded=False):
            top_req = (f"{s['As_top_req'] / 100.0:,.2f}"
                       if s["As_top_req"] is not None else "—")
            bot_req = (f"{s['As_bot_req'] / 100.0:,.2f}"
                       if s["As_bot_req"] is not None else "—")
            st.markdown(
                f"""
| รายการ | ค่า |
|---|---|
| d (เหล็กบน) / d (เหล็กล่าง) | {s['d_top'] / CM:,.2f} / {s['d_bot'] / CM:,.2f} cm |
| As,min | {s['As_min'] / 100.0:,.2f} cm² |
| Mu⁻ = {s['Mu_top'] * KN_TO_KGF:,.0f} kgf-m → As บน ที่ต้องการ | **{top_req} cm²** |
| As บน ที่จัดให้ = {s['top_qty']} × {s['top_size']} | {s['As_top_prov'] / 100.0:,.2f} cm² |
| Mu⁺ = {s['Mu_bot'] * KN_TO_KGF:,.0f} kgf-m → As ล่าง ที่ต้องการ | **{bot_req} cm²** |
| As ล่าง ที่จัดให้ = {s['bot_qty']} × {s['bot_size']} | {s['As_bot_prov'] / 100.0:,.2f} cm² |
| Vu | {s['Vu_kN'] * KN_TO_KGF:,.0f} kgf |
| φVc | {s['phiVc_kN'] * KN_TO_KGF:,.0f} kgf |
| φVs ({s['stirrup_size']} @ {s['stirrup_sp_cm']:.0f} cm, 2 ขา) | {s['phiVs_kN'] * KN_TO_KGF:,.0f} kgf |
| φVn = φVc + φVs | **{s['phiVn_kN'] * KN_TO_KGF:,.0f} kgf** |
| ระยะเรียงปลอกสูงสุด | {s['s_max_mm'] / CM:,.1f} cm |
"""
            )

    # ------------------------------------------------------------------
    # Drawing — 3 cross-sections
    # ------------------------------------------------------------------
    def _rb(s):
        return dict(top_dia=s["top_dia"], top_qty=s["top_qty"],
                    bot_dia=s["bot_dia"], bot_qty=s["bot_qty"],
                    stirrup_dia=s["stir_dia"],
                    top_size=s.get("top_size"), bot_size=s.get("bot_size"),
                    stirrup_size=s.get("stirrup_size"),
                    stirrup_sp_cm=s.get("stirrup_sp_cm"))

    section_img = None
    try:
        section_img = draw_beam_3_sect(b, h, covering,
                                       _rb(secs[0]), _rb(secs[1]), _rb(secs[2]))
        st.image(section_img,
                 caption="รายละเอียดหน้าตัด 3 ตำแหน่ง (Section Detailing)")
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    # ------------------------------------------------------------------
    # Overall verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบรวม")
    overall = all(s["passed"] for s in secs)
    if overall:
        st.success(f"{PASS_TXT} — ผ่านการตรวจสอบครบทั้ง 3 หน้าตัด")

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_beam_3_sect_report(
            {
                "b": b, "h": h, "covering": covering, "fc": fc, "fy": fy,
                "project": get_project_info(),
            },
            {"sections": secs, "section_img": section_img, "status": "PASS"},
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="beam_3sect_report.pdf",
            mime="application/pdf",
        )
    else:
        bad = ", ".join(sh for sh, s in zip(short, secs) if not s["passed"])
        st.error(f"{FAIL_TXT} — หน้าตัดที่ไม่ผ่าน: {bad}")


def _render_beam_section():
    st.title("การออกแบบคาน")
    st.caption("การดัด — หน้าตัดสี่เหลี่ยมเสริมเหล็กรับแรงดึงอย่างเดียว "
               "ตามมาตรฐาน ACI 318M-08 (หน่วยเมตริก)")

    # ------------------------------------------------------------------
    # Inputs  (section dimensions in cm)
    # ------------------------------------------------------------------
    st.subheader("ข้อมูลป้อนเข้า")
    c1, c2, c3 = st.columns(3)
    with c1:
        Mu_kgfm = st.number_input("โมเมนต์ประลัย Mu (kgf-m)", min_value=0.0,
                                  value=15300.0, step=100.0)
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

    # MKS -> SI for the ACI calculation core
    b = b_cm * CM
    h = h_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA
    Mu = Mu_kgfm * KGF_TO_KN                     # kgf-m -> kN.m

    # ------------------------------------------------------------------
    # Reinforcement selection
    # ------------------------------------------------------------------
    st.subheader("เหล็กเสริม")
    r1, r2 = st.columns(2)
    with r1:
        rebar_size = st.selectbox("ขนาดเหล็กเสริม", TOP_BOT_SIZES,
                                  index=TOP_BOT_SIZES.index("DB20"))
    with r2:
        qty = st.selectbox("จำนวนเส้น", list(range(2, 13)), index=1)

    rebar_dia = float(rebar_size[2:])
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
| Mu | {Mu * KN_TO_KGF:,.0f} kgf-m |
| Rn = Mu / (φ·b·d²) | {Rn / KSC_TO_MPA:,.1f} ksc |
"""
    )

    # ------------------------------------------------------------------
    # Visual detailing (b, h, covering are already in mm)
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_rc_section(
            b, h, covering, rebar_dia, qty, section_type="beam",
            bar_label=f"{qty} - {rebar_size}",
            stirrup_label=f"ปลอก Ø{STIRRUP_DIA:.0f} mm")
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
