"""ENGINEERING VALIDATION — footing & pile-cap design (``modules/footing.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_footing_calc.py`` (change detector only).

See ``docs/ENGINEERING_VALIDATION.md`` §4.6, §5 (FOOTING matrix), Appendix A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-FOOT-001",
        "Module": "modules/footing.py :: _flexure_as",
        "Description": "Required flexural steel at the column face for a "
                       "footing strip, and the infeasible signal "
                       "As = float('inf'), feasible = False when d <= 0 or the "
                       "section cannot develop Mu.",
        "Input": "Mu_Nmm, b_mm, d_mm, f'c, fy = REFERENCE REQUIRED "
                 "(one feasible, one infeasible, one zero-depth)",
        "Expected Result": "REFERENCE REQUIRED (As_req, Rn, rho, feasible)",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.2 / 15.4",
        "Tolerance": "Numerical 1e-6 ; infeasible = Discrete exact (inf)",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Infeasible sentinel is 'inf' here vs 'None' in beam/slab/"
                 "stair — Finding RB-1.",
    },
    {
        "Case ID": "EV-FOOT-002",
        "Module": "modules/footing.py :: _pile_coords",
        "Description": "Pile-centre coordinates for groups n = 1..9 at "
                       "spacing S, including the convention change (n = 2..5 "
                       "at +/-S/2, n = 6..9 at +/-S).",
        "Input": "n in 1..9, S = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (list of (x, y) per n)",
        "Reference": "Level A geometry + standard pile-group layouts",
        "Tolerance": "Discrete exact (abs 1e-9)",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Document the spacing-convention change — Finding RB-6.",
    },
    {
        "Case ID": "EV-FOOT-003",
        "Module": "modules/footing.py :: _temp_steel_ratio",
        "Description": "Minimum reinforcement ratio (ACI 7.12.2.1). "
                       "Byte-identical to slab / stair implementation.",
        "Input": "fy (MPa) = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level C — ACI 318M-08 7.12.2.1",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Shared reference with EV-SLAB-002 / EV-STAIR-002 (RB-5).",
    },
    {
        "Case ID": "EV-FOOT-004",
        "Module": "modules/footing.py :: _render_isolated_footing / "
                  "_render_pile_cap (+ nested _elastic_reactions, _side, _s0)",
        "Description": "Soil bearing pressure vs qa; two-way (punching) shear "
                       "min(vc1, vc2, vc3) with alpha_s = 40; one-way shear "
                       "0.17 lambda sqrt(f'c) b d; pile-head punching "
                       "0.33 lambda sqrt(f'c) bo d; elastic pile-reaction "
                       "distribution; flexure at the column face.",
        "Input": "BLOCKED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A hand calc + Level B independent worksheet + "
                     "Level C — ACI 318M-08 11.11.2.1 / 15.5 / 15.4",
        "Tolerance": "Numerical 1e-6 for closed forms ; verdicts = Pass-Fail",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "BLOCKED",
        "Notes": "Punching / one-way shear / bearing are computed only inside "
                 "the render functions; _elastic_reactions / _side / _s0 are "
                 "nested and not importable — Finding VF-02. HIGH PRIORITY "
                 "(P0): footing shear is a safety-governing check with zero "
                 "current test coverage.",
    },
]
