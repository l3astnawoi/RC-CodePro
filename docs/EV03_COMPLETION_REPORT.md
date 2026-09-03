# EV-03 — Completion Report
## Beam Engineering Validation & Corrective Fix

**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`
**Rule applied:** *fix only what the validation proves* — minimal, test-first.

---

## 1. Scope

**IN:** `modules/beam.py` — flexure (`_flex_ksc`, `_required_as`,
`_section_calc`, `_render_beam_section` verdict), one-way shear
(`_shear_check`, MKS shear block), reinforcement (`As_min`, `As_max` /
ductility), spacing, boundary/invalid inputs; the beam-relevant parts of
`utils/aci_318m.py` (`beta1`, `rho_min_flexure`, `rho_max_flexure`,
`phi_flexure`, `vc_beam`, `vc_beam_ksc`) and `utils/analysis.py`
(`solve_continuous_beam` — VF-04 only).

**OUT:** column, slab, footing, stair, building; new features; UI /
drawing / report redesign; any continuous-beam solver redesign.

**New EV-03 artifacts (all untracked, non-production):**
`tests/validation/reference/reference_beam_ev03.py` (independent, math-only),
`tests/validation/run_ev03_beam.py` (executable runner, not a pytest module).

**Production change:** `modules/beam.py` only (2 functions). Regression
tests added to `tests/test_beam_calc.py` (2 new functions).

## 2. Baseline (before any change)

```
py -3 -m pytest -q                        -> 73 passed, 0 skipped
py -3 tests/validation/run_ev02_validation.py --brief
                                         -> 120 checks: 104 PASS, 0 FAIL,
                                            11 REVIEW, 5 BLOCKED
py -3 tests/validation/run_ev03_beam.py   -> 127 checks: 104 PASS, 2 FAIL,
                                            21 REVIEW   (pre-fix)
```

The two pre-fix FAILs (both in phase D) are the proven defect — see §12.

## 3. Beam Flexure results  (phase A — 9 flexure + 4 `_required_as` cases)

`_flex_ksc` vs `reference_beam_ev03.flexure_layer_mks` (independent
Whitney block + ACI 9.3.2 φ), across the tension-controlled domain, the
`As_min` / `As_max` boundaries, `f'c` = 180 / 240 / 280 / 350 ksc, and a
small section:

| Parameter | Result |
|---|---|
| `a` (stress-block depth) | **PASS** — rel < 1e-6 every case |
| `Mn` | **PASS** — rel < 1e-6 every case |
| `φMn` (engine returns 0.90·Mn) | **PASS** vs `0.90·Mn` reference |
| `β₁`, `c`, `εₜ` (engine does not return these) | computed by the reference to check φ-validity — see §8/§10 |
| `_required_as`: `Mu = 0` | **PASS** — `As = 0`, feasible `True` |
| `_required_as`: very low `Mu`, moderate `Mu` | **PASS** — `As`, `Rn` rel < 1e-6 |
| `_required_as`: huge `Mu` (infeasible) | **PASS** — `feasible = False`, `As = None` |

Engine flexure arithmetic reproduces textbook ACI 318M-08. The **only**
flexure issue is that `_flex_ksc` applies `φ = 0.90` unconditionally
(VF-11) — addressed by the verdict fix in §13, not by changing the
formula.

## 4. Beam Shear results  (phase B — 9 boundary cases)

`_shear_check` (SI) vs `reference_shear.beam_shear_capacity_si`
(independent ACI 11.2 / 11.4):

| Case | Result |
|---|---|
| `Vu = 0` | **PASS** (verdict True) |
| `Vu` just below / at / just above `φVn` | **PASS** — boundary is inclusive (`φVn ≥ Vu`), flips correctly at `+ε` |
| `s = s_max` / `s = s_max + ε` | **PASS** — discrete flip, no tolerance applied |
| `Vs` just below / above `0.33√f'c·bw·d` | **PASS** — `d/2 → d/4` `s_max` transition triggers at the exact threshold (`>` strict) |
| `Vs > Vs_max` | **PASS** — `phiVs` capped at `Vs_max`, verdict `False` |
| `phiVc`, `Vs`, `Vs_max`, `phiVn`, `s_max` | **PASS** — rel < 1e-6 / abs < 1e-3 N every case |

SI shear is exact. The MKS shear block inside `_render_beam_section` uses
rounded metric coefficients — VF-12 / VF-13, §9.

## 5. Reinforcement results  (phase C — 4 material/section combos)

| Quantity | Engine | Reference | Result |
|---|---|---|---|
| `As_min` (MKS, `as_min_flexure_ksc`) | `max(0.8√f'c/fy, 14/fy)·b·d` | same, ACI 10.5.1 | **PASS** rel < 1e-9 |
| `As_max` (`_rho_max_ksc·b·d`) | `0.85·β₁·f'c/fy·0.375·b·d` | same, ACI 10.3.4 | **PASS** rel < 1e-9 |

Both formulas are correct. **The defect is that `As_max` was not wired
into the pass/fail verdict** (§12–§13).

## 6. Spacing results  (phases B / D)

- Stirrup `s_max` (SI `_shear_check`): `min(d/2, 600)`, halving to
  `min(d/4, 300)` when `Vs > 0.33√f'c·bw·d` — **PASS**, discrete flip
  verified at the exact boundary and at `± ε`.
- Stirrup `s_max` (MKS `_render_beam_section`): `min(d/2, 60 cm)` /
  `min(d/4, 30 cm)`, dense-stirrup trigger `1.06√f'c` — formula correct;
  the `1.06` literal is 0.6 % above the SI-exact `1.054` (**VF-13**, §9).
- Flexural bar spacing: `_render_beam_section` takes the spacing `S`
  directly from the user and checks `S ≤ s_max`; no minimum-clear-spacing
  or crack-control (ACI 10.6.4) check is performed — recorded as
  **VF-16** (scope limitation, not in EV-03 fix scope; the section-design
  tool checks strength + ductility + stirrup spacing, not bar detailing).

## 7. VF-07 — β₁ dual threshold

1. **Production:** `_beta1_ksc(fc_ksc)` — `0.85` for `f'c ≤ 280 ksc`,
   then `0.85 − 0.05·(f'c − 280)/70`, floor `0.65`.
2. **Reference / code-consistent:** ACI 318M-08 10.2.7.3 in MPa — break at
   `28 MPa = 285.53 ksc`, slope `−0.05` per `7 MPa = 71.38 ksc`.
3. **Thresholds differ:** yes — `280` vs `285.53` ksc.
4. **Root cause:** intentional metric rounding (`280 / 70` are the
   conventional round-number ksc equivalents). **R8.**
5. **Quantified effect on the BEAM engine:** `_flex_ksc` (`a`, `Mn`,
   `φMn`) contains **no β₁** — unaffected. β₁ enters **only**
   `_rho_max_ksc` → `As_max`. For `f'c` in `(280, 285.5]` ksc the engine
   β₁ is `< 0.85` while code-consistent is `0.85`; above that the engine
   β₁ is a few thousandths lower. In every case the engine `As_max` is
   **≤** the code-consistent value → the ductility ceiling is **slightly
   stricter (conservative)**. Max deviation ≈ 0.8 % of `As_max` at
   `f'c = 420 ksc`.
6. **Conclusion:** conservative, negligible, standard practice. **ACTION:
   ACCEPTED — no fix.**

## 8. VF-12 — MKS `V_c` coefficient (`0.53√f'c`)

1. **Production:** `vc_beam_ksc = 0.53·√f'c·b·d` [kgf] (used for the
   verdict in `_render_beam_section`).
2. **Reference:** exact MKS equivalent of ACI 11.2.1.1 SI
   `0.17·√f'c[MPa]·bw·d` = `0.17·√0.0980665·100/9.80665·√f'c·b·d`
   ≈ `0.5429·√f'c·b·d` [kgf].
3. **Code vs unit-form:** `0.53√f'c` [ksc] is a legitimate long-standing
   ACI-metric (kgf/cm²) code form — a unit-convention transcription, not
   a different requirement.
4. **Conservative?** Yes — `0.53` is `2.37 %` **below** the exact
   equivalent → under-estimates concrete shear → requires marginally more
   stirrups.
5. **Permitted by ACI 318M-08?** The 318M SI text is `0.17√f'c[MPa]`;
   `0.53√f'c[ksc]` is the corresponding metric form used by EIT / older
   ACI metric editions and is conservative relative to it.
6. **Intentional approximation or defect?** Intentional. **R8.**
   **ACTION: ACCEPTED — no fix.**

## 9. VF-13 (new) — MKS `Vs_max` and dense-stirrup trigger

`_render_beam_section` uses `Vs_max = 2.1·√f'c·b·d` and the `s_max → d/4`
trigger `Vs > 1.06·√f'c·b·d`.

- `Vs_max`: exact MKS equivalent of `0.66√f'c[MPa]` ≈ `2.108` → `2.1` is
  `0.36 %` low → **conservative**.
- Trigger: exact MKS equivalent of `0.33√f'c[MPa]` ≈ `1.054` → `1.06` is
  `0.59 %` **high** → for a `Vs` in the ≈ 0.6 %-wide band between the two,
  the engine keeps `s_max = d/2` where the SI-exact form would require
  `d/4`. Consequence is bounded (`d/2` vs `d/4`; the lower spacing is a
  detailing margin), and only that thin band is affected.
- **Root cause R8** (metric rounding). **ACTION: ACCEPTED with NOTE** —
  recommend aligning `_render_beam_section`'s three MKS shear coefficients
  (`0.53 / 1.06 / 2.1`) to the SI-exact values in an **EV-04 consistency
  pass**; not done in EV-03 because no unsafe design outcome is proven.

## 10. VF-04 — continuous-beam sampled peak (beam-relevant only)

- Analytical peak (single 6 m span, `w = 1000 kgf/m`): `wL²/8 = 4500.0`.
- Engine `solve_continuous_beam(...)["Mu_pos_kgfm"]`: `4499.886`.
- Analytic `M(x)` sampled on the **same** 200-pt grid: `4499.886` —
  identical to the engine → **the solver is exact; the entire error is
  fixed-grid sampling.**
- Gap: `0.114 kgf·m` = `0.0025 %`, **non-conservative** (under-estimate),
  **bounded** by the parabola sampling bound `(w/2)(h/2)² ≈ 0.114`.
- **Root cause R4** (numerical method). **ACTION: ACCEPTED** as a
  documented numerical limitation. **Solver NOT changed in EV-03.** EV-04
  may evaluate `M` at each span's interior stationary point analytically
  (would move `test_analysis.py` golden values → its own reviewed step
  with a before/after table).

## 11. Boundary results  (phase E — 9 invalid/edge inputs)

| Input | Behaviour | Verdict |
|---|---|---|
| `_flex_ksc(As=0)` | returns `(0, 0, 0)` — no crash | OK |
| `_flex_ksc(d=0)` / `(b<0)` | returns a negative `Mn` — no crash; caller (`_render_beam_section`) clamps `d>0` and `st.number_input(min_value)` blocks `b≤0` | OK (private helper, guarded caller) — **VF-15** |
| `_required_as(Mu=0)` | `(0, 0, 0, True)` — no crash | OK |
| `_required_as(f'c=0)` | **raises `ZeroDivisionError`** | unreachable — `f'c` UI `min_value = 180 ksc`; **VF-15** negative test |
| `_beta1_ksc(0)` / `(-10)` | returns `0.85` — no crash | OK |
| `_shear_check(s=0)` | `Vs = 0`, no `ZeroDivisionError` (guarded `if s_mm > 0`) | OK |
| `_shear_check(Vu<0)` | `ok = True` (negative demand trivially satisfied) | OK (physically vacuous input) |

**VF-15 (new):** `_required_as` and `_flex_ksc` have no internal
zero/negative-input guards; all such inputs are blocked by the UI's
`st.number_input(min_value=…)` and are unreachable in the app flow.
Classification **R9 (scope limitation)** — not a reachable defect; no fix
in EV-03. A defensive guard could be added in a later hardening pass.

## 12. Discrepancy table

| # | Where | Reference | Engine (pre-fix) | Root cause | Conservatism |
|---|---|---|---|---|---|
| 1 | `_render_beam_section` verdict, over-reinforced section (`As > As_max`, `εₜ < 0.004`) | **FAIL** (`φMn_ACI` with φ from `εₜ` `< Mu`; ACI 10.3.4 / 10.3.5) | **PASS** (`bot_ductile_ok` computed but omitted from `bottom_ok`; `φMn` uses fixed `φ = 0.90`) | **R3** | **NON-conservative FALSE PASS** |
| 2 | `_section_calc` verdict, same section class | **FAIL** | **PASS** (no ductility check computed at all) | **R3** | **NON-conservative FALSE PASS** |
| 3 | VF-07 β₁ 280 ksc vs 285.5 ksc | code-consistent β₁ | ≤ code β₁ (only via `As_max`) | R8 | conservative, ≤ 0.8 % |
| 4 | VF-12 `V_c` `0.53` vs `0.5429` | 0.5429 | 0.53 | R8 | conservative, 2.4 % |
| 5 | VF-13 `Vs_max` `2.1` vs `2.108` | 2.108 | 2.1 | R8 | conservative, 0.4 % |
| 6 | VF-13 dense trigger `1.06` vs `1.054` | 1.054 | 1.06 | R8 | non-conservative, 0.6 % (bounded consequence) |
| 7 | VF-04 `Mu_pos` sampled vs analytic | `wL²/8` | 0.0025 % low | R4 | non-conservative, bounded by grid |
| 8 | VF-15 `_required_as(f'c=0)` | (n/a) | `ZeroDivisionError` | R9 | unreachable (UI-blocked) |

## 13. Production fixes  (`modules/beam.py` ONLY — discrepancies #1 & #2)

**Root cause:** the tension-controlled / maximum-reinforcement limit
(ACI 318M-08 10.3.4; `εₜ ≥ 0.004` is **mandatory** for a flexural member
per 10.3.5) was **not enforced in the pass/fail verdict** of either beam
design path.

| Function | Change | Lines |
|---|---|---|
| `_section_calc` | + `from utils.aci_318m import … rho_max_flexure`; compute `As_max_top/bot = rho_max_flexure(fc,fy)·b·d`; compute `top_ductile_ok / bot_ductile_ok`; **add both to `passed`**; add `As_max_top/bot`, `top/bot_ductile_ok` to the return dict | import + `_section_calc` body (~+13 lines) |
| `_render_beam_section` | `bottom_ok = bot_strength_ok and bot_min_ok` → `… and bot_ductile_ok`; same for `top_ok`; add matching FAIL-reason messages to the `fails` list; change the two over-reinforcement `st.warning` conditions from `X_ok and not X_ductile_ok` (now always false) to `not X_ductile_ok` | verdict block + `fails` block (~+8 lines) |

**Not changed:** no formula, no numeric constant, no unit conversion, no
`_flex_ksc`, no `_required_as`, no `_shear_check`, no `utils/*`, no other
module, no UI layout, no report structure, no golden value. The
`rho_max_flexure` used is the existing SI ACI 10.3.4 helper (already
regression-tested and EV-02-validated as `EV-ACI-003`).

**Not fixed (mooted by the above, documented):** `_flex_ksc`'s fixed
`φ = 0.90` (VF-11) — after the verdict fix, any section reaching a PASS
has `εₜ ≥ 0.005`, where `φ = 0.90` is correct; a non-TC section now FAILs
regardless of the `φMn` value. Touching `_flex_ksc` would be broader than
minimal and risk the `test_flex_ksc` golden.

## 14. Regression results

**Test-first** (§16): both new tests were confirmed to **FAIL** against
the pre-fix engine, then to **PASS** after the fix.

```
py -3 -m pytest -q        ->  75 passed, 0 failed, 0 skipped
```

| Suite | Count |
|---|---|
| Existing regression (unchanged) | **73 passed** — every original golden value identical |
| New EV-03 beam regression | **+2 passed** — `tests/test_beam_calc.py::test_section_calc_over_reinforced_fails_ductility`, `test_section_calc_tension_controlled_ductile_ok` |
| **Total pytest** | **75 passed** |
| EV-02 engineering validation (re-run) | **120 checks — 104 PASS, 0 FAIL, 11 REVIEW, 5 BLOCKED** (unchanged — no beam helper formula touched) |
| EV-03 beam engineering validation | **127 checks — 107 PASS, 0 FAIL, 20 REVIEW, 0 BLOCKED** |

## 15. Final validation results  (EV-03 runner, post-fix)

| Phase | Checks | PASS | REVIEW | Notes |
|---|---|---|---|---|
| A — flexure (`_flex_ksc`, `_required_as`) | 33 | 33 | 3 | `εₜ`/φ notes on the near-`As_max` case |
| B — shear (`_shear_check`) boundary matrix | 54 | 54 | 0 | all boundaries flip correctly |
| C — reinforcement (`As_min`, `As_max`) | 8 | 8 | 0 | rel < 1e-9 |
| D — composite verdict | 5 | 3 | 2 | D-01 source-check + D-02 logic PASS; D-03 `_section_calc` live PASS; D-01/D-03 notes = REVIEW (defect narrative) |
| E — boundary / invalid input | 9 | 3 | 6 | VF-15 negative tests |
| F — VF-07 / VF-12 / VF-13 / VF-04 | 18 | 6 | 9 | engineering conclusions |
| **Total** | **127** | **107** | **20** | **0 FAIL, 0 BLOCKED** |

## 16. Remaining REVIEW / BLOCKED items

**REVIEW (accepted / documented, no action in EV-03):**
VF-04 (R4 sampled peak), VF-07 (R8 β₁ 280 ksc), VF-12 (R8 `0.53√f'c`),
VF-13 (R8 MKS shear coefficients — EV-04 consistency pass recommended),
VF-15 (R9 no zero/negative-input guards; UI-blocked),
VF-16 (R9 no bar-spacing / crack-control detailing check in the
section-design tool).

**BLOCKED (EV-01, unchanged — need a compute/render split that is a
separate authorised refactor, not a validation step):** `EV-BEAM-005`
(full `_render_beam_section` / `_render_beam_3_sect` assembled numbers).
EV-03 mitigated this for the **verdict-composition logic** via the
importable `_section_calc` tests + the source-level check on
`_render_beam_section`.

## 17. Engineering safety assessment

- **Before EV-03:** a beam section reinforced past the tension-controlled
  limit (including past the mandatory `εₜ ≥ 0.004` of ACI 10.3.5) could
  receive a green **PASS** in both beam design paths, with `φMn` computed
  at an optimistic `φ = 0.90`. This is a **non-conservative** error that
  could pass an unsafe (brittle, over-reinforced) section.
- **After EV-03:** both paths **FAIL** such a section and state the reason
  (`As > As,max — not tension-controlled`). All tension-controlled
  sections are unaffected (verified: 73 goldens + `_section_calc` TC test
  + EV-03 D-02/D-04).
- **Residual non-conservatism:** only VF-13's `1.06` dense-stirrup
  trigger (0.6 %, bounded consequence) and VF-04's `Mu_pos` sampling
  (0.0025 %, bounded) — both negligible, both documented, neither
  produces an unsafe verdict on its own. Recommend closing VF-13 in EV-04.
- **Net:** the beam flexure + shear + reinforcement + ductility engine is
  now **independently validated** against ACI 318M-08 and a
  first-principles reference, with the one proven defect corrected.

## 18. Recommended EV-04

1. **EV-04 = SLAB** (next module in the same pattern: independent
   reference → validate → root-cause → minimal fix → regression →
   re-validate). Carry the VF-11 pattern check: `_as_flexure_ksc` /
   `_required_as_flexure` also hardcode `φ = 0.90` — verify the slab
   caller (`_render_slab_design`) enforces `ρ ≤ ρ_max`; if not, same R3
   fix.
2. **MKS shear coefficient consistency pass** (VF-13): align
   `_render_beam_section`'s `0.53 / 1.06 / 2.1` to the SI-exact
   `0.5429 / 1.0540 / 2.1083` (or convert `f'c` to MPa and call
   `vc_beam`), as a small reviewed change with before/after golden diff.
3. **VF-04 remedy** (separate reviewed step): analytic interior-stationary
   -point moment in `solve_continuous_beam`, with a `test_analysis.py`
   golden-value before/after table.
4. **VF-15 / VF-16 hardening** (optional, low priority): defensive
   zero/negative-input guards on the pure flexure helpers; a
   bar-spacing / crack-control (ACI 10.6.4) check in the section-design
   tool.
5. **Wire the EV-02 + EV-03 runners into pytest** behind a marker
   (`-m validation`) so the independent checks run in CI without moving
   the default count.

---

## Final checklist (EV-03 acceptance)

- [x] Beam flexure independently validated (phase A, 33 checks PASS)
- [x] Beam shear independently validated (phase B, 54 checks PASS)
- [x] Reinforcement independently validated (phase C — `As_min` / `As_max`)
- [x] Spacing independently validated (stirrup `s_max`, discrete boundaries)
- [x] Boundary + invalid-input matrix exercised (phase E)
- [x] VF-07 investigated → R8 ACCEPTED (no β₁ dependence in `_flex_ksc`)
- [x] VF-12 investigated → R8 ACCEPTED (conservative metric form)
- [x] VF-04 investigated → R4 ACCEPTED (sampling only; solver exact)
- [x] Every discrepancy has a root-cause classification (§12)
- [x] No fabricated expected values; no circular validation; no tolerance manipulation
- [x] Production fix only where proven necessary — 1 defect, `modules/beam.py` only, 2 functions
- [x] Test-first: new tests fail before, pass after
- [x] Existing 73 regression tests pass (0 golden values moved); total 75
- [x] All beam validation cases re-run — 0 FAIL, 0 BLOCKED
- [x] Remaining REVIEW / BLOCKED items documented (§16)
- [x] `git diff` audited — only `modules/beam.py` (+ `tests/test_beam_calc.py`, + untracked EV-03 files); `utils/aci_318m.py` / `utils/analysis.py` / `utils/boq.py` byte-identical to HEAD
- [x] No destructive git command used
- [x] EV-03 completion report created

**EV-03 is complete. EV-04 is NOT started.**
