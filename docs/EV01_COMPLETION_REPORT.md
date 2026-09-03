# EV-01 — Completion Report

**Task:** establish an Engineering Validation Framework for RC CodePro.
**Mode:** AUDIT + FRAMEWORK ONLY — no engine change, no finding fixed.
**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`

---

## 1. Files created

| Path | Purpose |
|---|---|
| `docs/ENGINEERING_VALIDATION.md` | Master validation plan — 12 sections + Calculation Engine Inventory + Validation Matrix + Reference Case Strategy + Acceptance Criteria + Traceability (Appendix A) + Validation Case schema (Appendix B) |
| `docs/EV01_COMPLETION_REPORT.md` | This report |
| `tests/validation/README.md` | How the validation package differs from the regression suite; the case schema; how EV-03 turns a stub into a real case |
| `tests/validation/conftest.py` | `collect_ignore_glob` — keeps the placeholders out of pytest collection so the 73/0-skipped baseline is untouched |
| `tests/validation/test_aci_318m_validation.py` | Planned cases `EV-ACI-001…006` (schema stubs, `NOT VALIDATED`) |
| `tests/validation/test_beam_validation.py` | Planned cases `EV-BEAM-001…005` |
| `tests/validation/test_column_validation.py` | Planned cases `EV-COL-001…004` |
| `tests/validation/test_slab_validation.py` | Planned cases `EV-SLAB-001…004` |
| `tests/validation/test_footing_validation.py` | Planned cases `EV-FOOT-001…004` |
| `tests/validation/test_stair_validation.py` | Planned cases `EV-STAIR-001…003` |
| `tests/validation/test_analysis_validation.py` | Planned cases `EV-ANLZ-001…002` |
| `tests/validation/test_building_validation.py` | Planned cases `EV-BLDG-001…004` |
| `tests/validation/test_boq_validation.py` | Planned case `EV-BOQ-001` |

**13 files created**, all new, all documentation or non-collected scaffold.

## 2. Files modified

**None.** No pre-existing tracked or untracked file was edited in EV-01.

`git diff --stat HEAD` is byte-for-byte identical to the pre-EV-01
snapshot: `12 files changed, 1447 insertions(+), 804 deletions(-)` — that
diff is the STEP 2–15 UI/report work, unchanged by EV-01.

## 3. Calculation-engine files changed — **NO**

Verified three ways:

1. `git status` — none of `utils/analysis.py`, `utils/aci_318m.py`,
   `utils/boq.py` appears as modified; `modules/*.py` show the **same**
   STEP 2–15 diff as before EV-01 (identical insertion/deletion totals).
2. `git diff HEAD -- utils/analysis.py utils/aci_318m.py utils/boq.py` →
   **empty** (pristine vs baseline).
3. MD5, working tree vs `HEAD` blob:
   - `utils/analysis.py`  `c4dd7cca5d4e68ee567fd8722252bdb1` == `c4dd7cca5d4e68ee567fd8722252bdb1`
   - `utils/aci_318m.py`  `f9f479fa7f0459d51dd5e97846aa413c` == `f9f479fa7f0459d51dd5e97846aa413c`
   - `utils/boq.py`       `c6da98bc86d2c21a6c34b93e69ec50e8` == `c6da98bc86d2c21a6c34b93e69ec50e8`

No formula, constant, unit conversion, condition, return value, function
signature or engineering assumption was touched. No test was edited. No
golden value was edited.

## 4. Framework status

**ESTABLISHED — not yet exercised.**

- The *plan* is complete: every in-scope calculation is inventoried,
  placed in the Validation Matrix, given a reference-level requirement, a
  risk rank and a validation priority, and traced end-to-end
  (requirement → function → regression test → validation case → reference
  → result).
- The *execution* has not started: **0** independent reference values
  exist, so **0** validation cases have been run and **0** PASS. Every
  planned case is `NOT VALIDATED` or `BLOCKED`.
- This is the intended EV-01 end state (brief §8: "EV-01 need not contain
  numerical validation cases if independent reference values do not exist
  yet").

## 5. Calculation functions inventoried

**47 importable pure functions** in scope:

| Area | Count | Functions |
|---|---|---|
| `utils/aci_318m.py` | 15 | `_bar_area`, `bar_area`, `bars_area`, `beta1`, `get_beta1`, `rho_min_flexure`, `as_min_flexure`, `calc_As_min`, `rho_balanced`, `rho_max_flexure`, `phi_flexure`, `rho_min_flexure_ksc`, `as_min_flexure_ksc`, `vc_beam`, `vc_beam_ksc` |
| `utils/analysis.py` | 2 | `_beam_element_k`, `solve_continuous_beam` |
| `modules/beam.py` | 6 | `_beta1_ksc`, `_rho_max_ksc`, `_flex_ksc`, `_required_as`, `_shear_check`, `_section_calc` |
| `modules/column.py` | 5 | `_beta1_col_ksc`, `_col_bar_xy`, `_whitney_area_centroid`, `_calculate_pm_curve`, `_point_in_poly` |
| `modules/slab.py` | 4 | `_temp_steel_ratio`, `_required_as_flexure`, `_as_flexure_ksc`, `_spacing_for` |
| `modules/footing.py` | 3 | `_temp_steel_ratio`, `_flexure_as`, `_pile_coords` |
| `modules/stair.py` | 4 | `_temp_steel_ratio`, `_required_as_flexure`, `_as_flexure_ksc`, `_spacing_for` |
| `modules/building.py` | 6 | `_parse_spacings`, `_grid_label_x`, `_column_labels`, `_panel_items`, `_calculate_column_loads`, `_auto_group_columns` |
| `utils/boq.py` | 2 | `_beam_length_m`, `estimate_building_boq` |

**Excluded** (recorded, not inventoried): 7 dead column P–M helpers
(`_pm_point`, `_pm_curve`, `_cap_M_at_P`, `_Pn_at_ecc`, `_bar_coords`,
`_layers`, `_phi_tied`), the dead slab render pair
(`_render_one_way_slab`, `_render_two_way_slab`), all UI/table/display
helpers (`_fmt_cell`, `_html_table`, `_row`, nested `_s`/`_rb`/…), and all
`utils/drawing.py` `draw_*` and `reports/pdf_generator.py` functions
(presentation layers).

**Additionally tracked:** **8 BLOCKED interleaved `render_*` compute
paths** (see item 10).

## 6. Validation items

- **Validation Matrix rows:** 60 calculation sub-items across 8 areas
  (BEAM 11, COLUMN 7, SLAB 6, FOOTING 10, STAIR 6, ANALYSIS 7,
  BUILDING 6, plus the ACI block feeding them) — Building's MODEL
  GENERATION and STRUCTURAL ANALYSIS rows are split as required.
- **Planned validation cases (Appendix A / schema stubs):** **33**
  (`EV-ACI` 6, `EV-BEAM` 5, `EV-COL` 4, `EV-SLAB` 4, `EV-FOOT` 4,
  `EV-STAIR` 3, `EV-ANLZ` 2, `EV-BLDG` 4, `EV-BOQ` 1).

## 7. Existing regression tests

**73 passed, 0 failed, 0 skipped** — before and after EV-01.

```
py -3 -m pytest -q   →   73 passed in 1.41s
```

Unchanged from the baseline. The `tests/validation/` placeholders are
excluded from collection, so the count did not move.

## 8. Validation cases PASS

**0.** No independent reference values exist yet, so no case has been
executed. (Brief §12: a case is never marked PASS by comparing the
program to its own output.)

## 9. Cases NOT VALIDATED

**27** of the 33 planned cases — reachable functions that are
regression-pinned only and awaiting an independent (Level A / B / C)
reference.

Effectively **all 47 inventoried functions** are `NOT VALIDATED`:
regression coverage is 45/47 direct + 2 indirect (`_bar_area`,
`_beam_element_k`), and independent engineering validation coverage is
**0/47**.

## 10. Cases BLOCKED

**6** planned cases (`EV-BEAM-005`, `EV-COL-004`, `EV-SLAB-004`,
`EV-FOOT-004`, `EV-STAIR-003`, `EV-BLDG-004`) covering **8 interleaved
compute paths** whose assembled numbers cannot be reached without a
compute/render split (out of scope for a validation step):

`_render_beam_section`, `_render_beam_3_sect`, `_render_column`,
`_render_slab_design`, `_render_isolated_footing`, `_render_pile_cap`
(+ nested `_elastic_reactions` / `_side` / `_s0`), `_render_straight_stair`,
`_render_u_shape_stair`, and the `Wu` load calculation inside
`render_building_model`.

Recorded as Findings **VF-01** (Wu in render) and **VF-02** (column /
footing / stair verdict assembly in render).

## 11. Engineering Review items mapped

All six `docs/ENGINEERING_REVIEW.md` items classified into the framework
(Section 9.1), plus the seven `docs/REGRESSION_BASELINE.md` review items
(RB-1…RB-7, Section 9.2) and eight new EV-01 observations (VF-01…VF-08,
Section 9.3). **None fixed.**

| ID | Classification | Feeds validation as |
|---|---|---|
| ER-01 | UI Issue / Documentation Issue | report-layer conversion — reconcile vs engine `As_req`/`As_min`, not a case |
| ER-02 | Documentation Issue | confirms Building = model + take-down + BOQ, not analysis |
| ER-03 | Documentation Issue | `_auto_group_columns` validated as rule-based, not "AI" |
| ER-04 | Numerical Method → **Validation Required** | `EV-ANLZ-002` / VF-04 — sampled peak, explicit sampling-error tolerance |
| ER-05 | UI Issue | drawing geometry out of scope |
| ER-06 | Documentation Issue | not a validation item |
| RB-1 | Engineering Assumption (API) | infeasible sentinel `None` vs `inf` — validate each signals infeasible |
| RB-2 | Numerical Method (harmless) | single-span `Mu_neg = -0.0` — check `== 0.0` downstream |
| RB-3 | Numerical Method → **Validation Required** | same as VF-04 |
| RB-4 | Numerical Method (harmless) | `_col_bar_xy("circ")` ~1e-15 — abs 1e-9 tolerance |
| RB-5 | Scope Limitation (maintenance) | duplicated helpers — validate once per implementation |
| RB-6 | Engineering Assumption | `_pile_coords` spacing convention — document, don't fix |
| RB-7 | Engineering Assumption → **Validation Required (Level C)** | dual β₁ threshold 28 MPa vs 280 ksc — quantify effect |
| VF-01 | Scope Limitation | `Wu` computed in `render_building_model` — BLOCKED |
| VF-02 | Scope Limitation | column/footing/stair verdicts in `render_*` — BLOCKED |
| VF-03 | Scope Limitation (dead code) | legacy column P–M set + dead slab renders — not validated, not deleted |
| VF-04 | Numerical Method → **Validation Required** | sampled `Mu_pos` in `solve_continuous_beam` |
| VF-05 | Engineering Assumption | `_calculate_column_loads` drops quarter-areas on removed columns (non-conservative) |
| VF-06 | Engineering Assumption | stair uses conservative single DL over the whole span |
| VF-07 | Engineering Assumption → **Validation Required (Level C)** | same dual β₁ threshold as RB-7 |
| VF-08 | Engineering Assumption | `estimate_building_boq` rebar ratios 150/120/90 kg/m³ — no cited source |

Risk ranked CRITICAL / HIGH / MEDIUM / LOW and prioritised P0 / P1 / P2 in
`docs/ENGINEERING_VALIDATION.md` §11.

## 12. Recommended EV-02 scope

**EV-02 = produce the P0 independent references and define the tolerances
that EV-01 left as "TO BE DEFINED".** Do **not** change the engine.

1. **P0 Level-A hand checks** (one worksheet per case, committed under
   `tests/validation/`):
   - `EV-ACI-001…005` — β₁, ρ_min, ρ_max, φ(εt), Vc (SI + MKS).
   - `EV-BEAM-001…003` — `_flex_ksc` φMn, `_required_as`, `_shear_check`
     for a worked tension-controlled section.
   - `EV-SLAB-001` / `EV-STAIR-001` — `_as_flexure_ksc` for a worked strip.
   - `EV-FOOT-001` — `_flexure_as` at a column face.
   - `EV-ANLZ-001` — continuous-beam reactions (1 / 2 / 3 spans) from
     classical formulae; `EV-ANLZ-002` — analytic `wL²/8` **with the
     stated sampling-error bound** (resolves VF-04 / ER-04 / RB-3).
   - `EV-COL-002` / `EV-COL-003` — `_point_in_poly`, `_col_bar_xy` geometry.
   - `EV-BLDG-002` — tributary areas for a regular grid, **plus** the
     removed-column case that exposes VF-05.
2. **P0 Level-C code checks:** dual β₁ threshold (VF-07 / RB-7) — quantify
   the ≈0.54 MPa / ≈2 ksc offset's effect on φMn and ρ_max; two-way `vc`
   three-expression minimum and `α_s`; tie-spacing limits.
3. **P0 Level-B references** (independent tool + saved worksheet):
   `EV-COL-001` full P–M curve; `EV-ANLZ` multi-span `M(x)`/`V(x)`.
4. **Define the "Engineering" tolerance band** per case (EV-01 §7 leaves
   it "TO BE DEFINED") — justified from each reference's own method.
5. **Turn P0 stubs into executable cases:** replace the skipped
   placeholder with a `test_*` that calls the real engine function and
   asserts against the reference; remove that file from
   `collect_ignore_glob`; update the suite total and explain the change.
6. **Defer to EV-03+:** the 6 BLOCKED cases (need a compute/render split,
   which is a separate authorised refactor step, not validation);
   `estimate_building_boq` ratio basis (VF-08); `_pile_coords` convention
   documentation (RB-6); the dead-code decision (VF-03); all P1/P2 items.

---

## Regression & integrity check — final

| Check | Result |
|---|---|
| `py -3 -m pytest -q` | **73 passed, 0 skipped** |
| `git diff HEAD -- utils/analysis.py utils/aci_318m.py utils/boq.py` | empty (pristine) |
| `git diff --stat HEAD` totals vs pre-EV-01 snapshot | identical (`1447 (+) / 804 (−)`) |
| Calculation-engine file modified in EV-01 | **NO** |
| Engineering Review item fixed in EV-01 | **NO** (all recorded as Findings) |
| Test file edited / golden value edited | **NO** |
| Destructive git command used | **NO** |

**EV-01 is complete. EV-02 is not started.**
