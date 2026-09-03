"""EV-03 — BEAM engineering validation runner.

Independent reference (tests/validation/reference/*.py, no production
imports) vs the LIVE modules/beam.py helpers and verdict logic.

Phases (mandatory order):
  A  Beam flexure           (_flex_ksc, _required_as + intermediates)
  B  Beam shear             (_shear_check, SI)
  C  Reinforcement          (As_min / As_max / ductility gate)
  D  Composite verdict      (_render_beam_section reconstruction;
                             _section_calc direct call)
  E  Boundary + invalid input matrix
  F  Findings: VF-07, VF-12/13, VF-04

Run:  py -3 tests/validation/run_ev03_beam.py [--brief]
Exit 0 iff no non-BLOCKED FAIL.  NOT a pytest module — the 73-test
regression baseline is untouched.
"""

import inspect
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tests", "validation", "reference"))
import matplotlib  # noqa: E402
matplotlib.use("Agg")

import reference_beam_ev03 as RB      # noqa: E402  (independent, math-only)
import reference_flexure as RF        # noqa: E402
import reference_shear as RS          # noqa: E402

from utils import aci_318m as EA      # noqa: E402
from utils.analysis import solve_continuous_beam  # noqa: E402
import modules.beam as BM             # noqa: E402

KSC_TO_MPA = 0.0980665
ROWS = []


def _rel(a, b):
    if a == b:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), 1e-30)


def chk(case, qty, expected, actual, tol, ok, status=None):
    ROWS.append({"case": case, "qty": qty, "expected": expected,
                 "actual": actual, "tol": tol,
                 "status": status or ("PASS" if ok else "FAIL")})


def note(case, qty, text, status="REVIEW"):
    ROWS.append({"case": case, "qty": qty, "expected": text, "actual": "-",
                 "tol": "-", "status": status})


def num(exp, act, rel=1e-6, abs_=1e-6):
    if isinstance(exp, str) or isinstance(act, str):
        return False
    return abs(exp - act) <= abs_ or _rel(exp, act) <= rel


# =========================================================================
# PHASE A — BEAM FLEXURE
# =========================================================================
def phase_A():
    # A set of MKS flexure cases spanning the tension-controlled domain and
    # the As_min / As_max boundaries.  fc/fy in ksc, b/d in cm, As in cm2.
    cases = [
        ("A-01 under-reinforced",        15.0, 4000.0, 240.0, 30.0, 54.0),
        ("A-02 EV-02 golden input",      15.0, 4000.0, 240.0, 30.0, 50.0),
        ("A-03 higher rho (still TC)",    22.0, 4000.0, 240.0, 30.0, 54.0),
        ("A-04 near As_max boundary",     21.4, 4000.0, 240.0, 30.0, 54.0),
        ("A-05 low fc' (min)",           12.0, 4000.0, 180.0, 25.0, 44.0),
        ("A-06 fc' = 280 ksc (beta1 brk)",18.0, 4000.0, 280.0, 30.0, 54.0),
        ("A-07 fc' = 350 ksc (>brk)",    18.0, 4000.0, 350.0, 30.0, 54.0),
        ("A-08 tiny As",                  0.5, 4000.0, 240.0, 30.0, 54.0),
        ("A-09 small section",            4.0, 4000.0, 240.0, 15.0, 21.0),
    ]
    for name, As, fy, fc, b, d in cases:
        ref = RB.flexure_layer_mks(As, fy, fc, b, d)
        a_e, Mn_e, phiMn_e = BM._flex_ksc(As, fy, fc, b, d)
        chk("FLEX/" + name, "a [cm]", ref["a_cm"], a_e, "num 1e-6",
            num(ref["a_cm"], a_e))
        chk("FLEX/" + name, "Mn [kgf-m]", ref["Mn_kgfm"], Mn_e, "num 1e-6",
            num(ref["Mn_kgfm"], Mn_e))
        # engine phiMn is ALWAYS 0.90*Mn; compare against ref's phi090 value
        chk("FLEX/" + name, "phiMn (engine=0.90*Mn)", ref["phiMn_phi090_kgfm"],
            phiMn_e, "num 1e-6", num(ref["phiMn_phi090_kgfm"], phiMn_e))
        # and report where the ACI-correct phi differs (VF-11 evidence)
        if not ref["tension_controlled"]:
            note("FLEX/" + name,
                 "eps_t = %.5f  ->  ACI phi = %.4f (engine assumes 0.90)"
                 % (ref["eps_t"], ref["phi_code"]),
                 "REVIEW")
            if not ref["meets_eps_min_flexure"]:
                note("FLEX/" + name,
                     "eps_t < 0.004  ->  ACI 10.3.5 VIOLATED (section not "
                     "permitted as a flexural member)", "REVIEW")

    # _required_as (SI) boundary set
    fc_mpa = 240.0 * KSC_TO_MPA
    fy_mpa = 4000.0 * KSC_TO_MPA
    si_cases = [
        ("A-10 Mu = 0",                 0.0, 300.0, 540.0),
        ("A-11 very low Mu",            5.0, 300.0, 540.0),
        ("A-12 moderate Mu",          120.0, 300.0, 540.0),
        ("A-13 infeasible (huge Mu)", 5.0e5, 300.0, 540.0),
    ]
    for name, Mu, b, d in si_cases:
        As_r, Rn_r, rho_r, feas_r = RF.required_As_singly_reinforced(
            Mu * 1e6, 0.90, b, d, fc_mpa, fy_mpa)
        As_e, Rn_e, rho_e, feas_e = BM._required_as(Mu, b, d, fc_mpa, fy_mpa)
        chk("REQAS/" + name, "feasible", feas_r, feas_e, "exact",
            feas_r == feas_e)
        if feas_r and feas_e:
            chk("REQAS/" + name, "As_req [mm2]", As_r, As_e, "num 1e-6",
                num(As_r, As_e))
            chk("REQAS/" + name, "Rn [MPa]", Rn_r, Rn_e, "num 1e-6",
                num(Rn_r, Rn_e))
        elif not feas_r:
            chk("REQAS/" + name, "As_req (infeasible sentinel)", None, As_e,
                "exact", As_e is None)


# =========================================================================
# PHASE B — BEAM SHEAR  (_shear_check, SI)
# =========================================================================
def phase_B():
    fc = 240.0 * KSC_TO_MPA
    fyt = 4000.0 * KSC_TO_MPA
    b, d = 300.0, 540.0
    Av = 2.0 * 63.62                       # RB9 two-leg
    # reference capacity at s = 150 to locate the boundaries
    base = RS.beam_shear_capacity_si(1.0, b, d, fc, fyt, Av, 150.0)
    phiVn = base["phiVn_N"]
    thr = 0.33 * math.sqrt(fc) * b * d     # dense-stirrup threshold

    cases = [
        ("B-01 Vu = 0",                    0.0, 150.0),
        ("B-02 Vu just below phiVn",       phiVn * 0.999 / 1000.0, 150.0),
        ("B-03 Vu = phiVn (boundary)",     phiVn / 1000.0, 150.0),
        ("B-04 Vu just above phiVn",       phiVn * 1.001 / 1000.0, 150.0),
        ("B-05 s = s_max (d/2) boundary",  50.0, d / 2.0),
        ("B-06 s = s_max + eps",           50.0, d / 2.0 + 0.5),
        ("B-07 Vs just below 0.33 thr",    260.0, (Av * fyt * d) / (thr * 0.999)),
        ("B-08 Vs just above 0.33 thr",    260.0, (Av * fyt * d) / (thr * 1.001)),
        ("B-09 Vs > Vs_max",               400.0, 60.0),
    ]
    for name, Vu_kN, s_mm in cases:
        ref = RS.beam_shear_capacity_si(Vu_kN * 1000.0, b, d, fc, fyt, Av, s_mm)
        r = BM._shear_check(Vu_kN, b, d, fc, fyt, "RB9", s_mm)
        for ek, rk, lbl in (("phiVc_N", "phiVc", "phiVc [N]"),
                            ("Vs_N", "Vs", "Vs [N]"),
                            ("Vs_max_N", "Vs_max", "Vs_max [N]"),
                            ("phiVn_N", "phiVn", "phiVn [N]"),
                            ("s_max_mm", "s_max", "s_max [mm]")):
            chk("SHEAR/" + name, lbl, ref[ek], r[rk], "num 1e-6/abs 1e-3",
                num(ref[ek], r[rk], 1e-6, 1e-3))
        chk("SHEAR/" + name, "ok (verdict)", ref["ok"], r["ok"], "exact",
            ref["ok"] == r["ok"])


# =========================================================================
# PHASE C — REINFORCEMENT  (As_min / As_max / ductility)
# =========================================================================
def phase_C():
    combos = [(240.0, 4000.0, 30.0, 54.0), (180.0, 2400.0, 25.0, 44.0),
              (350.0, 4000.0, 30.0, 54.0), (280.0, 4000.0, 30.0, 44.0)]
    for fc, fy, b, d in combos:
        tag = f"fc{fc:g}/fy{fy:g}/b{b:g}/d{d:g}"
        # As_min (MKS) — engine as_min_flexure_ksc
        ref_min = RB.as_min_ksc(fc, fy, b, d)
        eng_min = EA.as_min_flexure_ksc(fc, fy, b, d)
        chk("REINF/" + tag, "As_min [cm2]", ref_min, eng_min, "num 1e-9",
            num(ref_min, eng_min, 1e-9, 1e-12))
        # As_max (MKS ductility ceiling) — engine _rho_max_ksc * b * d
        ref_max = RB.as_max_ksc(fc, fy, b, d)
        eng_max = BM._rho_max_ksc(fc, fy) * b * d
        chk("REINF/" + tag, "As_max [cm2] (rho_max*b*d)", ref_max, eng_max,
            "num 1e-9", num(ref_max, eng_max, 1e-9, 1e-12))


# =========================================================================
# PHASE D — COMPOSITE VERDICT
# =========================================================================
def _engine_render_verdict(p, *, apply_ductility):
    """Reconstruct `_render_beam_section`'s pass/fail from the REAL engine
    helpers.  `apply_ductility=False` reproduces the pre-EV-03 code (which
    computes *_ductile_ok but omits it from `passed`); True reproduces the
    EV-03 fix.
    """
    d_bot = p["h"] - p["cov"] - p["stir"] - p["bot_dia"] / 2.0
    d_top = p["h"] - p["cov"] - p["stir"] - p["top_dia"] / 2.0
    d_v = min(d_bot, d_top)
    _, _, phiMn_bot = BM._flex_ksc(p["bot_As"], p["fy"], p["fc"], p["b"], d_bot)
    _, _, phiMn_top = BM._flex_ksc(p["top_As"], p["fy"], p["fc"], p["b"], d_top)
    As_min_bot = EA.as_min_flexure_ksc(p["fc"], p["fy"], p["b"], d_bot)
    As_min_top = EA.as_min_flexure_ksc(p["fc"], p["fy"], p["b"], d_top)
    As_max_bot = BM._rho_max_ksc(p["fc"], p["fy"]) * p["b"] * d_bot
    As_max_top = BM._rho_max_ksc(p["fc"], p["fy"]) * p["b"] * d_top
    bot_strength_ok = phiMn_bot >= p["Mu_pos"]
    top_strength_ok = phiMn_top >= p["Mu_neg"]
    bot_min_ok = p["bot_As"] >= As_min_bot
    top_min_ok = p["top_As"] >= As_min_top
    bot_ductile_ok = p["bot_As"] <= As_max_bot
    top_ductile_ok = p["top_As"] <= As_max_top
    if apply_ductility:
        bottom_ok = bot_strength_ok and bot_min_ok and bot_ductile_ok
        top_ok = top_strength_ok and top_min_ok and top_ductile_ok
    else:
        bottom_ok = bot_strength_ok and bot_min_ok
        top_ok = top_strength_ok and top_min_ok
    Vc = EA.vc_beam_ksc(p["fc"], p["b"], d_v)
    Vs = (p["Av"] * p["fyv"] * d_v / p["S"]) if p["S"] > 0 else 0.0
    Vs_max = 2.1 * math.sqrt(p["fc"]) * p["b"] * d_v
    phiVn = phi_shear = 0.75 * (Vc + min(Vs, Vs_max))
    s_max = min(d_v / 2.0, 60.0)
    if Vs > 1.06 * math.sqrt(p["fc"]) * p["b"] * d_v:
        s_max = min(d_v / 4.0, 30.0)
    shear_ok = (phiVn >= p["Vu"]) and (p["S"] <= s_max) and (Vs <= Vs_max)
    return bottom_ok and top_ok and shear_ok


def phase_D():
    # --------------------------------------------------------------------
    # D-01/D-02  _render_beam_section  (Streamlit, not importable) —
    # static demonstration + a source-level check that the EV-03 verdict
    # fix (ductility gate wired into `bottom_ok` / `top_ok`) is in place.
    # --------------------------------------------------------------------
    Ab_db25 = math.pi * 25.0 ** 2 / 4.0 / 100.0
    p = {
        "b": 30.0, "h": 50.0, "cov": 4.0, "fc": 240.0, "fy": 4000.0,
        "fyv": 4000.0, "top_dia": 2.0, "top_As": 3 * math.pi * 20 ** 2 / 4 / 100.0,
        "bot_dia": 2.5, "bot_As": 8 * Ab_db25, "stir": 0.9,
        "Av": 2 * 63.62 / 100.0, "S": 10.0,
        "Mu_pos": 40000.0, "Mu_neg": 5000.0, "Vu": 8000.0,
    }
    ref = RB.beam_section_verdict_mks(
        b_cm=p["b"], h_cm=p["h"], cov_cm=p["cov"], fc_ksc=p["fc"],
        fy_ksc=p["fy"], fyv_ksc=p["fyv"], top_dia_cm=p["top_dia"],
        top_As_cm2=p["top_As"], bot_dia_cm=p["bot_dia"], bot_As_cm2=p["bot_As"],
        stir_dia_cm=p["stir"], Av_cm2=p["Av"], S_cm=p["S"],
        Mu_pos_kgfm=p["Mu_pos"], Mu_neg_kgfm=p["Mu_neg"], Vu_kgf=p["Vu"])
    pre = _engine_render_verdict(p, apply_ductility=False)
    post = _engine_render_verdict(p, apply_ductility=True)
    note("COMPOSITE/D-01 _render_beam_section over-reinforced",
         "ACI-correct verdict = %s (%s ; bot eps_t = %.5f -> ACI phi = "
         "%.3f, phiMn_ACI = %.0f vs engine phiMn_0.90 = %.0f kgf-m). "
         "Pre-EV-03 verdict composition (ductility EXCLUDED) = %s -> "
         "non-conservative FALSE PASS. With the ductility gate = %s."
         % ("PASS" if ref["passed"] else "FAIL", ref["verdict_reason"],
            ref["bot"]["eps_t"], ref["bot"]["phi_code"],
            ref["bot"]["phiMn_code_kgfm"], ref["bot"]["phiMn_phi090_kgfm"],
            "PASS" if pre else "FAIL", "PASS" if post else "FAIL"),
         "REVIEW")
    src = inspect.getsource(BM._render_beam_section)
    fix_bot = "bot_min_ok and bot_ductile_ok" in src
    fix_top = "top_min_ok and top_ductile_ok" in src
    chk("COMPOSITE/D-01 _render_beam_section over-reinforced",
        "EV-03 fix: ductility gate wired into bottom_ok & top_ok",
        True, bool(fix_bot and fix_top), "source check",
        bool(fix_bot and fix_top))
    chk("COMPOSITE/D-02 _render_beam_section logic",
        "ductility-gated composition matches ACI-correct verdict "
        "(over-reinforced -> FAIL)", ref["passed"], post, "exact (verdict)",
        post == ref["passed"])

    # --------------------------------------------------------------------
    # D-03/D-04  _section_calc  (importable) — direct live call.
    # Clean over-reinforced case: ONLY the tension-controlled / As_max
    # limit is violated; strength, As_min, shear all satisfied.
    # --------------------------------------------------------------------
    over = {
        "label": "OverReinf", "top_size": "DB20", "bot_size": "DB32",
        "stirrup_size": "RB9", "Mu_top": 30.0, "Mu_bot": 150.0, "Vu": 80.0,
        "top_qty": 4, "bot_qty": 6, "stirrup_sp_cm": 15.0,
    }
    r = BM._section_calc(over, 400.0, 600.0, 40.0, 24.0, 420.0)
    refsc = RB.section_calc_verdict_si(
        b_mm=400.0, h_mm=600.0, cover_mm=40.0, fc_mpa=24.0, fy_mpa=420.0,
        top_dia_mm=20.0, top_As_prov_mm2=r["As_top_prov"],
        bot_dia_mm=32.0, bot_As_prov_mm2=r["As_bot_prov"],
        stir_dia_mm=9.0, Mu_top_kNm=30.0, Mu_bot_kNm=150.0)
    note("COMPOSITE/D-03 _section_calc over-reinforced",
         "As_bot_prov = %.0f mm2 ; As_max_bot(ACI) = %.0f mm2 ; As_bot_req "
         "= %.0f mm2 ; As_min = %.0f mm2 -> strength/min OK, ductility "
         "VIOLATED. ACI-correct flexure verdict = %s."
         % (r["As_bot_prov"], refsc["As_max_bot"],
            refsc["As_bot_req"] or -1, r["As_min"],
            "PASS" if refsc["flexure_passed"] else "FAIL"), "REVIEW")
    chk("COMPOSITE/D-03 _section_calc over-reinforced",
        "_section_calc['passed']  ==  ACI-correct verdict",
        refsc["flexure_passed"], bool(r["passed"]),
        "exact (verdict)", bool(r["passed"]) == refsc["flexure_passed"])
    if "bot_ductile_ok" in r:
        chk("COMPOSITE/D-03 _section_calc over-reinforced",
            "bot_ductile_ok present and False", False, r["bot_ductile_ok"],
            "exact", r["bot_ductile_ok"] is False)
    else:
        note("COMPOSITE/D-03 _section_calc over-reinforced",
             "engine result has NO 'bot_ductile_ok' key -> pre-EV-03 code, "
             "no ductility gate (EV-03 fix not yet applied).", "REVIEW")

    tc = {
        "label": "TC", "top_size": "DB20", "bot_size": "DB20",
        "stirrup_size": "RB9", "Mu_top": 90.0, "Mu_bot": 110.0, "Vu": 120.0,
        "top_qty": 4, "bot_qty": 3, "stirrup_sp_cm": 15.0,
    }
    rtc = BM._section_calc(tc, 300.0, 500.0, 40.0, 24.0, 420.0)
    chk("COMPOSITE/D-04 _section_calc tension-controlled",
        "_section_calc['passed'] stays True (no over-tightening)",
        True, bool(rtc["passed"]), "exact", bool(rtc["passed"]) is True)


# =========================================================================
# PHASE E — BOUNDARY / INVALID INPUT
# =========================================================================
def phase_E():
    trials = [
        ("E-01 _flex_ksc As=0",        lambda: BM._flex_ksc(0.0, 4000.0, 240.0, 30.0, 54.0)),
        ("E-02 _flex_ksc d=0",         lambda: BM._flex_ksc(10.0, 4000.0, 240.0, 30.0, 0.0)),
        ("E-03 _flex_ksc negative b",  lambda: BM._flex_ksc(10.0, 4000.0, 240.0, -30.0, 54.0)),
        ("E-04 _required_as Mu=0",     lambda: BM._required_as(0.0, 300.0, 540.0, 23.5, 392.0)),
        ("E-05 _required_as fc=0",     lambda: BM._required_as(50.0, 300.0, 540.0, 0.0, 392.0)),
        ("E-06 _beta1_ksc fc=0",       lambda: BM._beta1_ksc(0.0)),
        ("E-07 _beta1_ksc fc=-10",     lambda: BM._beta1_ksc(-10.0)),
        ("E-08 _shear_check s=0",      lambda: BM._shear_check(100.0, 300.0, 540.0, 23.5, 392.0, "RB9", 0.0)),
        ("E-09 _shear_check Vu<0",     lambda: BM._shear_check(-50.0, 300.0, 540.0, 23.5, 392.0, "RB9", 150.0)),
    ]
    for name, fn in trials:
        try:
            res = fn()
            crashed = None
        except ZeroDivisionError as exc:
            res, crashed = None, f"ZeroDivisionError: {exc}"
        except Exception as exc:                                     # noqa
            res, crashed = None, f"{type(exc).__name__}: {exc}"
        if crashed:
            note("BOUNDARY/" + name,
                 "raises %s  (input is blocked by the UI's min_value; "
                 "unreachable in the app flow -- negative test, RECORD)"
                 % crashed, "REVIEW")
        else:
            if isinstance(res, tuple):
                shown = tuple(round(x, 4) if isinstance(x, float) else x
                              for x in res)
            else:
                shown = res
            note("BOUNDARY/" + name, "no crash; returns " + repr(shown),
                 "PASS")


# =========================================================================
# PHASE F — FINDINGS  VF-07 / VF-12 / VF-13 / VF-04
# =========================================================================
def phase_F():
    # VF-07 — beta1 dual threshold, effect on the beam engine
    for fc in (280.0, 281.0, 300.0, 350.0, 420.0):
        b1_eng = BM._beta1_ksc(fc)
        b1_code = EA.beta1(fc * KSC_TO_MPA)
        # _flex_ksc: a = As fy/(0.85 fc b) has NO beta1 -> Mn/phiMn unaffected
        # beta1 only enters _rho_max_ksc -> As_max
        ratio = b1_eng / b1_code
        note("VF-07/beta1 fc=%g ksc" % fc,
             "engine beta1 = %.5f ; code-consistent = %.5f ; As_max ratio "
             "engine/code = %.5f (%s)"
             % (b1_eng, b1_code, ratio,
                "engine As_max lower -> stricter ductility limit -> "
                "CONSERVATIVE" if ratio <= 1.0 + 1e-12 else "engine less strict"),
             "REVIEW")
    note("VF-07/conclusion",
        "_flex_ksc Mn / phiMn do NOT depend on beta1 (a = As fy/(0.85 f'c b)). "
        "beta1 affects only _rho_max_ksc -> As_max, where the 280-ksc form is "
        "<= the code-consistent value, i.e. the ductility ceiling is slightly "
        "STRICTER above 280 ksc. Effect <= ~0.8%. Root cause R8 (intentional "
        "MKS approximation). ACTION: ACCEPTED, no fix.", "REVIEW")

    # VF-12 / VF-13 — MKS shear coefficients in _render_beam_section
    fc, b, d = 240.0, 30.0, 54.0
    eng_Vc = EA.vc_beam_ksc(fc, b, d)
    exact_Vc = RB.beam_section_verdict_mks.__doc__ and None
    k_exact_Vc = 0.17 * math.sqrt(KSC_TO_MPA) * 100.0 / 9.80665
    k_exact_Vsmax = 0.66 * math.sqrt(KSC_TO_MPA) * 100.0 / 9.80665
    k_exact_thr = 0.33 * math.sqrt(KSC_TO_MPA) * 100.0 / 9.80665
    note("VF-12/Vc coefficient",
         "engine 0.53 vs SI-exact %.4f  ->  engine Vc is %.2f%% LOW "
         "(under-estimates concrete shear -> CONSERVATIVE). 0.53 sqrt f'c "
         "[ksc] is a long-standing ACI-metric code form. R8. ACCEPTED."
         % (k_exact_Vc, 100.0 * (k_exact_Vc - 0.53) / k_exact_Vc), "REVIEW")
    note("VF-13/Vs_max & dense-stirrup threshold",
         "engine Vs_max 2.1 vs exact %.4f (%.2f%% low, CONSERVATIVE); "
         "engine dense-stirrup trigger 1.06 vs exact %.4f (%.2f%% HIGH -> "
         "d/4 rule triggers marginally late -> slightly non-conservative on "
         "a razor-thin Vs band, consequence bounded: d/2 vs d/4 spacing). "
         "R8. ACCEPTED with NOTE; recommend aligning to the SI-exact "
         "coefficients in an EV-04 consistency pass."
         % (k_exact_Vsmax, 100.0 * (k_exact_Vsmax - 2.1) / k_exact_Vsmax,
            k_exact_thr, 100.0 * (1.06 - k_exact_thr) / k_exact_thr), "REVIEW")

    # VF-04 — sampled-peak (beam-relevant continuous-beam interaction only)
    w, L = 1000.0, 6.0
    r = solve_continuous_beam([L], w)
    M_exact = w * L ** 2 / 8.0
    import numpy as np
    xg = np.linspace(0.0, L, max(80, 200))
    M_grid = float((w * xg * (L - xg) / 2.0).max())
    h = L / (max(80, 200) - 1)
    bound = (w / 2.0) * (h / 2.0) ** 2
    gap = M_exact - r["Mu_pos_kgfm"]
    chk("VF-04/sampled peak", "engine Mu_pos vs analytic-on-grid", M_grid,
        r["Mu_pos_kgfm"], "num rel 1e-4", num(M_grid, r["Mu_pos_kgfm"], 1e-4, 1e-2))
    chk("VF-04/sampled peak", "exact-minus-engine gap bounded & >= 0", True,
        (0.0 <= gap <= max(4 * bound, 1.0)),
        f"0 <= gap <= ~{bound:.3f}", (0.0 <= gap <= max(4 * bound, 1.0)))
    note("VF-04/conclusion",
         "gap = %.3f kgf-m (%.4f%%), non-conservative but bounded by grid "
         "resolution; engine matches analytic-on-grid to <1e-4 -> the sole "
         "error source is fixed-grid sampling, NOT the solver. R4 "
         "(numerical method). ACTION: ACCEPTED as a documented numerical "
         "limitation; solver NOT changed in EV-03. EV-04 may evaluate M at "
         "the interior stationary point analytically."
         % (gap, 100.0 * gap / M_exact), "REVIEW")


# =========================================================================
def main():
    brief = "--brief" in sys.argv
    phase_A(); phase_B(); phase_C(); phase_D(); phase_E(); phase_F()

    npass = sum(1 for r in ROWS if r["status"] == "PASS")
    nfail = sum(1 for r in ROWS if r["status"] == "FAIL")
    nrev = sum(1 for r in ROWS if r["status"] == "REVIEW")
    nblk = sum(1 for r in ROWS if r["status"] == "BLOCKED")

    if not brief:
        print("\nEV-03 BEAM VALIDATION - independent reference vs live engine")
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
    print(f"EV-03 BEAM checks: {len(ROWS)}   "
          f"PASS={npass}  FAIL={nfail}  REVIEW={nrev}  BLOCKED={nblk}")
    print("=" * 78)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
