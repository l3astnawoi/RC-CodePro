# RC CodePro — System Capability Matrix (EV-09)

**Status date:** 2026-09-03 · **Baseline:** `pytest` 80 passed / 0 failed / 0 skipped ·
EV-02…EV-09 runners **0 FAIL** · **Code:** ACI 318M-08, MKS display (cm, kgf, ksc,
kgf·m, kgf/m²), SI internally in `utils/aci_318m.py`.

This matrix answers the EV-09 question at the **system** level:

> *A validated Calculation Engine result — does it reach the UI / Summary /
> Drawing / Report **without changing VALUE, UNIT, STATUS or engineering
> meaning**, and **without producing a FALSE PASS**?*

Legend — **Validation Status**: `INDEPENDENT` = checked against a first-principles
reference that does **not** import production code (EV-02…EV-08); `REGRESSION` =
pinned by `tests/` only; `BLOCKED` = interleaved compute/render chain, not
importable as an end-to-end number (§10 of `ENGINEERING_VALIDATION.md`).
**Verdict chain**: `ENGINE → checks list + passed → ui.engineering_table (screen)`
**and the same** `checks + status → render_report_expander → build_report (PDF)`;
the drawing layer consumes already-computed values only.

---

## 1. Module × Capability

| Module | Calculation Capability | Validation Status | UI Status | Report Status | Drawing Status | Scope | Known Review | Release Status |
|---|---|---|---|---|---|---|---|---|
| **Beam** | Flexure (`_flex_ksc` / SI chain), shear (`vc_beam` 0.53√f'c MKS), `As,min` / **`As,max` (tension-controlled, EV-03 fix)**, φ=0.90 flexure with **ductility gate**, bar fit / spacing, 3-section (−M/+M/−M) | **INDEPENDENT** (EV-02 flexure+shear primitives; EV-03 127 checks 0 FAIL) · assembled `_render_beam_section` number = BLOCKED | `PASS` / `FAIL` badge (`ui.status_badge`) + per-row demand/capacity table + `st.error(FAIL_TXT + reasons)` on failure | Same `checks` + `status=passed` passed **unchanged** to `build_report`; `_status_state` no recompute | `draw_beam_*` — geometry, bars, stirrups, dimensions from design values; **no recompute** | Simply-/continuously-supported, positive+negative flexure, one-way shear, detailing that is implemented. **No** torsion / deflection / crack / development-length / deep-beam / lateral. | VF-04 (sampled +M peak, ≤~0.003 % non-conservative, bounded), VF-07/VF-12/VF-13 (MKS coefficient roundings — conservative), SYS-01 (EV-09 discovered → CLOSED in UI-01) | **READY** |
| **Slab** | One-way flexure, implemented two-way moment model, temperature/shrinkage steel, bar spacing, **ductility gate (EV-04 fix)** | **INDEPENDENT** (EV-04 77 checks 0 FAIL) · assembled `_render_slab_design` = BLOCKED · two-way coefficient **source** = `CODE REFERENCE REQUIRED` | `PASS` / `FAIL` badge + checks table + `st.warning` + `st.error` on failure | `checks` + `status` **unchanged** to `build_report` | `draw_slab_*` — panel, bar mat, spacing labels from design values; **no recompute** | One-way flexure + the **implemented** two-way moment method + temp steel + spacing + ductility. **No** punching / one-way shear / deflection / crack / development length / torsion. | **VF-SLAB-01** — two-way moment method is Grashof/Marcus-family, **non-ACI**; implemented **correctly** for what it is → `REVIEW`, number unchanged. VF-SLAB-02/03, SYS-01 (CLOSED — UI-01). | **READY (one-way)** · two-way = **REVIEW** (method disclosed) |
| **Footing** | Isolated: bearing, one-way (beam) shear, two-way (punching) shear, flexure, `d = h−cov−dₙ`. Pile cap: pile reaction distribution (axial + biaxial `M/Σx²`), **eccentricity-resolvable gate (EV-05 fix)**, per-pile punching, group flexure | **INDEPENDENT** (EV-05 67 checks 0 FAIL) · assembled `_render_isolated_footing` / `_render_pile_cap` = BLOCKED · nested `_elastic_reactions` / `_side` / `_s0` not importable | `PASS` / `FAIL` badge + checks table + `st.error` (incl. "resists eccentricity" chip) on failure | `checks` + `status` **unchanged** to `build_report` (both `render_report_expander` call sites) | `draw_footing_*` / `draw_pile_cap_*` — plan, section, pile layout, rebar from design values; drawing clamps only (`0.85·h` embed) — **no recompute** | Isolated footing + pile-cap **implemented** checks. **No** combined footing / mat / strap / raft / soil-structure interaction / settlement / pile group settlement / lateral pile. | **VF-09 RESOLVED — not a defect** (`3.464 = 2√3` is the exact regular-hexagon perimeter factor; circular branch uses `π(Dp+d)` correctly). **VF-FOOT-01** — VF-11 class **latent but not reachable** (shadowed by punching + one-way shear + bearing + flexure-infeasibility, all enforced). VF-FOOT-03 (`d` conservative). SYS-01 (CLOSED — UI-01). | **READY** |
| **Column** | Axial `Po`, `φPn,max` cap (`0.80·0.65·Po` tied), **full P–M interaction curve** (strain-compatibility, 44-point sweep + `Po` / `Pt` anchors), **variable φ 0.65→0.90** (ACI 9.3.2), ρ = Ast/Ag limits, tie spacing where implemented | **INDEPENDENT** — EV-06: the production `_calculate_pm_curve` matches an independent strain-compatibility solver to **rel < 2e-13**; `EV-COL-003/004/005` **UNBLOCKED & VALIDATED**; **0 production fixes** | `PASS` / `FAIL` badge + `pm_ok = point-in-polygon(Mu, Pu, φMn, φPn)` + checks table + `st.error` on failure | `checks` + `status` **unchanged** to `build_report` | `draw_column_*` + P–M diagram plot the **passed-in** curve arrays (`Mn = np.asarray(Mn)` for plotting only); "Safe zone (inside design curve)" label is engineering-correct — **no recompute** | Short column, **uniaxial** P–M, **unamplified** moments, tie calc where implemented. **No** slenderness / P-Δ / biaxial (Bresler) / confinement / splice design. | **VF-COL-01** — `φMn_at_Pu` display reads ≈0 near pure axial (display-only, **not** in `passed`). **VF-COL-03** — `Mu` input help text "not used in this version" is **stale** (Mu **is** used in `pm_ok`). **VF-COL-05** — module docstring mentions "biaxial / Bresler" — **stale** (uniaxial only). VF-10 (tie check has no provided-spacing input). SYS-01 (CLOSED — UI-01). All R10 / R9. | **READY (uniaxial short column)** |
| **Stair** | Straight flight + U-shape as an **inclined one-way slab**; DL of sloped waist (`t/cosθ`) + triangular steps (`R/2`); `Wu = 1.2DL + 1.6LL`; **positive mid-span** flexure `Mu = wL²/8`; `As,min` / temp steel; bar spacing; **ductility gate (EV-07 fix, VF-STAIR-01)** | **INDEPENDENT** (EV-07 70 checks 0 FAIL) · assembled `_render_straight_stair` / `_render_u_shape_stair` = BLOCKED | `PASS` / `FAIL` badge + checks table + `st.warning` + `st.error` on failure | `checks` + `status` **unchanged** to `build_report` | `draw_stair_*` — CAD elevation, tread/riser, waist, bars from design values; **no recompute** | Straight + U-shape, **inclined one-way slab**, **positive mid-span** flexure, min/temp steel, spacing, ductility. **No** support/negative moment, **no** flight shear, **no** landing two-way action, **no** deflection, **no** stringer/folded-plate. Load model = simply-supported span. | **VF-06** (straight-vs-U load model), STEP-14 (FAIL→REVIEW display — no engineering result masked, verified EV-07), VF-STAIR-02/03. SYS-01 (CLOSED — UI-01). | **READY (mid-span flexure of the idealised inclined slab)** |
| **Building Model** | Grid / geometry model, member enumeration, factored slab load `Wu = 1.2(t·2400+SDL) + 1.6LL`, **single-storey tributary vertical load-takedown**, rule-based preliminary column grouping (C1/C2/C3), budget BOQ | **INDEPENDENT** (EV-08 79 checks 0 FAIL) — **load conservation** `Σ Pu = Wu·floor_area` for the regular grid to **rel < 1e-9**; **0 production fixes** · assembled `render_building_model` `Wu` = BLOCKED (interleaved) | **`MODEL GENERATED`** (`info` badge — **never** a design PASS) + caption "…ยังไม่มีการวิเคราะห์โครงสร้าง…" | `status="MODEL"` → **`MODEL GENERATED`**; `_status_state("MODEL")` → `"MODEL"` — PDF **cannot** turn MODEL into PASS | `draw_building_grid` / column-load map — grid + tributary from model values; **no recompute** | (A) grid/geometry builder + (B) **single-storey** tributary vertical takedown + (C) budget BOQ. **NOT** structural analysis, **NOT** multi-storey accumulation, **NOT** a foundation reaction pathway, **NOT** beam line-load analysis, **NOT** lateral/wind/seismic. **No pass/fail verdict.** | **VF-05** — quarter-areas landing on a **removed** column are **dropped** (non-conservative for irregular grids; bounded: `Σarea + dropped = floor_area`; nothing is *sized* from these `Pu`). **ER-02** (report title "Analysis" over-claims — verdict is correctly MODEL). **ER-03** ("AI" wording for threshold clustering). VF-08 (BOQ rebar ratios — quantity only, not a load). | **READY as a MODEL** (not a design/analysis release) |
| **Continuous Beam Analysis** (`utils/analysis.py`) | `solve_continuous_beam` — three-moment (Clapeyron) method, SFD/BMD, support reactions, governing ±M | **INDEPENDENT** (EV-02 — independent three-moment reference; matches) | Feeds the Beam tab's demand side + SFD-BMD plot; no standalone verdict | Values flow into the Beam report as demand | SFD/BMD plot consumes computed arrays — **no recompute** | Prismatic continuous beam, point + UDL, vertical loads, small-deflection linear-elastic. **No** settlement / spring supports / non-prismatic / second-order / moment redistribution. | **VF-04 / ER-04** — governing **+M** is the peak of the **sampled** `M(x)` array → can sit marginally (≤~0.003 %) below the true analytic max between sample points. **Non-conservative but bounded**; test-locked. | **READY** (limitation documented) |
| **Drawing** (`utils/drawing.py`) | Matplotlib CAD: beam / column / slab / footing / pile-cap / stair / building-grid geometry, reinforcement, dimensions, P–M diagram plot | **N/A** (presentation) — EV-09 source audit: **no** call to `_calculate_pm_curve`, `solve_continuous_beam`, `_*flexure*`, `vc_beam`, `rho_max` | Rendered `st.image` / `st.pyplot` in the dark UI | **Same** PNG buffer embedded (white) in the PDF | — | Geometry + labels from **already-computed** values. Arithmetic present = dimension-line offsets + drawing clamps (`0.85·D` bar limit, leader offsets, `0.85·h` pile embed) — **not** engineering calculation. | **ER-05** — one white PNG shared by dark UI + white PDF (reads as a white block in the dark UI; correct for print). R10. | **READY** (no engineering result created) |
| **Report** (`reports/pdf_generator.py`) | `build_report` renders `params` / `checks` / `status` / `figures` faithfully; `_status_state` normalises `bool` / `str` → `PASS` / `FAIL` / `REVIEW` / `MODEL` | **N/A** (presentation) — EV-09 source audit: `_status_state` contains **no** `0.85` / `sqrt` / `rho` / `*fc`; `build_report` calls `_checks_table(pdf, checks)` + `_status_state(status, checks_ok)` with **no** recompute; `_status_state(True/False/"MODEL")` → `PASS/FAIL/MODEL` verified | — | Faithful: `status` PASS→PASS, FAIL→FAIL, MODEL→MODEL; per-row `ok` from the module | Embeds `draw_*` PNGs unchanged | Pure presentation. | **ER-01** — `_governing_as(r) = max(As_req, As_min)` (a **display selection** of which As governs the "required steel" line, from engine values — changes no verdict/capacity) + SI→MKS display helpers (fixed factors). **ER-06** — generation date absent on the direct `generate_*` paths. R10. | **READY** (renders engine truth; ER-01 = display-only selection) |
| **BOQ** (`utils/boq.py`) | `estimate_building_boq` — concrete volume, formwork area, rebar mass (ratio-based) for one storey; `_beam_length_m` | **INDEPENDENT** (EV-08 — reproduces an independent take-off to rel < 1e-9) | Table + caption "ค่าประมาณเบื้องต้นสำหรับงบประมาณ" (preliminary budget estimate only) | Optional BOQ table in the Building PDF | — | **Quantity** output only. **Not** a structural capacity, **not** a load source — nothing structural is computed from BOQ numbers. | **VF-08** — rebar ratios 150 / 120 / 90 kg/m³ (column/beam/slab) have no cited source (typical Thai budget values). R8/R9. | **READY** (quantity estimate; boundary explicit) |

---

## 2. What is NOT implemented (system-wide) — never shown as PASS

| Area | State | Where disclosed |
|---|---|---|
| Deflection / serviceability / crack control (beam, slab, stair) | **NOT IMPLEMENTED** | `ENGINEERING_VALIDATION.md` §10; per-module scope rows above |
| Development length / bar cut-off / splice design | **NOT IMPLEMENTED** | §10 |
| Torsion (beam), deep-beam action | **NOT IMPLEMENTED** | §10 |
| Punching / one-way shear (slab) | **NOT IMPLEMENTED** | EV-04 brief; scope row |
| Column slenderness / P-Δ / second-order | **NOT IMPLEMENTED** | §10; VF-COL scope |
| Biaxial column bending (Bresler / load-contour) | **NOT IMPLEMENTED** (docstring stale — VF-COL-05) | EV-06; §9.8 |
| Stair support/negative moment, flight shear, landing two-way action | **NOT IMPLEMENTED** | EV-07; scope row |
| Multi-storey gravity accumulation, foundation reaction pathway, beam line-load takedown | **NOT IMPLEMENTED** | EV-08; §9.10; scope row |
| Lateral load / wind / seismic / frame analysis, load combinations ≠ 1.2D+1.6L, live-load reduction, pattern loading | **NOT IMPLEMENTED** anywhere | §10; EV-08 §9.10 |
| Combined / mat / strap / raft footings; settlement; lateral pile | **NOT IMPLEMENTED** | EV-05; scope row |
| Two-way slab moment coefficients — ACI provenance | **UNVERIFIED** (method disclosed as non-ACI Grashof/Marcus) — number unchanged, status REVIEW | EV-04 §9.6; VF-SLAB-01 |

---

## 3. Verdict-chain integrity (the EV-09 core finding)

For every member module the chain is:

```
user input ──▶ engine helper(s) ──▶ checks list [(name, demand, capacity, ok), …]
                                     + passed  (AND of all ok, incl. the EV-fix gates)
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
        ui.engineering_table(checks)                 render_report_expander(
        ui.status_badge(pass/fail)                       checks=checks, status=passed)
        st.error(FAIL_TXT + reasons)  on fail                    │
                                                                ▼
                                                    build_report → _status_state(status)
                                                    _checks_table(checks)   (no recompute)
```

- **No independent recomputation** of `φMn` / `φVn` / `As` / `φPn` / the P–M curve
  in the UI, the report, or the drawing layer. Single source of truth = the module
  engine. (EV-09 phases C, D, E; source-level assertions in
  `tests/validation/run_ev09_system.py`.)
- **No FALSE PASS reachable:** the VF-11 tension-controlled class is fixed in
  beam / slab / stair, latent-unreachable in footing, absent in column, N/A in
  building. Every `passed` boolean includes its ductility / resolvability gate.
- **`MODEL` never becomes `PASS`:** `_status_state("MODEL") → "MODEL"`; the
  Building Model has no `passed` boolean and no design badge.
- **SYS-01 — CLOSED / RESOLVED in UI-01** (discovered EV-09). Pre-fix, a failing
  member design showed the amber **"REVIEW"** summary badge instead of a red
  **"FAIL"** — system-wide, consistent, **not** a false PASS. UI-01 changed the
  presentation mapping only: the 7 member summary badges + `main._module_status_
  rows` now render `fail`/**"FAIL"** on `passed is False`; DESIGN CHECKS rows show
  **"ไม่ผ่าน (FAIL)"**; `utils/ui.py:_BADGE` gained a first-class `review` state
  so REVIEW stays reachable for genuine limitation cases. No `passed`
  composition, engineering `checks`, `_status_state`, `build_report`, drawing,
  ACI calculation or calculation test changed. Verified: `pytest` 80 passed;
  `run_ev09_system.py` 56 checks / PASS 46 / FAIL 0 / REVIEW 10 / RELEASE READY.
  See `docs/ENGINEERING_REVIEW.md` → SYS-01 and the semantics contract
  (`EV09_COMPLETION_REPORT.md` §13).

---

*Generated by EV-09. No production calculation code was changed in EV-09. See
`docs/EV09_COMPLETION_REPORT.md` and `docs/ENGINEERING_RELEASE_MATRIX.md`.*
