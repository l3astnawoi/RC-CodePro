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
from utils.drawing import draw_column_pm_and_section
from utils.project import get_project_info
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
    st.title("การออกแบบเสา — แผนภาพปฏิสัมพันธ์ P-M (Biaxial)")
    st.caption("เสาสี่เหลี่ยมรับแรงตามแนวแกนร่วมกับโมเมนต์ดัดสองแกน — "
               "วิธีความเข้ากันได้ของความเครียด (Strain Compatibility) "
               "และ Bresler Reciprocal Load ตามมาตรฐาน ACI 318M-08")

    # ---- Section / material ----
    st.subheader("หน้าตัดและวัสดุ")
    c1, c2, c3 = st.columns(3)
    with c1:
        b_cm = st.number_input("ความกว้าง b (cm, แกน X)", min_value=20.0,
                               value=40.0, step=0.5, format="%.1f", key="col_b")
        fc_ksc = st.number_input("กำลังอัดคอนกรีต f'c (ksc)", min_value=180,
                                 value=240, step=10, format="%d", key="col_fc")
    with c2:
        h_cm = st.number_input("ความลึก h (cm, แกน Y)", min_value=20.0,
                               value=40.0, step=0.5, format="%.1f", key="col_h")
        fy_ksc = st.number_input("กำลังครากเหล็กเสริม fy (ksc)", min_value=2800,
                                 value=4000, step=100, format="%d", key="col_fy")
    with c3:
        covering_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=2.0,
                                      value=4.0, step=0.5, format="%.1f",
                                      key="col_cov")

    # ---- Factored loads ----
    st.subheader("แรงกระทำประลัย")
    l1, l2, l3 = st.columns(3)
    with l1:
        Pu_kgf = st.number_input("แรงตามแนวแกน Pu (kgf)", min_value=0.0,
                                 value=120000.0, step=1000.0, key="col_Pu")
    with l2:
        Mux_kgfm = st.number_input("โมเมนต์ดัดรอบแกน X, Mux (kgf-m)",
                                   min_value=0.0, value=7000.0, step=100.0,
                                   key="col_Mux")
    with l3:
        Muy_kgfm = st.number_input("โมเมนต์ดัดรอบแกน Y, Muy (kgf-m)",
                                   min_value=0.0, value=5000.0, step=100.0,
                                   key="col_Muy")

    # ---- Reinforcement ----
    st.subheader("เหล็กเสริม")
    r1, r2, r3 = st.columns(3)
    with r1:
        main_size = st.selectbox("ขนาดเหล็กเสริมหลัก", MAIN_SIZES,
                                 index=MAIN_SIZES.index("DB20"),
                                 key="col_main")
        n_x = int(st.number_input("จำนวนเหล็กด้านกว้าง b (n_x)", min_value=2,
                                  max_value=10, value=3, step=1, key="col_nx"))
    with r2:
        n_y = int(st.number_input("จำนวนเหล็กด้านลึก h (n_y)", min_value=2,
                                  max_value=10, value=3, step=1, key="col_ny"))
        stir_size = st.selectbox("ขนาดเหล็กปลอก", STIRRUP_SIZES, index=0,
                                 key="col_stir")
    with r3:
        stir_sp_cm = st.number_input("ระยะเรียงเหล็กปลอก (cm)", min_value=5.0,
                                     max_value=40.0, value=15.0, step=1.0,
                                     format="%.1f", key="col_stir_sp")

    # ---- MKS -> SI ----
    b = b_cm * CM
    h = h_cm * CM
    covering = covering_cm * CM
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA
    Pu = Pu_kgf * KGF_TO_KN                             # kgf   -> kN
    Mux = Mux_kgfm * KGF_TO_KN                          # kgf-m -> kN.m
    Muy = Muy_kgfm * KGF_TO_KN

    main_dia = float(main_size[2:])
    stir_dia = float(stir_size[2:])
    As_bar = bar_area(main_size)
    cc = covering + stir_dia + main_dia / 2.0           # cover to bar centroid

    total_bars = 2 * (n_x + n_y - 2)
    Ag = b * h
    Ast = total_bars * As_bar
    rho_g = Ast / Ag if Ag > 0 else 0.0
    ratio_ok = RHO_MIN <= rho_g <= RHO_MAX

    if cc >= min(b, h) / 2.0:
        st.error("ระยะหุ้ม + ปลอก + เหล็กหลัก มากเกินไปเมื่อเทียบกับขนาดหน้าตัด")
        return

    coords = _bar_coords(b, h, cc, n_x, n_y)

    # ---- P-M curves (bending about X: depth = h ; about Y: depth = b) ----
    layers_x = _layers(coords, As_bar, h, axis=1)
    layers_y = _layers(coords, As_bar, b, axis=0)
    nom_x, dsn_x, Po, phiPn_max = _pm_curve(h, b, fc, fy, layers_x, Ag, Ast)
    nom_y, dsn_y, _Po2, _cap2 = _pm_curve(b, h, fc, fy, layers_y, Ag, Ast)

    phiPn_max_kN = phiPn_max / 1000.0
    Pu_N = Pu * 1000.0
    axial_max_ok = Pu_N <= phiPn_max + 1.0

    phiMn_x = _cap_M_at_P(dsn_x, Pu_N)          # N·mm  (None -> beyond curve)
    phiMn_y = _cap_M_at_P(dsn_y, Pu_N)
    phiMn_x_kNm = None if phiMn_x is None else phiMn_x / 1.0e6
    phiMn_y_kNm = None if phiMn_y is None else phiMn_y / 1.0e6

    uniax_x_ok = (Mux <= 1.0e-9) or (phiMn_x_kNm is not None and Mux <= phiMn_x_kNm)
    uniax_y_ok = (Muy <= 1.0e-9) or (phiMn_y_kNm is not None and Muy <= phiMn_y_kNm)

    # ---- Bresler reciprocal-load (only when both moments act) ----
    biaxial = None
    biaxial_ok = True
    if Mux > 1.0e-9 and Muy > 1.0e-9 and Pu_N > 1.0e-6:
        ex = (Mux * 1.0e6) / Pu_N                       # mm
        ey = (Muy * 1.0e6) / Pu_N
        Pnx = _Pn_at_ecc(nom_x, ex)
        Pny = _Pn_at_ecc(nom_y, ey)
        if Pnx and Pny and Pnx > 0 and Pny > 0:
            inv = 1.0 / Pnx + 1.0 / Pny - 1.0 / Po
            Pn_bi = 1.0 / inv if inv > 0 else float("inf")
            phiPn_bi = min(PHI_CC * Pn_bi, phiPn_max)
            biaxial_ok = phiPn_bi >= Pu_N
            biaxial = {
                "ex_mm": ex, "ey_mm": ey,
                "Pnx_kN": Pnx / 1000.0, "Pny_kN": Pny / 1000.0,
                "Po_kN": Po / 1000.0, "Pn_bi_kN": Pn_bi / 1000.0,
                "phiPn_bi_kN": phiPn_bi / 1000.0,
            }
        else:
            biaxial_ok = uniax_x_ok and uniax_y_ok       # fallback
    else:
        biaxial_ok = uniax_x_ok and uniax_y_ok

    passed = ratio_ok and axial_max_ok and biaxial_ok

    # ------------------------------------------------------------------
    # Calculation steps
    # ------------------------------------------------------------------
    st.subheader("ขั้นตอนการคำนวณ")
    st.markdown(
        f"""
| รายการ | ค่า |
|---|---|
| พื้นที่หน้าตัดรวม Ag = b·h | {Ag / 100.0:,.2f} cm² |
| จำนวนเหล็กเสริม = 2(n_x + n_y − 2) = 2({n_x}+{n_y}−2) | **{total_bars} เส้น** |
| พื้นที่เหล็กเสริมทั้งหมด Ast = {total_bars} × {As_bar / 100.0:,.2f} | **{Ast / 100.0:,.2f} cm²** |
| อัตราส่วนเหล็กเสริม ρg = Ast / Ag | **{rho_g * 100.0:,.2f}%**  (ยอมให้ {RHO_MIN * 100:.0f}–{RHO_MAX * 100:.0f}%) |
| กำลังรับแรงตามแนวแกนล้วน Po = 0.85f'c(Ag−Ast) + fy·Ast | {Po / 1000.0 * KN_TO_KGF:,.0f} kgf |
| ขีดจำกัดแรงตามแนวแกน φPn,max = 0.80·φ·Po | **{phiPn_max_kN * KN_TO_KGF:,.0f} kgf** |
| กำลังโมเมนต์ออกแบบรอบแกน X ที่ Pu, φMn,x | {("—" if phiMn_x_kNm is None else f"{phiMn_x_kNm * KN_TO_KGF:,.0f} kgf-m")} |
| กำลังโมเมนต์ออกแบบรอบแกน Y ที่ Pu, φMn,y | {("—" if phiMn_y_kNm is None else f"{phiMn_y_kNm * KN_TO_KGF:,.0f} kgf-m")} |
"""
    )

    if biaxial is not None:
        st.markdown("**Bresler Reciprocal Load**")
        st.markdown(
            f"""
| รายการ | ค่า |
|---|---|
| ระยะเยื้องศูนย์ ex = Mux/Pu | {biaxial['ex_mm'] / CM:,.2f} cm |
| ระยะเยื้องศูนย์ ey = Muy/Pu | {biaxial['ey_mm'] / CM:,.2f} cm |
| Pnx (ดัดรอบแกน X ที่ ex) | {biaxial['Pnx_kN'] * KN_TO_KGF:,.0f} kgf |
| Pny (ดัดรอบแกน Y ที่ ey) | {biaxial['Pny_kN'] * KN_TO_KGF:,.0f} kgf |
| 1/Pn,biaxial = 1/Pnx + 1/Pny − 1/Po | {biaxial['Pn_bi_kN'] * KN_TO_KGF:,.0f} kgf |
| φPn,biaxial | **{biaxial['phiPn_bi_kN'] * KN_TO_KGF:,.0f} kgf**  (Pu = {Pu * KN_TO_KGF:,.0f} kgf) |
"""
        )

    # ------------------------------------------------------------------
    # Drawing — section + interaction diagram
    # ------------------------------------------------------------------
    section_img = None
    try:
        section_img = draw_column_pm_and_section(
            b, h, cc, main_dia, coords,
            [(m / 1.0e6 * KN_TO_KGF, p / 1000.0 * KN_TO_KGF) for (m, p) in dsn_x],
            [(m / 1.0e6 * KN_TO_KGF, p / 1000.0 * KN_TO_KGF) for (m, p) in dsn_y],
            Pu * KN_TO_KGF, Mux * KN_TO_KGF, Muy * KN_TO_KGF,
            phiPn_max_kN * KN_TO_KGF,
            bar_label=f"{total_bars} - {main_size}",
            tie_label=f"ปลอก {stir_size}",
            tie_cover_mm=covering,
        )
        st.image(section_img,
                 caption="หน้าตัดเสา + แผนภาพปฏิสัมพันธ์ P-M (Section + Interaction Diagram)")
    except Exception as exc:  # pragma: no cover
        st.warning(f"ไม่สามารถสร้างภาพได้: {exc}")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    st.subheader("ผลการตรวจสอบ")

    def _s(ok):
        return "✅ ผ่าน" if ok else "❌ ไม่ผ่าน"

    if Mux > 1e-9 and Muy > 1e-9:
        moment_row = (
            f"| การตรวจสอบสองแกน (Bresler) φPn,biaxial ≥ Pu | "
            f"{('%.0f' % (biaxial['phiPn_bi_kN'] * KN_TO_KGF)) if biaxial else '—'} ≥ "
            f"{Pu * KN_TO_KGF:,.0f} kgf | {_s(biaxial_ok)} |")
    elif Mux > 1e-9:
        moment_row = (
            f"| การตรวจสอบรอบแกน X: φMn,x ≥ Mux | "
            f"{('%.0f' % (phiMn_x_kNm * KN_TO_KGF)) if phiMn_x_kNm is not None else '—'} ≥ "
            f"{Mux * KN_TO_KGF:,.0f} kgf-m | {_s(uniax_x_ok)} |")
    elif Muy > 1e-9:
        moment_row = (
            f"| การตรวจสอบรอบแกน Y: φMn,y ≥ Muy | "
            f"{('%.0f' % (phiMn_y_kNm * KN_TO_KGF)) if phiMn_y_kNm is not None else '—'} ≥ "
            f"{Muy * KN_TO_KGF:,.0f} kgf-m | {_s(uniax_y_ok)} |")
    else:
        moment_row = f"| ไม่มีโมเมนต์ (แรงตามแนวแกนล้วน) | — | {_s(True)} |"

    st.markdown(
        f"""
| การตรวจสอบ | ค่า | สถานะ |
|---|---|---|
| อัตราส่วนเหล็กเสริม ρg | {rho_g * 100.0:,.2f}% (1–8%) | {_s(ratio_ok)} |
| ขีดจำกัดแรงตามแนวแกน Pu ≤ φPn,max | {Pu * KN_TO_KGF:,.0f} ≤ {phiPn_max_kN * KN_TO_KGF:,.0f} kgf | {_s(axial_max_ok)} |
{moment_row}
"""
    )

    if passed:
        st.success(f"{PASS_TXT} — เสารับแรง Pu, Mux, Muy ได้อย่างปลอดภัย")

        if not FONT_AVAILABLE:
            st.warning(font_status_message())

        pdf_bytes = generate_column_report(
            {
                "Pu": Pu, "Mux": Mux, "Muy": Muy,
                "b": b, "h": h, "covering": covering, "fc": fc, "fy": fy,
                "main_size": main_size, "n_x": n_x, "n_y": n_y,
                "total_bars": total_bars,
                "stirrup_size": stir_size, "stirrup_sp_cm": stir_sp_cm,
                "project": get_project_info(),
            },
            {
                "Ag": Ag, "Ast": Ast, "rho_g": rho_g,
                "Po_kN": Po / 1000.0, "phiPn_max_kN": phiPn_max_kN,
                "phiMn_x_kNm": phiMn_x_kNm, "phiMn_y_kNm": phiMn_y_kNm,
                "biaxial": biaxial,
                "ratio_ok": ratio_ok, "axial_max_ok": axial_max_ok,
                "uniax_x_ok": uniax_x_ok, "uniax_y_ok": uniax_y_ok,
                "biaxial_ok": biaxial_ok,
                "section_img": section_img, "status": "PASS",
            },
        )
        st.download_button(
            "ดาวน์โหลดรายงานการคำนวณ",
            data=pdf_bytes,
            file_name="column_pm_report.pdf",
            mime="application/pdf",
        )
    else:
        reasons = []
        if not ratio_ok:
            reasons.append(f"ρg = {rho_g * 100:,.2f}% อยู่นอกช่วง 1–8%")
        if not axial_max_ok:
            reasons.append(
                f"Pu = {Pu * KN_TO_KGF:,.0f} kgf > "
                f"φPn,max = {phiPn_max_kN * KN_TO_KGF:,.0f} kgf"
            )
        if not biaxial_ok:
            reasons.append("กำลังรับโมเมนต์/สองแกนไม่เพียงพอ")
        st.error(f"{FAIL_TXT} — " + "; ".join(reasons))


if __name__ == "__main__":
    render_column_module()
