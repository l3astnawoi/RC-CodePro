"""ENGINEERING VALIDATION — quantity take-off (``utils/boq.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_boq.py`` (change detector only).

``estimate_building_boq`` is a BUDGET-STAGE estimator, not a design output.
It is validated for internal consistency of the take-off arithmetic and
for the stated basis of its rebar ratios — NOT as a structural quantity.

See ``docs/ENGINEERING_VALIDATION.md`` §4.9, §5 (BUILDING/BOQ row), App. A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-BOQ-001",
        "Module": "utils/boq.py :: estimate_building_boq / _beam_length_m",
        "Description": "Concrete (m^3), formwork (m^2) and rebar (kg) take-off "
                       "for columns, beams and slab of a small hand-modelled "
                       "grid, plus the grand total; beam length counts shared "
                       "grid-line edges once; web depth = beam_h - slab_t.",
        "Input": "a 2x2-bay grid, storey height, section sizes (cm), "
                 "rebar ratios 150 / 120 / 90 kg/m^3 = REFERENCE REQUIRED; "
                 "also the removed-column + void-panel variant and the empty "
                 "grid",
        "Expected Result": "REFERENCE REQUIRED — hand take-off volumes / areas "
                           "/ masses",
        "Reference": "Level A — hand quantity take-off ; Level C — cite the "
                     "source / basis for the 150 / 120 / 90 kg/m^3 ratios or "
                     "record them as an explicit engineering assumption",
        "Tolerance": "Numerical 1e-6 for the geometry-driven volumes/areas ; "
                     "rebar mass inherits the (assumed) ratio",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Finding VF-08 — the rebar ratios have no cited source. "
                 "This case validates the take-off ARITHMETIC and the ratio "
                 "BASIS statement, not the structural adequacy of any member.",
    },
]
