"""ENGINEERING VALIDATION — beam design (``modules/beam.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_beam_calc.py`` (change detector only).
Cases below need an INDEPENDENT reference (hand calc / independent tool).

See ``docs/ENGINEERING_VALIDATION.md`` §4.3, §5 (BEAM matrix), Appendix A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-BEAM-001",
        "Module": "modules/beam.py :: _flex_ksc (+ _beta1_ksc)",
        "Description": "Flexural capacity phi*Mn of a singly-reinforced "
                       "rectangular section via the Whitney stress block "
                       "(a = As fy / (0.85 f'c b), Mn = As fy (d - a/2)).",
        "Input": "As, fy, f'c, b, d = REFERENCE REQUIRED (tension-controlled "
                 "case; MKS units cm / ksc / kgf.m)",
        "Expected Result": "REFERENCE REQUIRED (a, Mn, phi*Mn)",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.2 / 10.3.4",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "phi fixed at 0.90 in _flex_ksc — case must stay "
                 "tension-controlled or the comparison is invalid.",
    },
    {
        "Case ID": "EV-BEAM-002",
        "Module": "modules/beam.py :: _required_as",
        "Description": "Required tension steel for a factored moment "
                       "(SI, singly reinforced) and correct infeasible "
                       "signalling (As=None, feasible=False) when the section "
                       "cannot develop Mu.",
        "Input": "Mu_kNm, b, d, f'c, fy = REFERENCE REQUIRED (one feasible, "
                 "one deliberately infeasible)",
        "Expected Result": "REFERENCE REQUIRED (As, Rn, rho, feasible)",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.2",
        "Tolerance": "Numerical 1e-6 ; infeasible = Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Infeasible sentinel differs across modules — Finding RB-1.",
    },
    {
        "Case ID": "EV-BEAM-003",
        "Module": "modules/beam.py :: _shear_check (+ aci_318m.vc_beam)",
        "Description": "One-way shear: phi*Vc, phi*Vs = phi Av fy d / s, "
                       "Vs_max = 0.66 sqrt(f'c) b d, and the stirrup s_max "
                       "spacing limits.",
        "Input": "Vu, b, d, f'c, fyv, stirrup size, s = REFERENCE REQUIRED "
                 "(one case needing stirrups, one where phi*Vc governs, one "
                 "exceeding Vs_max)",
        "Expected Result": "REFERENCE REQUIRED (Vc, Vs, Vs_max, phi*Vn, s_max, "
                           "ok flags)",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 11.2 / 11.4",
        "Tolerance": "Numerical 1e-6 ; ok flags = Pass-Fail",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Av = 2 * bar_area assumes a two-leg stirrup.",
    },
    {
        "Case ID": "EV-BEAM-004",
        "Module": "modules/beam.py :: _section_calc",
        "Description": "One critical section end to end: top (-Mu) and bottom "
                       "(+Mu) flexure plus shear, and the assembled ok flags.",
        "Input": "section dict + b, h, cover, f'c, fy = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A hand calc + Level B independent worksheet",
        "Tolerance": "Numerical 1e-6 ; verdict = Pass-Fail",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Combines EV-BEAM-001..003; reuse their references.",
    },
    {
        "Case ID": "EV-BEAM-005",
        "Module": "modules/beam.py :: _render_beam_section / _render_beam_3_sect",
        "Description": "Full member design flow (load combination assembly -> "
                       "3 critical sections -> governing bars + stirrups).",
        "Input": "BLOCKED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level B independent worksheet",
        "Tolerance": "Engineering — TO BE DEFINED DURING EV-02",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "BLOCKED",
        "Notes": "Numbers are assembled inside the Streamlit render function; "
                 "needs a compute/render split (out of scope for validation). "
                 "Finding VF-02.",
    },
]
