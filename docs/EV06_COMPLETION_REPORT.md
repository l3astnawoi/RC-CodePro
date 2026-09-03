# EV-06 — Completion Report
## Column Engineering Validation (no corrective fix required)

**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`
**Rule applied:** *fix only what the validation proves.* EV-06 found the
column P-M / axial engine **sound** — no production change was warranted.

---

## 1. Scope

**IN:** `modules/column.py` — `_render_column` (rectangular & circular
tied/spiral column P-M design) and the pure helpers `_beta1_col_ksc`,
`_col_bar_xy`, `_whitney_area_centroid`, `_calculate_pm_curve`,
`_point_in_poly`; the column-relevant parts of `utils/aci_318m.py`.

**OUT (per brief §14–15 — NOT to be added):** slenderness, second-order /
moment magnification, biaxial interaction, seismic / confinement
detailing, any new column feature.

**New EV-06 artifacts (untracked, non-production):**
`tests/validation/reference/reference_column_ev06.py` — an **independent
strain-compatibility P-M solver** (`math`-only; ACI equations written out;
**no import of `modules.column`, `utils.aci_318m`, or any production P-M
function**); `tests/validation/run_ev06_column.py` (executable runner, not
a pytest module).

**Production change:** **none.** `modules/column.py` is byte-identical to
its pre-EV-06 state.

## 2. Baseline

```
py -3 -m pytest -q                          -> 78 passed, 0 skipped
py -3 tests/validation/run_ev02_validation.py --brief -> 120: 104 PASS, 0 FAIL
py -3 tests/validation/run_ev03_beam.py --brief       -> 127: 107 PASS, 0 FAIL
py -3 tests/validation/run_ev04_slab.py --brief       -> 77:  58 PASS, 0 FAIL
py -3 tests/validation/run_ev05_footing.py --brief    -> 67:  42 PASS, 0 FAIL
py -3 tests/validation/run_ev06_column.py             -> 87:  60 PASS, 0 FAIL,
                                                           27 REVIEW  (as delivered)
```

## 3. Implementation audit

| Function | Kind | Purpose |
|---|---|---|
| `_beta1_col_ksc(fc_ksc)` | IMPLEMENTED (pure, tested) | MKS β₁ (280 ksc break) |
| `_col_bar_xy(shape, …)` | IMPLEMENTED (pure, tested) | main-bar centre coords, perimeter walk, section-centre origin |
| `_whitney_area_centroid(shape, a, b, D, H)` | IMPLEMENTED (pure, tested) | compressed-concrete area + centroid for stress-block depth `a` |
| `_calculate_pm_curve(*, …)` | IMPLEMENTED (pure, tested) | **strain-compatibility P-M interaction curve, MKS** |
| `_point_in_poly(px, py, xs, ys)` | IMPLEMENTED (pure, tested) | even-odd ray-cast (is `(Mu, Pu)` inside the design polygon) |
| `render_column_module` | UI ONLY | tab / type routing |
| `_render_column()` | IMPLEMENTED (interleaved / BLOCKED) | **Check 1** `ρg` (0.01–0.08), **Check 2** `φPn,max = 0.80·0.65·Po`, **Check 3** tie `S_req = min(16db, 48d_tie, least dim) ≥ 5 cm`, **Check 4** full P-M (`pm_ok` = point-in-polygon). `passed = ratio_ok and axial_ok and spacing_ok and pm_ok` — **AND of all four** |
| `_phi_tied`, `_bar_coords`, `_layers`, `_pm_point`, `_pm_curve`, `_cap_M_at_P`, `_Pn_at_ecc` | **DEAD CODE** | not reached by `_render_column` (matches VF-03) |

**NOT IMPLEMENTED:** slenderness / `kl_u/r` / moment magnification /
second-order; **biaxial** (the docstring says "Bresler reciprocal-load",
but `_render_column` takes a single `Mu` — VF-COL-05); confinement /
seismic detailing; lap splices; dowels; sustained-load stiffness.

## 4. Geometry (phase A)

`_col_bar_xy('rect', …)` vs `reference_column_ev06.rect_bar_xy`
(independent perimeter-walk reproduction), 5 cases (default; cover 5;
DB25; 12 bars; 30×50 section) — **all bar coordinates match exactly**.

The column P-M engine does **not** use a single `d` — every bar layer has
its own depth `d_i = H/2 − y_i` from the compression face (strain
compatibility). `d_max` = extreme tension layer. Verified.

## 5. Material (phase B)

`_beta1_col_ksc` vs the independent MKS β₁, `f'c` = 180 / 240 / 280 / 300
/ 350 / 420 ksc — **all match** rel < 1e-12.

- **VF-COL-02 (= VF-07):** the 280 ksc literal break (vs 28 MPa =
  285.5 ksc). At `f'c = 300 ksc`: engine β₁ = 0.83571, code-consistent =
  0.83986. In `_calculate_pm_curve` a lower β₁ → smaller stress-block
  depth `a` → slightly smaller `Cc` and lever arm; second-order, mixed.
  **R8 (conservative metric convention). ACCEPTED — no fix.**
- **φ strain limit:** `_calculate_pm_curve` uses `ε_ty = fy/Es`
  (= 0.00196 for fy = 4000 ksc) for the compression-controlled limit —
  the **exact** ACI 10.3.3 form, not the 0.002 literal used in beam/slab.
  More precise; inconsistent across modules but **not a defect**. NOTE.

## 6. Reinforcement ratio (phase C)

- `ρg = Ast/Ag` — verified.
- `RHO_MIN = 0.01`, `RHO_MAX = 0.08` (ACI 10.9.1) — verified.
- **`ratio_ok` IS a term of `passed`** (source check) — `ρg` outside
  [0.01, 0.08] → `passed = False` (+ a `st.warning`). **ENFORCED** — no
  computed-but-ignored pattern.

## 7. Pure compression (phase D)

`_calculate_pm_curve` end-points and `_render_column` Check 2 vs the
independent axial anchors:

| Quantity | Result |
|---|---|
| `Po = 0.85 f'c (Ag − Ast) + fy·Ast` (`Pn[0]`) | **PASS** rel < 1e-9 |
| design cap `= 0.80·0.65·Po` (`φPn[0]`) | **PASS** rel < 1e-9 |
| `Pt = −fy·Ast` (`Pn[-1]`) | **PASS** rel < 1e-9 |
| `0.90·Pt` (`φPn[-1]`) | **PASS** rel < 1e-9 |
| `_render_column` Check 2 `φPn,max = 0.80·0.65·Po` | **PASS** rel < 1e-9 |

`Po` = **nominal** pure-axial strength; the design cap `= 0.80·φ·Po`
(φ = 0.65 tied) is the **maximum usable design axial strength**
(ACI 10.3.6.2) and is what `axial_ok` compares against and what the P-M
polygon's top is flattened to.

## 8. φPn,max (phase D)

- Formula: `α·φ·Po` with `α = 0.80`, `φ = 0.65` (tied) / `α = 0.85`,
  `φ = 0.75` (spiral) — ACI 10.3.6.2. Verified.
- **`axial_ok = phiPn_max ≥ Pu` IS a term of `passed`** (source check).
- Additionally, `pm_ok` (Check 4) independently rejects `Pu` above the
  polygon top (which is clamped to the same cap) — φPn,max is enforced
  **twice**, consistently.

## 9. P-M interaction (phase E) — the core

`_calculate_pm_curve` vs `reference_column_ev06.pm_curve` — an
**independent** strain-compatibility solver, compared **1:1 on the same
neutral-axis sweep** (`linspace(1.5H, 0.001H, 44)` + the 2 anchors = 46
points; the sweep grid is only sampling, so using the same grid is not
circular — each point's physics is re-derived independently):

| Array | max relative error (46 points) |
|---|---|
| `Mn` | **1.99 × 10⁻¹³** |
| `Pn` | **8.12 × 10⁻¹⁵** |
| `φMn` | **1.99 × 10⁻¹³** |
| `φPn` | **8.08 × 10⁻¹⁵** |

**`EV-COL-003` / `EV-COL-004` / `EV-COL-005` — UNBLOCKED and VALIDATED.**
EV-01 / EV-02 marked the interior P-M points BLOCKED for lack of a
trustworthy independent reference. EV-06 supplies it. Three named
interior points (low / intermediate / near-boundary eccentricity):

| Case | `c` (cm) | `Pn` (kgf) | `Mn` (kgf·m) | φ | `φMn` (kgf·m) | Result |
|---|---|---|---|---|---|---|
| `EV-COL-003` low ecc. | 48.84 | 399 092 | 2 860.5 | 0.65 | 1 859.3 | **PASS** rel < 1e-9 |
| `EV-COL-004` intermediate | 30.72 | 254 614 | 20 737.2 | 0.65 | 13 479.2 | **PASS** rel < 1e-9 |
| `EV-COL-005` near boundary | 13.98 | 74 174.8 | 23 380.3 | 0.844 | 19 725.6 | **PASS** rel < 1e-9 |

`tests/validation/reference/cases/column_pm.json` updated
(`status: BLOCKED → REFERENCE_READY`, `reference_method: LEVEL_B`).

## 10. Strain compatibility (phase F)

Traced one interaction point back to force equilibrium in **both**
implementations:

- **Balanced point** — analytic `c_b = ε_cu/(ε_cu + ε_y)·d_t = 20.622 cm`
  (`d_t = 34.10 cm`, `ε_y = 0.00196`). At `c_b` the extreme tension layer
  is exactly at yield (`ε_t = ε_y` — verified rel < 1e-9). `Pn ≈ 142 269
  kgf`, `Mn ≈ 26 431 kgf·m`, `φ = 0.65` (compression-controlled at the
  balanced point).
- **Force equilibrium** `C_tot − T_tot − Pn = 0` — residual **< 1 × 10⁻⁶
  kgf** (i.e. exact) in the independent reference.
- Engine vs reference at the dense-grid point nearest `c_b`, both
  evaluated at the **identical `c`** — `Pn` and `Mn` match rel < 1e-9.

The engine's strain model — `ε_s = ε_cu(c − d_i)/c`,
`fs = clip(ε_s·Es, ±fy)`, `0.85 f'c` subtracted for compression bars in
the stress block, `Cc = 0.85 f'c·b·min(a, H)`, `Mn` about the section
centre — is reproduced exactly.

## 11. φ transition (phase G)

`ε_t → φ` (ACI 9.3.2, tied) at compression-controlled (0.001), the
`ε_ty` boundary (0.00196), transition (0.0035 → 0.7766), the
tension-controlled boundary (0.005 → 0.90), and tension-controlled
(0.008 → 0.90) — **all match** rel < 1e-9.

**The column engine does NOT have the EV-03 / EV-04 VF-11 defect.** The
P-M check (`pm_ok`) uses the **per-point φ** computed inside
`_calculate_pm_curve` from each point's `ε_t`; φ varies correctly
0.65 → 0.90 along the curve. Check 2 `φPn,max` uses `φ = 0.65`, correct
for pure axial.

## 12. φMn_at_Pu (phase H) — the "≈ 0 near pure compression" finding

`_render_column` computes a **display** readout
`phiMn_at_Pu = max(φMn_c where │φPn_c − Pu│ ≤ 6 % of max│φPn_c│)`, with an
`np.interp(Pu, φPn_c[::-1], φMn_c[::-1])` fallback.

| `Pu` | readout | mask hits |
|---|---|---|
| ≈ 0.98·φPn,max | ≈ 9 542 kgf·m | 18 |
| ≈ 0.55·φPn,max | ≈ 16 191 kgf·m | 2 |
| ≈ 0.15·φPn,max | ≈ 18 654 kgf·m | 2 |

Answers to the §12 questions:
1. **Physical result, not a numerical artifact.** A section at ≈ pure
   axial has ≈ zero moment capacity — `φMn → 0` is correct there.
2. The point is at / near the top of the interaction curve (`c` large,
   `a → H`, all bars in compression).
3. The 6 %-window mask usually catches ≥ 2 points; the `np.interp`
   fallback is only hit if the mask is empty (rare — the window is wide).
   `φPn_c[::-1]` is non-strictly-increasing (a flat top clamped to the
   cap); `np.interp` handles this but ties are implementation-defined —
   another reason the mask branch is preferred.
4. If `Pu` is near `φPn,max` the readout **should** be ≈ 0 — that is the
   moment capacity available at that axial level.
5. If `Pu` is outside the curve, `pm_ok = False` and `axial_ok = False`
   → the section **FAILs**; `phiMn_at_Pu` is irrelevant to the verdict.
6. **No division-by-zero / zero lever arm.** `_calculate_pm_curve`
   guards `c ≥ 0.001·H`; `_point_in_poly` guards `(yj − yi) or 1e-12`;
   `np.interp` needs no division.

**VF-COL-01 (R10, presentation):** the readout is **not in the verdict**
(source check confirms — `passed` uses `pm_ok`), but shown as a
"capacity" next to a PASS it can read as "Mu vs capacity ≈ 0". A clearer
label (e.g. "utilisation from the interaction diagram") would help — UI,
not a calculation defect. **RECORD, no fix.**

## 13. P-M verdict (phase I)

`_point_in_poly` vs the independent even-odd ray-cast, 4 demand points:

| `(Mu, Pu)` | expected | engine | ind. ray-cast | Result |
|---|---|---|---|---|
| (6 000, 180 000) — inside | inside | inside | inside | **PASS** |
| (0, 900 000) — outside (high axial) | outside | outside | outside | **PASS** |
| (50 000, 180 000) — outside (high moment) | outside | outside | outside | **PASS** |
| (5 000, 1 000) — pure-bending region | inside | inside | inside | **PASS** |

`pm_ok` IS a term of `passed` (source check). Discrete verdict — no
tolerance applied.

## 14. Biaxial (phase L)

**NOT IMPLEMENTED.** The docstring mentions "biaxial … Bresler
reciprocal-load method", but `_render_column` takes a **single `Mu`** and
performs a uniaxial P-M check only. **VF-COL-05 (R10, stale docstring).**
Not added in EV-06.

## 15. Slenderness (phase L)

**NOT IMPLEMENTED.** No `kl_u/r`, no moment magnification, no second-order
analysis. **The column validation applies only to short-column,
unamplified P-M behaviour.** A slender column is outside the tool's
scope — the user must magnify `Mu` externally (ACI 10.10) before entering
it. Not added in EV-06.

## 16. Tie spacing (phase J)

`S_req = min(16·db, 48·d_tie, least dim)` (ACI 7.10.5.2) — formula
verified rel < 1e-12 for 3 bar/tie/section combos.

**VF-10 (re-confirmed from EV-02, R9):** there is **no user-provided
tie-spacing input** — the tool *designs* the spacing (= `S_req`, capped
at 7.5 cm for spiral) and only checks it is buildable (`S_req ≥ 5 cm`),
which is true for every real column. `spacing_ok` is in the verdict but
**effectively always True** — it cannot cause a wrong PASS, but it
validates nothing. Adding a provided-spacing check would be a **new
feature**. **RECORD, no fix.**

## 17. Bar arrangement

`_col_bar_xy` walks `n` bars around the tie perimeter (rect) or evenly on
a circle (circ), section-centre origin, `+y` toward the compression face
— verified against the independent reproduction (§4). The engine checks
`ρg` and the P-M capacity of that arrangement; it does **not** check
minimum bar count per face, clear spacing between bars, or seismic
distribution — **scope limitation** (not added).

## 18. Unit audit (phase B/D/E)

`_calculate_pm_curve` is **MKS-native** (ksc / cm / kgf / kgf·m).
`_render_column` inputs: `b`, `h`, `cov` in cm; `f'c`, `fy`, `fyv` in ksc;
`Pu` in kgf; `Mu` in kgf·m; `main_dia`, `tie_dia` in cm; `Ab =
bar_area(size)/100` cm². `Es = ES_KSC = 2 040 000 ksc`. The independent
reference used the same MKS system and matched to rel < 2e-13 —
**no unit-conversion discrepancy** (no R2 finding).

## 19. Discrepancies

**None that is a production defect.**

| # | Item | Reference | Engine | Root cause | Conservatism |
|---|---|---|---|---|---|
| 1 | full P-M curve (46 pts) | independent strain-compat | identical (rel < 2e-13) | — | **exact match** |
| 2 | VF-COL-01 `φMn_at_Pu` display | physically ≈ 0 near pure axial | ≈ 0 (correct) shown as "capacity" | **R10** | display only, verdict uses `pm_ok` |
| 3 | VF-10 tie-spacing check | provided-spacing check | designs `S_req`, checks ≥ 5 cm | **R9** | near-vacuous, cannot wrongly PASS |
| 4 | VF-COL-02 β₁ 280 ksc | code-consistent 285.5 ksc | 280 ksc | **R8** | conservative, second-order on P-M |
| 5 | VF-COL-03 `Mu` help text | "used in the P-M check" | "not used in this version" | **R10** | stale UI text; `Mu` *is* used |
| 6 | VF-COL-05 biaxial docstring | uniaxial only | docstring claims Bresler | **R10** | stale docstring; NOT IMPLEMENTED |
| 7 | VF-COL-04 `f'c = 0` etc. | (n/a) | no internal guard | **R9** | UI-blocked, unreachable |
| 8 | φ strain limit `fy/Es` vs 0.002 | `fy/Es` (exact ACI 10.3.3) | `fy/Es` | not a defect | more precise than beam/slab |

## 20. Root causes

- **R1–R5 (production defect):** **none.**
- **R8 (conservative metric convention):** VF-COL-02.
- **R9 (scope limitation / by design):** VF-10, VF-COL-04.
- **R10 (UI / presentation):** VF-COL-01, VF-COL-03, VF-COL-05.

## 21. Production fixes

**None.** `modules/column.py` is unchanged. The validation proved the
P-M / axial / φ-transition engine correct; nothing was fixed just to move
a number.

## 22. Regression

No production change → no new regression test (§25 is conditional on a
fixed defect). The existing `tests/test_column_calc.py` golden
`test_calculate_pm_curve_rect_anchor_points` (which already pins a
mid-curve interior point and `Mn.max()`) is now **independently
validated** by EV-06 — it is elevated from "regression only" to
"regression + independently validated".

```
py -3 -m pytest -q   ->  78 passed, 0 failed, 0 skipped   (unchanged)
```

## 23. Cross-module re-validation

| Suite | Result | Δ |
|---|---|---|
| `pytest -q` | **78 passed** | unchanged |
| EV-02 | **120 — 104 PASS, 0 FAIL** | unchanged |
| EV-03 beam | **127 — 107 PASS, 0 FAIL** | unchanged |
| EV-04 slab | **77 — 58 PASS, 0 FAIL** | unchanged |
| EV-05 footing | **67 — 42 PASS, 0 FAIL** | unchanged |
| EV-06 column | **87 — 60 PASS, 0 FAIL, 27 REVIEW, 0 BLOCKED** | new |

`utils/aci_318m.py` / `utils/analysis.py` / `utils/boq.py` byte-identical
to HEAD. `modules/beam.py` / `slab.py` / `footing.py` carry only the
EV-03 / EV-04 / EV-05 fixes (`git diff --stat` unchanged from EV-05).
`modules/column.py` unchanged. No destructive git.

## 24. Engineering safety assessment

- **The column P-M interaction engine is independently validated.** The
  full curve reproduces a from-scratch strain-compatibility solver to
  rel < 2 × 10⁻¹³; force equilibrium and the analytic balanced point are
  verified; the φ transition (0.65 → 0.90 from `ε_t`) is applied
  **per point**, correctly.
- **The column has no VF-11-class defect.** Unlike beam (EV-03) and slab
  (EV-04), which applied a fixed φ = 0.90 and omitted the
  tension-controlled limit from the verdict, `_calculate_pm_curve` uses
  the correct variable φ, and `passed` is the AND of all four computed
  checks (`ρg`, `φPn,max`, tie spacing, P-M). **No reachable
  non-conservative FALSE PASS.**
- **VF-COL-01 / VF-10** are display / scope items — neither changes the
  verdict. VF-COL-02 (β₁ 280 ksc) is conservative. VF-COL-03 / VF-COL-05
  are stale text.
- **Residual:** the tool covers **short-column, uniaxial, unamplified**
  P-M only. Slenderness, biaxial bending and seismic detailing are
  **NOT IMPLEMENTED** — a user designing a slender or biaxially-loaded
  column must handle those effects externally. The assembled
  `_render_column` numbers stay BLOCKED (interleaved), with every
  component (`_calculate_pm_curve`, `_point_in_poly`, the 4 checks'
  formulas) independently verified.
- **Net:** the column geometry, material, reinforcement ratio, pure
  compression, φPn,max, full P-M interaction, strain compatibility, φ
  transition and P-M verdict are validated against ACI 318M-08; no
  production change was needed.

## 25. Recommended EV-07

1. **EV-07 = STAIR** (next module, same pattern). Carry the **VF-11
   pattern check** a fourth time: `stair._as_flexure_ksc` /
   `_required_as_flexure` hardcode φ = 0.90 (already noted in EV-02
   VF-11) — verify `_render_straight_stair` / `_render_u_shape_stair`
   enforce `As ≤ As_max`; if not, and if reachable, the same R3 fix as
   EV-03 / EV-04. Also audit the sloped-waist / triangular-steps dead
   load, `Wu = 1.2 DL + 1.6 LL`, `Mu = Wu L²/8`, and the straight-vs-
   U-shape load-model difference (VF-06).
2. **VF-COL-01** — clearer `φMn_at_Pu` readout (UI: "utilisation from the
   interaction diagram" instead of a "capacity" that reads ≈ 0).
3. **VF-COL-03 / VF-COL-05** — fix the stale `Mu` help text and the
   biaxial docstring (1-line UI / doc changes).
4. **VF-FOOT-01 / VF-FOOT-03** (from EV-05), **VF-SLAB-01** (EV-04),
   **VF-13 / VF-04** (EV-03) — the deferred items.
5. **Wire the EV-02 … EV-06 runners into pytest** behind a marker so the
   independent checks run in CI without moving the default 78-count.

---

## Final checklist (EV-06 acceptance)

- [x] Actual column implementation audited (§3 — IMPLEMENTED / DEAD / NOT IMPLEMENTED)
- [x] Geometry validated (`_col_bar_xy`, 5 cases)
- [x] Material validated (`_beta1_col_ksc`, 6 `f'c`; VF-COL-02 recorded)
- [x] Reinforcement ratio validated (`ρg`, RHO_MIN/MAX, enforced in verdict)
- [x] Pure compression validated (`Po`, `Pt`, cap, `0.90 Pt`)
- [x] φPn,max validated (`0.80·0.65·Po`, enforced in verdict, twice)
- [x] P-M independent reference built + validated (46-point curve, rel < 2e-13)
- [x] Strain compatibility validated (balanced point, force equilibrium residual < 1e-6)
- [x] φ transition validated (compression / transition / tension controlled) — **no VF-11 defect**
- [x] `φMn_at_Pu` investigated (§12 — physical, not in verdict, VF-COL-01 / R10)
- [x] Tie spacing validated (formula) — VF-10 re-confirmed (R9, no provided-spacing input)
- [x] Bar arrangement validated where implemented (`_col_bar_xy`)
- [x] Minimum / maximum reinforcement validated (RHO_MIN/MAX, enforced)
- [x] Final verdict audited (`passed` = AND of all 4 computed checks)
- [x] False-PASS checks audited (§19 / §24 — none; no "warning but PASS")
- [x] Unit consistency checked (§18 — MKS-native, no R2)
- [x] Boundary matrix exercised (§ phase K)
- [x] Slenderness scope documented (NOT IMPLEMENTED)
- [x] Biaxial scope documented (NOT IMPLEMENTED, stale docstring VF-COL-05)
- [x] Every discrepancy classified (§19 / §20 — all R8 / R9 / R10)
- [x] No fabricated reference; no circular validation (independent strain-compat solver)
- [x] No tolerance manipulation; no reference edited to match the engine
- [x] Production fixes proven — **none needed**
- [x] `EV-COL-003 / 004 / 005` UNBLOCKED and VALIDATED
- [x] Existing regression ≥ 78 PASS — **78 passed** (unchanged)
- [x] EV-02 / EV-03 / EV-04 / EV-05 remain clean
- [x] EV-06 re-validated (87 checks, 0 FAIL)
- [x] `git diff` audited — **no production change**; `utils/*` and `modules/column.py` unchanged
- [x] EV-06 completion report created

**EV-06 is complete. EV-07 (recommended: STAIR) is NOT started.**
