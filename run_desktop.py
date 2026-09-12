import sys


def smoke_test(output):
    """Exercise the packaged native stack and Column without an event loop."""
    import json
    import traceback
    from pathlib import Path
    try:
        from PySide6.QtWidgets import QApplication, QLabel
        from desktop_app.main import DesktopWindow, CATEGORY_ORDER
        from desktop_app.home import CategoryCard, HeroCard, RecentProjectCard
        app = QApplication.instance() or QApplication([])
        window = DesktopWindow()
        window.go('Home')
        home = window.current_page()
        # Building Model is the one big "Continue Designing" hero card; the
        # rest of CATEGORY_ORDER renders as the standalone-tool cards below it.
        cards = home.findChildren(CategoryCard)
        assert len(cards) == len(CATEGORY_ORDER) - 1
        for card in cards:
            pix = [c.pixmap() for c in card.findChildren(QLabel)
                   if c.pixmap() is not None and not c.pixmap().isNull()]
            assert pix, 'home card %r has no icon (asset bundling / QtSvg?)' % card.title
        heroes = home.findChildren(HeroCard)
        assert len(heroes) == 1, 'expected exactly one Building Model hero card'
        # The seeded Building Model has no drawn members yet -> "Getting
        # Started", not a fabricated Project Overview.
        assert home._overview_pages.currentIndex() == 0
        # Recent Projects reflects the real on-disk MRU list, whatever it
        # holds on this machine -- not a fixed demo count.
        from desktop_app import recent_files as _recent_files
        n_recent = len(_recent_files.load())
        assert len(home.findChildren(RecentProjectCard)) == min(n_recent, 4)
        assert home._recent_empty.isHidden() == (n_recent > 0)
        window.go('Column')
        page = window.current_page()
        for shape in (0, 1):
            page.shape.setCurrentIndex(shape)
            page.calculate()
            assert page.result is not None
            assert not page.section.pixmap().isNull()
            assert not page.diagram.pixmap().isNull()
            report = page.report_bytes()
            assert report.startswith(b'%PDF-')
        window.close()
        window.go('Slab')
        slab = window.current_page()
        for lx in (4, 2):
            slab.fields['Lx'].setValue(lx)
            slab.calculate()
            assert slab.result is not None
            assert not slab.drawing.pixmap().isNull()
            assert slab.report_bytes().startswith(b'%PDF-')
        window.go('Footing')
        footing_tabs = window.current_page()
        footing = footing_tabs.widget(0)
        for shape in (0, 1):
            footing.shape.setCurrentIndex(shape)
            footing.calculate()
            assert footing.result is not None
            assert not footing.drawing.pixmap().isNull()
            assert footing.report_bytes().startswith(b'%PDF-')
        footing_tabs.setCurrentIndex(1)
        pile = footing_tabs.widget(1)
        for kind in (0, 1):
            pile.kind.setCurrentIndex(kind)
            pile.calculate()
            assert pile.result is not None
            assert not pile.drawing.pixmap().isNull()
            assert pile.report_bytes().startswith(b'%PDF-')
        window.go('Stair')
        stair_tabs = window.current_page()
        stair = stair_tabs.widget(0)
        stair.calculate()
        assert stair.result is not None
        assert not stair.drawing.pixmap().isNull()
        assert stair.report_bytes().startswith(b'%PDF-')
        stair_tabs.setCurrentIndex(1)
        u_stair = stair_tabs.widget(1)
        u_stair.calculate()
        assert u_stair.result is not None
        assert not u_stair.drawing.pixmap().isNull()
        assert u_stair.report_bytes().startswith(b'%PDF-')
        window.go('Building Model')
        building = window.current_page()
        seed = [m for m in building.canvas.members if m['kind'] == 'grid']
        assert {m['label'] for m in seed} == {'A', '1'}          # seeded grid framework
        building.canvas.clear(); building._sync_model()
        assert building.model is None and building.canvas.members == []
        building._select_tool('column')
        building.canvas.add_member('column', [(0, 0)])
        building.canvas.add_member('column', [(400, 0)])
        building._select_tool('beam')
        building.canvas.add_member('beam', [(0, 0), (400, 0)])
        assert len(building.canvas.members) == 3
        assert building.model is not None and len(building.model['members']) == 3
        building.view_tabs.setCurrentIndex(1)
        building._refresh_3d()
        assert building.figure.axes and len(building.figure.axes[0].lines) >= 3
        building.set_view('บน XY')
        assert building.figure.axes[0].elev == 90
        model_path = Path(output).with_suffix('.rcmodel')
        building.write_model(model_path)
        building.canvas.clear(); building._sync_model()
        assert building.model is None
        building.read_model(model_path)
        assert len(building.canvas.members) == 3 and building.model is not None
        building.canvas.select_member(building.canvas.members[-1])
        building.delete_selected()
        assert len(building.canvas.members) == 2
        building.undo_model()
        assert len(building.canvas.members) == 3
        building.redo_model()
        assert len(building.canvas.members) == 2
        wall = building.canvas.add_member('wall', [(0, 100), (400, 100)])
        building.canvas.select_member(wall)
        building.properties.end_z.setValue(4.2)
        building.properties.apply()
        assert wall['z_end'] == 4.2
        minor = building.canvas.add_grid('v', 80, minor=True)
        assert not minor['_bubble'].isVisible()
        building._refresh_3d()
        assert building.figure.axes[0].collections
        assert building.plan_level_box.currentIndex() == building.level_box.currentIndex()
        # Packaged model editing: same-type selection and atomic bulk height.
        first = building.canvas.add_member('column', [(900, 900)])
        second = building.canvas.add_member('column', [(1000, 900)])
        building.canvas.select_same_type(first)
        assert first in building.canvas.selected_set and second in building.canvas.selected_set
        building.properties.height.setValue(4.5)
        building.properties.height.editingFinished.emit()
        assert first['z_end'] - first['z_start'] == 4.5
        assert second['z_end'] - second['z_start'] == 4.5
        assert building.draw_properties['column'].defaults is not None
        building._refresh_3d()
        assert not building.figure.axes[0]._axis3don
        assert building.model_interaction.geometry
        # Other-level visibility remains independent from level edit locking.
        upper = building.canvas.add_member('beam', [(900, 1000), (1100, 1000)],
                                           level={'name': 'ชั้นอื่น', 'elev': 3.5})
        assert upper['item'].isVisible() and not building.canvas.is_editable(upper)
        building.other_levels_button.setChecked(False)
        assert not upper['item'].isVisible()
        building.other_levels_button.setChecked(True)
        # Concrete and the PDF-derived steel families are explicitly separated.
        assert building.material_pickers['beam'].currentData() == 'concrete'
        building.material_pickers['beam'].setCurrentIndex(1)
        building.material_pickers['beam'].activated.emit(1)
        assert building._pickers['beam'].count() == 32
        building.family_pickers['beam'].setCurrentIndex(2)
        building.family_pickers['beam'].activated.emit(2)
        assert building._pickers['beam'].count() == 73
        assert building._active_section_label('beam').startswith('เหล็ก · H ')
        # Editable Side View is projected on a user-selected main grid.
        building.canvas.add_grid('v', 0)
        building.canvas.add_grid('h', 0)
        building._refresh_side_grids()
        assert building.side_grid_box.count() >= 2
        building.view_tabs.setCurrentIndex(2)
        building.side_canvas.refresh()
        assert building.view_tabs.tabText(2) == 'Side View 2D'
        assert building.side_canvas.grid is not None
        # Member snapping exposes endpoint, midpoint and nearest-line targets.
        from PySide6.QtCore import QPointF
        snap_beam = building.canvas.add_member('beam', [(0, 1200), (400, 1200)])
        assert building.canvas._snap_point(QPointF(205, 1205), exclude=upper) == (200.0, 1200.0)
        building.canvas.select_member(snap_beam)
        assert len(building.canvas._member_handles) == 2
        Path(output).write_text(json.dumps({'ok': True}), encoding='utf-8')
        return 0
    except Exception:
        Path(output).write_text(traceback.format_exc(), encoding='utf-8')
        return 1

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        raise SystemExit(smoke_test(sys.argv[2]))
    from desktop_app.main import main
    raise SystemExit(main())
