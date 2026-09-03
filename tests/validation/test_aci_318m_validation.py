"""ENGINEERING VALIDATION — ACI 318M-08 core helpers (``utils/aci_318m.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
No independent reference values exist yet.  This module is excluded from
pytest collection by ``tests/validation/conftest.py`` and does not count
against the 73-test regression baseline.

Regression coverage for these functions already lives in
``tests/test_aci_318m.py`` — that is a CHANGE DETECTOR, not validation
(``docs/REGRESSION_BASELINE.md``).  The cases below must be checked against
an INDEPENDENT reference (hand calc / ACI text), never against the
program's own output.

See ``docs/ENGINEERING_VALIDATION.md`` §4.1, §5 (ACI matrix), Appendix A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

# --- Planned validation cases (schema: docs/ENGINEERING_VALIDATION.md App. B)
VALIDATION_CASES = [
    {
        "Case ID": "EV-ACI-001",
        "Module": "utils/aci_318m.py :: beta1 / get_beta1",
        "Description": "Stress-block factor beta_1 across the ACI 10.2.7.3 "
                       "piecewise definition (<=28 MPa, transition, floor 0.65).",
        "Input": "f'c = REFERENCE REQUIRED (>=3 points incl. 28 MPa break "
                 "and a point in the linear-taper range)",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level C — ACI 318M-08 10.2.7.3 (and Level A arithmetic)",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Cross-check against MKS _beta1_ksc / _beta1_col_ksc — "
                 "Finding VF-07 / RB-7 (28 MPa vs 280 ksc break).",
    },
    {
        "Case ID": "EV-ACI-002",
        "Module": "utils/aci_318m.py :: rho_min_flexure / rho_min_flexure_ksc "
                  "/ as_min_flexure / as_min_flexure_ksc / calc_As_min",
        "Description": "Minimum flexural steel ratio and area, both governing "
                       "branches max(0.25 sqrt f'c / fy, 1.4 / fy) [SI] and "
                       "max(0.8 sqrt f'c / fy, 14 / fy) [MKS].",
        "Input": "f'c, fy, b, d = REFERENCE REQUIRED (one case per governing "
                 "branch, SI and MKS)",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.5.1",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Verify SI<->MKS numerical equivalence of the two forms.",
    },
    {
        "Case ID": "EV-ACI-003",
        "Module": "utils/aci_318m.py :: rho_balanced / rho_max_flexure",
        "Description": "Balanced ratio (ACI 10.3.2) and tension-controlled "
                       "rho_max at eps_t = 0.005 / (c/d = 3/8) (ACI 10.3.4).",
        "Input": "f'c, fy = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.3.2 / 10.3.4",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Pair with beam._rho_max_ksc (EV-BEAM cross-check).",
    },
    {
        "Case ID": "EV-ACI-004",
        "Module": "utils/aci_318m.py :: phi_flexure",
        "Description": "Strength-reduction factor vs net tensile strain: "
                       "compression-controlled floor, linear transition, "
                       "tension-controlled 0.90 — tied and spiral.",
        "Input": "eps_t in {0.001, eps_ty, 0.0035, 0.005, 0.006}, spiral in "
                 "{False, True}",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level C — ACI 318M-08 9.3.2 (Level A interpolation)",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Check both transition endpoints and the spiral floor 0.75.",
    },
    {
        "Case ID": "EV-ACI-005",
        "Module": "utils/aci_318m.py :: vc_beam / vc_beam_ksc",
        "Description": "Concrete one-way shear strength "
                       "Vc = 0.17 lambda sqrt(f'c) bw d [SI] and "
                       "0.53 sqrt(f'c) b d [MKS].",
        "Input": "f'c, bw, d, lambda = REFERENCE REQUIRED (SI and MKS)",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 11.2.1.1",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Confirm 0.53 sqrt(ksc) form equals 0.17 sqrt(MPa) form.",
    },
    {
        "Case ID": "EV-ACI-006",
        "Module": "utils/aci_318m.py :: bar_area / bars_area / _bar_area / REBAR",
        "Description": "Nominal reinforcing-bar areas (pi d^2 / 4) and the "
                       "designation lookup table.",
        "Input": "designations = REFERENCE REQUIRED (e.g. RB6, RB9, DB16, DB20, "
                 "DB25), n = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A geometry + Level C — standard bar schedule",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Table values are data, not a formula — confirm each entry.",
    },
]
