"""Regression golden values — modules/building.py pure helpers.

Grid parsing, labels, panels, tributary-area load takedown, auto grouping.
No Streamlit widgets are exercised.
"""

from _helpers import approx
import modules.building as B

XC = [0.0, 4.0, 9.0, 13.0]
YC = [0.0, 4.0, 8.0]
NODES = [(x, y) for y in YC for x in XC]
CL = B._column_labels(4, 3)


# --- grid parsing -------------------------------------------------------
def test_parse_spacings_representative():
    coords, spac = B._parse_spacings("4.0, 5.0, 4.0", [4, 5, 4])
    assert coords == [0.0, 4.0, 9.0, 13.0]
    assert spac == [4.0, 5.0, 4.0]


def test_parse_spacings_empty_falls_back():
    coords, spac = B._parse_spacings("", [4, 4])
    assert coords == [0.0, 4.0, 8.0]
    assert spac == [4.0, 4.0]


def test_parse_spacings_drops_invalid_and_non_positive():
    coords, spac = B._parse_spacings("3,,x,-2, 6", [1])
    assert coords == [0.0, 3.0, 9.0]
    assert spac == [3.0, 6.0]


def test_parse_spacings_accepts_semicolon_and_newline():
    coords, spac = B._parse_spacings("4;4\n5", [1])
    assert coords == [0.0, 4.0, 8.0, 13.0]
    assert spac == [4.0, 4.0, 5.0]


# --- labels / panels ------------------------------------------------
def test_grid_label_x():
    assert [B._grid_label_x(i) for i in (0, 1, 25, 26, 27, 51, 52)] == \
        ["A", "B", "Z", "AA", "AB", "AZ", "BA"]


def test_column_labels():
    assert B._column_labels(4, 3) == [
        "A-1", "B-1", "C-1", "D-1",
        "A-2", "B-2", "C-2", "D-2",
        "A-3", "B-3", "C-3", "D-3",
    ]


def test_panel_items():
    assert B._panel_items(4, 3) == [
        ("Panel A-B / 1-2", (0, 0)),
        ("Panel B-C / 1-2", (1, 0)),
        ("Panel C-D / 1-2", (2, 0)),
        ("Panel A-B / 2-3", (0, 1)),
        ("Panel B-C / 2-3", (1, 1)),
        ("Panel C-D / 2-3", (2, 1)),
    ]


# --- load takedown ------------------------------------------------
def test_column_loads_full_grid():
    loads = B._calculate_column_loads(XC, YC, NODES, [], 1000.0, CL)
    assert len(loads) == 12
    assert loads[(0.0, 0.0)] == {
        "grid": "A-1", "trib_area_m2": approx(4.0), "Pu_kgf": approx(4000.0)}
    assert loads[(9.0, 4.0)] == {
        "grid": "C-2", "trib_area_m2": approx(18.0), "Pu_kgf": approx(18000.0)}
    assert sum(v["trib_area_m2"] for v in loads.values()) == approx(104.0)
    assert sum(v["Pu_kgf"] for v in loads.values()) == approx(104000.0)


def test_column_loads_removed_and_void():
    pidx = {lbl: ij for lbl, ij in B._panel_items(4, 3)}
    active = [n for n, lbl in zip(NODES, CL) if lbl != "B-2"]
    loads = B._calculate_column_loads(
        XC, YC, active, [pidx["Panel A-B / 1-2"]], 1000.0, CL)
    assert len(loads) == 11
    assert (4.0, 4.0) not in loads                      # B-2 removed
    assert sum(v["trib_area_m2"] for v in loads.values()) == approx(74.0)


# --- auto grouping ------------------------------------------------
def test_auto_group_columns():
    loads = B._calculate_column_loads(XC, YC, NODES, [], 1000.0, CL)
    assert B._auto_group_columns(loads) == {
        "B-2": "C1", "D-3": "C3", "C-1": "C2", "B-1": "C2",
        "A-2": "C3", "D-2": "C3", "A-1": "C3", "D-1": "C3",
        "C-3": "C2", "B-3": "C2", "A-3": "C3", "C-2": "C1",
    }


def test_auto_group_columns_empty():
    assert B._auto_group_columns({}) == {}


# --- building levels (floor count + heights -> elevations) ---------
import pytest  # noqa: E402


def test_building_levels_single_floor():
    levels, total = B._building_levels(1, [3.50])
    assert levels == [{"floor": 1, "height": 3.50, "elevation": 3.50}]
    assert total == approx(3.50)


def test_building_levels_three_floors_representative():
    levels, total = B._building_levels(3, [3.50, 3.20, 3.20])
    assert [lv["floor"] for lv in levels] == [1, 2, 3]
    assert [lv["height"] for lv in levels] == approx([3.50, 3.20, 3.20])
    assert [lv["elevation"] for lv in levels] == approx([3.50, 6.70, 9.90])
    assert total == approx(9.90)


def test_building_levels_different_heights():
    levels, total = B._building_levels(3, [4.00, 3.50, 3.00])
    assert [lv["elevation"] for lv in levels] == approx([4.00, 7.50, 10.50])
    assert total == approx(10.50)


def test_building_levels_invalid_floor_count_raises():
    for bad in (0, -1):
        with pytest.raises(ValueError):
            B._building_levels(bad, [])


def test_building_levels_invalid_height_raises():
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            B._building_levels(2, [3.20, bad])
    # count / heights length mismatch is also rejected
    with pytest.raises(ValueError):
        B._building_levels(3, [3.0, 3.0])


def test_building_levels_missing_data_is_safe():
    # an existing building_grid stash saved before this feature has no
    # "levels" key -> readers must tolerate its absence, no crash
    legacy_stash = {"x_coords": [0.0, 4.0], "slab": {"t_cm": 12.0}}
    assert legacy_stash.get("levels") is None
    # and the helper still builds defaults for a fresh model, accepting
    # an int height list and a float storey count
    levels, total = B._building_levels(3.0, [3, 3, 3])
    assert [lv["floor"] for lv in levels] == [1, 2, 3]
    assert total == approx(9.0)


# --- multi-level stack: Foundation + Level 0 + Floor 1..N ----------
def _ids(stack):
    return [lv["id"] for lv in stack]


def test_level_stack_three_floors():
    stack, total = B._building_level_stack(3, [3.50, 3.20, 3.20])
    assert _ids(stack) == ["foundation", "level_0",
                           "floor_1", "floor_2", "floor_3"]
    floors = [lv for lv in stack if lv["kind"] == "floor"]
    assert [lv["elevation"] for lv in floors] == approx([3.50, 6.70, 9.90])
    assert [lv["height"] for lv in floors] == approx([3.50, 3.20, 3.20])
    assert [(lv["z_bottom"], lv["z_top"]) for lv in floors] == \
        [approx((0.0, 3.50)), approx((3.50, 6.70)), approx((6.70, 9.90))]
    assert total == approx(9.90)
    # 2D selector: Foundation + every storey, NO Level 0, NO Floor 4
    assert B._floor_view_options(stack) == [
        ("foundation", "ฐานราก (Foundation)"),
        ("floor_1", "ชั้น 1"), ("floor_2", "ชั้น 2"), ("floor_3", "ชั้น 3"),
    ]


def test_level_stack_unequal_heights():
    stack, _ = B._building_level_stack(3, [4.00, 3.50, 3.00])
    floors = [lv for lv in stack if lv["kind"] == "floor"]
    assert [lv["elevation"] for lv in floors] == approx([4.00, 7.50, 10.50])


def test_level_stack_five_floors_selector():
    stack, _ = B._building_level_stack(5, [3.2, 3.2, 3.2, 3.2, 3.2])
    assert [name for _, name in B._floor_view_options(stack)] == [
        "ฐานราก (Foundation)", "ชั้น 1", "ชั้น 2", "ชั้น 3", "ชั้น 4", "ชั้น 5"]


def test_level_stack_reduce_floors():
    stack, _ = B._building_level_stack(2, [3.50, 3.20])
    assert [oid for oid, _ in B._floor_view_options(stack)] == \
        ["foundation", "floor_1", "floor_2"]


def test_level_stack_top_elevation_for_3d():
    stack, total = B._building_level_stack(3, [3.50, 3.20, 3.20])
    top = max(lv["elevation"] for lv in stack if lv["kind"] == "floor")
    assert top == approx(9.90)
    assert total == approx(9.90)   # 3D geometry spans 0 .. 9.90, not 1 storey


def test_selected_level_is_view_only():
    stack, _ = B._building_level_stack(3, [3.50, 3.20, 3.20])
    sel = B._resolve_selected_level(stack, "floor_2")
    assert sel["name"] == "ชั้น 2"
    assert sel["elevation"] == approx(6.70)
    # resolving a view id does not mutate the stack
    before = [dict(lv) for lv in stack]
    B._resolve_selected_level(stack, "floor_1")
    assert [dict(lv) for lv in stack] == before
    # a stale selection (floor removed after reducing floor count) -> Floor 1
    assert B._resolve_selected_level(stack, "floor_9")["id"] == "floor_1"


def test_foundation_separate_from_floor_count():
    stack, _ = B._building_level_stack(3, [3.50, 3.20, 3.20])
    fnd = next(lv for lv in stack if lv["id"] == "foundation")
    assert fnd["floor_number"] is None and fnd["kind"] == "reference"
    # Foundation is NOT one of the storeys
    assert len([lv for lv in stack if lv["kind"] == "floor"]) == 3


def test_level_stack_foundation_reference_level():
    # a user-set foundation reference (may be negative) is carried, not
    # invented, and never changes the storey count / elevations
    stack, total = B._building_level_stack(
        2, [3.50, 3.20], foundation_elev=-1.50)
    fnd = next(lv for lv in stack if lv["id"] == "foundation")
    assert fnd["elevation"] == approx(-1.50)
    assert total == approx(6.70)
    assert [lv["elevation"] for lv in stack if lv["kind"] == "floor"] == \
        approx([3.50, 6.70])
    # default (no reference given) -> 0.00, no fabricated depth
    stack0, _ = B._building_level_stack(1, [3.50])
    assert next(lv for lv in stack0
                if lv["id"] == "foundation")["elevation"] == approx(0.0)


def test_level_stack_missing_data_is_safe():
    # legacy building_grid without a "level_stack" key -> readers tolerate it
    legacy = {"levels": {"number_of_floors": 2}}
    assert legacy["levels"].get("level_stack") is None
    assert legacy["levels"].get("foundation_elevation_m") is None
    # invalid inputs still raise the same Thai validation errors
    for bad_n in (0, -1):
        with pytest.raises(ValueError):
            B._building_level_stack(bad_n, [])
    with pytest.raises(ValueError):
        B._building_level_stack(2, [3.0, 0.0])


# --- column size + true-scale plan rectangle ---------------------
def test_column_size_representative():
    cs = B._column_size(0.30, 0.40)
    assert cs == {"width_m": 0.30, "length_m": 0.40}


def test_column_rectangle_true_scale():
    xmin, xmax, ymin, ymax = B._column_rectangle(5.00, 4.00, 0.30, 0.40)
    assert (xmin, xmax) == approx((4.85, 5.15))
    assert (ymin, ymax) == approx((3.80, 4.20))
    # width -> X extent, length -> Y extent (no axis swap)
    assert (xmax - xmin) == approx(0.30)
    assert (ymax - ymin) == approx(0.40)


def test_column_rectangle_square_stays_square():
    xmin, xmax, ymin, ymax = B._column_rectangle(0.0, 0.0, 0.30, 0.30)
    assert (xmax - xmin) == approx(ymax - ymin)          # 0.30 x 0.30


def test_column_rectangle_preserves_1_to_2_aspect():
    xmin, xmax, ymin, ymax = B._column_rectangle(0.0, 0.0, 0.30, 0.60)
    assert (ymax - ymin) / (xmax - xmin) == approx(2.0)


def test_column_size_invalid_width_raises():
    for bad in (0, -1):
        with pytest.raises(ValueError):
            B._column_size(bad, 0.30)


def test_column_size_invalid_length_raises():
    for bad in (0, -1):
        with pytest.raises(ValueError):
            B._column_size(0.30, bad)


def test_column_size_does_not_change_engineering():
    # the tributary load takedown does NOT take a column size — changing
    # the model column geometry cannot alter any structural result
    import inspect
    sig = inspect.signature(B._calculate_column_loads)
    assert not any("col" in p and "size" in p for p in sig.parameters)
    loads_a = B._calculate_column_loads(XC, YC, NODES, [], 1000.0, CL)
    loads_b = B._calculate_column_loads(XC, YC, NODES, [], 1000.0, CL)
    assert {k: v["Pu_kgf"] for k, v in loads_a.items()} == \
        {k: v["Pu_kgf"] for k, v in loads_b.items()}
    # _column_size / _column_rectangle produce only geometry, never a load
    cs1 = B._column_size(0.30, 0.30)
    cs2 = B._column_size(0.40, 0.50)
    assert set(cs1) == set(cs2) == {"width_m", "length_m"}


def test_floor_selector_resolves_after_column_size_added():
    # TEST 7 / TEST 9 — floor selection + Foundation are unaffected by the
    # new column-size feature
    stack, _ = B._building_level_stack(3, [3.50, 3.20, 3.20])
    assert B._resolve_selected_level(stack, "floor_2")["id"] == "floor_2"
    assert B._resolve_selected_level(stack, "floor_2")["elevation"] == \
        approx(6.70)
    fnd = next(lv for lv in stack if lv["id"] == "foundation")
    assert fnd["floor_number"] is None
    assert len([lv for lv in stack if lv["kind"] == "floor"]) == 3


# --- beam size + auto-generated beam geometry --------------------
_BXC = [0.0, 5.0, 10.0]
_BYC = [0.0, 4.0]
_BALL = [(x, y) for y in _BYC for x in _BXC]


def test_beam_size_valid():                                  # S-TEST 1
    assert B._beam_size(0.25, 0.50) == {"width_m": 0.25, "depth_m": 0.50}


def test_beam_size_invalid_width_rejected():                 # S-TEST 2
    for bad in (0, -1):
        with pytest.raises(ValueError):
            B._beam_size(bad, 0.50)


def test_beam_size_invalid_depth_rejected():                 # S-TEST 3
    for bad in (0, -1):
        with pytest.raises(ValueError):
            B._beam_size(0.25, bad)


def test_beam_rectangle_horizontal_width():                  # S-TEST 4
    poly = B._beam_rectangle(0.0, 0.0, 5.0, 0.0, 0.25)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    assert (max(xs) - min(xs)) == approx(5.00)   # length along X
    assert (max(ys) - min(ys)) == approx(0.25)   # true beam width across Y


def test_beam_rectangle_vertical_width():                    # S-TEST 5
    poly = B._beam_rectangle(0.0, 0.0, 0.0, 4.0, 0.25)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    assert (max(ys) - min(ys)) == approx(4.00)   # length along Y
    assert (max(xs) - min(xs)) == approx(0.25)   # true beam width across X


def test_beam_uses_model_coordinates():                      # S-TEST 6
    # centreline 5.00 m -> 10.00 m at y = 4.00, width 0.30
    poly = B._beam_rectangle(5.0, 4.0, 10.0, 4.0, 0.30)
    assert min(p[0] for p in poly) == approx(5.00)
    assert max(p[0] for p in poly) == approx(10.00)
    assert min(p[1] for p in poly) == approx(3.85)
    assert max(p[1] for p in poly) == approx(4.15)


def test_beams_generated_between_existing_columns():         # S-TEST 7 / 8
    beams = B._generate_beams(_BXC, _BYC, _BALL)
    # 2 grid rows x 2 spans  +  3 grid cols x 1 span  = 7
    assert len(beams) == 7
    assert {b["axis"] for b in beams} == {"x", "y"}
    # every beam's ends sit on real grid coordinates
    grid = {(round(x, 3), round(y, 3)) for x in _BXC for y in _BYC}
    for b in beams:
        assert (round(b["start"][0], 3), round(b["start"][1], 3)) in grid
        assert (round(b["end"][0], 3), round(b["end"][1], 3)) in grid


def test_no_beam_without_supporting_column():                # S-TEST 9 support
    partial = [xy for xy in _BALL if xy != (5.0, 0.0)]
    beams = B._generate_beams(_BXC, _BYC, partial)
    # the 3 segments touching the removed node are gone -> 7 - 3 = 4
    assert len(beams) == 4
    for b in beams:
        assert (5.0, 0.0) not in (tuple(b["start"]), tuple(b["end"]))


def test_beam_generation_deterministic_per_grid():           # S-TEST 8
    # the same grid + columns always yields the same beam set (shared
    # geometry — the storey selection only changes the VIEW)
    a = B._generate_beams(_BXC, _BYC, _BALL)
    b = B._generate_beams(_BXC, _BYC, _BALL)
    assert [x["id"] for x in a] == [x["id"] for x in b]


def test_beam_size_does_not_change_engineering():            # S-TEST 13
    import inspect
    sig = inspect.signature(B._calculate_column_loads)
    assert not any("beam" in p for p in sig.parameters)
    loads_a = B._calculate_column_loads(XC, YC, NODES, [], 1000.0, CL)
    loads_b = B._calculate_column_loads(XC, YC, NODES, [], 1000.0, CL)
    assert {k: v["Pu_kgf"] for k, v in loads_a.items()} == \
        {k: v["Pu_kgf"] for k, v in loads_b.items()}
    # beam-size helpers yield only geometry keys, never a load / capacity
    assert set(B._beam_size(0.2, 0.4)) == {"width_m", "depth_m"}


def test_column_and_grid_unchanged_by_beam_feature():        # S-TEST 10 / 11
    # column geometry helper still behaves exactly as before
    assert B._column_rectangle(5.0, 4.0, 0.30, 0.40) == \
        approx((4.85, 5.15, 3.80, 4.20))
    # grid parsing / labels untouched
    coords, spac = B._parse_spacings("4.0, 5.0, 4.0", [4, 5, 4])
    assert coords == [0.0, 4.0, 9.0, 13.0]
    assert B._column_labels(4, 3)[:4] == ["A-1", "B-1", "C-1", "D-1"]


# --- INPUT / MODEL / OUTPUT reorganization + Foundation Type -----
def test_foundation_type_options():
    ids = [i for i, _ in B.FOUNDATION_TYPES]
    assert ids == ["spread", "pile"]                 # order fixed
    for _id, label in B.FOUNDATION_TYPES:
        assert isinstance(label, str) and label      # every option labelled
    # default is the first option (spread) — matches st.selectbox default
    assert B.FOUNDATION_TYPES[0][0] == "spread"


def test_reorg_preserves_all_pure_helpers():
    # the section reshuffle is UI-only; every model-geometry helper the
    # sections rely on must still be importable and behave identically
    for name in ("_parse_spacings", "_column_labels", "_panel_items",
                 "_calculate_column_loads", "_auto_group_columns",
                 "_building_levels", "_building_level_stack",
                 "_floor_view_options", "_resolve_selected_level",
                 "_column_size", "_column_rectangle",
                 "_beam_size", "_beam_rectangle", "_generate_beams"):
        assert callable(getattr(B, name)), name
    # spot-check a couple end-to-end
    stack, tot = B._building_level_stack(3, [3.5, 3.2, 3.2])
    assert tot == approx(9.90)
    beams = B._generate_beams([0.0, 5.0], [0.0, 4.0],
                              [(0.0, 0.0), (5.0, 0.0), (0.0, 4.0)])
    assert len(beams) == 2          # A1-B1 (x) + A1-A2 (y); B1-B2 has no B2


# --- Additional (non-grid) Column -> Column beams ---------------
_ABN = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (0.0, 4.0), (10.0, 4.0)]
_ABL = ["A-1", "B-1", "C-1", "A-2", "C-2"]
_ABC = B._active_column_centers(_ABN, _ABL, _ABN)


def _mk(sid, eid, lvl="floor_1"):
    return {"id": "AB-01", "start_label": sid, "end_label": eid,
            "level_id": lvl, "width_m": 0.25, "depth_m": 0.50}


def test_additional_beam_column_centers_from_active():   # TEST 1 / 6
    assert _ABC["B-1"] == (5.0, 0.0) and _ABC["C-2"] == (10.0, 4.0)
    # a removed column is not offered
    part = B._active_column_centers(_ABN, _ABL,
                                    [xy for xy in _ABN if xy != (5.0, 0.0)])
    assert "B-1" not in part


def test_additional_beam_start_end_coords():             # TEST 2
    polys = B._additional_beam_polys([_mk("A-1", "C-1")], _ABC,
                                     "floor_1", 0.25)
    assert len(polys) == 1
    xs = [p[0] for p in polys[0]]
    assert min(xs) == approx(0.0) and max(xs) == approx(10.0)


def test_additional_beam_width_and_horizontal():         # TEST 3 / 4
    poly = B._additional_beam_polys([_mk("A-1", "C-1")], _ABC,
                                    "floor_1", 0.25)[0]
    ys = [p[1] for p in poly]
    assert (max(ys) - min(ys)) == approx(0.25)           # true beam width


def test_additional_beam_vertical():                     # TEST 5
    b = _mk("A-1", "A-2")
    b["width_m"] = 0.30                                  # per-beam stored width
    poly = B._additional_beam_polys([b], _ABC, "floor_1", 0.99)[0]
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    assert (max(xs) - min(xs)) == approx(0.30)           # width across X
    assert (max(ys) - min(ys)) == approx(4.00)           # length along Y


def test_additional_beam_non_grid_position():            # TEST 6
    # A-2 (0,4) -> C-2 (10,4): a beam on the y=4 line between end columns —
    # needs NO new grid line / coordinate
    poly = B._additional_beam_polys([_mk("A-2", "C-2")], _ABC,
                                    "floor_1", 0.25)[0]
    assert min(p[1] for p in poly) == approx(3.875)
    assert max(p[1] for p in poly) == approx(4.125)


def test_additional_beam_same_floor_ok():                # TEST 7
    ok, msg = B._validate_additional_beam("A-1", "B-1", "floor_1",
                                          "floor_1", [])
    assert ok and msg == ""


def test_additional_beam_different_floor_rejected():     # TEST 8
    ok, msg = B._validate_additional_beam("A-1", "B-1", "floor_1",
                                          "floor_2", [])
    assert not ok and "ชั้นเดียวกัน" in msg


def test_additional_beam_self_connection_rejected():     # TEST 9
    ok, msg = B._validate_additional_beam("A-1", "A-1", "floor_1",
                                          "floor_1", [])
    assert not ok and "คนละเสา" in msg


def test_additional_beam_duplicate_rejected():           # TEST 10
    existing = [B._beam_pair_key("C-1", "A-1")]           # C-1 -> A-1 added
    ok, msg = B._validate_additional_beam("A-1", "C-1", "floor_1",
                                          "floor_1", existing)   # A-1 -> C-1
    assert not ok and "อยู่แล้ว" in msg
    assert B._beam_pair_key("A-1", "C-1") == B._beam_pair_key("C-1", "A-1")


def test_additional_beam_delete_and_prune():             # TEST 11 / 26
    beams = [_mk("A-1", "B-1", "floor_1"),
             {"id": "AB-02", "start_label": "C-1", "end_label": "C-2",
              "level_id": "floor_3", "width_m": 0.25, "depth_m": 0.5}]
    # floors reduced 3 -> 2  =>  AB-02 (floor_3) is pruned, AB-01 kept
    kept, dropped = B._prune_additional_beams(
        beams, ["floor_1", "floor_2"], list(_ABC.keys()))
    assert [b["id"] for b in kept] == ["AB-01"] and dropped == 1
    # a column that no longer exists also prunes its beams
    kept2, dropped2 = B._prune_additional_beams(
        [_mk("A-1", "Z-9", "floor_1")], ["floor_1"], list(_ABC.keys()))
    assert kept2 == [] and dropped2 == 1


def test_additional_beam_floor_selector_filter():        # TEST 12 / 16
    ab = [_mk("A-1", "C-1", "floor_1")]
    assert len(B._additional_beam_polys(ab, _ABC, "floor_1", 0.25)) == 1
    assert len(B._additional_beam_polys(ab, _ABC, "floor_2", 0.25)) == 0


def test_additional_beam_id_never_collides_with_auto():  # TEST 13-support
    nxt = B._next_additional_beam_id([{"id": "bx_0_0"}, {"id": "by_1_2"},
                                      {"id": "AB-01"}, {"id": "AB-07"}])
    assert nxt == "AB-08"          # ignores bx_/by_, continues AB- sequence


def test_additional_beam_does_not_touch_grid_or_calc():  # TEST 13-15 / 16
    # grid parsing + column labels are unchanged by any of the new helpers
    assert B._parse_spacings("4,5,4", [1])[0] == [0.0, 4.0, 9.0, 13.0]
    assert B._column_rectangle(5.0, 4.0, 0.30, 0.40) == \
        approx((4.85, 5.15, 3.80, 4.20))
    # the additional-beam helpers produce only geometry (tuples/dicts),
    # never a load / capacity / verdict
    polys = B._additional_beam_polys([_mk("A-1", "B-1")], _ABC, "floor_1",
                                     0.25)
    assert all(isinstance(pt, tuple) and len(pt) == 2
               for poly in polys for pt in poly)
    ok, _ = B._validate_additional_beam("A-1", "B-1", "floor_1", "floor_1",
                                        [])
    assert ok is True
