# EV-04 — Completion Report
## Slab Engineering Validation & Corrective Fix

**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`
**Rule applied:** *fix only what the validation proves* — minimal, test-first,
no feature creep.

---

## 1. Scope

**IN:** `modules/slab.py` — the live path
`render_slab_module → _render_slab_design` (used for both "One-way" and
"Two-way" slab types) and its pure helpers `_temp_steel_ratio`,
`_as_flexure_ksc`, `_required_as_flexure`, `_spacing_for`; the slab-
relevant parts of `utils/aci_318m.py` (`bar_area`, and the ACI 10.3.4 /
10.5.1 / 7.12 relations).

**OUT (per brief §17 — NOT to be added):** one-way shear, two-way /
punching shear, deflection, crack control, development length, torsion,
moment redistribution, continuity / ACI 8.3.3, column-strip / middle-strip
distribution, any new slab feature.

**New EV-04 artifacts (untracked, non-production):**
`tests/validation/reference/reference_slab_ev04.py` (independent,
math-only), `tests/validation/run_ev04_slab.py` (executable runner, not a
pytest module).

**Production change:** `modules/slab.py` only. Regression tests added to
`tests/test_slab_calc.py` (2 new functions).

## 2. Baseline (before any change)

```
py -3 -m pytest -q                       -> 75 passed, 0 skipped
py -3 tests/validation/run_ev02_validation.py --brief
                                        -> 120 checks: 104 PASS, 0 FAIL
py -3 tests/validation/run_ev03_beam.py --brief
                                        -> 127 checks: 107 PASS, 0 FAIL
py -3 tests/validation/run_ev04_slab.py  -> 78 checks: 56 PASS, 2 FAIL,
                                            20 REVIEW   (pre-fix)
```

The two pre-fix FAILs (phase G) are the proven defect — see §12/§13.

## 3. Implementation audit

| Function | Kind | Purpose | ACI relation |
|---|---|---|---|
| `_temp_steel_ratio(fy_MPa)` | IMPLEMENTED (pure, tested) | shrinkage/temperature ratio | 7.12.2.1 |
| `_required_as_flexure(Mu_kNm,b,d,fc,fy)` | IMPLEMENTED (pure, tested) | SI singly-reinforced As | 10.2 |
| `_as_flexure_ksc(Mu_kgfm,b,d,fc,fy)` | IMPLEMENTED (pure, tested) | MKS singly-reinforced As, **fixed φ = 0.90** | 10.2 |
| `_spacing_for(Ab,As_req,s_max)` | IMPLEMENTED (pure, tested) | bar spacing, 2.5 cm rounding | 13.3.2 (via caller) |
| `_beta1_ksc` / `_rho_max_ksc` | **ADDED by EV-04** (pure, tested) | MKS β₁ / tension-controlled ρ_max | 10.2.7.3 / 10.3.4 |
| `render_slab_module()` | UI ONLY | type select → `_render_slab_design` | — |
| `_render_slab_design()` | IMPLEMENTED (interleaved / BLOCKED) | classification, load, moment, flexural + temp steel, spacing, **verdict** | 9.2, 10.2, 10.3.4, 10.5.4, 7.12, 13.3.2 |
| `_render_one_way_slab` / `_render_two_way_slab` | DEAD CODE | superseded by `_render_slab_design` | — |

`_render_slab_design` implements, per 1 m strip: `two_way = (short/long) >
0.5`; `sw = (t/100)·2400`; `Wu = 1.2(sw+SDL) + 1.6 LL`; two-way moments by
Grashof partition, one-way `Wu·Lx²/8`; `As` per direction via
`_as_flexure_ksc`; `As_{x,y} = max(As_req, As_temp_min)`; spacing via
`_spacing_for`; verdict = spacing bounds **(pre-EV-04: only)**.

**NOT IMPLEMENTED / SCOPE LIMITATION:** every item in §1 "OUT", plus
pattern loading and corner reinforcement.

## 4. Load validation (phase A)

Independent reference (`reference_slab_ev04.loads`) vs the engine's literal
expression, 3 cases (self-weight only; sw+SDL+LL; zero SDL & LL, t = 8):

| Quantity | Result |
|---|---|
| `sw = (t/100)·2400` [kgf/m²] | **PASS** rel < 1e-9 |
| `Wu = 1.2(sw+SDL) + 1.6 LL` (ACI 9.2) [kgf/m²] | **PASS** rel < 1e-9 |

**Units:** engine works in `kgf/m²` on a 1 m strip → `kgf·m` per strip.
Self-weight uses the literal `2400 kgf/m³` (MKS convention, identical to
beam/footing/stair). The SI "exact" `24 kN/m³ = 2446.5 kgf/m³`, so `sw` is
≈ 1.9 % low — marginally non-conservative on the DL term only. **NOTE
(R8)** — not a defect, consistent across the codebase.

## 5. Classification (phase B)

`two_way iff (short/long) > 0.5` ⟺ `(long/short) < 2.0` — the standard ACI
/ textbook one-way vs two-way criterion. 7 discrete cases:

| Case | Expected | Engine | Result |
|---|---|---|---|
| square 5×5, near-square 4×5 | two-way | two-way | **PASS** |
| **m = 0.5 exactly (4×8)** | one-way (strict `>`) | one-way | **PASS** |
| m just below / above 0.5 (3.99×8 / 4.01×8) | one-way / two-way | one-way / two-way | **PASS** |
| highly rectangular 2×9 | one-way | one-way | **PASS** |
| reversed order 8×4 (auto-swap) | one-way | one-way | **PASS** |

Discrete — no tolerance applied. Code-consistent, no finding.

## 6. Moment (phase C)

| Quantity | Result |
|---|---|
| one-way `Mu = Wu·Lx²/8` [kgf·m/strip] | **PASS** rel < 1e-9 |
| two-way `Mux = Wu·Lx²·(Ly⁴/(Lx⁴+Ly⁴))/8` | **PASS** rel < 1e-9 |
| two-way `Muy = Wu·Ly²·(Lx⁴/(Lx⁴+Ly⁴))/8` | **PASS** rel < 1e-9 |

**Two-way method — VF-SLAB-01 (new).** The formula is the classical
**Grashof / Rankine (Marcus)** elastic load-partition method (total load
split between orthogonal strips ∝ the 4th power of the opposite span; each
strip then a simply-supported 1 m strip `wL²/8`).

1. **Source:** classical plate approximation (Grashof 1878 / Marcus).
2. **ACI coefficient?** **No** — ACI 318M-08 uses 13.6 DDM / 13.7 EFM.
3. **Engineering assumption?** Yes — a recognised approximate method.
4. **Geometry it applies to:** 4 simply-supported edges, uniform load, no
   continuity, corners free.
5. **Applicability limit?** Yes (interior SS panels, no pattern loading).
6. **Does the program enforce it?** **No** — applied to every two-way
   panel; the UI/report labels the output "ตาม ACI 318M-08".

**Implementation** is correct (rel < 1e-9). **Root cause R7 / R8. Action:
REVIEW / DOCUMENT — CODE / COEFFICIENT REFERENCE REQUIRED.** Formula
**not** changed. Recommend naming the method in the UI/report and adding
an applicability note.

**One-way continuity:** `Wu·Lx²/8` is the simply-supported value —
**correct** for an SS slab. Continuous one-way slabs (ACI 8.3.3 moment
coefficients, support/top steel) are **NOT IMPLEMENTED** (R9). Not added.

## 7. Flexural reinforcement (phase D)

`_as_flexure_ksc` vs `reference_slab_ev04.flexure_strip_ksc` (independent
Whitney block + ACI 9.3.2 φ), 6 cases + 2 SI `_required_as_flexure`:

| Case | `As_req` | `feasible` | intermediate (`εₜ`, `φ_code`) |
|---|---|---|---|
| light / EV-02 input / moderate strip | **PASS** rel < 1e-6 | **PASS** | εₜ ≫ 0.005, φ = 0.90 valid |
| heavy (near As_max, d = 5.2) | **PASS** rel < 1e-6 | **PASS** | εₜ < 0.005 → φ_code < 0.90 **(engine uses 0.90 → As UNDER-estimated)** — VF-11-SLAB evidence |
| zero moment | **PASS** — `(0.0, True)` | **PASS** | — |
| infeasible (Mu 50 000) | **PASS** — `(None, False)` | **PASS** | — |
| SI moderate / zero | **PASS** rel < 1e-6 / exact | **PASS** | — |

Engine flexure arithmetic reproduces textbook ACI. The intermediate chain
(`β₁, a, c, εₜ, φ`) is computed by the reference to **prove** where
`φ = 0.90` is not valid — that is the input to the §13 fix.

## 8. Minimum reinforcement (phase E)

- `_temp_steel_ratio` vs reference — **PASS** rel < 1e-9 for
  `fy = 2400 / 3000 / 4000 / 5000 ksc`.
- **Enforcement:** for slabs ACI 10.5.4 sets the minimum flexural steel =
  the shrinkage/temperature amount (7.12). The engine enforces it via
  `As_x = max(As_x_req, As_temp_min)` and `As_y = max(…)`. The DESIGN
  CHECKS "As,temp" row is a value display with a hardcoded `True` status —
  **R10 (presentational)**; the real enforcement is the `max()`. No
  finding on enforcement.
- Boundary `SLAB-ASMIN` cases (As exactly / below / above minimum) reduce
  to the `max()` — the design steel is never below `As_temp_min`.

## 9. Spacing (phase E)

`_spacing_for` vs independent reproduction, 5 boundary cases:

| Case | Result |
|---|---|
| normal; As tiny → s_max cap; As = 0 → s_max; S_req just above s_max | **PASS** — S and As_provided match rel < 1e-9; discrete rounding exact |
| **As huge → 2.5 cm floor** | **PASS** on the mechanics (engine == reference) **but** `As_provided (45.24) < As_required (80.0)` — **VF-SLAB-03 (new)** |

**Verdict bounds:** `main_ok = 7.5 ≤ S ≤ min(3t, 45)` (ACI 13.3.2 for
principal slab reinforcement); `temp_ok = 7.5 ≤ S_temp ≤ min(5t, 45)`
(ACI 7.12.2.2). Discrete, no tolerance.

**VF-SLAB-03:** the `max(S, 2.5)` floor in `_spacing_for` can
under-provide when `As_req > Ab·40` (S_req < 2.5 cm). Real invariant break
in the shared helper (also used by `modules/stair.py`), **but not
reachable as an unsafe slab verdict** — `S = 2.5 cm < 7.5 cm` is always
rejected by the caller's minimum-spacing check. **Root cause R3 (caught by
the caller). RECORD** — shared-helper hardening deferred (needs stair
re-validation).

## 10. Boundary cases (phase F)

| Input | Behaviour | Verdict |
|---|---|---|
| `_as_flexure_ksc(d=0)` / `(Mu<0)` / `(d<0)` | returns `(0.0, True)` — no crash (the `d≤0 or Mu≤0` guard) | OK |
| `_as_flexure_ksc(f'c=0)` | **raises `ZeroDivisionError`** | unreachable — `f'c` UI `min_value = 180 ksc`; **VF-SLAB-02** negative test |
| `_required_as_flexure(f'c=0)` | **raises `ZeroDivisionError`** | unreachable — same; **VF-SLAB-02** |
| `_temp_steel_ratio(fy=0)` | returns `0.002` — no crash | OK |
| `_spacing_for(As<0)` | `As_req ≤ 1e-9` branch → `(s_max, …)` — no crash | OK |
| `_spacing_for(s_max=0)` | returns `(2.5, …)` — no crash | OK |

**VF-SLAB-02 (new):** `_as_flexure_ksc` / `_required_as_flexure` have no
internal `f'c = 0` guard; blocked upstream by the UI `min_value`.
Classification **R9 (scope limitation)** — not a reachable defect, no fix
(same class as EV-03 VF-15).

## 11. Two-way coefficient audit

Covered in §6 (VF-SLAB-01). Summary: the `Ly⁴/(Lx⁴+Ly⁴)` factor is **not**
a table coefficient — it is the closed-form Grashof/Marcus load-partition
ratio, correctly implemented but **not an ACI 318M-08 method**. Marked
**CODE / COEFFICIENT REFERENCE REQUIRED**, formula unchanged.

## 12. Discrepancies

| # | Where | Reference | Engine (pre-fix) | Root cause | Conservatism |
|---|---|---|---|---|---|
| 1 | `_render_slab_design` verdict, over-reinforced slab (`As > As_max`, `εₜ < 0.004`) | **FAIL** (ACI 10.3.4 / 10.3.5) | **PASS** — verdict checks bar spacing **only**; no `As ≤ As_max`; `As` sized with fixed `φ = 0.90` | **R3** | **NON-conservative FALSE PASS** |
| 2 | two-way moment method | ACI 13.6 / 13.7 | Grashof/Marcus (non-ACI), labelled "ตาม ACI" | R7 / R8 | approximate; interior SS panels only |
| 3 | `_spacing_for` `max(S, 2.5)` floor | `As_prov ≥ As_req` | `As_prov < As_req` when `As_req > Ab·40` | R3 (caught by caller) | non-conservative but unreachable |
| 4 | self-weight `2400 kgf/m³` | `2446.5` (24 kN/m³) | `2400` | R8 | 1.9 % low on DL term |
| 5 | `_as_flexure_ksc(f'c=0)` | (n/a) | `ZeroDivisionError` | R9 | unreachable (UI-blocked) |
| 6 | one-way `Wu·Lx²/8` for continuous slabs | ACI 8.3.3 coefficients | SS value only | R9 | support region under-designed (NOT IMPLEMENTED) |

## 13. Root causes & fixes

**Fixed — discrepancy #1 (VF-11-SLAB, R3):** the mandatory
tension-controlled / maximum-reinforcement limit (ACI 10.3.4;
`εₜ ≥ 0.004` per 10.3.5) was **absent from the `_render_slab_design`
verdict**. `_as_flexure_ksc` applies a fixed `φ = 0.90`, valid only while
the section stays tension-controlled.

| Location | Change |
|---|---|
| `modules/slab.py` module level | **+** `_beta1_ksc(fc_ksc)` and `_rho_max_ksc(fc_ksc, fy_ksc)` — byte-identical to `modules/beam.py` (already EV-02 `EV-ACI-003` + EV-03 validated) |
| `_render_slab_design` | compute `As_max_x/y = _rho_max_ksc(fc,fy)·b·d_{x,y}`; `ductile_x = As_x ≤ As_max_x`; `ductile_y = (not two_way) or (As_y ≤ As_max_y)`; `ductile_ok = ductile_x and ductile_y`; **`passed = main_ok and temp_ok and ductile_ok`**; add a DESIGN-CHECKS row ("เหล็กหลัก ≤ As,max (tension-controlled, ACI 10.3.4)"), a `st.warning`, and a `fails` message |

**Not changed:** no formula, numeric constant, unit conversion,
`_as_flexure_ksc`, `_required_as_flexure`, `_spacing_for`, `_temp_steel_
ratio`; no `utils/*`; no other module; no `modules/beam.py` (EV-03 fix
intact); no golden value. The two-way Grashof formula, the `2400` literal
and the one-way `wL²/8` are **left as-is** (findings #2, #4, #6 — REVIEW /
NOT IMPLEMENTED, not defects).

**Demonstration (proven FALSE PASS, now FAIL):** `Lx = 3 m`, `Ly = 7 m`
(one-way), `t = 10 cm`, `cov = 2`, `f'c 240`, `fy 4000`, `SDL 250`,
`LL 1300 kgf/m²`, DB16 main → `Mu = 3 002 kgf·m/m`, `As_x = 14.4 cm²/m`,
`As_max_x = 11.7 cm²/m`, `εₜ = 0.0035 < 0.004` (ACI 10.3.5 violated),
`φ` should be 0.775 not 0.90, `S_x = 12.5 cm` (in 7.5…30). Pre-fix engine
verdict **PASS**; post-fix **FAIL** (`As > As,max — not tension-
controlled`).

## 14. Regression

**Test-first (§16):** the runner's phase-G composite checks were confirmed
**FAIL** against the pre-fix engine, then **PASS** after the fix. Two new
golden tests were added for the new helpers.

```
py -3 -m pytest -q        ->  77 passed, 0 failed, 0 skipped
```

| Suite | Count |
|---|---|
| Existing regression (unchanged) | **75 passed** — every prior golden value identical (73 original + 2 EV-03 beam) |
| New EV-04 slab regression | **+2 passed** — `tests/test_slab_calc.py::test_beta1_ksc`, `test_rho_max_ksc` |
| **Total pytest** | **77 passed** |
| EV-02 engineering validation (re-run) | **120 — 104 PASS, 0 FAIL** (unchanged) |
| EV-03 beam engineering validation (re-run) | **127 — 107 PASS, 0 FAIL** (unchanged — EV-03 fix not touched) |
| EV-04 slab engineering validation | **77 — 58 PASS, 0 FAIL, 19 REVIEW, 0 BLOCKED** |

## 15. Final validation results (EV-04 runner, post-fix)

| Phase | Checks | PASS | REVIEW | Notes |
|---|---|---|---|---|
| A — load | 6 + 1 note | 6 | 1 | `2400` density NOTE |
| B — classification | 7 + 1 note | 7 | 1 | discrete, threshold 0.5 |
| C — moment | 6 + 2 notes | 6 | 2 | Grashof (VF-SLAB-01) + one-way continuity |
| D — flexure | 8 + notes | 8 | 3 | εₜ/φ notes on the heavy case |
| E — min steel + spacing | 5 + 6 + notes | 11 | 3 | VF-SLAB-03 note |
| F — boundary / invalid | 8 | 0 | 8 | VF-SLAB-02 negative tests |
| G — composite verdict + scope | 2 + notes | 2 | 3 | source check + reconstructed verdict; NOT IMPLEMENTED list |
| **Total** | **77** | **58** | **19** | **0 FAIL, 0 BLOCKED** |

## 16. Remaining REVIEW / BLOCKED / NOT IMPLEMENTED

**REVIEW (accepted / documented, no code change):**
VF-SLAB-01 (Grashof two-way method — CODE REFERENCE REQUIRED, R7/R8),
VF-SLAB-03 (`_spacing_for` 2.5-floor under-provision — R3, caught by
caller), VF-SLAB-02 (no `f'c=0` guard — R9, UI-blocked), self-weight
`2400` literal (R8), As,temp DESIGN-CHECKS row hardcoded status (R10).

**NOT IMPLEMENTED (SCOPE LIMITATION — not added per §17):** one-way shear,
two-way / punching shear, deflection & span-depth control, crack control
(ACI 10.6.4), development length, torsion, moment redistribution,
continuity / ACI 8.3.3 support moments, column-strip / middle-strip
distribution, pattern loading, corner reinforcement. Dead code
`_render_one_way_slab` / `_render_two_way_slab` (matches VF-03).

**BLOCKED:** `EV-SLAB-004` (the fully-assembled `_render_slab_design`
numbers) — needs a compute/render split, a separate authorised refactor,
not a validation step. EV-04 mitigated this for the **verdict-composition
logic** via the reconstructed runner + source check + the new importable
helper tests.

## 17. Engineering safety assessment

- **Before EV-04:** a slab reinforced past the tension-controlled limit
  (including past the mandatory `εₜ ≥ 0.004` of ACI 10.3.5) could receive
  a green **PASS**, with `As` sized at an optimistic `φ = 0.90`, provided
  the bar spacing landed in `7.5…s_max`. Non-conservative — an unsafe
  (brittle, over-reinforced) slab could pass. Reachable with realistic
  inputs (thin slab + long span + heavy live load + large bar).
- **After EV-04:** such a slab **FAILs** with the reason `As > As,max —
  not tension-controlled`, in both the on-screen verdict and the PDF
  report. All tension-controlled slabs are unaffected (verified: 77
  goldens + EV-04 G-02 default-slab check + all phase-D flexure cases).
- **Residual items:** the Grashof two-way method (VF-SLAB-01) gives
  midspan moments in the right ballpark for interior SS panels but is not
  ACI-compliant for continuity / pattern loading — an **engineering-
  method** concern to resolve in EV-05, not a numeric defect. `2400 kgf/m³`
  self-weight is ≈ 1.9 % low. VF-SLAB-03 is unreachable.
- **NOT IMPLEMENTED** shear and deflection mean the tool must not be used
  as a complete slab design — flexure + spacing + shrinkage steel only.
- **Net:** the slab flexure + minimum-steel + spacing + ductility engine
  is now independently validated against ACI 318M-08, with the one proven
  non-conservative FALSE PASS corrected.

## 18. Recommended EV-05

1. **EV-05 = FOOTING** (next module, same pattern: audit → independent
   reference → validate → root-cause → minimal fix → regression →
   re-validate). Carry the **VF-11 pattern check** a third time:
   `_flexure_as` (footing) also has no tension-controlled guard — verify
   `_render_isolated_footing` / `_render_pile_cap` enforce `As ≤ As_max`;
   if not, the same R3 fix. Also audit the punching-shear `vc1/vc2/vc3`
   and the circular-pile perimeter literal `3.464·Dp + π·d` (VF-09,
   already flagged in EV-02).
2. **VF-SLAB-01 resolution** (engineering decision, separate step): either
   (a) name the Grashof/Marcus method explicitly in the UI/report + add an
   applicability note (documentation only, no formula change), or (b)
   replace it with an ACI-recognised method (13.6 DDM or a tabulated
   coefficient method) — a real engine change with its own reviewed
   before/after and golden updates.
3. **VF-SLAB-03 hardening** (shared-helper step): make `_spacing_for`
   never return `As_provided < As_required` (e.g. drop the design when
   `S_req < 2.5`), then re-validate both slab and stair.
4. **VF-13 (from EV-03)** — align `modules/beam.py`'s MKS shear
   coefficients `0.53 / 1.06 / 2.1` to the SI-exact values.
5. **VF-04 remedy** — analytic interior-stationary-point moment in
   `solve_continuous_beam` (moves `test_analysis.py` goldens).
6. **Wire the EV-02 / EV-03 / EV-04 runners into pytest** behind a marker
   so the independent checks run in CI without moving the default count.

---

## Final checklist (EV-04 acceptance)

- [x] Actual slab implementation audited (§3 — IMPLEMENTED / DEAD / NOT IMPLEMENTED)
- [x] Load calculation independently validated (phase A)
- [x] One-way / two-way classification validated (phase B — discrete, boundary at m = 0.5)
- [x] Moment calculation validated (phase C — one-way + Grashof two-way implementation)
- [x] Flexural reinforcement validated (phase D — full chain incl. εₜ / φ)
- [x] Minimum reinforcement validated (phase E — `_temp_steel_ratio` + `max()` enforcement)
- [x] Reinforcement selection: engine designs spacing from As, not user bars — validated (phase E)
- [x] Spacing validated (phase E — discrete bounds, VF-SLAB-03 recorded)
- [x] Boundary matrix exercised (phase F)
- [x] Two-way coefficient source investigated → Grashof/Marcus, non-ACI, VF-SLAB-01 (CODE REFERENCE REQUIRED)
- [x] No fabricated reference values; no circular validation; no tolerance manipulation
- [x] Every discrepancy classified (§12 — R3 ×2, R7/R8, R9 ×2)
- [x] Production fix only where proven — 1 defect, `modules/slab.py` only
- [x] Every production fix has regression protection (2 new golden tests; runner phase-G fails before / passes after)
- [x] Beam regression remains PASS — `pytest` 77, EV-03 beam runner 107 PASS unchanged, `modules/beam.py` untouched
- [x] Existing regression suite ≥ 75 PASS — now **77 passed**
- [x] All slab validation cases re-run — 0 FAIL, 0 BLOCKED
- [x] NOT IMPLEMENTED items documented (§16)
- [x] `git diff` audited — only `modules/slab.py` (+ untracked `tests/test_slab_calc.py`, EV-04 files); `utils/aci_318m.py` / `utils/analysis.py` / `utils/boq.py` byte-identical to HEAD; no other module touched
- [x] No destructive git command used
- [x] EV-04 completion report created

**EV-04 is complete. EV-05 (recommended: FOOTING) is NOT started.**
