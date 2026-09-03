# RC CodePro — Engineering Release Matrix (EV-09)

**Decision date:** 2026-09-03 · **Gate:** EV-09 System-Wide Consolidation &
Release Gate · **Baseline:** `pytest` **80 passed**, 0 failed, 0 skipped ·
EV-02…EV-09 runners **0 FAIL**.

Column meanings:

- **Core Calc** — is the module's own engineering calculation validated?
  `PASS` = matched by an independent first-principles reference (EV-02…EV-08);
  `MODEL` = no design calculation (Building Model).
- **Independent Validation** — a reference that does **not** import production
  code exists and agrees within per-case tolerance.
- **Verdict Audit** — the `passed` / `status` boolean correctly reflects **every
  implemented** safety check (EV-09 false-PASS audit, phase H).
- **UI Consistency** — on-screen labels / units / badges do not over-claim the
  engine (EV-09 phases B, G).
- **Report** — `build_report` renders the module's `checks` + `status`
  **unchanged**; no recompute (EV-09 phases C, E).
- **Drawing** — `utils/drawing.py` consumes computed values only; no recompute
  (EV-09 phase D).
- **Release** — per-module engineering-release verdict.

---

## Release Matrix

| Module | Core Calc | Independent Validation | Verdict Audit | UI Consistency | Report | Drawing | Release |
|---|---|---|---|---|---|---|---|
| **Beam** | PASS | PASS (EV-02 + EV-03, 127 checks 0 FAIL) | PASS — `As,max` tension-controlled gate added EV-03 (VF-11) | PASS *(SYS-01 CLOSED by UI-01 — failed design now renders the red "FAIL" badge)* | PASS — `checks`+`status` unchanged | PASS — geometry only | **READY** |
| **Slab** | PASS (one-way) | PASS (EV-04, 77 checks 0 FAIL) | PASS — ductility gate added EV-04 (VF-11 class) | PASS *(SYS-01 CLOSED — UI-01)* | PASS | PASS | **READY (one-way)** · two-way method = **REVIEW** (VF-SLAB-01, non-ACI, disclosed, number unchanged) |
| **Footing** | PASS | PASS (EV-05, 67 checks 0 FAIL) | PASS — eccentricity-resolvable gate added EV-05 (VF-FOOT-02); VF-09 RESOLVED (not a defect) | PASS *(SYS-01 CLOSED — UI-01)* | PASS — both report call sites | PASS | **READY** |
| **Column** | PASS | PASS (EV-06 — P–M curve rel < 2e-13 vs independent strain-compatibility solver; EV-COL-003/004/005 UNBLOCKED) | PASS — variable φ applied correctly; **0 fixes needed**; `φMn_at_Pu` display is not in `passed` (VF-COL-01) | REVIEW — VF-COL-03 (`Mu` help "not used" is stale — Mu **is** used) + VF-COL-05 (docstring "biaxial/Bresler" stale). R10, no calc impact. | PASS | PASS — plots passed-in curve | **READY (uniaxial short column)** |
| **Stair** | PASS | PASS (EV-07, 70 checks 0 FAIL) | PASS — ductility gate added EV-07 (VF-STAIR-01, VF-11 class, both renders); STEP-14 FAIL→REVIEW verified to mask no result | PASS *(SYS-01 CLOSED — UI-01)* | PASS | PASS | **READY (mid-span flexure of the idealised inclined one-way slab)** |
| **Building** | MODEL | PASS (EV-08 — load conservation `Σ Pu = Wu·floor_area` rel < 1e-9 for the regular grid; BOQ rel < 1e-9; **0 fixes**) | N/A — **no design verdict**; on-screen "MODEL GENERATED", PDF `status="MODEL"`, `_status_state("MODEL")→"MODEL"` (PDF cannot turn MODEL into PASS) | REVIEW — ER-02 (report **title** "Analysis" over-claims; verdict is correctly MODEL) + ER-03 ("AI" wording for threshold clustering). R10. | PASS — MODEL preserved | PASS | **READY as a MODEL** (grid + single-storey tributary takedown + budget BOQ — **not** a structural-analysis release) |
| **Continuous Beam Analysis** | PASS | PASS (EV-02 — independent three-moment reference) | N/A (feeds Beam demand) | PASS | PASS (flows into Beam report demand) | PASS (SFD/BMD plots computed arrays) | **READY** — VF-04/ER-04 (sampled +M peak, ≤~0.003 % non-conservative, bounded, test-locked) DOCUMENTED |
| **Drawing** | N/A | N/A — EV-09 source audit: no calc-helper call | N/A | PASS — no label implies an unimplemented check ("Safe zone" is correct) | ER-05 (shared white PNG) — R10 | — | **READY** (creates no engineering result) |
| **Report** | N/A | N/A — EV-09 source audit: `_status_state` no maths; `build_report` no recompute | PASS — `_status_state` True→PASS / False→FAIL / "MODEL"→MODEL verified | PASS | ER-01 (`_governing_as = max(As_req, As_min)` — display selection of engine values; ER-06 gen-date) — R10 | — | **READY** (renders engine truth) |
| **BOQ** | N/A (quantity) | PASS (EV-08 — independent take-off rel < 1e-9) | N/A | PASS — caption "preliminary budget estimate only" | PASS (optional table) | — | **READY** — VF-08 (rebar ratios uncited) DOCUMENTED; **not a load source** |

---

## Release-blocking classification (all findings)

| Class | Meaning | Count | IDs |
|---|---|---|---|
| **A — RELEASE BLOCKER** | reachable non-conservative defect / false PASS / unit error / load loss into a sized member / verdict inversion / report mutates a result | **0** | — |
| **B — RELEASE REVIEW** | consistent, non-over-claiming, but worth a UI-phase decision | 2 open + 1 closed | ~~**SYS-01** (FAIL badge showed "REVIEW")~~ → **CLOSED by UI-01** (presentation mapping only; failed design now shows the red "FAIL" badge; first-class `review` state added); **VF-SLAB-01** (two-way method non-ACI, disclosed); **VF-04/ER-04** (sampled +M peak) |
| **C — DOCUMENTED LIMITATION** | intentional scope / conservative approximation, disclosed | 9 | VF-05 (irregular-grid quarter-area drop), VF-FOOT-01 (VF-11 latent-unreachable), VF-FOOT-03 (`d` conservative), VF-07/VF-12/VF-13 (MKS coefficient roundings — conservative), VF-08 (BOQ ratios), VF-10 (tie-spacing input), VF-SLAB-02/03, VF-STAIR-02/03, RB-1…RB-7 |
| **D — UI ONLY** | wording / presentation, zero engineering-value impact | 6 | ER-01 (`_governing_as` display selection), ER-02 (building report title), ER-03 ("AI" wording), ER-05 (shared PNG), ER-06 (gen-date), VF-COL-01 (`φMn_at_Pu` display), VF-COL-03 (`Mu` help text), VF-COL-05 (biaxial docstring) |
| **E — FUTURE FEATURE** | not implemented; never shown as PASS | — | deflection, dev length, torsion, punching/one-way slab shear, slenderness/P-Δ, biaxial, stair support/shear, multi-storey accumulation, foundation pathway, beam line-load, lateral/wind/seismic, combined/mat/strap footings |

*(D and E counts overlap the “Known Review” cells above; VF-COL-01/03/05 sit in
both a module row and class D.)*

---

## FINAL ENGINEERING RELEASE DECISION

# ✅ ENGINEERING RELEASE READY

**Criteria (EV-09 §24):**

| # | Criterion | Result |
|---|---|---|
| 1 | No unresolved critical safety defect | ✅ 0 Category-A findings |
| 2 | No reachable false PASS | ✅ VF-11 class fixed (beam/slab/stair), latent-unreachable (footing), absent (column), N/A (building); every `passed` includes its gate |
| 3 | No unit error | ✅ EV-02…EV-08 audited every conversion — no R2 |
| 4 | No load-conservation failure | ✅ regular grid `Σ Pu = Wu·floor_area` rel < 1e-9; VF-05 irregular-grid drop is bounded, documented, feeds nothing sized |
| 5 | Report does not change an engineering result | ✅ `build_report` renders `checks`+`status` unchanged; `_status_state` no recompute; MODEL↛PASS |
| 6 | UI does not falsely claim PASS | ✅ FAIL / MODEL badges never over-claim; SYS-01 (badge showed "REVIEW" for a failed design — under-states, never over-states) **CLOSED by UI-01** — failed design now shows the red "FAIL" badge |
| 7 | All validated engines still pass | ✅ `pytest` 80/0/0; EV-02…EV-09 runners 0 FAIL |
| 8 | Verdict chain correct | ✅ engine → `checks`+`passed` → screen **and** report, single source of truth |
| 9 | Scope explicit | ✅ `SYSTEM_CAPABILITY_MATRIX.md` §2, this matrix, `ENGINEERING_VALIDATION.md` §10 |
| 10 | Known limitations documented | ✅ Engineering Review Register (`EV09_COMPLETION_REPORT.md` §22), `ENGINEERING_REVIEW.md`, `ENGINEERING_VALIDATION.md` §9 |

**Scope of this release:** RC CodePro is released as a **member-level ACI 318M-08
design tool** (beam flexure/shear/detailing, one-way slab, isolated footing &
pile cap, short uniaxial column with full P–M interaction, inclined-slab stair
mid-span flexure, continuous-beam analysis) **plus** a **Building MODEL**
(grid + single-storey tributary vertical takedown + budget BOQ). It is **not**
released as a building structural-analysis package. Every "REVIEW" and "MODEL"
state is intentional and disclosed; no "PASS" is shown where evidence does not
support it.

**Conditions carried forward to UI Integration (next phase — not part of EV-09):**

1. **SYS-01** — ✅ **DONE in UI-01.** The summary badge now reads **"FAIL"** (red)
   when `passed is False`; **"REVIEW"** is reserved as a first-class state for
   genuine limitations. Presentation mapping only — no calculation, `passed`,
   `_status_state`, report, drawing or test change. `pytest` 80 passed;
   `run_ev09_system.py` 56 checks / PASS 46 / FAIL 0 / REVIEW 10 / RELEASE READY.
2. **VF-COL-03 / VF-COL-05 / ER-02 / ER-03** — 1-line stale-text corrections
   (with before/after), no logic change.
3. **ER-01 / ER-06** — move the `max(As_req, As_min)` selection + SI→MKS display
   helpers into the modules (or a shared helper); keep the numeric factors.
4. **VF-SLAB-01** — obtain the ACI reference (or a cited textbook table) for the
   two-way moment coefficients, or keep the method disclosed as `REVIEW`.

None of the above is a safety defect; none blocks the engineering release of the
validated calculation engine.
