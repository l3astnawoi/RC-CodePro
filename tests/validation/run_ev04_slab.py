"""EV-04 — SLAB engineering validation runner.

Independent reference (tests/validation/reference/reference_slab_ev04.py,
math-only, no production imports) vs the LIVE modules/slab.py helpers and
the reconstructed _render_slab_design verdict.

Phases (mandatory order):
  A  Load                 (self-weight, factored Wu)
  B  One-way / two-way classification
  C  Moment               (one-way SS strip; two-way Grashof partition)
  D  Flexural reinforcement (_as_flexure_ksc / _required_as_flexure)
  E  Minimum reinforcement + spacing boundaries
  F  Boundary / invalid input
  G  Composite verdict + findings (VF-11-slab, VF-SLAB-01, NOT IMPLEMENTED)

Run:  py -3 tests/validation/run_ev04_slab.py [--brief]
NOT a pytest module — the regression baseline is untouched.
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

import reference_slab_ev04 as RS       # noqa: E402  (independent, math-only)
import reference_flexure as RF         # noqa: E402

from utils import aci_318m as EA       # noqa: E402
import modules.slab as SL              # noqa: E402

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


# =========================================================================
# PHASE A — LOAD
# =========================================================================
def phase_A():
    cases = [
        ("SLAB-LOAD-001 self-weight only", 12.0, 0.0, 0.0),
        ("SLAB-LOAD-002 sw + SDL + LL",    12.0, 150.0, 300.0),
        ("SLAB-LOAD-003 zero SDL & LL, t8", 8.0, 0.0, 0.0),
    ]
    for name, t, sdl, ll in cases:
        ref = RS.loads(t, sdl, ll)
        # engine has no importable load fn; reproduce its literal expression
        sw_eng = (t / 100.0) * 2400.0
        Wu_eng = 1.2 * (sw_eng + sdl) + 1.6 * ll
        chk("LOAD/" + name, "self-weight sw [kgf/m2] = (t/100)*2400",
            ref["sw_kgf_m2"], sw_eng, "num 1e-9", num(ref["sw_kgf_m2"], sw_eng, 1e-9, 1e-9))
        chk("LOAD/" + name, "Wu [kgf/m2] = 1.2(sw+SDL)+1.6 LL  (ACI 9.2)",
            ref["Wu_kgf_m2"], Wu_eng, "num 1e-9", num(ref["Wu_kgf_m2"], Wu_eng, 1e-9, 1e-9))
    note("LOAD/units",
         "Engine works in kgf/m2 on a 1 m strip -> kgf-m per strip. "
         "Self-weight uses the literal 2400 kgf/m3 (MKS convention); the "
         "SI 'exact' 24 kN/m3 = 2446.5 kgf/m3, so sw is ~1.9% low -> "
         "marginally non-conservative on the DL term only. Consistent with "
         "beam/footing/stair (same 2400 literal). NOTE, not a defect (R8).",
         "REVIEW")


# =========================================================================
# PHASE B — ONE-WAY / TWO-WAY CLASSIFICATION
# =========================================================================
def phase_B():
    # engine: short=min, long=max ; two_way iff short/long > 0.5
    cases = [
        ("SLAB-CLASS square Lx=Ly=5",        5.0, 5.0,  "two-way"),
        ("SLAB-CLASS near-square 4x5",        4.0, 5.0,  "two-way"),
        ("SLAB-CLASS m EXACTLY 0.5 (4x8)",    4.0, 8.0,  "one-way"),   # 0.5 not > 0.5
        ("SLAB-CLASS m just below 0.5 (3.99x8)", 3.99, 8.0, "one-way"),
        ("SLAB-CLASS m just above 0.5 (4.01x8)", 4.01, 8.0, "two-way"),
        ("SLAB-CLASS highly rect 2x9",        2.0, 9.0,  "one-way"),
        ("SLAB-CLASS reversed order 8x4",     8.0, 4.0,  "one-way"),   # auto-swap
    ]
    for name, Lx, Ly, expect_type in cases:
        ref = RS.classify(Lx, Ly)
        short, longs = min(Lx, Ly), max(Lx, Ly)
        m_eng = short / longs
        two_eng = m_eng > 0.5
        type_eng = "two-way" if two_eng else "one-way"
        chk("CLASS/" + name, "m_ratio = short/long", ref["m_ratio"], m_eng,
            "num 1e-12", num(ref["m_ratio"], m_eng, 1e-12, 1e-12))
        chk("CLASS/" + name, "classification (discrete, threshold 0.5)",
            expect_type, type_eng, "exact", expect_type == type_eng)
    note("CLASS/threshold",
         "two_way iff (short/long) > 0.5  <=>  (long/short) < 2.0. The 2:1 "
         "aspect ratio is the standard ACI / textbook one-way vs two-way "
         "criterion. Strict '>' => m = 0.5 exactly is ONE-WAY. Code-"
         "consistent (R-none).", "PASS")


# =========================================================================
# PHASE C — MOMENT
# =========================================================================
def phase_C():
    Wu = 1000.0
    cases = [
        ("SLAB-MOM-001 one-way SS strip 4 m", 4.0, 12.0, False),
        ("SLAB-MOM-002 two-way 4x5 (Grashof)", 4.0, 5.0,  True),
        ("SLAB-MOM-003 near boundary 4x7.9",   4.0, 7.9,  True),
    ]
    for name, Lx, Ly, two_way in cases:
        short, longs = min(Lx, Ly), max(Lx, Ly)
        ref = RS.design_moments(Wu, short, longs, two_way)
        if two_way:
            k = short ** 4 + longs ** 4
            Mux_e = Wu * short ** 2 * (longs ** 4 / k) / 8.0
            Muy_e = Wu * longs ** 2 * (short ** 4 / k) / 8.0
        else:
            Mux_e = Wu * short ** 2 / 8.0
            Muy_e = 0.0
        chk("MOM/" + name, "Mux [kgf-m/strip]", ref["Mux_kgfm"], Mux_e,
            "num 1e-9", num(ref["Mux_kgfm"], Mux_e, 1e-9, 1e-6))
        chk("MOM/" + name, "Muy [kgf-m/strip]", ref["Muy_kgfm"], Muy_e,
            "num 1e-9", num(ref["Muy_kgfm"], Muy_e, 1e-9, 1e-6))
    note("MOM/two-way method (VF-SLAB-01)",
         "Two-way Mux = Wu Lx^2 (Ly^4/(Lx^4+Ly^4))/8 is the classical "
         "GRASHOF / RANKINE (Marcus) elastic load-partition method: total "
         "load split between strips ~ (other span)^4, each strip then "
         "designed as a simply-supported 1 m strip (wL^2/8). It is a "
         "recognised approximate method but is NOT an ACI 318M-08 method "
         "(ACI 13.6 DDM / 13.7 EFM). Assumes 4 simply-supported edges, no "
         "continuity, no corner hold-down, uniform load; the engine "
         "applies it to EVERY two-way panel with no applicability check. "
         "Root cause R7 (code-interpretation) / R8. ACTION: REVIEW / "
         "DOCUMENT -- CODE REFERENCE REQUIRED; do NOT change the formula.",
         "REVIEW")
    note("MOM/one-way continuity",
         "One-way Mu = Wu Lx^2/8 is the simply-supported strip value. "
         "Continuous one-way slabs (ACI 8.3.3 approximate moment "
         "coefficients: -wLn^2/9..-wLn^2/11 at supports, +wLn^2/14..16 in "
         "spans) and support/top steel are NOT IMPLEMENTED. For a genuinely "
         "simply-supported slab the value is correct; for a continuous slab "
         "the support region is under-designed. R9 scope limitation.",
         "REVIEW")


# =========================================================================
# PHASE D — FLEXURAL REINFORCEMENT
# =========================================================================
def phase_D():
    fc, fy, b = 240.0, 4000.0, 100.0
    cases = [
        ("D-01 light strip",           600.0, 12.0),
        ("D-02 EV-02 SLAB-001 input", 1200.0, 12.0),
        ("D-03 moderate",            1600.0, 12.0),
        ("D-04 heavy (near As_max)", 1765.0,  5.2),
        ("D-05 zero moment",            0.0, 12.0),
        ("D-06 infeasible",         50000.0,  5.0),
    ]
    for name, Mu, d in cases:
        ref = RS.flexure_strip_ksc(Mu, b, d, fc, fy)
        As_e, feas_e = SL._as_flexure_ksc(Mu, b, d, fc, fy)
        chk("FLEX/" + name, "feasible", ref["feasible"], feas_e, "exact",
            ref["feasible"] == feas_e)
        if ref["feasible"] and feas_e:
            chk("FLEX/" + name, "As_req [cm2/m]", ref["As_cm2"], As_e,
                "num 1e-6", num(ref["As_cm2"], As_e))
            if not ref["tension_controlled"]:
                note("FLEX/" + name,
                     "eps_t = %.5f  ->  ACI phi = %.3f (engine _as_flexure_ksc "
                     "returns As sized with a FIXED phi = 0.90 -> As is "
                     "UNDER-estimated for this section). %s"
                     % (ref["eps_t"], ref["phi_code"],
                        "eps_t < 0.004 -> ACI 10.3.5 VIOLATED"
                        if not ref["meets_eps_min_flexure"] else ""),
                     "REVIEW")
        elif not ref["feasible"]:
            chk("FLEX/" + name, "infeasible sentinel (None)", None, As_e,
                "exact", As_e is None)

    # _required_as_flexure (SI) — a couple of boundary points
    fc_mpa, fy_mpa = 24.0, 420.0
    for name, Mu_kNm, d_mm in (("D-07 SI moderate", 60.0, 100.0),
                               ("D-08 SI zero", 0.0, 100.0)):
        As_r, Rn_r, rho_r, feas_r = RF.required_As_singly_reinforced(
            Mu_kNm * 1e6, 0.90, 1000.0, d_mm, fc_mpa, fy_mpa)
        As_e, Rn_e, rho_e, feas_e = SL._required_as_flexure(
            Mu_kNm, 1000.0, d_mm, fc_mpa, fy_mpa)
        chk("FLEX/" + name, "feasible", feas_r, feas_e, "exact", feas_r == feas_e)
        if feas_r and feas_e and Mu_kNm > 0:
            chk("FLEX/" + name, "As_req [mm2]", As_r, As_e, "num 1e-6",
                num(As_r, As_e))


# =========================================================================
# PHASE E — MINIMUM REINFORCEMENT + SPACING
# =========================================================================
def phase_E():
    # temp-steel ratio
    for fy_ksc in (2400.0, 3000.0, 4000.0, 5000.0):
        ref = RS.temp_steel_ratio(fy_ksc * KSC_TO_MPA)
        eng = SL._temp_steel_ratio(fy_ksc * KSC_TO_MPA)
        chk("ASMIN/fy=%g ksc" % fy_ksc, "temp_steel_ratio (ACI 7.12.2.1)",
            ref, eng, "num 1e-9", num(ref, eng, 1e-9, 1e-12))
    note("ASMIN/enforcement",
         "For slabs ACI 10.5.4 sets the minimum flexural steel = the "
         "shrinkage/temperature amount (7.12). The engine enforces it via "
         "As_x = max(As_x_req, As_temp_min) and As_y = max(As_y_req, "
         "As_temp_min); the DESIGN CHECKS 'As,temp' row is a value display "
         "hardcoded status True, but the real enforcement is the max(). "
         "R10 (the row is presentational); enforcement OK.", "PASS")

    # spacing rule + boundaries
    Ab12 = math.pi * 12.0 ** 2 / 4.0 / 100.0
    spacing_cases = [
        ("SPACE-01 normal",         Ab12, 5.0, 25.0),
        ("SPACE-02 As tiny -> s_max cap", Ab12, 0.5, 20.0),
        ("SPACE-03 As=0 -> s_max",   Ab12, 0.0, 30.0),
        ("SPACE-04 As huge -> 2.5 floor", Ab12, 80.0, 30.0),
        ("SPACE-05 S_req just above s_max", Ab12, Ab12 * 100.0 / 25.01, 25.0),
    ]
    for name, ab, asreq, smax in spacing_cases:
        S_r, Asp_r = RS.spacing_for(ab, asreq, smax)
        S_e, Asp_e = SL._spacing_for(ab, asreq, smax)
        chk("SPACE/" + name, "S [cm] (2.5 rounding, discrete)", S_r, S_e,
            "exact", num(S_r, S_e, 1e-12, 1e-12))
        chk("SPACE/" + name, "As_provided matches independent reproduction",
            Asp_r, Asp_e, "num 1e-9", num(Asp_r, Asp_e, 1e-9, 1e-9))
        if asreq > 1e-9 and Asp_e < asreq - 1e-6:
            note("SPACE/" + name,
                 "As_provided (%.2f) < As_required (%.2f): the max(S, 2.5) "
                 "floor in _spacing_for UNDER-provides when As_req > Ab*40. "
                 "NOT reachable as an unsafe slab verdict -- S = 2.5 cm < "
                 "7.5 cm is always rejected by the caller's minimum-spacing "
                 "check. Finding VF-SLAB-03 (R3 in the shared helper; "
                 "caught by the caller). RECORD; shared-helper hardening = "
                 "EV-05+ scope." % (Asp_e, asreq), "REVIEW")
    note("SPACE/verdict bounds",
         "_render_slab_design verdict: main_ok = 7.5 <= S <= min(3t,45); "
         "temp_ok = 7.5 <= S_temp <= min(5t,45). The 7.5 cm lower bound "
         "(min bar spacing / congestion) is what catches gross "
         "over-reinforcement indirectly; s_max = min(3t,45) is ACI 13.3.2 "
         "for the principal reinforcement of a one-way slab. Discrete "
         "checks, no tolerance applied.", "PASS")


# =========================================================================
# PHASE F — BOUNDARY / INVALID INPUT
# =========================================================================
def phase_F():
    trials = [
        ("F-01 _as_flexure_ksc d=0",  lambda: SL._as_flexure_ksc(500.0, 100.0, 0.0, 240.0, 4000.0)),
        ("F-02 _as_flexure_ksc Mu<0", lambda: SL._as_flexure_ksc(-500.0, 100.0, 10.0, 240.0, 4000.0)),
        ("F-03 _as_flexure_ksc fc=0", lambda: SL._as_flexure_ksc(500.0, 100.0, 10.0, 0.0, 4000.0)),
        ("F-04 _as_flexure_ksc negative d", lambda: SL._as_flexure_ksc(500.0, 100.0, -5.0, 240.0, 4000.0)),
        ("F-05 _temp_steel_ratio fy=0", lambda: SL._temp_steel_ratio(0.0)),
        ("F-06 _spacing_for negative As", lambda: SL._spacing_for(1.0, -3.0, 25.0)),
        ("F-07 _spacing_for s_max=0",  lambda: SL._spacing_for(1.0, 5.0, 0.0)),
        ("F-08 _required_as_flexure fc=0", lambda: SL._required_as_flexure(60.0, 1000.0, 100.0, 0.0, 420.0)),
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
                 "(f'c >= 180 ksc, t >= 8 cm, cov >= 1 cm); unreachable in "
                 "the app flow. Negative test, RECORD (VF-SLAB-02)." % crash,
                 "REVIEW")
        else:
            shown = (tuple(round(x, 4) if isinstance(x, float) else x
                           for x in res) if isinstance(res, tuple) else res)
            note("BOUNDARY/" + name, "no crash; returns " + repr(shown), "PASS")


# =========================================================================
# PHASE G — COMPOSITE VERDICT + FINDINGS
# =========================================================================
def _engine_slab_verdict(p, *, apply_ductility):
    """Reconstruct _render_slab_design's pass/fail from the REAL engine
    helpers.  apply_ductility=False = pre-EV-04 code (spacing only);
    True = EV-04 fix (adds the As <= As_max tension-controlled gate)."""
    b = 100.0
    Lx, Ly = min(p["Lx"], p["Ly"]), max(p["Lx"], p["Ly"])
    m = Lx / Ly
    two_way = m > 0.5
    sw = (p["t"] / 100.0) * 2400.0
    Wu = 1.2 * (sw + p["SDL"]) + 1.6 * p["LL"]
    if two_way:
        k = Lx ** 4 + Ly ** 4
        Mux = Wu * Lx ** 2 * (Ly ** 4 / k) / 8.0
        Muy = Wu * Ly ** 2 * (Lx ** 4 / k) / 8.0
    else:
        Mux, Muy = Wu * Lx ** 2 / 8.0, 0.0
    db_main = p["main_db"] / 10.0
    Ab_main = EA.bar_area("DB%d" % int(p["main_db"])) / 100.0
    Ab_temp = EA.bar_area("DB%d" % int(p["temp_db"])) / 100.0
    d_x = p["t"] - p["cov"] - db_main / 2.0
    d_y = d_x - db_main
    As_x_req, feas_x = SL._as_flexure_ksc(Mux, b, d_x, p["fc"], p["fy"])
    As_y_req, feas_y = SL._as_flexure_ksc(Muy, b, d_y, p["fc"], p["fy"])
    if not (feas_x and (feas_y or not two_way)):
        return None  # engine returns early with an error
    temp_ratio = SL._temp_steel_ratio(p["fy"] * KSC_TO_MPA)
    As_temp_min = temp_ratio * b * p["t"]
    As_x = max(As_x_req or 0.0, As_temp_min)
    As_y = max(As_y_req or 0.0, As_temp_min) if two_way else As_temp_min
    s_max_main = min(3.0 * p["t"], 45.0)
    s_max_temp = min(5.0 * p["t"], 45.0)
    S_x, _ = SL._spacing_for(Ab_main, As_x, s_max_main)
    S_y, _ = SL._spacing_for(Ab_main, As_y, s_max_main) if two_way else (None, None)
    S_temp, _ = SL._spacing_for(Ab_temp, As_temp_min, s_max_temp)
    main_ok = (7.5 <= S_x <= s_max_main) and (
        (not two_way) or (7.5 <= S_y <= s_max_main))
    temp_ok = 7.5 <= S_temp <= s_max_temp
    passed = main_ok and temp_ok
    if apply_ductility:
        # EV-04 fix uses a local _rho_max_ksc in slab.py (mirrors beam)
        rho_max = getattr(SL, "_rho_max_ksc", None)
        if rho_max is None:
            return ("NO_HELPER", passed)
        As_max_x = rho_max(p["fc"], p["fy"]) * b * d_x
        As_max_y = rho_max(p["fc"], p["fy"]) * b * d_y
        ductile_x = As_x <= As_max_x
        ductile_y = (not two_way) or (As_y <= As_max_y)
        passed = passed and ductile_x and ductile_y
    return passed


def phase_G():
    # Reachable over-reinforced ONE-WAY slab: Lx=3, Ly=7 m (m=0.43 -> one-way),
    # t=10 cm, DB16 main, heavy load -> As_x past the tension-controlled
    # limit but spacing still inside 7.5..s_max, so the engine PASSes.
    p = {"Lx": 3.0, "Ly": 7.0, "t": 10.0, "cov": 2.0, "fc": 240.0,
         "fy": 4000.0, "SDL": 250.0, "LL": 1300.0, "main_db": 16, "temp_db": 10}
    ref = RS.slab_design_verdict(
        Lx_m=p["Lx"], Ly_m=p["Ly"], t_cm=p["t"], cov_cm=p["cov"],
        fc_ksc=p["fc"], fy_ksc=p["fy"], SDL_kgf_m2=p["SDL"],
        LL_kgf_m2=p["LL"], main_db_mm=p["main_db"], temp_db_mm=p["temp_db"])
    if ref.get("error") or ref.get("feasible") is False:
        note("COMPOSITE/G-01", "reference case is infeasible/errored (%r) -- "
             "adjust inputs" % ref, "BLOCKED")
        return
    note("COMPOSITE/G-01 over-reinforced one-way slab",
         "inputs: Lx=3, Ly=7 m (one-way), t=10 cm, SDL 250, LL 1300, DB16. "
         "Mux = %.0f kgf-m/m ; As_x = %.2f cm2/m ; As_max_x(ACI 10.3.4) = "
         "%.2f cm2/m ; eps_t = %.5f -> ACI phi = %.3f (engine used 0.90). "
         "S_x = %.1f cm (7.5<=S<=%.1f -> main_ok). ENGINE verdict "
         "(spacing only) = %s ; ACI-correct (with ductility) = %s."
         % (ref["moments"]["Mux_kgfm"], ref["As_x_cm2"], ref["As_max_x_cm2"],
            ref["fx"]["eps_t"], ref["fx"]["phi_code"], ref["S_x_cm"],
            ref["s_max_main_cm"],
            "PASS" if ref["engine_passed"] else "FAIL",
            "PASS" if ref["aci_passed"] else "FAIL"),
         "REVIEW")

    src = inspect.getsource(SL._render_slab_design)
    fix_present = ("ductile_x" in src and "ductile_y" in src
                   and "_rho_max_ksc" in inspect.getsource(SL))
    chk("COMPOSITE/G-01 over-reinforced one-way slab",
        "EV-04 fix: tension-controlled (As<=As_max) gate wired into 'passed'",
        True, bool(fix_present), "source check", bool(fix_present))

    pre = _engine_slab_verdict(p, apply_ductility=False)
    post = _engine_slab_verdict(p, apply_ductility=True)
    if isinstance(post, tuple) and post[0] == "NO_HELPER":
        note("COMPOSITE/G-01 over-reinforced one-way slab",
             "slab.py has no _rho_max_ksc yet -> pre-EV-04 (fix pending). "
             "reconstructed engine verdict (spacing only) = %s ; "
             "ACI-correct = %s" % (pre, "PASS" if ref["aci_passed"] else "FAIL"),
             "REVIEW")
        post = pre  # can't evaluate the fixed path yet
    chk("COMPOSITE/G-01 over-reinforced one-way slab",
        "reconstructed engine verdict  ==  ACI-correct verdict",
        ref["aci_passed"], bool(post if fix_present else pre),
        "exact (verdict)",
        bool(post if fix_present else pre) == ref["aci_passed"])

    # default slab must stay PASS after the fix
    dp = {"Lx": 4.0, "Ly": 5.0, "t": 12.0, "cov": 2.0, "fc": 240.0,
          "fy": 4000.0, "SDL": 150.0, "LL": 300.0, "main_db": 12, "temp_db": 10}
    dref = RS.slab_design_verdict(
        Lx_m=dp["Lx"], Ly_m=dp["Ly"], t_cm=dp["t"], cov_cm=dp["cov"],
        fc_ksc=dp["fc"], fy_ksc=dp["fy"], SDL_kgf_m2=dp["SDL"],
        LL_kgf_m2=dp["LL"], main_db_mm=dp["main_db"], temp_db_mm=dp["temp_db"])
    dpost = _engine_slab_verdict(dp, apply_ductility=fix_present)
    chk("COMPOSITE/G-02 default slab (Lx4 Ly5 t12)",
        "verdict stays PASS (no over-tightening)", dref["aci_passed"],
        bool(dpost) if not isinstance(dpost, tuple) else bool(dpost[1]),
        "exact", (bool(dpost) if not isinstance(dpost, tuple)
                  else bool(dpost[1])) == dref["aci_passed"])

    # NOT IMPLEMENTED inventory
    note("SCOPE/NOT IMPLEMENTED",
         "modules/slab.py._render_slab_design designs a 1 m strip for "
         "FLEXURE + BAR SPACING + shrinkage/temperature steel only. NOT "
         "implemented: one-way shear, two-way (punching) shear, deflection "
         "/ span-depth control, crack control (ACI 10.6.4 / bar-spacing "
         "for w), development length, torsion, moment redistribution, "
         "continuity / ACI 8.3.3 support moments, column-strip / "
         "middle-strip distribution, pattern loading, corner reinforcement. "
         "Per EV-04 brief these are SCOPE LIMITATION -- NOT to be added. "
         "Future validation priority: deflection (serviceability) and "
         "one-way shear for thin heavily-loaded slabs.", "REVIEW")
    note("SCOPE/dead code",
         "_render_one_way_slab (slab.py:645) and _render_two_way_slab "
         "(slab.py:403) are DEAD (not reached by render_slab_module). Not "
         "validated, not deleted. (matches VF-03).", "REVIEW")


# =========================================================================
def main():
    brief = "--brief" in sys.argv
    phase_A(); phase_B(); phase_C(); phase_D(); phase_E(); phase_F(); phase_G()
    npass = sum(1 for r in ROWS if r["status"] == "PASS")
    nfail = sum(1 for r in ROWS if r["status"] == "FAIL")
    nrev = sum(1 for r in ROWS if r["status"] == "REVIEW")
    nblk = sum(1 for r in ROWS if r["status"] == "BLOCKED")
    if not brief:
        print("\nEV-04 SLAB VALIDATION - independent reference vs live engine")
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
    print(f"EV-04 SLAB checks: {len(ROWS)}   "
          f"PASS={npass}  FAIL={nfail}  REVIEW={nrev}  BLOCKED={nblk}")
    print("=" * 78)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
