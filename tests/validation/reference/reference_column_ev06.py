"""EV-06 — Independent COLUMN P-M / axial validation reference.

Independent validation reference — NOT production calculation code.
Imports only ``math``.  No ``utils.*``, no ``modules.*``, and no call to
any production P-M function.

Re-implements, from ACI 318M-08 strain compatibility + the equivalent
rectangular stress block, a rectangular tied column P-M interaction:

    * neutral-axis sweep, eps_cu = 0.003
    * layer strains  eps_s = eps_cu (c - d_i) / c
    * layer stress   fs = clip(eps_s Es, -fy, fy) ;  bars inside the
      stress block have 0.85 f'c subtracted (displaced concrete)
    * Cc = 0.85 f'c * (b * min(a, H)) ,  a = beta1 c
    * Pn = Cc + Sum(Ab fs_i)
    * Mn = ( Cc * (H/2 - a/2) + Sum(Ab fs_i y_i) ) / 100      [kgf-m]
    * eps_t at the extreme tension layer -> phi (ACI 9.3.2, tied)
    * anchors: Po, design cap 0.80*0.65*Po, Pt = -fy Ast, 0.90 Pt

MKS unit system: ksc / cm / kgf / kgf-m  (matching _calculate_pm_curve).
"""

import math

EPS_CU = 0.003
ES_KSC = 2040000.0        # steel modulus, ksc  (~200 GPa)
EPS_TC = 0.005            # ACI 10.3.4 tension-controlled
PHI_CC_TIED = 0.65
PHI_TC = 0.90


def beta1_ksc(fc_ksc):
    """ACI 10.2.7.3, MKS-literal form (280 ksc break) — matches the engine
    (`_beta1_col_ksc`).  VF-07 tracks the 280 ksc vs 28 MPa (285.5 ksc)
    choice; it is a conservative metric convention, not a defect."""
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def phi_from_eps_t(eps_t, fy_ksc, spiral=False):
    """ACI 9.3.2 strength-reduction factor from the net tensile strain.
    Compression-controlled limit = eps_ty = fy / Es (ACI 10.3.3, the
    engine uses this exact form, not the 0.002 literal used in beam/slab).
    """
    phi0 = 0.75 if spiral else PHI_CC_TIED
    eps_ty = fy_ksc / ES_KSC
    if eps_t <= eps_ty:
        return phi0
    if eps_t >= EPS_TC:
        return PHI_TC
    return phi0 + (PHI_TC - phi0) * (eps_t - eps_ty) / (EPS_TC - eps_ty)


def rect_bar_xy(b_cm, h_cm, cov_cm, tie_dia_cm, main_dia_cm, n):
    """Independent reproduction of `_col_bar_xy('rect', ...)` — n bars walked
    around the tie perimeter, section-centre origin, +y toward the
    compression face."""
    n = max(int(n), 4)
    x0 = -b_cm / 2.0 + cov_cm + tie_dia_cm + main_dia_cm / 2.0
    y0 = -h_cm / 2.0 + cov_cm + tie_dia_cm + main_dia_cm / 2.0
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


def axial_anchors(fc_ksc, fy_ksc, b_cm, h_cm, n_bars, Ab_cm2, tied=True):
    Ag = b_cm * h_cm
    Ast = n_bars * Ab_cm2
    Po = 0.85 * fc_ksc * (Ag - Ast) + fy_ksc * Ast          # kgf
    alpha, phi0 = (0.80, 0.65) if tied else (0.85, 0.75)
    return {
        "Ag_cm2": Ag, "Ast_cm2": Ast,
        "Po_kgf": Po,
        "phiPn_max_kgf": alpha * phi0 * Po,                 # ACI 10.3.6.2
        "Pnt_kgf": -fy_ksc * Ast,
        "phiPnt_kgf": 0.90 * (-fy_ksc * Ast),
    }


def pm_point(*, c_cm, fc_ksc, fy_ksc, b_cm, h_cm, bars, Ab_cm2, spiral=False):
    """Full strain-compatibility state at a given neutral-axis depth c
    (from the extreme compression fibre).  Returns Pn, Mn (folded to |Mn|
    like the engine), eps_t, phi, phiPn, phiMn, and the equilibrium
    residual for cross-checking.
    """
    H = h_cm
    beta1 = beta1_ksc(fc_ksc)
    a = min(beta1 * c_cm, H)
    Acc = b_cm * a
    y_cc = H / 2.0 - a / 2.0
    Cc = 0.85 * fc_ksc * Acc                                # kgf

    ys = [p[1] for p in bars]
    d_i = [H / 2.0 - y for y in ys]                         # depth from comp face
    d_max = max(d_i)

    Fs = []
    for di in d_i:
        eps_s = EPS_CU * (c_cm - di) / c_cm
        fs = max(-fy_ksc, min(fy_ksc, eps_s * ES_KSC))      # ksc
        if fs > 0.0 and di <= a:
            fs -= 0.85 * fc_ksc
        Fs.append(Ab_cm2 * fs)                              # kgf per bar

    Pn = Cc + sum(Fs)
    Mn = (Cc * y_cc + sum(f * y for f, y in zip(Fs, ys))) / 100.0   # kgf-m
    eps_t = EPS_CU * (d_max - c_cm) / c_cm
    phi = phi_from_eps_t(eps_t, fy_ksc, spiral)

    # equilibrium cross-check: C (concrete + comp steel) - T (tension steel) = Pn
    C_tot = Cc + sum(f for f in Fs if f > 0.0)
    T_tot = -sum(f for f in Fs if f < 0.0)
    return {
        "c_cm": c_cm, "a_cm": a, "beta1": beta1,
        "Acc_cm2": Acc, "y_cc_cm": y_cc, "Cc_kgf": Cc,
        "Fs_kgf": Fs, "Pn_kgf": Pn, "Mn_kgfm": abs(Mn),
        "eps_t": eps_t, "phi": phi,
        "phiPn_kgf": phi * Pn, "phiMn_kgfm": phi * abs(Mn),
        "C_tot_kgf": C_tot, "T_tot_kgf": T_tot,
        "equil_residual_kgf": (C_tot - T_tot) - Pn,
    }


def balanced_point(*, fc_ksc, fy_ksc, b_cm, h_cm, bars, Ab_cm2):
    """The balanced point: extreme tension steel exactly at yield strain.
        c_b = eps_cu / (eps_cu + eps_y) * d_t
    where d_t is the depth of the extreme tension layer.  Analytically
    traceable -> a hand anchor for the interior of the curve.
    """
    H = h_cm
    d_t = max(H / 2.0 - p[1] for p in bars)
    eps_y = fy_ksc / ES_KSC
    c_b = EPS_CU / (EPS_CU + eps_y) * d_t
    pt = pm_point(c_cm=c_b, fc_ksc=fc_ksc, fy_ksc=fy_ksc, b_cm=b_cm,
                  h_cm=h_cm, bars=bars, Ab_cm2=Ab_cm2)
    pt["d_t_cm"] = d_t
    pt["eps_y"] = eps_y
    pt["c_b_cm"] = c_b
    return pt


def pm_curve(*, fc_ksc, fy_ksc, b_cm, h_cm, bars, Ab_cm2, spiral=False,
             n_pts=44):
    """Independent P-M curve on the SAME neutral-axis sweep the engine uses
    (linspace(1.5H, 0.001H, n_pts)) so points can be compared 1:1, plus the
    prepended/appended anchors.  The sweep grid is just sampling -- using
    the same grid is not circular (the physics at each c is recomputed
    here independently)."""
    H = h_cm
    xs_c = [1.5 * H + (0.001 * H - 1.5 * H) * i / (n_pts - 1)
            for i in range(n_pts)]
    pts = [pm_point(c_cm=c, fc_ksc=fc_ksc, fy_ksc=fy_ksc, b_cm=b_cm,
                    h_cm=h_cm, bars=bars, Ab_cm2=Ab_cm2, spiral=spiral)
           for c in xs_c]
    an = axial_anchors(fc_ksc, fy_ksc, b_cm, h_cm, len(bars), Ab_cm2,
                       tied=not spiral)
    Po, cap = an["Po_kgf"], an["phiPn_max_kgf"]
    Pt, phiPt = an["Pnt_kgf"], an["phiPnt_kgf"]

    Mn = [0.0] + [p["Mn_kgfm"] for p in pts] + [0.0]
    Pn = [Po] + [min(p["Pn_kgf"], Po) for p in pts] + [Pt]
    phiMn = [0.0] + [p["phiMn_kgfm"] for p in pts] + [0.0]
    phiPn = [cap] + [min(p["phiPn_kgf"], cap) for p in pts] + [phiPt]
    return {"Mn": Mn, "Pn": Pn, "phiMn": phiMn, "phiPn": phiPn,
            "points": pts, "anchors": an, "c_grid": xs_c}


def point_in_poly(px, py, xs, ys):
    """Independent even-odd ray-cast (for cross-checking `_point_in_poly`)."""
    n = len(xs)
    inside = False
    j = n - 1
    for i in range(n):
        yi, yj = ys[i], ys[j]
        if (yi > py) != (yj > py):
            xint = (xs[j] - xs[i]) * (py - yi) / ((yj - yi) or 1.0e-12) + xs[i]
            if px < xint:
                inside = not inside
        j = i
    return inside


def tie_spacing_max(main_dia_cm, tie_dia_cm, least_dim_cm):
    """ACI 318M-08 7.10.5.2 — s_max = min(16 db, 48 d_tie, least dim)."""
    return min(16.0 * main_dia_cm, 48.0 * tie_dia_cm, least_dim_cm)
