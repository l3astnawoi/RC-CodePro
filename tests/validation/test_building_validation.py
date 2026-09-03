"""ENGINEERING VALIDATION — building model (``modules/building.py``).

EV-01 STATUS: PLACEHOLDER — NOT VALIDATED.
Excluded from pytest collection by ``tests/validation/conftest.py``;
does not count against the 73-test regression baseline.

Regression coverage: ``tests/test_building_calc.py`` (change detector only).

The EV brief requires MODEL GENERATION and STRUCTURAL ANALYSIS to be kept
separate.  The Building Model is grid generation + a simplified tributary
gravity take-down + a budget BOQ — it is NOT a structural design check and
its report status reads "MODEL GENERATED", never a design "PASS".

See ``docs/ENGINEERING_VALIDATION.md`` §4.8, §5 (BUILDING matrix), App. A.
"""

import pytest

pytest.skip(
    "EV-01: framework only — no independent reference values yet "
    "(see docs/ENGINEERING_VALIDATION.md)",
    allow_module_level=True,
)

VALIDATION_CASES = [
    {
        "Case ID": "EV-BLDG-001",
        "Module": "modules/building.py :: _parse_spacings / _grid_label_x / "
                  "_column_labels / _panel_items",
        "Description": "MODEL GENERATION — grid string ('4@5, 3') parsed to "
                       "cumulative coordinates; node / column / panel "
                       "enumeration and labelling.",
        "Input": "grid strings + nx, ny = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (coordinate list, label list, "
                           "panel list)",
        "Reference": "Level A — by-hand grid expansion",
        "Tolerance": "Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Pure model bookkeeping — no engineering content.",
    },
    {
        "Case ID": "EV-BLDG-002",
        "Module": "modules/building.py :: _calculate_column_loads",
        "Description": "STRUCTURAL ANALYSIS (simplified) — tributary gravity "
                       "take-down: each solid panel contributes a quarter of "
                       "its area to each of its four corner columns; void "
                       "panels contribute nothing; quarter-areas that would "
                       "land on a removed column are DROPPED (not "
                       "redistributed).",
        "Input": "regular grid, Wu, no removals -> corner / edge / interior "
                 "column Pu ; then a grid with a removed column and a void "
                 "panel = REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (trib_area_m2 and Pu_kgf per "
                           "column; and Sum(Pu) < Wu * solid_area when "
                           "columns are removed)",
        "Reference": "Level A — hand tributary areas for a regular rectangular "
                     "grid + Level B for the removed-column case",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Finding VF-05: dropped quarter-areas make the take-down "
                 "non-conservative for irregular layouts — this is a "
                 "documented simplification, not a bug to fix here. It is NOT "
                 "a frame analysis (no stiffness, no continuity, no lateral).",
    },
    {
        "Case ID": "EV-BLDG-003",
        "Module": "modules/building.py :: _auto_group_columns",
        "Description": "Post-processing — RULE-BASED grouping by load ratio: "
                       ">= 0.75 Pmax -> C1, >= 0.45 -> C2, else C3. "
                       "(The UI labels this 'AI' — Finding ER-03 — but it is "
                       "fixed-threshold clustering.)",
        "Input": "a load dict spanning all three bands + the empty dict = "
                 "REFERENCE REQUIRED",
        "Expected Result": "REFERENCE REQUIRED (mark per grid)",
        "Reference": "Level A — apply the thresholds by hand",
        "Tolerance": "Discrete exact",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "NOT VALIDATED",
        "Notes": "Validate as deterministic thresholding, not 'AI'.",
    },
    {
        "Case ID": "EV-BLDG-004",
        "Module": "modules/building.py :: render_building_model (interleaved)",
        "Description": "Factored slab load "
                       "Wu = 1.2 (t/100 * 2400 + SDL) + 1.6 LL computed inside "
                       "the render function and fed to _calculate_column_loads.",
        "Input": "BLOCKED",
        "Expected Result": "REFERENCE REQUIRED",
        "Reference": "Level A — ACI 318M-08 9.2 load combination arithmetic",
        "Tolerance": "Numerical 1e-6",
        "Actual Result": "NOT RUN",
        "Difference": "NOT RUN",
        "Status": "BLOCKED",
        "Notes": "Finding VF-01 — no importable helper for Wu; needs a "
                 "compute/render split (out of scope for validation).",
    },
]
