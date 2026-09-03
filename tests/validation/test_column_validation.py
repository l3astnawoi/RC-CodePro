"""ENGINEERING VALIDATION — column design (``modules/column.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_column_calc.py`` (change detector only).

See ``docs/ENGINEERING_VALIDATION.md`` §4.4, §5 (COLUMN matrix), Appendix A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-COL-001",
        "Module": "modules/column.py :: _calculate_pm_curve "
                  "(+ _whitney_area_centroid, _beta1_col_ksc, _col_bar_xy)",
        "Description": "Axial-flexural interaction curve (Mn, Pn, phi*Mn, "
                       "phi*Pn) by strain compatibility for a rectangular "
                       "tied column — checked at named anchor points: pure "
                       "compression phi*Pn,max, balanced point, pure bending, "
                       "pure tension.",
        "Input": "b, h, f'c, fy, bar layout, Ab, spiral=False = REFERENCE "
                 "REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (P, M at each anchor + >=2 "
                           "intermediate strain states)",
        "Reference": "Level A hand calc at anchors + Level B independent "
                     "P-M tool for the full curve",
        "Tolerance": "Numerical 1e-6 at closed-form anchors ; Engineering "
                     "(TBD EV-02) for the discretised curve",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Curve is discretised — treat like VF-04: state the "
                 "discretisation error bound explicitly.",
    },
    {
        "Case ID": "EV-COL-002",
        "Module": "modules/column.py :: _point_in_poly",
        "Description": "Design adequacy test — is the factored demand "
                       "(Mu, Pu) inside the phi-reduced interaction polygon.",
        "Input": "polygon vertices + demand points clearly inside / outside / "
                 "on the boundary = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (bool per point)",
        "Reference": "Level A geometry",
        "Tolerance": "Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Include a point on an edge to pin the boundary convention.",
    },
    {
        "Case ID": "EV-COL-003",
        "Module": "modules/column.py :: _col_bar_xy",
        "Description": "Longitudinal-bar centroid coordinates for rectangular "
                       "(perimeter distribution) and circular (even angular "
                       "spacing) columns.",
        "Input": "shape, b, h, D, cover, tie dia, main dia, n = REFERENCE "
                 "REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (list of (x, y))",
        "Reference": "Level A geometry",
        "Tolerance": "Discrete exact (abs 1e-9 on coordinates)",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Circular bars on axis land at ~1e-15, not 0.0 — Finding RB-4.",
    },
    {
        "Case ID": "EV-COL-004",
        "Module": "modules/column.py :: _render_column (interleaved)",
        "Description": "rho_g limits (1%-8%), phi*Pn,max axial cap "
                       "(ALPHA_MAX = 0.80, tied), and tie / spiral spacing "
                       "limits, plus the assembled PASS/FAIL verdict.",
        "Input": "BLOCKED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A hand calc + Level C — ACI 318M-08 10.3.6.2 / "
                     "10.9.1 / 7.10.5",
        "Tolerance": "Numerical 1e-6 ; verdict = Pass-Fail",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "BLOCKED",
        "Notes": "Assembled inside the render function — Finding VF-02. Legacy "
                 "dead P-M helpers (_pm_point/_pm_curve/...) are out of scope "
                 "— Finding VF-03.",
    },
]
