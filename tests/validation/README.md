# `tests/validation/` — Engineering Validation cases (EV framework)

**EV-01: scaffold + stubs (nothing collected by `pytest`).
EV-02: independent reference set built under `reference/` and an
executable runner `run_ev02_validation.py`. Still NOT wired into
`pytest` — `pytest -q` stays exactly 73 passed, 0 skipped.**

This package is **separate** from the golden-value regression suite in
`tests/` and serves a different purpose.

## EV-02 layout

```
tests/validation/
  reference/
    reference_aci.py        beta1, rho_min/max, phi, Vc, two-way vc,
                            tie s_max, column axial anchors  (pure math)
    reference_flexure.py    singly-reinforced Mn / phiMn / As_req,
                            temp-steel ratio, bar spacing     (pure math)
    reference_shear.py      one-way shear Vc / Vs / phiVn / s_max
    reference_analysis.py   continuous beam by the THREE-MOMENT method
                            + single-span sampled-peak analysis (VF-04)
    reference_column.py     P-M axial anchors (Po, cap, Pnt); interior
                            of the curve is BLOCKED, not fabricated
    _build_cases.py         regenerates cases/*.json from the above
    cases/*.json            31 reference cases in the Appendix-B schema
                            (NO `actual_engine_result` — reference only)
  run_ev02_validation.py    loads cases/*.json, calls the LIVE engine for
                            the actual value, prints
                            Case / Expected / Actual / Diff / Tol / Status
```

**Run the EV-02 validation:**

```bash
py -3 tests/validation/run_ev02_validation.py          # full table
py -3 tests/validation/run_ev02_validation.py --brief  # summary only
```

Latest result: **120 checks — 104 PASS, 0 FAIL, 11 REVIEW, 5 BLOCKED**.

**No-circularity rule:** every `reference/*.py` module imports only
`math` / `numpy` — never `utils.*` or `modules.*`. The engine is imported
**only** inside `run_ev02_validation.py`, to obtain the *actual* value.

## The two-suite picture

| | `tests/test_*.py` (regression) | `tests/validation/test_*_validation.py` (this package) |
|---|---|---|
| Question answered | "did the output change?" | "is the output engineering-correct?" |
| Compared against | RC CodePro's own frozen past output | an **independent** reference (hand calc / independent tool / ACI text) |
| Count | **73 tests, must stay 73 passed** | **0** at EV-01 (placeholders excluded from collection) |
| Authority | `docs/REGRESSION_BASELINE.md` | `docs/ENGINEERING_VALIDATION.md` |

## Why nothing runs yet

Per the EV-01 brief, a validation case may **not** be created by comparing
the program to itself. Each case needs an `Expected Result` from an
independent source and that source does not exist yet — every planned case
carries `Reference: REFERENCE REQUIRED` and `Status: NOT VALIDATED`.

To keep the regression baseline at exactly **73 passed, 0 skipped**, the
placeholder modules in this directory are excluded from pytest collection
by `tests/validation/conftest.py` (`collect_ignore_glob`). They are
plain-text design stubs until EV-03 fills in references, tolerances and
expected values and removes the exclusion.

## Files

| File | Covers (see `docs/ENGINEERING_VALIDATION.md` §4–5, Appendix A) |
|---|---|
| `test_aci_318m_validation.py`   | `EV-ACI-001…006` — β₁, ρ_min, ρ_max, φ, Vc, bar areas |
| `test_beam_validation.py`       | `EV-BEAM-001…005` — flexural capacity, required As, shear, section verdict, full flow (BLOCKED) |
| `test_column_validation.py`     | `EV-COL-001…004` — P–M curve, design point, bar geometry, ρg/φPn,max/ties (BLOCKED) |
| `test_slab_validation.py`       | `EV-SLAB-001…004` — flexural As, min steel, spacing, classification/moments (BLOCKED) |
| `test_footing_validation.py`    | `EV-FOOT-001…004` — flexure As, pile layout, min steel, shear/bearing/punching (BLOCKED) |
| `test_stair_validation.py`      | `EV-STAIR-001…003` — flexural As, min steel/spacing, load/moment (BLOCKED) |
| `test_analysis_validation.py`   | `EV-ANLZ-001…002` — continuous-beam solve, governing extrema (VF-04 sampled peak) |
| `test_building_validation.py`   | `EV-BLDG-001…004` — grid parsing, gravity take-down (VF-05), grouping, Wu (BLOCKED) |
| `test_boq_validation.py`        | `EV-BOQ-001` — quantity take-off (VF-08 ratio basis) |

## Validation Case schema

Each planned case is one record (mirrored in the placeholder docstrings):

```
Case ID          EV-<AREA>-<NNN>
Module           source file + function(s) under validation
Description      one-sentence statement of the engineering quantity
Input            complete explicit input set, units stated
Expected Result  the INDEPENDENT reference value(s) — never a program output
Reference        Level A: <hand-calc ref> | Level B: <independent tool + worksheet>
                 | Level C: <ACI clause> | REFERENCE REQUIRED
Tolerance        Numerical 1e-6 | Engineering <justified band, TBD in EV-02>
                 | Discrete exact | Pass-Fail
Actual Result    value RC CodePro returns (filled at execution)
Difference       actual - expected (absolute and relative)
Status           NOT VALIDATED | PASS | FAIL | REVIEW | BLOCKED
Notes            assumptions, links to Findings VF-/RB-/ER-
```

`Status` at EV-01 is `NOT VALIDATED` for every case (or `BLOCKED` where the
quantity is only reachable inside a `render_*` function and needs a
compute/render split that is out of scope for validation work).

## How EV-03 turns a placeholder into a real case

1. Produce the independent reference (worksheet committed alongside).
2. Fill `Expected Result`, `Reference`, `Tolerance`.
3. Replace the stub with an executable `test_*` that calls the **real**
   engine function named in the case and asserts against the reference.
4. Remove that filename from `collect_ignore_glob`.
5. Update the suite total and explain the change in that step's completion
   report (`docs/ENGINEERING_VALIDATION.md` §12).

## Rules (from the EV brief)

- Never copy a golden test here and call it validation.
- Never invent a reference number to make a case PASS.
- If a case FAILs, record it as a Finding — do **not** edit the engine
  inside a validation step (`docs/ENGINEERING_VALIDATION.md` §11).
