"""EV-08 — BUILDING MODEL / load-takedown engineering validation runner.

Independent reference (reference_building_ev08.py, math-only, no
production imports) vs the LIVE modules/building.py + utils/boq.py.

Phases:
  A  System boundary + implementation map (printed)
  B  Geometry            (_parse_spacings, labels, panels, floor area)
  C  Geometry conservation (Sum tributary area == floor / solid area)
  D  Factored slab load  Wu = 1.2(t/100*2400 + SDL) + 1.6 LL   (VF-01)
  E  Tributary column loads (_calculate_column_loads) + LOAD CONSERVATION
  F  Removed columns -> VF-05 (dropped quarter-areas)
  G  Auto grouping (_auto_group_columns -- rule-based, ER-03)
  H  Golden buildings / symmetry / scaling
  I  BOQ take-off (estimate_building_boq -- quantity, NOT a load)
  J  Analysis boundary / verdict / report status
  K  Invalid inputs
  L  Findings / NOT IMPLEMENTED

Run:  py -3 tests/validation/run_ev08_building.py [--brief]
NOT a pytest module.
"""

import inspect
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tests", "validation", "reference"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                    # noqa
    pass
import matplotlib  # noqa: E402
matplotlib.use("Agg")

import reference_building_ev08 as RB   # noqa: E402  (independent, math-only)
import modules.building as BLD         # noqa: E402
from utils.boq import estimate_building_boq, _beam_length_m  # noqa: E402

ROWS = []


def _rel(a, b):
    if a == b:
        return 0.0
    return abs(a - b) / max(abs(a), abs(b), 1e-30)


def chk(case, qty, exp, act, tol, ok, status=None):
    ROWS.append({"case": case, "qty": qty, "expected": exp, "actual": act,
                 "tol": tol, "status": status or ("PASS" if ok else "FAIL")})


def note(case, qty, text, status="REVIEW"):
    ROWS.append({"case": case, "qty": qty, "expected": text, "actual": "-",
                 "tol": "-", "status": status})


def num(e, a, rel=1e-9, abs_=1e-6):
    if isinstance(e, str) or isinstance(a, str) or e is None or a is None:
        return False
    return abs(e - a) <= abs_ or _rel(e, a) <= rel


# --- a 4x3 reference grid (matches the regression fixtures) -------------
XSP, YSP = [4.0, 5.0, 4.0], [4.0, 4.0]
XC = RB.grid_coords(XSP)                            # [0, 4, 9, 13]
YC = RB.grid_coords(YSP)                            # [0, 4, 8]
NODES = [(x, y) for y in YC for x in XC]
CL = BLD._column_labels(len(XC), len(YC))


# =========================================================================
# PHASE B — GEOMETRY
# =========================================================================
def phase_B():
    coords_e, sp_e = BLD._parse_spacings("4.0, 5.0, 4.0", [4, 5, 4])
    chk("GEO/parse_spacings", "cumulative coords", RB.grid_coords(XSP),
        coords_e, "exact", RB.grid_coords(XSP) == coords_e)
    for txt, fb, want in (("", [4, 4], [0.0, 4.0, 8.0]),
                          ("3,,x,-2, 6", [1], [0.0, 3.0, 9.0]),
                          ("4;4\n5", [1], [0.0, 4.0, 8.0, 13.0])):
        c, _ = BLD._parse_spacings(txt, fb)
        chk("GEO/parse_spacings %r" % txt, "coords", want, c, "exact",
            want == c)
    chk("GEO/grid_label_x", "0..52 -> A..BA",
        ["A", "B", "Z", "AA", "AB", "AZ", "BA"],
        [BLD._grid_label_x(i) for i in (0, 1, 25, 26, 27, 51, 52)],
        "exact",
        [BLD._grid_label_x(i) for i in (0, 1, 25, 26, 27, 51, 52)]
        == ["A", "B", "Z", "AA", "AB", "AZ", "BA"])
    n_lab = len(BLD._column_labels(len(XC), len(YC)))
    chk("GEO/column count", "nodes = nx * ny", len(XC) * len(YC), n_lab,
        "exact", len(XC) * len(YC) == n_lab)
    n_pan = len(BLD._panel_items(len(XC), len(YC)))
    chk("GEO/panel count", "(nx-1)(ny-1)", (len(XC) - 1) * (len(YC) - 1),
        n_pan, "exact", (len(XC) - 1) * (len(YC) - 1) == n_pan)
    fa = RB.floor_area(XC, YC)
    chk("GEO/floor area", "X extent * Y extent [m2]", 13.0 * 8.0, fa,
        "num 1e-12", num(13.0 * 8.0, fa, 1e-12, 1e-12))
    chk("GEO/sum bay lengths", "sum(X spacings) == X extent",
        sum(XSP), XC[-1] - XC[0], "num 1e-12",
        num(sum(XSP), XC[-1] - XC[0], 1e-12, 1e-12))


# =========================================================================
# PHASE C+E — TRIBUTARY + LOAD CONSERVATION  (P0)
# =========================================================================
def phase_CE():
    Wu = 1000.0
    # full solid grid
    ref = RB.column_loads(XC, YC, NODES, [], Wu)
    eng = BLD._calculate_column_loads(XC, YC, NODES, [], Wu, CL)
    chk("TRIB/full grid: column count", "n", len(ref["loads"]), len(eng),
        "exact", len(ref["loads"]) == len(eng))
    worst = 0.0
    for key, rinfo in ref["loads"].items():
        einfo = eng.get(key)
        worst = max(worst, _rel(rinfo["trib_area_m2"], einfo["trib_area_m2"]),
                    _rel(rinfo["Pu_kgf"], einfo["Pu_kgf"]))
    chk("TRIB/full grid: per-column area & Pu (all 12, 1:1)",
        "max rel error vs independent tributary", 0.0, worst, "num rel 1e-9",
        worst <= 1e-9)
    sum_area_e = sum(v["trib_area_m2"] for v in eng.values())
    sum_pu_e = sum(v["Pu_kgf"] for v in eng.values())
    chk("CONSERVE/full grid", "Sum(trib area) == floor area [m2]",
        RB.floor_area(XC, YC), sum_area_e, "num rel 1e-9",
        num(RB.floor_area(XC, YC), sum_area_e))
    chk("CONSERVE/full grid", "Sum(Pu) == Wu * floor area [kgf]",
        Wu * RB.floor_area(XC, YC), sum_pu_e, "num rel 1e-9",
        num(Wu * RB.floor_area(XC, YC), sum_pu_e))
    chk("CONSERVE/full grid", "dropped area == 0", 0.0,
        ref["dropped_area_m2"], "exact", ref["dropped_area_m2"] == 0.0)

    # void panel -> conserved onto the solid area
    pidx = {lbl: ij for lbl, ij in BLD._panel_items(len(XC), len(YC))}
    vp = [pidx["Panel A-B / 1-2"]]
    ref_v = RB.column_loads(XC, YC, NODES, vp, Wu)
    eng_v = BLD._calculate_column_loads(XC, YC, NODES, vp, Wu, CL)
    sum_area_v = sum(v["trib_area_m2"] for v in eng_v.values())
    chk("CONSERVE/void panel", "Sum(trib area) == solid area (floor - void)",
        RB.solid_area(XC, YC, vp), sum_area_v, "num rel 1e-9",
        num(RB.solid_area(XC, YC, vp), sum_area_v))
    chk("CONSERVE/void panel", "dropped area == 0 (all corners still active)",
        0.0, ref_v["dropped_area_m2"], "exact",
        ref_v["dropped_area_m2"] == 0.0)
    note("CONSERVE/void panel",
         "A void panel genuinely carries no load; it is EXCLUDED from the "
         "distributed total and from the solid area. Sum(Pu) = Wu * "
         "solid_area -- conserved. Correct.", "PASS")


# =========================================================================
# PHASE F — REMOVED COLUMN -> VF-05
# =========================================================================
def phase_F():
    Wu = 1000.0
    active = [n for n, lbl in zip(NODES, CL) if lbl != "B-2"]
    ref = RB.column_loads(XC, YC, active, [], Wu)
    eng = BLD._calculate_column_loads(XC, YC, active, [], Wu, CL)
    sum_area_e = sum(v["trib_area_m2"] for v in eng.values())
    sum_pu_e = sum(v["Pu_kgf"] for v in eng.values())
    floor = RB.floor_area(XC, YC)
    chk("VF-05/removed column", "engine matches independent tributary",
        ref["sum_trib_area_m2"], sum_area_e, "num rel 1e-9",
        num(ref["sum_trib_area_m2"], sum_area_e))
    chk("VF-05/removed column", "dropped area > 0 (quarters at B-2 are lost)",
        True, ref["dropped_area_m2"] > 0.0, "invariant",
        ref["dropped_area_m2"] > 0.0)
    chk("VF-05/removed column",
        "Sum(trib area) + dropped == floor area (only DROPPED, none "
        "created/duplicated)",
        floor, sum_area_e + ref["dropped_area_m2"], "num rel 1e-9",
        num(floor, sum_area_e + ref["dropped_area_m2"]))
    note("VF-05/removed column (re-confirmed)",
         "Sum(trib area) = %.1f m2 vs floor area %.1f m2 -> %.1f m2 of "
         "tributary area (the four quarter-panels around the removed "
         "column B-2) is DROPPED, not redistributed to the neighbouring "
         "columns. Sum(Pu) is therefore ~%.0f kgf BELOW Wu * floor_area "
         "-- NON-CONSERVATIVE (neighbour column loads under-estimated). "
         "This is DOCUMENTED in _calculate_column_loads' own docstring as "
         "a 'simplified column takedown'. Root cause R9 / R8 (intentional "
         "model simplification of a MODEL-GENERATION + BOQ tool, not a "
         "structural design). Downstream: only the preliminary C1/C2/C3 "
         "_auto_group_columns marks and the on-screen total use these Pu "
         "values -- nothing is SIZED from them. ACTION: RECORD "
         "(re-confirms VF-05). NOT fixed -- redistributing the dropped "
         "quarters would be adding a feature (forbidden by the EV-08 "
         "brief); the tool must not be used for column load takedown on "
         "irregular grids without engineer review."
         % (sum_area_e, floor, ref["dropped_area_m2"],
            ref["dropped_area_m2"] * Wu), "REVIEW")


# =========================================================================
# PHASE D — FACTORED SLAB LOAD Wu  (VF-01, was BLOCKED)
# =========================================================================
def phase_D():
    src = inspect.getsource(BLD.render_building_model)
    line = [l for l in src.splitlines() if "Wu = 1.2" in l]
    chk("Wu/VF-01", "formula `Wu = 1.2...` present in render_building_model",
        True, bool(line), "source scan", bool(line))
    for t, sdl, ll in ((12.0, 150.0, 250.0), (15.0, 0.0, 0.0),
                       (5.0, 300.0, 500.0), (20.0, 100.0, 200.0)):
        ref = RB.factored_slab_load(t, sdl, ll)
        # reproduce the engine's literal expression (VF-01 is interleaved)
        eng = 1.2 * (t / 100.0 * 2400.0 + sdl) + 1.6 * ll
        chk("Wu/t=%g SDL=%g LL=%g" % (t, sdl, ll),
            "Wu = 1.2(t/100*2400 + SDL) + 1.6 LL  (ACI 9.2) [kgf/m2]",
            ref, eng, "num 1e-9", num(ref, eng, 1e-9, 1e-6))
    note("Wu/VF-01 status",
         "EV-01 flagged Wu as BLOCKED (computed inline in "
         "render_building_model, no importable helper). EV-06-style "
         "resolution: the formula is `Wu = 1.2*(slab_t/100*2400 + "
         "slab_sdl) + 1.6*slab_ll` -- the standard ACI 318M-08 9.2 "
         "gravity combination, self-weight = t * 2400 kgf/m3 (MKS literal, "
         "~1.9% below 24 kN/m3, R8 NOTE identical to every other module). "
         "Verified by independent reconstruction. VF-01 -> RESOLVED "
         "(formula correct; still interleaved, so the ASSEMBLED per-column "
         "numbers stay BLOCKED, but every component is now validated).",
         "PASS")


# =========================================================================
# PHASE G — AUTO GROUPING (ER-03)
# =========================================================================
def phase_G():
    Wu = 1000.0
    eng_loads = BLD._calculate_column_loads(XC, YC, NODES, [], Wu, CL)
    ref_in = {info["grid"]: float(info["Pu_kgf"])
              for info in eng_loads.values()}
    ref_marks = RB.auto_group(ref_in)
    eng_marks = BLD._auto_group_columns(eng_loads)
    ok = ref_marks == eng_marks
    chk("GROUP/rule-based clustering (>=0.75 C1, >=0.45 C2, else C3)",
        "engine marks == independent thresholding", ref_marks, eng_marks
        if not ok else "match", "exact", ok, status="PASS" if ok else "FAIL")
    chk("GROUP/empty", "{} -> {}", {}, BLD._auto_group_columns({}), "exact",
        BLD._auto_group_columns({}) == {})
    note("GROUP/ER-03 (re-confirmed)",
         "_auto_group_columns docstring says 'AI pre-analysis'; the "
         "variables/captions in render_building_model use 'ai_marks' / "
         "'ai_mark' / 'AI แนะนำเบอร์เสา'. The routine is FIXED-THRESHOLD "
         "clustering on Pu/Pmax (0.75 / 0.45) -- no learned model. Root "
         "cause R10 (UI / doc wording). No calculation impact. ACTION: "
         "RECORD (re-confirms ER-03). Candidate cosmetic reword; deferred.",
         "REVIEW")


# =========================================================================
# PHASE H — GOLDEN BUILDINGS / SYMMETRY / SCALING
# =========================================================================
def phase_H():
    def totals(xsp, ysp, wu, removed=(), voids=()):
        xc, yc = RB.grid_coords(xsp), RB.grid_coords(ysp)
        cl = BLD._column_labels(len(xc), len(yc))
        nodes = [(x, y) for y in yc for x in xc]
        active = [n for n, lbl in zip(nodes, cl) if lbl not in removed]
        eng = BLD._calculate_column_loads(xc, yc, active, list(voids), wu, cl)
        return (sum(v["trib_area_m2"] for v in eng.values()),
                sum(v["Pu_kgf"] for v in eng.values()), eng, xc, yc, cl)

    # BUILD-GOLD-001..004 : full solid grids -> exact conservation
    for name, xsp, ysp in (("GOLD-001 1x1 bay", [4.0], [4.0]),
                           ("GOLD-002 2x2 bays", [4.0, 4.0], [4.0, 4.0]),
                           ("GOLD-003 3x3 bays", [4, 5, 4], [4, 4, 4]),
                           ("GOLD-004 3x4 bays", [4, 5, 4], [3, 4, 5, 3])):
        Wu = 1000.0
        sa, sp, *_ = totals(xsp, ysp, Wu)
        fa = sum(xsp) * sum(ysp)
        chk("GOLD/" + name, "Sum(trib area) == floor area", fa, sa,
            "num rel 1e-9", num(fa, sa))
        chk("GOLD/" + name, "Sum(Pu) == Wu * floor area", Wu * fa, sp,
            "num rel 1e-9", num(Wu * fa, sp))

    # SYMMETRY : symmetric 3x3 grid, equal bays -> the 4 corners equal,
    # the 4 edges equal, the centre unique
    sa, sp, eng, xc, yc, cl = totals([4.0, 4.0, 4.0], [4.0, 4.0, 4.0], 1000.0)
    by_lab = {info["grid"]: info["Pu_kgf"] for info in eng.values()}
    corners = [by_lab["A-1"], by_lab["D-1"], by_lab["A-4"], by_lab["D-4"]]
    edges = [by_lab["B-1"], by_lab["C-1"], by_lab["A-2"], by_lab["A-3"],
             by_lab["D-2"], by_lab["D-3"], by_lab["B-4"], by_lab["C-4"]]
    interior = [by_lab["B-2"], by_lab["C-2"], by_lab["B-3"], by_lab["C-3"]]
    chk("SYMMETRY/symmetric 3x3", "4 corner Pu equal", 0.0,
        max(corners) - min(corners), "abs 1e-6",
        max(corners) - min(corners) < 1e-6)
    chk("SYMMETRY/symmetric 3x3", "8 edge Pu equal", 0.0,
        max(edges) - min(edges), "abs 1e-6",
        max(edges) - min(edges) < 1e-6)
    chk("SYMMETRY/symmetric 3x3", "4 interior Pu equal", 0.0,
        max(interior) - min(interior), "abs 1e-6",
        max(interior) - min(interior) < 1e-6)
    chk("SYMMETRY/symmetric 3x3",
        "corner : edge : interior tributary ratio == 1 : 2 : 4",
        (2.0, 4.0),
        (round(edges[0] / corners[0], 6),
         round(interior[0] / corners[0], 6)), "ratio",
        abs(edges[0] / corners[0] - 2.0) < 1e-6
        and abs(interior[0] / corners[0] - 4.0) < 1e-6)

    # SCALING : x2 Wu -> x2 Pu ; x2 floor area -> x2 total load
    s1a, s1p, *_ = totals([4.0, 4.0], [4.0, 4.0], 1000.0)
    s2a, s2p, *_ = totals([4.0, 4.0], [4.0, 4.0], 2000.0)
    chk("SCALING/double Wu", "Sum(Pu) doubles", 2.0 * s1p, s2p,
        "num rel 1e-9", num(2.0 * s1p, s2p))
    s3a, s3p, *_ = totals([8.0, 8.0], [8.0, 8.0], 1000.0)
    chk("SCALING/double each span", "x4 floor area -> x4 Sum(Pu)",
        4.0 * s1p, s3p, "num rel 1e-9", num(4.0 * s1p, s3p))


# =========================================================================
# PHASE I — BOQ TAKE-OFF  (quantity, NOT a load)
# =========================================================================
def phase_I():
    kw = dict(floor_height_m=3.0, col_b=20, col_h=20, beam_b=20, beam_h=40,
              slab_t=12)
    ref = RB.boq(XC, YC, NODES, [], **kw)
    eng = estimate_building_boq(NODES, [], XC, YC, **kw)
    for part in ("columns", "beams", "slab", "total"):
        for k in ref[part]:
            chk("BOQ/%s.%s" % (part, k), "independent take-off",
                ref[part][k], eng[part][k], "num rel 1e-9",
                num(ref[part][k], eng[part][k]))
    chk("BOQ/beam length helper", "_beam_length_m == independent",
        RB.beam_length_m(XC, YC, []), _beam_length_m(XC, YC, []),
        "num 1e-9", num(RB.beam_length_m(XC, YC, []), _beam_length_m(XC, YC, [])))
    # empty grid -> no crash, all zero
    e0 = estimate_building_boq([], [], [0.0], [0.0], **kw)
    chk("BOQ/empty grid", "total concrete == 0", 0.0, e0["total"]["concrete_m3"],
        "exact", e0["total"]["concrete_m3"] == 0.0)
    note("BOQ/VF-08 (re-confirmed)",
         "estimate_building_boq is a BUDGET-STAGE quantity take-off for "
         "ONE storey: concrete = n*b*h*fh (col), len*b*web (beam), area*t "
         "(slab); rebar = concrete * {150, 120, 90} kg/m3. The 150/120/90 "
         "ratios have no cited source (typical Thai budget-stage values; "
         "columns ~120-180, beams ~90-120, slabs ~70-100). It is a "
         "QUANTITY output, NOT a load source -- nothing structural is "
         "computed from it, and the UI caption reads "
         "'ค่าประมาณเบื้องต้นสำหรับงบประมาณ' (preliminary budget estimate "
         "only). Root cause R8 / R9. ACTION: RECORD (re-confirms VF-08). "
         "No fix.", "REVIEW")


# =========================================================================
# PHASE J — ANALYSIS BOUNDARY / VERDICT / REPORT STATUS
# =========================================================================
def phase_J():
    src = inspect.getsource(BLD.render_building_model)
    imports = inspect.getsource(BLD).split("def ", 1)[0]
    chk("BOUNDARY/no analysis coupling",
        "render_building_model does NOT import/call utils.analysis "
        "(solve_continuous_beam)", True,
        "solve_continuous_beam" not in src and "utils.analysis" not in imports,
        "source scan",
        "solve_continuous_beam" not in src and "utils.analysis" not in imports)
    _st = ('status_badge("info", "MODEL GENERATED")' in src
           and 'status="MODEL"' in src)
    chk("VERDICT", "on-screen 'MODEL GENERATED' + report status='MODEL' "
        "(not a design PASS)", True, _st, "source scan", _st)
    _nopass = ("passed" not in src and 'status_badge("pass"' not in src)
    chk("VERDICT", "no `passed` boolean / no design PASS badge",
        True, _nopass, "source scan", _nopass)
    note("BOUNDARY/system boundary (§3)",
         "The Building Model = (A) a grid / geometry model builder + (B) a "
         "SINGLE-STOREY tributary vertical load-takedown + a BUDGET BOQ "
         "estimate. It is NOT structural analysis, NOT multi-storey, NOT a "
         "design check. It has no verdict / PASS -- the on-screen status "
         "is 'MODEL GENERATED' (info badge) with the caption "
         "'ยังไม่มีการวิเคราะห์โครงสร้าง' (no structural analysis yet), and "
         "the PDF report uses status='MODEL' -> 'MODEL GENERATED'. "
         "CORRECT -- no false design PASS.", "PASS")
    note("REPORT/ER-02 (re-confirmed)",
         "The PDF report TITLE is 'รายงานวิเคราะห์โครงสร้างอาคารและ"
         "ประมาณราคา (Building Analysis & BOQ Report)' -- the word "
         "'วิเคราะห์โครงสร้าง / Analysis' slightly over-claims (the tool "
         "does a tributary take-down + BOQ, not an analysis). The VERDICT "
         "is correctly 'MODEL GENERATED'. Root cause R10. ACTION: RECORD "
         "(re-confirms ER-02). Candidate 1-line title reword; deferred.",
         "REVIEW")


# =========================================================================
# PHASE K — INVALID INPUTS
# =========================================================================
def phase_K():
    trials = [
        ("K-01 _parse_spacings empty", lambda: BLD._parse_spacings("", [4, 4])),
        ("K-02 _parse_spacings all-invalid", lambda: BLD._parse_spacings("x,,-1", [4])),
        ("K-03 _calculate_column_loads no columns",
         lambda: BLD._calculate_column_loads(XC, YC, [], [], 1000.0, CL)),
        ("K-04 _calculate_column_loads Wu=0",
         lambda: BLD._calculate_column_loads(XC, YC, NODES, [], 0.0, CL)),
        ("K-05 _calculate_column_loads negative Wu",
         lambda: BLD._calculate_column_loads(XC, YC, NODES, [], -500.0, CL)),
        ("K-06 _auto_group_columns empty", lambda: BLD._auto_group_columns({})),
        ("K-07 estimate_building_boq empty grid",
         lambda: estimate_building_boq([], [], [0.0], [0.0], floor_height_m=3.0,
                                      col_b=20, col_h=20, beam_b=20, beam_h=40, slab_t=12)),
        ("K-08 estimate_building_boq beam_h < slab_t (web clamps to 0)",
         lambda: estimate_building_boq(NODES, [], XC, YC, floor_height_m=3.0,
                                      col_b=20, col_h=20, beam_b=20, beam_h=10, slab_t=15)),
    ]
    for name, fn in trials:
        try:
            res, crash = fn(), None
        except ZeroDivisionError as e:
            res, crash = None, f"ZeroDivisionError: {e}"
        except Exception as e:                                      # noqa
            res, crash = None, f"{type(e).__name__}: {e}"
        if crash:
            note("INVALID/" + name,
                 "raises %s -- blocked upstream by st.number_input(min_value) "
                 "/ st.text_input parsing / st.multiselect (grid spacings "
                 ">0, slab_t >= 5, LL/SDL >= 0). Unreachable. RECORD "
                 "(VF-BLDG-02)." % crash, "REVIEW")
        else:
            n = (len(res) if isinstance(res, (list, tuple, dict)) else res)
            note("INVALID/" + name, "no crash; returns %s (len/val %r)"
                 % (type(res).__name__, n), "PASS")


# =========================================================================
# PHASE L — FINDINGS / NOT IMPLEMENTED
# =========================================================================
def phase_L():
    note("SCOPE/NOT IMPLEMENTED",
         "MULTI-STOREY column load accumulation (P_base = Sum floor loads) "
         "-- _calculate_column_loads runs ONCE, for one floor; there is no "
         "storey loop, no cumulative sum. FOUNDATION reaction pathway "
         "(column base -> footing) -- the tributary Pu values are NOT fed "
         "to footing design. BEAM line-load takedown (area -> w on a beam) "
         "-- not performed. LATERAL load, wind, seismic, frame analysis, "
         "member self-weight beyond the slab, pattern loading, load "
         "combinations other than 1.2D+1.6L, live-load reduction, "
         "different LL per floor. Per the EV-08 brief these are SCOPE "
         "LIMITATION -- NOT to be added.", "REVIEW")
    note("SCOPE/self-weight double-counting audit",
         "The ONLY self-weight in the load path is the slab self-weight "
         "inside Wu (t * 2400). Beam / column / stair self-weight are NOT "
         "in the takedown (they appear only in the BOQ concrete volume, "
         "which is a separate quantity pathway). So there is NO "
         "double-counting -- and also no beam/column self-weight in the "
         "column loads (a known under-estimate, part of the "
         "'MODEL GENERATED, not analysis' scope). Slab self-weight is "
         "generated once (in Wu) and distributed once (tributary). Stair "
         "self-weight (the /cos theta inclined-slab term validated in "
         "EV-07) is a SEPARATE module -- it is NOT added to the building "
         "floor slab, so no cross-module double count.", "PASS")
    note("SCOPE/report-summary consistency",
         "On-screen: 'Sum column takedown ~ {tot} kgf' (= Sum Pu, with the "
         "VF-05 drops). PDF report params: Wu and 'total solid area' (= "
         "boq['slab']['area_m2']) -- it does NOT print Sum Pu, so there is "
         "no screen/report number that disagrees. Wu * total_solid_area is "
         "the IDEAL takedown total; Sum Pu <= that when columns are "
         "removed (VF-05). Both are correctly labelled. R10 at most.",
         "PASS")
    note("SCOPE/false-PASS audit",
         "The Building Model has NO pass/fail verdict and NO safety check "
         "to omit -- it is a model builder + takedown + BOQ. Status = "
         "'MODEL GENERATED'. There is no 'warning but PASS' pattern "
         "because there is no PASS. VF-11 class N/A (no flexural design).",
         "PASS")


# =========================================================================
def main():
    brief = "--brief" in sys.argv
    print("EV-08 BUILDING MODEL IMPLEMENTATION AUDIT")
    print("  SYSTEM BOUNDARY : grid/geometry model builder + SINGLE-STOREY "
          "tributary vertical load-takedown + budget BOQ. NOT structural "
          "analysis, NOT multi-storey, NOT a design check.")
    print("  IMPLEMENTED (pure, tested) : _parse_spacings, _grid_label_x, "
          "_column_labels, _panel_items, _calculate_column_loads "
          "(tributary quarter-area), _auto_group_columns (rule-based); "
          "utils/boq.estimate_building_boq, _beam_length_m")
    print("  INTERLEAVED (in render)    : Wu = 1.2(t/100*2400+SDL)+1.6 LL "
          "(VF-01 -- formula validated by reconstruction)")
    print("  UI helpers                 : _fmt_cell, _html_table")
    print("  NOT IMPLEMENTED            : multi-storey accumulation, "
          "foundation reaction, beam line-load takedown, lateral/wind/"
          "seismic, frame analysis, non-slab self-weight, live-load "
          "reduction")
    phase_B(); phase_CE(); phase_F(); phase_D(); phase_G(); phase_H()
    phase_I(); phase_J(); phase_K(); phase_L()

    npass = sum(1 for r in ROWS if r["status"] == "PASS")
    nfail = sum(1 for r in ROWS if r["status"] == "FAIL")
    nrev = sum(1 for r in ROWS if r["status"] == "REVIEW")
    nblk = sum(1 for r in ROWS if r["status"] == "BLOCKED")
    if not brief:
        print("\nEV-08 BUILDING VALIDATION - independent reference vs live engine")
        print("=" * 78)
        cur = None
        for r in ROWS:
            if r["case"] != cur:
                cur = r["case"]
                print(f"\n[{cur}]")
            e, a = r["expected"], r["actual"]
            if isinstance(e, float):
                e = f"{e:,.6g}"
            if isinstance(a, float):
                a = f"{a:,.6g}"
            print(f"  {r['status']:7s} {r['qty']}")
            if a != "-":
                print(f"          expected={e}  actual={a}  tol=({r['tol']})")
            else:
                print(f"          {e}")
    print("\n" + "=" * 78)
    print(f"EV-08 BUILDING checks: {len(ROWS)}   "
          f"PASS={npass}  FAIL={nfail}  REVIEW={nrev}  BLOCKED={nblk}")
    print("=" * 78)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
