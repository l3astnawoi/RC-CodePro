# RC CodePro — Engineering Regression Baseline

**Date:** 2026-09-02
**Step:** 2A — Regression Harness / Golden-Value Tests
**Suite:** `tests/` · run with `pytest` (config in `pytest.ini`)

---

## Purpose

Before any UI refactoring (STEP 3 onward) touches code where calculation
logic and Streamlit widgets are interleaved, this suite pins the **current
numeric behaviour** of every calculation function that can be called
directly. It is a *change detector*: if a later edit alters a formula, a
constant, a unit conversion or a rounding path, a test fails.

---

## Current calculation implementation covered

| Area | Module | Functions locked |
|---|---|---|
| ACI 318M-08 core | `utils/aci_318m.py` | `beta1`, `get_beta1`, `rho_min_flexure`, `as_min_flexure`, `rho_balanced`, `rho_max_flexure`, `phi_flexure`, `calc_As_min`, `vc_beam`, `rho_min_flexure_ksc`, `as_min_flexure_ksc`, `vc_beam_ksc`, `bar_area`, `bars_area`, `PHI`, `phi`, strain constants |
| Continuous beam analysis | `utils/analysis.py` | `solve_continuous_beam` — reactions, support coords, `L_total`, `Mu_pos_kgfm`, `Mu_neg_kgfm`, `Vu_kgf`, sampled `x/V/M`, equilibrium, `ValueError` on empty/all-non-positive spans |
| BOQ take-off | `utils/boq.py` | `estimate_building_boq` (columns / beams / slab / total / ratios / table), `_beam_length_m` |
| Building model | `modules/building.py` | `_parse_spacings`, `_grid_label_x`, `_column_labels`, `_panel_items`, `_calculate_column_loads`, `_auto_group_columns` |
| Beam design | `modules/beam.py` | `_beta1_ksc`, `_rho_max_ksc`, `_flex_ksc`, `_required_as`, `_shear_check`, `_section_calc` |
| Column P-M | `modules/column.py` | `_beta1_col_ksc`, `_col_bar_xy`, `_whitney_area_centroid`, `_calculate_pm_curve` (anchor + mid-curve points), `_point_in_poly` |
| Slab design | `modules/slab.py` | `_temp_steel_ratio`, `_as_flexure_ksc`, `_spacing_for`, `_required_as_flexure` |
| Footing design | `modules/footing.py` | `_temp_steel_ratio`, `_flexure_as`, `_pile_coords` |
| Stair design | `modules/stair.py` | `_temp_steel_ratio`, `_required_as_flexure`, `_as_flexure_ksc`, `_spacing_for` |

**Total: 73 tests, all passing.**

Per file: `test_aci_318m.py` 19 · `test_analysis.py` 6 · `test_beam_calc.py` 7 ·
`test_boq.py` 4 · `test_building_calc.py` 11 · `test_column_calc.py` 9 ·
`test_footing_calc.py` 5 · `test_slab_calc.py` 7 · `test_stair_calc.py` 5.

---

## Golden values

Every expected number in the suite was obtained by:

1. importing the **real** function from this repository,
2. calling it with representative / boundary / alternative / invalid inputs,
3. recording the returned value at full `repr()` precision,
4. pasting that value into the test as the expected constant.

Comparison tolerance: `pytest.approx(value, rel=1e-9, abs=1e-9)`
(`tests/_helpers.py`). `abs=1e-9` only absorbs values that are legitimately
zero (e.g. a signed `-0.0` or ~1e-15 floating dust); it does **not** widen
tolerance enough to hide a formula change.

> **Golden values represent CURRENT SOFTWARE BEHAVIOUR.
> They are NOT an independent engineering validation.**

---

## Blocked tests (could not be unit-tested without refactoring)

Refactoring is **out of scope** for this step, so these were left alone and
recorded here rather than forced.

| Location | Why blocked |
|---|---|
| `modules/footing.py` — `_elastic_reactions`, `_side`, `_s0` | Declared as **nested functions inside** `_render_isolated_footing` / `_render_pile_cap`. Not importable; calling the parent executes Streamlit widget code. → *Cannot safely unit-test without extraction.* |
| Full design flows — `_render_beam_section`, `_render_beam_3_sect`, `_render_column`, `_render_slab_design`, `_render_straight_stair`, `_render_u_shape_stair`, `_render_isolated_footing`, `_render_pile_cap`, `render_building_model` | Calculation and `st.*` calls interleaved in one function. Their pure sub-helpers *are* covered above; the end-to-end assembled numbers are not, pending a compute/render split. |
| `modules/column.py` legacy set — `_pm_point`, `_pm_curve`, `_cap_M_at_P`, `_Pn_at_ecc`, `_bar_coords`, `_layers` | Dead code (not called by `_render_column`). Deliberately not pinned — locking unused code adds maintenance without regression value. Left untouched (no deletion). |

---

## Potential engineering review (RECORD ONLY — do not fix in refactor steps)

These are observations from capturing current behaviour. They are **not**
bugs to fix here; they need an engineer's decision.

1. **Inconsistent "infeasible" sentinel.** `beam._required_as`,
   `slab._as_flexure_ksc`, `slab._required_as_flexure`,
   `stair._as_flexure_ksc`, `stair._required_as_flexure` return
   `As = None` when the section is too shallow; `footing._flexure_as`
   returns `As = float("inf")`. Callers must handle both forms.
2. **`solve_continuous_beam` single simply-supported span** returns
   `Mu_neg_kgfm = -0.0` (signed zero from `max(-M.min(), 0.0)`).
3. **`solve_continuous_beam` positive moment is a sampled value.**
   e.g. one span `wL²/8` exact = 9000, solver returns 8999.7727
   (≈0.0025 % low) because the fixed sampling grid misses exact mid-span.
   Applies to every span's `Mu_pos` / `M_max`.
4. **`_col_bar_xy("circ", …)`** yields ~1e-15 instead of exact 0.0 on
   axis-aligned bars — harmless unless downstream code does `== 0.0`.
5. **Duplicated helpers.** `_temp_steel_ratio` is byte-identical in
   `slab.py`, `footing.py`, `stair.py`; `_as_flexure_ksc` + `_spacing_for`
   identical in `slab.py` & `stair.py`. A future single-source
   consolidation must be behaviour-neutral (this suite will confirm).
6. **`_pile_coords` spacing convention changes with count.** n = 2..5 put
   piles at `±S/2` (group ≈ S wide); n = 6..9 put piles at `±S`
   (group ≈ 2S wide) for the same input `S`.
7. **Two `beta1` transition thresholds.** SI `aci_318m.beta1` breaks at
   28 MPa; MKS `beam._beta1_ksc` / `column._beta1_col_ksc` break at
   280 ksc (≈ 27.46 MPa). Expected given unit systems, flagged for
   consistency review.

---

## Refactoring rule

Before modifying any calculation function:

1. `pytest` — confirm green baseline.
2. Make the change.
3. `pytest` — run again.
4. Compare results.
5. **Investigate every regression.** A failing golden-value test means the
   output moved — find out why.
6. **Never edit a golden value merely to make a test pass.**

A golden value may be **intentionally** updated only when **all** of:

- the engineering change is reviewed and approved,
- the new expected behaviour is documented (here + in the PR),
- old vs new result is recorded side by side.

---

## What this baseline does NOT cover

- UI rendering, layout, CSS, navigation, widgets, callbacks.
- PDF report content / layout (`reports/pdf_generator.py`).
- Drawing geometry (`utils/drawing.py` `draw_*`).
- The interleaved compute paths inside `render_*` functions (see *Blocked*).
- Independent correctness vs. ACI 318M-08 text — this is a *change*
  detector, not a code-compliance checker.
