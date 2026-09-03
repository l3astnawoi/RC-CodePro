"""ENGINEERING VALIDATION — continuous-beam solver (``utils/analysis.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_analysis.py`` (change detector only).

See ``docs/ENGINEERING_VALIDATION.md`` §4.2, §5 (ANALYSIS matrix), Appendix A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-ANLZ-001",
        "Module": "utils/analysis.py :: solve_continuous_beam / _beam_element_k",
        "Description": "Euler-Bernoulli matrix-stiffness solution of a "
                       "multi-span continuous beam on simple supports under a "
                       "uniform load: support reactions and the V(x) / M(x) "
                       "diagrams.",
        "Input": "spans_m, w_kgf_per_m = REFERENCE REQUIRED "
                 "(1 span; 2 equal spans; 3 spans incl. an unequal set)",
        "Expected Result": "REFERENCE REQUIRED — closed-form reactions "
                           "(e.g. 2 equal spans L, w: end 3wL/8, centre "
                           "10wL/8) and interior support / midspan moments",
        "Reference": "Level A statics + classical continuous-beam formulae + "
                     "Level B independent frame analysis for the diagrams",
        "Tolerance": "Numerical 1e-6 for reactions ; Engineering (TBD EV-02) "
                     "for sampled diagram ordinates",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "EI = 1 and equal EI per span — reactions are EI-independent "
                 "for prismatic members, so the hand check is exact.",
    },
    {
        "Case ID": "EV-ANLZ-002",
        "Module": "utils/analysis.py :: solve_continuous_beam "
                  "(Mu_pos_kgfm / Mu_neg_kgfm / Vu_kgf)",
        "Description": "Governing design actions extracted as extrema of the "
                       "SAMPLED M(x) / V(x) arrays (n_points grid), vs the "
                       "ANALYTIC peaks.",
        "Input": "single simply-supported span L, w — analytic +Mu = w L^2 / 8",
        "Expected Result": "REFERENCE REQUIRED — analytic w L^2 / 8, "
                           "0 hogging, w L / 2 shear",
        "Reference": "Level A statics ; Level B for multi-span peak locations",
        "Tolerance": "Explicit sampling-error bound = w L^2 / 8 * "
                     "(pi^2 / (2 (n_points - 1)^2)) approx — state per case, "
                     "NOT a blanket loosened band",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Finding VF-04 / ER-04 / RB-3: the returned +Mu is slightly "
                 "below the true peak because the maximum falls between "
                 "sample points (observed ~0.0025% low for w L^2/8 = 9000). "
                 "Also RB-2: single-span Mu_neg returns signed -0.0.",
    },
]
