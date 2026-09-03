"""EV-03 — Independent BEAM section validation reference.

Independent validation reference — NOT production calculation code.
Imports only `math`.  No `utils.*`, no `modules.*`.

Covers the assembled beam-section design decision (flexure top/bottom +
one-way shear + ductility + spacing), re-derived from ACI 318M-08 so the
EV-03 runner can compare it against `modules/beam.py`'s helpers and the
verdict logic in `_render_beam_section` / `_section_calc`.

MKS unit system: ksc / cm / kgf / kgf-m  (matching `_render_beam_section`).
"""

import math

EPS_CU = 0.003
EPS_TC = 0.005          # ACI 10.3.4 tension-controlled
EPS_MIN_FLEXURE = 0.004  # ACI 10.3.5 mandatory minimum for flexural members
PHI_TC = 0.90
PHI_CC_TIED = 0.65
EPS_TY_LITERAL = 0.002  # engine/aci_318m EPSILON_TY literal


def beta1_ksc(fc_ksc):
    """ACI 10.2.7.3, MKS-literal form (280 ksc break) — matches the engine's
    `_beta1_ksc`.  VF-07 tracks the 280 ksc vs 28 MPa (285.5 ksc) choice."""
    if fc_ksc <= 280.0:
        return 0.85
    return max(0.65, 0.85 - 0.05 * (fc_ksc - 280.0) / 70.0)


def phi_from_eps_t(eps_t, spiral=False):
    """ACI 9.3.2 strength-reduction factor from the net tensile strain,
    eps_ty = 0.002 literal (as the engine uses)."""
    phi_c = 0.75 if spiral else PHI_CC_TIED
    if eps_t <= EPS_TY_LITERAL:
        return phi_c
    if eps_t >= EPS_TC:
        return PHI_TC
    return phi_c + (PHI_TC - phi_c) * (eps_t - EPS_TY_LITERAL) / (EPS_TC - EPS_TY_LITERAL)


def flexure_layer_mks(As_cm2, fy_ksc, fc_ksc, b_cm, d_cm):
    """One tension layer, singly reinforced, Whitney block — full chain
    with every intermediate value.

        a   = As fy / (0.85 f'c b)
        c   = a / beta1
        eps_t = 0.003 (d - c) / c
        Mn  = As fy (d - a/2) / 100          [kgf-m]
        phi = phi(eps_t)  (ACI 9.3.2)
        phiMn_code   = phi      * Mn         <-- the ACI-correct value
        phiMn_phi090 = 0.90     * Mn         <-- what _flex_ksc returns
    """
    if As_cm2 <= 0.0 or d_cm <= 0.0:
        return {"a_cm": 0.0, "c_cm": 0.0, "eps_t": float("inf"),
                "Mn_kgfm": 0.0, "phi_code": PHI_TC,
                "phiMn_code_kgfm": 0.0, "phiMn_phi090_kgfm": 0.0,
                "tension_controlled": True, "meets_eps_min_flexure": True}
    beta1 = beta1_ksc(fc_ksc)
    a = As_cm2 * fy_ksc / (0.85 * fc_ksc * b_cm)
    c = a / beta1
    eps_t = EPS_CU * (d_cm - c) / c
    Mn = As_cm2 * fy_ksc * (d_cm - a / 2.0) / 100.0
    phi = phi_from_eps_t(eps_t)
    return {
        "beta1": beta1, "a_cm": a, "c_cm": c, "eps_t": eps_t,
        "Mn_kgfm": Mn,
        "phi_code": phi,
        "phiMn_code_kgfm": phi * Mn,
        "phiMn_phi090_kgfm": PHI_TC * Mn,
        "tension_controlled": eps_t >= EPS_TC,
        "meets_eps_min_flexure": eps_t >= EPS_MIN_FLEXURE,
    }


def rho_min_ksc(fc_ksc, fy_ksc):
    """ACI 10.5.1 MKS:  max(0.8 sqrt f'c / fy, 14/fy)."""
    return max(0.8 * math.sqrt(fc_ksc) / fy_ksc, 14.0 / fy_ksc)


def rho_max_tc_ksc(fc_ksc, fy_ksc):
    """ACI 10.3.4 tension-controlled maximum ratio, MKS (eps_t = 0.005)."""
    return (0.85 * beta1_ksc(fc_ksc) * fc_ksc / fy_ksc
            * EPS_CU / (EPS_CU + EPS_TC))


def as_min_ksc(fc_ksc, fy_ksc, b_cm, d_cm):
    return rho_min_ksc(fc_ksc, fy_ksc) * b_cm * d_cm


def as_max_ksc(fc_ksc, fy_ksc, b_cm, d_cm):
    return rho_max_tc_ksc(fc_ksc, fy_ksc) * b_cm * d_cm


def beam_section_verdict_mks(*, b_cm, h_cm, cov_cm, fc_ksc, fy_ksc, fyv_ksc,
                             top_dia_cm, top_As_cm2, bot_dia_cm, bot_As_cm2,
                             stir_dia_cm, Av_cm2, S_cm,
                             Mu_pos_kgfm, Mu_neg_kgfm, Vu_kgf):
    """Independent recomputation of the `_render_beam_section` decision.

    Uses the ACI-correct phi (from eps_t) for the flexural strength check,
    and INCLUDES the ductility limit (As <= As_max, i.e. eps_t >= 0.005)
    in the pass/fail verdict — this is where the engine's pre-EV-03 code
    computed `*_ductile_ok` but left it out of `passed`.

    Shear uses the SI-exact metric coefficients:
        Vc     = 0.5429 sqrt(f'c) b d      (exact MKS equiv. of 0.17 sqrt MPa)
        Vs_max = 2.108  sqrt(f'c) b d      (exact MKS equiv. of 0.66 sqrt MPa)
        dense-stirrup threshold 1.054 sqrt(f'c) b d  (0.33 sqrt MPa)
    The engine uses the traditional 0.53 / 2.1 / 1.06; the runner reports
    both and flags direction (VF-12 / VF-13).
    """
    d_bot = h_cm - cov_cm - stir_dia_cm - bot_dia_cm / 2.0
    d_top = h_cm - cov_cm - stir_dia_cm - top_dia_cm / 2.0
    d_v = min(d_bot, d_top)

    bot = flexure_layer_mks(bot_As_cm2, fy_ksc, fc_ksc, b_cm, d_bot)
    top = flexure_layer_mks(top_As_cm2, fy_ksc, fc_ksc, b_cm, d_top)

    As_min_bot = as_min_ksc(fc_ksc, fy_ksc, b_cm, d_bot)
    As_min_top = as_min_ksc(fc_ksc, fy_ksc, b_cm, d_top)
    As_max_bot = as_max_ksc(fc_ksc, fy_ksc, b_cm, d_bot)
    As_max_top = as_max_ksc(fc_ksc, fy_ksc, b_cm, d_top)

    bot_strength_ok = bot["phiMn_code_kgfm"] >= Mu_pos_kgfm
    top_strength_ok = top["phiMn_code_kgfm"] >= Mu_neg_kgfm
    bot_min_ok = bot_As_cm2 >= As_min_bot
    top_min_ok = top_As_cm2 >= As_min_top
    bot_ductile_ok = bot_As_cm2 <= As_max_bot
    top_ductile_ok = top_As_cm2 <= As_max_top

    bottom_ok = bot_strength_ok and bot_min_ok and bot_ductile_ok
    top_ok = top_strength_ok and top_min_ok and top_ductile_ok

    # shear (SI-exact metric coefficients)
    Vc = 0.5428753 * math.sqrt(fc_ksc) * b_cm * d_v
    Vs = (Av_cm2 * fyv_ksc * d_v / S_cm) if S_cm > 0.0 else 0.0
    Vs_max = 2.108331 * math.sqrt(fc_ksc) * b_cm * d_v
    phiVn = 0.75 * (Vc + min(Vs, Vs_max))
    s_max = min(d_v / 2.0, 60.0)
    if Vs > 1.053977 * math.sqrt(fc_ksc) * b_cm * d_v:
        s_max = min(d_v / 4.0, 30.0)
    shear_strength_ok = phiVn >= Vu_kgf
    shear_spacing_ok = S_cm <= s_max
    shear_vsmax_ok = Vs <= Vs_max
    shear_ok = shear_strength_ok and shear_spacing_ok and shear_vsmax_ok

    passed = top_ok and bottom_ok and shear_ok
    return {
        "d_bot_cm": d_bot, "d_top_cm": d_top, "d_v_cm": d_v,
        "bot": bot, "top": top,
        "As_min_bot": As_min_bot, "As_min_top": As_min_top,
        "As_max_bot": As_max_bot, "As_max_top": As_max_top,
        "bot_strength_ok": bot_strength_ok, "top_strength_ok": top_strength_ok,
        "bot_min_ok": bot_min_ok, "top_min_ok": top_min_ok,
        "bot_ductile_ok": bot_ductile_ok, "top_ductile_ok": top_ductile_ok,
        "bottom_ok": bottom_ok, "top_ok": top_ok,
        "Vc_kgf": Vc, "Vs_kgf": Vs, "Vs_max_kgf": Vs_max, "phiVn_kgf": phiVn,
        "s_max_cm": s_max, "shear_ok": shear_ok,
        "passed": passed,
        "verdict_reason":
            "PASS" if passed else "; ".join(
                r for r in (
                    None if bot_strength_ok else "bot phiMn < +Mu",
                    None if bot_min_ok else "bot As < As_min",
                    None if bot_ductile_ok else "bot As > As_max (not tension-controlled)",
                    None if top_strength_ok else "top phiMn < -Mu",
                    None if top_min_ok else "top As < As_min",
                    None if top_ductile_ok else "top As > As_max (not tension-controlled)",
                    None if shear_strength_ok else "phiVn < Vu",
                    None if shear_spacing_ok else "S > s_max",
                    None if shear_vsmax_ok else "Vs > Vs_max",
                ) if r),
    }


def section_calc_verdict_si(*, b_mm, h_mm, cover_mm, fc_mpa, fy_mpa,
                            top_dia_mm, top_As_prov_mm2,
                            bot_dia_mm, bot_As_prov_mm2,
                            stir_dia_mm, Mu_top_kNm, Mu_bot_kNm):
    """Independent recomputation of the `_section_calc` FLEXURE decision
    (SI), including the tension-controlled / As_max limit that the engine's
    pre-EV-03 `_section_calc` never checked.

        As_req : required singly-reinforced tension-controlled steel
        As_min : ACI 10.5.1
        As_max : ACI 10.3.4  (rho_max at eps_t = 0.005)
        req_ok    = As_prov >= As_req  and As_req feasible
        min_ok    = As_prov >= As_min
        ductile_ok= As_prov <= As_max
    """
    d_top = max(h_mm - cover_mm - stir_dia_mm - top_dia_mm / 2.0, 1.0)
    d_bot = max(h_mm - cover_mm - stir_dia_mm - bot_dia_mm / 2.0, 1.0)

    def _req_as(Mu_Nmm, d):
        Rn = Mu_Nmm / (0.90 * b_mm * d ** 2)
        disc = 1.0 - 2.0 * Rn / (0.85 * fc_mpa)
        if disc < 0.0:
            return None, False
        rho = (0.85 * fc_mpa / fy_mpa) * (1.0 - math.sqrt(disc))
        return rho * b_mm * d, True

    def _rho_min(fc, fy):
        return max(0.25 * math.sqrt(fc) / fy, 1.4 / fy)

    def _rho_max(fc, fy):
        b1 = 0.85 if fc <= 28.0 else max(0.65, 0.85 - 0.05 * (fc - 28.0) / 7.0)
        return 0.85 * b1 * fc / fy * EPS_CU / (EPS_CU + EPS_TC)

    As_top_req, feas_top = _req_as(Mu_top_kNm * 1e6, d_top)
    As_bot_req, feas_bot = _req_as(Mu_bot_kNm * 1e6, d_bot)
    As_min = _rho_min(fc_mpa, fy_mpa) * b_mm * d_bot
    As_max_top = _rho_max(fc_mpa, fy_mpa) * b_mm * d_top
    As_max_bot = _rho_max(fc_mpa, fy_mpa) * b_mm * d_bot

    top_req_ok = feas_top and top_As_prov_mm2 >= (As_top_req or math.inf)
    bot_req_ok = feas_bot and bot_As_prov_mm2 >= (As_bot_req or math.inf)
    top_min_ok = top_As_prov_mm2 >= As_min
    bot_min_ok = bot_As_prov_mm2 >= As_min
    top_ductile_ok = top_As_prov_mm2 <= As_max_top
    bot_ductile_ok = bot_As_prov_mm2 <= As_max_bot

    flexure_passed = (top_req_ok and bot_req_ok and top_min_ok and bot_min_ok
                      and top_ductile_ok and bot_ductile_ok)
    return {
        "d_top": d_top, "d_bot": d_bot,
        "As_top_req": As_top_req, "As_bot_req": As_bot_req,
        "As_min": As_min, "As_max_top": As_max_top, "As_max_bot": As_max_bot,
        "top_req_ok": top_req_ok, "bot_req_ok": bot_req_ok,
        "top_min_ok": top_min_ok, "bot_min_ok": bot_min_ok,
        "top_ductile_ok": top_ductile_ok, "bot_ductile_ok": bot_ductile_ok,
        "flexure_passed": flexure_passed,
    }
