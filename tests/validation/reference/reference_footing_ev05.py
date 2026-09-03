"""EV-05 — Independent FOOTING / PILE-CAP validation reference.

Independent validation reference — NOT production calculation code.
Imports only ``math``.  No ``utils.*``, no ``modules.*``.

Re-derives, from ACI 318M-08 and first principles, what
``modules/footing.py`` computes:

  * isolated footing: self-weight, service & net-factored soil pressure,
    two-way (punching) shear geometry + capacity, one-way shear, flexure
    at the column face, minimum steel, spacing, tension-controlled limit
  * pile cap: pile coordinates, elastic pile-reaction distribution
    (R_i = P/n + M_y x_i/Sx2 + M_x y_i/Sy2), the four pile-head punching
    perimeters (incl. the hexagon 2*sqrt(3)*Dp + pi*d derivation), column
    punching, one-way shear, flexure

SI units: N, N-mm, MPa, mm  (the engine's calculation core).
"""

import math

EPS_CU = 0.003
EPS_TC = 0.005
EPS_MIN_FLEXURE = 0.004
PHI_FLEX = 0.90
PHI_SHEAR = 0.75
LAMBDA = 1.0
ALPHA_S_INTERIOR = 40.0
CONC_UW_KGF = 2400.0
KGF_TO_KN = 9.80665 / 1000.0
KSC_TO_MPA = 0.0980665


# ---------------------------------------------------------------------------
# shared flexure helpers (SI) — the standard singly-reinforced relations
# ---------------------------------------------------------------------------
def beta1_si(fc_mpa):
    if fc_mpa <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_mpa - 28.0) / 7.0)


def rho_max_tc_si(fc_mpa, fy_mpa):
    """ACI 10.3.4 tension-controlled max ratio (eps_t = 0.005)."""
    return (0.85 * beta1_si(fc_mpa) * fc_mpa / fy_mpa
            * EPS_CU / (EPS_CU + EPS_TC))


def temp_steel_ratio(fy_mpa):
    """ACI 7.12.2.1."""
    if fy_mpa <= 350.0:
        return 0.0020
    if fy_mpa <= 420.0:
        return 0.0018
    return max(0.0018 * 420.0 / fy_mpa, 0.0014)


def flexure_as(Mu_Nmm, b_mm, d_mm, fc_mpa, fy_mpa):
    """Reproduce modules/footing.py::_flexure_as with the full strain chain.

    Returns dict incl. ``feasible`` (inf/False sentinel on d<=0/b<=0 or
    disc<0), and eps_t / phi_code so phi = 0.90 can be checked.
    """
    if d_mm <= 0.0 or b_mm <= 0.0:
        return {"As_req_mm2": math.inf, "Rn_MPa": 0.0, "rho": None,
                "feasible": False, "eps_t": None, "phi_code": None,
                "tension_controlled": False}
    Rn = Mu_Nmm / (PHI_FLEX * b_mm * d_mm ** 2)
    disc = 1.0 - 2.0 * Rn / (0.85 * fc_mpa)
    if disc < 0.0:
        return {"As_req_mm2": math.inf, "Rn_MPa": Rn, "rho": None,
                "feasible": False, "eps_t": None, "phi_code": None,
                "tension_controlled": False}
    rho = (0.85 * fc_mpa / fy_mpa) * (1.0 - math.sqrt(disc))
    As = rho * b_mm * d_mm
    a = As * fy_mpa / (0.85 * fc_mpa * b_mm)
    c = a / beta1_si(fc_mpa)
    eps_t = EPS_CU * (d_mm - c) / c if c > 0 else math.inf
    if eps_t <= 0.002:
        phi = 0.65
    elif eps_t >= EPS_TC:
        phi = 0.90
    else:
        phi = 0.65 + 0.25 * (eps_t - 0.002) / 0.003
    return {"As_req_mm2": As, "Rn_MPa": Rn, "rho": rho, "feasible": True,
            "a_mm": a, "c_mm": c, "eps_t": eps_t, "phi_code": phi,
            "tension_controlled": eps_t >= EPS_TC,
            "meets_eps_min_flexure": eps_t >= EPS_MIN_FLEXURE}


# ===========================================================================
# ISOLATED FOOTING
# ===========================================================================
def isolated_footing(*, P_DL_kgf, P_LL_kgf, B_m, L_m, h_cm, cov_cm,
                     cx_cm, cy_cm, fc_ksc, fy_ksc, q_a_ton,
                     db_long_mm, db_short_mm, n_long, n_short,
                     bar_area_long_mm2, bar_area_short_mm2):
    """Full independent recomputation of _render_isolated_footing, incl. the
    tension-controlled limit that the engine's verdict omits."""
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA
    B = B_m * 1000.0
    L = L_m * 1000.0
    h = h_cm * 10.0
    cov = cov_cm * 10.0
    cx = cx_cm * 10.0
    cy = cy_cm * 10.0
    area_m2 = B_m * L_m

    # loads
    Wf_kgf = area_m2 * (h_cm / 100.0) * CONC_UW_KGF
    q_service_kgf_m2 = (P_DL_kgf + P_LL_kgf + Wf_kgf) / area_m2
    q_a_kgf_m2 = q_a_ton * 1000.0
    bearing_ok = q_service_kgf_m2 <= q_a_kgf_m2
    qu_net_kgf_m2 = (1.2 * P_DL_kgf + 1.6 * P_LL_kgf) / area_m2
    qu_MPa = qu_net_kgf_m2 * KGF_TO_KN * 1.0e-3      # N/mm^2

    # effective depths — engine convention: d_long = h - cov - db_long
    d_long = h - cov - db_long_mm
    d_short = d_long - db_long_mm
    d_avg = 0.5 * (d_long + d_short)

    long_dim = max(B, L)
    short_dim = min(B, L)
    if B >= L:
        c_long, c_short = cx, cy
    else:
        c_long, c_short = cy, cx

    # two-way (punching) shear
    bo = 2.0 * (cx + d_avg) + 2.0 * (cy + d_avg)
    punch_area = max(B * L - (cx + d_avg) * (cy + d_avg), 0.0)
    Vup = qu_MPa * punch_area
    beta_c = max(cx, cy) / min(cx, cy)
    vc1 = 0.17 * (1.0 + 2.0 / beta_c) * LAMBDA * math.sqrt(fc)
    vc2 = 0.083 * (ALPHA_S_INTERIOR * d_avg / bo + 2.0) * LAMBDA * math.sqrt(fc)
    vc3 = 0.33 * LAMBDA * math.sqrt(fc)
    vc_punch = min(vc1, vc2, vc3)
    phiVc_punch = PHI_SHEAR * vc_punch * bo * d_avg
    punch_ok = Vup <= phiVc_punch
    vc_gov = "vc1" if vc_punch == vc1 else "vc2" if vc_punch == vc2 else "vc3"

    # one-way (beam) shear, section at d from the column face
    av_long = max((long_dim - c_long) / 2.0 - d_long, 0.0)
    Vu_long = qu_MPa * short_dim * av_long
    phiVc_v_long = PHI_SHEAR * 0.17 * LAMBDA * math.sqrt(fc) * short_dim * d_long
    beam_long_ok = Vu_long <= phiVc_v_long
    av_short = max((short_dim - c_short) / 2.0 - d_short, 0.0)
    Vu_short = qu_MPa * long_dim * av_short
    phiVc_v_short = PHI_SHEAR * 0.17 * LAMBDA * math.sqrt(fc) * long_dim * d_short
    beam_short_ok = Vu_short <= phiVc_v_short

    # flexure at the column face (ACI 15.4.2)
    Lc_long = (long_dim - c_long) / 2.0
    Lc_short = (short_dim - c_short) / 2.0
    Mu_long = qu_MPa * short_dim * Lc_long ** 2 / 2.0
    Mu_short = qu_MPa * long_dim * Lc_short ** 2 / 2.0
    fx_long = flexure_as(Mu_long, short_dim, d_long, fc, fy)
    fx_short = flexure_as(Mu_short, long_dim, d_short, fc, fy)

    temp_ratio = temp_steel_ratio(fy)
    As_min_long = temp_ratio * short_dim * h
    As_min_short = temp_ratio * long_dim * h

    As_prov_long = n_long * bar_area_long_mm2
    As_prov_short = n_short * bar_area_short_mm2
    s_long = ((short_dim - 2.0 * cov) / (n_long - 1)
              if n_long > 1 else short_dim - 2.0 * cov)
    s_short = ((long_dim - 2.0 * cov) / (n_short - 1)
               if n_short > 1 else long_dim - 2.0 * cov)
    s_max = min(3.0 * h, 450.0)
    sp_long_ok = s_long <= s_max
    sp_short_ok = s_short <= s_max

    flex_long_ok = fx_long["feasible"] and As_prov_long >= fx_long["As_req_mm2"]
    flex_short_ok = fx_short["feasible"] and As_prov_short >= fx_short["As_req_mm2"]
    asmin_long_ok = As_prov_long >= As_min_long
    asmin_short_ok = As_prov_short >= As_min_short

    # tension-controlled limit (ACI 10.3.4 / 10.3.5) — ABSENT from the engine
    As_max_long = rho_max_tc_si(fc, fy) * short_dim * d_long
    As_max_short = rho_max_tc_si(fc, fy) * long_dim * d_short
    ductile_long = As_prov_long <= As_max_long
    ductile_short = As_prov_short <= As_max_short

    engine_passed = (bearing_ok and beam_long_ok and beam_short_ok and punch_ok
                     and flex_long_ok and flex_short_ok
                     and asmin_long_ok and asmin_short_ok
                     and sp_long_ok and sp_short_ok)
    aci_passed = engine_passed and ductile_long and ductile_short

    return {
        "fc_MPa": fc, "fy_MPa": fy,
        "Wf_kgf": Wf_kgf, "q_service_kgf_m2": q_service_kgf_m2,
        "q_allow_kgf_m2": q_a_kgf_m2, "bearing_ok": bearing_ok,
        "qu_net_kgf_m2": qu_net_kgf_m2, "qu_MPa": qu_MPa,
        "d_long_mm": d_long, "d_short_mm": d_short, "d_avg_mm": d_avg,
        "bo_mm": bo, "Vup_N": Vup, "beta_c": beta_c,
        "vc1_MPa": vc1, "vc2_MPa": vc2, "vc3_MPa": vc3,
        "vc_punch_MPa": vc_punch, "vc_governs": vc_gov,
        "phiVc_punch_N": phiVc_punch, "punch_ok": punch_ok,
        "Vu_long_N": Vu_long, "phiVc_v_long_N": phiVc_v_long,
        "beam_long_ok": beam_long_ok,
        "Vu_short_N": Vu_short, "phiVc_v_short_N": phiVc_v_short,
        "beam_short_ok": beam_short_ok,
        "Mu_long_Nmm": Mu_long, "Mu_short_Nmm": Mu_short,
        "fx_long": fx_long, "fx_short": fx_short,
        "As_min_long_mm2": As_min_long, "As_min_short_mm2": As_min_short,
        "As_prov_long_mm2": As_prov_long, "As_prov_short_mm2": As_prov_short,
        "s_long_mm": s_long, "s_short_mm": s_short, "s_max_mm": s_max,
        "As_max_long_mm2": As_max_long, "As_max_short_mm2": As_max_short,
        "ductile_long": ductile_long, "ductile_short": ductile_short,
        "flex_long_ok": flex_long_ok, "flex_short_ok": flex_short_ok,
        "asmin_long_ok": asmin_long_ok, "asmin_short_ok": asmin_short_ok,
        "sp_long_ok": sp_long_ok, "sp_short_ok": sp_short_ok,
        "engine_passed": engine_passed, "aci_passed": aci_passed,
    }


# ===========================================================================
# PILE CAP
# ===========================================================================
def pile_coords(n, S):
    """Independent reproduction of modules/footing.py::_pile_coords
    (centre-to-centre, origin = column centre, mm)."""
    r3 = math.sqrt(3.0)
    if n == 1:
        return [(0.0, 0.0)]
    if n == 2:
        return [(0.0, -S / 2.0), (0.0, S / 2.0)]
    if n == 3:
        return [(0.0, S / r3), (S / 2.0, -S / (2.0 * r3)),
                (-S / 2.0, -S / (2.0 * r3))]
    if n == 4:
        return [(-S / 2.0, -S / 2.0), (S / 2.0, -S / 2.0),
                (S / 2.0, S / 2.0), (-S / 2.0, S / 2.0)]
    if n == 5:
        return [(0.0, 0.0), (S / 2.0, S / 2.0), (S / 2.0, -S / 2.0),
                (-S / 2.0, S / 2.0), (-S / 2.0, -S / 2.0)]
    if n == 6:
        return [(-S / 2.0, S), (S / 2.0, S), (-S / 2.0, 0.0),
                (S / 2.0, 0.0), (-S / 2.0, -S), (S / 2.0, -S)]
    if n == 7:
        pts = [(0.0, 0.0)]
        for i in range(6):
            ang = math.radians(60.0 * i)
            pts.append((S * math.cos(ang), S * math.sin(ang)))
        return pts
    if n == 8:
        return [(0.0, S), (0.0, -S), (S, 0.0), (-S, 0.0),
                (S, S), (S, -S), (-S, S), (-S, -S)]
    if n == 9:
        return [(0.0, S), (0.0, -S), (S, 0.0), (-S, 0.0),
                (S, S), (S, -S), (-S, S), (-S, -S), (0.0, 0.0)]
    return [((i - (n - 1) / 2.0) * S, 0.0) for i in range(n)]


def elastic_pile_reactions(coords, axial, ecc_load, ex_mm, ey_mm):
    """Standard elastic pile-group distribution:
        R_i = axial/n + (ecc_load*ex)*x_i/Sx2 + (ecc_load*ey)*y_i/Sy2
    Terms with Sx2 = 0 or Sy2 = 0 are dropped (an axis with no pile offset
    cannot carry a moment about it).  Returns (R_list, Sx2, Sy2).
    """
    n = len(coords)
    Sx2 = sum(px * px for (px, py) in coords)
    Sy2 = sum(py * py for (px, py) in coords)
    my = ecc_load * ex_mm
    mx = ecc_load * ey_mm
    out = []
    for (px, py) in coords:
        r = axial / n
        if Sx2 > 0.0:
            r += my * px / Sx2
        if Sy2 > 0.0:
            r += mx * py / Sy2
        out.append(r)
    return out, Sx2, Sy2


def pile_head_punching_perimeter(shape, Dp_mm, d_avg_mm):
    """Critical shear perimeter at d/2 around one pile head (ACI 15.5 / R11.11).

    square / I-section : 4*(Dp + d)              -- square of side Dp
    circular          : pi*(Dp + d)             -- exact for a circle
    hexagonal         : 2*sqrt(3)*Dp + pi*d
        A regular hexagon of ACROSS-FLATS width Dp has perimeter
        6 * (Dp/sqrt(3)) = 2*sqrt(3)*Dp = 3.4641*Dp .  Offsetting the
        critical section by d/2 rounds the 6 corners into 6 x 60deg arcs of
        radius d/2, i.e. one full circle of circumference pi*d.  So the
        exact offset perimeter is  2*sqrt(3)*Dp + pi*d .  (The engine's
        literal 3.464 is 2*sqrt(3) to 4 s.f. -- VF-09 is NOT a defect.)
    """
    if shape in ("square", "isec"):
        return 4.0 * (Dp_mm + d_avg_mm), "4*(Dp + d)"
    if shape == "hex":
        return 2.0 * math.sqrt(3.0) * Dp_mm + math.pi * d_avg_mm, \
            "2*sqrt(3)*Dp + pi*d"
    return math.pi * (Dp_mm + d_avg_mm), "pi*(Dp + d)"     # circular


def hexagon_perimeter_factor():
    """Return (engine_literal, exact) for the hexagon Dp coefficient."""
    return 3.464, 2.0 * math.sqrt(3.0)
