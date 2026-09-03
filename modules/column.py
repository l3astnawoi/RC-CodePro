"""Streamlit UI — RC rectangular / circular column: uniaxial P-M design.

Strain-compatibility method (ACI 318M-08 10.2 / 10.3):
    * sweep the neutral-axis depth c, εcu = 0.003
    * build ONE single-axis nominal and design (φ) P-M interaction curve
    * φ (tied) interpolates 0.65 -> 0.90 with the net tensile strain εt
      (0.75 -> 0.90 for spiral columns)
    * axial cap  Pu,max = α φ [0.85 f'c (Ag - Ast) + fy Ast]
      (α = 0.80 tied, 0.85 spiral)
    * verdict = the demand point (Mu, Pu) lies inside the design P-M curve

The current implementation is UNIAXIAL only — a single moment demand Mu
checked against a single-axis interaction curve.  Biaxial X/Y interaction
and the Bresler reciprocal-load method are NOT implemented.

UI units: cm / ksc / kgf ; converted to mm / MPa / N internally.
"""

import math

import numpy as np
import streamlit as st

from utils import ui
from utils.aci_318m import get_beta1, rebars, bar_area
from utils.drawing import (draw_column_pm_and_section, draw_column_detail,
                           draw_pm_diagram, fig_to_png_buf)
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
    """Column Design — RC CodePro visual language (same as Beam).

    Full-width flow: the P-M interaction diagram and the cross-section
    detail need the width, so the Design Summary is a horizontal band near
    the top rather than a right rail.  All engineering logic is unchanged.
    """
    ui.breadcrumb("Member Design", "Column")
    ui.page_header("Column Design", "Axial + Flexural Design — ACI 318M-08")

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


ES_KSC = 2040000.0            # steel modulus in ksc (~= 200,000 MPa)
EPS_CU_COL = 0.003           # ultimate concrete strain


def _beta1_col_ksc(fc_ksc):
    """beta1 stress-block factor, ACI 318M-08 10.2.7.3, MKS form."""
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def _col_bar_xy(shape, b, h, D, cov, tie_dia, main_dia, n):
    """Main-bar centre coordinates (cm, section-centre origin), matching the
    layout used by ``draw_column_detail``."""
    n = max(int(n), 4)
    if shape == "circ":
        Rb = D / 2.0 - cov - tie_dia - main_dia / 2.0
        return [(Rb * math.cos(math.pi / 2.0 - 2.0 * math.pi * k / n),
                 Rb * math.sin(math.pi / 2.0 - 2.0 * math.pi * k / n))
                for k in range(n)]
    x0 = -b / 2.0 + cov + tie_dia + main_dia / 2.0
    y0 = -h / 2.0 + cov + tie_dia + main_dia / 2.0
    x1, y1 = -x0, -y0
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    seg = [x1 - x0, y1 - y0, x1 - x0, y1 - y0]
    per = sum(seg) or 1.0
    out = []
    for i in range(n):
        dwalk = per * i / n
        for sidx in range(4):
            if dwalk <= seg[sidx] or sidx == 3:
                (ax, ay), (bx, by) = corners[sidx], corners[(sidx + 1) % 4]
                tt = (dwalk / seg[sidx]) if seg[sidx] else 0.0
                out.append((ax + (bx - ax) * tt, ay + (by - ay) * tt))
                break
            dwalk -= seg[sidx]
    return out


def _whitney_area_centroid(shape, a, b, D, H):
    """Whitney compression-block area (cm2) and its centroid distance above
    the section centre (cm) for a block depth ``a`` from the extreme
    compression fibre (the +y face)."""
    if shape == "circ":
        r = D / 2.0
        a = min(max(a, 0.0), 2.0 * r)
        if a <= 0.0:
            return 0.0, 0.0
        if a >= 2.0 * r:
            return math.pi * r * r, 0.0
        al = math.acos(max(-1.0, min(1.0, (r - a) / r)))
        denom = al - math.sin(al) * math.cos(al)
        area = r * r * denom
        ybar = ((2.0 * r * math.sin(al) ** 3) / (3.0 * denom)
                if denom > 1.0e-9 else r - a / 2.0)
        return area, ybar
    a = min(max(a, 0.0), H)
    return b * a, H / 2.0 - a / 2.0


def _calculate_pm_curve(*, shape, b, h, D, fc, fy, bars, Ab, spiral,
                        n_pts=44):
    """Strain-compatibility P-M interaction curve, MKS (ksc / cm / kgf).

    bars : [(x_cm, y_cm), ...] from the section centre, +y toward the
           extreme compression fibre.  Ab : one main-bar area (cm2).
    Returns (Mn, Pn, phiMn, phiPn) — numpy arrays, kgf-m and kgf, ordered
    from pure compression to pure tension (a closed polygon on M = 0).
    """
    H = D if shape == "circ" else h
    Ag = (math.pi * D * D / 4.0) if shape == "circ" else b * h
    Ast = len(bars) * Ab
    beta1 = _beta1_col_ksc(fc)
    ys = np.array([p[1] for p in bars], dtype=float)
    d_i = H / 2.0 - ys                                 # depth from comp. face
    d_max = float(d_i.max())                           # extreme tension layer
    eps_y = fy / ES_KSC
    phi0 = 0.75 if spiral else 0.65
    alpha = 0.85 if spiral else 0.80

    Mn_l, Pn_l, pMn_l, pPn_l = [], [], [], []
    for c in np.linspace(1.5 * H, 0.001 * H, int(n_pts)):
        a = min(beta1 * c, H)
        Acc, y_cc = _whitney_area_centroid(shape, a, b, D, H)
        Cc = 0.85 * fc * Acc                           # kgf, compression +ve
        eps_s = EPS_CU_COL * (c - d_i) / c
        fs = np.clip(eps_s * ES_KSC, -fy, fy)          # ksc
        in_block = d_i <= a
        fs = np.where((fs > 0.0) & in_block, fs - 0.85 * fc, fs)
        Fs = Ab * fs                                   # kgf per bar
        Pn = Cc + float(Fs.sum())                      # kgf
        Mn = (Cc * y_cc + float((Fs * ys).sum())) / 100.0   # kgf-m, about centre
        eps_t = EPS_CU_COL * (d_max - c) / c           # +ve = tension
        if eps_t <= eps_y:
            ph = phi0
        elif eps_t >= 0.005:
            ph = 0.90
        else:
            ph = phi0 + (0.90 - phi0) * (eps_t - eps_y) / (0.005 - eps_y)
        Mn_l.append(abs(Mn))
        Pn_l.append(Pn)
        pMn_l.append(ph * abs(Mn))
        pPn_l.append(ph * Pn)

    Po = 0.85 * fc * (Ag - Ast) + fy * Ast             # kgf, pure compression
    Pt = -fy * Ast                                     # kgf, pure tension
    cap = alpha * phi0 * Po                            # ACI 10.3.6 design cap

    Mn = np.concatenate(([0.0], Mn_l, [0.0]))
    Pn = np.concatenate(([Po], np.minimum(Pn_l, Po), [Pt]))
    phiMn = np.concatenate(([0.0], pMn_l, [0.0]))
    phiPn = np.concatenate(([cap], np.minimum(pPn_l, cap), [0.90 * Pt]))
    return Mn, Pn, phiMn, phiPn


def _point_in_poly(px, py, xs, ys):
    """Even-odd ray-casting point-in-polygon test."""
    n = len(xs)
    inside = False
    j = n - 1
    for i in range(n):
        yi, yj = ys[i], ys[j]
        if ((yi > py) != (yj > py)):
            xint = (xs[j] - xs[i]) * (py - yi) / ((yj - yi) or 1.0e-12) + xs[i]
            if px < xint:
                inside = not inside
        j = i
    return inside


def _render_column():
    st.caption("ตรวจสอบอัตราส่วนเหล็กเสริม ρg, กำลังรับแรงตามแนวแกน φPn,max, "
               "ปฏิสัมพันธ์ P-M และระยะเรียงเหล็กปลอก/เหล็กเกลียว ตามมาตรฐาน "
               "ACI 318M-08 — หน่วยเมตริก (cm, kgf, kgf-m, ksc)")

    shape = st.selectbox("ประเภทเสา (Column Type)", COL_SHAPES, key="cd_shape")
    circular = shape.startswith("Circular")

    # -- optional: pull a governing Pu from the Building Model takedown --
    _groups = st.session_state.get("column_design_groups") or {}
    if _groups:
        with st.expander("📥 ดึงแรงจากโมเดลอาคาร (Import Pu from Building Model)",
                         expanded=False):
            g1, g2 = st.columns([2, 1])
            with g1:
                _mark = st.selectbox("เลือกเบอร์เสา (Column Mark)",
                                     list(_groups.keys()), key="cd_import_mark")
            with g2:
                st.write("")
                if st.button("เติมค่า Pu อัตโนมัติ", key="cd_import_btn"):
                    st.session_state["cd_Pu"] = float(
                        _groups[_mark]["Pu_kgf"])
                    st.rerun()
            _gi = _groups.get(_mark, {})
            st.caption(
                f"เบอร์ {_mark}: เสาควบคุม {_gi.get('governing_grid', '-')} · "
                f"Pu = {_gi.get('Pu_kgf', 0):,.0f} kgf"
            )

    st.markdown("#### MEMBER INPUT")

    # ------------------------------------------------------------------
    # 1a. Geometry  (widget keys / defaults unchanged)
    # ------------------------------------------------------------------
    with ui.section_card("GEOMETRY — เรขาคณิตหน้าตัด"):
        if circular:
            gc1, gc2 = st.columns(2)
            with gc1:
                D_cm = st.number_input("เส้นผ่านศูนย์กลาง D (cm)",
                                       min_value=20.0, value=45.0, step=1.0,
                                       format="%.1f", key="cd_D")
            b_cm = h_cm = float(D_cm)
            with gc2:
                cov_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=2.0,
                                         value=4.0, step=0.5, format="%.1f",
                                         key="cd_cov")
        else:
            gc1, gc2, gc3 = st.columns(3)
            with gc1:
                b_cm = st.number_input("ความกว้าง b (cm)", min_value=20.0,
                                       value=40.0, step=1.0, format="%.1f",
                                       key="cd_b")
            with gc2:
                h_cm = st.number_input("ความลึก h (cm)", min_value=20.0,
                                       value=40.0, step=1.0, format="%.1f",
                                       key="cd_h")
            D_cm = None
            with gc3:
                cov_cm = st.number_input("ระยะหุ้มคอนกรีต (cm)", min_value=2.0,
                                         value=4.0, step=0.5, format="%.1f",
                                         key="cd_cov")

    # ------------------------------------------------------------------
    # 1b. Material  (widget keys / defaults unchanged)
    # ------------------------------------------------------------------
    with ui.section_card("MATERIAL — วัสดุ"):
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            fc_ksc = st.number_input("f'c (ksc)", min_value=180, value=240,
                                     step=10, format="%d", key="cd_fc")
        with mc2:
            fy_ksc = st.number_input("fy เหล็กหลัก (ksc)", min_value=2400,
                                     value=4000, step=100, format="%d",
                                     key="cd_fy")
        with mc3:
            fyv_ksc = st.number_input("fyv ปลอก/เกลียว (ksc)", min_value=2400,
                                      value=2400, step=100, format="%d",
                                      key="cd_fyv")

    # ------------------------------------------------------------------
    # 2. Loads
    # ------------------------------------------------------------------
    with ui.section_card("LOADS — แรงกระทำ"):
        lc1, lc2 = st.columns(2)
        with lc1:
            _pu_kw = {} if "cd_Pu" in st.session_state else {"value": 180000.0}
            Pu = st.number_input("แรงตามแนวแกนประลัย Pu (kgf)", min_value=0.0,
                                 step=1000.0, key="cd_Pu", **_pu_kw)
        with lc2:
            Mu = st.number_input(
                "โมเมนต์ดัดประลัย Mu (kgf-m)", min_value=0.0, value=6000.0,
                step=100.0, key="cd_Mu",
                help="โมเมนต์ดัดที่กระทำ — ใช้ตรวจสอบจุด (Mu, Pu) "
                     "กับเส้นปฏิสัมพันธ์ P-M (แกนเดียว)")

    # ------------------------------------------------------------------
    # 3. Reinforcement
    # ------------------------------------------------------------------
    with ui.section_card("REINFORCEMENT — เหล็กเสริม"):
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            main_size = st.selectbox("เหล็กเสริมหลัก — ขนาด", MAIN_SIZES,
                                     index=MAIN_SIZES.index("DB20"),
                                     key="cd_msz")
        with rc2:
            n_bars = int(st.number_input(
                "จำนวนเหล็กเสริมหลักทั้งหมด (เส้น)",
                min_value=(6 if circular else 4),
                value=(8 if circular else 8), step=(2 if circular else 1),
                key="cd_nbar"))
        with rc3:
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

    # ------------------------------------------------------------------
    # Check 4 — full P-M interaction (strain-compatibility, ACI 318M-08)
    # ------------------------------------------------------------------
    _shape_key = "circ" if circular else "rect"
    bars_xy = _col_bar_xy(_shape_key, b, h, D, cov, tie_dia, main_dia, n_bars)
    Mn_c, Pn_c, phiMn_c, phiPn_c = _calculate_pm_curve(
        shape=_shape_key, b=b, h=h, D=D, fc=fc, fy=fy, bars=bars_xy, Ab=Ab,
        spiral=circular)
    pm_ok = _point_in_poly(Mu, Pu, phiMn_c, phiPn_c)
    # nearest design capacity at the demand axial level (for the readout)
    _pP = np.asarray(phiPn_c)
    _msk = np.abs(_pP - Pu) <= (0.06 * max(abs(_pP).max(), 1.0))
    phiMn_at_Pu = float(np.asarray(phiMn_c)[_msk].max()) if _msk.any() else \
        float(np.interp(Pu, _pP[::-1], np.asarray(phiMn_c)[::-1]))

    passed = ratio_ok and axial_ok and spacing_ok and pm_ok

    # ==================================================================
    # DESIGN SUMMARY  (reads existing verdict + existing values only)
    # ==================================================================
    st.markdown("#### DESIGN SUMMARY")
    with st.container(border=True):
        sc_status, sc_util = st.columns([1, 2])
        with sc_status:
            st.markdown("**STATUS**")
            ui.status_badge("pass" if passed else "fail",
                            "PASS" if passed else "FAIL")
        with sc_util:
            st.markdown("**UTILIZATION** (demand / capacity)")
            ui.utilization("แรงตามแนวแกน  Pu / φPn,max", Pu, phiPn_max)
            ui.utilization("โมเมนต์  Mu / φMn@Pu", Mu, phiMn_at_Pu)

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            ui.kpi("φPn,max (kgf)", f"{phiPn_max:,.0f}")
        with k2:
            ui.kpi("φMn @ Pu (kgf-m)", f"{phiMn_at_Pu:,.0f}")
        with k3:
            ui.kpi("ρg (%)", f"{rho_g * 100.0:,.2f}")
        with k4:
            ui.kpi("S แนะนำ (cm)", f"≤ {S_req:,.1f}")

        b_ratio, b_axial, b_pm, b_tie = st.columns(4)
        with b_ratio:
            st.caption("อัตราส่วนเหล็ก ρg")
            ui.status_badge(bool(ratio_ok))
        with b_axial:
            st.caption("แรงตามแนวแกน")
            ui.status_badge(bool(axial_ok))
        with b_pm:
            st.caption("ปฏิสัมพันธ์ P-M")
            ui.status_badge(bool(pm_ok))
        with b_tie:
            st.caption("ระยะเรียงเหล็กขวาง")
            ui.status_badge(bool(spacing_ok))

    # ==================================================================
    # DESIGN CHECKS  (existing demand/capacity tuples — one source,
    # rendered here and passed unchanged to the PDF report)
    # ==================================================================
    st.markdown("#### DESIGN CHECKS — ผลการตรวจสอบ")
    checks = [
        ("อัตราส่วนเหล็ก ρg (1–8%)", f"{rho_g * 100:,.2f} %",
         "1.00 – 8.00 %", ratio_ok),
        ("ปฏิสัมพันธ์ P-M — (Mu, Pu) ในเส้นออกแบบ",
         f"Mu = {Mu:,.0f} kgf-m", f"φMn ≈ {phiMn_at_Pu:,.0f} kgf-m", pm_ok),
        ("กำลังตามแนวแกน (φPn,max ≥ Pu)", f"{Pu:,.0f} kgf",
         f"{phiPn_max:,.0f} kgf", axial_ok),
        (("ระยะพิตช์เหล็กเกลียว" if circular else "ระยะเรียงเหล็กปลอก"),
         f"S ≤ {S_req:,.1f} cm",
         f"{'พิตช์ 2.5–7.5 cm' if circular else f'≤ {least_dim:,.0f} cm'}",
         spacing_ok),
    ]
    ui.engineering_table(
        ["รายการตรวจสอบ", "Demand", "Capacity", "สถานะ"],
        [[name, dem, cap, "ผ่าน (PASS)" if ok else "ไม่ผ่าน (FAIL)"]
         for name, dem, cap, ok in checks],
        right_from=1,
    )
    if not ratio_ok:
        side = "ต่ำกว่า 1%" if rho_g < RHO_MIN else "เกิน 8%"
        st.warning(f"ρg {side} — ปรับจำนวน/ขนาดเหล็ก หรือขนาดหน้าตัด")
    if circular and not spacing_ok:
        st.warning("พิตช์ที่ต้องใช้ < 2.5 cm — เพิ่มขนาดเหล็กเกลียว")

    # ---- overall verdict (existing logic, existing text) -------------
    if passed:
        st.success(f"{PASS_TXT} — ρg, ปฏิสัมพันธ์ P-M, φPn,max ≥ Pu และ"
                   f"ระยะเรียงเหล็กขวางผ่านเกณฑ์")
    else:
        fails = []
        if not ratio_ok:
            fails.append(f"ρg = {rho_g * 100:,.2f}% นอกช่วง 1–8%")
        if not pm_ok:
            fails.append("จุด (Mu, Pu) อยู่นอกเส้นออกแบบ P-M (เกินกำลัง)")
        if not axial_ok:
            fails.append(f"Pu = {Pu:,.0f} > φPn,max = {phiPn_max:,.0f} kgf")
        if not spacing_ok:
            fails.append("ระยะเรียงเหล็กขวางไม่ผ่านเกณฑ์")
        st.error(f"{FAIL_TXT} — " + "; ".join(fails))

    # ---- step-by-step derivation (existing table, collapsed) --------
    with st.expander("รายละเอียดการคำนวณทีละขั้น (Detailed calculation)",
                     expanded=False):
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
| แรงประลัยที่กระทำ (Pu , Mu) | {Pu:,.0f} kgf , {Mu:,.0f} kgf-m |
| กำลังโมเมนต์ออกแบบที่ระดับ Pu (φMn) | **≈ {phiMn_at_Pu:,.0f} kgf-m** |
| จุด (Mu, Pu) อยู่ภายในเส้นออกแบบ P-M | {"ใช่ (ปลอดภัย)" if pm_ok else "ไม่ (เกินกำลัง)"} |
| ระยะเรียง{"เหล็กเกลียว (พิตช์)" if circular else "เหล็กปลอก"} ที่แนะนำ S | **≤ {S_req:,.1f} cm** |
| เกณฑ์ระยะเรียง | {spacing_note} |
"""
        )

    # ==================================================================
    # DRAWING / DETAIL  (drawing engine + geometry unchanged)
    # ==================================================================
    st.markdown("#### DRAWING / DETAIL — รายละเอียดหน้าตัดเสา")
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

    # ==================================================================
    # INTERACTION / CAPACITY DIAGRAM  (curve data + plotting unchanged)
    # ==================================================================
    st.markdown("#### INTERACTION / CAPACITY DIAGRAM — แผนภาพ P-M")
    pm_img = None
    try:
        pm_fig = draw_pm_diagram(Mn_c, Pn_c, phiMn_c, phiPn_c, Mu, Pu)
        st.pyplot(pm_fig, use_container_width=True)
        st.caption("แผนภาพปฏิสัมพันธ์ P-M (P-M Interaction Diagram)")
        pm_img = fig_to_png_buf(pm_fig)
    except Exception as exc:  # pragma: no cover
        st.warning(f"ไม่สามารถสร้างแผนภาพ P-M ได้: {exc}")

    # ------------------------------------------------------------------
    # ==================================================================
    # OUTPUT / REPORT  (report engine unchanged)
    # ==================================================================
    st.markdown("#### OUTPUT / REPORT — รายงานการคำนวณ")
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
            ("โมเมนต์ดัด Mu", Mu, "kgf-m", 0),
            ("พื้นที่หน้าตัดรวม Ag", Ag, "cm²", 1),
            ("พื้นที่เหล็กเสริม Ast", Ast, "cm²", 2),
        ],
        checks=checks,
        figures=[
            ("รายละเอียดหน้าตัดเสา (Column Cross-Section)", section_img),
            ("แผนภาพปฏิสัมพันธ์ P-M (P-M Interaction Diagram)", pm_img),
        ],
        status=passed,
        summary=("ρg, ปฏิสัมพันธ์ P-M, φPn,max ≥ Pu และระยะเรียงเหล็กขวางผ่าน"
                 "เกณฑ์ ACI 318M-08" if passed
                 else "มีรายการไม่ผ่าน — โปรดตรวจสอบตารางการตรวจสอบ"))


if __name__ == "__main__":
    render_column_module()
