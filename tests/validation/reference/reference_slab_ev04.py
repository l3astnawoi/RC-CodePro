"""EV-04 — Independent SLAB validation reference.

Independent validation reference — NOT production calculation code.
Imports only ``math``.  No ``utils.*``, no ``modules.*``.

Re-derives, from ACI 318M-08 and classical plate theory, everything the
live ``modules/slab.py._render_slab_design`` computes:

* one-way / two-way classification (Lx/Ly threshold)
* self-weight, factored load Wu
* design moments — one-way simply-supported strip; two-way by the
  classical Grashof / Rankine (Marcus) elastic load-partition method
  (this is what the engine implements; see EV-04 report re: ACI status)
* singly-reinforced flexural steel per direction, with the full chain
  (beta1, a, c, eps_t, phi) so phi = 0.90 can be checked, not assumed
* shrinkage / temperature minimum steel (ACI 7.12.2.1 / 10.5.4)
* provided-bar spacing (the engine's 2.5 cm rounding rule)
* the ACI-correct composite verdict — INCLUDING the tension-controlled /
  As_max limit that the engine's verdict omits (the EV-04 finding).

MKS unit system: ksc / cm / kgf / kgf-m / kgf per m^2, matching the engine.
"""

import math

CONC_DENSITY_KGF_M3 = 2400.0     # engine literal (MKS convention)
EPS_CU = 0.003
EPS_TC = 0.005                   # ACI 10.3.4 tension-controlled
EPS_MIN_FLEXURE = 0.004          # ACI 10.3.5 mandatory for flexural members
EPS_TY_LITERAL = 0.002
PHI_TC = 0.90


# ---------------------------------------------------------------------------
def beta1_ksc(fc_ksc):
    """ACI 10.2.7.3, MKS-literal form (280 ksc break) — matches the engine."""
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def temp_steel_ratio(fy_mpa):
    """ACI 318M-08 7.12.2.1 shrinkage & temperature ratio (fy in MPa):
        fy <= 350 -> 0.0020 ; 350 < fy <= 420 -> 0.0018 ;
        fy > 420  -> max(0.0018*420/fy, 0.0014)
    """
    if fy_mpa <= 350.0:
        return 0.0020
    if fy_mpa <= 420.0:
        return 0.0018
    return max(0.0018 * 420.0 / fy_mpa, 0.0014)


def rho_max_tc_ksc(fc_ksc, fy_ksc):
    """ACI 10.3.4 tension-controlled maximum ratio, MKS (eps_t = 0.005)."""
    return (0.85 * beta1_ksc(fc_ksc) * fc_ksc / fy_ksc
            * EPS_CU / (EPS_CU + EPS_TC))


# ---------------------------------------------------------------------------
def classify(Lx_m, Ly_m):
    """Engine rule:  short = min, long = max ;  two_way iff  short/long > 0.5
    (equivalently long/short < 2.0).  The 2:1 aspect ratio is the standard
    ACI / textbook one-way vs two-way criterion."""
    short, longspan = min(Lx_m, Ly_m), max(Lx_m, Ly_m)
    m = short / longspan if longspan > 0 else 0.0
    return {"short_m": short, "long_m": longspan, "m_ratio": m,
            "two_way": m > 0.5,
            "type": "two-way" if m > 0.5 else "one-way"}


def loads(t_cm, SDL_kgf_m2, LL_kgf_m2):
    sw = (t_cm / 100.0) * CONC_DENSITY_KGF_M3          # kgf/m^2
    DL = sw + SDL_kgf_m2
    Wu = 1.2 * DL + 1.6 * LL_kgf_m2                    # kgf/m^2 (ACI 9.2)
    return {"sw_kgf_m2": sw, "DL_kgf_m2": DL, "Wu_kgf_m2": Wu}


def design_moments(Wu_kgf_m2, Lx_m, Ly_m, two_way):
    """Per 1 m strip, kgf-m.

    one-way : Mu = Wu * Lx^2 / 8            (simply supported)
    two-way : Grashof / Rankine load partition
              Mux = Wu * Lx^2 * (Ly^4/(Lx^4+Ly^4)) / 8   (short span)
              Muy = Wu * Ly^2 * (Lx^4/(Lx^4+Ly^4)) / 8   (long span)
    NOTE: Lx is the short span (caller must pass short, long).
    """
    if two_way:
        k = Lx_m ** 4 + Ly_m ** 4
        Mux = Wu_kgf_m2 * Lx_m ** 2 * (Ly_m ** 4 / k) / 8.0
        Muy = Wu_kgf_m2 * Ly_m ** 2 * (Lx_m ** 4 / k) / 8.0
    else:
        Mux = Wu_kgf_m2 * Lx_m ** 2 / 8.0
        Muy = 0.0
    return {"Mux_kgfm": Mux, "Muy_kgfm": Muy, "Mu_main_kgfm": max(Mux, Muy)}


# ---------------------------------------------------------------------------
def flexure_strip_ksc(Mu_kgfm, b_cm, d_cm, fc_ksc, fy_ksc):
    """Singly-reinforced required steel for a strip, MKS, full chain.

        Rn  = Mu*100 / (phi * b * d^2)      (phi = 0.90 assumed, checked below)
        rho = (0.85 f'c / fy)(1 - sqrt(1 - 2 Rn / (0.85 f'c)))
        As  = rho b d
        a   = As fy / (0.85 f'c b) ;  c = a / beta1
        eps_t = 0.003 (d - c) / c
        phi_code = ACI 9.3.2(eps_t)

    Returns dict incl. ``feasible`` (False when the sqrt argument < 0) and
    ``tension_controlled`` / ``meets_eps_min_flexure``.
    """
    if d_cm <= 0.0 or Mu_kgfm <= 0.0:
        return {"As_cm2": 0.0, "feasible": True, "Rn_ksc": 0.0, "rho": 0.0,
                "a_cm": 0.0, "c_cm": 0.0, "eps_t": float("inf"),
                "phi_code": PHI_TC, "tension_controlled": True,
                "meets_eps_min_flexure": True}
    Rn = (Mu_kgfm * 100.0) / (PHI_TC * b_cm * d_cm ** 2)
    disc = 1.0 - 2.0 * Rn / (0.85 * fc_ksc)
    if disc < 0.0:
        return {"As_cm2": None, "feasible": False, "Rn_ksc": Rn, "rho": None,
                "a_cm": None, "c_cm": None, "eps_t": None, "phi_code": None,
                "tension_controlled": False, "meets_eps_min_flexure": False}
    rho = (0.85 * fc_ksc / fy_ksc) * (1.0 - math.sqrt(disc))
    As = rho * b_cm * d_cm
    beta1 = beta1_ksc(fc_ksc)
    a = As * fy_ksc / (0.85 * fc_ksc * b_cm)
    c = a / beta1
    eps_t = EPS_CU * (d_cm - c) / c
    if eps_t <= EPS_TY_LITERAL:
        phi = 0.65
    elif eps_t >= EPS_TC:
        phi = 0.90
    else:
        phi = 0.65 + 0.25 * (eps_t - EPS_TY_LITERAL) / (EPS_TC - EPS_TY_LITERAL)
    return {"As_cm2": As, "feasible": True, "Rn_ksc": Rn, "rho": rho,
            "a_cm": a, "c_cm": c, "eps_t": eps_t, "phi_code": phi,
            "tension_controlled": eps_t >= EPS_TC,
            "meets_eps_min_flexure": eps_t >= EPS_MIN_FLEXURE}


def spacing_for(As_bar_cm2, As_req_cm2, s_max_cm):
    """Engine's bar-spacing rule for a 1 m strip (2.5 cm rounding)."""
    if As_req_cm2 <= 1.0e-9:
        S = s_max_cm
    else:
        S_req = As_bar_cm2 * 100.0 / As_req_cm2
        S = min(math.floor(S_req / 2.5) * 2.5, s_max_cm)
        S = max(S, 2.5)
    return S, As_bar_cm2 * 100.0 / S


# ---------------------------------------------------------------------------
def slab_design_verdict(*, Lx_m, Ly_m, t_cm, cov_cm, fc_ksc, fy_ksc,
                        SDL_kgf_m2, LL_kgf_m2, main_db_mm, temp_db_mm):
    """Full independent recomputation of ``_render_slab_design``'s decision,
    with the ACI-correct verdict = the engine's spacing checks **plus** the
    tension-controlled / As_max limit (ACI 10.3.4 / 10.3.5) that the engine
    omits from ``passed``.
    """
    b = 100.0
    cls = classify(Lx_m, Ly_m)
    Lx, Ly, two_way = cls["short_m"], cls["long_m"], cls["two_way"]
    ld = loads(t_cm, SDL_kgf_m2, LL_kgf_m2)
    mm = design_moments(ld["Wu_kgf_m2"], Lx, Ly, two_way)

    db_main = main_db_mm / 10.0
    Ab_main = math.pi * main_db_mm ** 2 / 4.0 / 100.0
    Ab_temp = math.pi * temp_db_mm ** 2 / 4.0 / 100.0
    d_x = t_cm - cov_cm - db_main / 2.0
    d_y = d_x - db_main
    if d_y <= 0.0:
        return {"error": "d_y <= 0", "classify": cls}

    fx = flexure_strip_ksc(mm["Mux_kgfm"], b, d_x, fc_ksc, fy_ksc)
    fy_ = flexure_strip_ksc(mm["Muy_kgfm"], b, d_y, fc_ksc, fy_ksc)
    feasible = fx["feasible"] and (fy_["feasible"] or not two_way)
    if not feasible:
        return {"feasible": False, "classify": cls, "moments": mm,
                "fx": fx, "fy": fy_}

    temp_ratio = temp_steel_ratio(fy_ksc * 0.0980665)
    As_temp_min = temp_ratio * b * t_cm
    As_x = max(fx["As_cm2"] or 0.0, As_temp_min)
    As_y = max(fy_["As_cm2"] or 0.0, As_temp_min) if two_way else As_temp_min

    s_max_main = min(3.0 * t_cm, 45.0)
    s_max_temp = min(5.0 * t_cm, 45.0)
    S_x, Asp_x = spacing_for(Ab_main, As_x, s_max_main)
    S_y, Asp_y = spacing_for(Ab_main, As_y, s_max_main) if two_way else (None, None)
    S_temp, Asp_temp = spacing_for(Ab_temp, As_temp_min, s_max_temp)

    main_ok = (7.5 <= S_x <= s_max_main) and (
        (not two_way) or (7.5 <= S_y <= s_max_main))
    temp_ok = 7.5 <= S_temp <= s_max_temp

    # --- ductility / tension-controlled limit (ACI 10.3.4 / 10.3.5) -----
    rho_max = rho_max_tc_ksc(fc_ksc, fy_ksc)
    As_max_x = rho_max * b * d_x
    As_max_y = rho_max * b * d_y
    ductile_x = As_x <= As_max_x
    ductile_y = (not two_way) or (As_y <= As_max_y)

    engine_passed = main_ok and temp_ok                     # what the engine returns
    aci_passed = main_ok and temp_ok and ductile_x and ductile_y

    reasons = []
    if not main_ok:
        reasons.append("main-bar spacing out of 7.5..s_max")
    if not temp_ok:
        reasons.append("temp-bar spacing out of 7.5..s_max")
    if not ductile_x:
        reasons.append("As_x > As_max (short dir not tension-controlled)")
    if not ductile_y:
        reasons.append("As_y > As_max (long dir not tension-controlled)")

    return {
        "classify": cls, "loads": ld, "moments": mm,
        "d_x_cm": d_x, "d_y_cm": d_y,
        "fx": fx, "fy": fy_,
        "As_temp_min_cm2": As_temp_min, "As_x_cm2": As_x, "As_y_cm2": As_y,
        "s_max_main_cm": s_max_main, "s_max_temp_cm": s_max_temp,
        "S_x_cm": S_x, "S_y_cm": S_y, "S_temp_cm": S_temp,
        "main_ok": main_ok, "temp_ok": temp_ok,
        "As_max_x_cm2": As_max_x, "As_max_y_cm2": As_max_y,
        "ductile_x": ductile_x, "ductile_y": ductile_y,
        "engine_passed": engine_passed,
        "aci_passed": aci_passed,
        "verdict_reason": "PASS" if aci_passed else "; ".join(reasons),
    }
