# RC CodePro — Engineering Validation Framework

**Framework revision:** EV-01
**Date:** 2026-09-02
**Status:** framework established · **no validation cases executed yet**
**Regression baseline at time of writing:** `pytest -q` → **73 passed**

> **This document is a plan, not a result.**
> EV-01 sets up *how* RC CodePro's calculation engine will be independently
> validated. It does **not** validate anything and it does **not** change
> any calculation. Every numeric acceptance value is deliberately left as
> `REFERENCE REQUIRED` — to be supplied from an independent source in
> EV-02 onward.

---

## 1. Purpose

RC CodePro produces reinforced-concrete design results (capacities,
required steel, PASS/FAIL verdicts, governing forces, quantity take-offs)
that an engineer may rely on for real design decisions. Before that
reliance is appropriate, every calculation in the engine must be checked
against an **independent** reference — a hand calculation, an independent
tool/spreadsheet, or the ACI 318M-08 code text — and **not** merely
against the program's own past output.

This framework:

1. Enumerates every calculation function in the engine (Section 4).
2. Maps each calculation to its requirement, its regression test, its
   validation case, and its reference (Sections 5, 9).
3. Defines the reference-case strategy (Section 6), acceptance criteria
   (Section 7) and the validation-case schema (Section 7 / the
   `tests/validation/` package).
4. Records what is validated today (Section 8: **nothing**), the open
   findings that feed validation (Section 9), what is not yet in scope
   (Section 10), and the change-control / regression rules (Sections
   11–12).

---

## 2. Scope

**In scope (the "calculation engine"):**

| File | Role |
|---|---|
| `utils/aci_318m.py` | ACI 318M-08 material constants + flexure/shear helper functions (SI and MKS) |
| `utils/analysis.py` | 1-D continuous-beam matrix-stiffness solver |
| `utils/boq.py` | building-frame quantity take-off (concrete / formwork / rebar) |
| `modules/beam.py` | beam flexure + shear design helpers |
| `modules/column.py` | column axial + P–M interaction helpers |
| `modules/slab.py` | one-way / two-way slab flexure + spacing helpers |
| `modules/footing.py` | isolated footing + pile-cap design helpers |
| `modules/stair.py` | RC stair (straight + U-shape) design helpers |
| `modules/building.py` | grid parsing + tributary gravity load take-down + rule-based grouping |

**Out of scope for this framework:**

- UI / layout / CSS / navigation / widgets / `st.*` callbacks.
- PDF report content & layout — `reports/pdf_generator.py`
  (presentation layer; consumes engine values, see ER-01).
- Drawing geometry — `utils/drawing.py` `draw_*` (presentation layer).
- `utils/project.py` (project-state plumbing, no engineering maths).
- The **interleaved compute paths inside `render_*` functions** — their
  *importable sub-helpers* are in scope; the assembled end-to-end numbers
  inside `_render_beam_section`, `_render_column`, `_render_slab_design`,
  `_render_isolated_footing`, `_render_pile_cap`, `_render_straight_stair`,
  `_render_u_shape_stair`, `render_building_model` are **BLOCKED** pending a
  compute/render split (Section 10).

---

## 3. Validation Philosophy

1. **Regression ≠ validation.** The existing `tests/` suite (73 golden
   tests) freezes *current software behaviour*. It answers *"did the
   output move?"*, never *"is the output engineering-correct?"*.
   `docs/REGRESSION_BASELINE.md` states this explicitly.
2. **Validation is against an independent reference.** A validation case
   PASSes only when the program output matches a value obtained
   **without running RC CodePro** — a Level-A hand check, a Level-B
   independent tool, or a Level-C code-text derivation (Section 6).
3. **No fabricated references.** If a reference value is not yet available
   it is recorded as `REFERENCE REQUIRED`. A validation case is never
   marked PASS by comparing the program to itself.
4. **Findings are recorded, not fixed.** Anything discovered that looks
   like an engineering problem is added to Section 9 (and, if it is a
   genuine engineering concern, to `docs/ENGINEERING_REVIEW.md`) — it is
   **not** repaired inside a validation step.
5. **The engine is frozen during validation.** No formula, constant,
   unit conversion, condition, return value or engineering assumption may
   change while validation work is in progress. Any required engineering
   change is a separate, reviewed, documented step with its own before/
   after golden-value diff (Section 11).
6. **Traceability end-to-end.** Requirement → function → regression test →
   validation case → reference → result (Section 9).

---

## 4. Calculation Engine Inventory

Function names are taken verbatim from the source. "Regression test"
lists the file/tests in `tests/` that currently pin the function.
"Validation" is the EV status — at EV-01 every entry is **NOT VALIDATED**
(regression only, no independent reference).

### 4.1 `utils/aci_318m.py` — ACI 318M-08 core (SI unless noted)

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_bar_area(diameter_mm)` | nominal round-bar area `π d²/4` | d | area | mm² | indirect (via `bar_area`) | NOT VALIDATED | LOW |
| `bar_area(designation)` | nominal area for `"DB20"` etc. from `REBAR` table | bar name | area | mm² | `test_aci_318m::test_bar_area` | NOT VALIDATED | MEDIUM (table values) |
| `bars_area(designation, n)` | `n · bar_area` | name, count | area | mm² | `test_aci_318m::test_bars_area` | NOT VALIDATED | LOW |
| `beta1(fc)` | stress-block factor β₁ — ACI 10.2.7.3 | f'c | β₁ | — (MPa in) | `test_aci_318m::test_beta1_representative`, `test_beta1_boundary` | NOT VALIDATED | HIGH |
| `get_beta1(fc)` | alias → `beta1` | f'c | β₁ | — | `test_beta1_representative` | NOT VALIDATED | HIGH |
| `rho_min_flexure(fc, fy)` | ρ_min = max(0.25√f'c/fy, 1.4/fy) — ACI 10.5.1 | f'c, fy | ratio | — (MPa) | `test_aci_318m::test_rho_min_flexure` | NOT VALIDATED | HIGH |
| `as_min_flexure(fc, fy, b, d)` | ρ_min·b·d | f'c, fy, b, d | area | mm² (MPa/mm) | `test_aci_318m::test_as_min_flexure` | NOT VALIDATED | HIGH |
| `calc_As_min(fc, fy, b, d)` | alias → `as_min_flexure` | — | area | mm² | `test_aci_318m::test_calc_As_min` | NOT VALIDATED | HIGH |
| `rho_balanced(fc, fy)` | balanced ρ — ACI 10.3.2 | f'c, fy | ratio | — | `test_aci_318m::test_rho_balanced` | NOT VALIDATED | MEDIUM |
| `rho_max_flexure(fc, fy)` | tension-controlled ρ_max (εt = 0.005, c/d = 3/8) — ACI 10.3.4 | f'c, fy | ratio | — | `test_aci_318m::test_rho_max_flexure` | NOT VALIDATED | HIGH |
| `phi_flexure(epsilon_t, spiral=False)` | strain-based φ with transition — ACI 9.3.2 | εt, spiral flag | φ | — | `test_aci_318m::test_phi_flexure_*` (×4) | NOT VALIDATED | HIGH |
| `rho_min_flexure_ksc(fc_ksc, fy_ksc)` | MKS ρ_min = max(0.8√f'c/fy, 14/fy) | f'c, fy | ratio | — (ksc) | `test_aci_318m::test_rho_min_flexure_ksc` | NOT VALIDATED | HIGH |
| `as_min_flexure_ksc(fc_ksc, fy_ksc, b_cm, d_cm)` | MKS ρ_min·b·d | f'c, fy, b, d | area | cm² (ksc/cm) | `test_aci_318m::test_as_min_flexure_ksc` | NOT VALIDATED | HIGH |
| `vc_beam(fc, bw, d, lam=1.0)` | concrete one-way shear `0.17λ√f'c·bw·d` — ACI 11.2.1.1 | f'c, bw, d, λ | Vc | N (MPa/mm) | `test_aci_318m::test_vc_beam` | NOT VALIDATED | HIGH |
| `vc_beam_ksc(fc_ksc, b_cm, d_cm)` | MKS `0.53√f'c·b·d` | f'c, b, d | Vc | kgf (ksc/cm) | `test_aci_318m::test_vc_beam_ksc` | NOT VALIDATED | HIGH |
| constants `EPSILON_CU`, `ES`, `EPSILON_TY`, `EPSILON_TENSION_CONTROLLED`, `PHI_*`, `PHI`, `phi`, `REBAR`, `rebars` | ACI material / φ / bar data | — | — | — | referenced by tests above | NOT VALIDATED | HIGH |

### 4.2 `utils/analysis.py` — continuous-beam solver

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_beam_element_k(L)` | 4×4 Euler–Bernoulli element stiffness (EI = 1) | span L | 4×4 matrix | consistent (EI = 1) | indirect | NOT VALIDATED | HIGH |
| `solve_continuous_beam(spans_m, w_kgf_per_m, n_points=80)` | assemble K/F, BC `v = 0` at supports, solve free DOFs, reactions `R = (K d − F)[fixed]`, integrate `V(x)` / `M(x)`; governing `Mu_pos` = `max(M.max, 0)`, `Mu_neg` = `max(−M.min, 0)`, `Vu` = `max(|V|)` | span list, udl w | dict: `reactions_kgf`, `x_supports_m`, `L_total_m`, `x`/`V`/`M`, `Mu_pos_kgfm`, `Mu_neg_kgfm`, `Vu_kgf` | m, kgf/m, kgf, kgf·m | `test_analysis` (×6): 2/3/1-span golden reactions + Mu_pos/Mu_neg/Vu, empty→`ValueError`, all-non-positive→`ValueError`, non-positive filtered | NOT VALIDATED | CRITICAL |

### 4.3 `modules/beam.py` — beam design helpers (importable, pure)

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_beta1_ksc(fc_ksc)` | MKS β₁ (transition at 280 ksc) | f'c | β₁ | — (ksc) | `test_beam_calc::test_beta1_ksc` | NOT VALIDATED | HIGH |
| `_rho_max_ksc(fc_ksc, fy_ksc)` | MKS tension-controlled ρ_max | f'c, fy | ratio | — (ksc) | `test_beam_calc::test_rho_max_ksc` | NOT VALIDATED | HIGH |
| `_flex_ksc(As_cm2, fy_ksc, fc_ksc, b_cm, d_cm)` | Whitney block: `a = As·fy/(0.85 f'c b)`, `Mn = As·fy·(d − a/2)`, `φMn = 0.9 Mn` | As, fy, f'c, b, d | (a, Mn, φMn) | cm, kgf·m, kgf·m | `test_beam_calc::test_flex_ksc` | NOT VALIDATED | CRITICAL |
| `_required_as(Mu_kNm, b, d, fc, fy)` | SI singly-reinforced required As; returns `As = None`, `feasible = False` when `1 − 2Rn/(0.85 f'c) < 0` | Mu, b, d, f'c, fy | (As, Rn, ρ, feasible) | mm², MPa | `test_beam_calc::test_required_as_feasible` / `_infeasible` | NOT VALIDATED | CRITICAL |
| `_shear_check(Vu_kN, b, d, fc, fy, stirrup_size, s_mm)` | `Vc = vc_beam`, `Av = 2·bar_area`, `Vs = Av·fy·d/s`, `Vs_max = 0.66√f'c·b·d`, `φVn = 0.75(Vc + Vs)`, spacing limits | Vu, b, d, f'c, fyv, stirrup, s | dict (Vc/Vs/Vs_max/φVn, s_max, ok flags) | N, mm | `test_beam_calc::test_shear_check` | NOT VALIDATED | CRITICAL |
| `_section_calc(sec_in, b, h, covering, fc, fy)` | one section: top(−Mu)/bottom(+Mu) flexure + shear, assembled ok flags | section dict + geometry | per-section results dict | mm², N, N·mm | `test_beam_calc::test_section_calc` (1 golden) | NOT VALIDATED | CRITICAL |
| `render_beam_module`, `_render_design_sidecard`, `_render_beam_analysis`, `_render_beam_section`, `_render_beam_3_sect`, `_load_input`, nested `_s`/`_rb`/`_r_top`/`_r_bot`/`_r_shear`/`_ratio` | UI + interleaved assembly | — | — | — | — | **BLOCKED** (interleaved / nested / UI) | — |

### 4.4 `modules/column.py` — column P–M helpers (importable, pure)

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_beta1_col_ksc(fc_ksc)` | MKS β₁ | f'c | β₁ | — (ksc) | `test_column_calc::test_beta1_col_ksc` | NOT VALIDATED | HIGH |
| `_col_bar_xy(shape, b, h, D, cov, tie_dia, main_dia, n)` | main-bar centroid coordinates (rect perimeter / circle) | shape + geometry + n | list of (x, y) | mm | `test_column_calc::test_col_bar_xy_rect` / `_circ` | NOT VALIDATED | MEDIUM |
| `_whitney_area_centroid(shape, a, b, D, H)` | compressed-concrete area + centroid for stress-block depth `a` | shape, a, b, D, H | (area, y_centroid) | mm², mm | `test_column_calc::test_whitney_area_centroid_*` (×4) | NOT VALIDATED | HIGH |
| `_calculate_pm_curve(*, shape, b, h, D, fc, fy, bars, Ab, spiral, npts=…)` | strain-compatibility P–M interaction curve | section, materials, bar layout, spiral flag | `Mn`, `Pn`, `phiMn`, `phiPn` arrays | N·mm, N | `test_column_calc::test_calculate_pm_curve_rect_anchor_points` (anchor + mid-curve), `test_point_in_poly` | NOT VALIDATED | CRITICAL |
| `_point_in_poly(px, py, xs, ys)` | is `(Mu, Pu)` inside the design curve | point, polygon | bool | — | `test_column_calc::test_point_in_poly` | NOT VALIDATED | HIGH |
| `_render_column` (interleaved) | ρg, `φPn,max` (axial cap `ALPHA_MAX = 0.80`), tie/spiral spacing, P–M verdict assembly | — | — | — | — | **BLOCKED** (interleaved) | CRITICAL |
| legacy `_phi_tied`, `_bar_coords`, `_layers`, `_pm_point`, `_pm_curve`, `_cap_M_at_P`, `_Pn_at_ecc` | **dead code** — not called by `_render_column` | — | — | — | none (deliberately not pinned) | NOT IN SCOPE (dead) | — |

### 4.5 `modules/slab.py` — slab helpers (importable, pure)

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_temp_steel_ratio(fy)` | shrinkage/temperature ρ — ACI 7.12.2.1 (`0.0020` / `0.0018` / `max(0.0018·420/fy, 0.0014)`) | fy (MPa) | ratio | — | `test_slab_calc::test_temp_steel_ratio` (+ boundary) | NOT VALIDATED | HIGH |
| `_required_as_flexure(Mu_kNm, b, d, fc, fy)` | SI singly-reinforced required As; `None`/`False` when infeasible | Mu, b, d, f'c, fy | (As, Rn, ρ, feasible) | mm², MPa | `test_slab_calc::test_required_as_flexure` | NOT VALIDATED | CRITICAL |
| `_as_flexure_ksc(Mu_kgfm, b_cm, d_cm, fc_ksc, fy_ksc)` | MKS required As per strip; `(0.0, True)` when Mu ≤ 0 or d ≤ 0; `(None, False)` when infeasible | Mu, b, d, f'c, fy | (As_cm2, feasible) | cm², ksc | `test_slab_calc::test_as_flexure_ksc_*` (×3) | NOT VALIDATED | CRITICAL |
| `_spacing_for(As_bar_cm2, As_req_cm2, s_max_cm)` | bar spacing `⌊S_req/2.5⌋·2.5`, capped `s_max`, floored 2.5; provided As back-calculated | Ab, As_req, s_max | (S_cm, As_prov) | cm, cm² | `test_slab_calc::test_spacing_for` / `_zero_requirement_uses_s_max` | NOT VALIDATED | HIGH |
| `_render_slab_design` (interleaved) | m = Lx/Ly one/two-way classification, moment coefficients, self-weight `t/100·2400`, `_temp_steel_ratio(fy·KSC_TO_MPA)`, spacing verdict | — | — | — | — | **BLOCKED** (interleaved) | CRITICAL |
| `_render_two_way_slab`, `_render_one_way_slab`, nested `_s` | **dead code** (superseded by `_render_slab_design`; ≈460 lines) | — | — | — | none | NOT IN SCOPE (dead) | — |

### 4.6 `modules/footing.py` — footing helpers (importable, pure)

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_temp_steel_ratio(fy)` | ACI 7.12.2.1 (byte-identical to `slab._temp_steel_ratio`) | fy (MPa) | ratio | — | `test_footing_calc::test_temp_steel_ratio` | NOT VALIDATED | HIGH |
| `_flexure_as(Mu_Nmm, b_mm, d_mm, fc, fy)` | SI required As; returns `As = float("inf")`, `feasible = False` when `d ≤ 0` or `1 − 2Rn/(0.85 f'c) < 0` | Mu, b, d, f'c, fy | (As_req, Rn, ρ, feasible) | mm², MPa | `test_footing_calc::test_flexure_as_*` (×3: feasible / infeasible→`inf` / zero-depth→`inf`) | NOT VALIDATED | CRITICAL |
| `_pile_coords(n, S)` | pile-centre coordinates for a group of `n` (1–9) piles at spacing `S` | n, S | list of (x, y) | mm | `test_footing_calc::test_pile_coords_layouts` (n = 1,2,3,4,7,9) | NOT VALIDATED | MEDIUM |
| `_render_isolated_footing` (interleaved) | bearing pressure vs qa; two-way (punching) shear `min(vc1, vc2, vc3)` with `ALPHA_S = 40`; one-way shear `0.17λ√f'c·b·d`; flexure at column face; min steel; spacing `min(3h, 450)` | — | — | — | — | **BLOCKED** (interleaved) | CRITICAL |
| `_render_pile_cap` (interleaved) + nested `_elastic_reactions`, `_side`, `_s0` | elastic pile-reaction distribution, punching (column + pile head), one-way shear, flexure per axis | — | — | — | — | **BLOCKED** (nested / interleaved) | CRITICAL |

### 4.7 `modules/stair.py` — stair helpers (importable, pure)

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_temp_steel_ratio(fy)` | ACI 7.12.2.1 (byte-identical to slab / footing) | fy (MPa) | ratio | — | `test_stair_calc::test_temp_steel_ratio` | NOT VALIDATED | HIGH |
| `_required_as_flexure(Mu_kNm, b, d, fc, fy)` | SI required As (byte-identical to `slab._required_as_flexure`) | Mu, b, d, f'c, fy | (As, Rn, ρ, feasible) | mm², MPa | `test_stair_calc::test_required_as_flexure` | NOT VALIDATED | CRITICAL |
| `_as_flexure_ksc(Mu_kgfm, b_cm, d_cm, fc_ksc, fy_ksc)` | MKS required As (byte-identical to `slab._as_flexure_ksc`) | Mu, b, d, f'c, fy | (As_cm2, feasible) | cm², ksc | `test_stair_calc::test_as_flexure_ksc` / `_zero_moment` | NOT VALIDATED | CRITICAL |
| `_spacing_for(Ab_cm2, As_req_cm2, s_max_cm)` | bar spacing (byte-identical to `slab._spacing_for`) | Ab, As_req, s_max | (S, As_prov) | cm, cm² | `test_stair_calc::test_spacing_for` | NOT VALIDATED | HIGH |
| `_render_straight_stair` (interleaved) | sloped-waist DL `t/100·2400/cosθ` + triangular-steps DL `(R/100)/2·2400` + SDL; `Wu = 1.2 DL + 1.6 LL`; `Mu = Wu·Lx²/8`; flexure via `_as_flexure_ksc`; `_temp_steel_ratio(fy·KSC_TO_MPA)`; spacing verdict | — | — | — | — | **BLOCKED** (interleaved) | HIGH |
| `_render_u_shape_stair` (interleaved) | flight + landing DL, conservative `max_DL`, `Mu = Wu·L²/8`, `_required_as_flexure`, spacing verdict | — | — | — | — | **BLOCKED** (interleaved) | HIGH |

### 4.8 `modules/building.py` — model generation + gravity take-down

**Model generation and structural analysis are separated per the EV-01 brief.**

| Function | Purpose | Layer | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|---|
| `_parse_spacings(text, fallback)` | grid string → cumulative absolute coords | model generation | text, fallback list | (coords, spacings) | m | `test_building_calc::test_parse_spacings_*` (×4) | NOT VALIDATED | LOW |
| `_grid_label_x(i)` | 0→"A" … 26→"AA" | model generation | index | label | — | `test_building_calc::test_grid_label_x` | NOT VALIDATED | LOW |
| `_column_labels(nx, ny)` | row-major node labels | model generation | nx, ny | list | — | `test_building_calc::test_column_labels` | NOT VALIDATED | LOW |
| `_panel_items(nx, ny)` | `(label, (i, j))` per panel | model generation | nx, ny | list | — | `test_building_calc::test_panel_items` | NOT VALIDATED | LOW |
| `_calculate_column_loads(x_coords, y_coords, active_columns, void_panels, wu_kgf_m2, col_labels=None)` | **gravity load take-down (tributary area)**: each solid panel gives ¼ area to each corner node; voids contribute nothing; ¼-areas on removed columns are dropped | **structural analysis** (simplified) | grid, active cols, voids, Wu | `{(x, y): {grid, trib_area_m2, Pu_kgf}}` | m², kgf | `test_building_calc::test_column_loads_full_grid` / `_removed_and_void` | NOT VALIDATED | HIGH |
| `_auto_group_columns(column_loads)` | **rule-based** grouping: ratio ≥ 0.75 → C1, ≥ 0.45 → C2, else C3 | post-processing | load dict | `{grid: mark}` | — | `test_building_calc::test_auto_group_columns` / `_empty` | NOT VALIDATED | MEDIUM |
| `render_building_model` (interleaved) | factored slab load `Wu = 1.2·(t/100·2400 + SDL) + 1.6·LL` computed inside the render function | structural analysis input | — | — | — | — | **BLOCKED** (interleaved) | HIGH |
| `_fmt_cell`, `_html_table` | table formatting | UI / display | — | — | — | — | NOT IN SCOPE (UI) | — |

### 4.9 `utils/boq.py` — quantity take-off

| Function | Purpose | Inputs | Outputs | Units | Regression test | Validation | Eng. risk |
|---|---|---|---|---|---|---|---|
| `_beam_length_m(x_coords, y_coords, void_panels)` | total beam length on grid lines bounding solid panels (shared edges counted once) | grid, voids | length | m | `test_boq::test_beam_length_helper` | NOT VALIDATED | LOW |
| `estimate_building_boq(active_columns, void_panels, x_coords, y_coords, floor_height_m, col_b, col_h, beam_b, beam_h, slab_t, *, rebar_ratio_col=150, rebar_ratio_beam=120, rebar_ratio_slab=90)` | concrete (m³) / formwork (m²) / rebar (kg) for columns, beams, slab + grand total, using budget-stage rebar ratios | grid, sections (cm), storey height (m), ratios | dict (`columns`/`beams`/`slab`/`total`/`table`/`ratios`) | m³, m², kg | `test_boq` (×4: full solid, removed+void, `_beam_length_m`, empty grid) | NOT VALIDATED | MEDIUM (budget-stage estimator, not a design output) |
| `_row(name, part)` | table row formatting | — | — | — | — | NOT IN SCOPE (display) | — |
| constants `REBAR_RATIO_COLUMN` = 150, `REBAR_RATIO_BEAM` = 120, `REBAR_RATIO_SLAB` = 90 (kg/m³) | budget rebar ratios | — | — | — | — | NOT VALIDATED — **Level C: state basis / source** | MEDIUM |

**Inventoried calculation functions (in scope): 47**
(15 ACI + 2 analysis + 6 beam + 5 column *(+7 dead, excluded)* + 4 slab
*(+dead render pair, excluded)* + 3 footing + 4 stair + 6 building + 2 BOQ
= 47 — counting importable pure functions only; the interleaved `render_*`
compute paths are additionally tracked as **8 BLOCKED items**.)

---

## 5. Validation Matrix

Legend — **Existing Test:** ✔ pinned in `tests/`, ✘ none.
**Independent Validation:** always **NONE** at EV-01. **Status:** always
**NOT VALIDATED** at EV-01 (or **BLOCKED** where noted).

### BEAM

| Calculation | Function(s) | Reference Required (level) | Existing Test | Independent Validation | Status |
|---|---|---|---|---|---|
| Load / factored moment & shear input | *(from `_render_beam_analysis` / analysis solver)* | A + B | ✔ (`test_analysis`) | NONE | NOT VALIDATED |
| Flexural capacity `φMn` | `_flex_ksc`, `_beta1_ksc` | A + C (ACI 10.2, 10.3.4) | ✔ | NONE | NOT VALIDATED |
| Required reinforcement `As_req` | `_required_as` (SI) | A + C (ACI 10.2) | ✔ | NONE | NOT VALIDATED |
| Minimum reinforcement `As_min` | `aci_318m.as_min_flexure` / `as_min_flexure_ksc` / `rho_min_flexure*` | A + C (ACI 10.5.1) | ✔ | NONE | NOT VALIDATED |
| Maximum reinforcement `ρ_max` | `_rho_max_ksc`, `aci_318m.rho_max_flexure` | A + C (ACI 10.3.4) | ✔ | NONE | NOT VALIDATED |
| Shear concrete capacity `Vc` | `aci_318m.vc_beam` / `vc_beam_ksc` | A + C (ACI 11.2.1.1) | ✔ | NONE | NOT VALIDATED |
| Shear reinforcement `Vs`, `Vs,max`, `φVn` | `_shear_check` | A + C (ACI 11.4.7) | ✔ | NONE | NOT VALIDATED |
| Stirrup spacing `s_max` | `_shear_check` (s_max branch) | C (ACI 11.4.5) | ✔ | NONE | NOT VALIDATED |
| Assembled section verdict (top/bottom/shear ok) | `_section_calc` | A + B | ✔ (1 golden) | NONE | NOT VALIDATED |
| Full design flow (`_render_beam_section` / `_render_beam_3_sect`) | interleaved | B | ✘ | NONE | **BLOCKED** |
| Deflection / serviceability | — | *not implemented* | — | — | N/A (no implementation) |

### COLUMN

| Calculation | Function(s) | Reference Required (level) | Existing Test | Independent Validation | Status |
|---|---|---|---|---|---|
| Reinforcement ratio `ρg` (1–8 %) | `_render_column` (`RHO_MIN` = 0.01, `RHO_MAX` = 0.08) | A + C (ACI 10.9.1) | ✘ | NONE | **BLOCKED** |
| Maximum axial limit `φPn,max` | `_render_column` (`ALPHA_MAX` = 0.80, tied) | A + C (ACI 10.3.6.2) | ✘ | NONE | **BLOCKED** |
| P–M interaction curve `(φMn, φPn)` | `_calculate_pm_curve`, `_whitney_area_centroid`, `_beta1_col_ksc` | A (anchor points) + B | ✔ (anchor + mid points) | NONE | NOT VALIDATED |
| Design-point check `(Mu, Pu)` inside curve | `_point_in_poly` | A | ✔ | NONE | NOT VALIDATED |
| Bar arrangement / geometry | `_col_bar_xy` | A | ✔ | NONE | NOT VALIDATED |
| Tie / spiral spacing | `_render_column` (`16·db`, `48·d_tie`, least dim / spiral pitch) | C (ACI 7.10.5 / 10.9.3) | ✘ | NONE | **BLOCKED** |
| Slenderness / P-Δ | — | *not implemented* | — | — | N/A (no implementation) |

### SLAB

| Calculation | Function(s) | Reference Required (level) | Existing Test | Independent Validation | Status |
|---|---|---|---|---|---|
| Load (self-weight + SDL + LL, factored) | `_render_slab_design` (`t/100·2400`; `Wu = 1.2 DL + 1.6 LL`) | A | ✘ | NONE | **BLOCKED** |
| One-way / two-way classification | `_render_slab_design` (`m = Lx/Ly`, threshold 0.5) | C (ACI 13 / 8.3.3 practice) | ✘ | NONE | **BLOCKED** |
| Design moment(s) per 1 m strip | `_render_slab_design` (span-ratio coefficients) | A + B | ✘ | NONE | **BLOCKED** |
| Flexural reinforcement `As` | `_as_flexure_ksc` / `_required_as_flexure` | A + C (ACI 10.2) | ✔ | NONE | NOT VALIDATED |
| Minimum (shrinkage/temp) reinforcement | `_temp_steel_ratio` | A + C (ACI 7.12.2.1) | ✔ | NONE | NOT VALIDATED |
| Bar spacing (provided + `s_max`) | `_spacing_for`; `s_max = min(3t, 45)` / `min(5t, 45)` in render | C (ACI 13.3.2 / 7.12.2.2) | ✔ (`_spacing_for` only) | NONE | NOT VALIDATED (helper) / **BLOCKED** (`s_max`) |

### FOOTING

| Calculation | Function(s) | Reference Required (level) | Existing Test | Independent Validation | Status |
|---|---|---|---|---|---|
| Soil bearing pressure (service) vs `qa` | `_render_isolated_footing` | A | ✘ | NONE | **BLOCKED** |
| Eccentricity / pressure distribution (pile cap) | `_render_pile_cap` → nested `_elastic_reactions` | A + B | ✘ | NONE | **BLOCKED** (nested) |
| Overturning / uplift (pile `Rmin ≥ 0`) | `_render_pile_cap` | A | ✘ | NONE | **BLOCKED** |
| Flexure at column face → `As_req` | `_flexure_as`; render moment arm | A + C (ACI 15.4) | ✔ (`_flexure_as` only) | NONE | NOT VALIDATED (helper) / **BLOCKED** (moment) |
| One-way (beam) shear | `_render_isolated_footing` / `_render_pile_cap` (`0.17λ√f'c·b·d`) | A + C (ACI 11.2 / 15.5) | ✘ | NONE | **BLOCKED** |
| Two-way (punching) shear | `_render_isolated_footing` (`min(vc1, vc2, vc3)`, `ALPHA_S = 40`); `_render_pile_cap` (column + pile-head) | A + C (ACI 11.11.2.1) | ✘ | NONE | **BLOCKED** |
| Minimum reinforcement | `_temp_steel_ratio` | A + C (ACI 7.12) | ✔ | NONE | NOT VALIDATED |
| Bar spacing `s_max = min(3h, 450)` | `_render_isolated_footing` / `_render_pile_cap` | C | ✘ | NONE | **BLOCKED** |
| Pile group layout | `_pile_coords` | A (geometry) | ✔ | NONE | NOT VALIDATED |
| Pile cap punching of a single pile head | `_render_pile_cap` (`0.33λ√f'c·bo,pile·d`) | A + C (ACI 15.5) | ✘ | NONE | **BLOCKED** |

### STAIR

| Calculation | Function(s) | Reference Required (level) | Existing Test | Independent Validation | Status |
|---|---|---|---|---|---|
| Load — straight (sloped waist + triangular steps + SDL, factored) | `_render_straight_stair` | A | ✘ | NONE | **BLOCKED** |
| Load — U-shape (flight + landing, conservative `max_DL`, factored) | `_render_u_shape_stair` | A | ✘ | NONE | **BLOCKED** |
| Design moment `Mu = Wu·L²/8` | `_render_straight_stair` / `_render_u_shape_stair` | A | ✘ | NONE | **BLOCKED** |
| Flexural reinforcement `As` | `_as_flexure_ksc` / `_required_as_flexure` | A + C (ACI 10.2) | ✔ | NONE | NOT VALIDATED |
| Minimum reinforcement | `_temp_steel_ratio` | A + C (ACI 7.12.2.1) | ✔ | NONE | NOT VALIDATED |
| Bar spacing (provided + `s_max = min(3t, 450)` / `min(5t, 450)`) | `_spacing_for` + render `s_max` | C | ✔ (`_spacing_for` only) | NONE | NOT VALIDATED / **BLOCKED** (`s_max`) |

### ANALYSIS (continuous beam)

| Calculation | Function(s) | Reference Required (level) | Existing Test | Independent Validation | Status |
|---|---|---|---|---|---|
| Element stiffness matrix (EI = 1) | `_beam_element_k` | A + C (Euler–Bernoulli) | indirect | NONE | NOT VALIDATED |
| Global assembly + boundary conditions | `solve_continuous_beam` | A + B | ✔ | NONE | NOT VALIDATED |
| Support reactions | `solve_continuous_beam` → `reactions_kgf` | A (statics) + B | ✔ (golden reactions) | NONE | NOT VALIDATED |
| Shear diagram `V(x)` | `solve_continuous_beam` → `V` | A + B | ✔ (`Vu_kgf` extremum) | NONE | NOT VALIDATED |
| Moment diagram `M(x)` | `solve_continuous_beam` → `M` | A + B | ✔ (`Mu_pos` / `Mu_neg` extrema) | NONE | NOT VALIDATED |
| Governing extrema (`Mu_pos`, `Mu_neg`, `Vu`) | `solve_continuous_beam` | A + B | ✔ | NONE | NOT VALIDATED — **see Finding VF-04 (sampled peak)** |
| Degenerate input handling (empty / non-positive spans) | `solve_continuous_beam` (`ValueError`, filter) | A | ✔ | NONE | NOT VALIDATED |

### BUILDING (model generation vs structural analysis)

| Calculation | Function(s) | Layer | Reference Required (level) | Existing Test | Independent Validation | Status |
|---|---|---|---|---|---|---|
| Grid parsing → coordinates | `_parse_spacings` | model generation | A | ✔ | NONE | NOT VALIDATED |
| Node / column / panel enumeration | `_grid_label_x`, `_column_labels`, `_panel_items` | model generation | A | ✔ | NONE | NOT VALIDATED |
| Factored slab load `Wu` | `render_building_model` (interleaved) | analysis input | A | ✘ | NONE | **BLOCKED** |
| Tributary / load take-down → column `Pu` | `_calculate_column_loads` | structural analysis (simplified) | A + B | ✔ | NONE | NOT VALIDATED — **see Finding VF-05** |
| Column grouping (marks) | `_auto_group_columns` | post-processing (rule-based) | A | ✔ | NONE | NOT VALIDATED |
| BOQ — concrete / formwork / rebar | `estimate_building_boq`, `_beam_length_m` | budget estimate (not a design output) | A + C (state ratio basis) | ✔ | NONE | NOT VALIDATED |

---

## 6. Reference Case Strategy

Three reference levels. A calculation may need more than one.

### Level A — HAND CHECK
Closed-form engineering cases an engineer can verify by hand:
- rectangular singly-reinforced `φMn`, `As_req`, `As_min`, `ρ_max`
- `Vc`, `Vs`, `φVn` for a rectangular beam with a known stirrup
- `β₁` at representative `f'c`
- `phi_flexure` at εt = 0.001 / 0.0035 / 0.006 (+ spiral)
- simply-supported / two-equal-span continuous-beam reactions and `wL²/8`
- tributary areas for a regular rectangular grid
- pile-group geometry for n = 2, 4, 9

### Level B — INDEPENDENT REFERENCE
A value from an independent calculation, spreadsheet or trusted tool
(built specifically for validation, recorded with its own worksheet):
- continuous-beam `M(x)` / `V(x)` diagrams and interior-span peaks
- column P–M interaction curve at several `Pn` levels
- two-way slab moment coefficients for representative aspect ratios
- footing punching-shear governing `vc` among the three ACI expressions
- BOQ totals for a small hand-modelled frame

### Level C — CODE REFERENCE
Checks of an equation form, coefficient or limit against ACI 318M-08:
- `β₁` piecewise definition (10.2.7.3)
- `ρ_min` (10.5.1), tension-controlled `c/d` limit (10.3.4)
- φ strain limits and transition (9.3.2)
- `Vc = 0.17λ√f'c·bw·d` (11.2.1.1) and the MKS `0.53√f'c` form
- two-way `vc` three-expression minimum (11.11.2.1), `α_s` values
- tie spacing `16 db / 48 d_tie / least dim` (7.10.5)
- shrinkage/temperature ratios (7.12.2.1) and `s_max` (7.12.2.2, 13.3.2)
- MKS `0.53√f'c` vs SI `0.17√f'c` equivalence and the `280 ksc` vs
  `28 MPa` `β₁` break (see Finding VF-07)
- the budget rebar-ratio basis for `estimate_building_boq` (150 / 120 / 90
  kg/m³) — cite the source, or mark as an engineering assumption

**No Level-B or Level-C reference numbers are entered in EV-01.**
Where a reference is not yet available the validation case carries
`Reference: REFERENCE REQUIRED` and `Status: NOT VALIDATED`.

---

## 7. Acceptance Criteria

Criteria are typed; a case declares which type(s) apply.

| Type | Definition | Default tolerance | Rationale |
|---|---|---|---|
| **Numerical (closed-form)** | program vs an exact hand/code value | relative `1e-6` (abs `1e-9` for true zeros) | closed-form maths; only floating-point dust is absorbed |
| **Engineering (independent tool)** | program vs an independent numerical model that itself discretises | **TO BE DEFINED DURING EV-02** — expected band ≈ 0.5 – 2 % depending on the reference's own method; must be justified per case, never picked arbitrarily | the reference is not exact; the band must reflect the reference's method, not hide a program error |
| **Discrete / exact** | integer counts, bar designations, layout coordinates, group marks, classification (`one-way` / `two-way`), `ValueError` on bad input | exact equality (coordinates: abs `1e-9`) | no tolerance is meaningful |
| **Pass/Fail logic** | the boolean verdict for a case whose demand/capacity are known | verdict must match the reference verdict **and** the governing ratio must agree within the numerical/engineering tolerance | a right verdict for the wrong reason is a FAIL |

**Sampled-quantity note.** `solve_continuous_beam` returns *sampled*
`Mu_pos` / `M_max` (Finding VF-04). Its Level-A/B acceptance must compare
against the **analytic** peak with a tolerance that is explicitly the
sampling error bound (documented per case), **not** a blanket loosened
band.

---

## 8. Current Validation Status

**EV-01: framework only, nothing validated.
EV-02: P0 primitives + flexure / shear / continuous-beam analysis checked
against independent references (three-moment method, hand-derived ACI
equations, first-principles flexure).
EV-03: BEAM re-validated end-to-end + one production defect fixed (VF-11,
the tension-controlled limit was not enforced in the verdict).
EV-04: SLAB re-validated + the same VF-11 defect class fixed in
`_render_slab_design`; two-way moment method identified as Grashof/Marcus
(non-ACI) → REVIEW.
EV-05: FOOTING re-validated; **VF-09 RESOLVED (not a defect)**; one fix
(VF-FOOT-02).
EV-06: COLUMN re-validated — the **full P-M interaction curve** matches an
independent strain-compatibility solver to rel < 2e-13;
**EV-COL-003/004/005 UNBLOCKED**; the column engine has **no** VF-11
defect; **0 production fixes**.
EV-07: STAIR re-validated (straight + U-shape); **VF-STAIR-01** fixed —
the same VF-11 class (tension-controlled limit absent from both stair
verdicts).
EV-08: BUILDING MODEL re-validated at the **system-integration** level —
**load conservation** holds for the regular grid (`Σ Pu = Wu·floor_area`,
rel < 1e-9); VF-01 (`Wu`) RESOLVED; system boundary documented
(model builder + single-storey tributary takedown + BOQ, no verdict);
**0 production fixes**.
EV-09: SYSTEM-WIDE consolidation & release gate — the verdict chain
`ENGINE → checks + passed → screen AND report` is single-sourced and
intact; the report / drawing layers perform **no** engineering
recompute; the false-PASS system audit is CLEAN; **0 Category-A
blockers**; **0 production changes**. **DECISION: ENGINEERING RELEASE
READY** (member-level design tool + Building MODEL; not a
structural-analysis package). One new REVIEW finding: **SYS-01** (a
failed member design shows the "REVIEW" summary badge, not "FAIL" —
consistent, under-states, never a false PASS; deferred to UI
Integration).
UI-01: **SYS-01 RESOLVED** — presentation mapping only (7 member summary
badges + Home dashboard now render `fail`/`FAIL` on `passed is False`;
DESIGN CHECKS rows show `ไม่ผ่าน (FAIL)`; a first-class `review` badge
state was added so REVIEW stays reachable for genuine limitation cases).
No engineering calculation, `passed` composition, `_status_state`,
`build_report`, drawing or calculation test was changed. `pytest` 80
passed; `run_ev09_system.py` 56 checks, PASS 46 / FAIL 0 / REVIEW 10;
ENGINEERING RELEASE READY.**
See `tests/validation/reference/`,
`docs/EV0{2,3,4,5,6,7,8,9}_COMPLETION_REPORT.md`,
`docs/SYSTEM_CAPABILITY_MATRIX.md`, `docs/ENGINEERING_RELEASE_MATRIX.md`,
`docs/ENGINEERING_REVIEW.md` (SYS-01 → CLOSED).

| Metric | EV-01 | EV-02 | EV-03 | EV-04 | EV-05 | EV-06 | EV-07 | EV-08 | after EV-09 |
|---|---|---|---|---|---|---|---|---|---|
| Functions with an **independent** engineering reference | 0 | ~24 | ~24 | ~30 | ~35 | ~40 | ~44 | ~50 | **~50** (EV-09 adds no calc ref) |
| Independent reference modules | 0 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | **12** |
| Executable checks (independent ref vs live engine) | 0 | 120 (104P·0F) | +127 beam | +77 slab | +67 footing | +87 column | +70 stair | +79 building | **+49 system (38P·0F·11R)** |
| Production calculation fixes applied | 0 | 0 | 1 (`beam.py`) | 2 (+`slab.py`) | 3 (+`footing.py`) | 3 (column: none) | 4 (+`stair.py`) | 4 (building: none) | **4** (EV-09: none) |
| Regression tests | 73, 0 skip | 73 | 75 | 77 | 78 | 78 | 80 | 80 | **80 passed, 0 skipped** |
| P-M interior cases (`EV-COL-003/004/005`) | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | VALIDATED | VALIDATED | VALIDATED | VALIDATED |
| Engineering release decision | — | — | — | — | — | — | — | — | **✅ READY** |

Every EV-02 … EV-08 numerical check that reached a live engine function
**passes** within its per-case tolerance. The **VF-11 class** — a
mandatory ACI 10.3.4 / 10.3.5 tension-controlled limit absent from the
design verdict, sized with a fixed φ = 0.90 — was found and **fixed in
`beam.py` (EV-03), `slab.py` (EV-04), and both stair renders (EV-07)**;
it is **latent but not reachable** in `footing.py` (EV-05) and **absent**
from `column.py` (EV-06). It **does not apply** to the Building Model
(EV-08 — no flexural design; no pass/fail verdict). EV-05 also resolved
VF-09 (not a defect) and fixed VF-FOOT-02 (§9.7); EV-06 unblocked the
interior column P–M points (§9.8); EV-08 resolved VF-01 and validated
load conservation for the regular grid (§9.10). The remaining `REVIEW`
items are modelling-choice / usage findings VF-04, VF-05, VF-07,
VF-11…VF-15, VF-SLAB-01…03, VF-FOOT-01/03/04, VF-COL-01…05, VF-STAIR-02/03,
ER-02/03, VF-08, VF-BLDG-02 (§9.1–§9.10); the `BLOCKED` items are now only
the render-interleaved beam / column / slab / footing / stair / building
compute chains (§10) — every importable / derivable component is
validated.

Still **not** independently validated: two-way slab moment coefficients,
irregular-grid column takedown (VF-05), and every assembled number that
lives inside a `render_*` function (§10). The EV-01 stub cases
`EV-BEAM-005`, `EV-COL-004`, `EV-SLAB-004`, `EV-FOOT-004`,
`EV-STAIR-003`, `EV-BLDG-004` remain `BLOCKED` for the same reason.

`tests/validation/` exists as a scaffold: 9 per-module `test_*_validation.py`
placeholder files (one per area), each carrying its planned cases in the
Appendix-B schema and a module-level `pytest.skip(...,
allow_module_level=True)`, plus `tests/validation/conftest.py` which
excludes them from collection (`collect_ignore_glob`). They contribute
**0** tests to the 73 baseline and **no numeric validation case**.

---

## 9. Known Findings (feed into validation)

### 9.1 From `docs/ENGINEERING_REVIEW.md` (ER-01 … ER-06)

| ID | Classification | Validation relevance |
|---|---|---|
| **ER-01** — report layer does unit conversion + `max(As_req, As_min)` selection | **UI Issue / Documentation Issue** (report presentation layer) | Not a calculation-engine validation item. Validate the *engine's* `As_req` / `As_min` (Sections 4.1, 4.3–4.7); the report's re-selection is a presentation concern to reconcile separately. |
| **ER-02** — Building report title says "structural analysis" | **Documentation Issue** | Not a validation item. Confirms Section 4.8's split: the Building Model is model generation + tributary take-down + BOQ, **not** structural analysis. |
| **ER-03** — "AI" wording for rule-based `_auto_group_columns` | **Documentation Issue** | Not a validation item. Validate `_auto_group_columns` as a **rule-based** grouping (Section 4.8). |
| **ER-04** — `solve_continuous_beam` governing `+Mu` is a *sampled* peak | **Numerical Method** → **Validation Required** | Tracked as **VF-04**. Level-A/B validation must compare vs the analytic peak with an explicit sampling-error tolerance (Section 7). |
| **ER-05** — CAD drawings shared between dark UI and white PDF | **UI Issue** | Not a calculation-engine validation item (drawing geometry is out of scope, Section 2). |
| **ER-06** — report footer drops generation date on `generate_*` paths | **Documentation Issue** | Not a validation item. |

### 9.2 From `docs/REGRESSION_BASELINE.md` "Potential engineering review" (RB-1 … RB-7)

| ID | Item | Classification | Validation relevance |
|---|---|---|---|
| **RB-1** | Inconsistent "infeasible" sentinel — `None`/`False` (beam, slab, stair) vs `float("inf")`/`False` (footing) | **Engineering Assumption** (API contract) | Validate that each variant correctly signals *infeasible* and that callers act on it; do **not** unify in a validation step. |
| **RB-2** | `solve_continuous_beam` single simply-supported span returns `Mu_neg_kgfm = -0.0` (signed zero) | **Numerical Method** (harmless) | Confirm `-0.0 == 0.0` downstream; no independent reference needed beyond "≈ 0". |
| **RB-3** | `solve_continuous_beam` positive moment is a sampled value (e.g. `wL²/8` exact 9000 → 8999.7727, ≈ 0.0025 % low) | **Numerical Method** → **Validation Required** | Same as **VF-04**. |
| **RB-4** | `_col_bar_xy("circ", …)` yields ~1e-15 instead of exact 0.0 on axis-aligned bars | **Numerical Method** (harmless) | Validate geometry with abs tolerance `1e-9`; flag if any downstream code does `== 0.0`. |
| **RB-5** | Duplicated helpers — `_temp_steel_ratio` identical in slab/footing/stair; `_as_flexure_ksc` + `_spacing_for` identical in slab/stair | **Scope Limitation** (maintenance) | Validate **once per distinct implementation**; note the duplication so a future consolidation is checked as behaviour-neutral. |
| **RB-6** | `_pile_coords` spacing convention changes with count (n = 2–5 at `±S/2`, n = 6–9 at `±S`) | **Engineering Assumption** | Validate each layout's geometry and document the convention change; do not "fix". |
| **RB-7** | Two `β₁` transition thresholds — SI `beta1` breaks at 28 MPa, MKS `_beta1_ksc` / `_beta1_col_ksc` break at 280 ksc (≈ 27.46 MPa) | **Engineering Assumption** → **Validation Required (Level C)** | Validate both against ACI 10.2.7.3 and quantify the ≈ 0.54 MPa offset's effect on `φMn` / `ρ_max`. |

### 9.3 New EV-01 observations (RECORD ONLY — not fixed)

| ID | Observation | Classification | Location |
|---|---|---|---|
| **VF-01** | The **factored slab load** `Wu = 1.2·(t/100·2400 + SDL) + 1.6·LL` for the Building Model is computed **inside `render_building_model`**, interleaved with widgets — no importable helper, no regression test. | **Scope Limitation** (compute/render split needed) | `modules/building.py` `render_building_model` |
| **VF-02** | The **column** design checks (`ρg` limits 1–8 %, `φPn,max` with `ALPHA_MAX = 0.80`, tie/spiral spacing) and the **footing / stair** shear + flexure + spacing checks live **only** inside `_render_column` / `_render_isolated_footing` / `_render_pile_cap` / `_render_straight_stair` / `_render_u_shape_stair`. Their sub-helpers are tested; the assembled governing numbers and verdicts are **BLOCKED** (not importable). | **Scope Limitation** | `modules/column.py`, `modules/footing.py`, `modules/stair.py` |
| **VF-03** | `modules/column.py` retains a **dead legacy P–M set** (`_pm_point`, `_pm_curve`, `_cap_M_at_P`, `_Pn_at_ecc`, `_bar_coords`, `_layers`, `_phi_tied`) not reached by `_render_column`; `modules/slab.py` retains dead `_render_one_way_slab` / `_render_two_way_slab` (~460 lines). Not validated, not deleted. | **Scope Limitation** (dead code) | `modules/column.py`, `modules/slab.py` |
| **VF-04** | `solve_continuous_beam` reports **sampled** `Mu_pos` / `M_max` (same as ER-04 / RB-3). Independent validation must use an explicit sampling-error tolerance. | **Numerical Method** → **Validation Required** | `utils/analysis.py` |
| **VF-05** | `_calculate_column_loads` is a **simplified** take-down: quarter-areas that would land on a *removed* column are **dropped** (not redistributed to neighbours), so total distributed `ΣPu` can be **less than** `Wu · total solid area` when columns are removed. Documented in the function's own docstring. | **Engineering Assumption** | `modules/building.py` `_calculate_column_loads` |
| **VF-06** | `_render_u_shape_stair` (default `is_eccentric` path aside) and `_render_straight_stair` apply the **conservative larger (flight) dead load over the whole span including the landing** for the straight stair, and `max(flight_DL, landing_DL)` for U-shape. Reference cases must mirror this assumption, not an "exact" per-region load. | **Engineering Assumption** | `modules/stair.py` |
| **VF-07** | Two `β₁` transition thresholds (same as RB-7): SI `aci_318m.beta1` at 28 MPa vs MKS `_beta1_ksc` / `_beta1_col_ksc` at 280 ksc (≈ 27.46 MPa). | **Engineering Assumption** → **Validation Required (Level C)** | `utils/aci_318m.py`, `modules/beam.py`, `modules/column.py` |
| **VF-08** | `estimate_building_boq` uses fixed **budget-stage** rebar ratios (150 / 120 / 90 kg/m³) with no cited source; it is explicitly a budget estimate, not a design quantity. | **Engineering Assumption** | `utils/boq.py` |

**No finding above was changed, fixed or worked around in EV-01.**

### 9.4 New EV-02 observations (RECORD ONLY — not fixed)

Surfaced while building the independent reference set (EV-02). All are
`REVIEW`-class: the affected calculation function **matches its own intent
numerically** (the EV-02 runner confirms this), but a modelling choice or
a usage pattern needs an engineer's sign-off before design output is
relied on.

| ID | Observation | Classification | Location | EV-02 case |
|---|---|---|---|---|
| ~~**VF-09**~~ **RESOLVED — NOT A DEFECT** *(EV-05)* | EV-02 recorded that the **circular-pile** punching perimeter uses `3.464·Dp + π·d`. That was a **mis-read of an incomplete code excerpt**. `modules/footing.py:952-961` has **four** shape branches: `square` / `isec` → `4·(Dp + d_avg)`; **`circular` → `π·(Dp + d_avg)`** (the correct ACI 11.11.1.2 form); **`hex` → `3.464·Dp + π·d_avg`**, where `3.464 = 2√3` is the **exact** regular-hexagon perimeter factor for an across-flats width `Dp` (`6·Dp/√3 = 2√3·Dp`), and `π·d_avg` is the d/2 corner rounding (6 × 60° arcs = one circle). All four perimeters are geometrically correct. Verified in EV-05 against independent geometry (rel < 3e-4 for the hex `2√3` vs `3.464` rounding). | **Not a finding** — the `3.464` literal is `2√3` applied only to hexagonal piles. | `modules/footing.py:953-961` `_render_pile_cap` | `EV-FOOT-002`, EV-05 phase I |
| **VF-10** | The column **tie-spacing check** computes `s_max = min(16·db, 48·d_tie, least dim)` (ACI 7.10.5.2 — correct formula) but then sets `spacing_ok = (s_max ≥ 5 cm)`, a constructability floor. It **never compares a user-supplied provided spacing** to `s_max`, so the "provided ≤ limit" PASS/FAIL boundary does not exist in the engine. | **Scope Limitation** | `modules/column.py:509-516` `_render_column` | `EV-ACI-007` |
| **VF-11** | `_flex_ksc` (beam) and `_as_flexure_ksc` / `_required_as_flexure` (slab, stair) apply `φ = 0.90` with **no internal tension-controlled guard**. Correct only while the caller enforces `ρ ≤ ρ_max`. `_render_beam_section` does (via `_rho_max_ksc`); if any current or future caller omits that check, `φMn` is overstated (≈ 10 % for `ε_t ≈ 0.004`). | **Engineering Assumption** (API contract) | `modules/beam.py:53`, `modules/slab.py:91`, `modules/slab.py:45`, `modules/stair.py:65` | `EV-BEAM-001/002`, `EV-SLAB-001` |
| **VF-12** | MKS one-way shear uses the traditional literal `Vc = 0.53·√f'c·b·d`. The exact MKS equivalent of the SI `0.17·√f'c·bw·d` is `≈ 0.5429·√f'c·b·d`; the `0.53` form is **≈ 2.4 % low (conservative)**. Standard ACI-MKS practice — recorded as a NOTE, not a defect. | **Numerical Method** (conservative) | `utils/aci_318m.py:247` `vc_beam_ksc` | `EV-ACI-005` |

**No finding above was changed, fixed or worked around in EV-02.**

### 9.5 EV-03 — BEAM validation results & corrective fix

EV-03 independently re-validated the beam calculation engine (flexure,
shear, reinforcement, spacing, boundary cases) against the EV-02
reference set plus a boundary matrix. See
`tests/validation/run_ev03_beam.py`
(**127 checks — 107 PASS, 0 FAIL, 20 REVIEW**) and
`docs/EV03_COMPLETION_REPORT.md`.

**One production defect proven and fixed** (test-first, minimal):

| ID | Finding | Root cause | Action |
|---|---|---|---|
| **VF-11** *(promoted)* | The tension-controlled / maximum-reinforcement limit (ACI 318M-08 10.3.4; and εₜ ≥ 0.004 is **mandatory** for a flexural member per 10.3.5) was **not enforced in the pass/fail verdict** of either beam design path. `_render_beam_section` computed `bot_ductile_ok` / `top_ductile_ok` but **excluded them from `bottom_ok` / `top_ok`** (only a `st.warning`). `_section_calc` computed **no** ductility check at all. Combined with `_flex_ksc`'s fixed `φ = 0.90`, an over-reinforced section produced a **non-conservative FALSE PASS** (demonstrated: `b30×h50`, `f'c 240`, `fy 4000`, 8-DB25 bottom, `Mu⁺ 40 000 kgf·m` → engine PASS; ACI-correct `εₜ = 0.0014 < 0.004`, φ = 0.65, `φMn = 31 700 < 40 000` → FAIL). | **R3 — production boundary/condition error** (a mandatory code check is computed-but-ignored / missing from the verdict). | **FIXED** in `modules/beam.py` only: `_section_calc` now computes `As_max_{top,bot} = rho_max_flexure(fc,fy)·b·d` and `{top,bot}_ductile_ok`, and includes them in `passed` (+ new return keys); `_render_beam_section` adds `and {bot,top}_ductile_ok` to `bottom_ok` / `top_ok` and a matching FAIL-reason message. Regression: `tests/test_beam_calc.py::test_section_calc_over_reinforced_fails_ductility` + `test_section_calc_tension_controlled_ductile_ok` (fail before, pass after). No formula, constant, unit or golden value changed; the SI `rho_max_flexure` used is already regression- and EV-02-validated. |

**Investigated, NOT a defect — no change (root cause R8 / R4):**

| ID | Finding | Engineering conclusion | Action |
|---|---|---|---|
| **VF-07** | MKS `_beta1_ksc` breaks at a literal 280 ksc (vs 28 MPa = 285.5 ksc). | `_flex_ksc` `Mn`/`φMn` do **not** depend on β₁ (`a = As·fy/(0.85 f'c b)`). β₁ enters only `_rho_max_ksc` → `As_max`, where the 280-ksc form gives β₁ **≤** the code-consistent value, i.e. the ductility ceiling is **slightly stricter (conservative)** above 280 ksc; effect ≤ ~0.8 %. Standard MKS practice. | **ACCEPTED (R8)** — no fix. |
| **VF-12** | `vc_beam_ksc` uses `0.53·√f'c` (MKS). | Exact SI-equivalent coefficient is `≈ 0.5429`; `0.53` is **≈ 2.4 % low → conservative** (under-estimates concrete shear). `0.53·√f'c` [ksc] is a long-standing ACI-metric code form. | **ACCEPTED (R8)** — no fix. |
| **VF-13** *(new)* | `_render_beam_section` MKS shear uses `Vs_max = 2.1·√f'c·b·d` and a dense-stirrup trigger `1.06·√f'c·b·d`. | `Vs_max`: exact ≈ 2.108 → `2.1` is 0.4 % low (**conservative**). Trigger: exact ≈ 1.054 → `1.06` is 0.6 % **high**, so the `s ≤ d/4` rule can trigger marginally late for a razor-thin `Vs` band; consequence bounded (`d/2` vs `d/4`, both code-permitted for the lower `Vs` range). | **ACCEPTED (R8) with NOTE** — recommend aligning the MKS shear coefficients to the SI-exact values in an EV-04 consistency pass (not a proven unsafe outcome). |
| **VF-04** | `solve_continuous_beam` `Mu_pos` is a sampled peak, ≈ 0.0025 % below the analytic `wL²/8` (non-conservative). | Engine matches the analytic moment sampled on the same grid to `< 1e-4` → the sole error is fixed-grid sampling, **not the solver**; the gap is bounded by `(w/2)(h/2)²`. | **ACCEPTED (R4)** — documented numerical limitation; solver **not** changed in EV-03. EV-04 may evaluate `M` at the interior stationary point analytically (would move `test_analysis.py` golden values → its own reviewed step). |

**Boundary / invalid-input matrix (EV-03 phase E):** `_flex_ksc`,
`_required_as`, `_beta1_ksc`, `_shear_check` were exercised with
zero / negative / out-of-range inputs. `_required_as` with `f'c = 0`
raises `ZeroDivisionError`; every such input is blocked upstream by the
UI's `st.number_input(min_value=…)` and is **unreachable in the app
flow**. Recorded as **VF-15** (defensive-guard gap, negative test) — not
a reachable defect, no fix in EV-03.

**No finding classified R6–R10 was treated as a production bug.**

### 9.6 EV-04 — SLAB validation results & corrective fix

EV-04 independently re-validated the slab calculation engine (load,
one-way/two-way classification, moment, flexural reinforcement, minimum
steel, spacing, boundary cases) against a first-principles reference. See
`tests/validation/reference/reference_slab_ev04.py`,
`tests/validation/run_ev04_slab.py`
(**77 checks — 58 PASS, 0 FAIL, 19 REVIEW**) and
`docs/EV04_COMPLETION_REPORT.md`.

**One production defect proven and fixed** (test-first, minimal — the same
class as EV-03's VF-11):

| ID | Finding | Root cause | Action |
|---|---|---|---|
| **VF-11-SLAB** | `_render_slab_design` sizes the flexural steel with `_as_flexure_ksc`, which applies a **fixed `φ = 0.90`** and has no tension-controlled guard. The verdict `passed = main_ok and temp_ok` checked **only bar spacing** — **no `As ≤ As_max` / tension-controlled check** anywhere. A reachable over-reinforced slab (`Lx 3 m`, `Ly 7 m` one-way, `t 10 cm`, `SDL 250`, `LL 1300 kgf/m²`, DB16 → `Mu = 3 002 kgf·m/m`, `As_x = 14.4 > As_max = 11.7 cm²/m`, `εₜ = 0.0035 < 0.004` → **ACI 10.3.5 violated**, φ should be 0.775 not 0.90) produced a **non-conservative FALSE PASS** because its bar spacing `S_x = 12.5 cm` sits inside `7.5…s_max`. | **R3 — production boundary/condition error** (mandatory code limit absent from the verdict). | **FIXED** in `modules/slab.py` only: added module-level `_beta1_ksc` / `_rho_max_ksc` (byte-identical to `modules/beam.py`, already EV-02/EV-03-validated); `_render_slab_design` now computes `As_max_x/y = _rho_max_ksc(fc,fy)·b·d` and `ductile_x/y`, includes `ductile_ok` in `passed`, and adds a DESIGN-CHECKS row + FAIL message + warning. Regression: `tests/test_slab_calc.py::test_beta1_ksc` + `test_rho_max_ksc` (golden). No formula, unit, condition or existing golden value changed. `pytest` 75 → **77 passed**. |

**Investigated, NOT a defect — no change:**

| ID | Finding | Engineering conclusion | Action |
|---|---|---|---|
| **VF-SLAB-01** *(new)* | Two-way design moments use `Mux = Wu·Lx²·(Ly⁴/(Lx⁴+Ly⁴))/8`, `Muy = Wu·Ly²·(Lx⁴/(Lx⁴+Ly⁴))/8`. | This is the classical **Grashof / Rankine (Marcus)** elastic load-partition method: total load split between orthogonal strips in proportion to the 4th power of the opposite span, each strip then designed as a simply-supported 1 m strip (`wL²/8`). It is a recognised approximate method but is **NOT an ACI 318M-08 method** (ACI 13.6 DDM / 13.7 EFM). It assumes 4 simply-supported edges, no continuity, no corner hold-down, uniform load; the engine applies it to **every** two-way panel with no applicability check, and the UI/report labels the result "ตาม ACI 318M-08". The closed-form **implementation is correct** (validated to rel < 1e-9). | **REVIEW / DOCUMENT (R7 / R8)** — **CODE / COEFFICIENT REFERENCE REQUIRED**. Do **not** change the formula. Recommend: state the method by name in the UI/report, and add an applicability note (interior SS panels, no pattern loading). |
| **VF-SLAB (one-way continuity)** | One-way `Mu = Wu·Lx²/8` — the simply-supported value. | Correct for a genuinely simply-supported slab. Continuous one-way slabs (ACI 8.3.3 approximate moment coefficients, support/top steel) are **NOT IMPLEMENTED**; the support region of a continuous slab is under-designed. | **NOT IMPLEMENTED (R9 scope limitation)** — do not add in EV-04. |
| **VF-SLAB-03** *(new)* | `_spacing_for`'s `max(S, 2.5)` floor can return `As_provided < As_required` when `As_req > Ab·40` (S_req < 2.5 cm). | Real invariant break in the shared helper, but **not reachable as an unsafe slab verdict** — `S = 2.5 cm < 7.5 cm` is always rejected by the caller's minimum-spacing check. Also used by `modules/stair.py`. | **RECORD (R3, caught by the caller)** — shared-helper hardening deferred to a later step (would need stair re-validation). |
| **VF-SLAB (self-weight 2400)** | `sw = (t/100)·2400 kgf/m³`. | `2400 kgf/m³` is the MKS convention (used identically by beam / footing / stair); the SI "exact" `24 kN/m³ = 2446.5 kgf/m³`, so `sw` is ≈ 1.9 % low → marginally non-conservative on the DL term only. | **ACCEPTED (R8)** — no fix (consistent across the codebase). |
| **VF-SLAB-02** *(new)* | `_as_flexure_ksc` / `_required_as_flexure` with `f'c = 0` raise `ZeroDivisionError`. | Blocked upstream by `st.number_input(min_value=180 ksc)`; unreachable in the app flow. Same class as EV-03 VF-15. | **RECORD (R9)** — negative test, no fix. |
| **As,temp DESIGN-CHECKS row** | Row status hardcoded `True`. | The minimum flexural steel (= shrinkage/temperature per ACI 10.5.4) **is** enforced — via `As_x = max(As_x_req, As_temp_min)` / `As_y = max(…)`; the row is a value display only. | **R10 (presentational)** — enforcement OK, no fix. |

**NOT IMPLEMENTED in `modules/slab.py` (SCOPE LIMITATION — not added):**
one-way shear, two-way / punching shear, deflection & span-depth control,
crack control (ACI 10.6.4), development length, torsion, moment
redistribution, continuity / ACI 8.3.3 support moments, column-strip /
middle-strip distribution, pattern loading, corner reinforcement. Dead
code `_render_one_way_slab` / `_render_two_way_slab` (matches VF-03).
**Future validation priority:** deflection (serviceability) and one-way
shear for thin, heavily-loaded slabs.

**No finding classified R6–R10 was treated as a production bug.**

### 9.7 EV-05 — FOOTING validation results & corrective fix

EV-05 independently re-validated `modules/footing.py` — isolated footing,
pile cap, eccentric pile cap. See
`tests/validation/reference/reference_footing_ev05.py`,
`tests/validation/run_ev05_footing.py`
(**67 checks — 42 PASS, 0 FAIL, 25 REVIEW**) and
`docs/EV05_COMPLETION_REPORT.md`.

**One production defect proven and fixed** (test-first, minimal):

| ID | Finding | Root cause | Action |
|---|---|---|---|
| **VF-FOOT-02** *(new)* | The elastic pile-group distribution `R_i = P/n + M_y·x_i/Σx² + M_x·y_i/Σy²` in `_render_pile_cap` guards `if sum_x2 > 0.0` / `if sum_y2 > 0.0` and **silently drops** the moment term when the group has no pile offset on that axis — **n = 1** (Σx² = Σy² = 0) and **n = 2** (piles colinear on Y, Σx² = 0). An applied column eccentricity about the un-resisted axis (F2E defaults `ex = 15 cm`) is then ignored: all `R_i` become equal, the cap's perpendicular direction is designed for ≈ zero moment, moment equilibrium `Σ R_i·x_i = P·ex` is violated, and **no warning is shown** (`uplift_ok` is True since all `R_i > 0`). The cap+column system is a mechanism. **Non-conservative silent acceptance of an unresolvable load case.** | **R3 — production boundary/condition error.** | **FIXED** in `modules/footing.py` only: added `ecc_resolvable_ok = not ((ex_mm != 0 and sum_x2 == 0) or (ey_mm != 0 and sum_y2 == 0))`, included it in `passed`, added an explanatory `st.error` and folded it into the DESIGN-SUMMARY pile-forces chip. Regression: `tests/test_footing_calc.py::test_pile_coords_degenerate_moment_resistance` (pins Σx²=0 for n≤2, Σx²/Σy²>0 for n≥3 — the geometry the gate relies on). No formula, constant, unit or golden value changed. `pytest` 77 → **78 passed**. |

**Investigated, NOT a defect — no change:**

| ID | Finding | Engineering conclusion | Action |
|---|---|---|---|
| **VF-09** *(RESOLVED)* | see §9.4 — the `3.464·Dp` literal is `2√3` (exact regular-hexagon perimeter factor), applied **only** to hexagonal piles; circular piles use the correct `π(Dp+d)`, square/I use `4(Dp+d)`. | All four pile-head punching perimeters are geometrically correct (verified in EV-05 phase I). EV-02's VF-09 was a mis-read. | **NOT A DEFECT** — EV-02 record corrected. |
| **VF-FOOT-01** *(new)* | Neither `_render_isolated_footing` nor `_render_pile_cap` has an `As ≤ As_max` / tension-controlled check in the verdict; `_flexure_as` uses a fixed `φ = 0.90`. Latent **R3**, same class as EV-03 beam / EV-04 slab. | **NOT a reachable non-conservative FALSE PASS.** Every load path that over-reinforces the flexural steel first fails one-way shear, punching shear, bearing, or flexure-infeasibility — **all of which ARE in the verdict** (proven in EV-05 phase G: the over-reinforced attempt `εₜ = 0.0016` fails `beam_long_ok`, `beam_short_ok`, `punch_ok`, `flex_short_ok`). The shear demand co-scales with the flexure demand. | **RECORD (R3, latent / shadowed)** — recommend adding the `As ≤ As_max` check for defense-in-depth + EV-03/04 consistency in a later step; **not fixed in EV-05** (not a proven reachable defect). |
| **VF-FOOT-03** *(new)* | `_render_isolated_footing` uses `d = h − cov − db_long` (a **full** bar diameter), whereas `_render_pile_cap` uses `d = h − embed − db/2`. | The isolated-footing value **under-estimates `d` by ≈ db/2** → **conservative** on both flexure (more `As`) and shear (lower `φVc`). Inconsistent between the two flows. | **RECORD (R8 / R2, conservative)** — no fix (changing it moves behaviour in the non-conservative direction; needs a reviewed step). Recommend harmonising to `db/2`. |
| **VF-FOOT-04** *(new)* | `_flexure_as` / `_temp_steel_ratio` etc. with `f'c = 0` raise `ZeroDivisionError`. | Blocked upstream by `st.number_input(min_value)` (`f'c ≥ 180 ksc`, `h ≥ 30 cm`, fixed pile-count selectbox). Unreachable. Same class as EV-03 VF-15 / EV-04 VF-SLAB-02. | **RECORD (R9)** — negative test, no fix. |
| Pile-head punching `vc` | `phiVc_pile` uses `0.33√f'c` (vc3) directly, not `min(vc1, vc2, vc3)`. | For a compact loaded area (a pile head, βc = 1) `vc3` **governs the minimum** anyway (`vc1 = 0.51√f'c`, `vc2 > 0.33√f'c` for a small `bo`), so this equals the ACI minimum in practice. | **NOTE (R8)** — no fix. |
| Self-weight `2400 kgf/m³` | `Wf = area·h·2400`. | MKS convention (identical to beam/slab); SI 24 kN/m³ = 2446.5 → ≈ 1.9 % low on the DL term only. | **ACCEPTED (R8)** — no fix. |
| `_pile_coords` convention | centre-to-centre, origin = column centre; `S` = adjacent-pile spacing (`3·Dp`). | n = 2–5 groups span ±S/2, n ≥ 6 span ±S — the **adjacent spacing is `S` throughout** (RB-6's "convention changes with count" is only the group extent). Verified for n = 1…9. | **Not a defect.** |

**NOT IMPLEMENTED in `modules/footing.py` (SCOPE LIMITATION — not added):**
eccentric **spread** footing (soil-pressure distribution, `e ≤ B/6`,
`q_max` / `q_min`, partial contact, shallow-footing uplift / overturning /
sliding), Wall / 2-Column / Combined / Strap footings (`UNDER_
CONSTRUCTION`), dowel / column-bearing design, development length,
**minimum bar clear-spacing** (ACI 7.6.1), settlement, pile-group
efficiency, lateral pile load. Nested `_elastic_reactions` / `_side` /
`_s0` are not importable → the assembled pile-cap numbers stay **BLOCKED**
(matches VF-02); EV-05 validated every importable / derivable piece
(pile geometry, the elastic-reaction formula + equilibrium, punching
perimeters, `vc1/vc2/vc3`, `_flexure_as`).

**No finding classified R6–R10 was treated as a production bug.**

### 9.8 EV-06 — COLUMN validation results (no corrective fix required)

EV-06 independently re-validated `modules/column.py` — geometry, material,
reinforcement ratio, pure compression, `φPn,max`, the **full P-M
interaction curve**, the φ transition, `φMn_at_Pu`, the P-M verdict, and
tie spacing. See
`tests/validation/reference/reference_column_ev06.py` (an independent
strain-compatibility P-M solver — `math`-only, ACI equations, **no import
of `modules.column`, `utils.aci_318m`, or any production P-M function**),
`tests/validation/run_ev06_column.py`
(**87 checks — 60 PASS, 0 FAIL, 27 REVIEW, 0 BLOCKED**) and
`docs/EV06_COMPLETION_REPORT.md`.

**No production defect found. `modules/column.py` is unchanged by EV-06.**

- **`_calculate_pm_curve` VALIDATED.** The engine's full 46-point P-M
  curve (`Mn`, `Pn`, `φMn`, `φPn`) reproduces the independent
  strain-compatibility reference to **rel < 2 × 10⁻¹³** at every point.
  Force equilibrium (`C_tot − T_tot − Pn = 0`) verified; the balanced
  point (analytic `c_b = ε_cu·d_t/(ε_cu + ε_y)`) verified.
- **`EV-COL-003` / `EV-COL-004` / `EV-COL-005` — UNBLOCKED.** EV-01 / EV-02
  marked the interior P-M points BLOCKED ("no trustworthy independent
  reference"). EV-06's `reference_column_ev06` is that reference; the
  three interior points (low / intermediate / near-boundary eccentricity)
  are now **VALIDATED**. `tests/validation/reference/cases/column_pm.json`
  updated (`status: BLOCKED → REFERENCE_READY`).
- **The column engine does NOT have the EV-03 / EV-04 VF-11 defect.** The
  P-M check (`pm_ok`, point-in-polygon on `φMn_c` / `φPn_c`) uses the
  **per-point φ** computed from each point's `ε_t` (0.65 → 0.90,
  ACI 9.3.2) — validated across compression-controlled / transition /
  tension-controlled. `φPn,max` (Check 2) correctly uses `φ = 0.65` for
  pure axial.
- **False-PASS audit:** `passed = ratio_ok and axial_ok and spacing_ok
  and pm_ok` — **all four computed checks are terms of the verdict**. No
  "warning but final PASS" pattern. `φMn_at_Pu` is display-only.

**Findings (all REVIEW / R8–R10 / scope — none is a production bug):**

| ID | Finding | Root cause | Action |
|---|---|---|---|
| **VF-COL-01** *(new)* | `φMn_at_Pu` — a **display** readout (`ui.utilization` / `ui.kpi` / a checks-table "capacity" cell) computed as `max(φMn_c where │φPn_c − Pu│ ≤ 6 % of max│φPn│)` with an `np.interp` fallback — reads ≈ 0 when `Pu` is near pure compression. **Physically correct** (a section at ≈ pure axial has ≈ zero moment capacity), but shown next to a PASS verdict it can read as "Mu vs capacity ≈ 0". The **verdict** is `pm_ok` (point-in-polygon), which is correct. | **R10 (presentation)** | **RECORD** — a clearer readout would help; UI, not a calculation defect. No fix. |
| **VF-10** *(re-confirmed from EV-02)* | Tie-spacing Check 3 (tied): `S_req = min(16·db, 48·d_tie, least dim)`; `spacing_ok = (S_req ≥ 5 cm)`. There is **no user-provided tie-spacing input** — the tool *designs* the spacing (= `S_req`) and only checks it is buildable (≥ 5 cm), which is true for every real column. `spacing_ok` is in the verdict but effectively always True. | **R9 (scope / by design)** | **RECORD** — adding a provided-spacing check would be a new feature. No fix. |
| **VF-COL-02** *(= VF-07)* | `_beta1_col_ksc` breaks at a literal 280 ksc (vs 28 MPa = 285.5 ksc). In `_calculate_pm_curve` a lower β₁ gives a smaller stress-block depth → slightly smaller `Cc` and lever arm; second-order, mixed. | **R8 (conservative metric convention)** | **ACCEPTED** — no fix. |
| **VF-COL-03** *(new)* | The `Mu` `number_input` help text says (in Thai) "not used in this version — reserved for a future P-M diagram", but `Mu` **is** used in `pm_ok = _point_in_poly(Mu, Pu, …)`, which gates the verdict. | **R10 (stale UI text)** | **RECORD** — candidate 1-line UI fix; not a calculation defect. Deferred. |
| **VF-COL-05** *(new)* | The module docstring says "biaxial … Bresler reciprocal-load method", but `_render_column` takes a **single `Mu`** and performs a uniaxial P-M check only. | **R10 (stale docstring)** | **RECORD** — biaxial is NOT IMPLEMENTED. |
| **VF-COL-04** *(new)* | `_calculate_pm_curve(f'c = 0)` and similar pure-helper calls with out-of-range inputs — no internal guard; blocked upstream by `st.number_input(min_value)` and the `cov + tie + bar ≥ dim/2` guard. Unreachable. | **R9** | **RECORD** — negative test, no fix. |
| φ strain limit | `_calculate_pm_curve` uses `ε_ty = fy/Es` for the compression-controlled limit — the **exact** ACI 10.3.3 form, not the 0.002 literal used in beam/slab. | not a defect (more precise; inconsistent) | **NOTE.** |
| bar-area rounding | `Ab = bar_area('DB20')/100` uses the `REBAR` table's `round(π d²/4, 2)` (a data lookup); the independent reference uses the same table value so the P-M comparison is exact. | — | **NOTE** (a from-scratch `π d²/4` differs ≈ 2 × 10⁻⁶ rel, per EV-02). |

**NOT IMPLEMENTED in `modules/column.py` (SCOPE LIMITATION — not added):**
slenderness / `kl_u/r` / moment magnification / second-order analysis
(the column validation applies **only** to short-column, unamplified P-M
behaviour — the user must magnify `Mu` externally); **biaxial** bending
(stale docstring); confinement / seismic tie detailing (ACI Ch. 21); lap
splices; column-to-footing dowels; creep / sustained-load stiffness
reduction. **Dead code:** `_phi_tied`, `_bar_coords`, `_layers`,
`_pm_point`, `_pm_curve`, `_cap_M_at_P`, `_Pn_at_ecc` (not reached by
`_render_column`; matches VF-03).

**No finding classified R6–R10 was treated as a production bug.**

### 9.9 EV-07 — STAIR validation results & corrective fix

EV-07 independently re-validated `modules/stair.py` — the two implemented
stair types (`_render_straight_stair`, `_render_u_shape_stair`). See
`tests/validation/reference/reference_stair_ev07.py`,
`tests/validation/run_ev07_stair.py`
(**70 checks — 40 PASS, 0 FAIL, 30 REVIEW**) and
`docs/EV07_COMPLETION_REPORT.md`.

**One production defect proven and fixed** (test-first, minimal — the
fourth instance of the VF-11 class after beam / slab / [footing-latent]):

| ID | Finding | Root cause | Action |
|---|---|---|---|
| **VF-STAIR-01** *(new)* | Both stair renders size flexural steel with a **fixed `φ = 0.90`** (`_as_flexure_ksc` straight, `_required_as_flexure` U-shape — byte-identical to the slab helpers) and **omit the `As ≤ As_max` / tension-controlled check** from the verdict. `_render_straight_stair`: `passed = main_ok and temp_ok` — **bar spacing only**. `_render_u_shape_stair`: `passed` checks strength + `As_min` + temp + spacing (more complete) but **still no `As ≤ As_max`**. A **reachable** over-reinforced straight flight (`R 17.5 / T 28 / N 10`, `t 8 cm`, `SDL 300`, `LL 615 kgf/m²`, DB16 → `Mu = 1 830 kgf·m/m`, `As_main = 12.9 > As_max = 8.5 cm²/m`, `εₜ = 0.0022 < 0.004` → **ACI 10.3.5 violated**, φ should be 0.67 not 0.90, `S_main = 15 cm` in `[7.5, 24]` → `main_ok`) produced a **non-conservative FALSE PASS**. | **R3 — production boundary/condition error** (mandatory ACI 10.3.4 / 10.3.5 limit absent from the verdict). | **FIXED** in `modules/stair.py` only: added module-level `_beta1_ksc` / `_rho_max_ksc` (byte-identical to beam / slab, already EV-02…EV-04 validated); imported the SI `rho_max_flexure` for the U-shape; **both renders** now compute `As_max_main` and `ductile_ok` and include it in `passed`, with a DESIGN-CHECKS row + warning + FAIL message. Regression: `tests/test_stair_calc.py::test_beta1_ksc` + `test_rho_max_ksc` (golden). No formula, unit, condition or existing golden value changed; `pytest` 78 → **80 passed**. |

**Investigated, NOT a defect / documented (all REVIEW):**

| ID | Finding | Root cause | Action |
|---|---|---|---|
| Support condition | Both renders idealise the flight as a **simply-supported single span** (`Mu = wL²/8`). No continuity, no support / top steel, no landing-slab design. | **R9 scope** | Exact for an SS flight; a continuous flight's support region is under-designed. NOT IMPLEMENTED — not added. |
| One-way shear | Neither render checks `Vu ≤ φVc`. | **R9 scope** | Consistent with the slab module. NOT IMPLEMENTED — not added. |
| **VF-STAIR-02** *(new)* | U-shape `sp_main_ok` / `sp_temp_ok` check only an **upper** bound (`s ≤ min(3t, 450)` / `min(5t, 450)`) on the user-provided spacing — no minimum / clear-spacing bound (the user input is capped at 5 cm in the widget). | **R9 scope** | RECORD — no minimum-clear-spacing (ACI 7.6.1) check. No fix. |
| **VF-STAIR-03** *(new)* | `_as_flexure_ksc` / `_required_as_flexure` with `f'c = 0` raise `ZeroDivisionError`. | **R9** | Blocked upstream by `st.number_input(min_value = 180 ksc)`. Unreachable. RECORD — negative test, no fix. Same class as EV-03 VF-15 / EV-04 VF-SLAB-02 / EV-05 VF-FOOT-04. |
| **VF-06** *(re-confirmed)* | Straight vs U-shape DL factoring differs: straight splits `DL_waist (/cos θ) + DL_steps (R/2)`, flight load over the whole horizontal span; U-shape uses `t_avg = t/cos θ + R/2` (same total) but `Wu = 1.2·max(flight_DL, landing_DL) + 1.6 LL` over the **whole** span `L = L_flight + L_land`. | **R8** | The `max()` for U-shape is a deliberate **conservative** treatment of the landing region. Engineering-equivalent DL, different factoring. NOTE. |
| Display `FAIL → REVIEW` (STEP 14) | Both renders show `ui.status_badge("pass" if passed else "warn", "PASS" if passed else "REVIEW")` — a failing design shows the amber **REVIEW** badge, not red **FAIL**. | **R10 (presentation)** | The `passed` boolean, the per-row PASS/REVIEW table, the `fails` / `reasons` list and the `st.error` are **unchanged** — the calculation and the detailed failure reporting are intact; only the top badge wording was softened (identical to the slab module). **No engineering result is masked.** RECORD. |
| self-weight `2400 kgf/m³` | `DL_waist` / `DL_steps` / `t_avg` use the literal 2400. | **R8** | MKS convention, identical across the codebase. ≈ 1.9 % low vs 24 kN/m³. ACCEPTED. |
| shared helper duplication (RB-5) | `_as_flexure_ksc` / `_spacing_for` are **functionally identical** to the slab versions (docstrings / parameter names differ only). | **R9 maintenance** | Validated once (EV-04 slab + EV-07 stair). RECORD. |

**NOT IMPLEMENTED in `modules/stair.py` (SCOPE LIMITATION — not added):**
one-way shear check; development / anchorage length; support (negative)
moment + top steel; landing-slab design; continuity; bar cut-off;
deflection / span-depth; crack control; nosing / step reinforcement. Stair
types L-shape / slabless / free-standing / spiral are `UNDER_CONSTRUCTION`
(`st.info` only, no calculation). The assembled `_render_*` numbers stay
**BLOCKED** (interleaved); EV-07 validated every importable / derivable
piece (geometry, self-weight, `Wu`, `Mu`, the flexure helper chains, temp
steel, spacing) and the verdict-composition logic.

**No finding classified R6–R10 was treated as a production bug.**

### 9.10 EV-08 — BUILDING MODEL & load-takedown validation results (no corrective fix required)

EV-08 independently re-validated `modules/building.py` + `utils/boq.py` at
the **system-integration** level — geometry, member enumeration, the
factored slab load, the **tributary column load-takedown**, load
conservation, the rule-based grouping, the budget BOQ, and the
analysis / verdict boundary. See
`tests/validation/reference/reference_building_ev08.py` (independent,
`math`-only — **no import of `modules.*` or `utils.analysis`**),
`tests/validation/run_ev08_building.py`
(**79 checks — 60 PASS, 0 FAIL, 19 REVIEW, 0 BLOCKED**) and
`docs/EV08_COMPLETION_REPORT.md`.

**No production defect found. `modules/building.py` and `utils/boq.py` are
unchanged by EV-08.**

**System boundary (the answer to the EV-08 §3 question):** the Building
Model is **(A) a grid / geometry model builder + (B) a SINGLE-STOREY
tributary vertical load-takedown + a budget BOQ estimate**. It is **NOT**
structural analysis, **NOT** multi-storey, **NOT** a design check. It has
**no pass/fail verdict** — the on-screen status is *"MODEL GENERATED"*
(an `info` badge, with the caption "ยังไม่มีการวิเคราะห์โครงสร้าง"), and
the PDF uses `status="MODEL"` → *"MODEL GENERATED"*. **Correct — no false
design PASS.** It does **not** import or call `utils.analysis`
(no coupling to the continuous-beam solver).

- **LOAD CONSERVATION — VALIDATED for the regular grid.** For a full solid
  grid (all columns active, no voids): `Σ trib_area = floor_area` and
  `Σ Pu = Wu · floor_area` **exactly**. Void panels genuinely carry no
  load and are excluded consistently (`Σ trib_area = solid_area`).
  `_calculate_column_loads` reproduces an independent tributary
  implementation to **rel < 1e-9**. Symmetry (corner : edge : interior
  tributary = 1 : 2 : 4 for equal bays) and scaling (×2 `Wu` → ×2 `ΣPu`;
  ×4 area → ×4 `ΣPu`) hold.
- **VF-BLDG-01 (= VF-01) — RESOLVED.** The `Wu = 1.2·(t/100·2400 + SDL) +
  1.6·LL` formula computed inside `render_building_model` (EV-01 marked it
  BLOCKED) is the standard ACI 318M-08 9.2 gravity combination, verified
  by independent reconstruction. Still interleaved — the *assembled*
  per-column numbers stay BLOCKED — but every component is now validated.
- **BOQ — VALIDATED.** `estimate_building_boq` (concrete / formwork /
  rebar for one storey) and `_beam_length_m` reproduce an independent
  take-off to **rel < 1e-9**.

**Findings (all REVIEW / R8–R10 / scope — none is a production bug):**

| ID | Finding | Root cause | Action |
|---|---|---|---|
| **VF-05** *(re-confirmed)* | `_calculate_column_loads` **drops** the quarter-areas that would land on a **removed** column (it does not redistribute them to the neighbours). So `Σ trib_area + dropped = floor_area` (no area created / duplicated — only **lost**), and `Σ Pu` is **below** `Wu · floor_area` — **non-conservative** (neighbour column loads under-estimated). Documented in the function's own docstring as a *"simplified column takedown"*. | **R9 / R8** — an intentional model simplification of a **model-generation + BOQ** tool, not a structural design. | **RECORD** — downstream, only the preliminary C1/C2/C3 `_auto_group_columns` marks and the on-screen total use these `Pu` values (nothing is *sized* from them). Redistributing the dropped quarters would be **adding a feature** (forbidden by the EV-08 brief). The tool must not be used for column load takedown on irregular grids without engineer review. **No fix.** |
| **ER-02** *(re-confirmed)* | The PDF report **title** is "รายงานวิเคราะห์โครงสร้างอาคารและประมาณราคา (Building Analysis & BOQ Report)" — "วิเคราะห์โครงสร้าง / Analysis" slightly over-claims. The **verdict** is correctly *"MODEL GENERATED"*. | **R10 (stale title)** | **RECORD** — candidate 1-line title reword. Deferred. |
| **ER-03** *(re-confirmed)* | `_auto_group_columns` docstring says "AI pre-analysis"; `render_building_model` uses `ai_marks` / `ai_mark` / "AI แนะนำเบอร์เสา". The routine is **fixed-threshold** clustering (`ratio ≥ 0.75 → C1`, `≥ 0.45 → C2`, else `C3`) — no learned model. Verified against independent thresholding. | **R10 (UI / doc wording)** | **RECORD** — cosmetic reword. Deferred. No calc impact. |
| **VF-08** *(re-confirmed)* | `estimate_building_boq` rebar ratios **150 / 120 / 90 kg/m³** (column / beam / slab) have no cited source (typical Thai budget-stage values). | **R8 / R9** | **RECORD** — it is a **quantity** output, **not a load source**; nothing structural is computed from it, and the UI caption reads "ค่าประมาณเบื้องต้นสำหรับงบประมาณ" (preliminary budget estimate only). No fix. |
| **VF-BLDG-02** *(new)* | `_parse_spacings` / `_calculate_column_loads` / `estimate_building_boq` with degenerate inputs (empty / all-invalid spacings, zero / negative `Wu`, `beam_h < slab_t`) — **no crash** (graceful: empty results, `web` clamps to 0, negative `Wu` propagates linearly). `f'c`-style zero-division does not arise (no material strength in this module). | **R9** | **RECORD** — UI-blocked (`st.number_input(min_value)`, text parsing drops non-positive spacings). No fix. |

**Double-counting / missing-load audit:** the **only** self-weight in the
load path is the **slab** self-weight inside `Wu` (`t · 2400`); it is
generated once and distributed once (tributary). Beam / column / stair
self-weight are **not** in the takedown (they appear only in the BOQ
concrete volume — a separate quantity pathway) — a known **under-estimate**
that is part of the "MODEL GENERATED, not analysis" scope. The stair
module's inclined-slab self-weight (the `1/cos θ` term validated in EV-07)
is a **separate** module and is **not** added to the building floor slab —
**no cross-module double count.**

**NOT IMPLEMENTED in the Building Model (SCOPE LIMITATION — not added):**
**multi-storey** column-load accumulation (`P_base = Σ floor loads` — the
takedown runs once, for one floor); **foundation** reaction pathway
(the tributary `Pu` values are not fed to footing design); **beam**
line-load takedown (area → `w`); lateral / wind / seismic / frame
analysis; member self-weight beyond the slab; pattern loading; load
combinations other than `1.2D + 1.6L`; live-load reduction; per-floor
live load. The assembled `_render_*` numbers stay **BLOCKED** (interleaved);
EV-08 validated every importable / derivable piece.

**No finding classified R6–R10 was treated as a production bug.**

---

### 9.11 EV-09 — SYSTEM-WIDE consolidation & release gate (no corrective fix required)

EV-09 is a **consolidation + release gate**, not a feature / refactor / UI phase.
It answers the *system* question: does a validated engine result keep its
**VALUE / UNIT / STATUS / engineering meaning** across
`ENGINE → RESULT → UI → SUMMARY → DRAWING → REPORT`, with **no FALSE PASS**?
See `docs/SYSTEM_CAPABILITY_MATRIX.md`, `docs/ENGINEERING_RELEASE_MATRIX.md`,
`docs/EV09_COMPLETION_REPORT.md` (28 sections) and
`tests/validation/run_ev09_system.py`
(**49 checks — 38 PASS, 0 FAIL, 11 REVIEW**).

**No production defect found. `modules/*`, `utils/*`, `reports/*`, `main.py` are
unchanged by EV-09.**

- **Verdict chain — INTACT.** Every member module builds one `checks` list
  `[(name, demand, capacity, ok), …]` + one `passed` boolean (the AND of all
  implemented checks, **including** the EV-03/04/05/07 ductility / resolvability
  gates), then renders it on screen **and** passes the **same** `checks` +
  `status=passed` to `render_report_expander` → `build_report`
  (`beam.py:820/822`, `column.py:697/702`, `slab.py:439/441`,
  `footing.py:619/621` + `1327/1355`, `stair.py:748/750`).
  `render_report_expander` (`utils/project.py:138`) is a pure pass-through.
- **Report layer — presentation only.** `_status_state(status, checks_ok)`
  normalises `bool` / `"MODEL"` / str → `PASS`/`FAIL`/`REVIEW`/`MODEL` with **no
  engineering maths** (source audit: no `0.85` / `sqrt` / `rho` / `* fc`);
  `_status_state(True) → "PASS"`, `(False) → "FAIL"`, `("MODEL") → "MODEL"`
  (verified). **The PDF cannot turn `MODEL` into `PASS`.**
- **Drawing layer — presentation only.** `utils/drawing.py` calls **none** of
  `_calculate_pm_curve` / `solve_continuous_beam` / `_*flexure*` / `vc_beam` /
  `rho_max`; its arithmetic is dimension offsets + drawing clamps (`0.85·D`,
  `0.85·h`). It creates **no** engineering result.
- **False-PASS system audit (P0) — CLEAN.** No module has
  `calculation = FAIL → check ignored → verdict = PASS`, no "warning only but
  overall PASS", no "UI PASS while engine FAIL". The VF-11 tension-controlled
  class is **fixed** (beam/slab/stair), **latent-unreachable** (footing),
  **absent** (column), **N/A** (building — no verdict).
- **Release-blocking classification:** **0 Category-A (blockers)**; 3 Category-B
  (REVIEW) at EV-09: **SYS-01** *(since **CLOSED** by UI-01)*, VF-SLAB-01,
  VF-04/ER-04; ~14 Category-C (documented limitation); 8 Category-D (UI only);
  the rest Category-E (future feature, never shown as PASS).

**Findings (all REVIEW / R10 / scope — none is a calculation bug; SYS-01 later
resolved in UI-01 as a presentation-only fix):**

| ID | Finding | Root cause | Action |
|---|---|---|---|
| **SYS-01** *(EV-09 discovered → **UI-01 CLOSED**)* | System-wide, every member module's DESIGN-SUMMARY badge (and the Home dashboard Beam row) showed **"REVIEW"** (amber) when `passed is False` — not a red **"FAIL"**. **Consistent** across all 6 modules. **Not a false PASS:** "REVIEW" ≠ "PASS", and the authoritative `st.error("❌ ไม่ผ่าน (FAIL) — <specific reasons>")` + per-row text always fire on `passed is False`. The summary badge **under-stated** severity; it never over-states. | **R10** — presentation-layer verdict-state mapping (summary badge granularity vs the detailed verdict). | **CLOSED / RESOLVED (UI-01).** Presentation mapping only: the 7 member summary badges + `main._module_status_rows` now render `fail`/`FAIL` on `passed is False`; DESIGN CHECKS rows show `ไม่ผ่าน (FAIL)`; `utils/ui.py:_BADGE` gained a first-class `review` state so REVIEW stays reachable for genuine limitation cases. **No** `passed` composition, engineering `checks`, `_status_state`, `build_report`, drawing, ACI calculation or calculation test changed. Verified: `pytest` 80 passed; `run_ev09_system.py` 56 checks / PASS 46 / FAIL 0 / REVIEW 10 / ENGINEERING RELEASE READY. See `docs/ENGINEERING_REVIEW.md` → SYS-01. |
| **ER-01** *(re-confirmed)* | `reports/pdf_generator.py:_governing_as(r) = max(As_req, As_min)` + SI→MKS display helpers live in the report layer. | **R10 / layer boundary** — a `max()` selection + display units outside the modules. Uses **engine** values; changes no verdict, no capacity. | **RECORD (Class D).** UI phase: move into the modules / a shared helper; keep the numeric factors. |
| **ER-02 / ER-03 / VF-COL-03 / VF-COL-05** *(re-confirmed)* | Stale text: building report **title** says "Analysis" (verdict is correctly `MODEL`); "AI" wording for fixed-threshold clustering; column `Mu` help "not used in this version" (Mu **is** used in `pm_ok`); column docstring mentions "biaxial / Bresler" (uniaxial only). | **R10** (UI / doc wording). | **RECORD (Class D).** 1-line corrections in UI Integration with before/after. No engineering value / unit / verdict affected. |
| **ER-05 / ER-06** *(re-confirmed)* | One white PNG shared by the dark UI + white PDF; generation date absent on the direct `generate_*` sheet footers. | **R10** (presentation). | **RECORD (Class D).** UI phase: opt-in dark `draw_*` variant (geometry untouched); add a "จัดทำ <today>" footer token. |

**Regression invariant held:** `pytest` **80 passed, 0 skipped** (EV-09 added no
pytest test and no production code); EV-02…EV-09 runners **0 FAIL**.

**RELEASE DECISION: ✅ ENGINEERING RELEASE READY** — released as a **member-level
ACI 318M-08 design tool** + a **Building MODEL** (grid + single-storey tributary
vertical takedown + budget BOQ); **not** as a building structural-analysis
package. Every "REVIEW" / "MODEL" state is intentional and disclosed; no "PASS"
is shown without supporting evidence. **STOP after EV-09 — UI Integration is a
separate later phase.**

---

## 10. Items Not Yet Validated

Everything (Section 8). In particular:

- **All 47 importable calculation functions** — regression-pinned only,
  **0 independent references**.
- **8 BLOCKED interleaved compute paths** — `_render_beam_section`,
  `_render_beam_3_sect`, `_render_column`, `_render_slab_design`,
  `_render_isolated_footing`, `_render_pile_cap`, `_render_straight_stair`,
  `_render_u_shape_stair`, plus the `Wu` calculation inside
  `render_building_model` — cannot be validated as end-to-end numbers
  until a compute/render split makes them importable
  (**do not perform that split in a validation step**).
- **Nested footing helpers** `_elastic_reactions`, `_side`, `_s0` — not
  importable (declared inside `_render_*`).
- **Deflection / serviceability** (beam, slab, stair) — **not implemented**;
  nothing to validate.
- **Slenderness / P-Δ** (column) — **not implemented**.
- **Lateral load / seismic / wind** — **not implemented** anywhere.
- **Drawing geometry, PDF layout, UI** — out of scope by design.

---

## 11. Change Control

While validation work is in progress the calculation engine is **frozen**.

1. **No edit** to a formula, numeric constant, unit conversion, condition,
   early return, return value, function signature or engineering
   assumption in any Section-2 in-scope file — for a UI, report, drawing,
   convenience or "clean-up" reason.
2. A genuine engineering change (e.g. acting on a validation FAIL) is a
   **separate, explicitly-authorised step**, never folded into validation,
   and must carry:
   - the reviewed engineering justification,
   - the ACI / reference citation,
   - `pytest` **before**, the change, `pytest` **after**,
   - a side-by-side old-value / new-value table for every golden test that
     moves, updated in `docs/REGRESSION_BASELINE.md`.
3. A golden value is **never** edited just to make a test green
   (`docs/REGRESSION_BASELINE.md` "Refactoring rule").
4. Findings (Section 9) are recorded, prioritised (below) and left in place.

### Risk × Priority ranking (drives EV-02+ order, not any change)

**Engineering risk** — impact on a safety-relevant design result:

| Risk | Calculations |
|---|---|
| **CRITICAL** | `solve_continuous_beam`; beam `_flex_ksc` / `_required_as` / `_shear_check` / `_section_calc`; column `_calculate_pm_curve` + `_render_column` (ρg, φPn,max); slab `_as_flexure_ksc` / `_required_as_flexure`; footing `_flexure_as` + punching/one-way shear (BLOCKED); stair `_required_as_flexure` / `_as_flexure_ksc` |
| **HIGH** | ACI `beta1` / `rho_min*` / `rho_max*` / `phi_flexure` / `vc_beam*` / `as_min*`; `_beta1_ksc` / `_beta1_col_ksc` / `_rho_max_ksc`; `_whitney_area_centroid`, `_point_in_poly`; `_temp_steel_ratio` (×3); `_spacing_for` (×2); `_calculate_column_loads`; render `s_max` limits; `render_building_model` `Wu` |
| **MEDIUM** | `bar_area` / `bars_area` (table values); `rho_balanced`; `_col_bar_xy`; `_pile_coords`; `_auto_group_columns`; `estimate_building_boq` + `_beam_length_m` |
| **LOW** | `_bar_area`; `_parse_spacings`; `_grid_label_x`; `_column_labels`; `_panel_items` |

**Validation priority:**

- **P0 — validate before any results are used for real design:**
  every **CRITICAL** calculation above, plus the ACI **HIGH** primitives
  they depend on (`beta1`, `rho_min*`, `rho_max*`, `phi_flexure`,
  `vc_beam*`, `_beta1_ksc`, `_beta1_col_ksc`). Resolve **VF-04 / RB-3**
  (sampled peak) and **VF-07 / RB-7** (dual `β₁` threshold) as part of P0.
- **P1 — validate before broad release:** remaining **HIGH** items;
  `_calculate_column_loads` including the **VF-05** redistribution
  assumption; `_temp_steel_ratio` / `_spacing_for` (once per distinct
  implementation, **RB-5**); the BLOCKED column / footing / stair verdict
  assembly (needs the compute/render split first).
- **P2 — validate for completeness:** **MEDIUM** / **LOW** items;
  `_pile_coords` layout convention (**RB-6**); `estimate_building_boq`
  ratio basis (**VF-08**); dead-code decision (**VF-03**).

---

## 12. Regression Policy

- The **73-test** `tests/` suite is the regression baseline and is
  **unchanged by EV-01** (`pytest -q` → 73 passed before and after).
- Regression tests are **change detectors**, not validation. They stay.
- Validation cases live **separately** in `tests/validation/` and are
  clearly labelled. A validation case must **never** be created by copying
  a golden test and comparing the program to its own output
  (`docs/REGRESSION_BASELINE.md`, EV brief §12).
- New validation cases added in EV-02+ that carry a real independent
  reference **add** to the suite; the completion report for that step must
  state the new total and why it changed.
- If a validation case FAILs, the failure is investigated and reported —
  the engine is **not** edited to make it pass within the validation step
  (Section 11).

---

## Appendix A — Traceability (requirement → function → test → case → reference → result)

Format: `Requirement → function(s) → regression test → EV case ID →
reference status → validation status`.

```
ACI β1                → aci_318m.beta1 / get_beta1 / _beta1_ksc / _beta1_col_ksc
                       → test_aci_318m::test_beta1_*, test_beam_calc::test_beta1_ksc,
                         test_column_calc::test_beta1_col_ksc
                       → EV-ACI-001            → REFERENCE REQUIRED (Level C, ACI 10.2.7.3)  → NOT VALIDATED
ACI ρ_min flexure     → aci_318m.rho_min_flexure / _ksc / as_min_flexure / _ksc / calc_As_min
                       → test_aci_318m::test_rho_min_flexure*, test_as_min_flexure*
                       → EV-ACI-002            → REFERENCE REQUIRED (Level A + C, ACI 10.5.1) → NOT VALIDATED
ACI ρ_max (TC)        → aci_318m.rho_max_flexure / _rho_max_ksc
                       → test_aci_318m::test_rho_max_flexure, test_beam_calc::test_rho_max_ksc
                       → EV-ACI-003            → REFERENCE REQUIRED (Level A + C, ACI 10.3.4) → NOT VALIDATED
ACI φ (strain)        → aci_318m.phi_flexure
                       → test_aci_318m::test_phi_flexure_* (×4)
                       → EV-ACI-004            → REFERENCE REQUIRED (Level A + C, ACI 9.3.2)  → NOT VALIDATED
ACI Vc one-way        → aci_318m.vc_beam / vc_beam_ksc
                       → test_aci_318m::test_vc_beam, test_vc_beam_ksc
                       → EV-ACI-005            → REFERENCE REQUIRED (Level A + C, ACI 11.2.1.1)→ NOT VALIDATED
Bar areas             → aci_318m.bar_area / bars_area / _bar_area / REBAR
                       → test_aci_318m::test_bar_area, test_bars_area
                       → EV-ACI-006            → REFERENCE REQUIRED (Level A + C, table)      → NOT VALIDATED
Beam flexural cap.    → beam._flex_ksc (+ _beta1_ksc)
                       → test_beam_calc::test_flex_ksc
                       → EV-BEAM-001           → REFERENCE REQUIRED (Level A + C)             → NOT VALIDATED
Beam required As      → beam._required_as
                       → test_beam_calc::test_required_as_feasible / _infeasible
                       → EV-BEAM-002           → REFERENCE REQUIRED (Level A + C)             → NOT VALIDATED
Beam shear            → beam._shear_check (+ aci_318m.vc_beam)
                       → test_beam_calc::test_shear_check
                       → EV-BEAM-003           → REFERENCE REQUIRED (Level A + C, ACI 11.4)   → NOT VALIDATED
Beam section verdict  → beam._section_calc
                       → test_beam_calc::test_section_calc
                       → EV-BEAM-004           → REFERENCE REQUIRED (Level A + B)             → NOT VALIDATED
Beam full flow        → beam._render_beam_section / _render_beam_3_sect
                       → (none)
                       → EV-BEAM-005           → REFERENCE REQUIRED (Level B)                 → BLOCKED (interleaved)
Column P–M curve      → column._calculate_pm_curve / _whitney_area_centroid / _beta1_col_ksc
                       → test_column_calc::test_calculate_pm_curve_rect_anchor_points
                       → EV-COL-001            → REFERENCE REQUIRED (Level A anchors + Level B)→ NOT VALIDATED
Column design-point   → column._point_in_poly
                       → test_column_calc::test_point_in_poly
                       → EV-COL-002            → REFERENCE REQUIRED (Level A)                 → NOT VALIDATED
Column bar geometry   → column._col_bar_xy
                       → test_column_calc::test_col_bar_xy_rect / _circ
                       → EV-COL-003            → REFERENCE REQUIRED (Level A)                 → NOT VALIDATED
Column ρg / φPn,max / ties → column._render_column (interleaved)
                       → (none)
                       → EV-COL-004            → REFERENCE REQUIRED (Level A + C, ACI 10.3.6 / 10.9 / 7.10) → BLOCKED
Slab flexural As      → slab._as_flexure_ksc / _required_as_flexure
                       → test_slab_calc::test_as_flexure_ksc_* / test_required_as_flexure
                       → EV-SLAB-001           → REFERENCE REQUIRED (Level A + C)             → NOT VALIDATED
Slab min steel        → slab._temp_steel_ratio
                       → test_slab_calc::test_temp_steel_ratio
                       → EV-SLAB-002           → REFERENCE REQUIRED (Level A + C, ACI 7.12.2.1)→ NOT VALIDATED
Slab spacing          → slab._spacing_for
                       → test_slab_calc::test_spacing_for*
                       → EV-SLAB-003           → REFERENCE REQUIRED (Level C)                 → NOT VALIDATED
Slab classification / moments → slab._render_slab_design (interleaved)
                       → (none)
                       → EV-SLAB-004           → REFERENCE REQUIRED (Level B + C)             → BLOCKED
Footing flexure As    → footing._flexure_as
                       → test_footing_calc::test_flexure_as_* (×3)
                       → EV-FOOT-001           → REFERENCE REQUIRED (Level A + C, ACI 15.4)   → NOT VALIDATED
Footing pile layout   → footing._pile_coords
                       → test_footing_calc::test_pile_coords_layouts
                       → EV-FOOT-002           → REFERENCE REQUIRED (Level A geometry)        → NOT VALIDATED
Footing min steel     → footing._temp_steel_ratio
                       → test_footing_calc::test_temp_steel_ratio
                       → EV-FOOT-003           → REFERENCE REQUIRED (Level A + C, ACI 7.12)   → NOT VALIDATED
Footing shear / bearing / punching → footing._render_isolated_footing / _render_pile_cap (+ nested)
                       → (none)
                       → EV-FOOT-004           → REFERENCE REQUIRED (Level A + C, ACI 11.11 / 15.5) → BLOCKED
Stair flexural As     → stair._as_flexure_ksc / _required_as_flexure
                       → test_stair_calc::test_as_flexure_ksc* / test_required_as_flexure
                       → EV-STAIR-001          → REFERENCE REQUIRED (Level A + C)             → NOT VALIDATED
Stair min steel / spacing → stair._temp_steel_ratio / _spacing_for
                       → test_stair_calc::test_temp_steel_ratio / test_spacing_for
                       → EV-STAIR-002          → REFERENCE REQUIRED (Level A + C)             → NOT VALIDATED
Stair load / moment   → stair._render_straight_stair / _render_u_shape_stair (interleaved)
                       → (none)
                       → EV-STAIR-003          → REFERENCE REQUIRED (Level A)                 → BLOCKED
Continuous-beam solve → analysis.solve_continuous_beam / _beam_element_k
                       → test_analysis (×6)
                       → EV-ANLZ-001           → REFERENCE REQUIRED (Level A statics + Level B diagrams) → NOT VALIDATED
Continuous-beam governing extrema → analysis.solve_continuous_beam (Mu_pos / Mu_neg / Vu)
                       → test_analysis::test_two_equal_spans / _three_spans / _single_span
                       → EV-ANLZ-002           → REFERENCE REQUIRED (Level B, analytic peak + sampling bound) → NOT VALIDATED (VF-04)
Grid parsing / labels → building._parse_spacings / _grid_label_x / _column_labels / _panel_items
                       → test_building_calc (×7)
                       → EV-BLDG-001           → REFERENCE REQUIRED (Level A)                 → NOT VALIDATED
Gravity take-down     → building._calculate_column_loads
                       → test_building_calc::test_column_loads_full_grid / _removed_and_void
                       → EV-BLDG-002           → REFERENCE REQUIRED (Level A + B; document VF-05 drop rule) → NOT VALIDATED
Column grouping       → building._auto_group_columns
                       → test_building_calc::test_auto_group_columns / _empty
                       → EV-BLDG-003           → REFERENCE REQUIRED (Level A, rule-based)     → NOT VALIDATED
Factored slab load Wu → building.render_building_model (interleaved)
                       → (none)
                       → EV-BLDG-004           → REFERENCE REQUIRED (Level A)                 → BLOCKED
BOQ take-off          → boq.estimate_building_boq / _beam_length_m
                       → test_boq (×4)
                       → EV-BOQ-001            → REFERENCE REQUIRED (Level A + C ratio basis; VF-08) → NOT VALIDATED
```

---

## Appendix B — Validation Case Schema

Every EV validation case (from EV-02 onward) is one record:

| Field | Meaning |
|---|---|
| `Case ID` | `EV-<AREA>-<NNN>` — `AREA` ∈ ACI, BEAM, COL, SLAB, FOOT, STAIR, ANLZ, BLDG, BOQ |
| `Module` | source file + function(s) under validation |
| `Description` | the engineering quantity being checked, in one sentence |
| `Input` | complete, explicit input set (units stated) |
| `Expected Result` | the **independent** reference value(s) — never a program output |
| `Reference` | `Level A: <hand-calc worksheet ref>` / `Level B: <independent tool + worksheet ref>` / `Level C: <ACI clause>` / `REFERENCE REQUIRED` |
| `Tolerance` | acceptance type + value from Section 7 (`Numerical 1e-6` / `Engineering <justified band>` / `Discrete exact` / `Pass-Fail`) |
| `Actual Result` | the value RC CodePro returns for that input (filled at execution) |
| `Difference` | actual − expected (absolute and relative) |
| `Status` | `NOT VALIDATED` \| `PASS` \| `FAIL` \| `REVIEW` \| `BLOCKED` |
| `Notes` | assumptions, links to Findings (VF-/RB-/ER-), sampling bounds, etc. |

`Status` definitions:

- **NOT VALIDATED** — no independent reference yet (EV-01 state of every case).
- **PASS** — actual matches an independent reference within tolerance,
  and the verdict (if any) matches.
- **FAIL** — actual is outside tolerance, or the verdict disagrees.
  → record as a Finding; **do not edit the engine in the validation step**.
- **REVIEW** — the reference itself is uncertain, or the difference needs
  an engineer's judgement (e.g. a code-interpretation question).
- **BLOCKED** — the quantity cannot be reached without a compute/render
  split or other structural change that is out of scope for validation.

The Python placeholders in `tests/validation/` mirror this schema in
their docstrings and `pytest.skip` reason strings so EV-03 can turn each
into an executable case by filling `Expected Result` + `Reference` +
`Tolerance`.
