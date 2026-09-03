# EV-07 — Completion Report
## Stair Engineering Validation & Corrective Fix

**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`
**Rule applied:** *fix only what the validation proves* — minimal,
test-first, no feature creep. Validate the **actual structural
idealization** (an inclined one-way slab), not "stair = beam".

---

## 1. Scope

**IN:** `modules/stair.py` — `_render_straight_stair` (straight flight),
`_render_u_shape_stair` (U-shape / half-turn flight), and the pure helpers
`_temp_steel_ratio`, `_required_as_flexure`, `_as_flexure_ksc`,
`_spacing_for`; the stair-relevant part of `utils/aci_318m.py`.

**OUT (per brief §14–19 — NOT to be added):** one-way shear, development /
anchorage length, support (negative) moment + top steel, landing-slab
design, continuity, deflection, crack control, any new stair type.

**New EV-07 artifacts (untracked, non-production):**
`tests/validation/reference/reference_stair_ev07.py` (independent,
`math`-only), `tests/validation/run_ev07_stair.py` (executable runner,
not a pytest module).

**Production change:** `modules/stair.py` only. Regression tests added to
`tests/test_stair_calc.py` (2 new functions).

## 2. Baseline

```
py -3 -m pytest -q                          -> 78 passed, 0 skipped
py -3 tests/validation/run_ev02_validation.py --brief -> 120: 104 PASS, 0 FAIL
py -3 tests/validation/run_ev03_beam.py --brief       -> 127: 107 PASS, 0 FAIL
py -3 tests/validation/run_ev04_slab.py --brief       -> 77:  58 PASS, 0 FAIL
py -3 tests/validation/run_ev05_footing.py --brief    -> 67:  42 PASS, 0 FAIL
py -3 tests/validation/run_ev06_column.py --brief     -> 87:  60 PASS, 0 FAIL
py -3 tests/validation/run_ev07_stair.py              -> 70:  37 PASS, 3 FAIL,
                                                           30 REVIEW  (pre-fix)
```

The 3 pre-fix FAILs (phase H) are the proven defect — see §21 / §23.

## 3. Implementation map

| Function | Kind | Purpose |
|---|---|---|
| `_temp_steel_ratio(fy_MPa)` | IMPLEMENTED (pure, tested) | ACI 7.12.2.1 shrinkage/temp ratio |
| `_required_as_flexure(Mu_kNm, b, d, fc, fy)` | IMPLEMENTED (pure, tested) | SI singly-reinforced As; **fixed φ = 0.90**; None/False when infeasible |
| `_as_flexure_ksc(Mu_kgfm, b, d, fc, fy)` | IMPLEMENTED (pure, tested) | MKS singly-reinforced As; **fixed φ = 0.90**; `(0, True)` for `Mu ≤ 0`; `(None, False)` infeasible — **functionally == `slab._as_flexure_ksc`** |
| `_spacing_for(Ab, As_req, s_max)` | IMPLEMENTED (pure, tested) | bar spacing, 2.5 cm rounding — **functionally == slab** |
| `_beta1_ksc` / `_rho_max_ksc` | **ADDED by EV-07** (pure, tested) | MKS β₁ / tension-controlled ρ_max |
| `render_stair_module` | UI ONLY | type routing |
| `_render_straight_stair()` | IMPLEMENTED (interleaved / BLOCKED) | MKS; `Lx = N·T/100`; `DL_waist = (t/100)·2400/cos θ`; `DL_steps = ((R/100)/2)·2400`; `Wu = 1.2 DL + 1.6 LL`; `Mu = Wu·Lx²/8`; `_as_flexure_ksc`; temp steel; spacing verdict |
| `_render_u_shape_stair()` | IMPLEMENTED (interleaved / BLOCKED) | SI core; `t_avg = t/cos θ + R/2`; `L = L_flight + L_land`; `Wu = 1.2·max(flight_DL, landing_DL) + 1.6 LL`; `Mu = Wu·L²/8`; `_required_as_flexure`; strength + min + temp + spacing verdict |

**UNDER_CONSTRUCTION** (`st.info` only, no calculation): L-shape,
slabless, free-standing, spiral.

## 4. Geometry (phase A)

Straight flight reconstructed from the engine's literals and checked
against the independent reference:

| Quantity | Result |
|---|---|
| horizontal span `Lx = N·T/100` [m] | **PASS** rel < 1e-9 |
| slope `θ = atan2(R, T)` [deg] | **PASS** rel < 1e-9 |
| effective depth `d = t − cov − db/2` [cm] | **PASS** rel < 1e-9 |

**Span basis:** the straight flight is idealised as an **inclined one-way
slab** spanning the **horizontal projection** `Lx`. Loads are per
horizontal square metre; `Mu = Wu·Lx²/8`. The standard simplified stair
model — **not** a beam. (`d` uses the correct `−db/2` convention.)

## 5. Self-weight (phase B)

| Quantity | Result |
|---|---|
| `DL_waist = (t/100)·2400 / cos θ` [kgf/m²] (waist loaded on the **sloping** surface) | **PASS** rel < 1e-9 |
| `DL_steps = ((R/100)/2)·2400` [kgf/m²] (triangular step prism, `R/2` average height) | **PASS** rel < 1e-9 |

Concrete unit weight = the literal `2400 kgf/m³` (MKS convention,
identical to beam / slab / footing). SI `24 kN/m³ = 2446.5 kgf/m³`, so
`sw` is ≈ 1.9 % low on the DL term. **NOTE (R8)** — not a defect.

**U-shape:** `t_avg = t/cos θ + R/2` — the same total DL as
`DL_waist + DL_steps`, factored as one equivalent uniform thickness.
Verified.

## 6. Loads (phase C)

`Wu = 1.2·(DL_waist + DL_steps + SDL) + 1.6·LL` (ACI 9.2) — verified
rel < 1e-9 for the default and for self-only / LL-dominant / zero-LL
variants. U-shape: `Wu = 1.2·max(flight_DL, landing_DL) + 1.6·LL`.

## 7. Load application (phase C)

- Straight: loads are per **horizontal** square metre (`Wu` in kgf/m² is
  numerically the line load on a 1 m strip, kgf/m). The waist's slope is
  accounted for by the `1/cos θ` factor on its self-weight, **not** by
  changing the span. Correct.
- U-shape: `kgf/m² → kN/m²` via `KGF_TO_KN`, then `Mu` in kN·m/m; the
  detailed table converts back with `KN_TO_KGF`. No conversion
  discrepancy (§19).
- **No concentrated / patch load** input — NOT IMPLEMENTED.

## 8. Moment (phase D)

`Mu = Wu·Lx²/8` (straight) / `Wu·L²/8` (U-shape) — **simply-supported
single span**. Verified rel < 1e-9 for default / short (`N = 4`) / long
(`N = 20`). Units: straight kgf·m per strip; U-shape kN·m/m.

## 9. Support condition (phase D)

**SIMPLY SUPPORTED single span** (`Mu = wL²/8`). No continuity, no
negative / support moment, no top steel, no landing-support reaction, no
fixed-end. **NOT IMPLEMENTED (R9 scope).** Exact for a genuinely
simply-supported flight; a continuous flight's support region is
under-designed. Not added.

## 10. Shear (phase E)

**NOT IMPLEMENTED.** Neither render performs a one-way shear check
(`Vu ≤ φVc`). Consistent with the slab module (EV-04). For a typical
inclined one-way slab / stair, `0.17·λ·√f'c·bw·d` comfortably exceeds
`Wu·Lx/2` — but the **check is absent**. **R9 scope.** Not added.
`sp_main_ok` etc. are spacing checks, not shear. **No false-PASS**: there
is no computed shear result that is ignored — the check simply does not
exist.

## 11. Flexure (phase F)

`_as_flexure_ksc` (straight, MKS) vs `reference_stair_ev07._flex_chain_ksc`
and `_required_as_flexure` (U-shape, SI) vs `_flex_chain_si` — independent
Whitney block + ACI 9.3.2 φ chain:

| Case | Result |
|---|---|
| light / EV-02 STAIR-001 input / moderate strip | **PASS** rel < 1e-6 |
| heavy (near / past `As_max`, `d = 5.2 cm`) | **PASS** rel < 1e-6; reference reports `εₜ < 0.005` → φ_code < 0.90 → **VF-STAIR-01 evidence** |
| zero moment | **PASS** — `(0.0, True)` |
| infeasible (`disc < 0`) | **PASS** — `(None, False)`; both renders `st.error` + `return` |
| U-shape SI moderate / zero / infeasible | **PASS** rel < 1e-6 / exact |

## 12. φ (phase F)

Both stair flexure helpers apply a **fixed φ = 0.90** with **no
tension-controlled guard** — byte-identical to the slab helpers
(EV-04 VF-11-SLAB). ACI-correct φ for `εₜ` = 0.001 / 0.0035 / 0.006 is
0.65 / 0.777 / 0.90. The helpers **always** return `As` sized at
φ = 0.90; only the **EV-07 ductility gate** (`As ≤ As_max`, §20) keeps the
design inside the φ = 0.90 domain.

## 13. As_min (phase G)

- Straight: `As_temp_min = temp_ratio·b·t`; `As_main = max(As_req,
  As_temp_min)` — the minimum **is** applied to the main-steel value.
- U-shape: `As_min = temp_ratio·b·t`; `main_min_ok = As_prov_main ≥
  As_min` **and** `temp_min_ok = As_prov_temp ≥ As_min` — **both in the
  verdict**.
- `_temp_steel_ratio` matches the reference rel < 1e-9 for
  `fy = 2400 / 4000 / 5000 ksc`.

## 14. Temperature steel (phase G)

`_temp_steel_ratio` (ACI 7.12.2.1) validated (§13). Straight:
`temp_ok = 7.5 ≤ S_temp ≤ min(5t, 45)` **in the verdict**. U-shape:
`temp_min_ok` + `sp_temp_ok` **in the verdict**.

## 15. Spacing (phase G)

`_spacing_for` (2.5 cm rounding) — verified exact for safe / tiny-As /
zero-As / huge-As cases.

- **Straight:** `main_ok = 7.5 ≤ S_main ≤ min(3t, 45)`; `temp_ok = 7.5 ≤
  S_temp ≤ min(5t, 45)`. Discrete. The 7.5 cm lower bound catches gross
  over-reinforcement indirectly (as in slab).
- **U-shape:** the **user** provides `main_sp` / `temp_sp` (widget-capped
  5–45 cm); `sp_main_ok = main_sp ≤ min(3t, 450)`, upper bound only —
  **VF-STAIR-02** (no minimum-clear-spacing / ACI 7.6.1 check). R9,
  RECORD, no fix.
- **VF-SLAB-03** (shared `_spacing_for` 2.5 cm floor can under-provide
  when `As_req > Ab·40`) is present here too — NOT reachable as an unsafe
  stair verdict (`S = 2.5 < 7.5` rejected by `main_ok`). RECORD.

## 16. Development / anchorage (phase J)

**NOT IMPLEMENTED.** No development / anchorage length, no bar cut-off, no
hook check. Engineering impact: the user must detail bar anchorage into
the supports / landing per ACI Ch. 12 externally. Not added.

## 17. Stair configuration (phase J)

| Type | Status |
|---|---|
| Straight flight | **IMPLEMENTED** (`_render_straight_stair`) |
| U-shape / half-turn | **IMPLEMENTED** (`_render_u_shape_stair`) |
| L-shape, slabless, free-standing, spiral | **UNDER_CONSTRUCTION** (`st.info` only) |
| dog-leg / scissor / helical / cantilever | NOT IMPLEMENTED |

No support / top / landing reinforcement in either implemented type —
both design a **single simply-supported span for positive midspan moment
only**.

## 18. False-PASS audit (phase H / J)

| Check | computed? | in `passed`? (pre-EV-07) | in `passed`? (post-EV-07) |
|---|---|---|---|
| straight: `main_ok` (main spacing) | yes | **yes** | yes |
| straight: `temp_ok` (temp spacing) | yes | **yes** | yes |
| straight: `As_prov ≥ As_main` | yes (display) | **implicit** (`_spacing_for` over-provides) | implicit |
| straight: **`As ≤ As_max`** (ductility) | **no** | — | **yes (FIX)** |
| U-shape: `main_req_ok` (strength) | yes | **yes** | yes |
| U-shape: `main_min_ok` / `temp_min_ok` | yes | **yes** | yes |
| U-shape: `sp_main_ok` / `sp_temp_ok` | yes | **yes** | yes |
| U-shape: **`As ≤ As_max`** (ductility) | **no** | — | **yes (FIX)** |
| infeasible section (`disc < 0`) | yes | `st.error` + `return` (both) | unchanged |
| one-way shear | **no** (not implemented) | — | — |

Display `FAIL → REVIEW` badge (STEP 14): the `passed` boolean, the
per-row table, the `fails` / `reasons` list and `st.error` are
**unchanged** — only the top badge wording was softened (identical to the
slab module). **R10 — no engineering result is masked.**

## 19. Unit audit (phase A–D)

- **Straight:** MKS-native — `R`, `T`, `t`, `cov` in cm; `f'c`, `fy` in
  ksc; `Wu` in kgf/m² (= kgf/m on a 1 m strip); `Mu` in kgf·m per strip;
  `_as_flexure_ksc` MKS. Matched the reference rel < 1e-9.
- **U-shape:** `f'c = fc_ksc·0.0980665`, `fy = fy_ksc·0.0980665` (MPa);
  `Wu_kg` [kgf/m²] `→ Wu` [kN/m²] via `KGF_TO_KN`; `Mu` [kN·m/m];
  detailed table converts back with `KN_TO_KGF`. `_required_as_flexure`
  SI (`Mu` in kN·m, `b`, `d` in mm, `f'c`, `fy` in MPa). Matched
  rel < 1e-6.
- **No R2 conversion finding.**

## 20. Boundary matrix (phase F / G / H / I)

Geometry (`d = 0` → `st.error` + `return`), load (self-only / LL-dominant
/ zero-LL), moment (short / long span), flexure (zero / infeasible /
near-`As_max`), `As_min` (via `max()`), spacing (safe / `s_max` cap /
2.5 floor), verdict (default PASS / over-reinforced FAIL). Invalid
inputs: `_as_flexure_ksc(f'c = 0)` / `_required_as_flexure(f'c = 0)` →
`ZeroDivisionError`, blocked upstream by `st.number_input(min_value)` —
**VF-STAIR-03 (R9)**, unreachable, no fix.

## 21. Findings

| # | Finding | Root cause | Conservatism |
|---|---|---|---|
| 1 | **VF-STAIR-01** — `As ≤ As_max` / tension-controlled limit absent from **both** stair verdicts; `φ = 0.90` hardcoded in the flexure helpers | **R3** | **NON-conservative FALSE PASS** (straight, proven reachable) |
| 2 | Simply-supported single span; no support / top / landing steel; no continuity | **R9 scope** | NOT IMPLEMENTED |
| 3 | One-way shear check absent | **R9 scope** | NOT IMPLEMENTED |
| 4 | **VF-STAIR-02** — U-shape spacing check is upper-bound only (no min clear spacing) | **R9 scope** | RECORD |
| 5 | **VF-STAIR-03** — `f'c = 0` etc. → `ZeroDivisionError` | **R9** | UI-blocked, unreachable |
| 6 | **VF-06** (re-confirmed) — straight vs U-shape DL factoring differs; U-shape `max(flight, landing)` over the whole span | **R8** | **conservative** (U-shape landing region) |
| 7 | Display `FAIL → REVIEW` badge (STEP 14) | **R10** | no calc / verdict / failure-message change |
| 8 | self-weight `2400 kgf/m³` | **R8** | ≈ 1.9 % low on DL |
| 9 | `_as_flexure_ksc` / `_spacing_for` functionally == slab (RB-5) | **R9 maintenance** | validated once |

## 22. Root causes

- **R3 (production defect, fixed):** #1 — VF-STAIR-01.
- **R9 (scope limitation / NOT IMPLEMENTED / unreachable):** #2, #3, #4,
  #5, #9.
- **R8 (conservative approximation):** #6, #8.
- **R10 (UI / presentation):** #7.

## 23. Production fixes  (`modules/stair.py` ONLY — finding #1)

**Root cause:** the mandatory tension-controlled / maximum-reinforcement
limit (ACI 10.3.4; `εₜ ≥ 0.004` per 10.3.5) was **absent from both stair
verdicts**. The flexure helpers apply a fixed `φ = 0.90`, valid only
while the waist stays tension-controlled.

| Location | Change |
|---|---|
| module level | **+** `_beta1_ksc(fc_ksc)` and `_rho_max_ksc(fc_ksc, fy_ksc)` — byte-identical to `modules/beam.py` / `modules/slab.py` (already EV-02 `EV-ACI-003` + EV-03 / EV-04 validated); **+** `rho_max_flexure` in the `utils.aci_318m` import (for the SI U-shape) |
| `_render_straight_stair` | compute `As_max_main = _rho_max_ksc(fc, fy)·b·d`; `ductile_ok = As_main ≤ As_max_main`; **`passed = main_ok and temp_ok and ductile_ok`**; + a DESIGN-CHECKS row, a `st.warning`, a `fails` message |
| `_render_u_shape_stair` | compute `As_max_main = rho_max_flexure(fc, fy)·b·d`; `ductile_ok = As_prov_main ≤ As_max_main`; **add `and ductile_ok` to `passed`**; + a DESIGN-CHECKS row, a `reasons` message; fold into the first DESIGN-SUMMARY chip |

**Not changed:** no formula, numeric constant, unit conversion,
`_as_flexure_ksc`, `_required_as_flexure`, `_spacing_for`,
`_temp_steel_ratio`; no `utils/*` (only an **import** of the already-
validated `rho_max_flexure`); no other module; no `modules/beam.py` /
`slab.py` / `footing.py` (EV-03 / EV-04 / EV-05 fixes intact); no
`modules/column.py`; no golden value.

**Demonstration (proven FALSE PASS → FAIL):** straight flight
`R 17.5 / T 28 / N 10`, `t = 8 cm`, `cov = 2`, `f'c 240`, `fy 4000`,
`SDL 300`, `LL 615 kgf/m²`, DB16 main → `Lx = 2.80 m`,
`Mu = 1 830 kgf·m/m`, `As_main = 12.9 cm²/m`, `As_max = 8.5 cm²/m`,
`εₜ = 0.0022 < 0.004` (ACI 10.3.5 violated), `φ` should be 0.67 not 0.90,
`S_main = 15 cm` in `[7.5, 24]`. Pre-fix engine verdict **PASS**;
post-fix **FAIL** (`As > As,max — not tension-controlled`).

## 24. Regression

**Test-first (§25):** the runner's phase-H checks (source + reconstructed
verdict) were confirmed **FAIL** against the pre-fix engine, then **PASS**
after the fix. Two new golden tests for the new helpers.

```
py -3 -m pytest -q   ->   80 passed, 0 failed, 0 skipped
```

| Suite | Count |
|---|---|
| Existing regression (unchanged) | **78 passed** — every prior golden value identical (73 + 2 beam + 2 slab + 1 footing) |
| New EV-07 stair regression | **+2 passed** — `tests/test_stair_calc.py::test_beta1_ksc`, `test_rho_max_ksc` |
| **Total pytest** | **80 passed** |

## 25. Cross-module re-validation

| Suite | Result | Δ |
|---|---|---|
| `pytest -q` | **80 passed** | +2 (stair helper tests) |
| EV-02 | **120 — 104 PASS, 0 FAIL** | unchanged |
| EV-03 beam | **127 — 107 PASS, 0 FAIL** | unchanged |
| EV-04 slab | **77 — 58 PASS, 0 FAIL** | unchanged |
| EV-05 footing | **67 — 42 PASS, 0 FAIL** | unchanged |
| EV-06 column | **87 — 60 PASS, 0 FAIL** | unchanged |
| EV-07 stair | **70 — 40 PASS, 0 FAIL, 30 REVIEW, 0 BLOCKED** | new |

`utils/aci_318m.py` / `utils/analysis.py` / `utils/boq.py` byte-identical
to HEAD. `modules/beam.py` / `slab.py` / `footing.py` / `column.py` /
`building.py` unchanged from EV-06. `modules/stair.py` +52 ins / +5 del,
in `_beta1_ksc` / `_rho_max_ksc` + the two render verdicts. No destructive
git.

## 26. Remaining REVIEW

VF-STAIR-02 (U-shape spacing upper-bound only, R9), VF-STAIR-03 (`f'c = 0`
guard, R9 / UI-blocked), VF-06 (straight-vs-U DL factoring, R8
conservative), the STEP-14 `FAIL → REVIEW` badge (R10 — no result
masked), self-weight `2400` (R8), shared-helper duplication (RB-5). The
assembled `_render_*` numbers stay **BLOCKED** (interleaved) — every
component formula is independently validated.

## 27. Not implemented

One-way shear; development / anchorage length; support (negative) moment
+ top steel; landing-slab design; continuity / multi-span analysis; bar
cut-off; deflection / span-depth control; crack control; nosing / step
reinforcement. Stair types L-shape / slabless / free-standing / spiral
(`UNDER_CONSTRUCTION`). Concentrated / patch loads.

## 28. Engineering safety assessment

- **Before EV-07:** an over-reinforced straight flight (thin waist + long
  span + heavy live load — realistic combination, all within the widget
  minimums) received a green **PASS**, with `As` sized at an optimistic
  `φ = 0.90` and `εₜ` as low as 0.0022 (below the mandatory 0.004 of
  ACI 10.3.5). A brittle, non-ductile stair could pass. The U-shape
  verdict had the same latent gap.
- **After EV-07:** both stair renders **FAIL** such a section with an
  explicit reason (`As > As,max — not tension-controlled`), in the
  on-screen verdict, the DESIGN-CHECKS table and the PDF report. All
  tension-controlled stairs are unaffected (verified: 80 goldens +
  EV-07 H-02 default-straight-stair check + all phase-F flexure cases).
- **Residual:** the tool covers **positive midspan flexure + minimum
  steel + spacing + ductility** of a **simply-supported single flight**
  only. One-way shear, support / landing steel, continuity, development
  length and deflection are **NOT IMPLEMENTED** — a user designing a
  continuous or heavily-loaded stair must handle those externally. The
  `FAIL → REVIEW` badge (R10) softens the wording but masks no result.
- **The VF-11 class is now closed across the module set:** found and
  fixed in `beam.py` (EV-03), `slab.py` (EV-04) and both stair renders
  (EV-07); latent-but-unreachable in `footing.py` (EV-05); absent from
  `column.py` (EV-06).
- **Net:** the stair geometry, self-weight, load combination, load
  application, moment, flexure, minimum steel, temperature steel, spacing
  and ductility are independently validated against ACI 318M-08, and the
  one proven non-conservative FALSE PASS is corrected.

## 29. Recommended EV-08

1. **EV-08 = BUILDING MODEL** (the last member module). Per EV-01, this
   is **model generation + tributary gravity take-down + BOQ**, **NOT a
   structural design check** (its report status reads "MODEL GENERATED",
   never a design "PASS" — ER-02). Validate: grid parsing
   (`_parse_spacings`), node / column / panel enumeration, the tributary
   take-down (`_calculate_column_loads` — including the **VF-05**
   dropped-quarter-area assumption), rule-based grouping
   (`_auto_group_columns` — the "AI" mislabel, ER-03), the factored slab
   load `Wu` inside `render_building_model` (VF-01, currently BLOCKED),
   and `estimate_building_boq` + `_beam_length_m` (VF-08 rebar-ratio
   basis). No VF-11 pattern applies (no flexural design).
2. **Deferred UI / doc items:** VF-COL-01 / VF-COL-03 / VF-COL-05
   (EV-06), VF-SLAB-01 (EV-04 Grashof method decision), VF-FOOT-01 /
   VF-FOOT-03 (EV-05), VF-13 / VF-04 (EV-03).
3. **Wire the EV-02 … EV-07 runners into pytest** behind a marker so the
   independent checks run in CI without moving the default 80-count.

---

## Final checklist (EV-07 acceptance)

- [x] Actual stair implementation audited (§3 — IMPLEMENTED / UNDER_CONSTRUCTION / NOT IMPLEMENTED)
- [x] Independent reference created (`reference_stair_ev07.py`, math-only)
- [x] Geometry validated (`Lx`, `θ`, `d` — horizontal-projection span, not a beam)
- [x] Self-weight validated (`DL_waist` sloped, `DL_steps` triangular; `t_avg` U-shape)
- [x] Load combination validated (`Wu = 1.2 DL + 1.6 LL`, ACI 9.2)
- [x] Load application validated (per-horizontal-m², `1/cos θ` on waist self-weight)
- [x] Moment validated (`Wu·Lx²/8` / `Wu·L²/8`, simply supported)
- [x] Support assumption validated (simply supported — no continuity, NOT IMPLEMENTED documented)
- [x] Shear validated (NOT IMPLEMENTED — no computed-but-ignored result)
- [x] Flexure validated (`_as_flexure_ksc` MKS + `_required_as_flexure` SI chains)
- [x] φ validated (fixed 0.90 in the helpers → VF-STAIR-01; gated by the EV-07 ductility check)
- [x] `As_min` validated (`max(As_req, As_temp_min)` straight; `main_min_ok` / `temp_min_ok` U-shape)
- [x] Temperature steel validated (`_temp_steel_ratio`, in the verdict)
- [x] Spacing validated (`_spacing_for` + bounds; VF-STAIR-02 recorded)
- [x] Development / anchorage scope documented (NOT IMPLEMENTED)
- [x] Stair configuration scope documented (straight + U-shape only)
- [x] Final verdict audited (`passed` = AND of all computed checks after the fix)
- [x] False-PASS audit completed (§18 — VF-STAIR-01 found & fixed; no residual)
- [x] Unit audit completed (§19 — MKS straight, SI U-shape, no R2)
- [x] Boundary matrix completed (§20)
- [x] Every discrepancy classified (§21 / §22 — R3 ×1, R8 ×2, R9 ×5, R10 ×1)
- [x] No circular validation; no fabricated reference; no tolerance manipulation
- [x] Production fix test-first (FAIL before, PASS after)
- [x] Regression ≥ 78 PASS — **80 passed**
- [x] EV-02 / EV-03 / EV-04 / EV-05 / EV-06 = 0 FAIL each
- [x] EV-07 re-validated — 0 FAIL
- [x] `git diff` audited — only `modules/stair.py` (+ untracked `tests/test_stair_calc.py`, EV-07 files); `utils/*` byte-identical to HEAD; no other module touched
- [x] EV-07 completion report created

**EV-07 is complete. EV-08 (recommended: BUILDING MODEL) is NOT started.**
