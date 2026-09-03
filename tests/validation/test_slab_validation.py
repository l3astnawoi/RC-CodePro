"""ENGINEERING VALIDATION — slab design (``modules/slab.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_slab_calc.py`` (change detector only).

See ``docs/ENGINEERING_VALIDATION.md`` §4.5, §5 (SLAB matrix), Appendix A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-SLAB-001",
        "Module": "modules/slab.py :: _as_flexure_ksc / _required_as_flexure",
        "Description": "Required flexural steel per 1 m strip for a given "
                       "design moment (MKS and SI paths), plus the Mu<=0 / "
                       "d<=0 -> (0.0, True) and infeasible -> (None, False) "
                       "branches.",
        "Input": "Mu, b(=100 cm / 1000 mm), d, f'c, fy = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (As per strip, feasible flag)",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.2",
        "Tolerance": "Numerical 1e-6 ; branch flags = Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "_as_flexure_ksc is byte-identical to stair._as_flexure_ksc "
                 "— validate once, note the duplication (RB-5).",
    },
    {
        "Case ID": "EV-SLAB-002",
        "Module": "modules/slab.py :: _temp_steel_ratio",
        "Description": "Shrinkage / temperature reinforcement ratio: 0.0020 "
                       "(fy<=300), 0.0018 (fy~350-420), "
                       "max(0.0018*420/fy, 0.0014) above.",
        "Input": "fy (MPa) = REFERENCE REQUIRED (one per branch + boundaries)",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level C — ACI 318M-08 7.12.2.1 (Level A arithmetic)",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Identical implementation in slab / footing / stair (RB-5).",
    },
    {
        "Case ID": "EV-SLAB-003",
        "Module": "modules/slab.py :: _spacing_for",
        "Description": "Bar spacing from required As: S = floor(S_req/2.5)*2.5, "
                       "capped at s_max, floored at 2.5 cm; provided As "
                       "back-calculated from the chosen spacing.",
        "Input": "Ab, As_req, s_max = REFERENCE REQUIRED (incl. As_req = 0 -> "
                 "s_max, and a governing-s_max case)",
        "Expected Result": "REFERENCE REQUIRED (S_cm, As_prov)",
        "Reference": "Level A arithmetic + Level C — ACI 318M-08 13.3.2 / "
                     "7.12.2.2 for the s_max used by the caller",
        "Tolerance": "Numerical 1e-6 ; rounding step = Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "s_max itself is set in _render_slab_design (BLOCKED).",
    },
    {
        "Case ID": "EV-SLAB-004",
        "Module": "modules/slab.py :: _render_slab_design (interleaved)",
        "Description": "One-way / two-way classification (m = Lx/Ly), the "
                       "moment coefficients, the factored self-weight + SDL + "
                       "LL load, and the final spacing verdict.",
        "Input": "BLOCKED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level B independent worksheet + Level C — ACI 318M-08 "
                     "Ch. 13 / moment-coefficient method",
        "Tolerance": "Engineering — TO BE DEFINED DURING EV-02 ; "
                     "classification = Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "BLOCKED",
        "Notes": "Assembled inside the render function (VF-02). Dead "
                 "_render_one_way_slab / _render_two_way_slab are out of scope "
                 "(VF-03).",
    },
]
