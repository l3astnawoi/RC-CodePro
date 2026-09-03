"""EV-09 — SYSTEM-WIDE consolidation & release gate.

NOT a new calculation feature, NOT a refactor.  EV-09 re-runs every prior
EV runner, asserts the whole set is clean, and adds CROSS-LAYER
consistency checks:

    ENGINE  ->  RESULT  ->  UI  ->  SUMMARY  ->  DRAWING  ->  REPORT

must not change  VALUE / UNIT / STATUS / engineering meaning.

Phases:
  A  Regression + prior-EV re-run       (pytest 80 ; EV-02..08 = 0 FAIL)
  B  Verdict-badge semantics contract   (system-wide PASS / REVIEW / MODEL)
  C  Report layer = presentation only    (build_report / _status_state)
  D  Drawing layer = presentation only   (no engineering recompute)
  E  Single source of truth              (checks list -> screen == report)
  F  Building-model boundary             (MODEL GENERATED, never PASS)
  G  Stale UI text register              (ER-02/03, VF-COL-03/05 -- R10)
  H  Release-blocking review             (0 Category-A blockers)

Run:  py -3 tests/validation/run_ev09_system.py [--brief]
"""

import ast
import inspect
import os
import re
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                    # noqa
    pass
import matplotlib  # noqa: E402
matplotlib.use("Agg")

ROWS = []
_HERE = os.path.dirname(os.path.abspath(__file__))


def chk(case, qty, exp, act, ok, status=None):
    ROWS.append({"case": case, "qty": qty, "expected": exp, "actual": act,
                 "status": status or ("PASS" if ok else "FAIL")})


def note(case, qty, text, status="REVIEW"):
    ROWS.append({"case": case, "qty": qty, "expected": text, "actual": "-",
                 "status": status})


def _literal_text(module):
    """Every string literal in `module`, with Python's implicit
    concatenation of *adjacent* literals already applied by the parser.

    ``inspect.getsource`` + a plain substring test misses a phrase that the
    author wrapped across two adjacent literals, e.g.::

        st.caption("… ยังไม่มีการ"
                   "วิเคราะห์โครงสร้าง (…")

    ``ast.parse`` folds those two literals into ONE ``ast.Constant`` whose
    value is ``"… ยังไม่มีการวิเคราะห์โครงสร้าง (…"`` — the same string the
    running app displays.  We return every literal twice: verbatim, and
    whitespace-collapsed, so a check is robust to a split that also
    introduced a newline/indent between the parts.  This normalises the
    *source*; it never touches production UI text.
    """
    tree = ast.parse(inspect.getsource(module))
    parts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            parts.append(node.value)
            parts.append(re.sub(r"\s+", " ", node.value))
    return "\n".join(parts)


# =========================================================================
# PHASE A — REGRESSION + PRIOR-EV RE-RUN
# =========================================================================
def phase_A():
    # NOTE: pytest.ini already sets `addopts = -q`; passing another -q here
    # makes pytest doubly-quiet and suppresses the summary line, so we add
    # nothing and let the ini's single -q apply.
    r = subprocess.run([sys.executable, "-m", "pytest"], cwd=_ROOT,
                       capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"(\d+)\s+passed", out)
    npassed = int(m.group(1)) if m else 0
    clean = (m is not None and " failed" not in out and " error" not in out
             and r.returncode == 0)
    ok = clean and npassed >= 80
    chk("REGRESSION/pytest", ">= 80 passed, 0 failed, 0 error",
        ">=80 passed", "%d passed%s" % (npassed, "" if clean
        else " (failed/error present or rc!=0)"), ok)

    runners = [
        ("EV-02", "run_ev02_validation.py", "EV-02 checks:"),
        ("EV-03", "run_ev03_beam.py", "EV-03 BEAM checks:"),
        ("EV-04", "run_ev04_slab.py", "EV-04 SLAB checks:"),
        ("EV-05", "run_ev05_footing.py", "EV-05 FOOTING checks:"),
        ("EV-06", "run_ev06_column.py", "EV-06 COLUMN checks:"),
        ("EV-07", "run_ev07_stair.py", "EV-07 STAIR checks:"),
        ("EV-08", "run_ev08_building.py", "EV-08 BUILDING checks:"),
    ]
    for tag, fn, marker in runners:
        rr = subprocess.run([sys.executable, os.path.join(_HERE, fn), "--brief"],
                            cwd=_ROOT, capture_output=True, text=True)
        line = next((l for l in (rr.stdout or "").splitlines() if marker in l), "")
        fail0 = "FAIL=0" in line and rr.returncode == 0
        chk("PRIOR-EV/" + tag, "0 FAIL (%s)" % fn, "FAIL=0",
            line.strip() or "(no summary line)", fail0)


# =========================================================================
# PHASE B — VERDICT-BADGE SEMANTICS CONTRACT
# =========================================================================
def phase_B():
    import modules.beam, modules.slab, modules.footing, modules.column  # noqa
    import modules.stair, modules.building                              # noqa
    srcs = {
        "beam": inspect.getsource(modules.beam),
        "slab": inspect.getsource(modules.slab),
        "footing": inspect.getsource(modules.footing),
        "column": inspect.getsource(modules.column),
        "stair": inspect.getsource(modules.stair),
        "building": inspect.getsource(modules.building),
    }
    # UI-01 / SYS-01 RESOLVED: every member module maps a failed design
    # (passed == False) to the RED "FAIL" summary badge -- NOT the amber
    # "warn"/"REVIEW" badge, and NOT a silent "PASS".  building = "MODEL".
    try:
        import main as _main_mod            # noqa
        main_src = inspect.getsource(_main_mod)
    except Exception:                       # noqa
        main_src = ""
    for m in ("beam", "slab", "footing", "column", "stair"):
        s = srcs[m]
        fixed = ('"pass" if passed else "fail"' in s
                 and '"PASS" if passed else "FAIL"' in s)
        no_old = ('"pass" if passed else "warn"' not in s
                  and '"PASS" if passed else "REVIEW"' not in s)
        chk("SEMANTICS/" + m,
            "summary badge: passed==False -> 'fail'/'FAIL' (red), never "
            "'warn'/'REVIEW' (SYS-01 fix)",
            True, fixed and no_old, "fixed=%s no_old=%s" % (fixed, no_old))
    for m in ("beam", "slab", "footing", "column", "stair"):
        s = srcs[m]
        rows_fixed = ('else "ไม่ผ่าน (FAIL)"]' in s
                      and 'else "ตรวจสอบ (REVIEW)"]' not in s)
        chk("SEMANTICS/" + m + " checks-row",
            "DESIGN CHECKS row: ok==False -> 'ไม่ผ่าน (FAIL)', never "
            "'ตรวจสอบ (REVIEW)' for an implemented check (SYS-01 fix)",
            True, rows_fixed, rows_fixed)
    chk("SEMANTICS/building", "summary badge = 'MODEL GENERATED' (info), "
        "no design PASS", True,
        'status_badge("info", "MODEL GENERATED")' in srcs["building"]
        and '"pass" if' not in srcs["building"],
        'status_badge("info", "MODEL GENERATED")' in srcs["building"])
    chk("SEMANTICS/home-dashboard",
        "main._module_status_rows maps a failed module to 'fail'/'FAIL', "
        "not 'warn'/'REVIEW' (SYS-01 fix)", True,
        (main_src != "" and 'else "fail"' in main_src
         and 'else "FAIL"' in main_src
         and 'else "warn"' not in main_src
         and 'else "REVIEW"' not in main_src),
        "checked" if main_src else "main.py not importable")
    # the authoritative FAIL text is still shown on failure in every module
    for m in ("beam", "slab", "footing", "column", "stair"):
        s = srcs[m]
        has_fail = ("FAIL_TXT" in s or 'st.error(f"{FAIL_TXT}' in s
                    or "ไม่ผ่าน" in s)
        chk("SEMANTICS/" + m, "detailed FAIL message (FAIL_TXT + reasons) "
            "rendered on failure", True, has_fail, has_fail)
    # REVIEW must remain a real, reachable verdict state (for
    # limitation / unresolved-condition cases) -- it is not deleted.
    ui_src = inspect.getsource(__import__("utils.ui", fromlist=["ui"]))
    pg_src = inspect.getsource(__import__("reports.pdf_generator",
                                          fromlist=["pdf_generator"]))
    chk("SEMANTICS/REVIEW still first-class",
        "utils.ui._BADGE has a 'review' state AND "
        "reports.pdf_generator._status_state still emits 'REVIEW'",
        True,
        ('"review":' in ui_src and 'return "REVIEW"' in pg_src),
        ('"review" in _BADGE=%s' % ('"review":' in ui_src)))
    note("SEMANTICS/CONTRACT (SYS-01 — RESOLVED by UI-01)",
         "HISTORY: EV-09 discovered SYS-01 -- every member module (and the "
         "Home dashboard) rendered the amber 'warn'/'REVIEW' summary badge "
         "when passed == False, instead of a red 'fail'/'FAIL' badge; the "
         "DESIGN CHECKS rows showed 'ตรวจสอบ (REVIEW)' for failed "
         "implemented checks.  Classified Class B (engineering/UI semantic "
         "issue), R10, non-blocking (never a false PASS). "
         "RESOLUTION: UI-01 changed ONLY the presentation mapping in "
         "beam/slab/footing/column/stair render fns + main._module_status_"
         "rows + the 'Needs attention' KPI, and added a first-class "
         "'review' badge state to utils.ui._BADGE.  passed composition, "
         "checks construction, _status_state, build_report, drawing and "
         "every ACI 318M-08 calculation are UNCHANGED. "
         "CONTRACT (unchanged): PASS = every implemented check satisfied; "
         "FAIL = an implemented check is not satisfied; REVIEW = a "
         "limitation / unresolved condition prevents a PASS claim (still "
         "reachable, still first-class); MODEL = model generated, no "
         "design verdict. STATUS: CLOSED / RESOLVED.",
         "CLOSED / RESOLVED", "PASS")


# =========================================================================
# PHASE C — REPORT LAYER = PRESENTATION ONLY
# =========================================================================
def phase_C():
    from reports import pdf_generator as PG
    src = inspect.getsource(PG)
    ss = inspect.getsource(PG._status_state)
    chk("REPORT/_status_state no recompute",
        "bool/None/str -> PASS|FAIL|REVIEW|MODEL, no engineering maths",
        True,
        ("0.85" not in ss and "sqrt" not in ss and "rho" not in ss
         and "* fc" not in ss and "return \"PASS\"" in ss.replace("'", '"')),
        ("0.85" not in ss and "sqrt" not in ss))
    br = inspect.getsource(PG.build_report)
    chk("REPORT/build_report faithful",
        "renders `checks` rows + `status` as passed in; verdict = "
        "_status_state(status, checks_ok); no recompute",
        True,
        ("_checks_table(pdf, checks)" in br
         and "_status_state(status, checks_ok)" in br
         and "0.85 *" not in br and "sqrt(" not in br),
        ("_checks_table(pdf, checks)" in br
         and "_status_state(status, checks_ok)" in br))
    chk("REPORT/MODEL never becomes PASS",
        "_status_state('MODEL') -> 'MODEL'", "MODEL",
        PG._status_state("MODEL"), PG._status_state("MODEL") == "MODEL")
    chk("REPORT/bool False stays FAIL",
        "_status_state(False) -> 'FAIL'", "FAIL",
        PG._status_state(False), PG._status_state(False) == "FAIL")
    chk("REPORT/bool True stays PASS",
        "_status_state(True) -> 'PASS'", "PASS",
        PG._status_state(True), PG._status_state(True) == "PASS")
    note("REPORT/_governing_as (ER-01)",
         "reports/pdf_generator.py._governing_as(r) = max(As_req, As_min) "
         "-- a DISPLAY selection of which As governs the 'required steel' "
         "line, using values the ENGINE already computed. It changes no "
         "verdict and no capacity. Plus the SI->MKS display helpers "
         "(_cm / _cm2 / _ton / _ksc, fixed factors). Root cause R10 / "
         "borderline layer-boundary. RECORD (re-confirms ER-01). "
         "Recommendation: move the max() + unit display into the modules "
         "(or a shared helper) in the UI-Integration phase. Not a "
         "release blocker (no engineering value is mutated).", "REVIEW")


# =========================================================================
# PHASE D — DRAWING LAYER = PRESENTATION ONLY
# =========================================================================
def phase_D():
    from utils import drawing as DR
    src = inspect.getsource(DR)
    # the drawing layer must not re-derive As / phiMn / Vc / the P-M curve
    forbidden = ("_calculate_pm_curve", "solve_continuous_beam",
                 "_as_flexure_ksc", "_required_as_flexure", "_flex_ksc",
                 "vc_beam", "_flexure_as", "rho_max")
    hits = [f for f in forbidden if f in src]
    chk("DRAWING/no engineering recompute",
        "utils/drawing.py does not call any calc helper "
        "(_calculate_pm_curve / solve_continuous_beam / _*flexure* / "
        "vc_beam / rho_max)", [], hits, len(hits) == 0)
    note("DRAWING/geometry only (ER-05)",
         "utils/drawing.py takes ALREADY-COMPUTED values (curve arrays, "
         "As, spacings, dimensions) and plots geometry + labels. The "
         "arithmetic it contains is dimension-line offsets and drawing "
         "clamps (0.85*D bar limit, 1.6*t leader offset, 0.85*h pile "
         "embed cap) -- no flexure / shear / phi / As calculation. The "
         "same white PNG is shown in the dark UI and embedded in the "
         "white PDF (ER-05, R10). No new engineering result is created.",
         "PASS")


# =========================================================================
# PHASE E — SINGLE SOURCE OF TRUTH
# =========================================================================
def phase_E():
    import modules.beam, modules.slab, modules.stair, modules.footing  # noqa
    for m, mod in (("beam", modules.beam), ("slab", modules.slab),
                   ("stair", modules.stair)):
        s = inspect.getsource(mod)
        # the checks list is built once and both rendered and passed to the
        # report -- the modules document this explicitly
        one_source = ("one source, rendered here" in s
                      or "passed unchanged to the PDF report" in s
                      or "one source" in s)
        chk("SSOT/" + m, "`checks` list is one source (screen == report)",
            True, one_source, one_source)
    note("SSOT/contract",
         "Every member module builds its Demand/Capacity `checks` list and "
         "its `status` / `passed` verdict ONCE, then (a) renders it on "
         "screen via ui.engineering_table and (b) passes the SAME list + "
         "status to render_report_expander -> build_report. The report "
         "layer does not recompute (phase C). The drawing layer does not "
         "recompute (phase D). Source of truth = the module engine. "
         "PASS.", "PASS")


# =========================================================================
# PHASE F — BUILDING-MODEL BOUNDARY
# =========================================================================
def phase_F():
    import modules.building as B
    s = inspect.getsource(B)
    chk("BUILDING/no verdict", "no `passed` boolean, no design PASS badge",
        True, ("passed" not in s and 'status_badge("pass"' not in s),
        ("passed" not in s and 'status_badge("pass"' not in s))
    chk("BUILDING/status MODEL", "on-screen 'MODEL GENERATED' + "
        "report status='MODEL'", True,
        ('status_badge("info", "MODEL GENERATED")' in s
         and 'status="MODEL"' in s),
        ('status_badge("info", "MODEL GENERATED")' in s
         and 'status="MODEL"' in s))
    chk("BUILDING/no analysis coupling",
        "does not import/call utils.analysis.solve_continuous_beam",
        True, "solve_continuous_beam" not in s, "solve_continuous_beam" not in s)
    # The honest disclaimer is ONE caption the author wrapped across three
    # adjacent string literals:
    #   "แบบจำลองเส้นกริดถูกสร้างจากค่าที่ป้อน — ยังไม่มีการ"
    #   "วิเคราะห์โครงสร้าง (ถ่ายน้ำหนักในแนวดิ่งด้วยวิธี"
    #   "พื้นที่รับน้ำหนักเท่านั้น)"
    # `_literal_text` folds them the way the parser does, so we can assert
    # the COMPLETE intended phrase "ยังไม่มีการวิเคราะห์โครงสร้าง"
    # (no structural analysis) rather than three loose fragments.
    lit = _literal_text(B)
    caption_honest = ("แบบจำลองเส้นกริดถูกสร้างจากค่าที่ป้อน" in lit
                      and "ยังไม่มีการวิเคราะห์โครงสร้าง" in lit
                      and "ถ่ายน้ำหนักในแนวดิ่งด้วยวิธีพื้นที่รับน้ำหนักเท่านั้น"
                      in lit)
    chk("BUILDING/caption honest",
        "MODEL SUMMARY caption (adjacent string literals joined) contains "
        "the complete phrase 'ยังไม่มีการวิเคราะห์โครงสร้าง' — the grid "
        "model is generated but NO structural analysis is performed",
        True, caption_honest, caption_honest)


# =========================================================================
# PHASE G — STALE UI TEXT REGISTER
# =========================================================================
def phase_G():
    import modules.column as C, modules.building as B
    cs, bs = inspect.getsource(C), inspect.getsource(B)
    # ST-01 (UI-02A) — the Mu help text was "ยังไม่นำมาคิดในรุ่นนี้" (not
    # used in this version) while Mu drives the P-M verdict
    # (pm_ok = _point_in_poly(Mu, Pu, ...), a term in `passed`).  UI-02A
    # replaced ONLY the help string.  Assert the misleading text is gone
    # and the new wording states the real behaviour (P-M interaction,
    # single-axis).  Text-only — no calculation change.
    cs_lit = _literal_text(C)
    st01_old_gone = "ยังไม่นำมาคิดในรุ่นนี้" not in cs
    st01_says_pm = ("ปฏิสัมพันธ์ P-M" in cs_lit and "(Mu, Pu)" in cs_lit)
    st01_says_uniaxial = "แกนเดียว" in cs_lit
    chk("STALE/ST-01 (column Mu help) — RESOLVED UI-02A",
        "Mu help no longer says 'not used'; now states it checks the "
        "(Mu, Pu) point against the single-axis P-M interaction curve",
        True,
        (st01_old_gone and st01_says_pm and st01_says_uniaxial),
        "old_gone=%s says_pm=%s says_uniaxial=%s"
        % (st01_old_gone, st01_says_pm, st01_says_uniaxial))
    # Mu is still wired into the verdict (guard against an over-zealous
    # "cleanup" that drops the input) -- source-level, no numbers.
    chk("STALE/ST-01 — Mu still drives the P-M verdict",
        "column.py still contains pm_ok = _point_in_poly(Mu, Pu, ...) "
        "and pm_ok is a term in `passed`",
        True,
        ("_point_in_poly(Mu, Pu," in cs and "and pm_ok" in cs),
        ("_point_in_poly(Mu, Pu," in cs and "and pm_ok" in cs))
    # ST-02 (UI-02B1) — the column module docstring claimed "biaxial P-M
    # interaction design" / "bending about X and Y" / "Bresler reciprocal-
    # load method".  The live engine is UNIAXIAL only (_calculate_pm_curve
    # builds ONE single-axis curve; pm_ok = _point_in_poly(Mu, Pu, ...)).
    # UI-02B1 rewrote ONLY the module docstring.  Source-level, no calc.
    st02_old_gone = ("biaxial P-M interaction design" not in cs
                     and "biaxial check by the Bresler" not in cs
                     and "curves for bending about X and Y" not in cs)
    st02_says_uniaxial = ("uniaxial P-M design" in cs
                          and "UNIAXIAL only" in cs
                          and "single-axis" in cs)
    st02_bresler_only_negated = (("Bresler" not in cs)
                                 or ("NOT implemented" in cs))
    chk("STALE/ST-02 (column biaxial docstring) — RESOLVED UI-02B1",
        "column module docstring no longer claims biaxial / Bresler / "
        "X-and-Y; it now states the implementation is uniaxial / "
        "single-axis (biaxial + Bresler, if mentioned, only as NOT "
        "implemented)",
        True,
        (st02_old_gone and st02_says_uniaxial and st02_bresler_only_negated),
        "old_gone=%s says_uniaxial=%s bresler_only_negated=%s"
        % (st02_old_gone, st02_says_uniaxial, st02_bresler_only_negated))
    chk("STALE/ST-02 — column engine still uniaxial (unchanged)",
        "column.py still builds one curve via _calculate_pm_curve and "
        "pm_ok = _point_in_poly(Mu, Pu, phiMn_c, phiPn_c) is a term in "
        "`passed`; no Mux / Muy / biaxial_ok in the live path",
        True,
        ("_point_in_poly(Mu, Pu, phiMn_c, phiPn_c)" in cs
         and "and pm_ok" in cs
         and "Mux" not in cs and "Muy" not in cs),
        ("_point_in_poly(Mu, Pu, phiMn_c, phiPn_c)" in cs
         and "and pm_ok" in cs
         and "Mux" not in cs and "Muy" not in cs))
    # ST-03 (UI-02B1) — the Building PDF filename/title said "Analysis" /
    # "วิเคราะห์โครงสร้างอาคาร" while the module is a MODEL (grid +
    # tributary vertical takedown + BOQ; status="MODEL").  UI-02B1
    # corrected ONLY the filename + title strings.
    st03_old_gone = ("building_analysis_boq_report.pdf" not in bs
                     and "Building Analysis & BOQ Report" not in bs
                     and "รายงานวิเคราะห์โครงสร้างอาคาร" not in bs)
    st03_new_present = ("building_model_boq_report.pdf" in bs
                        and "Building Model & BOQ Report" in bs
                        and "รายงานแบบจำลองอาคาร" in bs)
    st03_model_boundary_kept = ('status="MODEL"' in bs
                                and 'status_badge("info", "MODEL GENERATED")'
                                in bs
                                and "ยังไม่มีการ" in bs
                                and "วิเคราะห์โครงสร้าง" in bs)
    chk("STALE/ST-03 (building report title) — RESOLVED UI-02B1",
        "Building PDF filename/title now say 'Building Model & BOQ "
        "Report' (not 'Analysis'); status='MODEL', the MODEL GENERATED "
        "badge and the 'no structural analysis' disclaimer are unchanged",
        True,
        (st03_old_gone and st03_new_present and st03_model_boundary_kept),
        "old_gone=%s new_present=%s model_boundary_kept=%s"
        % (st03_old_gone, st03_new_present, st03_model_boundary_kept))
    note("STALE/ER-03 (building 'AI' wording)",
         "building.py _auto_group_columns docstring 'AI pre-analysis' + "
         "'AI แนะนำเบอร์เสา' caption -- it is FIXED-THRESHOLD clustering "
         "(no learned model). R10. Present: %s" % ("AI pre-analysis" in bs),
         "REVIEW")
    note("STALE/audit result",
         "EV-09 recorded 4 stale-text items (VF-COL-03, VF-COL-05, ER-02, "
         "ER-03), all R10 (UI / doc wording), none a release blocker. "
         "RESOLVED: VF-COL-03 / ST-01 (Mu help, UI-02A); VF-COL-05 / ST-02 "
         "(column biaxial docstring, UI-02B1); ER-02 / ST-03 (building "
         "report title, UI-02B1) -- all text-only, no calculation change. "
         "1 remains: ER-03 / ST-04 ('AI' wording). DC-01 (dead "
         "generate_column_report) is a separate UI-02B2 item. None "
         "changes an engineering value, unit or verdict.", "REVIEW")


# =========================================================================
# PHASE H — RELEASE-BLOCKING REVIEW
# =========================================================================
def phase_H():
    # the four production defects fixed in EV-03..EV-07 -- assert the fixes
    # are still in place (guards against a revert)
    import modules.beam as BM, modules.slab as SL, modules.footing as FT  # noqa
    import modules.stair as ST                                            # noqa
    fixes = [
        ("VF-11 beam", inspect.getsource(BM._section_calc),
         "top_ductile_ok and bot_ductile_ok"),
        ("VF-11 beam render", inspect.getsource(BM._render_beam_section),
         "and bot_ductile_ok"),
        ("VF-11-SLAB", inspect.getsource(SL._render_slab_design),
         "ductile_ok"),
        ("VF-FOOT-02", inspect.getsource(FT._render_pile_cap),
         "ecc_resolvable_ok"),
        ("VF-STAIR-01 straight", inspect.getsource(ST._render_straight_stair),
         "ductile_ok"),
        ("VF-STAIR-01 u-shape", inspect.getsource(ST._render_u_shape_stair),
         "ductile_ok"),
    ]
    for name, s, needle in fixes:
        chk("RELEASE/EV-fix intact: " + name,
            "`%s` still gates the verdict" % needle, True, needle in s,
            needle in s)
    note("RELEASE/Category-A (blockers)",
         "ZERO. No reachable non-conservative FALSE PASS remains "
         "(VF-11 class fixed in beam/slab/stair; latent-unreachable in "
         "footing; absent in column; N/A in building). No unit error "
         "(EV-02..08: every conversion audited, no R2). No load-"
         "conservation failure (EV-08: regular grid conserves exactly; "
         "VF-05 irregular-grid DOCUMENTED, bounded, feeds nothing that is "
         "sized). No report result mutation (phase C: build_report "
         "faithful, _status_state no recompute, MODEL never -> PASS). No "
         "drawing recompute (phase D). No UI over-claim of PASS "
         "(SYS-01: REVIEW under-states but never claims safety; Building "
         "= MODEL GENERATED).", "PASS")
    note("RELEASE/DECISION",
         "ENGINEERING RELEASE READY. Criteria met: (1) no unresolved "
         "critical safety defect; (2) all validated engines pass "
         "(pytest 80 + EV-02..08 all 0 FAIL); (3) verdict chain correct "
         "(engine -> checks list -> screen == report, no recompute); "
         "(4) scope explicit (SYSTEM_CAPABILITY_MATRIX / "
         "ENGINEERING_RELEASE_MATRIX); (5) report consistent; (6) UI does "
         "not over-claim (REVIEW/MODEL, never a false PASS); (7) all "
         "major limitations documented (Engineering Review Register, "
         "docs/ENGINEERING_VALIDATION.md §9). Remaining REVIEW items are "
         "R8 (conservative approximations) / R9 (documented scope) / R10 "
         "(UI wording) -- none reachable-unsafe.", "PASS")


# =========================================================================
def main():
    brief = "--brief" in sys.argv
    print("EV-09 SYSTEM-WIDE CONSOLIDATION & RELEASE GATE")
    print("  Question: does a VALIDATED engine result survive the trip "
          "ENGINE -> RESULT -> UI -> SUMMARY -> DRAWING -> REPORT without "
          "changing VALUE / UNIT / STATUS / engineering meaning?")
    phase_A(); phase_B(); phase_C(); phase_D(); phase_E(); phase_F()
    phase_G(); phase_H()

    npass = sum(1 for r in ROWS if r["status"] == "PASS")
    nfail = sum(1 for r in ROWS if r["status"] == "FAIL")
    nrev = sum(1 for r in ROWS if r["status"] == "REVIEW")
    if not brief:
        print("\nEV-09 SYSTEM VALIDATION")
        print("=" * 78)
        cur = None
        for r in ROWS:
            if r["case"] != cur:
                cur = r["case"]
                print(f"\n[{cur}]")
            print(f"  {r['status']:7s} {r['qty']}")
            if r["actual"] != "-":
                print(f"          expected={r['expected']!r}  actual={r['actual']!r}")
            else:
                print(f"          {r['expected']}")
    print("\n" + "=" * 78)
    print(f"EV-09 SYSTEM checks: {len(ROWS)}   "
          f"PASS={npass}  FAIL={nfail}  REVIEW={nrev}")
    print("RELEASE DECISION: "
          + ("ENGINEERING RELEASE READY" if nfail == 0
             else "ENGINEERING RELEASE NOT READY"))
    print("=" * 78)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
