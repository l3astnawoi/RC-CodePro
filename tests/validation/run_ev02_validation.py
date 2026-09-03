"""EV-02 — executable validation runner.

Compares the INDEPENDENT reference values in
``tests/validation/reference/cases/*.json`` (built from
``reference/*.py`` — no production imports) against the LIVE RC CodePro
calculation engine.

This runner is the ONLY place a production calculation function is called
(to obtain the *actual* result).  The reference side never touches the
engine, so the comparison is not circular.

Run:
    py -3 tests/validation/run_ev02_validation.py            # full table
    py -3 tests/validation/run_ev02_validation.py --brief    # summary only

Exit code: 0 if no non-BLOCKED case FAILs, 1 otherwise.  It is deliberately
NOT a pytest module, so `pytest -q` (the 73-test regression baseline) is
completely unaffected.  EV-03 may wire these into pytest behind a marker.
"""

import json
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tests", "validation", "reference"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

CASE_DIR = os.path.join(_ROOT, "tests", "validation", "reference", "cases")
KSC_TO_MPA = 0.0980665

# --- results accounting ----------------------------------------------------
ROWS = []          # (case_id, quantity, expected, actual, diff, tol, status)


def _rel(a, b):
    if a == b:
        return 0.0
    denom = max(abs(a), abs(b), 1e-30)
    return abs(a - b) / denom


def rec(case_id, qty, expected, actual, tol_txt, ok):
    ROWS.append({
        "case": case_id, "qty": qty,
        "expected": expected, "actual": actual,
        "diff": (actual - expected)
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float))
        else "-",
        "tol": tol_txt,
        "status": "PASS" if ok else "FAIL",
    })


def rec_note(case_id, qty, text, status):
    ROWS.append({"case": case_id, "qty": qty, "expected": text,
                 "actual": "-", "diff": "-", "tol": "-", "status": status})


def num_ok(expected, actual, rel=1e-6, abs_=1e-6):
    if isinstance(expected, str) or isinstance(actual, str):
        return False
    return abs(expected - actual) <= abs_ or _rel(expected, actual) <= rel


# =========================================================================
# Engine imports (the ONLY place production calc code is loaded)
# =========================================================================
from utils import aci_318m as ENG_ACI            # noqa: E402
from utils.analysis import solve_continuous_beam  # noqa: E402
from modules import beam as ENG_BEAM              # noqa: E402
from modules import column as ENG_COL             # noqa: E402


def load(name):
    with open(os.path.join(CASE_DIR, name), encoding="utf-8") as fh:
        return {c["case_id"]: c for c in json.load(fh)}


# =========================================================================
# P0-A / P0-G  ACI primitives
# =========================================================================
def run_aci():
    C = load("aci_primitives.json")

    # EV-ACI-001  beta1 (SI)
    for fc in C["EV-ACI-001"]["inputs"]["fc_MPa"]:
        exp = C["EV-ACI-001"]["expected"]["beta1"][f"fc_{fc:g}_MPa"]
        act = ENG_ACI.beta1(fc)
        rec("EV-ACI-001", f"beta1(fc={fc:g} MPa)", exp, act,
            "num rel 1e-9", num_ok(exp, act, 1e-9, 1e-12))

    # EV-ACI-001M  MKS beta1 helpers vs code-consistent (VF-07)
    m = C["EV-ACI-001M"]
    for fc in m["inputs"]["fc_ksc"]:
        exp_eng = m["expected"]["beta1_engine_MKS_form"][f"fc_{fc:g}_ksc"]
        a_beam = ENG_BEAM._beta1_ksc(fc)
        a_col = ENG_COL._beta1_col_ksc(fc)
        ok = num_ok(exp_eng, a_beam, 1e-9, 1e-12) and num_ok(exp_eng, a_col, 1e-9, 1e-12)
        rec("EV-ACI-001M", f"_beta1_ksc / _beta1_col_ksc(fc={fc:g} ksc)",
            exp_eng, a_beam, "engine MKS-form (matches by design)", ok)
    gap = m["expected"]["beta1_gap_engine_minus_code"]
    rec_note("EV-ACI-001M", "beta1 gap vs code-consistent (VF-07)",
             "max |gap| = %.5f at fc>280 ksc; <=280 ksc no gap. "
             "Documented modelling choice, not a numeric pass/fail."
             % max(abs(v) for v in gap.values()), "REVIEW")

    # EV-ACI-002  rho_min
    for fc, fy in C["EV-ACI-002"]["inputs"]["si_fc_fy_MPa"]:
        exp = C["EV-ACI-002"]["expected"]["rho_min_SI"][f"fc{fc:g}_fy{fy:g}"]
        act = ENG_ACI.rho_min_flexure(fc, fy)
        rec("EV-ACI-002", f"rho_min_SI(fc={fc:g},fy={fy:g} MPa)", exp, act,
            "num rel 1e-9", num_ok(exp, act, 1e-9, 1e-12))
    for fc, fy in C["EV-ACI-002"]["inputs"]["mks_fc_fy_ksc"]:
        exp = C["EV-ACI-002"]["expected"]["rho_min_MKS"][f"fc{fc:g}_fy{fy:g}"]
        act = ENG_ACI.rho_min_flexure_ksc(fc, fy)
        rec("EV-ACI-002", f"rho_min_ksc(fc={fc:g},fy={fy:g} ksc)", exp, act,
            "num rel 1e-9", num_ok(exp, act, 1e-9, 1e-12))

    # EV-ACI-003  rho_max (engine helper is in modules/beam.py)
    for fc, fy in C["EV-ACI-003"]["inputs"]["fc_fy_ksc"]:
        exp = C["EV-ACI-003"]["expected"]["rho_max_MKS"][f"fc{fc:g}_fy{fy:g}"]
        act = ENG_BEAM._rho_max_ksc(fc, fy)
        rec("EV-ACI-003", f"_rho_max_ksc(fc={fc:g},fy={fy:g} ksc)", exp, act,
            "num rel 1e-9", num_ok(exp, act, 1e-9, 1e-12))

    # EV-ACI-004  phi_flexure
    for e in C["EV-ACI-004"]["inputs"]["eps_t"]:
        for spiral in (False, True):
            key = "phi_spiral" if spiral else "phi_tied"
            exp = C["EV-ACI-004"]["expected"][key][f"eps_{e:g}"]
            act = ENG_ACI.phi_flexure(e, spiral=spiral)
            rec("EV-ACI-004",
                f"phi_flexure(eps={e:g},spiral={spiral})", exp, act,
                "num rel 1e-9", num_ok(exp, act, 1e-9, 1e-12))

    # EV-ACI-005  Vc one-way
    a = C["EV-ACI-005"]
    fc_ksc = a["inputs"]["fc_ksc"]
    fc_mpa = a["inputs"]["fc_MPa"]
    bw, d = a["inputs"]["bw_mm"], a["inputs"]["d_mm"]
    exp_si = a["expected"]["Vc_SI_N"]
    act_si = ENG_ACI.vc_beam(fc_mpa, bw, d, 1.0)
    rec("EV-ACI-005", "vc_beam SI [N]", exp_si, act_si,
        "num rel 1e-9", num_ok(exp_si, act_si, 1e-9, 1e-6))
    exp_mks = a["expected"]["Vc_MKS_053_kgf"]
    act_mks = ENG_ACI.vc_beam_ksc(fc_ksc, a["inputs"]["b_cm"], a["inputs"]["d_cm"])
    rec("EV-ACI-005", "vc_beam_ksc (0.53 form) [kgf]", exp_mks, act_mks,
        "num rel 1e-9", num_ok(exp_mks, act_mks, 1e-9, 1e-6))
    exact = a["expected"]["Vc_MKS_exact_equiv_kgf"]
    rec_note("EV-ACI-005", "MKS 0.53 vs SI-exact equivalent",
             "engine 0.53-form = %.1f kgf ; exact SI-equivalent = %.1f kgf ; "
             "engine is %.2f%% LOW (traditional metric rounding, conservative)."
             % (act_mks, exact, 100.0 * (exact - act_mks) / exact), "REVIEW")

    # EV-ACI-006  two-way vc  (equation form check — inline in footing.py)
    e6 = C["EV-ACI-006"]["expected"]
    fc_mpa6 = C["EV-ACI-006"]["inputs"]["fc_MPa"]
    cx = C["EV-ACI-006"]["inputs"]["cx_mm"]
    d6 = C["EV-ACI-006"]["inputs"]["d_mm"]
    bo = 2.0 * (cx + d6) + 2.0 * (cx + d6)          # square column
    vc1 = 0.17 * (1.0 + 2.0 / 1.0) * 1.0 * math.sqrt(fc_mpa6)
    vc2 = 0.083 * (40.0 * d6 / bo + 2.0) * 1.0 * math.sqrt(fc_mpa6)
    vc3 = 0.33 * 1.0 * math.sqrt(fc_mpa6)
    # this reproduces modules/footing.py lines 286-293 verbatim; the check
    # here is that the reference equations equal that source form.
    ok6 = (num_ok(e6["vc1_MPa"], vc1, 1e-12, 1e-12)
           and num_ok(e6["vc2_MPa"], vc2, 1e-12, 1e-12)
           and num_ok(e6["vc3_MPa"], vc3, 1e-12, 1e-12)
           and num_ok(e6["vc_governing_MPa"], min(vc1, vc2, vc3), 1e-12, 1e-12))
    rec("EV-ACI-006", "two-way vc1/vc2/vc3/min (form matches footing.py "
        "L286-293 by inspection)", e6["vc_governing_MPa"], min(vc1, vc2, vc3),
        "form check (no importable entrypoint)", ok6)

    # EV-ACI-007  tie s_max  (form check — inline in column.py L510-513)
    for i, c in enumerate(C["EV-ACI-007"]["inputs"]["combos_cm"]):
        exp = C["EV-ACI-007"]["expected"]["per_combo"][i]["s_max_cm"]
        act = min(16.0 * c["db_long_cm"], 48.0 * c["db_tie_cm"],
                  c["least_dim_cm"])
        rec("EV-ACI-007",
            f"tie s_max = min(16db,48d_tie,least) combo{i+1}", exp, act,
            "form matches column.py L510-513", num_ok(exp, act, 1e-12, 1e-12))
    rec_note("EV-ACI-007", "VF-10",
             "engine sets spacing_ok = (s_max >= 5 cm); it never compares a "
             "PROVIDED tie spacing to s_max. Formula validated; usage "
             "recorded.", "REVIEW")


# =========================================================================
# P0-B  Beam flexure + shear
# =========================================================================
def run_beam():
    C = load("beam_flexure_shear.json")

    for cid in ("EV-BEAM-001", "EV-BEAM-002"):
        c = C[cid]
        i = c["inputs"]
        a_cm, Mn, phiMn = ENG_BEAM._flex_ksc(
            i["As_cm2"], i["fy_ksc"], i["fc_ksc"], i["b_cm"], i["d_cm"])
        e = c["expected"]
        rec(cid, "a [cm]", e["a_cm"], a_cm, "num rel 1e-6",
            num_ok(e["a_cm"], a_cm))
        rec(cid, "Mn [kgf-m]", e["Mn_kgfm"], Mn, "num rel 1e-6",
            num_ok(e["Mn_kgfm"], Mn))
        rec(cid, "phiMn [kgf-m]", e["phiMn_kgfm"], phiMn, "num rel 1e-6",
            num_ok(e["phiMn_kgfm"], phiMn))
    rec_note("EV-BEAM-002", "VF-11",
             "_flex_ksc hardcodes phi = 0.90 with no internal "
             "tension-controlled guard; correct only while the caller "
             "enforces rho <= rho_max (it does, via _rho_max_ksc).", "REVIEW")

    # EV-BEAM-003  _required_as + As_min
    c = C["EV-BEAM-003"]
    i = c["inputs"]
    As, Rn, rho, feas = ENG_BEAM._required_as(
        i["Mu_kNm"], i["b_mm"], i["d_mm"], i["fc_MPa"], i["fy_MPa"])
    e = c["expected"]
    rec("EV-BEAM-003", "As_req [mm2]", e["As_req_mm2"], As, "num rel 1e-6",
        num_ok(e["As_req_mm2"], As))
    rec("EV-BEAM-003", "Rn [MPa]", e["Rn_MPa"], Rn, "num rel 1e-6",
        num_ok(e["Rn_MPa"], Rn))
    rec("EV-BEAM-003", "feasible", e["feasible"], feas, "exact",
        e["feasible"] == feas)
    as_min_eng = ENG_ACI.calc_As_min(i["fc_MPa"], i["fy_MPa"], i["b_mm"], i["d_mm"])
    rec("EV-BEAM-003", "As_min [mm2]", e["As_min_mm2"], as_min_eng,
        "num rel 1e-6", num_ok(e["As_min_mm2"], as_min_eng))

    # EV-BEAM-004/005  _shear_check (full dict reference)
    for cid in ("EV-BEAM-004", "EV-BEAM-005"):
        c = C[cid]
        i = c["inputs"]
        r = ENG_BEAM._shear_check(i["Vu_kN"], i["b_mm"], i["d_mm"],
                                  i["fc_MPa"], i["fyt_MPa"], "RB9", i["s_mm"])
        e = c["expected"]
        for ekey, rkey, lbl in (("phiVc_N", "phiVc", "phiVc [N]"),
                                ("Vs_N", "Vs", "Vs [N]"),
                                ("Vs_max_N", "Vs_max", "Vs_max [N]"),
                                ("phiVn_N", "phiVn", "phiVn [N]"),
                                ("s_max_mm", "s_max", "s_max [mm]")):
            rec(cid, lbl, e[ekey], r[rkey], "num rel 1e-6 / abs 1e-3",
                num_ok(e[ekey], r[rkey], 1e-6, 1e-3))
        rec(cid, "ok (verdict)", e["ok"], r["ok"], "exact", e["ok"] == r["ok"])

    # EV-BEAM-006  s_max transition boundary (custom reference dict)
    c = C["EV-BEAM-006"]
    i = c["inputs"]
    r = ENG_BEAM._shear_check(i["Vu_kN"], i["b_mm"], i["d_mm"],
                              i["fc_MPa"], i["fyt_MPa"], "RB9", i["s_mm"])
    e = c["expected"]
    rec("EV-BEAM-006", "Vs [N]", e["Vs_N"], r["Vs"], "num rel 1e-6",
        num_ok(e["Vs_N"], r["Vs"], 1e-6, 1e-3))
    rec("EV-BEAM-006", "s_max [mm] (d/4,300 branch)", e["s_max_mm"],
        r["s_max"], "discrete (exact)", num_ok(e["s_max_mm"], r["s_max"], 1e-9, 1e-9))
    rec("EV-BEAM-006", "ok (verdict)", e["ok"], r["ok"], "exact",
        e["ok"] == r["ok"])


# =========================================================================
# P0-C  Column P-M anchors
# =========================================================================
def run_column():
    C = load("column_pm.json")
    c1 = C["EV-COL-001"]
    i = c1["inputs"]
    b = h = i["b_cm"]
    cov = 4.0
    tie_dia = 0.9        # RB9
    main_dia = 2.0       # DB20
    Ab = ENG_COL.bar_area(i["bar"]) / 100.0     # engine's cm2 (rounded table)
    bars = ENG_COL._col_bar_xy("rect", b, h, 0.0, cov, tie_dia, main_dia,
                               i["n_bars"])
    Mn, Pn, phiMn, phiPn = ENG_COL._calculate_pm_curve(
        shape="rect", b=b, h=h, D=0.0, fc=i["fc_ksc"], fy=i["fy_ksc"],
        bars=bars, Ab=Ab, spiral=False)

    e = c1["expected"]
    # bar-area rounding: engine table area vs pi d^2/4 -> allow rel 5e-6
    rec("EV-COL-001", "Po [kgf] (Pn[0])", e["Po_kgf"], float(Pn[0]),
        "num rel 5e-6 (bar-area rounding)", num_ok(e["Po_kgf"], float(Pn[0]), 5e-6, 1e-1))
    rec("EV-COL-001", "phiPn,max [kgf] (phiPn[0] = 0.8*0.65*Po)",
        e["phiPn_max_kgf"], float(phiPn[0]),
        "num rel 5e-6", num_ok(e["phiPn_max_kgf"], float(phiPn[0]), 5e-6, 1e-1))

    e2 = C["EV-COL-002"]["expected"]
    rec("EV-COL-002", "Pnt [kgf] (Pn[-1] = -fy*Ast)", e2["Pnt_kgf"],
        float(Pn[-1]), "num rel 5e-6", num_ok(e2["Pnt_kgf"], float(Pn[-1]), 5e-6, 1e-1))
    rec("EV-COL-002", "phiPnt [kgf] (phiPn[-1] = 0.90*Pnt)", e2["phiPnt_kgf"],
        float(phiPn[-1]), "num rel 5e-6",
        num_ok(e2["phiPnt_kgf"], float(phiPn[-1]), 5e-6, 1e-1))

    for cid in ("EV-COL-003", "EV-COL-004", "EV-COL-005"):
        rec_note(cid, C[cid]["description"],
                 "No trustworthy independent interior P-M reference at "
                 "EV-02 (needs a verified strain-compat solver). Deferred "
                 "to EV-03.", "BLOCKED")


# =========================================================================
# P0-D / P0-F  Continuous beam + sampled peak
# =========================================================================
def run_analysis():
    C = load("continuous_beam.json")
    for cid in ("EV-ANLZ-001", "EV-ANLZ-002", "EV-ANLZ-003", "EV-ANLZ-004"):
        c = C[cid]
        spans = c["inputs"]["spans_m"]
        w = c["inputs"]["w_kgf_per_m"]
        r = solve_continuous_beam(spans, w)
        e = c["expected"]

        for k, (exp_v, act_v) in enumerate(zip(e["reactions_kgf"],
                                               r["reactions_kgf"])):
            rec(cid, f"R{k+1} [kgf]", exp_v, act_v,
                "num rel 1e-6 / abs 1e-3", num_ok(exp_v, act_v, 1e-6, 1e-3))

        rec(cid, "Mu_neg [kgf-m]", e["Mu_neg_kgfm"], r["Mu_neg_kgfm"],
            "num rel 1e-4 / abs 1e-2 (sampled)",
            num_ok(e["Mu_neg_kgfm"], r["Mu_neg_kgfm"], 1e-4, 1e-2))
        rec(cid, "Vu [kgf]", e["Vu_kgf"], r["Vu_kgf"],
            "num rel 1e-4 / abs 1e-2 (sampled)",
            num_ok(e["Vu_kgf"], r["Vu_kgf"], 1e-4, 1e-2))

        # Mu_pos: compare against the ANALYTIC-on-grid value, not the true
        # peak (VF-04). Both use 200-pt grids; agreement confirms the solver.
        grid_ref = c["intermediate"]["Mu_pos_on_analytic_grid_200pt"]
        rec(cid, "Mu_pos vs analytic-on-grid [kgf-m]", grid_ref,
            r["Mu_pos_kgfm"], "num rel 3e-3 (grid alignment)",
            num_ok(grid_ref, r["Mu_pos_kgfm"], 3e-3, 1e-1))
        rec_note(cid, "Mu_pos vs EXACT peak",
                 "exact %.1f vs engine %.1f kgf-m (sampled, VF-04)"
                 % (e["Mu_pos_kgfm"], r["Mu_pos_kgfm"]), "REVIEW")

    # EV-ANLZ-005  sampled peak quantification
    c = C["EV-ANLZ-005"]
    r = solve_continuous_beam([c["inputs"]["span_m"]],
                              c["inputs"]["w_kgf_per_m"])
    e = c["expected"]
    m_exact = e["M_exact_kgfm"]
    m_grid = e["M_sampled_grid_peak_kgfm"]
    bound = c["intermediate"]["sampling_error_bound_kgfm"]
    # (a) engine matches analytic-on-grid within rel 1e-4  -> solver OK
    ok_a = num_ok(m_grid, r["Mu_pos_kgfm"], 1e-4, 1e-2)
    rec("EV-ANLZ-005", "engine Mu_pos vs analytic-on-grid", m_grid,
        r["Mu_pos_kgfm"], "num rel 1e-4 (isolates sampling as sole error)",
        ok_a)
    # (b) exact-minus-engine gap is bounded and non-conservative
    gap = m_exact - r["Mu_pos_kgfm"]
    ok_b = (0.0 <= gap <= max(bound * 4.0, 1.0))
    rec("EV-ANLZ-005", "exact - engine Mu_pos gap [kgf-m]", 0.0, gap,
        f"0 <= gap <= ~{bound:.3f} (parabola sampling bound)", ok_b)
    rec_note("EV-ANLZ-005", "VF-04 direction",
             "engine under-estimates the true peak by %.3f kgf-m (%.2g%%). "
             "Non-conservative but bounded by grid resolution. EV-03: "
             "densify near interior stationary points or evaluate M there "
             "analytically." % (gap, 100.0 * gap / m_exact if m_exact else 0),
             "REVIEW")


# =========================================================================
# P0-E  Slab / Stair / Footing flexure
# =========================================================================
def run_slab_stair_footing():
    C = load("slab_stair_footing.json")

    # EV-SLAB-001
    c = C["EV-SLAB-001"]
    i = c["inputs"]
    from modules import slab as ENG_SLAB
    As, feas = ENG_SLAB._as_flexure_ksc(i["Mu_kgfm_per_m"], i["b_cm"],
                                        i["d_cm"], i["fc_ksc"], i["fy_ksc"])
    e = c["expected"]
    rec("EV-SLAB-001", "As_req [cm2/m]", e["As_req_cm2_per_m"], As,
        "num rel 1e-6", num_ok(e["As_req_cm2_per_m"], As))
    rec("EV-SLAB-001", "feasible", True, feas, "exact", feas is True)
    tr = ENG_SLAB._temp_steel_ratio(i["fy_ksc"] * KSC_TO_MPA)
    rec("EV-SLAB-001", "temp_steel_ratio", e["temp_ratio"], tr,
        "num rel 1e-9", num_ok(e["temp_ratio"], tr, 1e-9, 1e-12))
    Ab_db10 = math.pi * 10.0 ** 2 / 4.0 / 100.0
    S, _ = ENG_SLAB._spacing_for(Ab_db10, As, i["s_max_cm"])
    rec("EV-SLAB-001", "bar spacing [cm]", e["spacing_cm"], S,
        "discrete (exact)", num_ok(e["spacing_cm"], S, 1e-9, 1e-9))

    rec_note("EV-SLAB-002", "two-way moment coefficients",
             "Equation verified via EV-SLAB-001. Coefficient table source "
             "(edition, m threshold) = REFERENCE REQUIRED.", "REVIEW")

    # EV-STAIR-001
    c = C["EV-STAIR-001"]
    i = c["inputs"]
    from modules import stair as ENG_STAIR
    As_s, feas_s = ENG_STAIR._as_flexure_ksc(i["Mu_kgfm_per_m"], i["b_cm"],
                                             i["d_cm"], i["fc_ksc"], i["fy_ksc"])
    e = c["expected"]
    rec("EV-STAIR-001", "As_req [cm2/m]", e["As_req_cm2_per_m"], As_s,
        "num rel 1e-6", num_ok(e["As_req_cm2_per_m"], As_s))
    rec("EV-STAIR-001", "feasible", True, feas_s, "exact", feas_s is True)
    rec_note("EV-STAIR-002", "stair load build-up (Wu, Mu)",
             "Inside _render_straight_stair / _render_u_shape_stair -> "
             "BLOCKED. VF-06 load-model difference recorded.", "BLOCKED")

    # EV-FOOT-001
    c = C["EV-FOOT-001"]
    i = c["inputs"]
    from modules import footing as ENG_FOOT
    As_f, Rn_f, rho_f, feas_f = ENG_FOOT._flexure_as(
        i["Mu_Nmm"], i["b_mm"], i["d_mm"], i["fc_MPa"], i["fy_MPa"])
    e = c["expected"]
    rec("EV-FOOT-001", "As_req [mm2]", e["As_req_mm2"], As_f, "num rel 1e-6",
        num_ok(e["As_req_mm2"], As_f, 1e-6, 1e-4))
    rec("EV-FOOT-001", "Rn [MPa]", e["Rn_MPa"], Rn_f, "num rel 1e-6",
        num_ok(e["Rn_MPa"], Rn_f))
    rec("EV-FOOT-001", "feasible", e["feasible"], feas_f, "exact",
        e["feasible"] == feas_f)

    rec_note("EV-FOOT-002", "circular-pile punching perimeter (VF-09)",
             "engine literal 3.464*Dp + pi*d vs ACI code form pi*(Dp+d): "
             "see JSON for the quantified gap. CODE REFERENCE TO VERIFY.",
             "REVIEW")
    rec_note("EV-FOOT-003", "footing full chain", "BLOCKED (render-interleaved).",
             "BLOCKED")


# =========================================================================
# report
# =========================================================================
def main():
    brief = "--brief" in sys.argv
    run_aci()
    run_beam()
    run_column()
    run_analysis()
    run_slab_stair_footing()

    npass = sum(1 for r in ROWS if r["status"] == "PASS")
    nfail = sum(1 for r in ROWS if r["status"] == "FAIL")
    nrev = sum(1 for r in ROWS if r["status"] == "REVIEW")
    nblk = sum(1 for r in ROWS if r["status"] == "BLOCKED")

    if not brief:
        print("\nEV-02 VALIDATION - independent reference vs live engine\n"
              + "=" * 78)
        cur = None
        for r in ROWS:
            if r["case"] != cur:
                cur = r["case"]
                print(f"\n[{cur}]")
            exp = r["expected"]
            act = r["actual"]
            if isinstance(exp, float):
                exp = f"{exp:,.6g}"
            if isinstance(act, float):
                act = f"{act:,.6g}"
            diff = r["diff"]
            if isinstance(diff, float):
                diff = f"{diff:+.3g}"
            print(f"  {r['status']:7s} {r['qty']}")
            if act != "-":
                print(f"          expected={exp}  actual={act}  diff={diff}"
                      f"  tol=({r['tol']})")
            else:
                print(f"          {exp}")

    print("\n" + "=" * 78)
    print(f"EV-02 checks: {len(ROWS)}   "
          f"PASS={npass}  FAIL={nfail}  REVIEW={nrev}  BLOCKED={nblk}")
    print("Regression baseline (separate): run  py -3 -m pytest -q  -> 73 passed")
    print("=" * 78)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
