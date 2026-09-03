"""EV-07 — Independent STAIR validation reference.

Independent validation reference — NOT production calculation code.
Imports only ``math``.  No ``utils.*``, no ``modules.*``, no production
helper calls.

Re-derives what ``modules/stair.py`` computes for the two implemented
stair types, from first principles + ACI 318M-08:

  STRAIGHT flight (``_render_straight_stair``) — inclined one-way slab,
  1 m strip, MKS (ksc / cm / kgf):
    * Lx = N*T/100                       (horizontal span, m)
    * theta = atan2(R, T)
    * DL_waist = (t/100)*2400 / cos(theta)      (sloped waist, per m^2 horiz)
    * DL_steps = ((R/100)/2)*2400               (triangular steps)
    * Wu = 1.2 (DL_waist + DL_steps + SDL) + 1.6 LL     (kgf/m^2 = kgf/m)
    * Mu = Wu * Lx^2 / 8                 (simply supported, kgf-m per strip)
    * As from _as_flexure_ksc chain (phi = 0.90) + temp steel + spacing

  U-SHAPE flight (``_render_u_shape_stair``) — single-span inclined slab,
  landing + flight, SI core (MPa / mm / N):
    * L_flight = N*T/100 ; L = L_flight + L_land
    * t_avg = t/cos(theta) + R/2                (equivalent uniform thickness)
    * flight_DL  = (t_avg/100)*2400 + SDL
    * landing_DL = (t/100)*2400 + SDL
    * Wu = 1.2 * max(flight_DL, landing_DL) + 1.6 LL       (kgf/m^2)
    * Mu = Wu * L^2 / 8
    * As from _required_as_flexure chain (phi = 0.90); As_prov from the
      USER main-bar spacing

Both verdicts are re-derived INCLUDING the tension-controlled / As_max
limit (ACI 10.3.4 / 10.3.5) that the engine's verdict omits.
"""

import math

CONC_DENSITY_KGF_M3 = 2400.0
EPS_CU = 0.003
EPS_TC = 0.005
EPS_MIN_FLEXURE = 0.004
PHI_FLEX = 0.90
KSC_TO_MPA = 0.0980665
KGF_TO_KN = 9.80665 / 1000.0


# ---------------------------------------------------------------------------
def beta1_ksc(fc_ksc):
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def beta1_si(fc_mpa):
    if fc_mpa <= 28.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_mpa - 28.0) / 7.0)


def temp_steel_ratio(fy_mpa):
    """ACI 7.12.2.1 (fy in MPa)."""
    if fy_mpa <= 350.0:
        return 0.0020
    if fy_mpa <= 420.0:
        return 0.0018
    return max(0.0018 * 420.0 / fy_mpa, 0.0014)


def rho_max_tc_ksc(fc_ksc, fy_ksc):
    return (0.85 * beta1_ksc(fc_ksc) * fc_ksc / fy_ksc
            * EPS_CU / (EPS_CU + EPS_TC))


def rho_max_tc_si(fc_mpa, fy_mpa):
    return (0.85 * beta1_si(fc_mpa) * fc_mpa / fy_mpa
            * EPS_CU / (EPS_CU + EPS_TC))


def _flex_chain_ksc(Mu_kgfm, b_cm, d_cm, fc_ksc, fy_ksc):
    """Singly-reinforced As (cm2) for a strip, MKS, with the full strain
    chain so phi = 0.90 can be checked.  Mirrors _as_flexure_ksc:
    (0.0, True) when Mu <= 0 or d <= 0 ; (None, False) when infeasible."""
    if d_cm <= 0.0 or Mu_kgfm <= 0.0:
        return {"As_cm2": 0.0, "feasible": True, "Rn_ksc": 0.0,
                "eps_t": float("inf"), "phi_code": PHI_FLEX,
                "tension_controlled": True, "meets_eps_min_flexure": True}
    Rn = (Mu_kgfm * 100.0) / (PHI_FLEX * b_cm * d_cm ** 2)
    disc = 1.0 - 2.0 * Rn / (0.85 * fc_ksc)
    if disc < 0.0:
        return {"As_cm2": None, "feasible": False, "Rn_ksc": Rn,
                "eps_t": None, "phi_code": None,
                "tension_controlled": False, "meets_eps_min_flexure": False}
    rho = (0.85 * fc_ksc / fy_ksc) * (1.0 - math.sqrt(disc))
    As = rho * b_cm * d_cm
    a = As * fy_ksc / (0.85 * fc_ksc * b_cm)
    c = a / beta1_ksc(fc_ksc)
    eps_t = EPS_CU * (d_cm - c) / c
    if eps_t <= 0.002:
        phi = 0.65
    elif eps_t >= EPS_TC:
        phi = 0.90
    else:
        phi = 0.65 + 0.25 * (eps_t - 0.002) / 0.003
    return {"As_cm2": As, "feasible": True, "Rn_ksc": Rn, "rho": rho,
            "a_cm": a, "c_cm": c, "eps_t": eps_t, "phi_code": phi,
            "tension_controlled": eps_t >= EPS_TC,
            "meets_eps_min_flexure": eps_t >= EPS_MIN_FLEXURE}


def _flex_chain_si(Mu_kNm, b_mm, d_mm, fc_mpa, fy_mpa):
    """Mirrors _required_as_flexure (SI); None/False when infeasible.
    (_required_as_flexure returns As=0 for Mu<=0 with no strain chain; the
    reference does the same, skipping the eps_t computation.)"""
    if Mu_kNm <= 0.0 or d_mm <= 0.0:
        return {"As_mm2": 0.0, "feasible": True, "Rn_MPa": 0.0, "rho": 0.0,
                "eps_t": float("inf"), "phi_code": PHI_FLEX,
                "tension_controlled": True, "meets_eps_min_flexure": True}
    Mu = Mu_kNm * 1.0e6
    Rn = Mu / (PHI_FLEX * b_mm * d_mm ** 2)
    disc = 1.0 - 2.0 * Rn / (0.85 * fc_mpa)
    if disc < 0.0:
        return {"As_mm2": None, "feasible": False, "Rn_MPa": Rn,
                "eps_t": None, "phi_code": None,
                "tension_controlled": False, "meets_eps_min_flexure": False}
    rho = (0.85 * fc_mpa / fy_mpa) * (1.0 - math.sqrt(disc))
    As = rho * b_mm * d_mm
    a = As * fy_mpa / (0.85 * fc_mpa * b_mm)
    c = a / beta1_si(fc_mpa)
    eps_t = EPS_CU * (d_mm - c) / c
    if eps_t <= 0.002:
        phi = 0.65
    elif eps_t >= EPS_TC:
        phi = 0.90
    else:
        phi = 0.65 + 0.25 * (eps_t - 0.002) / 0.003
    return {"As_mm2": As, "feasible": True, "Rn_MPa": Rn, "rho": rho,
            "eps_t": eps_t, "phi_code": phi,
            "tension_controlled": eps_t >= EPS_TC,
            "meets_eps_min_flexure": eps_t >= EPS_MIN_FLEXURE}


def spacing_for(Ab_cm2, As_req_cm2, s_max_cm):
    if As_req_cm2 <= 1.0e-9:
        S = s_max_cm
    else:
        S_req = Ab_cm2 * 100.0 / As_req_cm2
        S = min(math.floor(S_req / 2.5) * 2.5, s_max_cm)
        S = max(S, 2.5)
    return S, Ab_cm2 * 100.0 / S


# ===========================================================================
# STRAIGHT FLIGHT
# ===========================================================================
def straight_stair(*, R_cm, T_cm, N, t_cm, cov_cm, fc_ksc, fy_ksc,
                   SDL_kgf_m2, LL_kgf_m2, main_db_mm, temp_db_mm,
                   main_Ab_cm2, temp_Ab_cm2):
    b = 100.0
    Lx = (N * T_cm) / 100.0                             # m, horizontal span
    theta = math.atan2(R_cm, T_cm)
    cos_th = math.cos(theta)

    DL_waist = (t_cm / 100.0) * CONC_DENSITY_KGF_M3 / cos_th
    DL_steps = ((R_cm / 100.0) / 2.0) * CONC_DENSITY_KGF_M3
    DL = DL_waist + DL_steps + SDL_kgf_m2
    Wu = 1.2 * DL + 1.6 * LL_kgf_m2                     # kgf/m^2 = kgf/m
    Mu = Wu * Lx ** 2 / 8.0                             # kgf-m per strip

    d = t_cm - cov_cm - main_db_mm / 10.0 / 2.0
    if d <= 0.0:
        return {"error": "d <= 0", "d_cm": d}

    fx = _flex_chain_ksc(Mu, b, d, fc_ksc, fy_ksc)
    if not fx["feasible"]:
        return {"feasible": False, "Mu_kgfm": Mu, "d_cm": d, "fx": fx}

    temp_ratio = temp_steel_ratio(fy_ksc * KSC_TO_MPA)
    As_temp_min = temp_ratio * b * t_cm
    As_main = max(fx["As_cm2"] or 0.0, As_temp_min)

    s_max_main = min(3.0 * t_cm, 45.0)
    s_max_temp = min(5.0 * t_cm, 45.0)
    S_main, Asp_main = spacing_for(main_Ab_cm2, As_main, s_max_main)
    S_temp, Asp_temp = spacing_for(temp_Ab_cm2, As_temp_min, s_max_temp)
    main_ok = 7.5 <= S_main <= s_max_main
    temp_ok = 7.5 <= S_temp <= s_max_temp

    rho_max = rho_max_tc_ksc(fc_ksc, fy_ksc)
    As_max_main = rho_max * b * d
    ductile_ok = As_main <= As_max_main

    engine_passed = main_ok and temp_ok
    aci_passed = main_ok and temp_ok and ductile_ok
    return {
        "Lx_m": Lx, "theta_deg": math.degrees(theta), "cos_theta": cos_th,
        "DL_waist_kgf_m2": DL_waist, "DL_steps_kgf_m2": DL_steps,
        "DL_kgf_m2": DL, "Wu_kgf_m2": Wu, "Mu_kgfm": Mu, "d_cm": d,
        "fx": fx, "As_temp_min_cm2": As_temp_min, "As_main_cm2": As_main,
        "s_max_main_cm": s_max_main, "s_max_temp_cm": s_max_temp,
        "S_main_cm": S_main, "S_temp_cm": S_temp,
        "main_ok": main_ok, "temp_ok": temp_ok,
        "rho_max": rho_max, "As_max_main_cm2": As_max_main,
        "ductile_ok": ductile_ok,
        "engine_passed": engine_passed, "aci_passed": aci_passed,
    }


# ===========================================================================
# U-SHAPE FLIGHT
# ===========================================================================
def u_shape_stair(*, R_cm, T_cm, N, L_land_m, t_cm, cov_cm, fc_ksc, fy_ksc,
                  SDL_kgf_m2, LL_kgf_m2, main_db_mm, main_sp_cm, temp_db_mm,
                  temp_sp_cm, main_area_mm2, temp_area_mm2):
    b = 1000.0                                          # mm strip
    fc = fc_ksc * KSC_TO_MPA
    fy = fy_ksc * KSC_TO_MPA
    L_flight = (N * T_cm) / 100.0
    L = L_flight + L_land_m
    theta = math.atan(R_cm / T_cm)
    t_avg_cm = (t_cm / math.cos(theta)) + (R_cm / 2.0)

    flight_DL = (t_avg_cm / 100.0) * CONC_DENSITY_KGF_M3 + SDL_kgf_m2
    landing_DL = (t_cm / 100.0) * CONC_DENSITY_KGF_M3 + SDL_kgf_m2
    max_DL = max(flight_DL, landing_DL)
    Wu_kg = 1.2 * max_DL + 1.6 * LL_kgf_m2              # kgf/m^2
    Wu = Wu_kg * KGF_TO_KN                              # kN/m^2
    Mu = Wu * L ** 2 / 8.0                              # kN.m/m

    d = t_cm * 10.0 - cov_cm * 10.0 - main_db_mm / 2.0  # mm
    if d <= 0.0:
        return {"error": "d <= 0", "d_mm": d}

    fx = _flex_chain_si(Mu, b, d, fc, fy)
    As_min = temp_steel_ratio(fy) * b * (t_cm * 10.0)   # mm^2/m
    if not fx["feasible"]:
        return {"feasible": False, "Mu_kNm": Mu, "d_mm": d, "fx": fx,
                "As_min_mm2": As_min}

    As_prov_main = main_area_mm2 * (b / (main_sp_cm * 10.0))
    As_prov_temp = temp_area_mm2 * (b / (temp_sp_cm * 10.0))
    max_sp_main = min(3.0 * t_cm * 10.0, 450.0)
    max_sp_temp = min(5.0 * t_cm * 10.0, 450.0)
    sp_main_ok = (main_sp_cm * 10.0) <= max_sp_main
    sp_temp_ok = (temp_sp_cm * 10.0) <= max_sp_temp

    main_req_ok = As_prov_main >= fx["As_mm2"]
    main_min_ok = As_prov_main >= As_min
    temp_min_ok = As_prov_temp >= As_min

    As_max_main = rho_max_tc_si(fc, fy) * b * d
    ductile_ok = As_prov_main <= As_max_main

    engine_passed = (main_req_ok and main_min_ok and temp_min_ok
                     and sp_main_ok and sp_temp_ok)
    aci_passed = engine_passed and ductile_ok
    return {
        "L_flight_m": L_flight, "L_m": L, "theta_deg": math.degrees(theta),
        "t_avg_cm": t_avg_cm, "flight_DL_kgf_m2": flight_DL,
        "landing_DL_kgf_m2": landing_DL, "max_DL_kgf_m2": max_DL,
        "Wu_kgf_m2": Wu_kg, "Wu_kN_m2": Wu, "Mu_kNm": Mu, "d_mm": d,
        "fx": fx, "As_min_mm2": As_min,
        "As_prov_main_mm2": As_prov_main, "As_prov_temp_mm2": As_prov_temp,
        "max_sp_main_mm": max_sp_main, "max_sp_temp_mm": max_sp_temp,
        "main_req_ok": main_req_ok, "main_min_ok": main_min_ok,
        "temp_min_ok": temp_min_ok, "sp_main_ok": sp_main_ok,
        "sp_temp_ok": sp_temp_ok,
        "As_max_main_mm2": As_max_main, "ductile_ok": ductile_ok,
        "engine_passed": engine_passed, "aci_passed": aci_passed,
    }
