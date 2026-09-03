"""Regression golden values — utils/boq.py : estimate_building_boq.

Tributary-area take-off.  Golden values captured from the current
implementation.
"""

from _helpers import approx
from utils.boq import estimate_building_boq, _beam_length_m
from modules.building import _column_labels, _panel_items

# 4 x 3 grid : X = 0,4,9,13  ·  Y = 0,4,8
XC = [0.0, 4.0, 9.0, 13.0]
YC = [0.0, 4.0, 8.0]
NODES = [(x, y) for y in YC for x in XC]


def test_full_solid_grid():
    r = estimate_building_boq(NODES, [], XC, YC, floor_height_m=3.0,
                              col_b=20, col_h=20, beam_b=20, beam_h=40,
                              slab_t=12)
    assert r["columns"] == {
        "count": 12,
        "concrete_m3": approx(1.44),
        "formwork_m2": approx(28.8),
        "rebar_kg": approx(216.0),
    }
    assert r["beams"] == {
        "length_m": approx(71.0),
        "concrete_m3": approx(3.976),
        "formwork_m2": approx(39.76),
        "rebar_kg": approx(477.12),
    }
    assert r["slab"] == {
        "area_m2": approx(104.0),
        "concrete_m3": approx(12.48),
        "formwork_m2": approx(104.0),
        "rebar_kg": approx(1123.2),
    }
    assert r["total"] == {
        "concrete_m3": approx(17.896),
        "formwork_m2": approx(172.56),
        "rebar_kg": approx(1816.32),
    }
    assert r["ratios"] == {
        "column_kg_per_m3": 150.0,
        "beam_kg_per_m3": 120.0,
        "slab_kg_per_m3": 90.0,
    }
    assert len(r["table"]) == 4
    assert r["table"][-1] == {
        "หมวดงาน": "รวมทั้งหมด (Grand Total)",
        "ปริมาตรคอนกรีต (ลบ.ม.)": approx(17.9),
        "พื้นที่ไม้แบบ (ตร.ม.)": approx(172.6),
        "น้ำหนักเหล็กเสริม (กก.)": approx(1816.0),
    }


def test_removed_column_plus_void_panel():
    cl = _column_labels(len(XC), len(YC))
    pidx = {lbl: ij for lbl, ij in _panel_items(len(XC), len(YC))}
    active = [n for n, lbl in zip(NODES, cl) if lbl != "B-2"]
    r = estimate_building_boq(active, [pidx["Panel A-B / 1-2"]], XC, YC,
                              floor_height_m=3.5, col_b=25, col_h=25,
                              beam_b=20, beam_h=45, slab_t=15)
    assert r["columns"]["count"] == 11
    assert r["columns"]["concrete_m3"] == approx(2.40625)
    assert r["columns"]["formwork_m2"] == approx(38.5)
    assert r["columns"]["rebar_kg"] == approx(360.9375)
    assert r["beams"]["length_m"] == approx(63.0)
    assert r["beams"]["concrete_m3"] == approx(3.78)
    assert r["beams"]["formwork_m2"] == approx(37.8)
    assert r["beams"]["rebar_kg"] == approx(453.6)
    assert r["slab"]["area_m2"] == approx(88.0)
    assert r["slab"]["concrete_m3"] == approx(13.2)
    assert r["slab"]["rebar_kg"] == approx(1188.0)
    assert r["total"]["concrete_m3"] == approx(19.38625)
    assert r["total"]["formwork_m2"] == approx(164.3)
    assert r["total"]["rebar_kg"] == approx(2002.5375)


def test_beam_length_helper():
    assert _beam_length_m(XC, YC, []) == approx(71.0)
    assert _beam_length_m(XC, YC, [(0, 0)]) == approx(63.0)


def test_empty_grid_no_crash():
    r = estimate_building_boq([], [], [0.0], [0.0], floor_height_m=3.0,
                              col_b=20, col_h=20, beam_b=20, beam_h=40,
                              slab_t=12)
    assert r["columns"]["count"] == 0
    assert r["total"]["concrete_m3"] == approx(0.0)
    assert r["total"]["formwork_m2"] == approx(0.0)
    assert r["total"]["rebar_kg"] == approx(0.0)
