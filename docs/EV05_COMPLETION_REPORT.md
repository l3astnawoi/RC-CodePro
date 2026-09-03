# EV-05 — Completion Report
## Footing Engineering Validation & Corrective Fix

**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`
**Rule applied:** *fix only what the validation proves* — minimal, test-first,
no feature creep. Footing is the highest-risk module → every discrepancy
routed through Independent Reference → ACI 318M-08 → reproducibility →
root cause → engineering impact → minimal fix.

---

## 1. Scope

**IN:** `modules/footing.py` — `_render_isolated_footing` (Isolated
Footing), `_render_pile_cap` (Pile Cap F1–F9 and Eccentric Pile Cap
F1E–F9E), and the pure helpers `_temp_steel_ratio`, `_flexure_as`,
`_pile_coords`; the footing-relevant parts of `utils/aci_318m.py`.

**OUT (per brief §17 — NOT to be added):** eccentric spread footing,
soil-pressure distribution, wall / 2C / combined / strap footings,
one-way shear / punching / deflection / crack control / development
length that is not already present, minimum bar clear-spacing, any new
footing feature.

**New EV-05 artifacts (untracked, non-production):**
`tests/validation/reference/reference_footing_ev05.py` (independent,
math-only), `tests/validation/run_ev05_footing.py` (executable runner,
not a pytest module).

**Production change:** `modules/footing.py` only. Regression test added to
`tests/test_footing_calc.py` (1 new function).

## 2. Baseline (before any change)

```
py -3 -m pytest -q                          -> 77 passed, 0 skipped
py -3 tests/validation/run_ev02_validation.py --brief -> 120: 104 PASS, 0 FAIL
py -3 tests/validation/run_ev03_beam.py --brief       -> 127: 107 PASS, 0 FAIL
py -3 tests/validation/run_ev04_slab.py --brief       -> 77:  58 PASS, 0 FAIL
py -3 tests/validation/run_ev05_footing.py            -> 67:  41 PASS, 1 FAIL,
                                                           25 REVIEW  (pre-fix)
```

The single pre-fix FAIL (`VF-FOOT-02/fix wired`, phase J) is the proven
defect — see §16 / §19.

## 3. Implementation audit

| Function | Kind | Purpose |
|---|---|---|
| `_temp_steel_ratio(fy_MPa)` | IMPLEMENTED (pure, tested) | ACI 7.12.2.1 shrinkage/temp ratio |
| `_flexure_as(Mu_Nmm, b_mm, d_mm, fc, fy)` | IMPLEMENTED (pure, tested) | SI singly-reinforced `As`; `inf`/`False` on `d≤0`/`b≤0` or `disc<0`; **fixed `φ = 0.90`** |
| `_pile_coords(n, S)` | IMPLEMENTED (pure, tested) | pile-centre coords, c/c, origin = column centre, n = 1…9 |
| `render_footing_module` / `_tab_shallow` / `_tab_pile` / `_tab_eccentric` | UI ONLY | tab routing |
| `_render_isolated_footing()` | IMPLEMENTED (interleaved / BLOCKED) | bearing (P/A), one-way shear ×2, punching (`vc1/vc2/vc3`), flexure ×2, `As_min` ×2, spacing ×2 — **all in the verdict** |
| `_render_pile_cap(n, kp, is_eccentric)` | IMPLEMENTED (interleaved / BLOCKED) | elastic pile reactions, uplift, column punching, pile-head punching (4 shapes), one-way shear ×2, flexure ×2, `As_min` ×2, spacing ×2 — **all in the verdict** |
| nested `_elastic_reactions`, `_side`, `_s0` | BLOCKED | not importable |

**NOT IMPLEMENTED:** eccentric **spread** footing (no `e`, no `q_max`/
`q_min`, no `e ≤ B/6`, no shallow-footing uplift/overturning/sliding — the
"eccentric" tab is an eccentric **pile cap**); Wall / 2C / Combined /
Strap footings (`UNDER_CONSTRUCTION`); dowels / column bearing;
development length; minimum bar clear-spacing (ACI 7.6.1); settlement;
pile-group efficiency; lateral pile load.

## 4. Isolated footing — load

Independent reference vs the engine's literal expressions:

| Quantity | Result |
|---|---|
| `Wf = B·L·(h/100)·2400` [kgf] | **PASS** rel < 1e-9 |
| `q_service = (P_DL + P_LL + Wf)/(B·L)` [kgf/m²] | **PASS** rel < 1e-9 |
| `qu_net = (1.2 P_DL + 1.6 P_LL)/(B·L)` — **self-weight cancels** in the net factored pressure (ACI 15.2) | **PASS** rel < 1e-9 |

Self-weight uses the `2400 kgf/m³` MKS literal (≈ 1.9 % below `24 kN/m³`),
identical to beam/slab/pile-cap — **NOTE (R8)**, not a defect.

## 5. Soil pressure

`_render_isolated_footing` is **pure concentric P/A bearing**
(`bearing_ok = q_service ≤ q_a`). It has **no eccentricity input**, so
soil-pressure distribution, `q_max` / `q_min`, the `e ≤ B/6` / `e > B/6`
kern condition, partial contact and shallow-footing uplift are
**NOT IMPLEMENTED**. The `F2E`-style eccentric cases are eccentric **pile
caps** (§12).

## 6. Eccentricity / uplift

- **Isolated footing:** none — see §5.
- **Pile cap:** `ex_cm` / `ey_cm` inputs. Factored eccentric moments
  `Muy = Pu_net·(ex/100)`, `Mux = Pu_net·(ey/100)`. Reactions by the
  **elastic pile-group formula** `R_i = P/n + M_y·x_i/Σx² + M_x·y_i/Σy²`
  (`_elastic_reactions`). **Uplift** semantics — verified:
  1. `R_min_kgf = min(R_tot_list_kgf)` (service total incl. cap
     self-weight).
  2. It is **pile tension** (the elastic model's minimum pile reaction),
     not an external uplift load.
  3. `uplift_ok = R_min_kgf ≥ 0.0`.
  4. `uplift_ok` (like `reaction_ok`) **is** in `passed` — a footing with
     any pile in tension **FAILs**.
  5. A `st.warning` is shown when `not uplift_ok`, with `R_min` printed.
  6. Screen and report both read the same `passed` / `R_min` — consistent.
- **New finding (VF-FOOT-02)** — the elastic distribution silently drops
  a moment about an axis with `Σ = 0` (n = 1, n = 2). See §16 / §19.

## 7. Flexure

`_flexure_as` (engine) vs `reference_footing_ev05.flexure_as`
(independent Whitney block + ACI 9.3.2 φ), both directions of the default
footing and the pile-cap flexure inputs:

| Quantity | Result |
|---|---|
| `feasible` (incl. `inf`/`False` sentinel) | **PASS** exact |
| `As_req` [mm²], `Rn` [MPa] | **PASS** rel < 1e-6 |
| cantilever `Mu = qu·bw·Lc²/2` at the column face (ACI 15.4.2) | **PASS** rel < 1e-9 |

**VF-FOOT-03 (new):** `_render_isolated_footing` uses `d = h − cov −
db_long` (a **full** bar diameter), while `_render_pile_cap` uses
`d = h − embed − db/2`. The isolated-footing value under-estimates `d`
by ≈ db/2 → **conservative** (more `As`, lower `φVc`). Inconsistent.
**RECORD (R8/R2)** — no fix (harmonising to `db/2` moves behaviour
non-conservatively; needs a reviewed step).

## 8. One-way shear

Both `_render_isolated_footing` and `_render_pile_cap`:
- critical section at **`d` from the column face** (ACI 11.1.3.1 / 15.5.2)
  — verified.
- `φVc = 0.75·0.17·λ·√f'c·bw·d` (ACI 11.2.1.1), no `Vs` (footings have no
  stirrups) — verified form. `Vc` coefficient rel < 1e-9 against the
  independent SI value.
- `beam_long_ok` / `beam_short_ok` both **in the verdict**.
- Isolated: `av = max((long_dim − c)/2 − d, 0)`; Vu = `qu·bw·av`.
- Pile cap: `Vu` = Σ of the actual `Ru_i` of piles beyond the `d`-section
  (`_side`).

## 9. Punching shear — geometry

| Item | Engine | Independent geometry | Result |
|---|---|---|---|
| Isolated footing, rectangular column: `bo = 2(cx+d) + 2(cy+d)` (ACI 11.11.1.2, at `d/2`) | ✓ | ✓ | **PASS** rel < 1e-9 |
| `d_avg = ½(d_long + d_short)` for two-way shear (ACI R11.11.1) | ✓ | ✓ | verified |
| Pile-head punching perimeter — **square / I-section:** `4·(Dp + d_avg)` | ✓ | ✓ | **PASS** |
| Pile-head — **circular:** `π·(Dp + d_avg)` (correct ACI form) | ✓ | ✓ | **PASS** |
| Pile-head — **hexagonal:** `3.464·Dp + π·d_avg` = `2√3·Dp + π·d_avg` | ✓ | ✓ (`2√3` exact; `3.464` rel < 3e-4) | **PASS** |
| Pile-cap column punching: `bo = 4·(c + d_avg)`, `βc = 1` (square column) | ✓ | ✓ | verified |
| Column-punching `Vu = Pu_net − Σ(Ru_i inside the perimeter)` | ✓ | ✓ | verified form |

## 10. Punching shear — capacity

`vc1/vc2/vc3` (ACI 11.11.2.1, `α_s = 40` interior):

| Expression | Engine | Independent | Result |
|---|---|---|---|
| `vc1 = 0.17(1 + 2/βc)·√f'c` (Eq 11-31) | ✓ | ✓ | **PASS** rel < 1e-9 |
| `vc2 = 0.083(α_s·d/bo + 2)·√f'c` (Eq 11-32) | ✓ | ✓ | **PASS** rel < 1e-9 |
| `vc3 = 0.33·√f'c` (Eq 11-33) | ✓ | ✓ | **PASS** rel < 1e-9 |
| `vc = min(vc1, vc2, vc3)` — **governs: `vc3`** for the default (compact perimeter) | ✓ | ✓ | **PASS** |
| `φVc = 0.75·vc·bo·d_avg`; `punch_ok` in the verdict | ✓ | — | verified form |

**Pile-head `vc`:** `φVc_pile = 0.75·0.33·λ·√f'c·bo_pile·d_avg` uses
`vc3` directly rather than `min(vc1, vc2, vc3)`. For a compact loaded area
(a pile head, βc = 1) `vc3` governs the minimum anyway (`vc1 = 0.51√f'c`;
`vc2 > 0.33√f'c` for a small `bo`), so this **equals** the ACI minimum in
practice — **NOTE (R8)**, no fix.

## 11. Reinforcement

- Both flows **design from a user-entered bar count** (`qty_long` /
  `qty_short`); `As_prov = n · bar_area`. No bar-selection algorithm.
- `flex_*_ok = feasible and As_prov ≥ As_req` — in the verdict.
- `As_min = temp_ratio·bw·h` (ACI 7.12 / 15.4.3) — `asmin_*_ok` in the
  verdict; `temp_steel_ratio` rel < 1e-9 against the reference.
- **X / Y (long / short) directions** handled separately; short-direction
  bars sit on top of the long bars (`d_short = d_long − db_long`).
- **No top reinforcement** (footings/caps designed for bottom flexure
  only — no applied uplift moment case).

## 12. Pile cap

`_pile_coords` (engine) vs independent reproduction, **n = 1 … 9** — all
coordinates match exactly. Elastic reactions:

| Check | Result |
|---|---|
| 4-pile concentric → all `R_i = P/n` | **PASS** |
| 4-pile `ex = 150` → `Σ R_i = P` (force equilibrium) | **PASS** rel < 1e-9 |
| 4-pile `ex = 150` → `Σ R_i·x_i = P·ex` (moment equilibrium) | **PASS** rel < 1e-9 |
| 4-pile `ex = 150` → `R_i` not all equal (moment distributed) | **PASS** |

**Pile-cap flexure / one-way shear** use `_side` (nested, BLOCKED): `Mu` =
Σ `Ru_i·(coord − face)` for piles beyond the column face; `Vu` = Σ `Ru_i`
for piles beyond the `d`-section. Verified form; `_flexure_as` validated
(§7). The fully-assembled pile-cap numbers stay **BLOCKED** (nested
helpers not importable).

## 13. Eccentric footing (F1E–F9E = eccentric pile cap)

`_render_pile_cap(n, kp, is_eccentric=True)` — same engine as the regular
pile cap, with `ex` defaulting to 15 cm. Validated as the pile cap above,
**plus** the VF-FOOT-02 finding (§16) which is the *default* F2E case.

## 14. Boundary matrix

| Input | Behaviour | Verdict |
|---|---|---|
| `_flexure_as(d=0)` / `(b=0)` / `(d<0)` | `(inf, 0, None, False)` — no crash | OK (sentinel) |
| `_flexure_as(Mu=0)` | `(0, 0, 0, True)` — no crash | OK |
| `_flexure_as(f'c=0)` | **`ZeroDivisionError`** | unreachable — `f'c` UI `min_value = 180 ksc`; **VF-FOOT-04** |
| `_flexure_as(huge Mu)` | `(inf, …, False)` — no crash | OK |
| `_temp_steel_ratio(fy=0)` | `0.002` — no crash | OK |
| `_pile_coords(n=1)` | `[(0,0)]` | OK |
| `_pile_coords(n=0)` | `[]` — no crash | OK (n from a fixed selectbox in the UI) |
| `_pile_coords(S=0)` | all-`(0,0)` — no crash | OK (S = 3·Dp ≥ 45 cm in the UI) |

**VF-FOOT-04 (new):** `_flexure_as` etc. have no internal `f'c = 0`
guard; blocked upstream by `st.number_input(min_value)`. **R9** — negative
test, no fix (same class as EV-03 VF-15 / EV-04 VF-SLAB-02).

## 15. VF-09 — circular / hexagonal pile punching perimeter

**RESOLVED — NOT A DEFECT.** EV-02 recorded that the circular-pile
perimeter uses `3.464·Dp + π·d`; that was a **mis-read of an incomplete
excerpt**. `modules/footing.py:952-961`:

```
square / I-section :  4·(Dp + d_avg)
circular           :  π·(Dp + d_avg)          <- correct ACI 11.11.1.2
hexagonal          :  3.464·Dp + π·d_avg
```

Geometry of the hexagon branch:
- A regular hexagon of **across-flats** width `Dp` has perimeter
  `6·(Dp/√3) = 2√3·Dp = 3.46410·Dp`. `3.464` is `2√3` to 4 s.f.
- Offsetting the critical section by `d/2` rounds the 6 corners into
  6 × 60° arcs of radius `d/2` → one full circle → `+ π·d_avg`.
- So `bo_pile = 2√3·Dp + π·d_avg` is the **exact** offset perimeter.

All four perimeters are geometrically correct (EV-05 phase I, rel < 3e-4
for the `2√3` vs `3.464` rounding). **EV-02's VF-09 record is corrected
in `docs/ENGINEERING_VALIDATION.md` §9.4.** No production change.

## 16. Two-pile distribution — VF-FOOT-02

`_elastic_reactions` (line 856):
```
if sum_x2 > 0.0:  r += my * px / sum_x2
if sum_y2 > 0.0:  r += mx * py / sum_y2
```

`_pile_coords(2, S) = [(0, −S/2), (0, S/2)]` → **`Σx² = 0`** (both piles
at `x = 0`), `Σy² = S²/2 > 0`. `n = 2` is the **only** layout with
`Σx² = 0` (n = 1 has `Σx² = Σy² = 0`).

**Behaviour (EV-05 phase J, reproduced independently):**
- `ey ≠ 0` (moment about X — the Y-row **can** resist): `R1 ≠ R2`,
  `Σ R_i·y_i = P·ey`. **Correct.**
- `ex ≠ 0` (moment about Y — the Y-row **cannot** resist): the `my` term
  is **silently dropped** by the `if sum_x2 > 0.0` guard → `R1 = R2`,
  `Σ R_i·x_i = 0 ≠ P·ex`. The cap's X-direction flexure / shear are then
  designed for **≈ zero moment**, and **no warning** is shown
  (`uplift_ok` is True — all `R_i > 0`). The cap + column is a mechanism.
- The eccentric-pile-cap tab (F2E) **defaults `ex = 15 cm`**, so this is
  the *default* F2E behaviour.

**Root cause R3** — a load configuration the model cannot resolve is
silently accepted → non-conservative. **PROVEN reachable.**

## 17. Discrepancy table

| # | Where | Reference | Engine (pre-fix) | Root cause | Conservatism |
|---|---|---|---|---|---|
| 1 | `_render_pile_cap`, `n ≤ 2` with `ex`/`ey` about the un-resisted axis | verdict must **FAIL** (mechanism) | verdict **PASS** — moment term silently dropped, no warning | **R3** | **NON-conservative silent acceptance** |
| 2 | VF-09 circular/hex pile perimeter | `π(Dp+d)` / `2√3·Dp + π·d` | identical | — | **not a discrepancy** (EV-02 mis-read) |
| 3 | VF-FOOT-01: no `As ≤ As_max` in either footing verdict | — | latent | **R3** | latent; **not reachable** (shear/punching/bearing fail first) |
| 4 | VF-FOOT-03: isolated `d = h − cov − db` vs pile-cap `h − embed − db/2` | `h − cov − db/2` | `h − cov − db` (isolated) | R8/R2 | **conservative** (~db/2 low on `d`) |
| 5 | VF-FOOT-04: `_flexure_as(f'c=0)` | (n/a) | `ZeroDivisionError` | R9 | unreachable (UI-blocked) |
| 6 | pile-head `vc` uses `vc3` not `min(vc1,vc2,vc3)` | `min(...)` | `vc3` | R8 | equal in practice (vc3 governs for compact areas) |
| 7 | self-weight `2400 kgf/m³` | `2446.5` | `2400` | R8 | ≈ 1.9 % low on the DL term |

## 18. Root causes

- **R3 (fixed):** #1 — VF-FOOT-02.
- **R3 (latent, not reachable, recorded):** #3 — VF-FOOT-01.
- **R8/R2 (conservative, recorded):** #4 — VF-FOOT-03; #6, #7 — NOTEs.
- **R9 (unreachable, recorded):** #5 — VF-FOOT-04.
- **Not a discrepancy:** #2 — VF-09 resolved.

## 19. Production fixes  (`modules/footing.py` ONLY — discrepancy #1)

**Root cause:** `_render_pile_cap`'s elastic distribution can only carry a
moment about an axis with pile offset on the perpendicular axis; for
`n = 1` (`Σx² = Σy² = 0`) and `n = 2` (`Σx² = 0`) an applied column
eccentricity about the un-resisted axis was silently dropped and the
verdict still reported PASS.

| Change | Detail |
|---|---|
| `_render_pile_cap` (before `passed`) | `+ ecc_resolvable_ok = not ((ex_mm != 0.0 and sum_x2 == 0.0) or (ey_mm != 0.0 and sum_y2 == 0.0))` |
| `passed` | `+ and ecc_resolvable_ok` |
| verdict / warning | `+ st.error("❌ กลุ่มเสาเข็มนี้ต้านโมเมนต์จากการเยื้องศูนย์ของเสาไม่ได้ …")` when `not ecc_resolvable_ok` |
| DESIGN SUMMARY chip | first chip now `reaction_ok and uplift_ok and ecc_resolvable_ok` (label "แรงเข็ม / แรงถอน / ผัง") |

**Not changed:** no formula, numeric constant, unit conversion,
`_elastic_reactions`, `_flexure_as`, `_pile_coords`, `_temp_steel_ratio`;
no `utils/*`; no other module; no `modules/beam.py` / `modules/slab.py`
(EV-03 / EV-04 fixes intact); no golden value.

**Regression:** `tests/test_footing_calc.py::
test_pile_coords_degenerate_moment_resistance` — pins `Σx² = 0` for
`n ≤ 2` and `Σx², Σy² > 0` for `n = 3 … 9` (the geometry the gate relies
on). Confirmed to FAIL if the gate is removed from the runner's source
check; the pytest test itself pins the geometric premise.

## 20. Regression

**Test-first (§26):** the runner's `VF-FOOT-02/fix wired` source check was
confirmed **FAIL** against the pre-fix engine, then **PASS** after the fix.

```
py -3 -m pytest -q        ->  78 passed, 0 failed, 0 skipped
```

| Suite | Count |
|---|---|
| Existing regression (unchanged) | **77 passed** — every prior golden value identical (73 original + 2 beam + 2 slab) |
| New EV-05 footing regression | **+1 passed** — `test_pile_coords_degenerate_moment_resistance` |
| **Total pytest** | **78 passed** |
| EV-02 engineering validation (re-run) | **120 — 104 PASS, 0 FAIL** (unchanged) |
| EV-03 beam engineering validation (re-run) | **127 — 107 PASS, 0 FAIL** (unchanged) |
| EV-04 slab engineering validation (re-run) | **77 — 58 PASS, 0 FAIL** (unchanged) |
| EV-05 footing engineering validation | **67 — 42 PASS, 0 FAIL, 25 REVIEW, 0 BLOCKED** |

## 21. Final validation results (EV-05 runner, post-fix)

| Phase | Focus | PASS | REVIEW |
|---|---|---|---|
| B — isolated footing load | self-weight, `q_service`, `qu_net` | 3 | 2 |
| C — flexure | `_flexure_as` both directions | 6 | 1 |
| D — one-way shear | critical section + `Vc` form | 1 | 1 |
| E — punching geometry + capacity | `bo`, `vc1/vc2/vc3`, governing | 6 | 0 |
| F — reinforcement / min steel / spacing | `temp_ratio`, `As_min` form | 3 | 3 |
| G — composite verdict + VF-FOOT-01 | reachability probe | 1 | 4 |
| H — pile geometry + elastic reactions | `_pile_coords` n=1…9, equilibrium | 13 | 1 |
| I — pile-head punching perimeters (VF-09) | 4 shapes + `2√3` | 5 | 2 |
| J — two-pile eccentric (VF-FOOT-02) | Σx²=0, term dropped, fix wired | 6 | 1 |
| K — boundary / invalid input | 10 negative tests | — | 10 (2 unreachable-crash) |
| **Total** | | **~42** | **~25** |

**0 FAIL, 0 BLOCKED-with-no-coverage** — every importable / derivable
piece of the footing engine is validated; the assembled numbers inside
`_render_*` remain BLOCKED (nested helpers) with their component formulas
verified.

## 22. Remaining REVIEW / BLOCKED / NOT IMPLEMENTED

**REVIEW (accepted / recorded, no code change):**
- **VF-FOOT-01** — no `As ≤ As_max` / tension-controlled gate in either
  footing verdict; **latent R3, not reachable** (one-way / punching shear
  / bearing / flexure-infeasibility, all enforced, fail first). Recommend
  the defense-in-depth check for EV-06+ consistency.
- **VF-FOOT-03** — isolated-footing `d = h − cov − db` vs pile-cap
  `h − embed − db/2`; conservative, inconsistent. Recommend harmonising.
- **VF-FOOT-04** — no `f'c = 0` guard; UI-blocked.
- pile-head `vc3`-only; self-weight `2400`; `_pile_coords` group-extent
  convention — all NOTE / not-a-defect.

**BLOCKED:** the fully-assembled `_render_isolated_footing` /
`_render_pile_cap` numbers (nested `_elastic_reactions` / `_side` / `_s0`
not importable). EV-05 validated every component formula and the
verdict-composition logic (via the reconstructed runner + source check).

**NOT IMPLEMENTED (scope, not added):** eccentric spread footing,
soil-pressure distribution / kern / partial contact, wall / 2C / combined
/ strap footings, minimum bar clear-spacing (ACI 7.6.1), dowels,
development length, settlement, pile-group efficiency, lateral pile load.

## 23. Engineering safety assessment

- **Before EV-05:** a pile cap that **cannot** resist the applied column
  eccentricity (`n = 1` with any `ex`/`ey`; `n = 2` with `ex` along the
  pile row — the *default* F2E case) reported a green **PASS**, designing
  the un-resisted direction for ≈ zero moment with no warning. A user
  could build a foundation that is a mechanism.
- **After EV-05:** such a configuration **FAILs** with an explicit error
  ("the pile group cannot resist the column eccentricity — add piles,
  re-arrange, or centre the column"). All other pile-cap and isolated-
  footing configurations are unaffected (verified: 78 goldens + EV-05
  G-01 default-footing check + all component-formula checks).
- **VF-09 is not a defect** — the punching perimeters (circular, square,
  I-section, hexagonal) are all geometrically correct.
- **VF-FOOT-01** (missing tension-controlled gate) is **latent, not
  reachable** — the footing verdict *does* enforce one-way shear,
  punching shear and bearing, which fail before flexure can be
  over-reinforced. Unlike beam/slab, no fix is warranted by the
  validation.
- **VF-FOOT-03** is **conservative** (footing `d` under-estimated).
- **Residual:** the assembled `_render_*` numbers are BLOCKED (component
  formulas verified); the isolated footing is concentric-only.
- **Net:** the footing engine's load, soil pressure, flexure, one-way
  shear, punching geometry + capacity, pile geometry, elastic pile-
  reaction distribution and minimum-steel are now independently
  validated against ACI 318M-08, VF-09 is cleared, and the one proven
  non-conservative defect (VF-FOOT-02) is fixed.

## 24. Recommended EV-06

1. **EV-06 = COLUMN** (next module, same pattern). High-value targets:
   the P–M interaction curve interior (still `BLOCKED` since EV-01 —
   build an independent strain-compatibility solver, verify it first
   against a hand-checked balanced point + a published interaction
   chart), `φPn,max` (`ALPHA_MAX = 0.80` tied), `ρg` limits, tie /
   spiral spacing (VF-10 — the check compares `s_max ≥ 5 cm`, never a
   provided spacing), slenderness (NOT IMPLEMENTED?).
2. **VF-FOOT-01 defense-in-depth** — add the `As ≤ As_max` gate to
   `_render_isolated_footing` / `_render_pile_cap` for consistency with
   the EV-03 / EV-04 fixes (latent, low urgency).
3. **VF-FOOT-03** — harmonise the isolated-footing effective depth to
   `d = h − cov − db/2` (a reviewed change with before/after; currently
   conservative).
4. **VF-SLAB-01** (from EV-04) — engineering decision on the Grashof
   two-way method (name it / add applicability note, or replace with an
   ACI method).
5. **VF-13** (from EV-03) — align the MKS beam-shear coefficients.
6. **VF-04** — analytic interior-stationary-point moment in
   `solve_continuous_beam` (moves `test_analysis.py` goldens).
7. **Wire the EV-02 … EV-05 runners into pytest** behind a marker.

---

## Final checklist (EV-05 acceptance)

- [x] Actual footing implementation audited (§3 — IMPLEMENTED / BLOCKED / NOT IMPLEMENTED)
- [x] Isolated footing independently validated (load, pressure, flexure, one-way shear, punching, reinforcement, min steel, spacing)
- [x] Soil pressure independently validated (concentric P/A — eccentric spread footing NOT IMPLEMENTED, documented)
- [x] Eccentricity independently validated (pile-cap elastic distribution + equilibrium)
- [x] Uplift semantics investigated (§6 — pile tension, `R_min ≥ 0`, in the verdict, screen == report)
- [x] Flexure independently validated (`_flexure_as` + cantilever `Mu`)
- [x] One-way shear validated (critical section at `d`, `Vc` form)
- [x] Punching geometry independently derived (rectangular `bo`, 4 pile-head perimeters incl. the hexagon `2√3` derivation)
- [x] Punching capacity independently validated (`vc1/vc2/vc3` + governing minimum)
- [x] VF-09 investigated → **RESOLVED, NOT A DEFECT** (record corrected)
- [x] Reinforcement independently validated (bar-count design, `flex_ok`, X/Y directions)
- [x] Minimum reinforcement validated (`temp_ratio·bw·h`, in the verdict)
- [x] Spacing validated (`s ≤ min(3h, 450)`; min clear-spacing NOT IMPLEMENTED, documented)
- [x] Pile cap independently validated (coords n=1…9, elastic reactions)
- [x] Pile reaction equilibrium checked (`Σ R = P`, `Σ R·x = P·ex`)
- [x] Pile coordinate convention investigated (c/c, origin = column centre, `S` consistent)
- [x] Two-pile eccentric distribution investigated → **VF-FOOT-02, R3, FIXED**
- [x] Eccentric footing validated (= eccentric pile cap; F2E default is the VF-FOOT-02 case)
- [x] Boundary matrix exercised (§14)
- [x] False-PASS checks audited (§18 / §22 — VF-FOOT-01 latent-not-reachable, VF-FOOT-02 fixed)
- [x] Screen / report consistency checked (uplift, verdict, units)
- [x] No fabricated reference values; no circular validation; no tolerance manipulation
- [x] Every discrepancy classified (§17 / §18)
- [x] Every production fix proven and regression-protected
- [x] Existing regression ≥ 77 PASS — now **78 passed**
- [x] EV-02 / EV-03 / EV-04 remain clean (120 / 127 / 77, 0 FAIL each)
- [x] EV-05 validation re-run after the fix — 0 FAIL
- [x] `git diff` audited — only `modules/footing.py` (+ untracked `tests/test_footing_calc.py`, EV-05 files); `utils/*` byte-identical to HEAD; no other module touched; no destructive git
- [x] EV-05 completion report created

**EV-05 is complete. EV-06 (recommended: COLUMN) is NOT started.**
