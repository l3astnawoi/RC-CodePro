# EV-02 — Completion Report

**Task:** build the independent Engineering Reference Cases for RC CodePro's
P0 calculations, per the EV-01 Validation Framework.
**Mode:** REFERENCE / VALIDATION DATA ONLY — no engine change, no finding fixed.
**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`

---

## 1. Reference cases created

**31 reference cases**, in `tests/validation/reference/cases/*.json`, in the
Appendix-B schema (`case_id / module / category / description / inputs /
reference_method / code_reference / expected / intermediate / tolerance /
notes / status`). No `actual_engine_result` field — EV-02 is independent
reference only.

| File | Cases | IDs |
|---|---|---|
| `aci_primitives.json` | 8 | `EV-ACI-001`, `EV-ACI-001M`, `EV-ACI-002…007` |
| `beam_flexure_shear.json` | 6 | `EV-BEAM-001…006` |
| `column_pm.json` | 5 | `EV-COL-001…005` |
| `continuous_beam.json` | 5 | `EV-ANLZ-001…005` |
| `slab_stair_footing.json` | 7 | `EV-SLAB-001/002`, `EV-STAIR-001/002`, `EV-FOOT-001/002/003` |

Plus the **executable runner** `tests/validation/run_ev02_validation.py`,
which loads those JSON cases, calls the **live engine** for the actual
value, and prints `Case / Expected / Actual / Diff / Tolerance / Status`.

**Latest run: 120 checks — 104 PASS, 0 FAIL, 11 REVIEW, 5 BLOCKED.**

## 2. P0 functions covered

| P0 group | Engine function(s) with an independent reference | Case IDs |
|---|---|---|
| P0-A ACI primitives | `aci_318m.beta1` / `get_beta1`, `rho_min_flexure`, `rho_min_flexure_ksc`, `phi_flexure`, `vc_beam`, `vc_beam_ksc`; `beam._beta1_ksc`, `beam._rho_max_ksc`, `column._beta1_col_ksc` | `EV-ACI-001..005`, `EV-ACI-001M` |
| P0-B Beam flexure + shear | `beam._flex_ksc`, `beam._required_as`, `aci_318m.calc_As_min`, `beam._shear_check` | `EV-BEAM-001..006` |
| P0-C Column P-M | `column._calculate_pm_curve` **anchors only** (`Po`, design cap, `Pnt` via the curve end-points), `column._col_bar_xy` | `EV-COL-001/002` (`003/004/005` BLOCKED) |
| P0-D Continuous beam | `analysis.solve_continuous_beam` — reactions, support moments, `Mu_neg`, `Vu`, `Mu_pos` | `EV-ANLZ-001..004` |
| P0-E Slab / Stair / Footing flexure | `slab._as_flexure_ksc`, `slab._temp_steel_ratio`, `slab._spacing_for`, `stair._as_flexure_ksc`, `footing._flexure_as` | `EV-SLAB-001`, `EV-STAIR-001`, `EV-FOOT-001` |
| P0-F Sampled-peak (VF-04) | `analysis.solve_continuous_beam` `Mu_pos_kgfm` vs analytic `wL²/8` | `EV-ANLZ-005` |
| P0-G Code-sensitive | `beta1` dual threshold (VF-07); two-way `vc1/vc2/vc3` form (footing); tie `s_max` form (column) | `EV-ACI-001M`, `EV-ACI-006`, `EV-ACI-007` |

≈ **24 distinct engine functions** now carry at least one independent
engineering reference (0 before EV-02).

## 3. Code references

Every ACI-linked case records `code_reference = {code, section, equation}`.
All target **ACI 318M-08** (the program's stated code); no newer edition
was silently substituted.

| Case | ACI 318M-08 section |
|---|---|
| `EV-ACI-001` / `-001M` | 10.2.7.3 (β₁) |
| `EV-ACI-002` | 10.5.1 (ρ_min) |
| `EV-ACI-003` | 10.3.4 (tension-controlled ρ_max) |
| `EV-ACI-004` | 9.3.2 (φ from ε_t) |
| `EV-ACI-005` | 11.2.1.1 Eq. 11-3 (V_c) |
| `EV-ACI-006` | 11.11.2.1 Eqs 11-31/32/33 (two-way v_c) |
| `EV-ACI-007` | 7.10.5.2 (tie spacing) |
| `EV-BEAM-001..003`, `EV-SLAB-001`, `EV-STAIR-001`, `EV-FOOT-001` | 10.2.7 / 10.3.4 / 9.3.2 / 10.5.1 / 15.4 |
| `EV-BEAM-004..006` | 11.2.1.1 / 11.4.7 / 11.4.5.3 |
| `EV-COL-001/002` | 10.3.6.1 / 10.3.6.2 |
| `EV-FOOT-002` | 11.11.1.2 / R11.11 / 15.5 — **CODE REFERENCE TO VERIFY** for the `3.464` literal |
| `EV-SLAB-002` | Ch. 13 moment-coefficient method — **CODE REFERENCE TO VERIFY** (edition / table) |
| `EV-ANLZ-*` | structural analysis (three-moment theorem), not a code clause |

## 4. Independent calculation methods

| Method | Where | Independence argument |
|---|---|---|
| **Hand ACI equations** re-typed from the code text | `reference_aci.py`, `reference_flexure.py`, `reference_shear.py` | no import of `utils.aci_318m` — coefficients (0.85, 0.17, 0.66, 0.083, 0.33, 0.25/1.4, 0.375) written literally from ACI 318M-08 |
| **Three-Moment Theorem (Clapeyron) + statics** | `reference_analysis.py` | a *different formulation* from the engine's direct-stiffness Euler-Bernoulli element assembly; solves `M_{i-1}L_a + 2M_i(L_a+L_b) + M_{i+1}L_b = −(wL_a³/4 + wL_b³/4)` then reactions by free-body. Never calls `solve_continuous_beam()`. |
| **Analytic parabola on a sampling grid** | `reference_analysis.sampled_peak_analysis` | evaluates the *exact* `M(x) = wx(L−x)/2` on a reproduced 200-pt grid to predict the engine's sampled peak — the moment solution is analytic, only the grid is shared |
| **Closed-form axial anchors** | `reference_column.py` | `Po = 0.85f'c(Ag−Ast)+fyAst`, `cap = 0.80·0.65·Po`, `Pnt = −fyAst` — exact end-points, no strain-compatibility loop reused |

The no-circularity rule holds: `import`-graph check — every
`reference/*.py` imports only `math` / `numpy`; the engine is imported
**only** in `run_ev02_validation.py`.

## 5. Tolerance decisions (per case, with rationale)

| Type | Applied to | Value | Rationale |
|---|---|---|---|
| **Numerical (exact)** | β₁, ρ_min, ρ_max, φ, V_c, two-way v_c, tie s_max | rel `1e-9`, abs `1e-12` | closed-form piecewise-linear / algebraic; only float dust |
| **Numerical** | `_flex_ksc`, `_required_as`, `_shear_check`, `_as_flexure_ksc`, `_flexure_as`, continuous-beam reactions & support moments | rel `1e-6`, abs `1e-3`…`1e-6` | closed-form quadratic inversion / linear solve; sub-ppm agreement expected |
| **Numerical (bar-area rounding)** | column `Po` / cap / `Pnt` | rel `5e-6` | engine's `REBAR` table stores `round(πd²/4, 2)` mm²; reference uses unrounded — a ≈ 2 × 10⁻⁶ relative offset in `Ast`, flagged not slacked |
| **Discrete / exact** | `feasible` flags, verdicts, bar-spacing rounding step, s_max branch flag, `governed_by` | exact equality | no tolerance is meaningful |
| **Engineering (sampled)** | continuous-beam `Mu_pos` vs analytic-on-grid | rel `3e-3` | the engine grid is `max(80·n_span, 200)` pts + support clustering; the reference grid is 200 pts — the residual is grid *alignment*, bounded and documented |
| **Engineering (VF-04)** | `Mu_pos` exact-minus-engine gap | `0 ≤ gap ≤ (w/2)(h/2)²` | the acceptance is that the non-conservative sampling error is **bounded and attributable to sampling**, not that it is zero |
| **Engineering — TBD** | `EV-ACI-001M` (β₁ gap), `EV-ACI-005` (0.53 vs exact), `EV-FOOT-002` (circular perimeter), `EV-SLAB-002` (two-way coeff) | `value: "TBD"` + `status: REVIEW` | these document a modelling choice or an unresolved code-mapping question; EV-03 decides acceptability. No tolerance was chosen to make the engine pass. |

## 6. REFERENCE_READY cases — 23

`EV-ACI-001, 002, 003, 004, 005, 006, 007` ·
`EV-BEAM-001, 002, 003, 004, 005, 006` ·
`EV-COL-001, 002` ·
`EV-ANLZ-001, 002, 003, 004, 005` ·
`EV-SLAB-001` · `EV-STAIR-001` · `EV-FOOT-001`

All 23 were run against the live engine — **every numerical check passed**
within its per-case tolerance.

## 7. REVIEW cases — 3 (case-level); 11 REVIEW lines in the runner

Case-level: `EV-ACI-001M` (β₁ dual threshold, VF-07) · `EV-SLAB-002`
(two-way moment coefficients — equation verified, coefficient source
required) · `EV-FOOT-002` (circular-pile punching perimeter, VF-09).

The runner additionally emits REVIEW annotation rows for VF-10, VF-11,
VF-12, and the `Mu_pos` vs exact-peak note on each `EV-ANLZ` case
(VF-04). These are not failures — they are the findings in §10, attached
to the case that surfaced them.

## 8. BLOCKED cases — 5

| Case | Why BLOCKED (not skipped-to-hide) |
|---|---|
| `EV-COL-003` / `-004` / `-005` | interior P–M points need an independent strain-compatibility solver whose own correctness must first be established (hand-checked balanced point / published chart / second tool). Not fabricated. Anchors `EV-COL-001/002` delivered. |
| `EV-STAIR-002` | stair load build-up (`W_u`, `M_u`) is assembled inside `_render_straight_stair` / `_render_u_shape_stair` — no importable entry point (needs the compute/render split, out of EV-02 scope). |
| `EV-FOOT-003` | isolated-footing / pile-cap full chain (bearing, one-way & two-way shear, flexure assembly) is render-interleaved; nested `_elastic_reactions` / `_side` / `_s0` not importable. Component equations *are* covered (`EV-ACI-005/006`, `EV-FOOT-001`). |

## 9. Discrepancies discovered

**Zero numerical FAILs.** Every reachable engine calculation matched its
independent reference within tolerance. The differences that *were*
observed are all bounded and expected:

| Observation | Magnitude | Direction | Verdict |
|---|---|---|---|
| `solve_continuous_beam` `Mu_pos` vs exact `wL²/8` | ≈ 0.0025 % (single span: 0.114 kgf·m of 4500) | **non-conservative** (under-estimates) | within the parabola sampling bound; VF-04, `REVIEW` |
| MKS `vc_beam_ksc` `0.53` vs exact SI-equivalent `0.5429` | ≈ 2.37 % | **conservative** (under-estimates capacity) | standard ACI-MKS rounding; VF-12, `NOTE` |
| MKS `β₁` (280 ksc break) vs code-consistent (28 MPa) | ≤ 0.0058 in β₁, only for f'c > 280 ksc (≈ 27.5 MPa) | β₁ slightly low above the break | second-order on φM_n; VF-07, `REVIEW` |
| column `Po` (bar-area table rounding) | ≈ 5 × 10⁻⁷ relative | negligible | `round(πd²/4, 2)` in `REBAR`; documented |

None of these is an engine error; each is a documented modelling choice.

## 10. Engineering findings (RECORD ONLY — not fixed)

Added to `docs/ENGINEERING_VALIDATION.md` §9.4:

- **VF-09** — circular-pile punching perimeter literal `3.464·Dp + π·d`
  (`modules/footing.py:957`); ACI 11.11.1.2 gives `π(Dp + d)`.
  `3.464 ≈ 2√3`, derivation unclear → **CODE REFERENCE TO VERIFY**. The
  square-column perimeter `4(c + d_avg)` in the same module is correct.
- **VF-10** — column tie-spacing check computes the correct ACI 7.10.5.2
  `s_max = min(16 db, 48 d_tie, least dim)` but then only checks
  `s_max ≥ 5 cm`; it never compares a *provided* spacing to `s_max`.
- **VF-11** — `_flex_ksc` / `_as_flexure_ksc` / `_required_as_flexure`
  apply `φ = 0.90` with no internal tension-controlled guard; correct
  only while the caller enforces `ρ ≤ ρ_max` (beam does).
- **VF-12** — MKS `V_c` uses the traditional `0.53√f'c b d`; the exact
  SI-equivalent coefficient is `≈ 0.5429`, so the engine form is
  ≈ 2.4 % conservative (NOTE, not a defect).

Confirmed & quantified (already logged): **VF-04** (sampled peak — bound
and direction now measured), **VF-07** (dual β₁ threshold — gap now
measured), **RB-1** (infeasible sentinel `inf` vs `None` — observed again
in `_flexure_as`).

## 11. Production calculation files changed?

**NO.**

- `git diff HEAD -- utils/aci_318m.py utils/analysis.py utils/boq.py` →
  **empty**; MD5 of each == `git show HEAD:` blob
  (`f9f479fa…`, `c4dd7cca…`, `c6da98bc…`).
- `modules/*.py` show only the pre-existing STEP 2–15 UI diff;
  `git diff --stat HEAD` totals are byte-identical to the pre-EV-01/EV-02
  snapshot (`12 files changed, 1447 insertions(+), 804 deletions(-)`).
- No `Edit`/`Write` was issued against any production file in EV-02.
- No existing test or golden value was modified. No destructive git
  command was used.

All EV-02 output is new, untracked files under
`tests/validation/reference/`, `tests/validation/run_ev02_validation.py`
and `docs/`.

## 12. Existing regression result

```
py -3 -m pytest -q   →   73 passed in ~1.4 s   (0 failed, 0 skipped)
```

Unchanged. The EV-02 validation runner is a standalone script, **not** a
pytest module, so the 73-test baseline is untouched.

- Regression tests: **73 passed**
- EV-02 validation checks: **104 passed, 0 failed, 11 review, 5 blocked**
  (`py -3 tests/validation/run_ev02_validation.py`)

## 13. Recommended EV-03 scope

1. **Compare, don't just reference.** Wire the EV-02 runner (or per-area
   `test_*` modules built from the JSON) into `pytest` behind a marker
   (e.g. `-m validation`) so the P0 checks run in CI *without* changing
   the default 73-count. Report `regression 73 / validation X·Y·Z`.
2. **Resolve the 3 REVIEW cases** with an engineer's decision:
   - VF-07 — accept the 280 ksc β₁ break, or converge the MKS helpers on
     the code-consistent form (an engine change → its own reviewed step
     with before/after golden diff).
   - VF-09 — confirm the intended circular-pile critical perimeter; if
     `π(Dp + d)` is correct, quantify the capacity impact of `3.464·Dp`.
   - VF-05-2 (`EV-SLAB-002`) — identify the two-way moment-coefficient
     table (edition, `m` threshold) the engine uses, then build a Level-B
     moment reference.
3. **Unblock the column P–M interior** (`EV-COL-003/004/005`): build an
   independent layer/fibre strain-compatibility solver, *verify it first*
   against a hand-checked balanced point and a published interaction
   chart, then use it as the Level-B reference for 3–5 interior points.
4. **Unblock the render-interleaved chains** (`EV-STAIR-002`,
   `EV-FOOT-003`, and the EV-01 `BLOCKED` stubs): this needs a
   compute/render split — a **separate, explicitly authorised**
   refactor step (not a validation step), each extracted helper landing
   with its own regression golden values.
5. **P1 references:** `_temp_steel_ratio` (once — RB-5), `_spacing_for`
   edge cases, `_pile_coords` geometry for all layouts (RB-6),
   `_calculate_column_loads` tributary areas incl. the VF-05 removed-
   column case, `estimate_building_boq` take-off arithmetic + ratio basis
   (VF-08).
6. **VF-04 remedy** (engine change, separate step): evaluate `M(x)` at
   each span's interior stationary point analytically, or densify the
   sampling grid there; update the `test_analysis.py` golden values with
   a documented before/after.

---

## Final checklist (EV-02 acceptance)

- [x] EV-01 framework used as the basis (case IDs, schema, matrix)
- [x] P0 scope prioritised (P0-A…P0-G)
- [x] Independent reference methodology defined (Levels A/B/C, no-circularity)
- [x] ACI 318M-08 mapping recorded where verifiable; "CODE REFERENCE TO VERIFY" elsewhere
- [x] β₁ case built (`EV-ACI-001` + `-001M` for VF-07)
- [x] V_c case built (`EV-ACI-005`, SI + MKS + exact-equivalent)
- [x] tie-spacing case built (`EV-ACI-007`) + VF-10 recorded
- [x] Beam flexure reference built (`EV-BEAM-001/002/003`)
- [x] Beam shear reference built (`EV-BEAM-004/005/006`)
- [x] Column P-M: anchors built (`EV-COL-001/002`); interior BLOCKED with reason
- [x] Continuous-beam reference built (`EV-ANLZ-001..004`, three-moment method)
- [x] Sampled-peak case built (`EV-ANLZ-005`, VF-04 quantified)
- [x] Slab flexure reference built (`EV-SLAB-001`; two-way coeff = REVIEW)
- [x] Stair flexure reference built (`EV-STAIR-001`; load model BLOCKED, VF-06 noted)
- [x] Footing flexure reference built (`EV-FOOT-001`); punching examined (`EV-ACI-006` form + `EV-FOOT-002` VF-09) / full chain BLOCKED
- [x] Tolerance defined per case, each with a rationale; "TBD" + REVIEW where undecided
- [x] No fabricated reference values (BLOCKED / REFERENCE REQUIRED used instead)
- [x] References never call a production calculation function
- [x] Validation is not circular (three-moment ≠ direct-stiffness; ACI text re-typed)
- [x] Production calculation files NOT modified
- [x] Existing regression tests NOT modified — `pytest -q` = 73 passed
- [x] EV-02 completion report created

**EV-02 is complete. EV-03 is not started.**
