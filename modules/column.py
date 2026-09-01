"""Streamlit UI — RC rectangular column: biaxial P-M interaction design.

Strain-compatibility method (ACI 318M-08 10.2 / 10.3):
    * sweep the neutral-axis depth c, εcu = 0.003
    * build the nominal and design (φ) P-M curves for bending about X and Y
    * φ (tied) interpolates 0.65 -> 0.90 with the net tensile strain εt
    * axial cap  Pu,max = 0.80 φ [0.85 f'c (Ag - Ast) + fy Ast]
    * biaxial check by the Bresler reciprocal-load method

UI units: cm / ksc / kN ; converted to mm / MPa / N internally.
"""

import math

import streamlit as st

from utils.aci_318m import get_beta1, rebars, bar_area
from utils.drawing import (draw_column_pm_and_section, draw_column_detail,
                           fig_to_png_buf)
from utils.project import get_project_info, render_report_expander
from reports.pdf_generator import (
    generate_column_report,
    FONT_AVAILABLE,
    font_status_message,
)

CM = 10.0                # cm -> mm
KSC_TO_MPA = 0.0980665   # ksc -> MPa
KGF_TO_KN = 9.80665 / 1000.0   # kgf -> kN  (also kgf-m -> kN.m)
KN_TO_KGF = 1000.0 / 9.80665   # kN  -> kgf (also kN.m -> kgf-m)
ES = 200000.0            # MPa, steel modulus
EPS_CU = 0.003           # ultimate concrete strain
PHI_CC = 0.65            # compression-controlled φ (tied)
PHI_TC = 0.90            # tension-controlled φ
EPS_TC = 0.005           # net tensile strain for tension-controlled
ALPHA_MAX = 0.80         # tied-column axial cap factor (ACI 10.3.6.2)
RHO_MIN = 0.01
RHO_MAX = 0.08
MAIN_SIZES = [s for s in rebars.keys() if s.startswith("DB")]   # DB12 .. DB32
STIRRUP_SIZES = ["RB9", "RB6", "DB10", "DB12"]
COL_SHAPES = ["Rectangular (Tied)", "Circular (Spiral)"]

PASS_TXT = "✅ ผ่านมาตรฐาน (PASS)"
FAIL_TXT = "❌ ไม่ผ่าน (FAIL)"

COLUMN_TYPES = [
    "Column (เสา)",
    "Corbel (แป้นหูช้าง)",
]

UNDER_CONSTRUCTION = "กำลังอยู่ระหว่างการพัฒนา (Under Construction)"


def render_column_module():
    column_type = st.selectbox("เลือกประเภทเสา (Column Type)", COLUMN_TYPES,
                               key="column_type")
    if column_type == "Column (เสา)":
        _render_column()
    else:
        st.info(UNDER_CONSTRUCTION)


# ===========================================================================
# Strain-compatibility helpers
# ===========================================================================


def _phi_tied(eps_t, fy):
    """ACI strength-reduction factor for a tied member from εt."""
    eps_ty = fy / ES
    if eps_t <= eps_ty:
        return PHI_CC
    if eps_t >= EPS_TC:
        return PHI_TC
    return PHI_CC + (PHI_TC - PHI_CC) * (eps_t - eps_ty) / (EPS_TC - eps_ty)


def _bar_coords(b, h, cc, n_x, n_y):
    """Perimeter bar centres (x, y) about the section centroid.

    n_x = bars per face parallel to b (top & bottom rows)
    n_y = bars per face parallel to h (left & right columns)
    Total = 2 (n_x + n_y - 2).
    """
    n_x = max(int(n_x), 2)
    n_y = max(int(n_y), 2)
    xm = b / 2.0 - cc
    ym = h / 2.0 - cc
    xs = [-xm + i * (2.0 * xm) / (n_x - 1) for i in range(n_x)]
    ys = [-ym + j * (2.0 * ym) / (n_y - 1) for j in range(n_y)]
    pts = []
    for x in xs:                       # top & bottom rows
        pts.append((x, ym))
        pts.append((x, -ym))
    for y in ys[1:-1]:                 # left & right, corners excluded
        pts.append((-xm, y))
        pts.append((xm, y))
    return pts


def _layers(coords, As_bar, span, axis):
    """Steel layers as (d, As) with d measured from the extreme compression
    fibre.  axis 0 = bending about Y (strain along x, depth = b);
    axis 1 = bending about X (strain along y, depth = h)."""
    grp = {}
    for (x, y) in coords:
        key = round(x if axis == 0 else y, 2)
        grp[key] = grp.get(key, 0.0) + As_bar
    return sorted(((span / 2.0 - k, a) for k, a in grp.items()),
                  key=lambda t: t[0])


def _pm_point(c, H, B, fc, fy, layers, beta1):
    """Nominal (Pn, Mn), φ and εt for one neutral-axis depth c (mm)."""
    a = min(beta1 * c, H)
    Cc = 0.85 * fc * B * a                              # N
    Pn = Cc
    Mn = Cc * (H / 2.0 - a / 2.0)
    d_t = layers[-1][0]
    for (d, As_i) in layers:
        eps_s = EPS_CU * (c - d) / c
        fs = max(-fy, min(fy, eps_s * ES))
        if d <= a and eps_s > 0.0:
            fs -= 0.85 * fc                             # displaced concrete
        Fs = As_i * fs
        Pn += Fs
        Mn += Fs * (H / 2.0 - d)
    eps_t = EPS_CU * (d_t - c) / c
    return Pn, Mn, _phi_tied(eps_t, fy), eps_t


def _pm_curve(H, B, fc, fy, layers, Ag, Ast, npts=48):
    """Return (nominal_pts, design_pts, Po) in N and N·mm.

    *_pts are lists of (M, P) ordered from pure compression to pure tension.
    """
    beta1 = get_beta1(fc)
    Po = 0.85 * fc * (Ag - Ast) + fy * Ast              # N
    phiPn_max = ALPHA_MAX * PHI_CC * Po                 # N (design cap)
    d_t = layers[-1][0]

    nom = [(0.0, Po)]
    dsn = [(0.0, min(ALPHA_MAX * PHI_CC * Po, phiPn_max))]

    c_hi, c_lo = 6.0 * H, 0.03 * d_t
    for i in range(npts):
        c = c_hi * (c_lo / c_hi) ** (i / (npts - 1))
        Pn, Mn, ph, _ = _pm_point(c, H, B, fc, fy, layers, beta1)
        nom.append((max(Mn, 0.0), Pn))
        phiPn = min(ph * Pn, phiPn_max)
        dsn.append((max(ph * Mn, 0.0), phiPn))

    Tn = -fy * Ast                                      # pure tension
    nom.append((0.0, Tn))
    dsn.append((0.0, PHI_TC * Tn))
    return nom, dsn, Po, phiPn_max


def _cap_M_at_P(dsn, P):
    """Design moment capacity φMn at axial level P (N).  None if out of range."""
    best = None
    for (M1, P1), (M2, P2) in zip(dsn, dsn[1:]):
        lo, hi = min(P1, P2), max(P1, P2)
        if lo - 1.0 <= P <= hi + 1.0:
            if abs(P2 - P1) < 1.0e-6:
                cand = max(M1, M2)
            else:
                t = (P - P1) / (P2 - P1)
                cand = M1 + t * (M2 - M1)
            best = cand if best is None else max(best, cand)
    return best


def _Pn_at_ecc(nom, e):
    """Nominal axial load Pn (N) on the curve where Mn = e·Pn (compression
    branch).  e in mm.  None if no intersection."""
    if e < 1.0e-6:
        return nom[0][1]
    best = None
    for (M1, P1), (M2, P2) in zip(nom, nom[1:]):
        denom = (M2 - M1) - e * (P2 - P1)
        if abs(denom) < 1.0e-9:
            continue
        t = (e * P1 - M1) / denom
        if -1.0e-6 <= t <= 1.0 + 1.0e-6:
            P = P1 + t * (P2 - P1)
            if P > 0.0:
                best = P if best is None else max(best, P)
    return best


# ===========================================================================
# UI
# ===========================================================================


def _render_column():
    st.title("การออกแบบเสา (Column — แรงตามแนวแกน + รายละเอียด)")
    st.caption("ตรวจสอบอัตราส่วนเหล็กเสริม ρg, กำลังรับแรงตามแนวแกน φPn,max และ "
               "ระยะเรียงเหล็กปลอก/เหล็กเกลียว ตามมาตรฐาน ACI 318M-08 — "
               "หน่วยเมตริก (cm, kgf, kgf-m, ksc)")

    shape = st.selectbox("ประเภทเสา (Column Type)", COL_SHAPES, key="cd_shape")
    circular = shape.startswith("Circular")

    # ------------------------------------------------------------------
    # 1. Section & Material
    # ------------------------------------------------------------------
    with st.expander("หน้าตัดและวัสดุ (Section & Material)", expanded=True):
        s1, s2 = st.columns(2)
        if circular:
            with s1:
                D_cm = st.number_input("เส้นผ่านศูนย์กลาง D (cm)", min_value=20.0,
                                       value=45.0, step=1.0, format="%.1f",
                                       key="cd_D")
            b_cm = h_cm = float(D_cm)
        else:
            with s1:
                b_cm = st.number_input("ความกว้าง b (cm)", min_value=20.0,
                                       value=40.0, step=1.0, format="%.1f",
                                       key="cd_b")
            with s2:
                h_cm = st.number_input("ความลึก h (cm)", min_value=20.0,
                                       value=40.0, step=1.0, format="%.1f",
                                       key="cd_h")
            D_cm = None

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            cov_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=2.0,
                                     value=4.0, step=0.5, format="%.1f",
                                     key="cd_cov")
        with m2:
            fc_ksc = st.number_input("f'c (ksc)", min_value=180, value=240,
                                     step=10, format="%d", key="cd_fc")
        with m3:
            fy_ksc = st.number_input("fy เหล็กหลัก (ksc)", min_value=2400,
                                     value=4000, step=100, format="%d",
                                     key="cd_fy")
        with m4:
            fyv_ksc = st.number_input("fyv ปลอก/เกลียว (ksc)", min_value=2400,
                                      value=2400, step=100, format="%d",
                                      key="cd_fyv")

    # ------------------------------------------------------------------
    # 2. Loads
    # ------------------------------------------------------------------
    with st.expander("แรงกระทำ (Loads)", expanded=True):
        l1, l2 = st.columns(2)
        with l1:
            Pu = st.number_input("แรงตามแนวแกนประลัย Pu (kgf)", min_value=0.0,
                                 value=180000.0, step=1000.0, key="cd_Pu")
        with l2:
            Mu = st.number_input(
                "โมเมนต์ดัดประลัย Mu (kgf-m)", min_value=0.0, value=6000.0,
                step=100.0, key="cd_Mu",
                help="ยังไม่นำมาคิดในรุ่นนี้ — เก็บไว้สำหรับแผนภาพ P-M ในอนาคต")

    # ------------------------------------------------------------------
    # 3. Reinforcement
    # ------------------------------------------------------------------
    with st.expander("เหล็กเสริม (Reinforcement)", expanded=True):
        r1, r2 = st.columns(2)
        with r1:
            main_size = st.selectbox("เหล็กเสริมหลัก — ขนาด", MAIN_SIZES,
                                     index=MAIN_SIZES.index("DB20"),
                                     key="cd_msz")
            n_bars = int(st.number_input(
                "จำนวนเหล็กเสริมหลักทั้งหมด (เส้น)",
                min_value=(6 if circular else 4),
                value=(8 if circular else 8), step=(2 if circular else 1),
                key="cd_nbar"))
        with r2:
            _tie_word = "เหล็กเกลียว (Spiral)" if circular else "เหล็กปลอก (Tie)"
            stir_size = st.selectbox(f"{_tie_word} — ขนาด", STIRRUP_SIZES,
                                     index=0, key="cd_ssz")

    # ---- MKS working values (cm / kgf / kgf-m / ksc) -----------------
    b, h, cov = float(b_cm), float(h_cm), float(cov_cm)
    fc, fy, fyv = float(fc_ksc), float(fy_ksc), float(fyv_ksc)
    main_dia = float(main_size[2:]) / 10.0        # cm
    tie_dia = float(stir_size[2:]) / 10.0         # cm
    Ab = bar_area(main_size) / 100.0              # cm2 per main bar
    a_tie = bar_area(stir_size) / 100.0           # cm2 per tie/spiral bar
    Ast = n_bars * Ab                             # cm2

    if circular:
        D = float(D_cm)
        Ag = math.pi * D * D / 4.0                # cm2
        least_dim = D
    else:
        D = None
        Ag = b * h
        least_dim = min(b, h)

    if cov + tie_dia + main_dia >= least_dim / 2.0:
        st.error("ระยะหุ้ม + ปลอก + เหล็กหลัก มากเกินไปเมื่อเทียบกับขนาดหน้าตัด")
        return

    # ------------------------------------------------------------------
    # Check 1 — gross steel ratio  1% <= rho_g <= 8%
    # ------------------------------------------------------------------
    rho_g = Ast / Ag if Ag > 0.0 else 0.0
    ratio_ok = RHO_MIN <= rho_g <= RHO_MAX

    # ------------------------------------------------------------------
    # Check 2 — max design axial capacity  phi*Pn,max  (ACI 10.3.6)
    #   Po = 0.85 f'c (Ag - Ast) + fy Ast
    #   tied   : phi*Pn,max = 0.80 * 0.65 * Po
    #   spiral : phi*Pn,max = 0.85 * 0.75 * Po
    # ------------------------------------------------------------------
    Po = 0.85 * fc * (Ag - Ast) + fy * Ast                 # kgf
    if circular:
        alpha, phi_c = 0.85, 0.75
    else:
        alpha, phi_c = 0.80, 0.65
    phiPn_max = alpha * phi_c * Po                          # kgf
    axial_ok = phiPn_max >= Pu

    # ------------------------------------------------------------------
    # Check 3 — transverse reinforcement spacing (ACI 7.10)
    #   tied   : s_max = min(16 db, 48 d_tie, least column dimension)
    #   spiral : clear pitch 25-75 mm and rho_s >= 0.45 (Ag/Ach - 1) f'c/fyt
    # ------------------------------------------------------------------
    if circular:
        Dch = D - 2.0 * cov                                 # core dia (cm)
        Ach = math.pi * Dch * Dch / 4.0
        rho_s_req = 0.45 * (Ag / Ach - 1.0) * fc / fyv
        # rho_s = 4 a_sp / (Dch * s)  ->  pitch to reach rho_s,req
        s_rho = (4.0 * a_tie / (Dch * rho_s_req)) if rho_s_req > 0 else 99.0
        S_req = min(s_rho, 7.5)                             # cap at 75 mm pitch
        spacing_ok = s_rho >= 2.5                           # else use a bigger spiral bar
        spacing_note = (f"ρs,ต้องการ = 0.45(Ag/Ach−1)·f'c/fyt = {rho_s_req:.4f} ; "
                        f"ระยะพิตช์ที่ต้องใช้ ≈ {s_rho:,.1f} cm (พิตช์ 2.5–7.5 cm)")
    else:
        s1v = 16.0 * main_dia
        s2v = 48.0 * tie_dia
        s3v = least_dim
        S_req = min(s1v, s2v, s3v)
        spacing_ok = S_req >= 5.0
        spacing_note = (f"s_max = min(16·db = {s1v:,.1f}, 48·d_tie = {s2v:,.1f}, "
                        f"ด้านแคบ = {s3v:,.1f}) cm")

    passed = ratio_ok and axial_ok and spacing_ok

    # ------------------------------------------------------------------
    # Calculation breakdown
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    _sec_txt = (f"วงกลม Ø {D:,.1f} cm" if circular
                else f"สี่เหลี่ยม {b:,.1f} × {h:,.1f} cm")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| หน้าตัด | {_sec_txt} |
| พื้นที่หน้าตัดรวม Ag | {Ag:,.1f} cm² |
| เหล็กเสริมหลัก | {n_bars} - {main_size} |
| พื้นที่เหล็กเสริมทั้งหมด Ast = {n_bars} × {Ab:,.2f} | **{Ast:,.2f} cm²** |
| อัตราส่วนเหล็กเสริม ρg = Ast / Ag | **{rho_g * 100.0:,.2f}%** (ยอมให้ 1–8%) |
| กำลังตามแนวแกนล้วน Po = 0.85·f'c·(Ag−Ast) + fy·Ast | {Po:,.0f} kgf |
| ตัวคูณ (α · φ) — {"เกลียว" if circular else "ปลอก"} | {alpha:.2f} · {phi_c:.2f} |
| ขีดจำกัดออกแบบ φPn,max = α·φ·Po | **{phiPn_max:,.0f} kgf** |
| แรงตามแนวแกนประลัย Pu | {Pu:,.0f} kgf |
| ระยะเรียง{"เหล็กเกลียว (พิตช์)" if circular else "เหล็กปลอก"} ที่แนะนำ S | **≤ {S_req:,.1f} cm** |
| เกณฑ์ระยะเรียง | {spacing_note} |
"""
    )
    st.caption("หมายเหตุ: โมเมนต์ Mu ยังไม่ถูกนำมาคิดในรุ่นนี้ "
               "(เตรียมไว้สำหรับแผนภาพปฏิสัมพันธ์ P-M)")

    # ------------------------------------------------------------------
    # Result cards
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")
    c_ratio, c_axial, c_tie = st.columns(3)
    with c_ratio:
        st.markdown("#### อัตราส่วนเหล็ก ρg")
        st.metric("ρg (1–8%)", f"{rho_g * 100.0:,.2f} %")
        (st.success if ratio_ok else st.error)(
            (PASS_TXT if ratio_ok else FAIL_TXT) + " — ρg")
        if not ratio_ok:
            side = "ต่ำกว่า 1%" if rho_g < RHO_MIN else "เกิน 8%"
            st.warning(f"ρg {side} — ปรับจำนวน/ขนาดเหล็ก หรือขนาดหน้าตัด")
    with c_axial:
        st.markdown("#### แรงตามแนวแกน")
        st.metric("φPn,max / Pu (kgf)", f"{phiPn_max:,.0f} / {Pu:,.0f}",
                  delta=f"{phiPn_max - Pu:,.0f}")
        (st.success if axial_ok else st.error)(
            (PASS_TXT if axial_ok else FAIL_TXT) + " — φPn,max ≥ Pu")
    with c_tie:
        st.markdown("#### ระยะเรียง" + ("เหล็กเกลียว" if circular else "เหล็กปลอก"))
        st.metric("S ที่แนะนำ (cm)", f"≤ {S_req:,.1f}")
        (st.success if spacing_ok else st.error)(
            (PASS_TXT if spacing_ok else FAIL_TXT) + " — ระยะเรียง")
        if circular and not spacing_ok:
            st.warning("พิตช์ที่ต้องใช้ < 2.5 cm — เพิ่มขนาดเหล็กเกลียว")

    # ------------------------------------------------------------------
    # CAD-style cross-section drawing
    # ------------------------------------------------------------------
    section_img = None
    try:
        fig = draw_column_detail(
            shape="circ" if circular else "rect",
            b_mm=b * CM, h_mm=h * CM,
            D_mm=(D * CM if circular else None),
            covering_mm=cov * CM, main_size=main_size, n_bars=n_bars,
            tie_size=stir_size, tie_sp_cm=S_req)
        st.pyplot(fig, use_container_width=True)
        st.caption("รายละเอียดหน้าตัดเสา (Column Cross-Section)")
        section_img = fig_to_png_buf(fig)        # PNG buffer for the report
    except Exception as exc:  # pragma: no cover
        st.warning(f"ไม่สามารถสร้างภาพหน้าตัดได้: {exc}")

    # ------------------------------------------------------------------
    # Overall verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบรวม")
    if passed:
        st.success(f"{PASS_TXT} — ρg, φPn,max ≥ Pu และระยะเรียงเหล็กขวางผ่านเกณฑ์")
    else:
        fails = []
        if not ratio_ok:
            fails.append(f"ρg = {rho_g * 100:,.2f}% นอกช่วง 1–8%")
        if not axial_ok:
            fails.append(f"Pu = {Pu:,.0f} > φPn,max = {phiPn_max:,.0f} kgf")
        if not spacing_ok:
            fails.append("ระยะเรียงเหล็กขวางไม่ผ่านเกณฑ์")
        st.error(f"{FAIL_TXT} — " + "; ".join(fails))

    # ------------------------------------------------------------------
    _sec_lbl = (f"วงกลม Ø {D:,.1f} cm" if circular
                else f"สี่เหลี่ยม {b:,.1f} × {h:,.1f} cm")
    render_report_expander(
        key="col_axial", filename="column_design_report.pdf",
        title="การออกแบบเสาคอนกรีตเสริมเหล็ก (ACI 318M-08)",
        params=[
            ("ประเภทเสา", shape), ("หน้าตัด", _sec_lbl),
            ("ระยะหุ้มคอนกรีต", cov, "cm", 1),
            ("f'c", fc, "ksc", 0), ("fy เหล็กหลัก", fy, "ksc", 0),
            ("fyv ปลอก/เกลียว", fyv, "ksc", 0),
            ("เหล็กเสริมหลัก", f"{n_bars} - {main_size}"),
            (("เหล็กเกลียว" if circular else "เหล็กปลอก"), stir_size),
            ("แรงตามแนวแกน Pu", Pu, "kgf", 0),
            ("โมเมนต์ Mu (ยังไม่คิด)", Mu, "kgf-m", 0),
            ("พื้นที่หน้าตัดรวม Ag", Ag, "cm²", 1),
            ("พื้นที่เหล็กเสริม Ast", Ast, "cm²", 2),
        ],
        checks=[
            ("อัตราส่วนเหล็ก ρg (1–8%)", f"{rho_g * 100:,.2f} %",
             "1.00 – 8.00 %", ratio_ok),
            ("กำลังตามแนวแกน (φPn,max ≥ Pu)", f"{Pu:,.0f} kgf",
             f"{phiPn_max:,.0f} kgf", axial_ok),
            (("ระยะพิตช์เหล็กเกลียว" if circular else "ระยะเรียงเหล็กปลอก"),
             f"S ≤ {S_req:,.1f} cm",
             f"{'พิตช์ 2.5–7.5 cm' if circular else f'≤ {least_dim:,.0f} cm'}",
             spacing_ok),
        ],
        figures=[("รายละเอียดหน้าตัดเสา (Column Cross-Section)", section_img)],
        status=passed,
        summary=("ρg, φPn,max ≥ Pu และระยะเรียงเหล็กขวางผ่านเกณฑ์ ACI 318M-08"
                 if passed else "มีรายการไม่ผ่าน — โปรดตรวจสอบตารางการตรวจสอบ"))


if __name__ == "__main__":
    render_column_module()
