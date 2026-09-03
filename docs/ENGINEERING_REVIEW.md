# Engineering Review Log

Issues discovered while doing UI / report presentation work (STEP 12–13).
**None of these were fixed** — they are recorded for a future engineering pass.
The report / drawing layers are presentation only; they must consume values
produced by the design modules, never recompute them.

**SYS-01** (below) was discovered in EV-09 and **RESOLVED in UI-01** — the only
entry in this log with a `CLOSED` status. ER-01 … ER-06 remain open.

---

## ER-01 — `reports/pdf_generator.py` performs unit conversions and a
governing-value selection inside the presentation layer

- **Location:** `reports/pdf_generator.py` — `_cm`, `_cm2`, `_ton`, `_kgf`,
  `_kgfm`, `_ksc` (SI → MKS display conversions) and `_governing_as(r)`
  (`max(As_req, As_min)`), plus the per-report `summary=` f-strings that
  reformat `results` values.
- **Observed behaviour:** the PDF generator receives `inputs` / `results`
  in SI calculation units and converts them for display; `_governing_as`
  picks `max(As_req, As_min)` for the "required As" line.
- **Why it may matter:** STEP 13's rule is that the report is a pure
  presentation layer. These helpers are display-only (fixed factors,
  `9.80665` / `0.0980665`, `/10`, `/100`) and do not change any check, but a
  `max(...)` selection and unit maths living in the report generator blur
  the layer boundary. If a module and the report ever disagree on the
  conversion factor or on which `As` governs, the PDF could show a number
  the module never computed.
- **Recommended future action:** move display conversions + governing-value
  selection into the modules (or a shared `utils` helper the modules call),
  and have the report render already-converted, already-selected values.
  Do **not** change the numeric factors when doing so.

## ER-02 — Building Model report title still says "structural analysis"

- **Location:** `modules/building.py` — `render_report_expander(title=
  "รายงานวิเคราะห์โครงสร้างอาคารและประมาณราคา (Building Analysis & BOQ
  Report)")`.
- **Observed behaviour:** STEP 13 changed the report **verdict** from a
  design `PASS` to `MODEL GENERATED`, but the report **title** still
  contains "วิเคราะห์โครงสร้าง / Building Analysis".
- **Why it may matter:** the Building Model does a grid layout + tributary
  gravity take-down + BOQ estimate — not a structural analysis in the
  solver sense. The title slightly over-claims.
- **Recommended future action:** rename to e.g. "แบบจำลองอาคารและประมาณ
  ราคา (Building Model & BOQ Report)". Deferred — STEP 13 was told to limit
  the Building change to verdict/status semantics only.

## ER-03 — `_auto_group_columns` / captions call threshold clustering "AI"

- **Location:** `modules/building.py` — `_auto_group_columns` docstring
  ("AI pre-analysis") and the Column-Grouping caption ("AI แนะนำเบอร์เสา").
- **Observed behaviour:** the routine is a fixed ratio threshold
  (`≥ 0.75·Pmax → C1`, `≥ 0.45 → C2`, else `C3`).
- **Why it may matter:** "AI" wording in an engineering deliverable can be
  misread as a learned model.
- **Recommended future action:** reword to "อัตโนมัติ / rule-based". Purely
  cosmetic; no logic change.

## ER-04 — `solve_continuous_beam` reports a *sampled* governing +M

- **Location:** `utils/analysis.py` — `Mu_pos_kgfm = max(M.max(), 0.0)` on
  the fixed `x` sampling grid; `tests/test_analysis.py` locks the sampled
  value.
- **Observed behaviour:** the governing `+Mu` handed to the Beam design
  tab / SFD-BMD annotation is the peak of the sampled moment array, which
  can be marginally below the true analytic maximum between sample points.
- **Why it may matter:** a very small non-conservative gap in the governing
  positive moment.
- **Recommended future action:** evaluate `M(x)` analytically at each span's
  interior stationary point, or densify sampling near mid-span. Test-locked;
  requires an engineering + golden-value review.

## ER-05 — Matplotlib CAD drawings are shared between the dark Streamlit UI
and the white PDF report

- **Location:** `utils/drawing.py` (all `draw_*` matplotlib helpers) +
  `reports/pdf_generator.py` `_image_section` / `_fig_to_buf`.
- **Observed behaviour:** the identical PNG buffer is shown with
  `st.image` / `st.pyplot` in the dark UI **and** embedded white in the
  PDF. STEP 12 could not dark-theme them without either a `draw_*`
  signature change or risking the printed report.
- **Why it may matter:** the drawings read as white blocks inside the dark
  UI (they are correct for print).
- **Recommended future action:** add an opt-in `dark=` / theme parameter to
  the `draw_*` helpers (or a screen-only post-process) so the UI can get a
  dark variant while `savefig` for the PDF stays white — **without**
  touching geometry, coordinates, dimensions or scale.

## ER-06 — Report footer no longer prints the generation date on the direct
`generate_*` paths

- **Location:** `reports/pdf_generator.py` `_Sheet.footer` (STEP 13).
- **Observed behaviour:** the footer was changed to
  `project name … · ACI 318M-08 · หน้า X / {nb}` per the STEP 13 footer
  spec. For `build_report` the generation date is still shown (it equals
  the page-1 title-block "วันที่"). For the direct `generate_*_report`
  functions the title-block "วันที่" is the *project* date, so the
  *generation* date is no longer printed anywhere on those sheets.
- **Why it may matter:** QA/QC sometimes wants the "sheet produced on"
  date distinct from the project date.
- **Recommended future action:** add a compact "จัดทำ <today>" token to the
  footer's right cell if there is horizontal room, or to the title block.
  Presentation only.

## SYS-01 — Failed member design showed an amber `REVIEW` summary badge
instead of a red `FAIL` badge  — **CLOSED / RESOLVED (UI-01)**

- **Discovered:** EV-09 (System-Wide Consolidation & Release Gate).
- **Location:** the DESIGN SUMMARY badge in `modules/beam.py`,
  `modules/slab.py`, `modules/footing.py` (×2), `modules/column.py`,
  `modules/stair.py` (×2), plus `main.py:_module_status_rows` (Home
  dashboard) and the Home "In review" KPI; secondary surface — the
  DESIGN CHECKS table row status text (`"ตรวจสอบ (REVIEW)"`).
- **Observed behaviour (pre-fix):** every member render function rendered
  `ui.status_badge("pass" if passed else "warn", "PASS" if passed else
  "REVIEW")`. When `passed is False` this produced the amber `warn` badge
  labelled "REVIEW" — never a red `fail`/"FAIL". The authoritative
  `st.error("❌ ไม่ผ่าน (FAIL) — <reasons>")`, the per-check red FAIL
  mini-badges, and the PDF (`_status_state(False) → "FAIL"`) were already
  correct — only the *summary badge* and the *checks-row text* softened
  "FAIL" to "REVIEW".
- **Classification:** Class B (engineering / UI **semantic** issue), root
  cause R10 (presentation-layer verdict-state mapping). **Not** a false
  PASS ("REVIEW" ≠ "PASS"); never over-claims safety; therefore
  non-blocking — EV-09 shipped `ENGINEERING RELEASE READY` with SYS-01
  carried as the first UI finding.
- **UI-01 IMPLEMENTATION (resolution):** presentation mapping only —
  - the 7 member summary badges now render
    `ui.status_badge("pass" if passed else "fail", "PASS" if passed else
    "FAIL")`;
  - `main.py:_module_status_rows` maps a failed module to `fail` / `FAIL`;
    the Home KPI is renamed "Needs attention" and counts `verdict ==
    "fail"` (still derived from the module `passed` result);
  - the DESIGN CHECKS row text for a failed *implemented* check is now
    `"ไม่ผ่าน (FAIL)"`;
  - `utils/ui.py:_BADGE` gains a first-class `"review"` state
    (amber, reuses `rc-badge-warn`) so REVIEW stays a real, reachable
    verdict for genuine limitation / unresolved-condition cases.
- **NOT changed:** `passed` composition, engineering `checks`
  construction, every ACI 318M-08 / flexure / shear / P–M / analysis
  calculation, `utils/aci_318m.py`, `utils/analysis.py`,
  `utils/drawing.py`, `reports/pdf_generator.py`
  (`_status_state` / `build_report` already rendered FAIL faithfully),
  the Building MODEL boundary and disclaimer, and all calculation test
  expectations.
- **Verification:** `py -3 -m pytest` → 80 passed / 0 failed / 0 skipped;
  `py -3 tests/validation/run_ev09_system.py` → 56 checks, PASS = 46,
  FAIL = 0, REVIEW = 10, `ENGINEERING RELEASE READY`. The EV-09 Phase-B
  semantics check was strengthened to assert the corrected `fail`/`FAIL`
  mapping and that a first-class `review` state still exists.
- **Status:** **CLOSED / RESOLVED (UI-01).**
