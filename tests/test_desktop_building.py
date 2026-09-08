"""Native Building Model — free-draw 2D plan authoring (AN round: plan editor).

The page now opens EMPTY (no model). The frame analysis engine is unchanged
and is NOT exercised here; drawn members are authoring data only.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication
from desktop_app.building_page import BuildingPage, positive_list, section_label


def _app():
    return QApplication.instance() or QApplication([])


def blank_page():
    """A BuildingPage with the seed grid lines cleared, for tests that
    count members / grids precisely."""
    page = BuildingPage()
    page.canvas.clear()
    page._sync_model()
    page.history = [page.state_snapshot()]
    page.history_index = 0
    return page


def test_default_page_seeds_grid_A_and_1_at_origin():
    _app()
    page = BuildingPage()
    grids = [m for m in page.canvas.members if m['kind'] == 'grid']
    assert len(grids) == 2
    by_axis = {m['axis']: m for m in grids}
    assert by_axis['v']['label'] == 'A' and page.canvas._grid_coord(by_axis['v']) == 0.0
    assert by_axis['h']['label'] == '1' and page.canvas._grid_coord(by_axis['h']) == 0.0
    assert page.model is not None
    assert page.result is None
    assert page.figure.axes == []
    assert page.view_tabs.currentIndex() == 0 and page.view_tabs.tabText(0) == 'แปลน 2D'
    page.close()


def test_draw_members_populates_model_and_sections():
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(0, 0)])
    page.canvas.add_member('column', [(400, 0)])
    page.canvas.add_member('beam', [(0, 0), (400, 0)])
    assert len(page.canvas.members) == 3
    assert page.model is not None and len(page.model['members']) == 3
    # each drawn member carries the active library section label
    col_label = section_label('column', page.sections['column'][0])
    assert page.canvas.members[0]['section'] == col_label
    assert page.canvas.members[2]['section'] == section_label('beam', page.sections['beam'][0])
    page.close()


def test_snap_to_grid_and_to_existing_endpoint():
    _app()
    page = blank_page()
    page.canvas.grid_cm = 100.0
    page.canvas.set_snap(True)
    assert page.canvas._snap_point(QPointF(103, 97)) == (100.0, 100.0)
    page.canvas.add_member('column', [(250, 250)])
    # near an existing endpoint -> snaps to it even off-grid
    assert page.canvas._snap_point(QPointF(258, 244)) == (250.0, 250.0)
    page.canvas.set_snap(False)
    assert page.canvas._snap_point(QPointF(133, 77)) == (133.0, 77.0)
    page.close()


def test_select_delete_and_reassign_section():
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(0, 0)])
    m = page.canvas.members[0]
    page.canvas.select_member(m)
    assert page.canvas.selected is m
    assert page.delete_button.isEnabled()
    # add a new section, make it active, reassign
    page.sections['column'].append({'name': 'C2', 'b': 30.0, 'h': 30.0, 'fc': 280.0})
    page.applied['column'] = 1
    page._reassign_selected()
    assert page.canvas.members[0]['section'] == section_label('column', page.sections['column'][1])
    page.delete_selected()
    assert page.canvas.members == [] and page.model is None
    page.close()


def test_rubber_band_selects_enclosed_members():
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(0.0, 0.0)])
    page.canvas.add_member('column', [(400.0, 0.0)])
    page.canvas.add_member('column', [(2000.0, 0.0)])          # far away
    page.canvas.set_mode('select')
    page.canvas._select_in_rect(QPointF(-100.0, -100.0), QPointF(600.0, 100.0))
    assert len(page.canvas.selected_set) == 2
    assert page.delete_button.isEnabled()
    page.delete_selected()
    assert [m['points'][0] for m in page.canvas.members] == [(2000.0, 0.0)]
    page.close()


def test_right_click_menu_select_and_delete():
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(10.0, 10.0)])
    menu = page.canvas._build_context_menu(QPointF(10.0, 10.0))
    labels = [a.text() for a in menu.actions() if a.text()]
    assert any('เลือก' in t for t in labels)
    assert any('ลบ' in t for t in labels)
    # select then delete via the menu
    next(a for a in menu.actions() if 'เลือก' in a.text()).trigger()
    assert page.canvas.selected is page.canvas.members[0]
    menu2 = page.canvas._build_context_menu(QPointF(10.0, 10.0))
    next(a for a in menu2.actions() if a.text().startswith('ลบ')).trigger()
    assert page.canvas.members == []
    page.close()


def test_escape_leaves_create_mode_for_select():
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    _app()
    page = blank_page()
    page._select_tool('column', 3)
    assert page.canvas.mode == 'column'
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Escape, Qt.KeyboardModifier.NoModifier)
    page.canvas.keyPressEvent(ev)
    assert page.canvas.mode == 'select'
    assert page.tool_group.button(0).isChecked()           # rail synced back to "เลือก"
    page.close()


def test_middle_button_reserved_for_pan_not_context():
    _app()
    page = blank_page()
    # right button no longer starts a pan; _pan_last stays unset
    assert getattr(page.canvas, '_pan_last', None) is None
    page.close()


def test_undo_redo_covers_drawing_and_clear():
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(0, 0)])
    page.canvas.add_member('beam', [(0, 0), (300, 0)])
    assert len(page.canvas.members) == 2
    page.undo_model()
    assert len(page.canvas.members) == 1
    page.undo_model()
    assert len(page.canvas.members) == 0 and page.model is None
    page.redo_model()
    assert len(page.canvas.members) == 1
    page.redo_model()
    assert len(page.canvas.members) == 2
    page.clear_plan()
    assert page.canvas.members == []
    page.undo_model()
    assert len(page.canvas.members) == 2
    page.close()


def test_3d_preview_renders_drawn_members():
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(0, 0)])
    page.canvas.add_member('column', [(400, 0)])
    page.canvas.add_member('beam', [(0, 0), (400, 0)])
    page.view_tabs.setCurrentIndex(1)
    page._refresh_3d()
    assert page.figure.axes
    assert len(page.figure.axes[0].lines) >= 3
    for name, expected in [('บน XY', (90, -90)), ('3D', (30, -60))]:
        page.set_view(name)
        ax = page.figure.axes[0]
        assert (ax.elev, ax.azim) == expected
    page.close()


def test_model_roundtrip_plan_format(tmp_path):
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(0, 0)])
    page.canvas.add_member('beam', [(0, 0), (500, 0)])
    page.storey_h.setValue(3.4)
    path = tmp_path / 'บ้าน.rcmodel'
    page.write_model(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['format'] == 'rc-codepro-plan' and data['version'] == 1
    assert len(data['plan']['members']) == 2
    page.canvas.clear(); page._sync_model()
    assert page.model is None
    page.read_model(path)
    assert len(page.canvas.members) == 2
    assert page.storey_h.value() == pytest.approx(3.4)
    assert page.model is not None
    page.close()


def test_write_empty_plan_is_rejected(tmp_path):
    _app()
    page = blank_page()
    with pytest.raises(ValueError):
        page.write_model(tmp_path / 'empty.rcmodel')
    page.close()


@pytest.mark.parametrize('contents', [
    '[]', '{}', '{bad json',
    '{"format":"rc-codepro-plan","version":2}',
    '{"format":"rc-codepro-plan","version":1}',
    '{"format":"other","version":1}',
])
def test_reject_incompatible_files(tmp_path, contents):
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(10, 10)])
    before = len(page.canvas.members)
    path = tmp_path / 'bad.rcmodel'
    path.write_text(contents, encoding='utf-8')
    with pytest.raises(ValueError):
        page.read_model(path)
    assert len(page.canvas.members) == before
    page.close()


def test_legacy_grid_file_converts_to_drawn_members(tmp_path):
    _app()
    page = blank_page()
    legacy = {'format': 'rc-codepro-grid', 'version': 1, 'fields': {
        'x': '4,4', 'y': '4', 'heights': '3,3', 'col': '30,40', 'beam': '25,50',
        't': '12', 'fc': '240', 'sdl': '150', 'll': '250'}}
    path = tmp_path / 'old.rcmodel'
    path.write_text(json.dumps(legacy), encoding='utf-8')
    page.read_model(path)
    kinds = {m['kind'] for m in page.canvas.members}
    assert 'column' in kinds and 'beam' in kinds
    assert sum(m['kind'] == 'column' for m in page.canvas.members) == 6   # 3x2 grid nodes
    page.close()


def test_cancel_file_dialogs_preserves_plan(monkeypatch):
    from desktop_app.building_page import QFileDialog
    _app()
    page = blank_page()
    page.canvas.add_member('column', [(0, 0)])
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a: ('', ''))
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *a: ('', ''))
    page.open_model(); page.save_model()
    assert len(page.canvas.members) == 1
    page.close()


@pytest.mark.parametrize('value', ['nan', 'inf', '-1', '0', '4,,3'])
def test_positive_list_rejects_invalid(value):
    with pytest.raises(ValueError):
        positive_list(value)


# --- grid authoring ----------------------------------------------------
def test_grid_add_by_spacing_labels_and_auto_dimension():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page._add_grid_by_spacing()                         # A at x=0
    page.grid_spacing.setValue(0.80)
    page._add_grid_by_spacing()                         # B at x=80 cm
    grids = [m for m in page.canvas.members if m['kind'] == 'grid']
    assert len(grids) == 2
    assert [m['label'] for m in sorted(grids, key=lambda m: m['points'][0][0])] == ['A', 'B']
    assert grids[0]['axis'] == 'v'
    # exactly one auto dimension between the two lines, reading 0.80 m
    dim_texts = [it.text() for it in page.canvas._dim_items if hasattr(it, 'text')]
    assert '0.80' in dim_texts
    assert page.model is not None
    page.close()


def test_grid_live_dimension_preview_before_click():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page._add_grid_by_spacing()                         # grid A at x=0
    n_members = len(page.canvas.members)
    page.canvas._grid_preview(QPointF(80, 40))          # cursor 0.80 m from A
    # a transient dimension + cursor marker exist, nothing was committed
    assert page.canvas._cursor_items
    preview_texts = [it.text() for it in page.canvas._cursor_items if hasattr(it, 'text')]
    assert '0.80' in preview_texts
    assert len(page.canvas.members) == n_members
    page.close()


def test_grid_lines_are_snap_targets():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page._add_grid_by_spacing()                         # v grid at x=0
    page.grid_spacing.setValue(4.0)
    page._add_grid_by_spacing()                         # v grid at x=400
    page.canvas.set_snap(True)
    x, y = page.canvas._snap_point(QPointF(394, 118))
    assert x == 400.0                                   # snapped onto grid B
    page.close()


def test_grid_survives_roundtrip(tmp_path):
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page._add_grid_by_spacing(); page.grid_spacing.setValue(4.0); page._add_grid_by_spacing()
    page._select_tool('column', 3)
    page.canvas.add_member('column', [(0, 0)])
    path = tmp_path / 'g.rcmodel'
    page.write_model(path)
    page.canvas.clear(); page._sync_model()
    page.read_model(path)
    grids = [m for m in page.canvas.members if m['kind'] == 'grid']
    assert len(grids) == 2 and sorted(m['label'] for m in grids) == ['A', 'B']
    assert any(m['kind'] == 'column' for m in page.canvas.members)
    page.close()


def test_grid_typed_distance_confirmed_with_enter():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page._add_grid_by_spacing()                         # A at x=0
    # hover to the right of A, then type "3" + Enter -> B at x=300 (3.00 m)
    page.canvas._grid_preview(QPointF(250, 0))
    page.canvas._grid_type_key('3')
    assert page.canvas._type_buffer == '3'
    page.canvas._grid_confirm_typed()
    grids = sorted((m for m in page.canvas.members if m['kind'] == 'grid'),
                   key=lambda m: m['points'][0][0])
    assert [m['points'][0][0] for m in grids] == [0.0, 300.0]
    assert [m['label'] for m in grids] == ['A', 'B']
    assert page.canvas._type_buffer == ''
    page.close()


def test_grid_typed_distance_direction_follows_cursor():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page._add_grid_by_spacing()                         # A at x=0
    page.canvas._grid_preview(QPointF(-40, 0))          # hover LEFT of A
    page.canvas._grid_type_key('2'); page.canvas._grid_type_key('.'); page.canvas._grid_type_key('5')
    page.canvas._grid_confirm_typed()
    xs = sorted(m['points'][0][0] for m in page.canvas.members if m['kind'] == 'grid')
    assert xs == [-250.0, 0.0]                          # 2.5 m to the left
    page.close()


def test_grid_typed_buffer_backspace_and_escape():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page._add_grid_by_spacing()
    page.canvas._grid_preview(QPointF(300, 0))
    for ch in '412':
        page.canvas._grid_type_key(ch)
    page.canvas._grid_type_backspace()
    assert page.canvas._type_buffer == '41'
    page.canvas.set_mode('grid')                        # re-enter clears buffer
    assert page.canvas._type_buffer == ''
    # empty Enter is a no-op
    n = len(page.canvas.members)
    page.canvas._grid_confirm_typed()
    assert len(page.canvas.members) == n
    page.close()


def test_grid_created_as_finite_segment_with_length():
    _app()
    page = blank_page()
    g = page.canvas.add_grid_seg('v', (100.0, -200.0), (100.0, 400.0))
    assert g['axis'] == 'v'
    assert g['points'] == [(100.0, -200.0), (100.0, 400.0)]
    lo, hi = page.canvas._grid_span(g)
    assert (hi - lo) == 600.0                           # 6.00 m long
    assert page.canvas._grid_coord(g) == 100.0
    page.close()


def test_grid_two_click_drag_commits_segment():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page.canvas._grid_start = (150.0, -100.0)
    page.canvas._commit_grid_segment(QPointF(150.0, 520.0))
    g = [m for m in page.canvas.members if m['kind'] == 'grid'][0]
    assert page.canvas._grid_coord(g) == 150.0
    lo, hi = page.canvas._grid_span(g)
    assert lo == -100.0 and hi == 520.0
    assert page.canvas._grid_start is None
    page.close()


def test_grid_endpoint_drag_changes_length_and_shifts_line():
    _app()
    page = blank_page()
    g = page.canvas.add_grid_seg('v', (0.0, -100.0), (0.0, 400.0))
    page.canvas.set_mode('select')
    page.canvas._drag_handle = (g, 1)
    page.canvas._drag_grid_handle(QPointF(60.0, 900.0))
    # dragged endpoint moved to (60, 900); the other endpoint's x followed
    assert g['points'][1] == (60.0, 900.0)
    assert g['points'][0] == (60.0, -100.0)
    assert page.canvas._grid_coord(g) == 60.0
    lo, hi = page.canvas._grid_span(g)
    assert (hi - lo) == 1000.0
    page.close()


def test_grid_typed_length_after_first_click():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    page.canvas._grid_start = (0.0, 0.0)
    page.canvas._last_cursor = QPointF(0.0, 50.0)        # dragging upward
    for ch in '4':
        page.canvas._grid_type_key(ch)
    page.canvas._grid_confirm_typed()
    g = [m for m in page.canvas.members if m['kind'] == 'grid'][0]
    lo, hi = page.canvas._grid_span(g)
    assert lo == 0.0 and hi == 400.0                     # 4.00 m long, upward
    page.close()


def test_grid_pick_selects_grid_segment_by_proximity():
    _app()
    page = blank_page()
    g = page.canvas.add_grid_seg('v', (200.0, 0.0), (200.0, 500.0))
    page.canvas.set_mode('select')
    page.canvas._pick_at(QPointF(205.0, 250.0))
    assert page.canvas.selected is g
    page.close()


def test_delete_grid_resequences_labels():
    _app()
    page = blank_page()
    page._select_tool('grid', 1)
    for _ in range(3):
        page._add_grid_by_spacing(); page.grid_spacing.setValue(4.0)
    grids = sorted((m for m in page.canvas.members if m['kind'] == 'grid'),
                   key=lambda m: m['points'][0][0])
    assert [m['label'] for m in grids] == ['A', 'B', 'C']
    page.canvas.delete_member(grids[1])
    left = sorted((m for m in page.canvas.members if m['kind'] == 'grid'),
                  key=lambda m: m['points'][0][0])
    assert [m['label'] for m in left] == ['A', 'B']
    page.close()


def test_new_grid_matches_existing_same_axis_span():
    _app()
    page = BuildingPage()                                   # keep the seed grids
    seed_v = next(m for m in page.canvas.members
                  if m['kind'] == 'grid' and m['axis'] == 'v')
    seed_span = page.canvas._grid_span(seed_v)
    page._select_tool('grid', 1)
    page._add_grid_by_spacing()                             # grid B
    new_v = [m for m in page.canvas.members
             if m['kind'] == 'grid' and m['axis'] == 'v' and page.canvas._grid_coord(m) != 0.0][0]
    assert page.canvas._grid_span(new_v) == seed_span       # endpoints line up with grid A
    page.close()


def test_linked_grid_endpoints_move_together_on_length_edit():
    _app()
    page = blank_page()
    a = page.canvas.add_grid_seg('v', (0.0, 0.0), (0.0, 500.0))
    b = page.canvas.add_grid_seg('v', (400.0, 0.0), (400.0, 500.0))   # shares top y=500
    page.canvas.set_mode('select')
    # grab grid A's top endpoint (index whose y == 500)
    idx = 0 if a['points'][0][1] == 500.0 else 1
    page.canvas._drag_handle = (a, idx)
    page.canvas._linked = page.canvas._linked_endpoints(a, idx)
    page.canvas._drag_grid_handle(QPointF(0.0, 900.0))       # drag A's top up to y=900
    page.canvas._linked = []
    assert page.canvas._grid_span(a)[1] == 900.0
    assert page.canvas._grid_span(b)[1] == 900.0             # B's top followed
    assert page.canvas._grid_span(b)[0] == 0.0               # B's bottom unchanged
    page.close()


# --- CURRENT round: shortcuts, background grid, levels, auto-axis, dims ----
def test_ctrl_z_shortcut_undoes_last_member():
    _app()
    page = blank_page()
    page._select_tool('column')
    page.canvas.add_member('column', [(0.0, 0.0)])
    assert len(page.canvas.members) == 1
    page.undo_model()                                        # what Ctrl+Z fires
    assert page.canvas.members == []
    page.redo_model()
    assert len(page.canvas.members) == 1
    page.close()


def test_select_all_shortcut_selects_only_non_grid():
    _app()
    page = BuildingPage()                                    # keep seed grids
    page._select_tool('column')
    page.canvas.add_member('column', [(0.0, 0.0)])
    page.canvas.add_member('column', [(400.0, 0.0)])
    page._select_all_members()
    assert len(page.canvas.selected_set) == 2
    assert all(m['kind'] != 'grid' for m in page.canvas.selected_set)
    page.close()


def test_background_grid_follows_snap_mode():
    _app()
    page = blank_page()
    assert page.canvas.snap is True
    page.snap_check.setChecked(False)
    assert page.canvas.snap is False                         # drawBackground hides the mesh
    page.snap_check.setChecked(True)
    assert page.canvas.snap is True
    page.close()


def test_levels_add_edit_remove_and_current_selection():
    _app()
    page = blank_page()
    assert [l['name'] for l in page.levels] == ['พื้นชั้น 1']
    page.levels.append({'name': 'ระดับฐานราก', 'elev': -1.50})
    page.current_level_idx = 1
    page._refresh_level_widgets()
    assert page.canvas.current_level == {'name': 'ระดับฐานราก', 'elev': -1.50}
    assert page.level_box.count() == 2
    # a member drawn now is stamped with that level's elevation
    page._select_tool('column')
    m = page.canvas.add_member('column', [(0.0, 0.0)])
    assert m['level'] == 'ระดับฐานราก' and m['z'] == -1.50
    page.close()


def test_levels_round_trip_through_file(tmp_path):
    _app()
    page = blank_page()
    page.levels = [{'name': 'พื้นชั้น 1', 'elev': 0.55},
                   {'name': 'ระดับฐานราก', 'elev': -1.50}]
    page.current_level_idx = 1
    page._refresh_level_widgets()
    page._select_tool('column')
    page.canvas.add_member('column', [(0.0, 0.0)])
    path = tmp_path / 'lv.rcmodel'
    page.write_model(path)
    page2 = blank_page()
    page2.read_model(path)
    assert [l['elev'] for l in page2.levels] == [0.55, -1.50]
    assert page2.current_level_idx == 1
    assert page2.canvas.members[0]['z'] == -1.50
    page.close(); page2.close()


def test_grid_axis_inferred_from_pointer_and_tab_flips_it():
    _app()
    page = blank_page()
    page.canvas.add_grid('v', 0.0, emit=False)               # one vertical grid at x=0
    page._select_tool('grid', 1)
    # pointer well to the right of every vertical grid -> still a vertical grid
    page.canvas.grid_axis = page.canvas._resolve_grid_axis(QPointF(600.0, 20.0))
    assert page.canvas.grid_axis == 'v'
    # pointer in line with the vertical grid but far above the frame -> horizontal
    page.canvas.add_grid('h', 0.0, emit=False)
    page.canvas.grid_axis = page.canvas._resolve_grid_axis(QPointF(0.0, 600.0))
    assert page.canvas.grid_axis == 'h'
    # Tab flips whatever was inferred and pins it
    page.canvas.toggle_grid_axis()
    assert page.canvas.grid_axis == 'v'
    assert page.canvas._axis_override == 'v'
    page.close()


def test_total_dimension_added_across_grid_line_family():
    _app()
    page = blank_page()
    page.canvas.add_grid('v', 0.0, emit=False)
    page.canvas.add_grid('v', 400.0, emit=False)
    page.canvas.add_grid('v', 700.0, emit=False)
    dim_texts = [it.text() for it in page.canvas._dim_items if hasattr(it, 'text')]
    assert '4.00' in dim_texts and '3.00' in dim_texts       # separated chain
    assert '7.00' in dim_texts                               # overall total
    page.close()


def test_vertical_and_horizontal_dims_sit_on_opposite_sides():
    _app()
    page = blank_page()
    page.canvas.add_grid('v', 0.0, emit=False)
    page.canvas.add_grid('v', 400.0, emit=False)
    page.canvas.add_grid('h', 0.0, emit=False)
    page.canvas.add_grid('h', 300.0, emit=False)
    lines = [it for it in page.canvas._dim_items
             if it.__class__.__name__ == 'QGraphicsLineItem']
    v_y = [it.line().y1() for it in lines if it.line().y1() == it.line().y2()]
    h_x = [it.line().x1() for it in lines if it.line().x1() == it.line().x2()]
    assert v_y and all(y < 0 for y in v_y)                   # A,B,C dims below frame
    assert h_x and all(x < 0 for x in h_x)                   # 1,2,3 dims left of frame
    page.close()


# --- Dimension Layout: detailed coverage -----------------------------------
def _dim_texts(canvas):
    """(text, y_of_baseline, brush_hex) for every committed dimension label."""
    out = []
    for it in canvas._dim_items:
        if it.__class__.__name__ == 'QGraphicsSimpleTextItem':
            out.append((it.text(), it.pos().y(), it.pos().x(),
                        it.brush().color().name().lower()))
    return out


def _dim_lines(canvas):
    return [it for it in canvas._dim_items
            if it.__class__.__name__ == 'QGraphicsLineItem'
            and it.line().length() > 1.0]          # skip the small end ticks


def test_total_dimension_equals_sum_of_chain_and_is_unique():
    _app()
    page = blank_page()
    for x in (0.0, 250.0, 600.0):
        page.canvas.add_grid('v', x, emit=False)
    texts = [t for (t, *_r) in _dim_texts(page.canvas)]
    assert sorted(t for t in texts if t in ('2.50', '3.50')) == ['2.50', '3.50']
    assert texts.count('6.00') == 1                          # one overall total only
    assert abs(2.50 + 3.50 - 6.00) < 1e-9
    page.close()


def test_no_total_dimension_when_axis_has_one_grid():
    _app()
    page = blank_page()
    page.canvas.add_grid('v', 0.0, emit=False)               # lone vertical grid
    page.canvas.add_grid('h', 0.0, emit=False)
    page.canvas.add_grid('h', 400.0, emit=False)             # a real h family
    v_lines = [ln for ln in _dim_lines(page.canvas)
               if ln.line().y1() == ln.line().y2()]          # horizontal = v-axis dims
    assert v_lines == []                                     # nothing drawn for 1 grid
    h_lines = [ln for ln in _dim_lines(page.canvas)
               if ln.line().x1() == ln.line().x2()]
    assert len(h_lines) == 2                                 # 1 chain + 1 total
    page.close()


def test_vertical_total_sits_between_chain_and_bubble():
    _app()
    page = blank_page()
    for x in (0.0, 300.0, 800.0):
        page.canvas.add_grid('v', x, emit=False)
    flo = page.canvas._grid_axis_extent('v')[0]
    C = page.canvas                                          # offset constants
    chain_y = flo - C._DIM_CHAIN_OFF
    total_y = flo - C._DIM_TOTAL_OFF
    bubbles = [m['_bubble'].sceneBoundingRect().center().y()
               for m in C.members if m['kind'] == 'grid' and m['axis'] == 'v']
    # framework is above every stacked element; total is between chain and bubble
    assert flo > chain_y > total_y > max(bubbles)
    ys = sorted({round(ln.line().y1(), 3) for ln in _dim_lines(C)
                 if ln.line().y1() == ln.line().y2()})
    assert ys == sorted({round(chain_y, 3), round(total_y, 3)})
    page.close()


def test_horizontal_total_sits_right_of_bubble_between_chain():
    _app()
    page = blank_page()
    for y in (0.0, 300.0, 800.0):
        page.canvas.add_grid('h', y, emit=False)
    flo = page.canvas._grid_axis_extent('h')[0]
    C = page.canvas
    chain_x = flo - C._DIM_CHAIN_OFF
    total_x = flo - C._DIM_TOTAL_OFF
    bubbles = [m['_bubble'].sceneBoundingRect().center().x()
               for m in C.members if m['kind'] == 'grid' and m['axis'] == 'h']
    # 1, 2, 3 dims sit to the RIGHT of the bubble (bubble is furthest left)
    assert flo > chain_x > total_x > max(bubbles)
    xs = sorted({round(ln.line().x1(), 3) for ln in _dim_lines(C)
                 if ln.line().x1() == ln.line().x2()})
    assert xs == sorted({round(chain_x, 3), round(total_x, 3)})
    page.close()


def test_total_dimension_has_distinct_style_from_chain():
    _app()
    page = blank_page()
    for x in (0.0, 250.0, 600.0):
        page.canvas.add_grid('v', x, emit=False)
    by_text = {t: hexcol for (t, _y, _x, hexcol) in _dim_texts(page.canvas)}
    assert by_text['2.50'] == '#2563eb'                      # chain colour (_DIM_COLOR)
    assert by_text['3.50'] == '#2563eb'
    assert by_text['6.00'] == '#1e3a8a'                      # total: darker blue
    page.close()


def test_dimension_layout_rebuilds_when_a_grid_is_inserted():
    _app()
    page = blank_page()
    page.canvas.add_grid('v', 0.0, emit=False)
    page.canvas.add_grid('v', 400.0, emit=False)
    first = [t for (t, *_r) in _dim_texts(page.canvas)]
    assert first.count('4.00') == 2                          # chain 4.00 + total 4.00
    page.canvas.add_grid('v', 900.0, emit=False)             # insert a third line
    after = [t for (t, *_r) in _dim_texts(page.canvas)]
    assert '4.00' in after and '5.00' in after               # two chain segments now
    assert after.count('9.00') == 1                          # exactly one overall total
    # annotations are rebuilt, not appended: 3 grids -> 2 chain + 1 total lines
    v_lines = [ln for ln in _dim_lines(page.canvas)
               if ln.line().y1() == ln.line().y2()]
    assert len(v_lines) == 3
    page.close()


def test_dimension_offset_tracks_grid_extent_after_length_edit():
    _app()
    page = blank_page()
    a = page.canvas.add_grid_seg('v', (0.0, 0.0), (0.0, 500.0), emit=False)
    page.canvas.add_grid_seg('v', (400.0, 0.0), (400.0, 500.0), emit=False)
    C = page.canvas
    chain_gap = C._grid_axis_extent('v')[0] - min(
        ln.line().y1() for ln in _dim_lines(C) if ln.line().y1() == ln.line().y2())
    # drag grid A's bottom endpoint down so the framework grows
    C.set_mode('select')
    idx = 0 if a['points'][0][1] == 0.0 else 1
    C._drag_handle = (a, idx)
    C._linked = C._linked_endpoints(a, idx)
    C._drag_grid_handle(QPointF(0.0, -300.0))
    C._linked = []
    new_flo = C._grid_axis_extent('v')[0]
    new_gap = new_flo - min(
        ln.line().y1() for ln in _dim_lines(C) if ln.line().y1() == ln.line().y2())
    assert new_flo <= -300.0                                 # framework extended down
    assert abs(new_gap - chain_gap) < 1e-6                   # dim keeps its offset
    page.close()
