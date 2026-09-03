# EV-09 — System-Wide Engineering Consolidation & Release Gate — Completion Report

**Project:** RC CodePro · **Code:** ACI 318M-08 · **Date:** 2026-09-03
**Phase type:** consolidation + release gate — **not** a feature, refactor or UI
redesign phase.
**Result:** **ENGINEERING RELEASE READY** · **0 production calculation changes in
EV-09.**

---

> ### ▸ POST-EV-09 UPDATE — UI-01 (SYS-01 CLOSED)
>
> EV-09 shipped `ENGINEERING RELEASE READY` with **SYS-01** carried as the first
> UI finding: a failed member design rendered the amber **"REVIEW"** summary
> badge instead of a red **"FAIL"** (Class B, R10 — a presentation-layer
> verdict-state mapping issue; never a false PASS).
>
> **UI-01 has since RESOLVED SYS-01** as a presentation-only change:
> - the 7 member DESIGN-SUMMARY badges (`beam`, `slab`, `footing` ×2, `column`,
>   `stair` ×2) now render `ui.status_badge("pass" if passed else "fail",
>   "PASS" if passed else "FAIL")`;
> - `main.py:_module_status_rows` maps a failed module to `fail` / `FAIL`; the
>   Home KPI is renamed **"Needs attention"** and still counts from the module
>   `passed` result;
> - DESIGN CHECKS table rows for a failed *implemented* check now read
>   **"ไม่ผ่าน (FAIL)"**;
> - `utils/ui.py:_BADGE` gained a first-class **`review`** state so REVIEW
>   remains a real, reachable verdict for genuine limitation / unresolved
>   conditions.
>
> **Unchanged:** `passed` composition, engineering `checks` construction, every
> ACI 318M-08 / flexure / shear / P–M / analysis calculation,
> `utils/aci_318m.py`, `utils/analysis.py`, `utils/drawing.py`,
> `reports/pdf_generator.py` (`_status_state` / `build_report` already rendered
> FAIL faithfully), the Building MODEL boundary + disclaimer, and all
> calculation test expectations.
>
> **Verification after UI-01:** `py -3 -m pytest` → **80 passed, 0 failed, 0
> skipped**; `py -3 tests/validation/run_ev09_system.py` → **56 checks, PASS =
> 46, FAIL = 0, REVIEW = 10, ENGINEERING RELEASE READY**. The EV-09 Phase-B
> semantics check was strengthened to assert the corrected `fail`/`FAIL`
> mapping and that a first-class `review` state still exists.
>
> The sections below are the **original EV-09 record** and are preserved as
> written (SYS-01 appears there as an open finding — that was true at EV-09).
> See `docs/ENGINEERING_REVIEW.md` → SYS-01 for the consolidated closure entry.

---

## 1. Objective

EV-02 … EV-08 already answered *"is each formula correct?"* — every importable /
derivable calculation function is matched by an independent first-principles
reference. EV-09 asks the **system** question:

> *A validated Calculation Engine result — does it still carry the same VALUE,
> UNIT, STATUS and engineering meaning after it travels
> `ENGINE → RESULT → UI → SUMMARY → DRAWING → REPORT`, and can it ever produce a
> FALSE PASS along the way?*

Deliverables: `docs/SYSTEM_CAPABILITY_MATRIX.md`,
`docs/ENGINEERING_RELEASE_MATRIX.md`, this report,
`tests/validation/run_ev09_system.py`, and an updated
`docs/ENGINEERING_VALIDATION.md` §9.11 / §8.

---

## 2. Baseline

| Item | Value |
|---|---|
| `pytest` (repo root, `pytest.ini` → `addopts = -q`, `testpaths = tests`) | **80 passed, 0 failed, 0 skipped** (1.4–1.7 s) |
| EV-02 `run_ev02_validation.py` | 120 checks — 104 PASS · **0 FAIL** · 11 REVIEW · 5 BLOCKED |
| EV-03 `run_ev03_beam.py` | 127 — 107 PASS · **0 FAIL** · 20 REVIEW |
| EV-04 `run_ev04_slab.py` | 77 — 58 PASS · **0 FAIL** · 19 REVIEW |
| EV-05 `run_ev05_footing.py` | 67 — 42 PASS · **0 FAIL** · 25 REVIEW |
| EV-06 `run_ev06_column.py` | 87 — 60 PASS · **0 FAIL** · 27 REVIEW |
| EV-07 `run_ev07_stair.py` | 70 — 40 PASS · **0 FAIL** · 30 REVIEW |
| EV-08 `run_ev08_building.py` | 79 — 60 PASS · **0 FAIL** · 19 REVIEW |
| **EV-09 `run_ev09_system.py` (new)** | **49 — 38 PASS · 0 FAIL · 11 REVIEW** → **ENGINEERING RELEASE READY** |

EV-09 did not reduce the regression baseline. Total automated regression
remains **80** (EV-09's runner is a standalone script, not a pytest module —
consistent with EV-02…EV-08).

---

## 3. Validation History

| Phase | Scope | Independent refs | Production fixes | Key outcome |
|---|---|---|---|---|
| EV-01 | Validation framework | 0 | 0 | framework only |
| EV-02 | ACI primitives, flexure, shear, continuous-beam analysis, axial anchors | 6 modules | 0 | independent references established; VF-01…VF-15 recorded |
| EV-03 | Beam | +1 (`reference_beam_ev03`) | **1** — `beam.py` (VF-11: tension-controlled `As,max` gate) | beam verdict now enforces ACI 10.3.4/10.3.5 |
| EV-04 | Slab | +1 | **+1** — `slab.py` (VF-11 class) | two-way method flagged non-ACI (VF-SLAB-01, REVIEW) |
| EV-05 | Footing | +1 | **+1** — `footing.py` (VF-FOOT-02: eccentricity-resolvable gate) | **VF-09 RESOLVED — not a defect** (`3.464 = 2√3`) |
| EV-06 | Column | +1 (independent strain-compat P–M solver) | **0** | production P–M curve matches rel < 2e-13; `EV-COL-003/004/005` UNBLOCKED; no VF-11 defect |
| EV-07 | Stair | +1 | **+1** — `stair.py` both renders (VF-STAIR-01, VF-11 class) | validated the actual idealisation (inclined one-way slab, not a beam) |
| EV-08 | Building Model | +1 | **0** | **load conservation** proven for the regular grid; system boundary documented; VF-01 RESOLVED |
| **EV-09** | **System consolidation** | **+1 meta-runner** | **0** | verdict chain intact end-to-end; **ENGINEERING RELEASE READY** |

Cumulative production calculation fixes: **4** (`beam.py`, `slab.py`,
`footing.py`, `stair.py`) — all of the **VF-11 tension-controlled class** except
`footing.py`, whose fix (VF-FOOT-02) is a different mechanism gate.

---

## 4. System Capability Matrix

Full matrix in **`docs/SYSTEM_CAPABILITY_MATRIX.md`** (Module × Calculation
Capability / Validation Status / UI Status / Report Status / Drawing Status /
Scope / Known Review / Release Status), covering Beam, Slab, Footing, Column,
Stair, Building, Continuous Beam Analysis, Drawing, Report, BOQ.

Headline: every member module is `INDEPENDENT`-validated for its implemented
scope; the assembled `_render_*` numbers remain `BLOCKED` (interleaved
compute/render — must not be split in a validation phase); the presentation
layers (Drawing, Report) are audited to contain **no** engineering
recomputation.

---

## 5. Engineering Scope Matrix

**VALIDATED** (independent reference agrees within tolerance) vs
**NOT IMPLEMENTED** (capability absent — never displayed as PASS):

### BEAM
- ✅ Flexure (SI + MKS chain) · ✅ Shear (`0.53√f'c` MKS `Vc`) · ✅ `As,min` ·
  ✅ **`As,max` / tension-controlled** (EV-03 fix) · ✅ φ = 0.90 flexure **with
  ductility gate** · ✅ Bar fit / spacing · ✅ 3-section −M/+M/−M
- ❌ Torsion · ❌ Deflection / crack control · ❌ Development length / cut-off ·
  ❌ Deep-beam · ❌ Lateral

### SLAB
- ✅ One-way flexure · ✅ **Implemented** two-way moment model (Grashof/Marcus
  family — *method disclosed, not ACI-verified* → REVIEW) · ✅ Temperature /
  shrinkage steel · ✅ Bar spacing · ✅ **Ductility** (EV-04 fix)
- ❌ Punching shear · ❌ One-way shear · ❌ Deflection · ❌ Crack control ·
  ❌ Development length · ❌ Torsion

### FOOTING
- ✅ Isolated: bearing, one-way (beam) shear, two-way (punching) shear, flexure ·
  ✅ Pile cap: pile reaction distribution (axial + biaxial `M/Σx²`), per-pile
  punching, group flexure · ✅ **Eccentricity-resolvable gate** (EV-05 fix) ·
  ✅ Punching perimeter for square / rect / **hexagon (`2√3·Dp + πd`)** /
  **circular (`π(Dp+d)`)** pile heads — **VF-09 confirmed correct**
- ❌ Combined / mat / strap / raft footings · ❌ Settlement · ❌ Soil-structure
  interaction · ❌ Lateral pile · ❌ Pile-group settlement

### COLUMN
- ✅ Axial `Po` · ✅ `φPn,max` cap · ✅ **Full P–M interaction curve**
  (strain-compatibility, 44-pt sweep + `Po`/`Pt` anchors) — **rel < 2e-13** vs
  independent solver · ✅ **Variable φ 0.65→0.90** (ACI 9.3.2) · ✅ ρ = Ast/Ag
  limits · ✅ Tie spacing where implemented
- ❌ Slenderness / P-Δ / second-order · ❌ Biaxial (Bresler / load-contour) —
  *docstring stale, VF-COL-05* · ❌ Confinement design · ❌ Splice design

### STAIR
- ✅ Straight flight · ✅ U-shape · ✅ **Inclined one-way slab** idealisation ·
  ✅ Sloped-waist (`t/cosθ`) + triangular-step (`R/2`) dead load · ✅ **Positive
  mid-span** flexure `wL²/8` · ✅ Minimum / temperature steel · ✅ Spacing ·
  ✅ **Ductility** (EV-07 fix)
- ❌ Support / negative-moment design · ❌ Flight shear · ❌ Landing two-way
  action · ❌ Deflection · ❌ Stringer / folded-plate models

### BUILDING
- ✅ Grid / geometry model · ✅ Member enumeration · ✅ Factored slab load `Wu`
  (`1.2(t·2400 + SDL) + 1.6LL`) · ✅ **Single-storey tributary vertical load
  takedown** (load-conserving for the regular grid) · ✅ Rule-based preliminary
  column grouping · ✅ Budget BOQ
- ❌ Multi-storey gravity accumulation · ❌ Full building structural analysis ·
  ❌ Beam line-load takedown (area → `w`) · ❌ Foundation reaction pathway ·
  ❌ Lateral / wind / seismic / frame analysis · ❌ Load combinations ≠
  1.2D+1.6L · ❌ Live-load reduction · ❌ Pattern loading · ❌ Member self-weight
  beyond the slab

---

## 6. Release-blocking Review

All `VF-*` / `ER-*` / `R1–R10` findings, classified by **engineering impact**
(not by name):

| Class | Definition | Count | Members |
|---|---|---|---|
| **A — RELEASE BLOCKER** | reachable non-conservative defect, false PASS, unit error, load loss into a sized member, verdict inversion, report mutating a result | **0** | — |
| **B — RELEASE REVIEW** | consistent + non-over-claiming, but a UI-phase decision point | 3 | SYS-01, VF-SLAB-01, VF-04/ER-04 |
| **C — DOCUMENTED LIMITATION** | intentional scope / conservative approximation, disclosed | ~14 | VF-05, VF-FOOT-01, VF-FOOT-03, VF-07, VF-12, VF-13, VF-08, VF-10, VF-SLAB-02, VF-SLAB-03, VF-STAIR-02, VF-STAIR-03, RB-1…RB-7 |
| **D — UI ONLY** | wording / presentation, zero engineering-value impact | 8 | ER-01, ER-02, ER-03, ER-05, ER-06, VF-COL-01, VF-COL-03, VF-COL-05 |
| **E — FUTURE FEATURE** | not implemented; never shown as PASS | — | deflection, dev length, torsion, slab shear, slenderness, biaxial, stair support/shear, multi-storey, foundation pathway, beam line-load, lateral/wind/seismic, combined footings |

**No Category-A finding exists. No reachable non-conservative issue remains.**
EV-09 therefore does **not** STOP; it proceeds to the release decision.

---

## 7. False-PASS System Audit (P0 of EV-09)

For each member module the safety chain
`INPUT → CALCULATION → CHECK BOOLEAN → FINAL VERDICT → DISPLAY → REPORT` was
traced. The audit looked for: `calculation = FAIL` but `check ignored` and
`verdict = PASS`; "warning only" with `overall PASS`; `UI status = PASS` while
`engine status = FAIL`.

| Module | `passed` boolean composition | FALSE PASS reachable? |
|---|---|---|
| **Beam** | `top_req_ok and bot_req_ok and top_min_ok and bot_min_ok and **top_ductile_ok and bot_ductile_ok** and sh["ok"]` (EV-03) | **No** — every implemented limit, incl. ACI 10.3.4/10.3.5, is ANDed in. Over-reinforced section → `passed=False` → "REVIEW" badge + `st.error`. |
| **Slab** | `main_ok and temp_ok and **ductile_ok**` (`ductile_x and ((not two_way) or ductile_y)`) (EV-04) | **No** |
| **Footing** | isolated: bearing + one-way + punching + flexure all ANDed; pile cap: `… and **ecc_resolvable_ok**` (EV-05) | **No** — VF-11 class is *latent* here but **not reachable** (shadowed by punching + one-way + bearing + flexure-infeasibility, all enforced). |
| **Column** | `ratio_ok and axial_ok and spacing_ok and **pm_ok**` (`pm_ok` = point-in-polygon of `(Mu,Pu)` inside the φ-reduced P–M curve) | **No** — variable φ is applied inside the validated curve; `φMn_at_Pu` (VF-COL-01) is **display-only**, deliberately **not** in `passed`. |
| **Stair** | straight: `main_ok and temp_ok and **ductile_ok**`; U-shape: `main_req_ok and main_min_ok and temp_min_ok and sp_main_ok and sp_temp_ok and **ductile_ok**` (EV-07) | **No** — STEP-14's FAIL→REVIEW display change verified in EV-07 to mask **no** engineering result (the reasons list + per-row detail still render). |
| **Building** | **none** — no `passed` boolean, no design badge; on-screen "MODEL GENERATED", PDF `status="MODEL"` | **N/A** — nothing is claimed PASS. `_status_state("MODEL") → "MODEL"`; the PDF path has no branch that turns MODEL into PASS. |

**Cross-layer:** `tests/validation/run_ev09_system.py` phases B/C/F assert at the
**source level** that (a) each member module uses
`ui.status_badge("pass" if passed else "warn", "PASS" if passed else "REVIEW")`
(never a silent PASS on failure), (b) each still renders the detailed
`FAIL_TXT` + reasons on failure, (c) `build_report` / `_status_state` perform no
recompute, (d) Building carries no `passed` boolean and `status="MODEL"`.

**One open item — SYS-01 (Class B, R10):** a failed member design shows the
amber **"REVIEW"** summary badge, not a red **"FAIL"**. This is **system-wide and
consistent** (all 6 modules + the Home dashboard). It is **not** a false PASS:
"REVIEW" ≠ "PASS", and the authoritative
`st.error("❌ ไม่ผ่าน (FAIL) — <specific reasons>")` plus the per-row
"ตรวจสอบ (REVIEW)" table always fire when `passed is False`. The summary badge
**under-states** severity; it never over-states. Deferred to UI Integration.

---

## 8. Single Source of Truth

| Value | Computed in | Recomputed anywhere? |
|---|---|---|
| `φMn`, `As,req`, `As,min`, `As,max`, `φVn`, `Vc`, `Vs` | the module engine (`_section_calc`, `_flex_ksc`, `vc_beam`, …) | **No.** UI reads them into the `checks` list; the report receives the **same** `checks` + `status` via `render_report_expander(checks=checks, status=passed)` (verified in `beam.py:820/822`, `column.py:697/702`, `slab.py:439/441`, `footing.py:619/621` + `1327/1355`, `stair.py:748/750`). `render_report_expander` (`utils/project.py:138`) is a pure pass-through to `build_report`. |
| P–M interaction curve `(φMn_c, φPn_c)` | `modules/column.py:_calculate_pm_curve` | **No.** The UI's `pm_ok` uses the returned arrays; `utils/drawing.py` plots `np.asarray(Mn)` of the **passed-in** arrays (type-coercion for matplotlib, not recomputation). |
| Report verdict state | `_status_state(status, checks_ok)` — normalises `bool` / `"MODEL"` / str → `PASS`/`FAIL`/`REVIEW`/`MODEL` | **No engineering value.** Source audit: no `0.85`, `sqrt`, `rho`, `* fc`. |
| "Required steel" line in the PDF | `reports/pdf_generator.py:_governing_as(r) = max(r["As_req"], r["As_min"])` | **Selection**, not recomputation — picks which **engine** value to print. Recorded as **ER-01 (Class D)**: a `max()` + SI→MKS display helpers living in the report layer blur the boundary but change no verdict and no capacity. UI-phase action: move into the modules / a shared helper, keeping the numeric factors. |
| Continuous-beam demand `Mu`, `Vu`, reactions | `utils/analysis.py:solve_continuous_beam` | **No.** Flows into the Beam tab's demand side + the SFD/BMD plot. |

**Preferred pipeline confirmed:** `ENGINE → return data (checks list + status) →
UI / REPORT / DRAWING`. No system-wide refactor performed.

---

## 9. Result Traceability

Representative "where does this number come from?" traces:

| Quantity | Origin function | → intermediate | → final | → UI | → Report |
|---|---|---|---|---|---|
| **Mu** (beam) | `solve_continuous_beam` (or direct input) | sampled `M(x)` array | `Mu_pos_kgfm = max(M.max(), 0)` | demand cell in `checks` + SFD/BMD annotation | same `checks` row |
| **Vu** (beam) | `solve_continuous_beam` / input | `V(x)` array | `Vu` at critical section | `checks` demand | same |
| **As** (beam) | `_section_calc → _flex_ksc` | `a`, `c`, `εt`, `As_req`, `As_min`, **`As_max = ρ_max·b·d`** | `As_prov` from bar selection; `bot_ductile_ok = As_prov ≤ As_max` | "As required / provided / max" rows + ductility row | same rows; `_governing_as = max(As_req, As_min)` for the summary line (ER-01) |
| **φMn** (beam) | `_section_calc` | `Mn` from `a`, `As_prov` | `φMn = 0.90·Mn` | capacity cell | same |
| **φVn** (beam) | `vc_beam` (`0.53√f'c` MKS) + `Vs` | `Vc`, `Vs` | `φVn = 0.75(Vc+Vs)` | capacity cell | same |
| **Pu / Mu_column** | user input (`Mu` help text stale — VF-COL-03) | — | passed to `pm_ok` | P–M point marker | demand rows |
| **φPn / φMn_column** | `_calculate_pm_curve` | strain sweep, per-layer `fs`, `Cc`, `Pn`, `Mn`, `εt`, **variable φ** | `(φMn_c, φPn_c)` arrays; `pm_ok = point_in_poly(Mu, Pu, …)` | curve + point-in-polygon verdict | curve figure + `checks` |
| **φMn_at_Pu** (column) | `_calculate_pm_curve` interpolation at `Pu` | — | **display only** — *not* in `passed` (VF-COL-01) | info line | info line |
| **Vu_footing / punching** | `_render_isolated_footing` / `_render_pile_cap` (interleaved → BLOCKED as an assembled number; **components** independently validated in EV-05) | `bo`, `d`, `vc` (`0.53 / 1.06 / …√f'c` MKS), `Vu_punch` | `φVc` vs `Vu`; perimeter per pile-head shape (VF-09 correct) | punching rows + "resists eccentricity" chip | same `checks` |
| **Wu** (building) | `render_building_model` inline | `1.2(t/100·2400 + SDL) + 1.6·LL` (VF-01 RESOLVED) | factored area load | shown in the model panel | `params` in the MODEL PDF |
| **Pu_column_building** | `_calculate_column_loads` | tributary `panel_area/4` per corner node; voids carry nothing; quarters on a removed column **dropped** (VF-05) | per-node `Pu = Wu·trib_area` | column-load map + takedown table | MODEL PDF (no verdict) |

Every safety-critical number resolves to a named engine function; the only
layer-boundary arithmetic is ER-01 (`max()` + display units) and drawing offsets.

---

## 10. UI Engineering Consistency

Pages checked: Home, Beam, Column, Slab, Footing, Stair, Building Model,
Drawing (embedded), Report (expander).

- **Input labels / units** — MKS throughout the member pages (cm, kgf, ksc,
  kgf·m, kgf/m²); SI only inside `utils/aci_318m.py`. No unlabelled critical
  result found (phase 10 of the spec, EV-09 unit audit §12).
- **Result labels** — demand/capacity rows carry units; the P–M "Safe zone
  (inside design curve)" label is engineering-correct.
- **PASS / FAIL / REVIEW** — member pages: `ui.status_badge("pass"/"warn",
  "PASS"/"REVIEW")` + detail table + `st.error` on failure. Building: **`MODEL
  GENERATED`** (`info`) — *never* "PASS" / "SAFE" / "DESIGN COMPLETE".
- **Capability claims** — the UI does **not** claim any capability beyond the
  engine, **except** the four stale-text items in §11 (all R10, all recorded).
- **Building caption** — "แบบจำลองเส้นกริดถูกสร้างจากค่าที่ป้อน — ยังไม่มีการ
  วิเคราะห์โครงสร้าง (ถ่ายน้ำหนักในแนวดิ่งด้วยวิธี…)" — **honest**: explicitly
  states no structural analysis is performed.

---

## 11. Stale UI Text Audit

`grep` over `not used / not implemented / coming soon / placeholder / AI /
analysis / safe / pass / complete / Bresler`:

| ID | Location | Text | Reality | Class | Action |
|---|---|---|---|---|---|
| **VF-COL-03** | `column.py` `Mu` `number_input(help=…)` | "ยังไม่นำมาคิดในรุ่นนี้" (not used in this version) | `Mu` **is** used — `pm_ok = _point_in_poly(Mu, Pu, φMn_c, φPn_c)` | R10 | UI phase — 1-line, with before/after |
| **VF-COL-05** | `column.py` module docstring | mentions "biaxial … Bresler reciprocal-load method" | only **uniaxial** P–M implemented | R10 | UI phase — docstring correction |
| **ER-02** | `building.py` `render_report_expander(title=…)` | "รายงานวิเคราะห์โครงสร้างอาคาร… (Building Analysis & BOQ Report)" | tributary take-down + BOQ, **not** analysis; verdict is correctly `MODEL` | R10 | UI phase — title reword |
| **ER-03** | `building.py` `_auto_group_columns` docstring + "AI แนะนำเบอร์เสา" caption | "AI pre-analysis" | fixed-threshold clustering (`≥0.75·Pmax→C1`, `≥0.45→C2`, else C3), no learned model | R10 | UI phase — reword to "rule-based / อัตโนมัติ" |

`building.py:294` caption ("ยังไม่มีการวิเคราะห์โครงสร้าง") is **honest, not
stale**. `utils/drawing.py` "Safe zone" is **engineering-correct**. No stale
item carries engineering ambiguity that affects a value, unit or verdict — none
is fixed in EV-09 (cosmetic-only changes are out of scope for a validation
phase).

---

## 12. Unit Audit

| Unit | Where | Status |
|---|---|---|
| `kgf`, `kgf/m`, `kgf/m²`, `kgf·m`, `kgf·cm` | member-page demands / capacities, load inputs | labelled, consistent |
| `cm`, `cm²`, `cm²/m`, `mm`, `m` | geometry, steel areas, spacings, spans | labelled, consistent |
| `ksc` | material strengths (`f'c`, `fy`) on member pages | labelled |
| `MPa` / SI (N, mm) | `utils/aci_318m.py` only (internal) | not surfaced to the UI unlabelled |
| SI→MKS display factors | `reports/pdf_generator.py` `_cm` `_cm2` `_ton` `_ksc` (`/10`, `/100`, `9.80665`, `0.0980665`) | fixed constants, **ER-01** (Class D) — display only, no engine unit changed |

No engine unit is converted where it need not be. Labels match the values shown.
No R2 (unit-error) finding exists across EV-02…EV-09.

---

## 13. Verdict Semantics (contract)

| Token | Meaning | Shown when |
|---|---|---|
| **PASS** | every **implemented** engineering check is satisfied for the design as entered | member module, `passed is True` → green badge |
| **FAIL** | an **implemented** engineering check is **not** satisfied | authoritative detail: `st.error("❌ ไม่ผ่าน (FAIL) — <reasons>")` + per-row table, whenever `passed is False` |
| **REVIEW** | a PASS cannot be claimed — either an implemented check failed (see the FAIL detail) **or** a known limitation prevents the claim | member module summary badge when `passed is False`; per-row "ตรวจสอบ (REVIEW)"; Home dashboard for the Beam row |
| **MODEL** | a model was generated but **no structural design/analysis** was performed | Building Model — on-screen `MODEL GENERATED`, PDF `status="MODEL"` |
| **NOT IMPLEMENTED** | the capability does not exist in this version | scope tables (`SYSTEM_CAPABILITY_MATRIX.md` §2, this report §5) — never rendered as PASS |
| **BLOCKED** | validation cannot yet establish correctness of an **assembled** number (interleaved compute/render) | EV runners + `ENGINEERING_VALIDATION.md` §10 |

**Rule:** `PASS` is never substituted for `MODEL`, `REVIEW`, or
`NOT IMPLEMENTED`. **SYS-01 (open, Class B):** the member summary badge currently
renders `REVIEW` for a `passed is False` design instead of a distinct `FAIL`.
Per the contract this is *admissible* (REVIEW ⊇ "an implemented check failed")
and is **not** a false PASS, but it under-states severity at the summary level.
UI-Integration decision: give `passed is False` its own red `FAIL` badge,
reserving `REVIEW` for limitation-only cases.

---

## 14. Report Consistency

`reports/pdf_generator.py`:

- `build_report(*, title, project_name, engineer, location, params, checks,
  figures, status, summary, boq_dataframe)` — renders `params` and `checks`
  rows verbatim, `state = _status_state(status, checks_ok)`,
  `_result_block(pdf, state == "PASS", state, summary)`.
- `_status_state(True) → "PASS"`, `_status_state(False) → "FAIL"`,
  `_status_state("MODEL") → "MODEL"` — **verified in `run_ev09_system.py`
  phase C**. No `0.85` / `sqrt` / `rho` / `* fc` in `_status_state`.
- The module passes its **own** `checks` list + `status=passed` — the report
  cannot disagree with the screen (§8).
- **Building:** `status="MODEL"` → PDF shows `MODEL GENERATED`. **No PDF branch
  converts `MODEL` → `PASS`.**
- Per-member bespoke `generate_*_report(inputs, results)` functions render
  `results` values as-is; **ER-06** (Class D) — generation date absent on those
  sheets' footers.

---

## 15. Drawing Consistency

`utils/drawing.py` — EV-09 source audit (`run_ev09_system.py` phase D):

- **No** call to `_calculate_pm_curve`, `solve_continuous_beam`, `_as_flexure_ksc`,
  `_required_as_flexure`, `_flex_ksc`, `vc_beam`, `_flexure_as`, `rho_max`.
- All arithmetic is **drawing geometry**: dimension-line offsets, leader
  positions, and drawing clamps (`0.85·D` bar-position limit, `1.6·t` leader
  offset, `0.85·h` pile embed cap). `Mn = np.asarray(Mn)` coerces the
  **passed-in** curve for matplotlib — not a recomputation.
- No drawing label implies an unimplemented check. "Safe zone (inside design
  curve)" is engineering-correct for the plotted φ-reduced P–M curve.
- **ER-05** (Class D) — the same white PNG is shown in the dark UI and embedded
  in the white PDF; a screen-only dark variant is a UI-phase item, geometry
  untouched.

Drawings create **no** engineering result.

---

## 16. BOQ Boundary

`utils/boq.py`:

- `estimate_building_boq` outputs **quantities** — concrete volume (m³),
  formwork area (m²), rebar mass (kg, ratio-based: column 150 / beam 120 /
  slab 90 kg/m³) — and `_beam_length_m` (m), for **one storey**.
- Independently validated in EV-08 (reproduces a hand take-off to rel < 1e-9).
- **Not** a structural capacity; **not** a load source — the source code
  computes nothing structural from BOQ numbers, and the caption reads
  "ค่าประมาณเบื้องต้นสำหรับงบประมาณ" (preliminary budget estimate).
- **VF-08** (Class C) — the rebar ratios have no cited source (typical Thai
  budget-stage values). Documented; no fix.

---

## 17. Building Boundary

Final statement of scope (UI / PDF / docs must not exceed this):

**Building Model IS:** (A) a grid / geometry model builder · (B) a
**single-storey** tributary **vertical** load-takedown · (C) preliminary
rule-based column grouping · (D) a budget BOQ estimate.

**Building Model IS NOT:** multi-storey gravity accumulation · full building
structural analysis · beam line-load analysis · a foundation reaction pathway ·
lateral / wind / seismic analysis · a design check with a pass/fail verdict.

**Enforcement:** no `passed` boolean; on-screen `MODEL GENERATED` + the honest
"ยังไม่มีการวิเคราะห์โครงสร้าง" caption; PDF `status="MODEL"`; no coupling to
`utils.analysis`. **Open (Class D):** the PDF **title** still says
"วิเคราะห์โครงสร้าง / Analysis" (ER-02) — the verdict is correct, the title
over-claims; reword in the UI phase.

---

## 18. Member Boundaries

| Module | Released scope | Not implemented (never PASS) |
|---|---|---|
| **Beam** | flexure (+/−M), one-way shear, `As,min`/`As,max`, φ + ductility, bar fit/spacing, 3-section | torsion, deflection, crack, dev length, deep beam, lateral |
| **Slab** | one-way flexure, temp steel, spacing, ductility; two-way moment method **disclosed non-ACI → REVIEW** | punching, one-way shear, deflection, crack, dev length, torsion |
| **Footing** | isolated (bearing/one-way/punching/flexure) + pile cap (distribution/punching/flexure/eccentricity gate) | combined/mat/strap/raft, settlement, SSI, lateral pile |
| **Column** | **short**, **uniaxial** P–M, **unamplified** moments, variable φ, ρ limits, tie spacing where implemented | slenderness/P-Δ, biaxial (Bresler), confinement, splices |
| **Stair** | straight + U-shape, inclined one-way slab, **positive mid-span** flexure, min/temp steel, spacing, ductility; **simply-supported** load model | support/negative moment, flight shear, landing two-way action, deflection |
| **Continuous Beam Analysis** | prismatic, linear-elastic, three-moment, vertical point+UDL | settlement/spring supports, non-prismatic, second-order, redistribution; **sampled +M peak (VF-04)** |

UI, report and documentation wording were checked for consistency with these
boundaries (§10, §11, §17).

---

## 19. Golden Cases

One representative case per module, reusing the **already-validated** EV-02…EV-08
references (no new expected numbers invented):

| Case | Source reference | Asserts |
|---|---|---|
| **BEAM-GOLD** | `reference_beam_ev03` + `run_ev03_beam.py` (127 checks) | flexure/shear/`As,max` engine == independent ref within tolerance |
| **SLAB-GOLD** | `reference_slab_ev04` + `run_ev04_slab.py` (77) | one-way flexure + ductility gate == ref |
| **FOOTING-GOLD** | `reference_footing_ev05` + `run_ev05_footing.py` (67) | bearing/one-way/punching/flexure + hex & circular perimeter == ref |
| **COLUMN-GOLD** | `reference_column_ev06` + `run_ev06_column.py` (87) | full P–M curve == independent strain-compat solver, rel < 2e-13 |
| **STAIR-GOLD** | `reference_stair_ev07` + `run_ev07_stair.py` (70) | inclined-slab DL + mid-span flexure + ductility == ref |
| **BUILDING-GOLD** | `reference_building_ev08` + `run_ev08_building.py` (79) | `Σ Pu = Wu·floor_area` (load conservation) + BOQ take-off == ref |

`run_ev09_system.py` phase A re-executes all six runners and asserts each reports
`FAIL=0`; the engine→UI→report value identity is covered by phases C/E (the
report receives the module's own `checks`+`status`, unchanged).

---

## 20. System Trace

`tests/validation/run_ev09_system.py` (new, standalone script — **not** a pytest
module, consistent with EV-02…EV-08):

| Phase | Checks |
|---|---|
| **A** Regression + prior-EV re-run | `pytest` ≥ 80 passed / 0 failed / 0 error; each EV-02…EV-08 runner `FAIL=0` |
| **B** Verdict-badge semantics | source-level: every member module uses `"pass" if passed else "warn"` / `"PASS" if passed else "REVIEW"`; each renders `FAIL_TXT` + reasons on failure; Building = `"MODEL GENERATED"` (info), no design PASS; **SYS-01** documented |
| **C** Report = presentation only | `_status_state` has no engineering maths; `build_report` calls `_checks_table` + `_status_state` with no recompute; `_status_state(True/False/"MODEL") → PASS/FAIL/MODEL`; **ER-01** noted |
| **D** Drawing = presentation only | `utils/drawing.py` calls no calc helper; **ER-05** noted |
| **E** Single source of truth | beam/slab/stair document the "one source, rendered here and passed unchanged to the PDF" contract |
| **F** Building boundary | no `passed` boolean; `MODEL GENERATED` + `status="MODEL"`; no `solve_continuous_beam` coupling; honest caption |
| **G** Stale UI text register | VF-COL-03, VF-COL-05, ER-02, ER-03 — all present, all R10, all deferred |
| **H** Release-blocking review | the 4 EV-03…EV-07 fixes are still wired into their `passed` booleans (revert guard); 0 Category-A; **ENGINEERING RELEASE READY** |

**Result: 49 checks — 38 PASS, 0 FAIL, 11 REVIEW → ENGINEERING RELEASE READY.**
No visual/screenshot comparison is used as evidence of calculation correctness.

---

## 21. Regression

| Suite | Before EV-09 | After EV-09 |
|---|---|---|
| `pytest` | 80 passed, 0 skipped | **80 passed, 0 skipped** (unchanged — EV-09 added no pytest test and no production code) |
| EV-02 | 0 FAIL | 0 FAIL |
| EV-03 | 0 FAIL | 0 FAIL |
| EV-04 | 0 FAIL | 0 FAIL |
| EV-05 | 0 FAIL | 0 FAIL |
| EV-06 | 0 FAIL | 0 FAIL |
| EV-07 | 0 FAIL | 0 FAIL |
| EV-08 | 0 FAIL | 0 FAIL |
| **EV-09** | — | **0 FAIL** (49 checks) |

Invariant held: EV-09 did not reduce the regression baseline.

---

## 22. Engineering Review Register (consolidated)

`Conservative?` = does the finding err on the **safe** side? · `Status` ∈
CLOSED / ACCEPTED / DOCUMENTED / FUTURE / RELEASE BLOCKER.

| ID | Module | Finding | Type | Severity | Conservative? | Status | Release Action |
|---|---|---|---|---|---|---|---|
| **VF-11** | Beam | tension-controlled `As,max` limit absent from the verdict; sized at fixed φ=0.90 | R3 (boundary omitted) | High (pre-fix: non-conservative false PASS) | pre-fix **No** | **CLOSED** (EV-03: `As,max` gate + regression test) | none — fixed |
| **VF-11-SLAB** | Slab | same class in `_render_slab_design` | R3 | High | pre-fix **No** | **CLOSED** (EV-04) | none — fixed |
| **VF-STAIR-01** | Stair | same class in both stair renders | R3 | High | pre-fix **No** | **CLOSED** (EV-07) | none — fixed |
| **VF-FOOT-02** | Footing | pile cap with n ≤ 2 and eccentricity about the un-resisted axis reported PASS | R3 | Medium | pre-fix **No** | **CLOSED** (EV-05: `ecc_resolvable_ok` gate) | none — fixed |
| **VF-FOOT-01** | Footing | VF-11 class present in the footing flexure helper | R3 (latent) | Low | **Yes** (shadowed by punching + one-way + bearing + flexure-infeasibility) | **DOCUMENTED** (EV-05 — not reachable) | monitor if the shadowing checks are ever relaxed |
| **VF-09** | Footing | circular/hex pile-head punching perimeter | R6 (EV-02 mis-read) | — | — | **CLOSED — not a defect** (`3.464 = 2√3` exact hexagon factor; circular uses `π(Dp+d)`) | none |
| **VF-01 / VF-BLDG-01** | Building | `Wu` formula unverified (interleaved) | R7 | — | **Yes** | **CLOSED** (EV-08 — independent reconstruction; assembled number stays BLOCKED) | none |
| **VF-05** | Building | quarter-areas on a removed column are **dropped**, not redistributed | R9 / R8 | Medium | **No** (neighbour `Pu` under-estimated) but **bounded** (`Σarea + dropped = floor_area`) and **nothing is sized** from these `Pu` | **ACCEPTED** — documented in the function docstring + `SYSTEM_CAPABILITY_MATRIX` | do not use for irregular-grid column takedown without engineer review; redistribution = forbidden feature-add |
| **VF-04 / ER-04** | Analysis | governing `+M` is the peak of the **sampled** `M(x)` array | R4 | Low | **No** (≤~0.003 %) — bounded, test-locked | **DOCUMENTED** (Class B) | UI/analysis phase: analytic stationary point or denser sampling near mid-span |
| **VF-SLAB-01** | Slab | two-way moment method is Grashof/Marcus-family, **non-ACI** | R7 | Medium | unknown vs ACI — **method disclosed**, number unchanged | **DOCUMENTED / REVIEW** (Class B) | obtain ACI/textbook reference or keep disclosed as REVIEW; **do not change the number** without a golden-value review |
| **VF-07 / VF-12 / VF-13** | Beam | MKS coefficient roundings (`β1` dual threshold, `0.53√f'c` `Vc`, etc.) | R8 | Low | **Yes** (conservative) | **ACCEPTED** | none |
| **VF-SLAB-02 / VF-SLAB-03** | Slab | spacing floor at 2.5 cm; `As_provided ≥ As_required` invariant not held at the floor | R8 / R10 | Low | **Yes** | **ACCEPTED** | none |
| **VF-STAIR-02 / VF-STAIR-03** | Stair | U-shape load model; temp-steel detailing choices | R8 / R9 | Low | **Yes** | **ACCEPTED** | none |
| **VF-06** | Stair | straight-vs-U load model (simply-supported span) | R9 | — | **Yes** (mid-span +M only) | **DOCUMENTED** | scope stated; no support/negative-M design |
| **VF-08** | BOQ | rebar ratios 150/120/90 kg/m³ uncited | R8 / R9 | — | n/a (quantity, not a load) | **ACCEPTED** | none |
| **VF-10** | Column | tie-spacing check has no provided-spacing input | R9 | Low | — | **DOCUMENTED** | UI phase: add a provided tie-spacing input if tie design is to be a verdict item |
| **VF-COL-01** | Column | `φMn_at_Pu` display reads ≈0 near pure axial | R10 | Low | n/a (display-only, not in `passed`) | **DOCUMENTED** (Class D) | UI phase: guard/annotate the display near the axial cap |
| **VF-COL-03** | Column | `Mu` input help "not used in this version" — stale (Mu **is** used) | R10 | Low | n/a | **DOCUMENTED** (Class D) | UI phase: 1-line help-text fix |
| **VF-COL-05** | Column | module docstring mentions biaxial/Bresler — uniaxial only | R10 | Low | n/a | **DOCUMENTED** (Class D) | UI phase: docstring correction |
| **VF-BLDG-02** | Building | degenerate inputs handled gracefully (no crash) | R9 | — | **Yes** | **ACCEPTED** | none |
| **VF-14 / VF-15** | ACI primitives | minor MKS/SI presentation notes | R8 / R10 | Low | **Yes** | **ACCEPTED** | none |
| **ER-01** | Report | `_governing_as = max(As_req, As_min)` + SI→MKS display helpers in the report layer | R10 | Low | n/a (engine values, no verdict change) | **DOCUMENTED** (Class D) | UI phase: move selection + display units into the modules/shared helper; keep factors |
| **ER-02** | Building | PDF report **title** says "Analysis" | R10 | Low | n/a (verdict is `MODEL`) | **DOCUMENTED** (Class D) | UI phase: title reword |
| **ER-03** | Building | "AI" wording for fixed-threshold clustering | R10 | Low | n/a | **DOCUMENTED** (Class D) | UI phase: reword "rule-based" |
| **ER-05** | Drawing | one white PNG shared by dark UI + white PDF | R10 | Low | n/a | **DOCUMENTED** (Class D) | UI phase: opt-in dark `draw_*` variant, geometry untouched |
| **ER-06** | Report | generation date absent on direct `generate_*` sheets | R10 | Low | n/a | **DOCUMENTED** (Class D) | UI phase: add "จัดทำ <today>" token |
| **RB-1 … RB-7** | various | `REGRESSION_BASELINE.md` "potential engineering review" notes (pile coordinate convention, etc.) | R7–R10 | Low | mostly **Yes** | **DOCUMENTED** | carried; addressed where relevant in EV-05 (RB-6 pile coords) |
| **SYS-01** | all members + Home | a failed design showed the amber **"REVIEW"** summary badge, not a red **"FAIL"** (pre-UI-01) | R10 | Low–Medium (under-states, never over-states; **not** a false PASS) | **Yes** (conservative direction — never claims safety) | **CLOSED / RESOLVED (UI-01)** — was Class B, new in EV-09 | **DONE in UI-01:** presentation mapping only — 7 member summary badges + `main._module_status_rows` render `fail`/`FAIL` on `passed is False`; DESIGN CHECKS rows show `ไม่ผ่าน (FAIL)`; first-class `review` badge state added to `utils/ui.py`. No calculation / `passed` / `_status_state` / report / drawing / test change. |

**No entry has status `RELEASE BLOCKER`.** Historical findings are retained
(none deleted).

---

## 23. Production Changes

**EV-09 made ZERO production calculation changes.**

- `git diff` for `modules/*`, `utils/*`, `reports/*`, `main.py` since the EV-08
  end state: **no change** attributable to EV-09.
- Files added by EV-09: `tests/validation/run_ev09_system.py`,
  `docs/SYSTEM_CAPABILITY_MATRIX.md`, `docs/ENGINEERING_RELEASE_MATRIX.md`,
  `docs/EV09_COMPLETION_REPORT.md`, and the `docs/ENGINEERING_VALIDATION.md`
  §9.11 / §8 append.
- The EV-09 brief permits a production change only for a *system-level safety
  defect that could not have been fixed in a prior EV*. **None was found.**
  SYS-01 is R10 (presentation) and is explicitly deferred, not fixed, because a
  validation phase does not make cosmetic UI changes and SYS-01 is not a safety
  defect.

The pre-existing uncontroversial working-tree changes (STEP 2–15 UI work + the
EV-03/04/05/07 fixes + all EV docs) are unchanged by EV-09 and remain
uncommitted, awaiting the user's explicit commit instruction.

---

## 24. Final Release Matrix

Full matrix in **`docs/ENGINEERING_RELEASE_MATRIX.md`**. Summary:

| Module | Core Calc | Independent Validation | Verdict Audit | UI | Report | Drawing | Release |
|---|---|---|---|---|---|---|---|
| Beam | PASS | PASS | PASS | PASS* | PASS | PASS | **READY** |
| Slab | PASS | PASS | PASS | PASS* | PASS | PASS | **READY** (two-way = REVIEW) |
| Footing | PASS | PASS | PASS | PASS* | PASS | PASS | **READY** |
| Column | PASS | PASS | PASS | REVIEW (R10) | PASS | PASS | **READY** (uniaxial short) |
| Stair | PASS | PASS | PASS | PASS* | PASS | PASS | **READY** (mid-span flexure) |
| Building | MODEL | PASS | N/A | REVIEW (R10) | PASS | PASS | **READY as a MODEL** |
| Continuous Beam Analysis | PASS | PASS | N/A | PASS | PASS | PASS | **READY** (VF-04 documented) |
| Drawing | N/A | N/A | N/A | PASS | ER-05 | — | **READY** |
| Report | N/A | N/A | PASS | PASS | ER-01 | — | **READY** |
| BOQ | N/A | PASS | N/A | PASS | PASS | — | **READY** |

`*` SYS-01 — FAIL renders as the "REVIEW" badge (under-states, never
over-claims).

---

## 25. Release Decision

# ✅ ENGINEERING RELEASE READY

All ten EV-09 §24 criteria are met (see `ENGINEERING_RELEASE_MATRIX.md`):
no unresolved critical safety defect; no reachable false PASS; no unit error;
no load-conservation failure; the report changes no engineering result; the UI
never falsely claims PASS; all validated engines still pass; the verdict chain is
correct and single-sourced; scope is explicit; known limitations are documented.

**Released as:** a **member-level ACI 318M-08 design tool** (beam, one-way slab,
isolated footing & pile cap, short uniaxial column with full P–M interaction,
inclined-slab stair mid-span flexure, continuous-beam analysis) **plus a Building
MODEL** (grid + single-storey tributary vertical takedown + budget BOQ).
**Not** released as a building structural-analysis package.

---

## 26. Remaining Limitations (carried into release)

1. **SYS-01** — failed member designs show "REVIEW", not "FAIL", at the summary
   badge (detail text and per-row table still say FAIL). Class B, R10.
2. **VF-SLAB-01** — two-way slab moment coefficients are a non-ACI
   Grashof/Marcus method; disclosed, number unchanged, status REVIEW.
3. **VF-04 / ER-04** — continuous-beam governing `+M` is a sampled peak;
   ≤~0.003 % non-conservative, bounded, test-locked.
4. **VF-05** — Building Model drops tributary quarter-areas at removed columns
   (non-conservative for irregular grids; nothing is sized from these values).
5. **Assembled `_render_*` numbers remain BLOCKED** — the interleaved
   compute/render chains cannot be validated as end-to-end numbers without a
   compute/render split (which a validation phase must not perform). Every
   importable / derivable component **is** validated.
6. **Stale text** (VF-COL-03, VF-COL-05, ER-02, ER-03) and
   **layer-boundary display logic** (ER-01, ER-06) — all R10, all deferred.
7. **Not implemented** (never shown as PASS): deflection/serviceability,
   development length, torsion, slab punching/one-way shear, column
   slenderness/P-Δ/biaxial, stair support/shear, multi-storey accumulation,
   foundation reaction pathway, beam line-load takedown, lateral/wind/seismic,
   combined/mat/strap footings.

---

## 27. Post-release Engineering Risks

| Risk | Likelihood | Mitigation in place |
|---|---|---|
| A user treats the **Building Model** output as a full structural analysis | Medium | on-screen `MODEL GENERATED` + "ยังไม่มีการวิเคราะห์โครงสร้าง" caption; PDF `status="MODEL"`; scope tables. **Residual:** the PDF title still says "Analysis" (ER-02). |
| A user reads the amber **"REVIEW"** summary badge as "minor issue" when the design actually **fails** an implemented check (SYS-01) | Medium | the `st.error("❌ ไม่ผ่าน (FAIL) — …")` box + per-row "ตรวจสอบ" table always render on `passed is False`. **Residual:** the summary badge. Fix in UI Integration. |
| A user applies the **column** module to a **slender** or **biaxially loaded** column | Medium | scope tables; **Residual:** the stale docstring mentions "biaxial/Bresler" (VF-COL-05) and the `Mu` help says "not used" (VF-COL-03). Fix in UI Integration. |
| A user relies on the **two-way slab** moments as ACI-compliant | Low–Medium | REVIEW status + disclosure that the method is non-ACI (VF-SLAB-01). |
| A user runs **irregular-grid** column takedown and trusts the per-column `Pu` | Low | function docstring + `SYSTEM_CAPABILITY_MATRIX` note (VF-05); nothing downstream is sized from these values. |
| Continuous-beam `+M` marginally under-predicted (VF-04) | Low | bounded ≤~0.003 %; test-locked; documented. |
| A future edit **reverts** one of the EV-03…EV-07 gates | Low | `run_ev09_system.py` phase H asserts each gate string is still present in its `passed` boolean; EV-03/04/05/07 regression tests fail if the fix is removed. |

---

## 28. Recommendation for UI Integration (next phase — NOT started in EV-09)

Priority order for the UI-Integration phase:

1. **SYS-01** — give `passed is False` a distinct red **"FAIL"** summary badge;
   reserve **"REVIEW"** for limitation-only states (e.g. two-way slab). Keep the
   detail text as-is.
2. **Stale text** — 1-line corrections with before/after: VF-COL-03 (`Mu` help),
   VF-COL-05 (column docstring), ER-02 (building report title), ER-03 ("AI" →
   "rule-based").
3. **Layer boundary** — move `_governing_as` (`max(As_req, As_min)`) and the
   SI→MKS display helpers out of `reports/pdf_generator.py` into the modules or a
   shared `utils` helper (ER-01); keep every numeric factor. Add the generation
   date to the direct `generate_*` footers (ER-06).
4. **Drawing** — opt-in `dark=` variant of the `draw_*` helpers for the
   Streamlit UI; `savefig` for the PDF stays white; **geometry, coordinates,
   dimensions, scale untouched** (ER-05).
5. **VF-SLAB-01** — obtain and cite the reference for the two-way moment
   coefficients, or keep the method disclosed as REVIEW in the UI.
6. **Do not** add any structural analysis, load path, design equation, member
   feature, seismic/wind, biaxial, slenderness or detailing in the UI phase —
   those are separate, post-UI engineering phases with their own validation.

**EV-09 END STATE:** EV-01 → … → EV-08 → **EV-09 System Consolidation** →
**ENGINEERING RELEASE GATE: READY** → **STOP.** UI Integration is a separate
phase and is **not** begun here.
