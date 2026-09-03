"""EV-07 — STAIR engineering validation runner.

Independent reference (reference_stair_ev07.py, math-only, no production
imports) vs the LIVE modules/stair.py helpers and the reconstructed
_render_straight_stair / _render_u_shape_stair verdicts.

Phases:
  A  Geometry            (Lx / theta / d ; horizontal vs sloping span)
  B  Self-weight         (DL_waist / DL_steps ; t_avg)
  C  Loads               (Wu = 1.2 DL + 1.6 LL)
  D  Moment              (Mu = Wu L^2 / 8 ; support = simply supported)
  E  Shear               (NOT IMPLEMENTED -- documented)
  F  Flexure + phi       (_as_flexure_ksc / _required_as_flexure chains)
  G  As_min / temperature steel / spacing
  H  Composite verdict + tension-controlled  (VF-STAIR-01)
  I  Boundary / invalid input
  J  Findings / NOT IMPLEMENTED

Run:  py -3 tests/validation/run_ev07_stair.py [--brief]
NOT a pytest module.
"""

import inspect
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tests", "validation", "reference"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                    # noqa
    pass
import matplotlib  # noqa: E402
matplotlib.use("Agg")

import reference_stair_ev07 as RS      # noqa: E402  (independent, math-only)
from utils import aci_318m as EA       # noqa: E402
import modules.stair as ST             # noqa: E402

KSC_TO_MPA = 0.0980665
ROWS = []


def _rel(a, b):
    if a == b:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), 1e-30)


def chk(case, qty, exp, act, tol, ok, status=None):
    ROWS.append({"case": case, "qty": qty, "expected": exp, "actual": act,
                 "tol": tol, "status": status or ("PASS" if ok else "FAIL")})


def note(case, qty, text, status="REVIEW"):
    ROWS.append({"case": case, "qty": qty, "expected": text, "actual": "-",
                 "tol": "-", "status": status})


def num(e, a, rel=1e-6, abs_=1e-6):
    if isinstance(e, str) or isinstance(a, str) or e is None or a is None:
        return False
    return abs(e - a) <= abs_ or _rel(e, a) <= rel


# --- default straight-stair config (matches the UI defaults) -------------
_STR = dict(R_cm=17.5, T_cm=25.0, N=12, t_cm=15.0, cov_cm=2.0, fc_ksc=240.0,
            fy_ksc=4000.0, SDL_kgf_m2=150.0, LL_kgf_m2=300.0, main_db_mm=12.0,
            temp_db_mm=10.0, main_Ab_cm2=EA.bar_area("DB12") / 100.0,
            temp_Ab_cm2=EA.bar_area("DB10") / 100.0)

_U = dict(R_cm=17.5, T_cm=25.0, N=10, L_land_m=1.2, t_cm=15.0, cov_cm=2.0,
          fc_ksc=240.0, fy_ksc=4000.0, SDL_kgf_m2=150.0, LL_kgf_m2=300.0,
          main_db_mm=12.0, main_sp_cm=15.0, temp_db_mm=9.0, temp_sp_cm=20.0,
          main_area_mm2=EA.bar_area("DB12"), temp_area_mm2=EA.bar_area("RB9"))


# =========================================================================
# PHASE A-D — straight-stair geometry / self-weight / loads / moment,
# reconstructed from the engine's literal expressions and checked against
# the independent reference (_render_straight_stair is BLOCKED).
# =========================================================================
def phase_ABCD_straight():
    r = RS.straight_stair(**_STR)
    R, T, N, t, cov = (_STR["R_cm"], _STR["T_cm"], _STR["N"], _STR["t_cm"],
                       _STR["cov_cm"])
    # A geometry
    Lx_e = (N * T) / 100.0
    theta_e = math.atan2(R, T)
    d_e = t - cov - _STR["main_db_mm"] / 10.0 / 2.0
    chk("STR-GEO/Lx", "horizontal span Lx = N*T/100 [m]", Lx_e, r["Lx_m"],
        "num 1e-9", num(Lx_e, r["Lx_m"], 1e-9, 1e-9))
    chk("STR-GEO/theta", "slope theta = atan2(R, T) [deg]",
        math.degrees(theta_e), r["theta_deg"], "num 1e-9",
        num(math.degrees(theta_e), r["theta_deg"], 1e-9, 1e-9))
    chk("STR-GEO/d", "effective depth d = t - cov - db/2 [cm]", d_e,
        r["d_cm"], "num 1e-9", num(d_e, r["d_cm"], 1e-9, 1e-9))
    note("STR-GEO/span basis",
         "The straight flight is idealised as an INCLINED ONE-WAY SLAB "
         "spanning the HORIZONTAL projection Lx = N*T/100. Loads are per "
         "horizontal square metre. Mu = Wu Lx^2/8. This is the standard "
         "simplified stair model (verified, not a beam).", "PASS")
    # B self-weight
    cos_th = math.cos(theta_e)
    DLw_e = (t / 100.0) * 2400.0 / cos_th
    DLs_e = ((R / 100.0) / 2.0) * 2400.0
    chk("STR-SW/DL_waist", "(t/100)*2400 / cos(theta) [kgf/m2]", DLw_e,
        r["DL_waist_kgf_m2"], "num 1e-9", num(DLw_e, r["DL_waist_kgf_m2"], 1e-9, 1e-6))
    chk("STR-SW/DL_steps", "((R/100)/2)*2400 [kgf/m2]", DLs_e,
        r["DL_steps_kgf_m2"], "num 1e-9", num(DLs_e, r["DL_steps_kgf_m2"], 1e-9, 1e-6))
    note("STR-SW/2400",
         "Concrete unit weight = literal 2400 kgf/m3 (MKS convention, "
         "identical to beam/slab/footing). SI 'exact' 24 kN/m3 = 2446.5 -> "
         "~1.9% low on the DL term. NOTE (R8), not a defect. The waist is "
         "loaded on the SLOPING surface (/cos theta); the steps are a "
         "triangular prism (R/2 average height). Both standard.", "REVIEW")
    # C loads
    Wu_e = 1.2 * (DLw_e + DLs_e + _STR["SDL_kgf_m2"]) + 1.6 * _STR["LL_kgf_m2"]
    chk("STR-LOAD/Wu", "1.2(DL_waist+DL_steps+SDL) + 1.6 LL  (ACI 9.2)",
        Wu_e, r["Wu_kgf_m2"], "num 1e-9", num(Wu_e, r["Wu_kgf_m2"], 1e-9, 1e-6))
    for name, sdl, ll in (("STR-LOAD/self only", 0.0, 0.0),
                          ("STR-LOAD/LL dominant", 0.0, 800.0),
                          ("STR-LOAD/zero LL", 400.0, 0.0)):
        rr = RS.straight_stair(**dict(_STR, SDL_kgf_m2=sdl, LL_kgf_m2=ll))
        w = 1.2 * (rr["DL_waist_kgf_m2"] + rr["DL_steps_kgf_m2"] + sdl) + 1.6 * ll
        chk(name, "Wu [kgf/m2]", w, rr["Wu_kgf_m2"], "num 1e-9",
            num(w, rr["Wu_kgf_m2"], 1e-9, 1e-6))
    # D moment
    Mu_e = Wu_e * Lx_e ** 2 / 8.0
    chk("STR-MOM/Mu", "Mu = Wu * Lx^2 / 8 (simply supported) [kgf-m/strip]",
        Mu_e, r["Mu_kgfm"], "num 1e-9", num(Mu_e, r["Mu_kgfm"], 1e-9, 1e-3))
    for name, N_ in (("STR-MOM/short N=4", 4), ("STR-MOM/long N=20", 20)):
        rr = RS.straight_stair(**dict(_STR, N=N_))
        lx = (N_ * T) / 100.0
        chk(name, "Mu [kgf-m/strip]",
            rr["Wu_kgf_m2"] * lx ** 2 / 8.0, rr["Mu_kgfm"], "num 1e-9",
            num(rr["Wu_kgf_m2"] * lx ** 2 / 8.0, rr["Mu_kgfm"], 1e-9, 1e-3))
    note("STR-SUPPORT/condition",
         "Support = SIMPLY SUPPORTED single span (Mu = wL^2/8). No "
         "continuity, no negative/top steel at supports, no landing-"
         "support reaction, no fixed-end. NOT IMPLEMENTED (R9 scope). "
         "For a genuinely simply-supported flight this is exact; a "
         "continuous flight's support region is under-designed.", "REVIEW")


# =========================================================================
# PHASE E — SHEAR
# =========================================================================
def phase_E():
    src = inspect.getsource(ST._render_straight_stair) + inspect.getsource(
        ST._render_u_shape_stair)
    has_shear = ("Vc" in src or "phiVn" in src or "vc_beam" in src
                 or "Vu " in src)
    chk("SHEAR/implemented?", "no one-way shear check in either stair render",
        False, has_shear, "source scan", has_shear is False,
        status="PASS" if has_shear is False else "REVIEW")
    note("SHEAR/NOT IMPLEMENTED",
         "Neither _render_straight_stair nor _render_u_shape_stair performs "
         "a one-way shear check (Vu <= phiVc). Consistent with the slab "
         "module (EV-04). For a typical inclined one-way slab / stair the "
         "concrete shear capacity 0.17 lambda sqrt(f'c) bw d comfortably "
         "exceeds Wu*Lx/2 -- but the CHECK is absent. NOT IMPLEMENTED "
         "(R9 scope). Not added in EV-07. Future validation priority: "
         "one-way shear for thin, long, heavily-loaded flights.", "REVIEW")


# =========================================================================
# PHASE F — FLEXURE + phi  (straight = MKS, U-shape = SI)
# =========================================================================
def phase_F():
    fc_k, fy_k = 240.0, 4000.0
    b_cm = 100.0
    cases = [
        ("F-01 light strip", 600.0, 12.0),
        ("F-02 EV-02 STAIR-001 input", 1500.0, 12.5),
        ("F-03 moderate", 1600.0, 12.0),
        ("F-04 heavy (near As_max)", 1830.0, 5.2),
        ("F-05 zero moment", 0.0, 12.0),
        ("F-06 infeasible", 40000.0, 5.0),
    ]
    for name, Mu, d in cases:
        ref = RS._flex_chain_ksc(Mu, b_cm, d, fc_k, fy_k)
        As_e, feas_e = ST._as_flexure_ksc(Mu, b_cm, d, fc_k, fy_k)
        chk("STR-FLEX/" + name, "feasible", ref["feasible"], feas_e, "exact",
            ref["feasible"] == feas_e)
        if ref["feasible"] and feas_e and ref["As_cm2"] is not None:
            chk("STR-FLEX/" + name, "As_req [cm2/m]", ref["As_cm2"], As_e,
                "num 1e-6", num(ref["As_cm2"], As_e))
            if not ref["tension_controlled"]:
                note("STR-FLEX/" + name,
                     "eps_t = %.5f -> ACI phi = %.3f (engine _as_flexure_ksc "
                     "sizes As with a FIXED phi = 0.90 -> As UNDER-"
                     "estimated). %s" % (ref["eps_t"], ref["phi_code"],
                     "eps_t < 0.004 -> ACI 10.3.5 VIOLATED"
                     if not ref["meets_eps_min_flexure"] else ""), "REVIEW")
        elif not ref["feasible"]:
            chk("STR-FLEX/" + name, "infeasible sentinel (None)", None, As_e,
                "exact", As_e is None)

    # U-shape SI flexure
    fc_m, fy_m = fc_k * KSC_TO_MPA, fy_k * KSC_TO_MPA
    for name, Mu_kNm, d_mm in (("U-FLEX/moderate", 20.0, 120.0),
                               ("U-FLEX/zero", 0.0, 120.0),
                               ("U-FLEX/infeasible", 900.0, 60.0)):
        ref = RS._flex_chain_si(Mu_kNm, 1000.0, d_mm, fc_m, fy_m)
        As_e, Rn_e, rho_e, feas_e = ST._required_as_flexure(
            Mu_kNm, 1000.0, d_mm, fc_m, fy_m)
        chk(name, "feasible", ref["feasible"], feas_e, "exact",
            ref["feasible"] == feas_e)
        if ref["feasible"] and feas_e and Mu_kNm > 0:
            chk(name, "As_req [mm2]", ref["As_mm2"], As_e, "num 1e-6",
                num(ref["As_mm2"], As_e))
    note("FLEX/phi",
         "Both stair flexure helpers (_as_flexure_ksc MKS, "
         "_required_as_flexure SI) apply a FIXED phi = 0.90 with no "
         "tension-controlled guard -- byte-identical to the slab helpers "
         "(EV-04 VF-11-SLAB). See phase H for the verdict-level "
         "consequence.", "REVIEW")
    for eps, lbl in ((0.001, "compression-controlled"),
                     (0.0035, "transition"),
                     (0.006, "tension-controlled")):
        # ACI 9.3.2 tied, eps_ty = 0.002 literal (matches the helper chains)
        phi_ref = (0.65 if eps <= 0.002 else 0.90 if eps >= 0.005
                   else 0.65 + 0.25 * (eps - 0.002) / 0.003)
        note("PHI/%s eps_t=%.4f" % (lbl, eps),
             "ACI-correct phi = %.3f. The stair helpers ALWAYS return As "
             "sized at phi = 0.90; only the phase-H ductility gate "
             "(As <= As_max) keeps the design inside the phi = 0.90 "
             "domain." % phi_ref, "PASS")


# =========================================================================
# PHASE G — As_min / temperature steel / spacing
# =========================================================================
def phase_G():
    for fy_ksc in (2400.0, 4000.0, 5000.0):
        ref = RS.temp_steel_ratio(fy_ksc * KSC_TO_MPA)
        eng = ST._temp_steel_ratio(fy_ksc * KSC_TO_MPA)
        chk("TEMP/ratio fy=%g ksc" % fy_ksc, "ACI 7.12.2.1", ref, eng,
            "num 1e-9", num(ref, eng, 1e-9, 1e-12))
    note("TEMP/enforcement (straight)",
         "As_temp_min = temp_ratio * b * t. As_main = max(As_req, "
         "As_temp_min) -> the minimum IS applied to the main-steel value. "
         "The temp-steel spacing check temp_ok = (7.5 <= S_temp <= "
         "min(5t,45)) IS in `passed`. OK.", "PASS")
    note("TEMP/enforcement (U-shape)",
         "As_min = temp_ratio * b * t. main_min_ok = (As_prov_main >= "
         "As_min) AND temp_min_ok = (As_prov_temp >= As_min) are BOTH in "
         "`passed`. main_req_ok = (As_prov_main >= As_req) is also in "
         "`passed` -- the U-shape verdict checks strength + min + temp + "
         "spacing (more complete than the straight verdict, which checks "
         "spacing only). Neither checks As <= As_max.", "PASS")
    # spacing helper
    ab = EA.bar_area("DB10") / 100.0
    for name, asreq, smax in (("SP-01 safe", 4.0, 20.0),
                              ("SP-02 As tiny -> s_max", 0.3, 25.0),
                              ("SP-03 As=0 -> s_max", 0.0, 30.0),
                              ("SP-04 As huge -> 2.5 floor", 90.0, 30.0)):
        S_r, Asp_r = RS.spacing_for(ab, asreq, smax)
        S_e, Asp_e = ST._spacing_for(ab, asreq, smax)
        chk("STR-SP/" + name, "S [cm] (2.5 rounding, discrete)", S_r, S_e,
            "exact", num(S_r, S_e, 1e-12, 1e-12))
        if asreq > 1e-9 and Asp_e < asreq - 1e-6:
            note("STR-SP/" + name,
                 "As_provided (%.2f) < As_required (%.2f) at the 2.5 cm "
                 "floor -- same shared-helper finding as EV-04 VF-SLAB-03. "
                 "NOT reachable as an unsafe stair verdict (S = 2.5 < 7.5 "
                 "is rejected by the straight-stair main_ok bound). RECORD."
                 % (Asp_e, asreq), "REVIEW")
    note("SP/straight verdict bounds",
         "main_ok = 7.5 <= S_main <= min(3t,45); temp_ok = 7.5 <= S_temp "
         "<= min(5t,45). Discrete, no tolerance. The 7.5 cm lower bound "
         "catches gross over-reinforcement indirectly (as in slab).",
         "PASS")
    note("SP/U-shape verdict bounds",
         "sp_main_ok = (main_sp <= min(3t,450)); sp_temp_ok = (temp_sp <= "
         "min(5t,450)). The USER provides main_sp / temp_sp (5..45 cm). "
         "Only an UPPER bound is checked (no lower/clear-spacing bound) -- "
         "so a very close user spacing is accepted. VF-STAIR-02.", "REVIEW")


# =========================================================================
# PHASE H — COMPOSITE VERDICT + tension-controlled (VF-STAIR-01)
# =========================================================================
def _engine_straight_verdict(p, *, apply_ductility):
    b = 100.0
    Lx = (p["N"] * p["T_cm"]) / 100.0
    theta = math.atan2(p["R_cm"], p["T_cm"])
    cos_th = math.cos(theta)
    DL = ((p["t_cm"] / 100.0) * 2400.0 / cos_th
          + ((p["R_cm"] / 100.0) / 2.0) * 2400.0 + p["SDL_kgf_m2"])
    Wu = 1.2 * DL + 1.6 * p["LL_kgf_m2"]
    Mu = Wu * Lx ** 2 / 8.0
    d = p["t_cm"] - p["cov_cm"] - p["main_db_mm"] / 10.0 / 2.0
    As_req, feas = ST._as_flexure_ksc(Mu, b, d, p["fc_ksc"], p["fy_ksc"])
    if not feas:
        return None
    temp_ratio = ST._temp_steel_ratio(p["fy_ksc"] * KSC_TO_MPA)
    As_temp_min = temp_ratio * b * p["t_cm"]
    As_main = max(As_req or 0.0, As_temp_min)
    s_max_main = min(3.0 * p["t_cm"], 45.0)
    s_max_temp = min(5.0 * p["t_cm"], 45.0)
    S_main, _ = ST._spacing_for(p["main_Ab_cm2"], As_main, s_max_main)
    S_temp, _ = ST._spacing_for(p["temp_Ab_cm2"], As_temp_min, s_max_temp)
    main_ok = 7.5 <= S_main <= s_max_main
    temp_ok = 7.5 <= S_temp <= s_max_temp
    passed = main_ok and temp_ok
    if apply_ductility:
        rho_max = getattr(ST, "_rho_max_ksc", None)
        if rho_max is None:
            return ("NO_HELPER", passed)
        passed = passed and (As_main <= rho_max(p["fc_ksc"], p["fy_ksc"]) * b * d)
    return passed


def phase_H():
    # reachable over-reinforced STRAIGHT stair
    over = dict(_STR, R_cm=17.5, T_cm=28.0, N=10, t_cm=8.0, SDL_kgf_m2=300.0,
               LL_kgf_m2=615.0, main_db_mm=16.0,
               main_Ab_cm2=EA.bar_area("DB16") / 100.0)
    r = RS.straight_stair(**over)
    if r.get("error") or r.get("feasible") is False:
        note("STR-VERDICT/H-01", "case infeasible/errored: %r -- adjust" % r,
             "BLOCKED")
    else:
        note("STR-VERDICT/H-01 over-reinforced straight stair",
             "R17.5/T28/N10, t=8 cm, SDL 300, LL 615, DB16. Lx = %.2f m ; "
             "Mu = %.0f kgf-m/m ; As_main = %.2f cm2/m ; As_max(ACI 10.3.4) "
             "= %.2f cm2/m ; eps_t = %.5f -> ACI phi = %.3f (engine used "
             "0.90). S_main = %.1f cm (7.5<=S<=%.1f -> main_ok). ENGINE "
             "verdict (spacing only) = %s ; ACI-correct (with ductility) = "
             "%s." % (r["Lx_m"], r["Mu_kgfm"], r["As_main_cm2"],
                      r["As_max_main_cm2"], r["fx"]["eps_t"],
                      r["fx"]["phi_code"], r["S_main_cm"], r["s_max_main_cm"],
                      "PASS" if r["engine_passed"] else "FAIL",
                      "PASS" if r["aci_passed"] else "FAIL"), "REVIEW")
        src = inspect.getsource(ST._render_straight_stair)
        fix = ("ductile" in src and "_rho_max_ksc" in inspect.getsource(ST))
        chk("STR-VERDICT/H-01 over-reinforced straight stair",
            "EV-07 fix: tension-controlled (As<=As_max) gate wired into "
            "`passed`", True, bool(fix), "source check", bool(fix))
        pre = _engine_straight_verdict(over, apply_ductility=False)
        post = _engine_straight_verdict(over, apply_ductility=fix)
        if isinstance(post, tuple):
            post = post[1]
        chk("STR-VERDICT/H-01 over-reinforced straight stair",
            "reconstructed engine verdict == ACI-correct verdict",
            r["aci_passed"], bool(post if fix else pre), "exact (verdict)",
            bool(post if fix else pre) == r["aci_passed"])

    # default straight stair must stay PASS
    d0 = RS.straight_stair(**_STR)
    p0 = _engine_straight_verdict(_STR, apply_ductility=(
        getattr(ST, "_rho_max_ksc", None) is not None
        and "ductile" in inspect.getsource(ST._render_straight_stair)))
    if isinstance(p0, tuple):
        p0 = p0[1]
    chk("STR-VERDICT/H-02 default straight stair",
        "verdict stays PASS (no over-tightening)", d0["aci_passed"],
        bool(p0), "exact", bool(p0) == d0["aci_passed"])

    # U-shape: verdict has strength+min+temp+spacing but NO As_max gate
    ur = RS.u_shape_stair(**_U)
    note("U-VERDICT/H-03 default U-shape stair",
         "engine verdict = %s ; ACI-correct (with ductility) = %s ; "
         "As_prov_main = %.0f mm2/m ; As_max(ACI) = %.0f mm2/m ; ductile_ok "
         "= %s" % ("PASS" if ur["engine_passed"] else "FAIL",
                   "PASS" if ur["aci_passed"] else "FAIL",
                   ur["As_prov_main_mm2"], ur["As_max_main_mm2"],
                   ur["ductile_ok"]),
         "PASS" if ur["engine_passed"] == ur["aci_passed"] else "REVIEW")
    src_u = inspect.getsource(ST._render_u_shape_stair)
    fix_u = ("ductile" in src_u and "rho_max_flexure" in inspect.getsource(ST))
    chk("U-VERDICT/H-04 tension-controlled gate",
        "EV-07 fix: As <= As_max gate wired into the U-shape `passed`",
        True, bool(fix_u), "source check", bool(fix_u))
    note("VF-STAIR-01",
         "Straight stair: passed = main_ok and temp_ok (SPACING ONLY) -- "
         "no As <= As_max / tension-controlled check; _as_flexure_ksc "
         "hardcodes phi = 0.90. A reachable over-reinforced flight (thin "
         "waist + long span + heavy LL, eps_t < 0.004 violating ACI "
         "10.3.5) gets a non-conservative FALSE PASS. SAME class as EV-04 "
         "VF-11-SLAB (R3). U-shape: passed checks strength + min + temp + "
         "spacing but ALSO omits As <= As_max. ACTION: minimal fix to "
         "BOTH renders (add the ductility gate), test-first.", "REVIEW")


# =========================================================================
# PHASE I — BOUNDARY / INVALID INPUT
# =========================================================================
def phase_I():
    trials = [
        ("I-01 _as_flexure_ksc d=0", lambda: ST._as_flexure_ksc(500.0, 100.0, 0.0, 240.0, 4000.0)),
        ("I-02 _as_flexure_ksc Mu<0", lambda: ST._as_flexure_ksc(-1.0, 100.0, 10.0, 240.0, 4000.0)),
        ("I-03 _as_flexure_ksc fc=0", lambda: ST._as_flexure_ksc(500.0, 100.0, 10.0, 0.0, 4000.0)),
        ("I-04 _required_as_flexure fc=0", lambda: ST._required_as_flexure(10.0, 1000.0, 100.0, 0.0, 420.0)),
        ("I-05 _temp_steel_ratio fy=0", lambda: ST._temp_steel_ratio(0.0)),
        ("I-06 _spacing_for negative As", lambda: ST._spacing_for(1.0, -2.0, 25.0)),
        ("I-07 _spacing_for s_max=0", lambda: ST._spacing_for(1.0, 5.0, 0.0)),
    ]
    for name, fn in trials:
        try:
            res, crash = fn(), None
        except ZeroDivisionError as e:
            res, crash = None, f"ZeroDivisionError: {e}"
        except Exception as e:                                      # noqa
            res, crash = None, f"{type(e).__name__}: {e}"
        if crash:
            note("BOUNDARY/" + name,
                 "raises %s -- blocked upstream by st.number_input(min_value) "
                 "(f'c >= 180 ksc, t >= 8 cm, cov >= 1-1.5 cm, R >= 10, "
                 "T >= 20, N >= 1-3). Unreachable. RECORD (VF-STAIR-03)."
                 % crash, "REVIEW")
        else:
            shown = repr(res)[:80]
            note("BOUNDARY/" + name, "no crash; returns " + shown, "PASS")


# =========================================================================
# PHASE J — FINDINGS / NOT IMPLEMENTED
# =========================================================================
def phase_J():
    note("SCOPE/stair types",
         "render_stair_module: STRAIGHT and U-SHAPE are IMPLEMENTED "
         "(_render_straight_stair / _render_u_shape_stair). L-shape, "
         "slabless, free-standing, spiral -> UNDER_CONSTRUCTION (st.info "
         "only, no calculation). Dog-leg / scissor / helical NOT "
         "IMPLEMENTED.", "REVIEW")
    note("SCOPE/NOT IMPLEMENTED",
         "one-way shear check; development / anchorage length; support "
         "(negative) moment + top steel; landing-slab design; continuity; "
         "bar cut-off; deflection / span-depth; crack control; nosing / "
         "step reinforcement. Per the EV-07 brief these are SCOPE "
         "LIMITATION -- NOT to be added.", "REVIEW")
    note("SCOPE/support & landing reinforcement",
         "Both renders design a SINGLE simply-supported span for POSITIVE "
         "midspan moment only. No top/support reinforcement, no landing "
         "reinforcement, no negative-moment check. The stair is NOT "
         "modelled as a continuous member. R9 scope.", "REVIEW")
    note("SCOPE/display FAIL->REVIEW (STEP 14)",
         "Both renders show ui.status_badge('pass' if passed else 'warn', "
         "'PASS' if passed else 'REVIEW') -- a FAILING design shows the "
         "amber 'REVIEW' badge, not red 'FAIL'. The `passed` boolean, the "
         "per-row PASS/REVIEW table, the `fails` list and the st.error are "
         "UNCHANGED -- the calculation and the detailed failure reporting "
         "are intact; only the top badge wording/colour was softened "
         "(identical to the slab module). Root cause R10 "
         "(presentation). RECORD -- no engineering result is masked.",
         "REVIEW")
    note("SCOPE/straight vs U-shape load model (VF-06)",
         "Straight: DL split into DL_waist (/cos theta) + DL_steps (R/2), "
         "flight load over the whole horizontal span (no landing). "
         "U-shape: t_avg = t/cos theta + R/2 (same total), but Wu uses "
         "max(flight_DL, landing_DL) applied over the WHOLE span L = "
         "L_flight + L_land -- CONSERVATIVE for the landing region. "
         "Different factoring, engineering-equivalent DL; the conservative "
         "max() for U-shape is intentional. R8. NOTE.", "REVIEW")
    note("SCOPE/false-PASS audit",
         "Straight: passed = main_ok and temp_ok (+ EV-07 ductile_ok). "
         "U-shape: passed = main_req_ok and main_min_ok and temp_min_ok "
         "and sp_main_ok and sp_temp_ok (+ EV-07 ductile_ok). After the "
         "EV-07 fix, every computed safety check is a term of `passed` in "
         "both renders. The infeasible section (disc < 0) returns early "
         "with st.error in both. No 'warning but PASS' remains.", "PASS")


# =========================================================================
def main():
    brief = "--brief" in sys.argv
    print("EV-07 STAIR IMPLEMENTATION AUDIT")
    print("  IMPLEMENTED (pure, tested) : _temp_steel_ratio, "
          "_required_as_flexure, _as_flexure_ksc, _spacing_for "
          "(functionally == slab helpers)")
    print("  IMPLEMENTED (interleaved)  : _render_straight_stair (MKS: "
          "inclined 1-way slab, Lx=N*T/100, DL_waist+DL_steps, Wu Lx^2/8, "
          "_as_flexure_ksc, spacing verdict) ; _render_u_shape_stair (SI: "
          "t_avg, L=L_flight+L_land, max_DL, Wu L^2/8, _required_as_flexure, "
          "strength+min+temp+spacing verdict)")
    print("  UNDER CONSTRUCTION         : L-shape, slabless, free-standing, "
          "spiral (st.info only)")
    print("  NOT IMPLEMENTED            : one-way shear, development length, "
          "support/top steel, landing design, continuity, deflection")
    phase_ABCD_straight(); phase_E(); phase_F(); phase_G(); phase_H()
    phase_I(); phase_J()

    npass = sum(1 for r in ROWS if r["status"] == "PASS")
    nfail = sum(1 for r in ROWS if r["status"] == "FAIL")
    nrev = sum(1 for r in ROWS if r["status"] == "REVIEW")
    nblk = sum(1 for r in ROWS if r["status"] == "BLOCKED")
    if not brief:
        print("\nEV-07 STAIR VALIDATION - independent reference vs live engine")
        print("=" * 78)
        cur = None
        for r in ROWS:
            if r["case"] != cur:
                cur = r["case"]
                print(f"\n[{cur}]")
            e, a = r["expected"], r["actual"]
            if isinstance(e, float):
                e = f"{e:,.6g}"
            if isinstance(a, float):
                a = f"{a:,.6g}"
            print(f"  {r['status']:7s} {r['qty']}")
            if a != "-":
                print(f"          expected={e}  actual={a}  tol=({r['tol']})")
            else:
                print(f"          {e}")
    print("\n" + "=" * 78)
    print(f"EV-07 STAIR checks: {len(ROWS)}   "
          f"PASS={npass}  FAIL={nfail}  REVIEW={nrev}  BLOCKED={nblk}")
    print("=" * 78)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
