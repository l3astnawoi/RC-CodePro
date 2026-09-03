"""ENGINEERING VALIDATION — stair design (``modules/stair.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_stair_calc.py`` (change detector only).

See ``docs/ENGINEERING_VALIDATION.md`` §4.7, §5 (STAIR matrix), Appendix A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-STAIR-001",
        "Module": "modules/stair.py :: _as_flexure_ksc / _required_as_flexure",
        "Description": "Required flexural steel per unit strip of the stair "
                       "waist slab (MKS and SI paths).",
        "Input": "Mu, b, d, f'c, fy = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (As, feasible)",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.2",
        "Tolerance": "Numerical 1e-6 ; branch flags = Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Byte-identical to slab._as_flexure_ksc / "
                 "slab._required_as_flexure — shared reference (RB-5).",
    },
    {
        "Case ID": "EV-STAIR-002",
        "Module": "modules/stair.py :: _temp_steel_ratio / _spacing_for",
        "Description": "Shrinkage / temperature ratio (ACI 7.12.2.1) and bar "
                       "spacing (floor to 2.5 cm step, capped at s_max).",
        "Input": "fy (MPa) ; Ab, As_req, s_max = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level C — ACI 318M-08 7.12.2.1 / 7.12.2.2 "
                     "(Level A arithmetic)",
        "Tolerance": "Numerical 1e-6 ; rounding step = Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Both helpers byte-identical to the slab versions (RB-5).",
    },
    {
        "Case ID": "EV-STAIR-003",
        "Module": "modules/stair.py :: _render_straight_stair / "
                  "_render_u_shape_stair (interleaved)",
        "Description": "Dead load of the sloped waist "
                       "(t/100 * 2400 / cos(theta)) plus triangular steps "
                       "((R/100)/2 * 2400) plus SDL; factored "
                       "Wu = 1.2 DL + 1.6 LL; design moment Mu = Wu L^2 / 8; "
                       "for U-shape the conservative max(flight, landing) DL.",
        "Input": "BLOCKED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A hand calc (statics + geometry)",
        "Tolerance": "Numerical 1e-6 ; verdict = Pass-Fail",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "BLOCKED",
        "Notes": "Load build-up and Mu are computed inside the render "
                 "functions — Finding VF-02 / VF-06. The reference must mirror "
                 "the conservative single-DL-over-whole-span assumption.",
    },
]
