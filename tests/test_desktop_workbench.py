import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMenuBar

from desktop_app import recent_files
from desktop_app.home import CategoryCard, HeroCard, RecentProjectCard
from desktop_app.main import DesktopWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_home_dashboard_has_hero_and_standalone_tools_with_no_recent_projects(monkeypatch):
    monkeypatch.setattr(recent_files, "load", lambda: [])
    app = _app()
    window = DesktopWindow()
    window.show()
    window.go("Home")
    app.processEvents()

    home = window.current_page()
    # Building Model is the one big "Continue Designing" entry point; the
    # other six categories are the standalone member tools below it.
    assert len(home.findChildren(HeroCard)) == 1
    assert len(home.findChildren(CategoryCard)) == 6
    # No real recent files on disk -> an honest empty state, not demo rows.
    assert len(home.findChildren(RecentProjectCard)) == 0
    assert home._recent_empty.isVisible()
    assert not window.ribbon.isVisible()
    assert not window.project_browser.isVisible()

    window.close()


def test_home_recent_projects_reflect_the_real_mru_list(tmp_path, monkeypatch):
    files = [tmp_path / "Villa.rcmodel", tmp_path / "Office.rcmodel"]
    for f in files:
        f.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(recent_files, "load", lambda: [str(f) for f in files])
    app = _app()
    window = DesktopWindow()
    window.show()
    window.go("Home")
    app.processEvents()

    home = window.current_page()
    cards = home.findChildren(RecentProjectCard)
    assert len(cards) == 2
    assert home._recent_empty.isHidden()

    window.close()


def test_model_workspace_shows_ribbon_browser_and_inspector():
    app = _app()
    window = DesktopWindow()
    window.show()
    window.go("Building Model")
    app.processEvents()

    assert window.ribbon.isVisible()
    assert window.project_browser.isVisible()
    assert window.inspector.isVisible()
    assert window.project_tree.topLevelItem(0).childCount() == 1
    assert window.project_tree.topLevelItem(0).isExpanded()
    building = window._pages['Building Model']
    assert window.inspector_stack.currentWidget() is building.tool_side
    assert building.workspace_splitter.count() == 1
    assert window.workspace.widget(0) is window.inspector
    assert window.workspace.widget(2) is window.project_browser
    assert building.cut_plan.value() == 0.0
    assert building.cut_plan.singleStep() == 0.10
    assert not building.member_toolbar.findChildren(type(building.undo_button))

    window.close()


def test_context_ribbon_switches_between_drawing_and_load_tools():
    app = _app()
    window = DesktopWindow(); window.show(); window.go('Building Model')
    app.processEvents()

    assert [window.ribbon_tabs.tabText(i) for i in range(window.ribbon_tabs.count())] == [
        'Drawing Model', 'Display', 'Load', 'Analysis', 'Design', 'Report']
    window.ribbon_tabs.setCurrentIndex(2); app.processEvents()
    page = window.building_page
    assert window.ribbon_stack.currentIndex() == 2
    assert page.detail.currentIndex() == page.load_detail_index
    assert page.load_wind.isVisible()
    assert page.edit_buttons['select'].isChecked()

    window.ribbon_tabs.setCurrentIndex(0); app.processEvents()
    assert page.detail.currentIndex() == 0
    assert page.tool_group.button(0).isChecked()
    window.close()


def test_left_edit_rail_has_requested_order_and_select_stays_active():
    app = _app()
    window = DesktopWindow(); window.show(); window.go('Building Model')
    app.processEvents(); page = window.building_page
    assert [page.edit_buttons[key].text() for key in page.edit_buttons] == [
        'Select', 'Move', 'Copy', 'Cut', 'Delete', 'Rotate', 'Undo', 'Redo']
    assert page.edit_buttons['select'].isChecked()
    page.edit_buttons['undo'].click(); app.processEvents()
    assert page.edit_buttons['select'].isChecked()
    window.close()


def test_file_edit_view_menus_expose_working_commands():
    app = _app()
    window = DesktopWindow()
    window.show(); window.go('Building Model'); app.processEvents()

    menu_titles = [action.text() for action in window.menu_strip.findChild(QMenuBar).actions()]
    assert menu_titles[:3] == ['File', 'Edit', 'View']
    assert list(window.file_actions) == [
        'New Project', 'Open Project', 'Save', 'Save As', 'Project Properties', 'Exit']
    assert list(window.edit_actions) == [
        'Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Delete', 'Select...', 'Select All']
    assert window.display_actions['True Scale Members'].isCheckable()
    assert list(window.help_actions) == ['วิธีใช้งาน']
    window.help_actions['วิธีใช้งาน'].trigger(); app.processEvents()
    assert window.current_page() is window._pages['Help']

    building = window.building_page
    column = building.canvas.add_member('column', [(100, 100)])
    building.canvas.select_member(column)
    window.edit_actions['Copy'].trigger(); window.edit_actions['Paste'].trigger()
    assert sum(m['kind'] == 'column' for m in building.canvas.members) == 2
    window.display_actions['True Scale Members'].trigger()
    assert building.canvas.true_scale_members
    window.close()


def test_detail_workspace_uses_full_width_canvas():
    app = _app()
    window = DesktopWindow()
    window.show()
    window.go("Beam")
    app.processEvents()

    assert window.ribbon.isVisible()
    assert not window.project_browser.isVisible()
    assert not window.inspector.isVisible()
    assert window.current_page().objectName() == "beamPage"

    window.close()
