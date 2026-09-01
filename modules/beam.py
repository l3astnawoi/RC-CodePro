"""Streamlit UI — RC beam design to ACI 318M-08. Thai UI.

* ``Beam Section`` — one rectangular section, flexure + shear, worked
  strictly in MKS units (cm / kgf / kgf-m / ksc).
* ``Beam 3 Sect`` — three critical sections (SI core, MKS display).
"""

import math

import streamlit as st

from utils.aci_318m import (phi, rebars, get_beta1, calc_As_min, bar_area,
                            vc_beam, as_min_flexure_ksc, vc_beam_ksc)
from utils.analysis import solve_continuous_beam
from utils.drawing import (draw_beam_detail, draw_beam_3_sect,
                           draw_beam_diagrams, fig_to_png_buf)
from utils.project import get_project_info, render_report_expander
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


def _beta1_ksc(fc_ksc):
    """Stress-block factor beta1 for f'c in ksc (ACI 318M-08 10.2.7.3, MKS
    form): 0.85 up to 280 ksc, then -0.05 per 70 ksc, floor 0.65."""
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def _rho_max_ksc(fc_ksc, fy_ksc):
    """Tension-controlled (net strain 0.005) reinforcement ratio, MKS."""
    return (0.85 * _beta1_ksc(fc_ksc) * fc_ksc / fy_ksc
            * 0.003 / (0.003 + 0.005))


def _flex_ksc(As_cm2, fy_ksc, fc_ksc, b_cm, d_cm):
    """Singly-reinforced flexural capacity of one steel layer, MKS.

    Returns ``(a_cm, Mn_kgfm, phiMn_kgfm)`` with phi = 0.90 (tension-
    controlled, ``phi['flexure']`` from utils.aci_318m).
    """
    a = As_cm2 * fy_ksc / (0.85 * fc_ksc * b_cm)          # cm
    Mn = As_cm2 * fy_ksc * (d_cm - a / 2.0) / 100.0       # kgf-m
    return a, Mn, phi["flexure"] * Mn


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
    """Dashboard layout — main visualisation / inputs on the left (3/4),
    a compact live design-results panel on the right (1/4)."""
    left, right = st.columns([3, 1], gap="large")

    with left:
        tab_an, tab_dsn = st.tabs(["📊 วิเคราะห์แรง (Analysis)",
                                   "🏗️ ออกแบบหน้าตัด (Design)"])
        with tab_an:
            _render_beam_analysis()
        with tab_dsn:
            beam_type = st.selectbox("เลือกประเภทคาน (Beam Type)", BEAM_TYPES,
                                     key="beam_type")
            if beam_type == "Beam Section (หน้าตัดคาน)":
                st.session_state["_beam_summary"] = _render_beam_section()
            elif beam_type == "Beam 3 Sect (คาน 3 หน้าตัด)":
                st.session_state["_beam_summary"] = _render_beam_3_sect()
            else:
                st.info(UNDER_CONSTRUCTION)
                st.session_state["_beam_summary"] = None

    with right:
        _render_design_sidecard(st.session_state.get("_beam_summary"))


# --- right-column design summary -------------------------------------------
_LBL = "#cbd5e1"        # muted label on dark
_OK = "#16a34a"
_BAD = "#dc2626"
_WARN = "#d97706"


def _util_row(label, ratio):
    """One 'demand / capacity' utilisation row: 'Ratio: 0.84 ✔️'."""
    finite = isinstance(ratio, (int, float)) and math.isfinite(ratio)
    ok = finite and ratio <= 1.0
    colour = _OK if ok else _BAD
    icon = "✔️" if ok else ("⚠️" if finite else "✖️")
    val = f"{ratio:.2f}" if finite else "N/A"
    return (
        '<div style="display:flex;justify-content:space-between;'
        'align-items:baseline;margin:3px 0;font-size:0.9rem;">'
        f'<span style="color:{_LBL};">{label}</span>'
        f'<span style="color:{colour};font-weight:700;">{val} {icon}</span>'
        '</div>'
    )


def _pf_badge(label, ok):
    """A coloured PASS / FAIL pill with its row label."""
    colour = _OK if ok else _BAD
    text = "PASS" if ok else "FAIL"
    icon = "✔️" if ok else "✖️"
    return (
        '<div style="display:flex;justify-content:space-between;'
        'align-items:center;margin:5px 0;">'
        f'<span style="color:{_LBL};font-size:0.9rem;">{label}</span>'
        f'<span style="background:{colour};color:#fff;padding:2px 10px;'
        'border-radius:999px;font-size:0.76rem;font-weight:700;'
        f'letter-spacing:0.03em;">{icon} {text}</span>'
        '</div>'
    )


def _render_design_sidecard(summary):
    st.markdown("### 📋 สรุปการออกแบบ")
    if not summary:
        st.caption("เลือกแท็บ «ออกแบบหน้าตัด» เพื่อดูผลสรุปแบบเรียลไทม์")
        return

    with st.container(border=True):
        st.markdown("**เหล็กเสริมที่เลือก (Selected Rebar)**")
        st.markdown(
            '<div style="line-height:1.9;font-size:0.92rem;">'
            f'🔺 เหล็กบน&nbsp;&nbsp;<b>{summary["top"]}</b><br>'
            f'🔻 เหล็กล่าง&nbsp;&nbsp;<b>{summary["bot"]}</b><br>'
            f'🔗 เหล็กปลอก&nbsp;&nbsp;<b>{summary["stirrup"]}</b>'
            '</div>',
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown("**อัตราส่วนกำลัง (Utilization)**")
        st.markdown(
            _util_row("เหล็กบน &minus;Mu", summary["ratio_top"])
            + _util_row("เหล็กล่าง +Mu", summary["ratio_bot"])
            + _util_row("แรงเฉือน Vu", summary["ratio_shear"]),
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown(
            _pf_badge("เหล็กบน (Top)", summary["top_ok"])
            + _pf_badge("เหล็กล่าง (Bottom)", summary["bottom_ok"])
            + _pf_badge("เหล็กปลอก (Stirrups)", summary["shear_ok"])
            + '<hr style="border:none;border-top:1px solid #334155;'
            'margin:6px 0;">'
            + _pf_badge("รวม (Overall)", summary["passed"]),
            unsafe_allow_html=True,
        )


def _load_input(label, key, default, help=None):
    """number_input for a factored-load field that the Analysis tab may
    pre-fill via ``st.session_state`` — pass ``value`` only when the key is
    not already set, so Streamlit does not warn about the double source."""
    kw = {} if key in st.session_state else {"value": float(default)}
    return st.number_input(label, min_value=0.0, step=100.0, format="%.0f",
                           key=key, help=help, **kw)


def _render_beam_analysis():
    st.subheader("วิเคราะห์คานต่อเนื่อง (Continuous Beam Analysis)")
    st.caption("ตัวแก้คาน 1 มิติ วิธี Matrix Stiffness — คานพาดต่อเนื่องบน "
               "ฐานรองรับแบบ pin/roller รับน้ำหนักแผ่สม่ำเสมอ "
               "(หน่วยเมตริก: m, kgf/m, kgf, kgf-m)")

    with st.expander("ข้อมูลคานและน้ำหนักบรรทุก", expanded=True):
        n_span = int(st.number_input("จำนวนช่วงคาน (Number of spans)",
                                     min_value=1, max_value=5, value=2,
                                     step=1, key="ba_nspan"))
        scols = st.columns(n_span)
        spans = []
        for i in range(n_span):
            with scols[i]:
                spans.append(st.number_input(
                    f"ช่วง L{i + 1} (m)", min_value=0.5, value=4.0,
                    step=0.5, format="%.2f", key=f"ba_L{i}"))
        d1, d2 = st.columns(2)
        with d1:
            DL = st.number_input("น้ำหนักบรรทุกคงที่ DL (kgf/m)",
                                 min_value=0.0, value=1000.0, step=50.0,
                                 key="ba_DL")
        with d2:
            LL = st.number_input("น้ำหนักบรรทุกจร LL (kgf/m)", min_value=0.0,
                                 value=800.0, step=50.0, key="ba_LL")

    Wu = 1.2 * DL + 1.6 * LL
    st.info(f"Wu = 1.2·DL + 1.6·LL = 1.2·{DL:,.0f} + 1.6·{LL:,.0f} = "
            f"**{Wu:,.1f} kgf/m**")

    if st.button("🔬 วิเคราะห์คาน (Analyze Beam)", type="primary",
                 key="ba_run"):
        try:
            res = solve_continuous_beam(spans, Wu)
        except Exception as exc:
            st.error(f"วิเคราะห์ไม่สำเร็จ: {exc}")
            res = None
        if res is not None:
            st.session_state["beam_diag"] = res
            # push the governing forces straight into the Design-tab widgets
            st.session_state["bs_Mup"] = float(round(res["Mu_pos_kgfm"]))
            st.session_state["bs_Mun"] = float(round(res["Mu_neg_kgfm"]))
            st.session_state["bs_Vu"] = float(round(res["Vu_kgf"]))

    res = st.session_state.get("beam_diag")
    if not res:
        st.caption("กดปุ่ม «วิเคราะห์คาน» เพื่อคำนวณ BMD / SFD และส่งค่าไปแท็บออกแบบ")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("+Mu สูงสุด (kgf-m)", f"{res['Mu_pos_kgfm']:,.0f}")
    m2.metric("−Mu สูงสุด (kgf-m)", f"{res['Mu_neg_kgfm']:,.0f}")
    m3.metric("Vu สูงสุด (kgf)", f"{res['Vu_kgf']:,.0f}")
    st.markdown("**แรงปฏิกิริยาที่ฐานรองรับ (Reactions):**  " + "  ·  ".join(
        f"R{i + 1} = {r:,.0f} kgf"
        for i, r in enumerate(res["reactions_kgf"])))

    try:
        fig = draw_beam_diagrams(res["x"], res["V"], res["M"])
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.warning("ยังไม่ได้ติดตั้งไลบรารี Plotly — `pip install plotly` "
                   "แล้วรีสตาร์ทแอป")
    except Exception as exc:  # pragma: no cover
        st.warning(f"ไม่สามารถวาดไดอะแกรมได้: {exc}")

    st.success("บันทึกค่า +Mu, −Mu, Vu ไปยังแท็บ «ออกแบบหน้าตัด» แล้ว — "
               "ช่องรับค่าจะถูกเติมให้อัตโนมัติ")


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

    def _r_top(s):
        if not s["feas_top"] or not s["As_top_prov"]:
            return float("inf")
        return (s["As_top_req"] or 0.0) / s["As_top_prov"]

    def _r_bot(s):
        if not s["feas_bot"] or not s["As_bot_prov"]:
            return float("inf")
        return (s["As_bot_req"] or 0.0) / s["As_bot_prov"]

    def _r_shear(s):
        return (s["Vu_kN"] / s["phiVn_kN"]) if s["phiVn_kN"] else float("inf")

    return {
        "kind": "3sect",
        "top": " · ".join(f"{s['top_qty']}-{s['top_size']}" for s in secs),
        "bot": " · ".join(f"{s['bot_qty']}-{s['bot_size']}" for s in secs),
        "stirrup": " · ".join(
            f"{s['stirrup_size']}@{s['stirrup_sp_cm']:.0f}" for s in secs),
        "ratio_top": max(_r_top(s) for s in secs),
        "ratio_bot": max(_r_bot(s) for s in secs),
        "ratio_shear": max(_r_shear(s) for s in secs),
        "top_ok": all(s["top_req_ok"] and s["top_min_ok"] for s in secs),
        "bottom_ok": all(s["bot_req_ok"] and s["bot_min_ok"] for s in secs),
        "shear_ok": all(s["shear_ok"] for s in secs),
        "passed": overall,
    }


def _render_beam_section():
    st.title("การออกแบบคาน (หน้าตัดคาน — โมเมนต์บวก / ลบ)")
    st.caption("ตรวจสอบการดัดพร้อมกัน: โมเมนต์บวก (กลางช่วง → เหล็กล่าง) และ "
               "โมเมนต์ลบ (ที่ฐานรองรับ → เหล็กบน) รวมทั้งแรงเฉือน ตามมาตรฐาน "
               "ACI 318M-08 — หน่วยเมตริก (cm, kgf, kgf-m, ksc)")

    # ------------------------------------------------------------------
    # 1. Section & Material
    # ------------------------------------------------------------------
    with st.expander("หน้าตัดและวัสดุ (Section & Material)", expanded=True):
        m1, m2, m3 = st.columns(3)
        with m1:
            b_cm = st.number_input("ความกว้างคาน b (cm)", min_value=15.0,
                                   value=30.0, step=1.0, format="%.1f",
                                   key="bs_b")
            fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)",
                                     min_value=180, value=240, step=10,
                                     format="%d", key="bs_fc")
        with m2:
            h_cm = st.number_input("ความลึกคาน h (cm)", min_value=20.0,
                                   value=55.0, step=1.0, format="%.1f",
                                   key="bs_h")
            fy_ksc = st.number_input("กำลังครากเหล็กหลัก fy (ksc)",
                                     min_value=2400, value=4000, step=100,
                                     format="%d", key="bs_fy")
        with m3:
            cov_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=2.0,
                                     value=4.0, step=0.5, format="%.1f",
                                     key="bs_cov")
            fyv_ksc = st.number_input("กำลังครากเหล็กปลอก fyv (ksc)",
                                      min_value=2400, value=2400, step=100,
                                      format="%d", key="bs_fyv")

    # ------------------------------------------------------------------
    # 2. Loads  — positive (mid-span) and negative (support) moment
    # ------------------------------------------------------------------
    with st.expander("แรงกระทำ (Loads)", expanded=True):
        if "beam_diag" in st.session_state:
            st.caption("ℹ️ ค่าด้านล่างถูกเติมจากแท็บ «วิเคราะห์แรง» — แก้ไขได้")
        l1, l2, l3 = st.columns(3)
        with l1:
            Mu_pos = _load_input(
                "โมเมนต์บวก +Mu (กลางช่วง, kgf-m)", "bs_Mup", 15300.0,
                help="ทำให้เกิดแรงดึงที่ด้านล่าง — ตรวจสอบด้วยเหล็กล่าง")
        with l2:
            Mu_neg = _load_input(
                "โมเมนต์ลบ −Mu (ที่ฐานรองรับ, kgf-m)", "bs_Mun", 18000.0,
                help="ทำให้เกิดแรงดึงที่ด้านบน — ตรวจสอบด้วยเหล็กบน (ค่าสัมบูรณ์)")
        with l3:
            Vu = _load_input("แรงเฉือนประลัย Vu (kgf)", "bs_Vu", 12000.0)
    Mu_neg = abs(Mu_neg)

    # ------------------------------------------------------------------
    # 3. Reinforcement Input
    # ------------------------------------------------------------------
    with st.expander("เหล็กเสริม (Reinforcement)", expanded=True):
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown("**เหล็กบน (Top Bars — รับ −Mu)**")
            top_size = st.selectbox("ขนาด", TOP_BOT_SIZES,
                                    index=TOP_BOT_SIZES.index("DB20"),
                                    key="bs_tsz")
            top_qty = int(st.number_input("จำนวนเส้น", min_value=2, value=4,
                                          step=1, key="bs_tq"))
        with r2:
            st.markdown("**เหล็กล่าง (Bottom Bars — รับ +Mu)**")
            bot_size = st.selectbox("ขนาด", TOP_BOT_SIZES,
                                    index=TOP_BOT_SIZES.index("DB20"),
                                    key="bs_bsz")
            bot_qty = int(st.number_input("จำนวนเส้น", min_value=2, value=3,
                                          step=1, key="bs_bq"))
        with r3:
            st.markdown("**เหล็กปลอก (Stirrups — รับ Vu)**")
            stir_size = st.selectbox("ขนาด", STIRRUP_SIZES, index=0,
                                     key="bs_ssz")
            S = st.number_input("ระยะเรียง S (cm)", min_value=2.5, value=15.0,
                                step=1.0, format="%.1f", key="bs_ssp")

    # ---- MKS working values (cm / kgf / kgf-m / ksc) -----------------
    b, h, cov = float(b_cm), float(h_cm), float(cov_cm)
    fc, fy, fyv = float(fc_ksc), float(fy_ksc), float(fyv_ksc)
    top_dia = float(top_size[2:]) / 10.0     # cm
    bot_dia = float(bot_size[2:]) / 10.0     # cm
    sdia = float(stir_size[2:]) / 10.0       # cm
    Ab_top = bar_area(top_size) / 100.0      # cm2 per top bar
    Ab_bot = bar_area(bot_size) / 100.0      # cm2 per bottom bar
    Av = 2.0 * bar_area(stir_size) / 100.0   # cm2 (2-leg stirrup)

    # effective depth to each layer
    d_bot = h - cov - sdia - bot_dia / 2.0   # tension = bottom (+Mu)
    d_top = h - cov - sdia - top_dia / 2.0   # tension = top    (-Mu)
    if min(d_top, d_bot) <= 0.0:
        st.error("ความลึกประสิทธิผล d ≤ 0 — ตรวจสอบ h ระยะหุ้ม หรือขนาดเหล็ก")
        return None

    # ------------------------------------------------------------------
    # Bottom bars vs positive moment
    # ------------------------------------------------------------------
    As_bot = bot_qty * Ab_bot
    a_bot, Mn_bot, phiMn_bot = _flex_ksc(As_bot, fy, fc, b, d_bot)
    As_min_bot = as_min_flexure_ksc(fc, fy, b, d_bot)
    As_max_bot = _rho_max_ksc(fc, fy) * b * d_bot
    bot_strength_ok = phiMn_bot >= Mu_pos
    bot_min_ok = As_bot >= As_min_bot
    bot_ductile_ok = As_bot <= As_max_bot
    bottom_ok = bot_strength_ok and bot_min_ok

    # ------------------------------------------------------------------
    # Top bars vs negative moment
    # ------------------------------------------------------------------
    As_top = top_qty * Ab_top
    a_top, Mn_top, phiMn_top = _flex_ksc(As_top, fy, fc, b, d_top)
    As_min_top = as_min_flexure_ksc(fc, fy, b, d_top)
    As_max_top = _rho_max_ksc(fc, fy) * b * d_top
    top_strength_ok = phiMn_top >= Mu_neg
    top_min_ok = As_top >= As_min_top
    top_ductile_ok = As_top <= As_max_top
    top_ok = top_strength_ok and top_min_ok

    # ------------------------------------------------------------------
    # Shear — Vc = 0.53*sqrt(f'c)*b*d  (MKS).  Use the smaller effective
    # depth of the two layers (conservative single value).
    # ------------------------------------------------------------------
    d_v = min(d_top, d_bot)
    Vc = vc_beam_ksc(fc, b, d_v)                            # kgf
    Vs = (Av * fyv * d_v / S) if S > 0.0 else 0.0           # kgf
    Vs_max = 2.1 * math.sqrt(fc) * b * d_v                  # kgf
    phiVn = phi["shear"] * (Vc + min(Vs, Vs_max))           # kgf
    s_max = min(d_v / 2.0, 60.0)                            # cm
    if Vs > 1.06 * math.sqrt(fc) * b * d_v:                 # dense-stirrup zone
        s_max = min(d_v / 4.0, 30.0)
    shear_strength_ok = phiVn >= Vu
    shear_spacing_ok = S <= s_max
    shear_vsmax_ok = Vs <= Vs_max
    shear_ok = shear_strength_ok and shear_spacing_ok and shear_vsmax_ok

    passed = top_ok and bottom_ok and shear_ok

    # ------------------------------------------------------------------
    # Calculation breakdown — both flexural layers side by side
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ — การดัด (Flexure)")
    st.markdown(
        f"""
| รายการ | เหล็กบน (−Mu) | เหล็กล่าง (+Mu) |
|---|---|---|
| เหล็กที่จัดให้ | {top_qty} - {top_size} | {bot_qty} - {bot_size} |
| ความลึกประสิทธิผล d = h − cover − Ø_ปลอก − Ø/2 | {d_top:,.2f} cm | {d_bot:,.2f} cm |
| As ที่จัดให้ | {As_top:,.2f} cm² | {As_bot:,.2f} cm² |
| a = As·fy / (0.85·f'c·b) | {a_top:,.2f} cm | {a_bot:,.2f} cm |
| Mn = As·fy·(d − a/2) | {Mn_top:,.0f} kgf-m | {Mn_bot:,.0f} kgf-m |
| **φMn = {phi['flexure']:.2f}·Mn** | **{phiMn_top:,.0f} kgf-m** | **{phiMn_bot:,.0f} kgf-m** |
| Mu ที่ต้องต้าน | {Mu_neg:,.0f} kgf-m | {Mu_pos:,.0f} kgf-m |
| As,min = max(0.8√f'c/fy, 14/fy)·b·d | {As_min_top:,.2f} cm² | {As_min_bot:,.2f} cm² |
| As,max (tension-controlled) | {As_max_top:,.2f} cm² | {As_max_bot:,.2f} cm² |
"""
    )

    st.subheader("ขั้นตอนการคำนวณ — แรงเฉือน (Shear)")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| ความลึกประสิทธิผลสำหรับแรงเฉือน d = min(d_บน, d_ล่าง) | {d_v:,.2f} cm |
| Vc = 0.53·√f'c·b·d | **{Vc:,.0f} kgf** |
| Av (เหล็กปลอก 2 ขา, {stir_size}) | {Av:,.2f} cm² |
| Vs = Av·fyv·d / S | **{Vs:,.0f} kgf** |
| Vs,max = 2.1·√f'c·b·d | {Vs_max:,.0f} kgf |
| φVn = {phi['shear']:.2f}·(Vc + Vs) | **{phiVn:,.0f} kgf** |
| ระยะเรียงปลอกสูงสุด s_max = min(d/2, 60) cm | {s_max:,.1f} cm |
"""
    )

    # ------------------------------------------------------------------
    # Three status cards — Top steel / Bottom steel / Stirrups
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    t_col, b_col, s_col = st.columns(3)
    with t_col:
        st.markdown("#### เหล็กบน — โมเมนต์ลบ")
        st.metric("φMn / |−Mu| (kgf-m)",
                  f"{phiMn_top:,.0f} / {Mu_neg:,.0f}",
                  delta=f"{phiMn_top - Mu_neg:,.0f}")
        st.metric("As / As,min (cm²)", f"{As_top:,.2f} / {As_min_top:,.2f}")
        (st.success if top_ok else st.error)(
            (PASS_TXT if top_ok else FAIL_TXT) + " — เหล็กบน (Top Steel)")
        if top_ok and not top_ductile_ok:
            st.warning("As,บน > As,max — เสริมเหล็กมากเกินไป")
    with b_col:
        st.markdown("#### เหล็กล่าง — โมเมนต์บวก")
        st.metric("φMn / +Mu (kgf-m)",
                  f"{phiMn_bot:,.0f} / {Mu_pos:,.0f}",
                  delta=f"{phiMn_bot - Mu_pos:,.0f}")
        st.metric("As / As,min (cm²)", f"{As_bot:,.2f} / {As_min_bot:,.2f}")
        (st.success if bottom_ok else st.error)(
            (PASS_TXT if bottom_ok else FAIL_TXT) + " — เหล็กล่าง (Bottom Steel)")
        if bottom_ok and not bot_ductile_ok:
            st.warning("As,ล่าง > As,max — เสริมเหล็กมากเกินไป")
    with s_col:
        st.markdown("#### เหล็กปลอก — แรงเฉือน")
        st.metric("φVn / Vu (kgf)", f"{phiVn:,.0f} / {Vu:,.0f}",
                  delta=f"{phiVn - Vu:,.0f}")
        st.metric("S / s_max (cm)", f"{S:,.1f} / {s_max:,.1f}")
        (st.success if shear_ok else st.error)(
            (PASS_TXT if shear_ok else FAIL_TXT) + " — เหล็กปลอก (Stirrups)")
        if not shear_vsmax_ok:
            st.warning("Vs > Vs,max — เพิ่มขนาดหน้าตัด (b·d)")

    # ------------------------------------------------------------------
    # CAD drawing — cross-section + side elevation (structure unchanged;
    # top & bottom bars now reflect the verified dual-moment design)
    # ------------------------------------------------------------------
    section_img = None
    try:
        fig = draw_beam_detail(
            b * CM, h * CM, cov * CM,
            top_size=top_size, top_qty=top_qty,
            bot_size=bot_size, bot_qty=bot_qty,
            stirrup_size=stir_size, stirrup_sp_cm=S)
        st.pyplot(fig, use_container_width=True)
        st.caption("รายละเอียดคาน — หน้าตัด + รูปด้าน (Beam Detailing)")
        section_img = fig_to_png_buf(fig)     # PNG buffer for the PDF report
    except Exception as exc:  # pragma: no cover - drawing must never break the page
        st.warning(f"ไม่สามารถสร้างภาพรายละเอียดได้: {exc}")

    # ------------------------------------------------------------------
    # Overall verdict + report
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบรวม")
    if passed:
        st.success(f"{PASS_TXT} — ผ่านทั้งเหล็กบน (−Mu), เหล็กล่าง (+Mu) และแรงเฉือน")
    else:
        fails = []
        if not top_strength_ok:
            fails.append(f"เหล็กบน φMn < |−Mu| ({phiMn_top:,.0f} < {Mu_neg:,.0f} kgf-m)")
        if not top_min_ok:
            fails.append(f"เหล็กบน As < As,min ({As_top:,.2f} < {As_min_top:,.2f} cm²)")
        if not bot_strength_ok:
            fails.append(f"เหล็กล่าง φMn < +Mu ({phiMn_bot:,.0f} < {Mu_pos:,.0f} kgf-m)")
        if not bot_min_ok:
            fails.append(f"เหล็กล่าง As < As,min ({As_bot:,.2f} < {As_min_bot:,.2f} cm²)")
        if not shear_strength_ok:
            fails.append(f"φVn < Vu ({phiVn:,.0f} < {Vu:,.0f} kgf)")
        if not shear_spacing_ok:
            fails.append(f"S > s_max ({S:,.1f} > {s_max:,.1f} cm)")
        if not shear_vsmax_ok:
            fails.append("Vs > Vs,max")
        st.error(f"{FAIL_TXT} — " + "; ".join(fails))

    # ------------------------------------------------------------------
    render_report_expander(
        key="beam_sec", filename="beam_design_report.pdf",
        title="การออกแบบคานคอนกรีตเสริมเหล็ก (ACI 318M-08)",
        params=[
            ("ความกว้างคาน b", b, "cm", 1), ("ความลึกคาน h", h, "cm", 1),
            ("ระยะหุ้มคอนกรีต", cov, "cm", 1),
            ("f'c", fc, "ksc", 0), ("fy เหล็กหลัก", fy, "ksc", 0),
            ("fyv เหล็กปลอก", fyv, "ksc", 0),
            ("โมเมนต์บวก +Mu", Mu_pos, "kgf-m", 0),
            ("โมเมนต์ลบ −Mu", Mu_neg, "kgf-m", 0),
            ("แรงเฉือน Vu", Vu, "kgf", 0),
            ("เหล็กบน", f"{top_qty} - {top_size}"),
            ("เหล็กล่าง", f"{bot_qty} - {bot_size}"),
            ("เหล็กปลอก", f"{stir_size} @ {S:.1f} cm"),
        ],
        checks=[
            ("การดัด — เหล็กบน (φMn ≥ |−Mu|)", f"{Mu_neg:,.0f} kgf-m",
             f"{phiMn_top:,.0f} kgf-m", top_strength_ok),
            ("เหล็กบน As ≥ As,min", f"{As_top:,.2f} cm²",
             f"{As_min_top:,.2f} cm²", top_min_ok),
            ("การดัด — เหล็กล่าง (φMn ≥ +Mu)", f"{Mu_pos:,.0f} kgf-m",
             f"{phiMn_bot:,.0f} kgf-m", bot_strength_ok),
            ("เหล็กล่าง As ≥ As,min", f"{As_bot:,.2f} cm²",
             f"{As_min_bot:,.2f} cm²", bot_min_ok),
            ("แรงเฉือน (φVn ≥ Vu)", f"{Vu:,.0f} kgf",
             f"{phiVn:,.0f} kgf", shear_strength_ok),
            ("ระยะเรียงปลอก (S ≤ s_max)", f"{S:.1f} cm",
             f"{s_max:.1f} cm", shear_spacing_ok),
        ],
        figures=[("รายละเอียดคาน (Cross-Section + Side Elevation)", section_img)],
        status=passed,
        summary=("ผ่านทั้งการดัดเหล็กบน/ล่าง และแรงเฉือน" if passed
                 else "มีรายการไม่ผ่าน — โปรดตรวจสอบตารางการตรวจสอบ"))

    def _ratio(demand, capacity):
        return (demand / capacity) if capacity > 0.0 else float("inf")

    return {
        "kind": "section",
        "top": f"{top_qty} - {top_size}",
        "bot": f"{bot_qty} - {bot_size}",
        "stirrup": f"{stir_size} @ {S:.0f} cm",
        "ratio_top": _ratio(Mu_neg, phiMn_top),
        "ratio_bot": _ratio(Mu_pos, phiMn_bot),
        "ratio_shear": _ratio(Vu, phiVn),
        "top_ok": top_ok,
        "bottom_ok": bottom_ok,
        "shear_ok": shear_ok,
        "passed": passed,
    }


# Backwards-compatible alias
render = render_beam_module


if __name__ == "__main__":
    render_beam_module()
