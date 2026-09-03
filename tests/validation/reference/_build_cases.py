"""EV-02 — generate the reference case JSON files under cases/.

Run:  py -3 tests/validation/reference/_build_cases.py

This script uses ONLY the independent reference calculators in this
package (reference_aci / reference_flexure / reference_shear /
reference_analysis / reference_column).  It never imports a production
calculation function.  The JSON it writes is the durable EV-02 artifact;
`run_ev02_validation.py` then compares those expected values against the
live engine.

Each case follows the schema in docs/ENGINEERING_VALIDATION.md Appendix B
/ tests/validation/README.md.  `actual_engine_result` is deliberately
absent (EV-02 is independent reference only).
"""

import json
import math
import os

import reference_aci as R_ACI
import reference_flexure as R_FLEX
import reference_shear as R_SHEAR
import reference_analysis as R_AN
import reference_column as R_COL

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cases")

KSC_TO_MPA = 0.0980665


def _w(name, cases):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cases, fh, indent=2, ensure_ascii=False)
    print(f"wrote {name}: {len(cases)} cases")


# ===========================================================================
# P0-A / P0-G  — ACI primitives
# ===========================================================================
def build_aci():
    cases = []

    # -- EV-ACI-001  beta1 -------------------------------------------------
    b1 = {}
    for fc in (21.0, 28.0, 35.0, 42.0, 56.0):
        b1[f"fc_{fc:g}_MPa"] = R_ACI.beta1_si(fc)
    cases.append({
        "case_id": "EV-ACI-001",
        "module": "utils/aci_318m.py :: beta1 / get_beta1",
        "category": "ACI primitive",
        "description": "Equivalent stress-block factor beta1 across the "
                       "ACI 10.2.7.3 piecewise definition.",
        "inputs": {"fc_MPa": [21.0, 28.0, 35.0, 42.0, 56.0]},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "10.2.7.3",
                           "equation": "beta1 = 0.85 (fc<=28); "
                                       "0.85-0.05(fc-28)/7 (>=0.65)"},
        "expected": {"beta1": b1},
        "intermediate": {
            "note": "35 MPa: 0.85-0.05*(7)/7 = 0.80 ; "
                    "42 MPa: 0.85-0.05*(14)/7 = 0.75 ; 56 MPa: floor 0.65"},
        "tolerance": {"type": "numerical", "rel": 1e-9, "abs": 1e-12,
                      "rationale": "closed-form piecewise linear; exact"},
        "notes": "Pair with EV-ACI-001M for the MKS-form discrepancy (VF-07).",
        "status": "REFERENCE_READY",
    })

    # -- EV-ACI-001M  beta1 MKS vs code-consistent (VF-07) ---------------
    pts = [240.0, 280.0, 300.0, 350.0, 420.0]
    mks = {f"fc_{p:g}_ksc": R_ACI.beta1_mks(p) for p in pts}
    codec = {f"fc_{p:g}_ksc": R_ACI.beta1_mks_via_si(p) for p in pts}
    gap = {f"fc_{p:g}_ksc": R_ACI.beta1_mks(p) - R_ACI.beta1_mks_via_si(p)
           for p in pts}
    cases.append({
        "case_id": "EV-ACI-001M",
        "module": "modules/beam.py :: _beta1_ksc ; modules/column.py :: "
                  "_beta1_col_ksc",
        "category": "ACI primitive / engineering assumption (VF-07)",
        "description": "MKS beta1 helpers break at a literal 280 ksc and "
                       "-0.05 per 70 ksc; the single ACI 10.2.7.3 "
                       "definition breaks at 28 MPa (= 285.53 ksc). "
                       "Quantify the resulting beta1 gap.",
        "inputs": {"fc_ksc": pts},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "10.2.7.3",
                           "equation": "one definition in MPa; MKS "
                                       "transcription should convert first"},
        "expected": {"beta1_engine_MKS_form": mks,
                     "beta1_code_consistent": codec,
                     "beta1_gap_engine_minus_code": gap},
        "intermediate": {
            "break_point_ksc_equiv_of_28MPa": 28.0 / KSC_TO_MPA,
            "max_abs_gap": max(abs(v) for v in gap.values()),
            "comment": "At/under 280 ksc both give 0.85 (no gap). Above the "
                       "break the MKS-form beta1 is a few thousandths LOWER "
                       "than the code-consistent value; effect on phiMn is "
                       "second order (changes 'a', not the lever arm much)."},
        "tolerance": {"type": "engineering", "value": "TBD",
                      "rationale": "this case documents a modelling choice, "
                                   "not a pass/fail on a single number; "
                                   "EV-03 decides whether the gap is "
                                   "acceptable for design output."},
        "notes": "RECORD ONLY. Do not change either helper.",
        "status": "REVIEW",
    })

    # -- EV-ACI-002  rho_min --------------------------------------------
    rmin_si = R_FLEX  # noqa (kept for clarity)
    combos_si = [(21.0, 392.266), (28.0, 392.266), (35.0, 392.266),
                 (24.0, 235.36)]
    exp_si = {f"fc{fc:g}_fy{fy:g}": R_ACI.rho_min_flexure_si(fc, fy)
              for fc, fy in combos_si}
    combos_mks = [(240.0, 4000.0), (280.0, 4000.0), (350.0, 4000.0),
                  (240.0, 2400.0)]
    exp_mks = {f"fc{fc:g}_fy{fy:g}": R_ACI.rho_min_flexure_mks(fc, fy)
               for fc, fy in combos_mks}
    cases.append({
        "case_id": "EV-ACI-002",
        "module": "utils/aci_318m.py :: rho_min_flexure / rho_min_flexure_ksc",
        "category": "ACI primitive",
        "description": "Minimum flexural steel ratio, both governing "
                       "branches, SI (0.25 sqrt/1.4) and MKS (0.8 sqrt/14).",
        "inputs": {"si_fc_fy_MPa": combos_si, "mks_fc_fy_ksc": combos_mks},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.5.1",
                           "equation": "rho_min = max(0.25 sqrt f'c / fy, "
                                       "1.4/fy) [MPa]"},
        "expected": {"rho_min_SI": exp_si, "rho_min_MKS": exp_mks},
        "intermediate": {
            "note": "For fy=392 MPa the 1.4/fy branch (0.003569) governs up "
                    "to fc ~ 31.4 MPa; above that 0.25 sqrt(fc)/fy governs."},
        "tolerance": {"type": "numerical", "rel": 1e-9, "abs": 1e-12,
                      "rationale": "closed form"},
        "notes": "MKS vs SI forms are numerically ~equivalent but not "
                 "identical (0.8 vs 0.25/sqrt(0.0980665)=0.7985; 14 vs "
                 "1.4/0.0980665=14.28). Small deliberate metric rounding.",
        "status": "REFERENCE_READY",
    })

    # -- EV-ACI-003  rho_max (tension-controlled) -----------------------
    combos = [(240.0, 4000.0), (280.0, 4000.0), (350.0, 4000.0),
              (240.0, 2400.0)]
    exp = {f"fc{fc:g}_fy{fy:g}": R_ACI.rho_max_tc_mks(fc, fy)
           for fc, fy in combos}
    cases.append({
        "case_id": "EV-ACI-003",
        "module": "modules/beam.py :: _rho_max_ksc "
                  "(cf. utils/aci_318m.rho_max_flexure)",
        "category": "ACI primitive",
        "description": "Tension-controlled maximum reinforcement ratio, "
                       "eps_t = 0.005 (c/d = 3/8), MKS.",
        "inputs": {"fc_fy_ksc": combos},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.3.4",
                           "equation": "rho_max = 0.85 beta1 f'c/fy * "
                                       "0.003/(0.003+0.005)"},
        "expected": {"rho_max_MKS": exp},
        "intermediate": {"factor_eps": 0.003 / (0.003 + 0.005)},
        "tolerance": {"type": "numerical", "rel": 1e-9, "abs": 1e-12,
                      "rationale": "closed form"},
        "notes": "Uses beta1_mks (280 ksc break) to match the engine helper.",
        "status": "REFERENCE_READY",
    })

    # -- EV-ACI-004  phi_flexure --------------------------------------
    strains = [0.001, 0.002, 0.00275, 0.00375, 0.005, 0.006]
    exp_tied = {f"eps_{e:g}": R_ACI.phi_from_strain(e, spiral=False)
                for e in strains}
    exp_sp = {f"eps_{e:g}": R_ACI.phi_from_strain(e, spiral=True)
              for e in strains}
    cases.append({
        "case_id": "EV-ACI-004",
        "module": "utils/aci_318m.py :: phi_flexure",
        "category": "ACI primitive",
        "description": "Strength-reduction factor vs net tensile strain, "
                       "tied and spiral, incl. both transition endpoints.",
        "inputs": {"eps_t": strains, "spiral": [False, True]},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "9.3.2",
                           "equation": "phi_c at eps_ty; 0.90 at 0.005; "
                                       "linear between (eps_ty = 0.002)"},
        "expected": {"phi_tied": exp_tied, "phi_spiral": exp_sp},
        "intermediate": {
            "eps_ty_literal": 0.002,
            "note": "Engine uses EPSILON_TY = 0.002 literal, not fy/Es. "
                    "For fy=420 MPa fy/Es = 0.0021 -> a ~0.4% wider "
                    "compression-controlled plateau. NOTE only."},
        "tolerance": {"type": "numerical", "rel": 1e-9, "abs": 1e-12,
                      "rationale": "closed form piecewise linear"},
        "notes": "",
        "status": "REFERENCE_READY",
    })

    # -- EV-ACI-005  Vc one-way -------------------------------------
    fc_ksc, b_cm, d_cm = 240.0, 30.0, 54.0
    fc_mpa = fc_ksc * KSC_TO_MPA
    eng_c, exact_c = R_ACI.vc_oneway_mks_053_coeff()
    cases.append({
        "case_id": "EV-ACI-005",
        "module": "utils/aci_318m.py :: vc_beam / vc_beam_ksc",
        "category": "ACI primitive",
        "description": "Concrete one-way (beam) shear strength, SI "
                       "0.17 sqrt f'c bw d and MKS 0.53 sqrt f'c b d.",
        "inputs": {"fc_ksc": fc_ksc, "b_cm": b_cm, "d_cm": d_cm,
                   "fc_MPa": fc_mpa, "bw_mm": b_cm * 10.0, "d_mm": d_cm * 10.0,
                   "lambda": 1.0},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "11.2.1.1",
                           "equation": "Vc = 0.17 lambda sqrt(f'c) bw d "
                                       "(Eq. 11-3)"},
        "expected": {
            "Vc_SI_N": R_ACI.vc_oneway_si(fc_mpa, b_cm * 10.0, d_cm * 10.0),
            "Vc_MKS_053_kgf": R_ACI.vc_oneway_mks_053(fc_ksc, b_cm, d_cm),
            "Vc_MKS_exact_equiv_kgf":
                R_ACI.vc_oneway_mks_from_si(fc_ksc, b_cm, d_cm),
        },
        "intermediate": {
            "mks_engine_coeff": eng_c,
            "mks_exact_coeff": exact_c,
            "coeff_ratio_engine_over_exact": eng_c / exact_c,
            "comment": "0.53 (engine) vs %.5f (exact SI-equivalent): the "
                       "traditional metric coefficient is ~2.4%% LOW, i.e. "
                       "slightly conservative. Standard ACI-MKS practice; "
                       "NOTE, not a defect." % exact_c},
        "tolerance": {
            "type": "engineering",
            "value": "SI form: numerical rel 1e-9. MKS 0.53 form vs "
                     "SI-exact: expect ~2.4% gap -- that gap is the "
                     "REFERENCE prediction, not slack.",
            "rationale": "two different code transcriptions; the gap is a "
                         "known modelling choice to be reported."},
        "notes": "",
        "status": "REFERENCE_READY",
    })

    # -- EV-ACI-006  two-way vc -------------------------------------
    fc_mpa2 = 240.0 * KSC_TO_MPA
    cx = cy = 400.0    # mm, square interior column
    d = 470.0          # mm
    bo = R_ACI.punching_perimeter_rect(cx, cy, d)
    vc1, vc2, vc3, vcg = R_ACI.vc_twoway_si(fc_mpa2, max(cx, cy) / min(cx, cy),
                                            bo, d, alpha_s=40.0)
    cases.append({
        "case_id": "EV-ACI-006",
        "module": "modules/footing.py :: _render_isolated_footing "
                  "(vc1/vc2/vc3 punching block)",
        "category": "ACI primitive / code-sensitive",
        "description": "Two-way (punching) shear stress capacity, three ACI "
                       "expressions and their governing minimum, square "
                       "interior column.",
        "inputs": {"fc_MPa": fc_mpa2, "cx_mm": cx, "cy_mm": cy, "d_mm": d,
                   "alpha_s": 40.0, "lambda": 1.0, "beta_c": 1.0},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "11.11.2.1",
                           "equation": "Eqs 11-31 (0.17(1+2/bc)), "
                                       "11-32 (0.083(as d/bo+2)), "
                                       "11-33 (0.33); vc = min"},
        "expected": {"b0_mm": bo, "vc1_MPa": vc1, "vc2_MPa": vc2,
                     "vc3_MPa": vc3, "vc_governing_MPa": vcg},
        "intermediate": {
            "governs": "vc3 (0.33 sqrt f'c) for a square column with a "
                       "compact critical perimeter -- confirm at runtime"},
        "tolerance": {"type": "numerical", "rel": 1e-9, "abs": 1e-12,
                      "rationale": "closed form"},
        "notes": "Rectangular b0 = 2(cx+d)+2(cy+d) is the ACI 11.11.1.2 "
                 "critical section -- correct. See EV-FOOT-002 for the "
                 "circular-pile perimeter finding (VF-09).",
        "status": "REFERENCE_READY",
    })

    # -- EV-ACI-007  tie spacing max (7.10.5.2) --------------------
    # main DB25 -> db = 2.5 cm ; tie RB9 -> 0.9 cm ; least dim 40 cm
    combos = [
        {"db_long_cm": 2.5, "db_tie_cm": 0.9, "least_dim_cm": 40.0},
        {"db_long_cm": 2.0, "db_tie_cm": 0.9, "least_dim_cm": 25.0},
        {"db_long_cm": 1.2, "db_tie_cm": 0.6, "least_dim_cm": 30.0},
    ]
    exp = []
    for c in combos:
        smax = R_ACI.tie_spacing_max(c["db_long_cm"], c["db_tie_cm"],
                                     c["least_dim_cm"])
        gov = min([("16db", 16.0 * c["db_long_cm"]),
                   ("48d_tie", 48.0 * c["db_tie_cm"]),
                   ("least_dim", c["least_dim_cm"])], key=lambda t: t[1])
        exp.append({"s_max_cm": smax, "governed_by": gov[0]})
    cases.append({
        "case_id": "EV-ACI-007",
        "module": "modules/column.py :: _render_column (tie-spacing check)",
        "category": "code-sensitive / discrete",
        "description": "Maximum permitted tie spacing = min(16 db_long, "
                       "48 db_tie, least column dimension).",
        "inputs": {"combos_cm": combos},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "7.10.5.2",
                           "equation": "s_max = min(16 db, 48 d_tie, "
                                       "least dimension)"},
        "expected": {"per_combo": exp},
        "intermediate": {
            "FINDING_VF10": "The engine computes s_max with exactly this "
                            "formula, then sets spacing_ok = (s_max >= 5 cm) "
                            "-- a constructability floor. It never receives a "
                            "PROVIDED tie spacing, so the 'below / at / above "
                            "the limit' PASS/FAIL boundary requested by the "
                            "EV-02 brief does not exist in the engine. "
                            "Validate the s_max FORMULA; record VF-10."},
        "tolerance": {"type": "discrete", "rationale": "exact min() of exact "
                      "products; governed-by branch is exact"},
        "notes": "RECORD ONLY.",
        "status": "REFERENCE_READY",
    })

    _w("aci_primitives.json", cases)


# ===========================================================================
# P0-B  — Beam flexure + shear
# ===========================================================================
def build_beam():
    cases = []
    fc_ksc, fy_ksc, b_cm, d_cm = 240.0, 4000.0, 30.0, 54.0

    # BEAM-FLEX-001  under-reinforced, clearly tension-controlled
    r = R_FLEX.singly_reinforced_capacity_mks(15.0, fy_ksc, fc_ksc, b_cm, d_cm)
    cases.append({
        "case_id": "EV-BEAM-001",
        "module": "modules/beam.py :: _flex_ksc",
        "category": "beam flexure",
        "description": "Flexural capacity of a singly-reinforced, "
                       "under-reinforced rectangular beam section (MKS).",
        "inputs": {"As_cm2": 15.0, "fy_ksc": fy_ksc, "fc_ksc": fc_ksc,
                   "b_cm": b_cm, "d_cm": d_cm},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.2.7 / 9.3.2",
                           "equation": "a = As fy/(0.85 f'c b); "
                                       "Mn = As fy (d - a/2); phi from eps_t"},
        "expected": {"a_cm": r["a_cm"], "Mn_kgfm": r["Mn_kgfm"],
                     "phiMn_kgfm": r["phiMn_kgfm_engine"]},
        "intermediate": r,
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-6,
                      "rationale": "closed-form; only float dust expected. "
                      "phi = 0.90 is valid here (eps_t = %.4f >> 0.005)."
                      % r["eps_t"]},
        "notes": "_flex_ksc returns phi*Mn with a HARDCODED phi = 0.90 "
                 "(phi['flexure']); it performs no internal tension-"
                 "controlled check. Valid only while the caller enforces "
                 "rho <= rho_max. See EV-BEAM-002 note (VF-11).",
        "status": "REFERENCE_READY",
    })

    # BEAM-FLEX-002  higher rho, still tension-controlled (guarded domain)
    r2 = R_FLEX.singly_reinforced_capacity_mks(22.0, fy_ksc, fc_ksc, b_cm, d_cm)
    cases.append({
        "case_id": "EV-BEAM-002",
        "module": "modules/beam.py :: _flex_ksc",
        "category": "beam flexure",
        "description": "Higher reinforcement ratio, still tension-controlled "
                       "(eps_t just above 0.005).",
        "inputs": {"As_cm2": 22.0, "fy_ksc": fy_ksc, "fc_ksc": fc_ksc,
                   "b_cm": b_cm, "d_cm": d_cm},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.2.7 / 9.3.2"},
        "expected": {"a_cm": r2["a_cm"], "Mn_kgfm": r2["Mn_kgfm"],
                     "phiMn_kgfm": r2["phiMn_kgfm_engine"]},
        "intermediate": dict(r2, **{
            "VF11": "If As is pushed further (e.g. 30 cm2 here -> eps_t = "
                    "0.0040 < 0.005), the true phi drops to ~0.82 but "
                    "_flex_ksc still returns 0.90*Mn, overstating phi*Mn by "
                    "~10%. The engine relies on the separate _rho_max_ksc "
                    "check in _render_beam_section to catch this. RECORD."}),
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-6,
                      "rationale": "eps_t = %.4f >= 0.005 so phi = 0.90 "
                      "still correct; closed form." % r2["eps_t"]},
        "notes": "",
        "status": "REFERENCE_READY",
    })

    # BEAM-FLEX-003  minimum-steel boundary via _required_as (SI)
    # Choose a small Mu so As_req is near As_min.
    fc_mpa = fc_ksc * KSC_TO_MPA
    fy_mpa = fy_ksc * KSC_TO_MPA
    b_mm, d_mm = b_cm * 10.0, d_cm * 10.0
    Mu_kNm = 60.0
    As, Rn, rho, feas = R_FLEX.required_As_singly_reinforced(
        Mu_kNm * 1.0e6, 0.90, b_mm, d_mm, fc_mpa, fy_mpa)
    as_min = R_ACI.rho_min_flexure_si(fc_mpa, fy_mpa) * b_mm * d_mm
    cases.append({
        "case_id": "EV-BEAM-003",
        "module": "modules/beam.py :: _required_as (+ calc_As_min)",
        "category": "beam flexure / minimum steel",
        "description": "Required tension steel for a light factored moment, "
                       "compared with As_min (ACI 10.5.1).",
        "inputs": {"Mu_kNm": Mu_kNm, "b_mm": b_mm, "d_mm": d_mm,
                   "fc_MPa": fc_mpa, "fy_MPa": fy_mpa, "phi": 0.90},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.2 / 10.5.1"},
        "expected": {"As_req_mm2": As, "Rn_MPa": Rn, "rho": rho,
                     "feasible": feas, "As_min_mm2": as_min,
                     "governing_As_mm2": max(As, as_min)},
        "intermediate": {
            "note": "As_req (%.1f) %s As_min (%.1f); the governing design "
                    "steel is max(As_req, As_min)."
                    % (As, "<" if As < as_min else ">=", as_min)},
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-6,
                      "rationale": "closed-form quadratic inversion"},
        "notes": "",
        "status": "REFERENCE_READY",
    })

    # BEAM-SHEAR-001  concrete-dominant (Vu < phiVc)
    fc_mpa = fc_ksc * KSC_TO_MPA
    fyt_mpa = fy_ksc * KSC_TO_MPA
    Av = 2.0 * 63.62      # RB9 two-leg, mm^2 (nominal 63.62 per REBAR table)
    sc = R_SHEAR.beam_shear_capacity_si(60_000.0, b_cm * 10.0, d_cm * 10.0,
                                        fc_mpa, fyt_mpa, Av, 200.0)
    cases.append({
        "case_id": "EV-BEAM-004",
        "module": "modules/beam.py :: _shear_check",
        "category": "beam shear",
        "description": "One-way shear where the concrete alone governs "
                       "(Vu below phi*Vc).",
        "inputs": {"Vu_kN": 60.0, "b_mm": b_cm * 10.0, "d_mm": d_cm * 10.0,
                   "fc_MPa": fc_mpa, "fyt_MPa": fyt_mpa,
                   "stirrup": "RB9 (Av = 2 x 63.62 mm2)", "s_mm": 200.0},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08",
                           "section": "11.2.1.1 / 11.4.7 / 11.4.5"},
        "expected": sc,
        "intermediate": {"phiVc_kN": sc["phiVc_N"] / 1000.0,
                         "phiVn_kN": sc["phiVn_N"] / 1000.0},
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-3,
                      "rationale": "closed form; abs in N"},
        "notes": "Verdict is Pass-Fail: reference predicts ok = True.",
        "status": "REFERENCE_READY",
    })

    # BEAM-SHEAR-002  stirrups required (phiVc < Vu < phiVn)
    sc2 = R_SHEAR.beam_shear_capacity_si(160_000.0, b_cm * 10.0, d_cm * 10.0,
                                         fc_mpa, fyt_mpa, Av, 150.0)
    cases.append({
        "case_id": "EV-BEAM-005",
        "module": "modules/beam.py :: _shear_check",
        "category": "beam shear",
        "description": "Shear demand needs stirrups; check phi*Vs, phi*Vn "
                       "and the verdict.",
        "inputs": {"Vu_kN": 160.0, "b_mm": b_cm * 10.0, "d_mm": d_cm * 10.0,
                   "fc_MPa": fc_mpa, "fyt_MPa": fyt_mpa,
                   "stirrup": "RB9 (Av = 2 x 63.62 mm2)", "s_mm": 150.0},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "11.4.7.2"},
        "expected": sc2,
        "intermediate": {"phiVn_kN": sc2["phiVn_N"] / 1000.0},
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-3,
                      "rationale": "closed form"},
        "notes": "",
        "status": "REFERENCE_READY",
    })

    # BEAM-SHEAR-003  s_max transition boundary (Vs vs 0.33 sqrt fc bw d)
    sc3 = R_SHEAR.beam_shear_capacity_si(260_000.0, b_cm * 10.0, d_cm * 10.0,
                                         fc_mpa, fyt_mpa, Av, 90.0)
    thr = 0.33 * math.sqrt(fc_mpa) * (b_cm * 10.0) * (d_cm * 10.0)
    cases.append({
        "case_id": "EV-BEAM-006",
        "module": "modules/beam.py :: _shear_check (s_max branch)",
        "category": "beam shear / discrete",
        "description": "When Vs exceeds 0.33 sqrt(f'c) bw d the maximum "
                       "stirrup spacing halves (d/4, 300 mm).",
        "inputs": {"Vu_kN": 260.0, "s_mm": 90.0, "b_mm": b_cm * 10.0,
                   "d_mm": d_cm * 10.0, "fc_MPa": fc_mpa, "fyt_MPa": fyt_mpa},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "11.4.5.3"},
        "expected": {"Vs_N": sc3["Vs_N"], "threshold_0p33_N": thr,
                     "half_d_rule_triggered": sc3["half_d_rule"],
                     "s_max_mm": sc3["s_max_mm"], "ok": sc3["ok"]},
        "intermediate": sc3,
        "tolerance": {"type": "discrete",
                      "rationale": "the branch flag and s_max are exact; "
                                   "Vs numerical rel 1e-6"},
        "notes": "",
        "status": "REFERENCE_READY",
    })

    _w("beam_flexure_shear.json", cases)


# ===========================================================================
# P0-C  — Column P-M anchors
# ===========================================================================
def build_column():
    cases = []
    fc_ksc, fy_ksc, b_cm, h_cm = 240.0, 4000.0, 40.0, 40.0
    Ab = R_COL.bar_area_cm2("DB20")
    Ag = R_COL.gross_area_rect_cm2(b_cm, h_cm)
    a = R_COL.axial_anchors_mks(fc_ksc, fy_ksc, Ag, 8, Ab, tied=True)

    cases.append({
        "case_id": "EV-COL-001",
        "module": "modules/column.py :: _render_column (Po / phiPn_max) ; "
                  "_calculate_pm_curve (Po, cap end-points)",
        "category": "column axial anchor",
        "description": "Pure-compression nominal strength Po and the tied "
                       "design axial cap phi*Pn,max.",
        "inputs": {"fc_ksc": fc_ksc, "fy_ksc": fy_ksc, "b_cm": b_cm,
                   "h_cm": h_cm, "n_bars": 8, "bar": "DB20",
                   "Ab_cm2": Ab, "Ag_cm2": Ag, "tied": True},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.3.6.1 / "
                           "10.3.6.2", "equation": "Po = 0.85 f'c (Ag-Ast) + "
                           "fy Ast ; phi*Pn,max = 0.80*0.65*Po (tied)"},
        "expected": {"Ast_cm2": a["Ast_cm2"], "Po_kgf": a["Po_kgf"],
                     "phiPn_max_kgf": a["phiPn_max_kgf"]},
        "intermediate": a,
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-3,
                      "rationale": "closed form. DB20 area pi*20^2/4/100 = "
                      "%.5f cm2 (engine uses REBAR table round(...,2) = "
                      "3.14 -> expect a ~1e-3 relative offset in Ast; "
                      "flagged, not slack)." % Ab},
        "notes": "The engine's Ab comes from REBAR['DB20']['area'] = "
                 "round(pi*400/4, 2) = 314.16 mm2; this reference uses the "
                 "unrounded pi*d^2/4. Difference is the rounding only.",
        "status": "REFERENCE_READY",
    })

    cases.append({
        "case_id": "EV-COL-002",
        "module": "modules/column.py :: _calculate_pm_curve (pure-tension "
                  "end-point)",
        "category": "column axial anchor",
        "description": "Pure-tension capacity Pnt = -fy*Ast and its design "
                       "value phi*Pnt (phi = 0.90).",
        "inputs": {"fy_ksc": fy_ksc, "n_bars": 8, "bar": "DB20",
                   "Ab_cm2": Ab},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.3 / 9.3.2"},
        "expected": {"Pnt_kgf": a["Pnt_kgf"], "phiPnt_kgf": a["phiPnt_kgf"]},
        "intermediate": a,
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-3,
                      "rationale": "closed form (bar-area rounding aside)"},
        "notes": "",
        "status": "REFERENCE_READY",
    })

    for cid, ecc in (("EV-COL-003", "low eccentricity"),
                     ("EV-COL-004", "balanced / intermediate eccentricity"),
                     ("EV-COL-005", "point near the design interaction "
                                    "boundary")):
        cases.append({
            "case_id": cid,
            "module": "modules/column.py :: _calculate_pm_curve",
            "category": "column P-M interior",
            "description": "Interaction point at %s." % ecc,
            "inputs": {"fc_ksc": fc_ksc, "fy_ksc": fy_ksc, "b_cm": b_cm,
                       "h_cm": h_cm, "n_bars": 8, "bar": "DB20"},
            "reference_method": "BLOCKED",
            "code_reference": {"code": "ACI 318M-08", "section": "10.2 / 10.3",
                               "equation": "strain compatibility, "
                                           "eps_cu = 0.003, Whitney block"},
            "expected": {"Pn_kgf": "REFERENCE REQUIRED",
                         "Mn_kgfm": "REFERENCE REQUIRED",
                         "phiPn_kgf": "REFERENCE REQUIRED",
                         "phiMn_kgfm": "REFERENCE REQUIRED"},
            "intermediate": {
                "why_blocked": "An interior P-M point needs an independent "
                               "strain-compatibility solver (layer/fibre "
                               "integration). Building one and trusting it "
                               "as a REFERENCE requires its own verification "
                               "(hand-checked balanced point, published "
                               "interaction chart, or a second tool). Per "
                               "the EV-02 brief this is marked BLOCKED "
                               "rather than fabricated. Anchors EV-COL-001/"
                               "002 are delivered; the full curve is EV-03 "
                               "scope."},
            "tolerance": {"type": "engineering", "value": "TBD",
                          "rationale": "no reference yet"},
            "notes": "BLOCKED - not skipped-to-hide; genuinely no "
                     "trustworthy independent value at EV-02.",
            "status": "BLOCKED",
        })

    _w("column_pm.json", cases)


# ===========================================================================
# P0-D / P0-F  — Continuous beam + sampled peak
# ===========================================================================
def build_analysis():
    cases = []
    w = 1000.0

    specs = [
        ("EV-ANLZ-001", [6.0], "single simply-supported span"),
        ("EV-ANLZ-002", [6.0, 6.0], "two equal spans"),
        ("EV-ANLZ-003", [6.0, 4.0], "two unequal spans"),
        ("EV-ANLZ-004", [6.0, 6.0, 6.0], "three equal spans (symmetric)"),
    ]
    for cid, spans, desc in specs:
        ref = R_AN.solve_continuous_beam_reference(spans, w)
        cases.append({
            "case_id": cid,
            "module": "utils/analysis.py :: solve_continuous_beam",
            "category": "continuous-beam analysis",
            "description": "%s, uniform load w on every span." % desc,
            "inputs": {"spans_m": spans, "w_kgf_per_m": w},
            "reference_method": "LEVEL_A",
            "code_reference": {"code": "Structural analysis",
                               "section": "Clapeyron three-moment theorem "
                                          "+ statics",
                               "equation": "M_{i-1}La + 2Mi(La+Lb) + "
                                           "M_{i+1}Lb = -(w La^3/4 + "
                                           "w Lb^3/4)"},
            "expected": {
                "reactions_kgf": ref["reactions_kgf"],
                "support_moments_kgfm": ref["support_moments_kgfm"],
                "Mu_pos_kgfm": ref["Mu_pos_analytic_kgfm"],
                "Mu_neg_kgfm": ref["Mu_neg_analytic_kgfm"],
                "Vu_kgf": ref["Vu_analytic_kgf"],
            },
            "intermediate": {
                "Mu_pos_on_analytic_grid_200pt":
                    ref["Mu_pos_on_grid_kgfm"],
                "method_note": "Three-moment is independent of the engine's "
                               "direct-stiffness Euler-Bernoulli element "
                               "assembly. EI cancels for prismatic members "
                               "on non-settling supports, so reactions and "
                               "internal forces are EI-independent."},
            "tolerance": {
                "type": "numerical",
                "rel": 1e-6, "abs": 1e-3,
                "rationale": "both methods are exact for this problem; the "
                             "only gap on reactions / support moments is "
                             "linear-solver round-off. Governing +Mu is "
                             "compared with a SEPARATE, looser sampled-peak "
                             "tolerance in EV-ANLZ-005 -- here Mu_pos uses "
                             "the analytic peak and may legitimately differ "
                             "from the engine's sampled value; see notes."},
            "notes": "For Mu_pos the engine returns a SAMPLED maximum "
                     "(Finding VF-04). Compare engine Mu_pos against "
                     "intermediate.Mu_pos_on_analytic_grid_200pt, not "
                     "against the analytic peak, when judging solver "
                     "correctness. EV-ANLZ-005 quantifies the sampling gap.",
            "status": "REFERENCE_READY",
        })

    sp = R_AN.sampled_peak_analysis(6.0, w)
    cases.append({
        "case_id": "EV-ANLZ-005",
        "module": "utils/analysis.py :: solve_continuous_beam "
                  "(Mu_pos_kgfm sampling)",
        "category": "numerical method (VF-04)",
        "description": "Effect of fixed-grid sampling on the reported "
                       "governing positive moment, single 6 m span.",
        "inputs": {"span_m": 6.0, "w_kgf_per_m": w, "grid_points": 200},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "Statics",
                           "section": "simply-supported UDL",
                           "equation": "M(x) = w x (L-x)/2 ; peak w L^2/8 "
                                       "at x = L/2"},
        "expected": {
            "M_exact_kgfm": sp["M_exact_kgfm"],
            "M_sampled_grid_peak_kgfm": sp["M_sampled_grid_peak_kgfm"],
            "abs_diff_kgfm": sp["abs_diff_kgfm"],
            "rel_diff": sp["rel_diff"],
        },
        "intermediate": sp,
        "tolerance": {
            "type": "engineering",
            "value": ("engine Mu_pos must match M_sampled_grid_peak within "
                      "rel 1e-4 (confirms the ONLY error source is grid "
                      "sampling, not the solver); and the exact-vs-sampled "
                      "gap must stay within the parabola sampling bound "
                      "(w/2)(h/2)^2 = %.4f kgf-m." % sp["sampling_error_bound_kgfm"]),
            "rationale": "VF-04 is a known non-conservative approximation; "
                         "the acceptance is that it is BOUNDED and "
                         "attributable to sampling, not that it is zero."},
        "notes": "Direction: sampling UNDER-estimates the peak "
                 "(non-conservative) by ~%.2g %%. Recommend EV-03 either "
                 "densify sampling near span interior stationary points or "
                 "evaluate M there analytically. DO NOT change the solver "
                 "in EV-02." % (100.0 * sp["rel_diff"]),
        "status": "REFERENCE_READY",
    })

    _w("continuous_beam.json", cases)


# ===========================================================================
# P0-E  — Slab / Stair / Footing flexure
# ===========================================================================
def build_slab_stair_footing():
    cases = []

    # ---- SLAB-FLEX-001  one-way strip, MKS ----------------------------
    Mu_kgfm, b_cm, d_cm, fc_ksc, fy_ksc = 1200.0, 100.0, 12.0, 240.0, 4000.0
    Rn = (Mu_kgfm * 100.0) / (0.90 * b_cm * d_cm ** 2)
    disc = 1.0 - 2.0 * Rn / (0.85 * fc_ksc)
    rho = (0.85 * fc_ksc / fy_ksc) * (1.0 - math.sqrt(disc))
    As = rho * b_cm * d_cm
    temp_ratio = R_FLEX.as_min_temp_ratio(fy_ksc * KSC_TO_MPA)
    cases.append({
        "case_id": "EV-SLAB-001",
        "module": "modules/slab.py :: _as_flexure_ksc ; _temp_steel_ratio ; "
                  "_spacing_for",
        "category": "slab flexure (one-way)",
        "description": "Required flexural steel for a 1 m one-way slab "
                       "strip, plus shrinkage/temperature minimum and bar "
                       "spacing.",
        "inputs": {"Mu_kgfm_per_m": Mu_kgfm, "b_cm": b_cm, "d_cm": d_cm,
                   "fc_ksc": fc_ksc, "fy_ksc": fy_ksc, "h_cm": 15.0,
                   "bar": "DB10 (Ab = 0.785 cm2)", "s_max_cm": 25.0},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08",
                           "section": "10.2 / 7.12.2.1 / 13.3.2"},
        "expected": {
            "Rn_ksc": Rn, "rho": rho, "As_req_cm2_per_m": As,
            "temp_ratio": temp_ratio,
            "As_min_cm2_per_m": temp_ratio * b_cm * 15.0,
            "spacing_cm": R_FLEX.bar_spacing_for(
                math.pi * 10.0 ** 2 / 4.0 / 100.0, As, 25.0)[0],
        },
        "intermediate": {"disc": disc,
                         "note": "As_min uses total thickness h (15 cm), not "
                                 "d; matches the engine."},
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-6,
                      "rationale": "closed form; spacing rule is discrete "
                                   "(exact)"},
        "notes": "_as_flexure_ksc also hardcodes phi = 0.90 with no TC "
                 "check (same as beam _flex_ksc, VF-11). eps_t here is "
                 "large (light strip) so 0.90 is valid.",
        "status": "REFERENCE_READY",
    })

    # ---- SLAB-FLEX-002  two-way: equation verified, coefficient RR ----
    cases.append({
        "case_id": "EV-SLAB-002",
        "module": "modules/slab.py :: _render_slab_design (two-way "
                  "coefficients) + _as_flexure_ksc",
        "category": "slab flexure (two-way)",
        "description": "Two-way slab design moment. The flexure->As step is "
                       "the same equation as EV-SLAB-001 (verified); the "
                       "MOMENT COEFFICIENT table used by the engine is not "
                       "independently verifiable here.",
        "inputs": {"note": "coefficients read from the engine's two-way "
                           "table for m = Lx/Ly"},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "Ch. 13 / "
                           "moment-coefficient method (edition-specific)",
                           "equation": "CODE REFERENCE TO VERIFY"},
        "expected": {"flexure_equation": "verified via EV-SLAB-001",
                     "moment_coefficients": "REFERENCE REQUIRED"},
        "intermediate": {
            "split": "Equation verified / Coefficient reference required. "
                     "The two-way coefficient source (which table, which "
                     "edition, one-way vs two-way threshold m) must be "
                     "identified before a moment reference can be built. "
                     "Do NOT invent coefficients."},
        "tolerance": {"type": "engineering", "value": "TBD"},
        "notes": "Partial: the As-from-moment mechanics are covered by "
                 "EV-SLAB-001; only the coefficient lookup is unresolved.",
        "status": "REVIEW",
    })

    # ---- STAIR-FLEX-001  _as_flexure_ksc unit ref (LEVEL A) ----------
    Mu_s, b_s, d_s = 1500.0, 100.0, 12.5
    Rn_s = (Mu_s * 100.0) / (0.90 * b_s * d_s ** 2)
    disc_s = 1.0 - 2.0 * Rn_s / (0.85 * fc_ksc)
    rho_s = (0.85 * fc_ksc / fy_ksc) * (1.0 - math.sqrt(disc_s))
    cases.append({
        "case_id": "EV-STAIR-001",
        "module": "modules/stair.py :: _as_flexure_ksc "
                  "(byte-identical to slab._as_flexure_ksc)",
        "category": "stair flexure",
        "description": "Required flexural steel for a straight-stair waist "
                       "strip, given the design moment.",
        "inputs": {"Mu_kgfm_per_m": Mu_s, "b_cm": b_s, "d_cm": d_s,
                   "fc_ksc": fc_ksc, "fy_ksc": fy_ksc},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.2"},
        "expected": {"Rn_ksc": Rn_s, "rho": rho_s,
                     "As_req_cm2_per_m": rho_s * b_s * d_s},
        "intermediate": {"disc": disc_s},
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-6,
                      "rationale": "closed form"},
        "notes": "The stair LOAD build-up (sloped-waist DL = t/100*2400/"
                 "cos(theta), triangular-steps DL = (R/100)/2*2400, "
                 "Wu = 1.2 DL + 1.6 LL, Mu = Wu L^2/8) is computed inside "
                 "_render_straight_stair and is BLOCKED (see EV-STAIR-002). "
                 "VF-06: the straight stair applies the sloped-waist load "
                 "over the horizontal projection L; the U-shape uses a "
                 "conservative max(flight, landing) DL. RECORD.",
        "status": "REFERENCE_READY",
    })
    cases.append({
        "case_id": "EV-STAIR-002",
        "module": "modules/stair.py :: _render_straight_stair / "
                  "_render_u_shape_stair (load build-up)",
        "category": "stair load model",
        "description": "Dead/live/factored load and design moment of the "
                       "stair flight -- assembled inside the render function.",
        "inputs": {"note": "geometry + SDL + LL"},
        "reference_method": "BLOCKED",
        "code_reference": {"code": "ACI 318M-08", "section": "9.2 / statics"},
        "expected": {"Wu_kgf_m2": "REFERENCE REQUIRED",
                     "Mu_kgfm": "REFERENCE REQUIRED"},
        "intermediate": {"why_blocked": "No importable helper; needs a "
                         "compute/render split (out of scope for EV-02). "
                         "The equations are visible in source and a hand "
                         "reference is straightforward -- deferred to EV-03 "
                         "once the split exists.",
                         "VF06": "straight vs U-shape load-model difference "
                                 "documented in EV-STAIR-001 notes."},
        "tolerance": {"type": "engineering", "value": "TBD"},
        "notes": "BLOCKED.",
        "status": "BLOCKED",
    })

    # ---- FOOTING-FLEX-001  _flexure_as unit ref (SI, LEVEL A) --------
    fc_mpa = fc_ksc * KSC_TO_MPA
    fy_mpa = fy_ksc * KSC_TO_MPA
    # width = short_dim, d = d_long ; a representative cantilever moment
    b_mm, d_mm = 2000.0, 480.0
    Mu_Nmm = 120.0e6
    As_f, Rn_f, rho_f, feas_f = R_FLEX.required_As_singly_reinforced(
        Mu_Nmm, 0.90, b_mm, d_mm, fc_mpa, fy_mpa)
    cases.append({
        "case_id": "EV-FOOT-001",
        "module": "modules/footing.py :: _flexure_as",
        "category": "footing flexure",
        "description": "Required flexural steel over a footing strip for a "
                       "given column-face cantilever moment (SI).",
        "inputs": {"Mu_Nmm": Mu_Nmm, "b_mm": b_mm, "d_mm": d_mm,
                   "fc_MPa": fc_mpa, "fy_MPa": fy_mpa, "phi": 0.90},
        "reference_method": "LEVEL_A",
        "code_reference": {"code": "ACI 318M-08", "section": "10.2 / 15.4"},
        "expected": {"As_req_mm2": As_f, "Rn_MPa": Rn_f, "rho": rho_f,
                     "feasible": feas_f},
        "intermediate": {
            "infeasible_sentinel": "_flexure_as returns As = float('inf'), "
                                   "feasible = False when d<=0 or disc<0 "
                                   "(vs None in beam/slab/stair -- RB-1)."},
        "tolerance": {"type": "numerical", "rel": 1e-6, "abs": 1e-4,
                      "rationale": "closed-form quadratic inversion"},
        "notes": "The full isolated-footing chain (self-weight, net "
                 "pressure qu, Mu = qu*width*Lc^2/2) is inside "
                 "_render_isolated_footing -> BLOCKED (EV-FOOT-003).",
        "status": "REFERENCE_READY",
    })

    # ---- FOOTING-PUNCH-002  circular-pile perimeter finding (VF-09) --
    Dp, d_avg = 300.0, 450.0
    code_p = R_ACI.punching_perimeter_circle_code(Dp, d_avg)
    eng_p = R_ACI.punching_perimeter_circle_engine_literal(Dp, d_avg)
    cases.append({
        "case_id": "EV-FOOT-002",
        "module": "modules/footing.py :: _render_pile_cap "
                  "(bo_pile = 3.464*Dp + pi*d_avg)",
        "category": "punching shear / code-sensitive (VF-09)",
        "description": "Critical shear perimeter for a single CIRCULAR pile "
                       "head. Engine uses a literal 3.464*Dp + pi*d; the "
                       "ACI 11.11.1.2 critical section for a circular "
                       "reaction area at d/2 is pi*(Dp + d).",
        "inputs": {"Dp_mm": Dp, "d_avg_mm": d_avg},
        "reference_method": "LEVEL_C",
        "code_reference": {"code": "ACI 318M-08", "section": "11.11.1.2 / "
                           "R11.11 / 15.5", "equation": "b0 = pi (Dp + d) "
                           "for a circular loaded area; "
                           "CODE REFERENCE TO VERIFY the 3.464 literal"},
        "expected": {"b0_code_pi_Dp_plus_d_mm": code_p,
                     "b0_engine_literal_mm": eng_p,
                     "abs_diff_mm": eng_p - code_p,
                     "rel_diff": (eng_p - code_p) / code_p},
        "intermediate": {
            "3.464": "~= 2*sqrt(3); origin unclear. Possibly a square-ish "
                     "idealisation of the pile with rounded corners "
                     "(pi*d term = 4 quarter-circles). Not equal-area, not "
                     "equal-perimeter to the circle. RECORD as VF-09.",
            "square_column_case_OK": "For a SQUARE column the engine's "
                                     "bo = 4(c + d_avg) is the correct ACI "
                                     "11.11.1.2 perimeter -- only the "
                                     "circular-pile literal is in question."},
        "tolerance": {"type": "engineering", "value": "TBD",
                      "rationale": "documents a code-mapping question; EV-03 "
                                   "to confirm the intended perimeter and "
                                   "quantify the capacity impact."},
        "notes": "RECORD ONLY. Do not change footing.py.",
        "status": "REVIEW",
    })
    cases.append({
        "case_id": "EV-FOOT-003",
        "module": "modules/footing.py :: _render_isolated_footing / "
                  "_render_pile_cap (bearing, one-way & two-way shear, "
                  "flexure chain)",
        "category": "footing full chain",
        "description": "End-to-end isolated-footing / pile-cap checks.",
        "inputs": {"note": "loads + geometry + soil qa"},
        "reference_method": "BLOCKED",
        "code_reference": {"code": "ACI 318M-08", "section": "11.11 / 15.x"},
        "expected": {"q_service": "REFERENCE REQUIRED",
                     "phiVc_punch": "REFERENCE REQUIRED",
                     "phiVc_oneway": "REFERENCE REQUIRED",
                     "As_req": "REFERENCE REQUIRED"},
        "intermediate": {"why_blocked": "computed inside render functions; "
                         "nested _elastic_reactions/_side/_s0 not importable. "
                         "Component equations ARE covered: EV-ACI-006 (two-"
                         "way vc), EV-ACI-005 (one-way vc form), EV-FOOT-001 "
                         "(flexure As). Full assembled numbers need the "
                         "compute/render split."},
        "tolerance": {"type": "engineering", "value": "TBD"},
        "notes": "BLOCKED.",
        "status": "BLOCKED",
    })

    _w("slab_stair_footing.json", cases)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build_aci()
    build_beam()
    build_column()
    build_analysis()
    build_slab_stair_footing()
    print("done.")
