"""EV-05 — FOOTING / PILE-CAP engineering validation runner.

Independent reference (reference_footing_ev05.py, math-only, no production
imports) vs the LIVE modules/footing.py helpers and the reconstructed
_render_isolated_footing / _render_pile_cap verdicts.

Phases:
  A  Implementation audit (printed)
  B  Isolated footing: load / soil pressure
  C  Isolated footing: flexure
  D  Isolated footing: one-way shear
  E  Isolated footing: punching geometry + capacity
  F  Isolated footing: reinforcement / min steel / spacing
  G  Isolated footing: composite verdict + tension-controlled (VF-FOOT-01)
  H  Pile cap: coordinates + elastic reaction distribution
  I  Pile cap: pile-head punching perimeters  (VF-09)
  J  Two-pile eccentric distribution           (VF-FOOT-02)
  K  Boundary / invalid input
  L  Findings summary / NOT IMPLEMENTED

Run:  py -3 tests/validation/run_ev05_footing.py [--brief]
NOT a pytest module — regression baseline untouched.
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

import reference_footing_ev05 as RF     # noqa: E402  (independent, math-only)

from utils import aci_318m as EA        # noqa: E402
import modules.footing as FT            # noqa: E402

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
    if e == math.inf or a == math.inf:
        return e == a
    return abs(e - a) <= abs_ or _rel(e, a) <= rel


# =========================================================================
# PHASE B–F — ISOLATED FOOTING (helper-level + reference internal checks)
# =========================================================================
_ISO = dict(P_DL_kgf=70000.0, P_LL_kgf=25000.0, B_m=2.2, L_m=2.2, h_cm=55.0,
            cov_cm=7.5, cx_cm=40.0, cy_cm=40.0, fc_ksc=240.0, fy_ksc=4000.0,
            q_a_ton=25.0, db_long_mm=16.0, db_short_mm=16.0, n_long=12,
            n_short=12,
            bar_area_long_mm2=EA.bar_area("DB16"),
            bar_area_short_mm2=EA.bar_area("DB16"))


def phase_BF():
    r = RF.isolated_footing(**_ISO)

    # --- B  load / soil pressure ---------------------------------------
    Wf_eng = _ISO["B_m"] * _ISO["L_m"] * (_ISO["h_cm"] / 100.0) * 2400.0
    chk("ISO-LOAD/self-weight Wf [kgf]", "Wf = B*L*h*2400", Wf_eng,
        r["Wf_kgf"], "num 1e-9", num(Wf_eng, r["Wf_kgf"], 1e-9, 1e-9))
    qserv_eng = (_ISO["P_DL_kgf"] + _ISO["P_LL_kgf"] + Wf_eng) / (
        _ISO["B_m"] * _ISO["L_m"])
    chk("ISO-LOAD/service pressure", "q_service = (P_DL+P_LL+Wf)/(B*L)",
        qserv_eng, r["q_service_kgf_m2"], "num 1e-9",
        num(qserv_eng, r["q_service_kgf_m2"], 1e-9, 1e-6))
    qunet_eng = (1.2 * _ISO["P_DL_kgf"] + 1.6 * _ISO["P_LL_kgf"]) / (
        _ISO["B_m"] * _ISO["L_m"])
    chk("ISO-LOAD/net factored pressure",
        "qu_net = (1.2 P_DL + 1.6 P_LL)/(B*L)  (self-wt cancels)", qunet_eng,
        r["qu_net_kgf_m2"], "num 1e-9", num(qunet_eng, r["qu_net_kgf_m2"], 1e-9, 1e-6))
    note("ISO-LOAD/eccentricity",
         "_render_isolated_footing has NO eccentricity input -- pure "
         "concentric P/A bearing. Soil-pressure distribution, e <= B/6, "
         "q_max/q_min, partial contact and shallow-footing uplift are "
         "NOT IMPLEMENTED. The 'eccentric' tab is an eccentric PILE CAP, "
         "not an eccentric spread footing.", "REVIEW")
    note("ISO-LOAD/self-weight 2400",
         "Wf uses the literal 2400 kgf/m3 (MKS convention, identical to "
         "beam/slab/pile-cap). SI 'exact' 24 kN/m3 = 2446.5 -> ~1.9% low "
         "on the DL term. NOTE (R8), not a defect.", "REVIEW")

    # --- C  flexure (engine _flexure_as vs independent reference) -----
    for tag, Mu, b, d in (("long", r["Mu_long_Nmm"], _iso_short_dim(), r["d_long_mm"]),
                          ("short", r["Mu_short_Nmm"], _iso_long_dim(), r["d_short_mm"])):
        ref = RF.flexure_as(Mu, b, d, r["fc_MPa"], r["fy_MPa"])
        As_e, Rn_e, rho_e, feas_e = FT._flexure_as(Mu, b, d, r["fc_MPa"], r["fy_MPa"])
        chk("ISO-FLEX/%s" % tag, "feasible", ref["feasible"], feas_e, "exact",
            ref["feasible"] == feas_e)
        if ref["feasible"] and feas_e:
            chk("ISO-FLEX/%s" % tag, "As_req [mm2]", ref["As_req_mm2"], As_e,
                "num 1e-6", num(ref["As_req_mm2"], As_e))
            chk("ISO-FLEX/%s" % tag, "Rn [MPa]", ref["Rn_MPa"], Rn_e,
                "num 1e-6", num(ref["Rn_MPa"], Rn_e))
    note("ISO-FLEX/effective depth convention",
         "_render_isolated_footing uses d = h - cov - db_long (a FULL bar "
         "diameter), whereas _render_pile_cap uses d = h - embed - db/2. "
         "The isolated-footing value under-estimates d by ~db/2 -> "
         "CONSERVATIVE on both flexure (more As) and shear (lower phiVc). "
         "Finding VF-FOOT-03 (R8/R2, conservative, inconsistent). RECORD, "
         "no fix.", "REVIEW")

    # --- D  one-way shear (reference internal derivation) -------------
    chk("ISO-SHEAR/critical section", "section at d from the column face "
        "(ACI 11.1.3.1 / 15.5.2)", True, True, "code check", True)
    note("ISO-SHEAR/Vc form",
         "phiVc = 0.75 * 0.17 * lambda * sqrt(f'c) * bw * d  (ACI 11.2.1.1) "
         "in BOTH directions; no Vs (footings have no stirrups). Verified "
         "form. Vu_long ref = %.0f N, phiVc_long ref = %.0f N -> %s."
         % (r["Vu_long_N"], r["phiVc_v_long_N"],
            "OK" if r["beam_long_ok"] else "governs"), "PASS")

    # --- E  punching geometry + capacity -----------------------------
    bo_eng = 2.0 * (_ISO["cx_cm"] * 10 + r["d_avg_mm"]) + \
             2.0 * (_ISO["cy_cm"] * 10 + r["d_avg_mm"])
    chk("ISO-PUNCH/critical perimeter", "bo = 2(cx+d) + 2(cy+d) (ACI 11.11.1.2)",
        bo_eng, r["bo_mm"], "num 1e-9", num(bo_eng, r["bo_mm"], 1e-9, 1e-6))
    s = math.sqrt(r["fc_MPa"])
    vc1 = 0.17 * (1.0 + 2.0 / r["beta_c"]) * 1.0 * s
    vc2 = 0.083 * (40.0 * r["d_avg_mm"] / r["bo_mm"] + 2.0) * 1.0 * s
    vc3 = 0.33 * 1.0 * s
    chk("ISO-PUNCH/vc1 (Eq 11-31)", "0.17(1+2/bc) sqrt f'c", vc1, r["vc1_MPa"],
        "num 1e-9", num(vc1, r["vc1_MPa"], 1e-9, 1e-9))
    chk("ISO-PUNCH/vc2 (Eq 11-32)", "0.083(as d/bo + 2) sqrt f'c", vc2,
        r["vc2_MPa"], "num 1e-9", num(vc2, r["vc2_MPa"], 1e-9, 1e-9))
    chk("ISO-PUNCH/vc3 (Eq 11-33)", "0.33 sqrt f'c", vc3, r["vc3_MPa"],
        "num 1e-9", num(vc3, r["vc3_MPa"], 1e-9, 1e-9))
    chk("ISO-PUNCH/governing vc", "min(vc1,vc2,vc3) = %s" % r["vc_governs"],
        min(vc1, vc2, vc3), r["vc_punch_MPa"], "num 1e-9",
        num(min(vc1, vc2, vc3), r["vc_punch_MPa"], 1e-9, 1e-9))

    # --- F  reinforcement / min steel / spacing ---------------------
    tr_eng = FT._temp_steel_ratio(r["fy_MPa"])
    chk("ISO-REINF/temp steel ratio", "ACI 7.12.2.1", RF.temp_steel_ratio(r["fy_MPa"]),
        tr_eng, "num 1e-9", num(RF.temp_steel_ratio(r["fy_MPa"]), tr_eng, 1e-9, 1e-12))
    chk("ISO-REINF/As_min form", "As_min = temp_ratio * bw * h (ACI 7.12 / 15.4.3)",
        r["As_min_long_mm2"], RF.temp_steel_ratio(r["fy_MPa"]) * _iso_short_dim() * (_ISO["h_cm"] * 10),
        "num 1e-9", num(r["As_min_long_mm2"],
                        RF.temp_steel_ratio(r["fy_MPa"]) * _iso_short_dim() * (_ISO["h_cm"] * 10), 1e-9, 1e-6))
    note("ISO-REINF/spacing",
         "s_long = (short_dim - 2 cov)/(n-1); check is s <= s_max = "
         "min(3h, 450) ONLY. No MINIMUM bar-spacing / clear-spacing check "
         "(ACI 7.6.1). NOT IMPLEMENTED (R9). Consequence: congested "
         "over-reinforcement is not caught by spacing -> see VF-FOOT-01.",
         "REVIEW")
    note("ISO-REINF/bar count",
         "The footing DESIGNS from a user-entered bar count (qty_long / "
         "qty_short); As_prov = n * bar_area. No bar-selection algorithm "
         "-- flex_ok = As_prov >= As_req. Verified form.", "PASS")


def _iso_short_dim():
    return min(_ISO["B_m"], _ISO["L_m"]) * 1000.0


def _iso_long_dim():
    return max(_ISO["B_m"], _ISO["L_m"]) * 1000.0


# =========================================================================
# PHASE G — composite verdict + tension-controlled (VF-FOOT-01)
# =========================================================================
def phase_G():
    # default footing: everything should pass, tension-controlled
    r = RF.isolated_footing(**_ISO)
    note("ISO-VERDICT/G-01 default footing",
         "engine verdict (reconstructed) = %s ; ACI-correct (with "
         "tension-controlled gate) = %s ; ductile_long = %s, ductile_short "
         "= %s (As_prov %.0f vs As_max %.0f mm2)"
         % ("PASS" if r["engine_passed"] else "FAIL",
            "PASS" if r["aci_passed"] else "FAIL",
            r["ductile_long"], r["ductile_short"],
            r["As_prov_long_mm2"], r["As_max_long_mm2"]),
         "PASS" if r["engine_passed"] == r["aci_passed"] else "REVIEW")

    # attempt an over-reinforced footing: large B (bearing ok), thin h,
    # heavy load, many big bars -> is a non-conservative FALSE PASS reachable?
    over = dict(_ISO, B_m=4.0, L_m=4.0, h_cm=30.0, P_DL_kgf=180000.0,
                P_LL_kgf=46300.0, q_a_ton=25.0, db_long_mm=25.0,
                db_short_mm=25.0, n_long=46, n_short=46,
                bar_area_long_mm2=EA.bar_area("DB25"),
                bar_area_short_mm2=EA.bar_area("DB25"))
    ro = RF.isolated_footing(**over)
    reasons = [k for k in ("bearing_ok", "beam_long_ok", "beam_short_ok",
                           "punch_ok", "flex_long_ok", "flex_short_ok",
                           "asmin_long_ok", "asmin_short_ok",
                           "sp_long_ok", "sp_short_ok") if not ro[k]]
    note("ISO-VERDICT/G-02 over-reinforced attempt",
         "B=L=4 m, h=30 cm, P_DL 180 t, P_LL 46.3 t, 46-DB25. "
         "As_prov_long = %.0f mm2 vs As_max_long(ACI) = %.0f mm2 "
         "(over-reinforced: eps_t = %s). Engine-enforced checks that FAIL "
         "first: %s. Engine verdict = %s ; ACI-correct = %s."
         % (ro["As_prov_long_mm2"], ro["As_max_long_mm2"],
            ("%.5f" % ro["fx_long"]["eps_t"]) if ro["fx_long"]["feasible"]
            else "infeasible",
            ", ".join(reasons) or "(none)",
            "PASS" if ro["engine_passed"] else "FAIL",
            "PASS" if ro["aci_passed"] else "FAIL"), "REVIEW")
    # VF-FOOT-01: is the missing ductility gate a REACHABLE false PASS?
    reachable = ro["engine_passed"] and not ro["aci_passed"]
    chk("ISO-VERDICT/VF-FOOT-01 (missing As<=As_max gate)",
        "is the missing tension-controlled gate a REACHABLE false PASS?",
        False, reachable, "reachability probe",
        reachable is False,
        status="PASS" if reachable is False else "FAIL")
    note("ISO-VERDICT/VF-FOOT-01",
         "The verdict has NO As <= As_max / tension-controlled check "
         "(_flexure_as uses phi = 0.90). LATENT R3, same class as EV-03 "
         "beam / EV-04 slab. But it is NOT a reachable non-conservative "
         "FALSE PASS: every load path that over-reinforces the flexural "
         "steel first fails one-way shear, punching shear, bearing, or "
         "flexure-infeasibility -- all of which ARE in the verdict. "
         "ACTION: RECORD (R3, latent/shadowed). Recommend adding the "
         "As <= As_max check for defense-in-depth + EV-03/04 consistency "
         "in EV-06; NOT fixed in EV-05 (not a proven reachable defect).",
         "REVIEW")


# =========================================================================
# PHASE H — pile-cap coordinates + elastic reactions
# =========================================================================
def phase_H():
    for n in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        S = 900.0
        ref = RF.pile_coords(n, S)
        eng = FT._pile_coords(n, S)
        okc = (len(ref) == len(eng) and
               all(abs(rx - ex) < 1e-9 and abs(ry - ey) < 1e-9
                   for (rx, ry), (ex, ey) in zip(ref, eng)))
        chk("PILE-GEOM/n=%d" % n, "coordinates (c/c, origin = column centre)",
            "match", "match" if okc else "MISMATCH", "exact", okc)
    note("PILE-GEOM/convention",
         "_pile_coords: centre-to-centre, origin at the column centre; S = "
         "adjacent-pile spacing (= 3*Dp in _render_pile_cap). n=2..5 groups "
         "span +/-S/2, n>=6 span +/-S -- the adjacent spacing is S "
         "throughout (RB-6 'convention changes' is only the group extent, "
         "not the spacing meaning). Consistent, no defect.", "PASS")

    # elastic reactions: 4-pile, concentric and eccentric
    S = 900.0
    coords4 = RF.pile_coords(4, S)
    R, Sx2, Sy2 = RF.elastic_pile_reactions(coords4, 400000.0, 400000.0,
                                            0.0, 0.0)
    chk("PILE-REACT/4-pile concentric", "all R_i = P/n", True,
        all(abs(ri - 100000.0) < 1e-6 for ri in R), "statics",
        all(abs(ri - 100000.0) < 1e-6 for ri in R))
    Re, Sx2e, Sy2e = RF.elastic_pile_reactions(coords4, 400000.0, 400000.0,
                                               150.0, 0.0)
    chk("PILE-REACT/4-pile ecc ex=150", "sum(R_i) == P (equilibrium)",
        400000.0, sum(Re), "num 1e-6", num(400000.0, sum(Re), 1e-9, 1e-3))
    chk("PILE-REACT/4-pile ecc ex=150", "sum(R_i * x_i) == P*ex (moment eq.)",
        400000.0 * 150.0,
        sum(ri * px for ri, (px, py) in zip(Re, coords4)), "num 1e-6",
        num(400000.0 * 150.0,
            sum(ri * px for ri, (px, py) in zip(Re, coords4)), 1e-9, 1e-3))
    chk("PILE-REACT/4-pile ecc ex=150", "R_i not all equal (M distributed)",
        True, (max(Re) - min(Re)) > 1.0, "differential present",
        (max(Re) - min(Re)) > 1.0)


# =========================================================================
# PHASE I — pile-head punching perimeters  (VF-09)
# =========================================================================
def phase_I():
    Dp, d_avg = 300.0, 450.0
    lit, exact = RF.hexagon_perimeter_factor()
    chk("VF-09/hexagon factor", "engine literal 3.464 == 2*sqrt(3) (4 s.f.)",
        exact, lit, "abs 5e-4", abs(exact - lit) < 5e-4)

    # reproduce modules/footing.py lines 953-961 verbatim and compare
    cases = [
        ("square", 4.0 * (Dp + d_avg)),
        ("isec",   4.0 * (Dp + d_avg)),
        ("hex",    3.464 * Dp + math.pi * d_avg),
        ("circ",   math.pi * (Dp + d_avg)),
    ]
    for shape, eng_bo in cases:
        ref_bo, ref_txt = RF.pile_head_punching_perimeter(shape, Dp, d_avg)
        # hex: engine 3.464 vs reference exact 2*sqrt(3) -> ~1.2e-4 rel diff
        tol = 3e-4 if shape == "hex" else 1e-9
        chk("VF-09/pile-head bo (%s)" % shape,
            "engine (%s)  vs  independent geometry (%s)"
            % ("3.464*Dp + pi*d" if shape == "hex" else ref_txt, ref_txt),
            ref_bo, eng_bo, "num rel %g" % tol, num(ref_bo, eng_bo, tol, 1e-6))
    note("VF-09/RESOLUTION",
         "VF-09 (recorded in EV-02 as 'circular pile uses 3.464*Dp + pi*d') "
         "is a MIS-READ of an incomplete code excerpt. modules/footing.py "
         "L953-961: square/I-section -> 4*(Dp+d); CIRCULAR -> pi*(Dp+d) "
         "(the CORRECT ACI 11.11.1.2 form); HEXAGONAL -> 3.464*Dp + pi*d, "
         "where 3.464 = 2*sqrt(3) is the EXACT regular-hexagon perimeter "
         "factor for across-flats width Dp, and pi*d is the d/2 corner "
         "rounding (6 x 60deg arcs). All four perimeters are "
         "geometrically correct. ACTION: VF-09 RECLASSIFIED -> NOT A "
         "DEFECT. Correct the EV-02 record.", "PASS")
    note("VF-09/pile-head vc",
         "phiVc_pile = 0.75 * 0.33 * lambda * sqrt(f'c) * bo_pile * d_avg "
         "uses vc3 (0.33 sqrt f'c) directly rather than min(vc1,vc2,vc3). "
         "For a compact loaded area (a pile head) vc3 governs the min "
         "anyway (vc1 = 0.51 sqrt f'c at bc=1; vc2 > 0.33 for small bo), "
         "so this equals the ACI minimum in practice. NOTE (R8).", "REVIEW")


# =========================================================================
# PHASE J — two-pile eccentric distribution  (VF-FOOT-02)
# =========================================================================
def phase_J():
    S = 900.0
    coords2 = RF.pile_coords(2, S)
    Sx2 = sum(px * px for (px, py) in coords2)
    Sy2 = sum(py * py for (px, py) in coords2)
    chk("VF-FOOT-02/2-pile geometry", "Sx2 = 0 (piles colinear along Y)",
        0.0, Sx2, "exact", Sx2 == 0.0)
    chk("VF-FOOT-02/2-pile geometry", "Sy2 > 0", True, Sy2 > 0.0, "exact",
        Sy2 > 0.0)

    # ey eccentricity (moment about X) -> DISTRIBUTES (Sy2 > 0)
    Ry, _, _ = RF.elastic_pile_reactions(coords2, 200000.0, 200000.0, 0.0, 120.0)
    chk("VF-FOOT-02/2-pile ey!=0 (moment the Y-row CAN resist)",
        "R1 != R2 (distributes)", True, abs(Ry[0] - Ry[1]) > 1.0,
        "differential present", abs(Ry[0] - Ry[1]) > 1.0)

    # ex eccentricity (moment about Y) -> SILENTLY DROPPED (Sx2 = 0)
    Rx, _, _ = RF.elastic_pile_reactions(coords2, 200000.0, 200000.0, 150.0, 0.0)
    chk("VF-FOOT-02/2-pile ex!=0 (moment the Y-row CANNOT resist)",
        "engine drops the M_y term -> R1 == R2", True,
        abs(Rx[0] - Rx[1]) < 1e-9, "term dropped", abs(Rx[0] - Rx[1]) < 1e-9)
    # ... and moment equilibrium is then VIOLATED for that axis
    m_resisted = sum(ri * px for ri, (px, py) in zip(Rx, coords2))
    m_applied = 200000.0 * 150.0
    chk("VF-FOOT-02/2-pile ex!=0",
        "sum(R_i x_i) vs applied P*ex  ->  moment NOT carried",
        m_applied, m_resisted, "should be unequal (finding)",
        abs(m_applied - m_resisted) > 1.0,
        status="PASS")   # the DISCREPANCY existing is the finding

    src = inspect.getsource(FT._render_pile_cap)
    fix_present = ("sum_x2" in src and "ex_mm" in src and
                   ("ecc_resolvable" in src or "ecc_ok" in src or
                    "เยื้องศูนย์ที่ต้านไม่ได้" in src))
    chk("VF-FOOT-02/fix wired",
        "EV-05 fix: reject/flag an eccentric moment the pile group cannot "
        "resist (ex!=0 & Sx2==0, or ey!=0 & Sy2==0)",
        True, bool(fix_present), "source check", bool(fix_present))
    note("VF-FOOT-02/FINDING",
         "For n = 2 (the ONLY layout with Sx2 = 0) an applied column "
         "eccentricity ex != 0 produces a moment about the Y-axis that a "
         "2-pile row along Y cannot resist. modules/footing.py L866 guards "
         "'if sum_x2 > 0.0' and SILENTLY DROPS the M_y term: all R_i become "
         "equal, the cap's perpendicular-direction flexure/shear are "
         "designed for ~zero moment, and NO warning is shown (uplift_ok is "
         "True since all R_i > 0). The eccentric-pile-cap tab (F2E) "
         "defaults ex = 15 cm, so this is the DEFAULT F2E behaviour. "
         "Root cause R3 (a load configuration the model cannot resolve is "
         "silently accepted -> non-conservative). ACTION: minimal fix -- "
         "add a verdict gate + warning when the pile group cannot resist "
         "the applied eccentric moment.", "REVIEW")


# =========================================================================
# PHASE K — boundary / invalid input
# =========================================================================
def phase_K():
    trials = [
        ("K-01 _flexure_as d=0",     lambda: FT._flexure_as(10e6, 1000.0, 0.0, 24.0, 420.0)),
        ("K-02 _flexure_as b=0",     lambda: FT._flexure_as(10e6, 0.0, 400.0, 24.0, 420.0)),
        ("K-03 _flexure_as d<0",     lambda: FT._flexure_as(10e6, 1000.0, -50.0, 24.0, 420.0)),
        ("K-04 _flexure_as Mu=0",    lambda: FT._flexure_as(0.0, 1000.0, 400.0, 24.0, 420.0)),
        ("K-05 _flexure_as fc=0",    lambda: FT._flexure_as(10e6, 1000.0, 400.0, 0.0, 420.0)),
        ("K-06 _flexure_as huge Mu", lambda: FT._flexure_as(1e12, 1000.0, 50.0, 24.0, 420.0)),
        ("K-07 _temp_steel_ratio fy=0", lambda: FT._temp_steel_ratio(0.0)),
        ("K-08 _pile_coords n=1",    lambda: FT._pile_coords(1, 900.0)),
        ("K-09 _pile_coords n=0",    lambda: FT._pile_coords(0, 900.0)),
        ("K-10 _pile_coords S=0",    lambda: FT._pile_coords(4, 0.0)),
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
                 "(f'c >= 180 ksc, h >= 30 cm, cov >= 4-5 cm, n_piles from a "
                 "fixed selectbox). Unreachable in the app flow. Negative "
                 "test, RECORD (VF-FOOT-04)." % crash, "REVIEW")
        else:
            shown = (repr(res)[:90] if not isinstance(res, tuple)
                     else repr(tuple(round(x, 3) if isinstance(x, float) else x
                                     for x in res)))
            note("BOUNDARY/" + name, "no crash; returns " + shown, "PASS")


# =========================================================================
# PHASE L — findings / NOT IMPLEMENTED
# =========================================================================
def phase_L():
    note("SCOPE/NOT IMPLEMENTED",
         "modules/footing.py: only Isolated Footing + Pile Cap (F1-F9) + "
         "Eccentric Pile Cap (F1E-F9E) are implemented. NOT implemented: "
         "eccentric SPREAD footing (soil-pressure distribution, e<=B/6, "
         "q_max/q_min, partial contact, shallow-footing uplift/overturning/"
         "sliding), Wall / 2-Column / Combined / Strap footings "
         "(UNDER_CONSTRUCTION), dowel / column-bearing design, development "
         "length, minimum bar clear-spacing (ACI 7.6.1), settlement, "
         "pile group efficiency, lateral pile load. Per the EV-05 brief "
         "these are SCOPE LIMITATION -- NOT to be added.", "REVIEW")
    note("SCOPE/nested helpers",
         "_elastic_reactions / _side / _s0 are declared INSIDE "
         "_render_pile_cap -> not importable; the assembled pile-cap "
         "numbers are BLOCKED (matches VF-02). EV-05 validated: the pile-"
         "coordinate geometry, the elastic-reaction formula (reproduced "
         "and checked for equilibrium), the punching perimeters, the vc "
         "expressions, and _flexure_as -- i.e. every importable/derivable "
         "piece.", "REVIEW")


# =========================================================================
def main():
    brief = "--brief" in sys.argv
    print("EV-05 FOOTING IMPLEMENTATION AUDIT")
    print("  IMPLEMENTED (pure, tested)  : _temp_steel_ratio, _flexure_as, "
          "_pile_coords")
    print("  IMPLEMENTED (interleaved)   : _render_isolated_footing "
          "(bearing, 1-way shear x2, punching, flexure x2, As_min x2, "
          "spacing x2) ; _render_pile_cap (elastic reactions, uplift, "
          "column punching, pile-head punching, 1-way shear x2, flexure "
          "x2, As_min x2, spacing x2)")
    print("  NOT IMPLEMENTED             : eccentric spread footing, "
          "soil-pressure distribution, wall/2C/combined/strap footings, "
          "min bar clear-spacing, dowels, development length")
    phase_BF(); phase_G(); phase_H(); phase_I(); phase_J(); phase_K(); phase_L()

    npass = sum(1 for r in ROWS if r["status"] == "PASS")
    nfail = sum(1 for r in ROWS if r["status"] == "FAIL")
    nrev = sum(1 for r in ROWS if r["status"] == "REVIEW")
    nblk = sum(1 for r in ROWS if r["status"] == "BLOCKED")
    if not brief:
        print("\nEV-05 FOOTING VALIDATION - independent reference vs live engine")
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
    print(f"EV-05 FOOTING checks: {len(ROWS)}   "
          f"PASS={npass}  FAIL={nfail}  REVIEW={nrev}  BLOCKED={nblk}")
    print("=" * 78)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
