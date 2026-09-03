# EV-08 — Completion Report
## Building Model & Load-Takedown Engineering Validation (no corrective fix required)

**Date:** 2026-09-02
**Baseline commit:** `5f51bc423633efc2c561d2fbfb3e13127a910baa`
**Rule applied:** *fix only what the validation proves.* EV-08 found the
Building Model's load path **sound for its scope** — no production change
was warranted. Focus: **CONSERVATION OF LOAD** through the pipeline.

---

## 1. Scope

**IN:** `modules/building.py` (`_parse_spacings`, `_grid_label_x`,
`_column_labels`, `_panel_items`, `_calculate_column_loads`,
`_auto_group_columns`, and the `Wu` computed inside
`render_building_model`) + `utils/boq.py` (`estimate_building_boq`,
`_beam_length_m`).

**OUT (per brief — NOT to be added):** 3D FEM, frame analysis, seismic /
wind / dynamic analysis, structural optimization, multi-storey
accumulation, foundation-reaction pathway, beam line-load takedown, any
new building feature.

**New EV-08 artifacts (untracked, non-production):**
`tests/validation/reference/reference_building_ev08.py` (independent,
`math`-only — **no `modules.*`, no `utils.analysis`**),
`tests/validation/run_ev08_building.py` (executable runner, not a pytest
module).

**Production change:** **none.** `modules/building.py` and `utils/boq.py`
are byte-identical to their pre-EV-08 state.

## 2. Baseline

```
py -3 -m pytest -q                          -> 80 passed, 0 skipped
EV-02 / 03 / 04 / 05 / 06 / 07 runners      -> 0 FAIL each
py -3 tests/validation/run_ev08_building.py -> 79 checks: 60 PASS, 0 FAIL,
                                                  19 REVIEW  (as delivered)
```

## 3. System boundary

**The Building Model = (A) a grid / geometry model builder + (B) a
SINGLE-STOREY tributary vertical load-takedown + a budget BOQ estimate.**

It is **NOT** structural analysis, **NOT** multi-storey, **NOT** a design
check. Evidence:
- The on-screen status is `ui.status_badge("info", "MODEL GENERATED")`
  with the caption *"แบบจำลองเส้นกริดถูกสร้าง… ยังไม่มีการวิเคราะห์
  โครงสร้าง (ถ่ายน้ำหนักในแนวดิ่งด้วยวิธีพื้นที่รับน้ำหนักเท่านั้น)"*
  ("… no structural analysis yet — vertical load takedown by the
  tributary-area method only").
- The PDF report is generated with `status="MODEL"` → verdict *"MODEL
  GENERATED"*.
- There is **no `passed` boolean**, **no `status_badge("pass"…)`**.
- It does **not** import or call `utils.analysis`
  (`solve_continuous_beam`) — no coupling to the continuous-beam solver.

**Correct — no false design PASS.**

## 4. Implementation map

| Function | Kind | Purpose |
|---|---|---|
| `_parse_spacings(text, fallback)` | IMPLEMENTED (pure, tested) | bay-spacing string → cumulative coords; drops non-positive / non-numeric |
| `_grid_label_x` / `_column_labels` / `_panel_items` | IMPLEMENTED (pure, tested) | node / panel enumeration & labelling |
| `_calculate_column_loads(x, y, active, voids, Wu, labels)` | IMPLEMENTED (pure, tested) | **tributary quarter-area column load-takedown** (one floor) |
| `_auto_group_columns(loads)` | IMPLEMENTED (pure, tested) | **rule-based** `Pu/Pmax` clustering → C1 / C2 / C3 (mislabelled "AI" — ER-03) |
| `render_building_model()` | INTERLEAVED (BLOCKED) | UI + `Wu = 1.2·(t/100·2400 + SDL) + 1.6·LL` (VF-01) + preview + BOQ button + report |
| `utils/boq.estimate_building_boq(...)` | IMPLEMENTED (pure, tested) | budget concrete / formwork / rebar for **one storey** |
| `utils/boq._beam_length_m(...)` | IMPLEMENTED (pure, tested) | total beam length on grid lines bounding solid panels |
| `_fmt_cell`, `_html_table` | UI ONLY | table rendering |

**DEAD CODE:** none. **NOT IMPLEMENTED:** §37.

## 5. Geometry

| Quantity | Result |
|---|---|
| `_parse_spacings` — cumulative coords, empty / all-invalid / mixed-separator | **PASS** exact (drops `x`, blanks, `-2`; accepts `;` and newline) |
| `_grid_label_x` — `0…52 → A…BA` | **PASS** exact |
| column count `= nx · ny` ; panel count `= (nx−1)(ny−1)` | **PASS** exact |
| `floor area = X-extent · Y-extent` | **PASS** rel < 1e-12 |
| `Σ(bay spacings) == grid extent` | **PASS** rel < 1e-12 |

## 6. Member assignment

Node / column / panel enumeration is **row-major** (`nodes = [(x, y) for y
in y_coords for x in x_coords]`), labels `A-1, B-1, …`, panels `Panel A-B
/ 1-2, …`. Removed columns come from a `multiselect` of labels; void
panels from a `multiselect` of panel labels. No connectivity graph, no
beam / column objects — the model is a **coordinate grid + a set of
active nodes + a set of void panels**. Verified against the golden
fixtures and the independent enumeration.

## 7. Floor loads

`Wu = 1.2·(slab_t/100·2400 + slab_sdl) + 1.6·slab_ll` — the **only** load
in the pipeline. `slab_t` cm, `slab_sdl` / `slab_ll` kgf/m². Verified by
independent reconstruction for `t` = 5 / 12 / 15 / 20 cm and various
SDL / LL (rel < 1e-9). **There is no separate service-load path** — the
Building Model works in factored `Wu` only (a limitation, §37).

## 8. Tributary areas — **P0**

`_calculate_column_loads`: every **solid** panel `(i, j)` contributes
`panel_area / 4` to **each of its four corner nodes**; **void** panels
contribute nothing; a quarter-area whose corner is **not an active
column** is **dropped**. Returns `{(x, y): {trib_area_m2, Pu_kgf = area·Wu}}`.

Verified against an independent quarter-area implementation:

| Case | Result |
|---|---|
| full solid 4×3 grid — all 12 columns' `trib_area` & `Pu` (1:1) | **PASS** rel < 1e-9 |
| symmetric 3×3-bay grid — `corner : edge : interior` tributary ratio | **1 : 2 : 4** exactly |
| interior column tributary `= s_x · s_y` ; edge `= s_x · s_y/2` ; corner `= s_x · s_y/4` | **PASS** (the quarter-area method reproduces the textbook tributary areas for a regular grid) |

## 9. Load distribution / conservation — **the acceptance criterion**

| Case | `Σ trib_area` vs | Result |
|---|---|---|
| **full solid grid** (all active, no voids) | `= floor_area` **exactly**; `Σ Pu = Wu · floor_area` | **PASS** rel < 1e-9 — **LOAD CONSERVED** |
| **void panel** | `= solid_area` (`= floor − void`); `Σ Pu = Wu · solid_area` | **PASS** — a void genuinely carries no load; consistent exclusion |
| **removed column** | `= floor_area − dropped`; `dropped > 0` | **VF-05** — see §10 / §31 |

`_calculate_column_loads` matches the independent tributary
implementation **rel < 1e-9** in every case. **Scaling:** ×2 `Wu` → ×2
`Σ Pu`; ×4 floor area → ×4 `Σ Pu`. **Symmetry:** the 4 corners are
equal, the 8 edges are equal, the 4 interior nodes are equal (equal
bays).

## 10. Load conservation — the removed-column case (VF-05)

Removing column **B-2** from the 4×3 grid: `Σ trib_area = 74.0 m²` vs
`floor_area = 104.0 m²`. The **30.0 m²** difference is the sum of the
four quarter-panels around B-2 — it is **DROPPED**, not redistributed to
the neighbours. The independent check confirms:

> `Σ trib_area + dropped == floor_area` (rel < 1e-9)
> — no area is **created or duplicated**; area is only **lost**.

So `Σ Pu` is **`Wu · 30 000` kgf below** `Wu · floor_area` —
**non-conservative** (the columns adjacent to B-2 carry more load in
reality than the model reports). This is **documented in
`_calculate_column_loads`' own docstring** ("Quarter-areas landing on a
removed column are dropped (simplified column takedown)"). **Root cause
R9 / R8** — an intentional simplification of a model-generation + BOQ
tool. **RECORD (re-confirms VF-05). No fix** — redistributing the dropped
quarters would be **adding a feature** (forbidden). The tool must not be
used for irregular-grid column takedown without engineer review.

## 11. Double-counting audit

The **only** self-weight in the load path is the **slab** self-weight
inside `Wu` (`t · 2400`). It is:
- **generated once** — in the `Wu` expression;
- **transferred once** — as `Wu` into `_calculate_column_loads`;
- **accumulated once** — the tributary sum per node.

Beam / column self-weight are **not** in the takedown (they appear only
in the BOQ concrete volume — a **separate quantity pathway**). **No
double-counting.**

## 12. Missing-load audit

- **Slab self-weight** — present (in `Wu`).
- **Beam / column self-weight** — **absent** from the takedown (a known
  under-estimate; part of the "MODEL GENERATED, not analysis" scope).
- **Multi-storey accumulation** — **absent** (`_calculate_column_loads`
  runs **once**; no storey loop; no `P_base = Σ Q_floor`). The tool
  reports **one floor's** tributary column loads only.
- **Stair self-weight** — a **separate module** (EV-07); it is **not**
  added to the building floor slab → **no cross-module double count**,
  but also not carried into the building takedown.

## 13. Column takedown

`Σ Pu` over all active columns = the on-screen "ผลรวมแรงถ่ายลงเสาทั้งหมด".
For a full solid grid this equals `Wu · floor_area` (conserved). **No
cumulative / multi-floor behaviour** — `Pu` is a single floor's tributary
load. **BUILD-COL-002 / -003 (2- / 3-storey accumulation) → NOT
IMPLEMENTED.**

## 14. Beam takedown

**NOT IMPLEMENTED.** The Building Model does **not** convert the area
load to a beam line load (`w = q · tributary_width`). Beams appear only
in the BOQ (their total length × section → concrete / formwork / rebar).

## 15. Slab transfer

The slab load is **generated once** (in `Wu`) and **distributed once**
(tributary → columns). The **slab-design** load (in `modules/slab.py`,
EV-04) is a **separate design pathway** with its own inputs — it is **not**
the Building Model's `Wu`, so there is **no double count** between the two.
The BOQ's slab **area** (`grid_area − void_area`) is a quantity, not a
load.

## 16. Foundation reaction

**NOT IMPLEMENTED.** The tributary `Pu` values are **not** fed to footing
design. There is no `Σ footing reactions ≈ building supported load` check
because there is no foundation pathway. (`modules/footing.py`, EV-05, is a
standalone tool.)

## 17. Self-weight

Only the **slab** — `t · 2400 kgf/m³` (the MKS literal, ≈ 1.9 % below
`24 kN/m³`; **R8 NOTE**, identical to beam / slab / footing / stair). No
beam / column / stair self-weight in the load path (§12). The BOQ
concrete volumes use the same section dimensions the user enters; they
are quantities, not weights applied as loads.

## 18. Live load

`slab_ll` (kgf/m²), one value, applied to the whole floor via `Wu`. **No
per-floor LL**, **no live-load reduction** (ASCE 7 / ACI), **no pattern
loading**. Documented limitation.

## 19. Load combination

`Wu = 1.2·D + 1.6·L` (ACI 318M-08 9.2) — the **only** combination.
`D = slab self-weight + SDL`, `L = LL`. Verified by independent
reconstruction. **No combining twice**: `Wu` is computed once and flows
straight into the tributary takedown; nothing downstream re-adds `L`.

## 20. Unit audit

| Symbol | Unit | Trace |
|---|---|---|
| grid spacings, coords, extents | m | `_parse_spacings` (text → float, cumulative) |
| `slab_t` | cm | `/100` → m in `Wu` and BOQ |
| `slab_sdl`, `slab_ll`, `Wu` | kgf/m² | `Wu` expression |
| `trib_area_m2` | m² | Σ of `(Δx)(Δy)/4` |
| `Pu_kgf` | kgf | `trib_area_m2 · Wu` |
| section dims (`col_b/h`, `beam_b/h`) | cm | `/100` → m in BOQ |
| `floor_height_m` | m | BOQ |
| BOQ outputs | m³ / m² / kg | independent take-off matched rel < 1e-9 |

**No R2 conversion finding.** The `2400` literal is the documented MKS
convention (R8).

## 21. Golden buildings

| Case | Grid | Result |
|---|---|---|
| BUILD-GOLD-001 | 1×1 bay | `Σ trib = floor_area`; `Σ Pu = Wu·area` — **PASS** |
| BUILD-GOLD-002 | 2×2 bays | **PASS** |
| BUILD-GOLD-003 | 3×3 bays (`4,5,4` × `4,4,4`) | **PASS** |
| BUILD-GOLD-004 | 3×4 bays (`4,5,4` × `3,4,5,3`) | **PASS** |

All full solid grids → **exact load conservation** (rel < 1e-9). No
"asymmetric loading" case — the Building Model applies **one uniform `Wu`**
to the whole floor (no per-panel or per-region load input).

## 22. Symmetry

Symmetric 3×3-bay grid, equal 4 m bays: **4 corners equal**, **8 edges
equal**, **4 interior equal** (Δ < 1e-6), with tributary ratio
`corner : edge : interior = 1 : 2 : 4`. **PASS.**

## 23. Scaling

- Double `Wu` → `Σ Pu` doubles (rel < 1e-9).
- Double every span (×4 floor area) → `Σ Pu` ×4 (rel < 1e-9).

Linear in `Wu` and in area, as expected for a tributary-area method.

## 24. Conservation

For a **full solid grid** every stage conserves:
`input Wu · floor_area  ==  Σ node Pu` (rel < 1e-9). Void panels: `Σ Pu =
Wu · solid_area`. Removed columns: `Σ Pu = Wu · (floor_area − dropped)` —
the only non-conservation, quantified and documented (§10, VF-05). There
is **no foundation stage** — the lowest implemented level is the column
tributary `Pu`.

## 25. Verdict

**No pass/fail verdict.** Status = *"MODEL GENERATED"* (info badge) / the
PDF `status="MODEL"`. **No false-PASS pattern** because there is no PASS.

## 26. Report / summary consistency

On-screen the model shows `Σ Pu` ("ผลรวมแรงถ่ายลงเสาทั้งหมด"). The PDF
report params show `Wu` and `total_solid_area (= boq["slab"]["area_m2"])`
— it does **not** print `Σ Pu`, so **no screen/report number
disagrees**. `Wu · total_solid_area` is the ideal takedown total;
`Σ Pu ≤ that` when columns are removed (VF-05). Both are correctly
labelled. **R10 at most** — no fix.

## 27. BOQ boundary

`estimate_building_boq` reproduces an independent take-off **rel < 1e-9**
(concrete `= n·b·h·fh` / `len·b·web` / `area·t`; formwork; rebar `=
concrete · {150, 120, 90}`). It is a **quantity** output — **not a load
source**; nothing structural is computed from it, and the caption reads
"ค่าประมาณเบื้องต้นสำหรับงบประมาณ" (preliminary budget estimate only).
**VF-08 (re-confirmed)** — the ratios have no cited source; R8 / R9;
no fix.

## 28. Analysis boundary

`render_building_model` **does not** import or call `utils.analysis`
(`solve_continuous_beam`). The Building Model and the continuous-beam
analysis (`modules/beam.py` analysis tab, EV-02 / EV-03) are **fully
separate** pathways. **No coupling created in EV-08.**

## 29. Invalid inputs

| Input | Behaviour | Verdict |
|---|---|---|
| `_parse_spacings("")` / `("x,,-1")` | falls back / drops → valid coord list — no crash | OK |
| `_calculate_column_loads(active=[])` | `{}` — no crash | OK |
| `_calculate_column_loads(Wu=0)` / `(Wu=-500)` | linear — `Pu` = 0 / negative — no crash | OK |
| `estimate_building_boq(empty grid)` | all-zero — no crash | OK |
| `estimate_building_boq(beam_h < slab_t)` | `web = max(…, 0)` clamps to 0 — no crash | OK |

**VF-BLDG-02 (new, R9):** no `ZeroDivisionError` arises (no material
strength in this module); degenerate inputs are graceful. UI-blocked by
`st.number_input(min_value)` and text parsing. **RECORD — no fix.**

## 30. False-PASS audit

The Building Model has **no pass/fail verdict** and **no safety check to
omit** — it is a model builder + takedown + BOQ. There is **no
"warning but PASS" pattern** because there is no PASS. **VF-11 class
N/A** (no flexural design).

## 31. Findings

| # | Finding | Root cause | Conservatism |
|---|---|---|---|
| 1 | **VF-05** (re-confirmed) — removed-column quarter-areas dropped, not redistributed | **R9 / R8** | **NON-conservative** for irregular grids (neighbour `Pu` under-estimated); documented; bounded (`Σarea + dropped = floor_area`) |
| 2 | **ER-02** (re-confirmed) — report title says "Analysis" | **R10** | verdict correctly "MODEL GENERATED" |
| 3 | **ER-03** (re-confirmed) — `_auto_group_columns` mislabelled "AI" | **R10** | fixed-threshold clustering; no calc impact |
| 4 | **VF-08** (re-confirmed) — BOQ rebar ratios 150/120/90, no cited source | **R8 / R9** | quantity output, not a load source; captioned "budget estimate only" |
| 5 | **VF-BLDG-02** (new) — no internal guards for degenerate inputs | **R9** | UI-blocked, unreachable; graceful anyway |
| 6 | multi-storey / foundation / beam takedown | **R9 scope** | NOT IMPLEMENTED |
| 7 | slab `2400 kgf/m³` self-weight literal | **R8** | ≈ 1.9 % low; MKS convention |
| 8 | VF-01 `Wu` interleaved in render | resolved — formula validated by reconstruction | assembled per-column numbers stay BLOCKED |

## 32. Root causes

- **R1–R5 (production defect):** **none.**
- **R8 (conservative / intentional approximation):** VF-05, VF-08, `2400`.
- **R9 (scope limitation):** VF-05, VF-08, VF-BLDG-02, multi-storey /
  foundation / beam takedown.
- **R10 (UI / presentation):** ER-02 (title), ER-03 ("AI").

## 33. Production fixes

**None.** `modules/building.py` and `utils/boq.py` are unchanged. The
load path is validated (conservation holds for the regular grid), the
`Wu` formula is validated, the BOQ arithmetic is validated, and the tool
correctly reports "MODEL GENERATED" with no design verdict.

## 34. Regression

No production change → no new regression test (§36 is conditional on a
fixed defect). The existing `tests/test_building_calc.py` (11 tests) and
`tests/test_boq.py` (4 tests) goldens — which already pin the full-grid
load conservation (`sum trib_area == 104.0`, `sum Pu == 104000`), the
removed-column case (`74.0`), the auto-grouping marks, and the BOQ
quantities — are now **independently validated** by EV-08 (elevated from
"regression only" to "regression + independently validated").

```
py -3 -m pytest -q   ->   80 passed, 0 failed, 0 skipped   (unchanged)
```

## 35. Cross-module re-validation

| Suite | Result | Δ |
|---|---|---|
| `pytest -q` | **80 passed** | unchanged |
| EV-02 | **120 — 104 PASS, 0 FAIL** | unchanged |
| EV-03 beam | **127 — 107 PASS, 0 FAIL** | unchanged |
| EV-04 slab | **77 — 58 PASS, 0 FAIL** | unchanged |
| EV-05 footing | **67 — 42 PASS, 0 FAIL** | unchanged |
| EV-06 column | **87 — 60 PASS, 0 FAIL** | unchanged |
| EV-07 stair | **70 — 40 PASS, 0 FAIL** | unchanged |
| EV-08 building | **79 — 60 PASS, 0 FAIL, 19 REVIEW, 0 BLOCKED** | new |

`utils/aci_318m.py` / `utils/analysis.py` / `utils/boq.py` byte-identical
to HEAD. `modules/{beam,slab,footing,column,stair}.py` carry only their
EV-03 … EV-07 changes. `modules/building.py` unchanged (`git diff --stat`
= the pre-existing STEP work only). No destructive git.

## 36. Remaining REVIEW

VF-05 (irregular-grid takedown — R9 / R8, documented), ER-02 (report
title — R10), ER-03 ("AI" wording — R10), VF-08 (BOQ ratios — R8 / R9),
VF-BLDG-02 (degenerate inputs — R9). None is a production bug; all are
scope / presentation / documented-approximation.

## 37. Not implemented

Multi-storey column-load accumulation; foundation-reaction pathway; beam
line-load takedown; lateral / wind / seismic / dynamic analysis; frame
analysis; member self-weight beyond the slab; pattern loading; load
combinations other than `1.2D + 1.6L`; live-load reduction; per-floor
live load; a service-load pathway; irregular / non-uniform floor loads.

## 38. Engineering safety assessment

- **Load conservation is validated for the intended use case** (a regular
  grid with all columns present): `Σ Pu = Wu · floor_area` exactly, and
  the corner : edge : interior tributary split is the textbook 1 : 2 : 4.
  The `Wu = 1.2D + 1.6L` combination is ACI-correct.
- **The tool is correctly scoped and labelled.** It is a **model builder
  + single-storey tributary takedown + budget BOQ** — it says so
  on-screen ("no structural analysis yet") and in the PDF ("MODEL
  GENERATED"). It has **no pass/fail verdict** and computes nothing that
  is *sized* from the takedown — so there is **no false-PASS risk** and
  the VF-11 class does not apply.
- **VF-05** is the one non-conservation: for grids with **removed
  columns**, the tributary area of the dropped quarter-panels is **not**
  redistributed, so the neighbouring column loads are **under-estimated**.
  This is documented in the code, bounded (`Σarea + dropped =
  floor_area`), and downstream feeds only the preliminary C1/C2/C3
  grouping and an on-screen total — **nothing is sized from it**. An
  engineer using the Building Model for column load takedown on an
  irregular grid must review / adjust the affected columns manually.
- **Not a design tool:** multi-storey accumulation, foundation reactions,
  beam takedown, non-slab self-weight and lateral loads are **NOT
  IMPLEMENTED** — the Building Model must not be relied on as a complete
  gravity load path.
- **Net:** the grid geometry, member enumeration, factored slab load,
  tributary column takedown (regular grid), rule-based grouping and the
  budget BOQ are independently validated; no production change was needed.

## 39. Recommended EV-09

1. **EV-09 = SYSTEM-WIDE CONSOLIDATION** — with all eight member / model
   modules now validated, EV-09 should:
   - **Wire the EV-02 … EV-08 runners into `pytest`** behind a marker
     (e.g. `-m validation`) so the ~570 independent checks run in CI
     without moving the default 80-count; report `regression 80 /
     validation P·F·R·B`.
   - **Close the deferred R10 / doc items** in one pass: VF-COL-01 (clearer
     `φMn_at_Pu` readout), VF-COL-03 / VF-COL-05 (stale `Mu` help text /
     biaxial docstring), ER-02 (Building report title), ER-03 ("AI" →
     "rule-based" wording) — all 1-line UI / doc changes, each with a
     before/after.
   - **Make the engineering decisions** on VF-SLAB-01 (Grashof two-way
     method: name it + applicability note, or replace with an ACI
     method), VF-FOOT-01 / VF-FOOT-03 (defense-in-depth ductility gate /
     effective-depth harmonisation), VF-13 (MKS beam-shear coefficients),
     VF-04 (analytic interior-peak moment — moves `test_analysis.py`
     goldens).
   - **Re-run all eight runners + `pytest`** after each change; keep
     0 FAIL throughout.
2. Do **not** start EV-09 automatically.

---

## Final checklist (EV-08 acceptance)

- [x] Actual Building implementation audited (§4)
- [x] System boundary clearly documented (§3 — model builder + single-storey takedown + BOQ, no verdict)
- [x] Independent reference created (`reference_building_ev08.py`, math-only, no `modules.*` / `utils.analysis`)
- [x] Geometry validated (§5)
- [x] Member assignment validated (§6 — row-major enumeration)
- [x] Floor area validated (§5)
- [x] Tributary area validated (§8 — corner : edge : interior = 1 : 2 : 4)
- [x] Dead load validated (§7 / §19 — slab self-weight in `Wu`)
- [x] Live load validated (§18 — one `slab_ll` per floor; per-floor LL NOT IMPLEMENTED)
- [x] Load combination validated (§19 — `1.2D + 1.6L`, ACI 9.2)
- [x] Load distribution validated (§9 — matches independent tributary rel < 1e-9)
- [x] **Load conservation validated** (§9 / §24 — `Σ Pu = Wu · floor_area` for the regular grid)
- [x] Double-counting audit completed (§11 — none)
- [x] Missing-load audit completed (§12 — multi-storey / beam / column self-weight NOT in path, documented)
- [x] Column takedown validated (§13 — single-storey; multi-storey NOT IMPLEMENTED)
- [x] Beam takedown — NOT IMPLEMENTED (§14)
- [x] Slab transfer validated (§15 — generated once, distributed once; separate from slab design)
- [x] Foundation reaction — NOT IMPLEMENTED (§16)
- [x] Self-weight paths validated (§17 — slab only; no cross-module stair double count)
- [x] Unit audit completed (§20 — no R2)
- [x] Golden buildings completed (§21 — 4 full solid grids, exact conservation)
- [x] Symmetry test completed (§22)
- [x] Scaling test completed (§23)
- [x] Final status / verdict audited (§25 — "MODEL GENERATED", no PASS)
- [x] Report / summary consistency checked (§26)
- [x] BOQ boundary checked (§27 — quantity, not a load; validated rel < 1e-9)
- [x] Analysis boundary checked (§28 — no coupling to `utils.analysis`)
- [x] Invalid-input behaviour documented (§29 — VF-BLDG-02, graceful, UI-blocked)
- [x] False-PASS audit completed (§30 — N/A, no verdict)
- [x] Every discrepancy classified (§31 / §32 — R8 / R9 / R10 only)
- [x] No circular validation; no fabricated reference
- [x] Production fixes test-first — **none needed**
- [x] Regression ≥ 80 PASS — **80 passed** (unchanged)
- [x] EV-02 … EV-07 = 0 FAIL each
- [x] EV-08 re-validated — 0 FAIL
- [x] `git diff` audited — **no production change**; `modules/building.py`, `utils/boq.py`, `utils/*` unchanged
- [x] EV-08 completion report created

**EV-08 is complete. EV-09 (recommended: system-wide consolidation) is NOT started.**
