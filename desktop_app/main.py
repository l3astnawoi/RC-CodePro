"""Native desktop shell. Calculation engines remain unchanged during migration.

Navigation is a flat QStackedWidget driven by ``DesktopWindow.go(name)``; the
Home page is a card launcher (see ``desktop_app/home.py``). Project,
Parameters and Help are reached from the header, kept separate from the
design categories.
"""
import sys

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QFormLayout, QFrame, QHBoxLayout,
                               QGroupBox, QLabel, QLineEdit, QMainWindow, QPushButton,
                               QInputDialog, QMenuBar, QSplitter, QStackedWidget, QTabBar,
                               QTabWidget, QToolButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from desktop_app.beam_page import BeamPage
from desktop_app.column_page import ColumnPage
from desktop_app.slab_page import SlabPage
from desktop_app.footing_page import FootingPage
from desktop_app.pile_cap_page import PileCapPage
from desktop_app.stair_page import StairPage
from desktop_app.u_stair_page import UStairPage
from desktop_app.building_page import BuildingPage
from desktop_app.home import (HomePage, PlaceholderPage, THEME_QSS, load_fonts,
                              svg_pixmap)

# Design categories only. Project / Parameters / Help live in the header.
CATEGORY_ORDER = ["Building Model", "Beam", "Column", "Slab", "Footing", "Stair", "Wall"]


class DesktopWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        load_fonts()
        self.project = {"name": "บ้านพักอาศัย 2 ชั้น", "location": "-", "engineer": "-"}
        self.setWindowTitle("RC CodePro — Desktop")
        self.resize(1360, 840)
        self.setMinimumSize(1024, 576)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.menu_strip = self._build_menu_strip(); self.crumb_bar = self.menu_strip
        shell.addWidget(self.menu_strip)
        self.ribbon = self._build_ribbon(); shell.addWidget(self.ribbon)

        self.pages = QStackedWidget()
        self.workspace = QSplitter(Qt.Horizontal)
        self.inspector = self._build_inspector(); self.workspace.addWidget(self.inspector)
        self.workspace.addWidget(self.pages)
        self.project_browser = self._build_project_browser(); self.workspace.addWidget(self.project_browser)
        self.workspace.setSizes([410, 980, 220]); self.workspace.setStretchFactor(1, 1)
        shell.addWidget(self.workspace, 1)
        self.work_status = self._build_status_bar(); shell.addWidget(self.work_status)

        # name -> widget, registered in stack order
        self._pages = {}
        self._register("Home", HomePage(
            self.go, on_open_file=self._open_recent_file,
            get_project=lambda: self.project,
            get_building=lambda: getattr(self, 'building_page', None)))
        self._register("Project", self._project_page())
        self._register("Parameters", PlaceholderPage(
            "พารามิเตอร์", "การตั้งค่าพารามิเตอร์การออกแบบส่วนกลางกำลังพัฒนา", "tools"))
        self._register("Help", PlaceholderPage(
            "วิธีใช้งาน RC CodePro",
            "การวาดโมเดล\n"
            "เลือก Grid, Footing, Column, Beam, Slab, Stair หรือ Wall จาก Drawing Model แล้วคลิกบนแปลน\n"
            "Ctrl ค้างระหว่างวาด = ล็อกแกน X/Y · Esc = ออกจากโหมดสร้าง\n\n"
            "การเลือกและแก้ไข\n"
            "คลิก Member เพื่อเลือก · Ctrl+คลิกเพื่อเลือกหลายชิ้น · Delete เพื่อลบ\n"
            "วางเมาส์บน Member เพื่อเน้นสี · กด Tab เพื่อวนเลือก Member ที่ซ้อนกัน\n"
            "ลากจุดจับปลาย Member เพื่อแก้ความยาว · ลากตัวกริดเพื่อย้ายกริดทั้งเส้น\n"
            "เมื่อเลือกกริด คลิกรูปกุญแจเพื่อให้ปลายกริดขยับแยกจากกริดอื่น\n"
            "เลือกกริด คาน กำแพง หรือบันไดหนึ่งชิ้น แล้วพิมพ์ความยาวเป็นเมตร กด Enter\n\n"
            "การกำหนดระยะแบบพิมพ์ค่า\n"
            "ระหว่างสร้างกริดหรือ Member ให้พิมพ์ตัวเลขหน่วยเมตร แล้วกด Enter\n"
            "ใช้ Tab เพื่อสลับแกน X/Y ในตำแหน่งที่โปรแกรมกำลังเล็ง\n\n"
            "มุมมอง\n"
            "เมาส์กลางลาก = เลื่อน · ล้อเมาส์ = ซูม\n"
            "ระดับ Cut Plan เริ่มที่ 0.00 m; เพิ่มค่าเพื่อเลื่อนระนาบตัดขึ้นและมองลง\n"
            "ใน 3D: Shift+เมาส์กลาง = หมุน · Full Screen = แสดงเต็มหน้าจอ\n\n"
            "การบันทึกและคำนวณ\n"
            "ใช้ File เพื่อสร้าง เปิด และบันทึกโครงการ · ใช้ Load และ Analysis สำหรับกำหนดและคำนวณแรง",
            "help"))
        self._register("Beam", BeamPage())
        self._register("Column", ColumnPage(self.project))
        self._register("Slab", SlabPage(self.project))
        footing_tabs = QTabWidget()
        footing_tabs.addTab(FootingPage(self.project, self.go), "ฐานรากแผ่เดี่ยว")
        footing_tabs.addTab(PileCapPage(self.project), "ฐานเสาเข็ม F2 / F4")
        self._register("Footing", footing_tabs)
        stair_tabs = QTabWidget()
        stair_tabs.addTab(StairPage(self.project), "บันไดช่วงตรง")
        stair_tabs.addTab(UStairPage(self.project), "บันไดหักกลับ U-Shape")
        self._register("Stair", stair_tabs)
        self._register("Building Model", BuildingPage(self.project))
        self.building_page = self._pages['Building Model']
        self.building_page.tool_side_external = True
        self.inspector_stack.addWidget(self.building_page.tool_side)
        self.building_page.canvas.changed.connect(self._refresh_workspace_chrome)
        self.building_page.canvas.picked.connect(lambda _member: self._refresh_workspace_chrome())
        self.building_page.level_box.currentIndexChanged.connect(lambda _i: self._refresh_workspace_chrome())
        self.building_page.snap_check.toggled.connect(lambda _on: self._refresh_workspace_chrome())
        self._register("Wall", PlaceholderPage(
            "Wall — ผนัง",
            "หน้าออกแบบผนัง (bearing / shear wall ตาม ACI 318M-08) กำลังพัฒนา", "wall"))

        self.setStyleSheet(THEME_QSS)
        self.go("Home")

    def _build_menu_strip(self):
        frame = QFrame(); frame.setObjectName('menuBar'); frame.setFixedHeight(34)
        layout = QHBoxLayout(frame); layout.setContentsMargins(8, 0, 8, 0); layout.setSpacing(0)
        menus = QMenuBar(frame); menus.setObjectName('mainMenu')
        menus.setNativeMenuBar(False)

        file_menu = menus.addMenu('File')
        self.file_actions = {
            'New Project': self._menu_action(file_menu, 'New Project', self._new_project, QKeySequence.StandardKey.New),
            'Open Project': self._menu_action(file_menu, 'Open Project', self._open_project, QKeySequence.StandardKey.Open),
            'Save': self._menu_action(file_menu, 'Save', self._save_project_file, QKeySequence.StandardKey.Save),
            'Save As': self._menu_action(file_menu, 'Save As', self._save_project_as, QKeySequence.StandardKey.SaveAs),
        }
        file_menu.addSeparator()
        self.file_actions['Project Properties'] = self._menu_action(
            file_menu, 'Project Properties', lambda: self.go('Project'))
        file_menu.addSeparator()
        self.file_actions['Exit'] = self._menu_action(file_menu, 'Exit', self.close, QKeySequence.StandardKey.Quit)

        edit_menu = menus.addMenu('Edit')
        self.edit_actions = {
            'Undo': self._menu_action(edit_menu, 'Undo', self._undo, QKeySequence.StandardKey.Undo),
            'Redo': self._menu_action(edit_menu, 'Redo', self._redo, QKeySequence.StandardKey.Redo),
        }
        edit_menu.addSeparator()
        for text, slot, shortcut in (
                ('Cut', self._cut, QKeySequence.StandardKey.Cut),
                ('Copy', self._copy, QKeySequence.StandardKey.Copy),
                ('Paste', self._paste, QKeySequence.StandardKey.Paste),
                ('Delete', self._delete, QKeySequence.StandardKey.Delete)):
            self.edit_actions[text] = self._menu_action(edit_menu, text, slot, shortcut)
        edit_menu.addSeparator()
        self.edit_actions['Select...'] = self._menu_action(edit_menu, 'Select...', self._select_by_type)
        self.edit_actions['Select All'] = self._menu_action(
            edit_menu, 'Select All', self._select_all, QKeySequence.StandardKey.SelectAll)

        view_menu = menus.addMenu('View')
        display_menu = view_menu.addMenu('Display')
        self.display_actions = {}
        for text, checked, slot in (
                ('Show Other Levels', True, self._toggle_other_levels),
                ('True Scale Members', False, self._toggle_true_scale),
                ('Beam Labels', True, lambda on: self._toggle_member_label('beam', on)),
                ('Column Labels', True, lambda on: self._toggle_member_label('column', on)),
                ('Footing Labels', True, lambda on: self._toggle_member_label('footing', on))):
            action = self._menu_action(display_menu, text, slot)
            action.setCheckable(True); action.setChecked(checked)
            self.display_actions[text] = action

        for text, route in [('Home', 'Home'), ('Define', 'Parameters'),
                            ('Assign', 'Building Model'), ('Analysis', 'Building Model'),
                            ('Design', 'Building Model'), ('Report', 'Building Model')]:
            menu = menus.addMenu(text)
            menu.addAction('Open', lambda _=False, name=route: self.go(name))
        help_menu = menus.addMenu('Help')
        self.help_actions = {
            'วิธีใช้งาน': self._menu_action(help_menu, 'วิธีใช้งาน', lambda: self.go('Help'))
        }
        brand = QLabel('RC Code Pro'); brand.setObjectName('appBrand')
        layout.addWidget(brand); layout.addSpacing(8); layout.addWidget(menus)
        layout.addStretch(1)
        self.proj_chip = QLabel(self.project['name']); self.proj_chip.setObjectName('headerProject')
        self.save_chip = QLabel('● Saved'); self.save_chip.setObjectName('headerSaved')
        layout.addWidget(self.proj_chip); layout.addSpacing(8); layout.addWidget(self.save_chip)
        layout.addSpacing(14)
        lang = QLabel('TH  ▾'); lang.setObjectName('headerMeta'); layout.addWidget(lang)
        layout.addSpacing(12)
        help_label = QLabel('?'); help_label.setObjectName('headerHelp'); layout.addWidget(help_label)
        return frame

    @staticmethod
    def _menu_action(menu, text, slot, shortcut=None):
        action = QAction(text, menu)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _ribbon_button(self, text, icon, target):
        button = QToolButton(); button.setObjectName('ribbonBtn'); button.setText(text)
        button.setIcon(QIcon(svg_pixmap(icon, 24))); button.setIconSize(QSize(24, 24))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); button.setFixedSize(76, 58)
        if callable(target):
            button.clicked.connect(target)
        else:
            button.clicked.connect(lambda: self.go(target))
        return button

    def _ribbon_group(self, title, commands):
        group = QFrame(); group.setObjectName('ribbonGroupFrame')
        col = QVBoxLayout(group); col.setContentsMargins(5, 0, 5, 0); col.setSpacing(0)
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(1)
        for text, icon, target in commands:
            row.addWidget(self._ribbon_button(text, icon, target))
        col.addLayout(row, 1)
        caption = QLabel(title); caption.setObjectName('ribbonGroup'); caption.setAlignment(Qt.AlignCenter)
        col.addWidget(caption)
        return group

    def _build_ribbon(self):
        frame = QFrame(); frame.setObjectName('ribbon'); frame.setFixedHeight(104)
        layout = QVBoxLayout(frame); layout.setContentsMargins(8, 2, 8, 3); layout.setSpacing(1)
        self.ribbon_tabs = QTabBar(); self.ribbon_tabs.setObjectName('ribbonTabs')
        for title in ('Drawing Model', 'Display', 'Loads', 'Analysis', 'Design', 'Detailing', 'Report'):
            self.ribbon_tabs.addTab(title)
        layout.addWidget(self.ribbon_tabs)
        self.ribbon_stack = QStackedWidget(); layout.addWidget(self.ribbon_stack, 1)

        drawing = QWidget(); drawing_row = QHBoxLayout(drawing)
        drawing_row.setContentsMargins(0, 0, 0, 0); drawing_row.setSpacing(3)
        groups = (
            ('Selection', (('Select', 'tools', 'select'),)),
            ('Reference', (('Grid', 'grid', 'grid'), ('Level', 'column', 'level'))),
            ('Frame', (('Column', 'column', 'column'), ('Beam', 'beam', 'beam'))),
            ('Area', (('Slab', 'slab', 'slab'), ('Wall', 'wall', 'wall'))),
            ('Foundation', (('Footing', 'footing', 'footing'),)),
            ('Other', (('Stair', 'stair', 'stair'),)),
        )
        for title, commands in groups:
            wired = [(text, icon, lambda _=False, tool=key: self._show_building_tool(tool))
                     for text, icon, key in commands]
            drawing_row.addWidget(self._ribbon_group(title, wired))
        drawing_row.addStretch(1); self.ribbon_stack.addWidget(drawing)

        display = QWidget(); display_row = QHBoxLayout(display)
        display_row.setContentsMargins(0, 0, 0, 0); display_row.setSpacing(3)
        for text, icon, index in (('Plan 2D', 'grid', 0), ('Model 3D', 'building', 1),
                                  ('Side View 2D', 'beam', 2)):
            display_row.addWidget(self._ribbon_button(
                text, icon, lambda _=False, tab=index: self._show_model_view(tab)))
        display_row.addWidget(self._ribbon_button(
            'Display Settings', 'tools', lambda: self._show_building_tool('view')))
        display_row.addStretch(1); self.ribbon_stack.addWidget(display)

        loads = QWidget(); load_row = QHBoxLayout(loads)
        load_row.setContentsMargins(0, 0, 0, 0); load_row.setSpacing(3)
        for text, icon, field in (
                ('Dead Load', 'slab', 'dead'), ('Live Load', 'beam', 'live'),
                ('Wind Load', 'building', 'wind'), ('Load Transfer', 'tools', 'transfer')):
            load_row.addWidget(self._ribbon_button(
                text, icon, lambda _=False, name=field: self._show_load_editor(name)))
        load_row.addStretch(1); self.ribbon_stack.addWidget(loads)

        analysis = QWidget(); analysis_row = QHBoxLayout(analysis)
        analysis_row.setContentsMargins(0, 0, 0, 0); analysis_row.setSpacing(3)
        analysis_row.addWidget(self._ribbon_button('Run Load Path', 'tools', self._run_load_analysis))
        analysis_row.addWidget(self._ribbon_button(
            'Analysis Results', 'project', lambda: self._show_load_editor('transfer')))
        analysis_row.addStretch(1); self.ribbon_stack.addWidget(analysis)

        design = QWidget(); design_row = QHBoxLayout(design)
        design_row.setContentsMargins(0, 0, 0, 0); design_row.setSpacing(3)
        for name, icon in (('Beam', 'beam'), ('Column', 'column'), ('Slab', 'slab'),
                           ('Footing', 'footing'), ('Stair', 'stair'), ('Wall', 'wall')):
            design_row.addWidget(self._ribbon_button(name, icon, name))
        design_row.addStretch(1); self.ribbon_stack.addWidget(design)

        detailing = QWidget(); detailing_row = QHBoxLayout(detailing)
        detailing_row.setContentsMargins(0, 0, 0, 0)
        detailing_row.addWidget(QLabel('Select a design workspace to view its existing detailing tools.'))
        detailing_row.addStretch(1); self.ribbon_stack.addWidget(detailing)

        report = QWidget(); report_row = QHBoxLayout(report)
        report_row.setContentsMargins(0, 0, 0, 0); report_row.setSpacing(3)
        for text, route, icon in (('Beam Report', 'Beam', 'beam'),
                                  ('Column Report', 'Column', 'column'),
                                  ('Slab Report', 'Slab', 'slab'),
                                  ('Footing Report', 'Footing', 'footing'),
                                  ('Stair Report', 'Stair', 'stair')):
            report_row.addWidget(self._ribbon_button(text, icon, route))
        report_row.addStretch(1); self.ribbon_stack.addWidget(report)

        self.ribbon_tabs.currentChanged.connect(self._activate_ribbon_tab)
        self.ribbon_stack.setCurrentIndex(0)
        return frame

    def _activate_ribbon_tab(self, index):
        self.ribbon_stack.setCurrentIndex(index)
        if index == 0:
            self._show_building_tool('select')
        elif index == 1:
            self._show_building_tool('view')
        elif index == 2:
            self._show_load_editor('transfer')

    def _show_model_view(self, index):
        page = self._building()
        if page is None:
            return
        self.go('Building Model')
        page.view_tabs.setCurrentIndex(index)

    def _run_load_analysis(self):
        page = self._building()
        if page is None:
            return
        self.go('Building Model')
        page.show_load_panel('transfer')
        page.run_load_transfer()

    def _show_building_tool(self, key):
        page = self._building()
        if page is None:
            return
        self.go('Building Model')
        page.select_tool(key)

    def _show_load_editor(self, field='transfer'):
        page = self._building()
        if page is None:
            return
        self.go('Building Model')
        page.show_load_panel(field)

    def _build_project_browser(self):
        frame = QFrame(); frame.setObjectName('projectBrowser'); frame.setMinimumWidth(190)
        layout = QVBoxLayout(frame); layout.setContentsMargins(8, 8, 6, 8); layout.setSpacing(6)
        head = QHBoxLayout(); title = QLabel('Project Browser'); title.setObjectName('panelTitle')
        head.addWidget(title); head.addStretch(1)
        collapse = QToolButton(); collapse.setText('»'); collapse.setToolTip('Collapse Project Browser')
        collapse.clicked.connect(lambda: self._set_side_panel('right', False)); head.addWidget(collapse)
        layout.addLayout(head)
        self.project_search = QLineEdit(); self.project_search.setPlaceholderText('Search project…')
        self.project_search.textChanged.connect(self._filter_project_tree); layout.addWidget(self.project_search)
        self.project_tree = QTreeWidget(); self.project_tree.setHeaderHidden(True)
        self.project_tree.itemClicked.connect(self._tree_open)
        layout.addWidget(self.project_tree, 1)
        self._refresh_project_tree()
        return frame

    def _refresh_project_tree(self):
        if not hasattr(self, 'project_tree'):
            return
        self.project_tree.clear()
        root = QTreeWidgetItem([f"Project: {self.project['name']}"]); root.setExpanded(True)
        model = QTreeWidgetItem(['Model']); model.setExpanded(True); root.addChild(model)
        stories = QTreeWidgetItem(['Stories & Levels']); stories.setExpanded(True); model.addChild(stories)
        page = self._building()
        levels = getattr(page, 'levels', []) if page is not None else []
        for index, level in sorted(enumerate(levels), key=lambda pair: pair[1]['elev'], reverse=True):
            item = QTreeWidgetItem([f"{level['name']}   {level['elev']:+.2f} m"])
            item.setData(0, Qt.UserRole, ('level', index)); stories.addChild(item)
        grids = QTreeWidgetItem(['Grids']); grids.setData(0, Qt.UserRole, 'Building Model'); model.addChild(grids)
        structural = QTreeWidgetItem(['Structural Elements']); structural.setExpanded(True); model.addChild(structural)
        members = getattr(getattr(page, 'canvas', None), 'members', []) if page is not None else []
        for kind, label in (('column', 'Columns'), ('beam', 'Beams'), ('slab', 'Slabs'),
                            ('wall', 'Walls'), ('footing', 'Foundations'), ('stair', 'Stairs')):
            subset = [m for m in members if m.get('kind') == kind]
            branch = QTreeWidgetItem([f'{label} ({len(subset)})']); structural.addChild(branch)
            for member in subset:
                name = member.get('id') or member.get('name') or member.get('section') or label[:-1]
                child = QTreeWidgetItem([str(name)]); child.setData(0, Qt.UserRole, ('member', member)); branch.addChild(child)
        supports = QTreeWidgetItem(['Supports']); supports.setData(0, Qt.UserRole, 'Footing'); model.addChild(supports)
        for title, children in (
            ('Loads', ('Load Cases', 'Load Assignments', 'Load Combinations')),
            ('Analysis', ('Model Status', 'Analysis Results')),
            ('Design', ('Beam Design', 'Column Design', 'Slab Design', 'Foundation Design')),
            ('Documents', ('Drawings', 'Reports'))):
            branch = QTreeWidgetItem([title]); root.addChild(branch)
            for child_text in children:
                child = QTreeWidgetItem([child_text]); child.setData(0, Qt.UserRole, 'Building Model'); branch.addChild(child)
        self.project_tree.addTopLevelItem(root); self.project_tree.expandToDepth(2)
        self._filter_project_tree(self.project_search.text() if hasattr(self, 'project_search') else '')

    def _filter_project_tree(self, text):
        query = text.strip().lower()
        def visit(item):
            child_match = any(visit(item.child(i)) for i in range(item.childCount()))
            matched = query in item.text(0).lower() or child_match
            item.setHidden(bool(query) and not matched)
            if query and child_match: item.setExpanded(True)
            return matched
        for i in range(self.project_tree.topLevelItemCount()): visit(self.project_tree.topLevelItem(i))

    def _tree_open(self, item, _column):
        route = item.data(0, Qt.UserRole)
        if isinstance(route, tuple) and route[0] == 'level':
            self.go('Building Model'); self.building_page.level_box.setCurrentIndex(route[1]); return
        if isinstance(route, tuple) and route[0] == 'member':
            self.go('Building Model'); self.building_page.canvas.select_members([route[1]]); return
        if route:
            self.go(route)

    def _build_inspector(self):
        frame = QFrame(); frame.setObjectName('inspector'); frame.setMinimumWidth(360)
        frame.setMaximumWidth(520)
        layout = QVBoxLayout(frame); layout.setContentsMargins(6, 8, 8, 8); layout.setSpacing(0)
        self.inspector_stack = QStackedWidget(); layout.addWidget(self.inspector_stack)
        generic = QWidget(); generic_layout = QVBoxLayout(generic)
        generic_layout.setContentsMargins(2, 0, 0, 0); generic_layout.setSpacing(7)
        header = QHBoxLayout(); title = QLabel('Properties'); title.setObjectName('panelTitle')
        header.addWidget(title); header.addStretch(1)
        collapse = QToolButton(); collapse.setText('«'); collapse.setToolTip('Collapse Properties')
        collapse.clicked.connect(lambda: self._set_side_panel('left', False)); header.addWidget(collapse)
        generic_layout.addLayout(header)
        self.inspector_name = QLineEdit('No selection'); self.inspector_name.setReadOnly(True); generic_layout.addWidget(self.inspector_name)
        self.inspector_values = {}
        for group_title, fields in [('Geometry', ['Section', 'Level', 'Length']),
                                    ('Material', ['Material', 'Grade']),
                                    ('Loads', ['Dead', 'Live']),
                                    ('Design', ['Status'])]:
            group = QGroupBox(group_title); form = QFormLayout(group); form.setContentsMargins(8, 12, 8, 8)
            for field in fields:
                value = QLineEdit('—'); value.setReadOnly(True); self.inspector_values[field] = value; form.addRow(field, value)
            generic_layout.addWidget(group)
        generic_layout.addStretch(1)
        self.inspector_stack.addWidget(generic)
        return frame

    def _set_side_panel(self, side, shown=True):
        panel = self.inspector if side == 'left' else self.project_browser
        panel.setVisible(bool(shown))
        if not shown:
            button = self.left_restore if side == 'left' else self.right_restore
            button.setVisible(True)
        self.workspace.setStretchFactor(1, 1)

    def _update_inspector_from_member(self, member):
        if member is None:
            self.inspector_name.setText('No selection')
            for value in self.inspector_values.values(): value.setText('—')
            return
        kind = member.get('kind', 'Member').title(); self.inspector_name.setText(kind)
        self.inspector_values['Section'].setText(str(member.get('section', '—')))
        self.inspector_values['Level'].setText(str(member.get('level', '—')))
        points = member.get('points', [])
        length = 0.0
        if len(points) >= 2:
            length = ((points[1][0]-points[0][0])**2 + (points[1][1]-points[0][1])**2)**0.5 / 100.0
        self.inspector_values['Length'].setText(f'{length:.2f} m' if length else 'Point')
        self.inspector_values['Material'].setText('Steel' if str(member.get('section', '')).startswith('เหล็ก') else 'Concrete')
        self.inspector_values['Grade'].setText("Selected section")
        self.inspector_values['Status'].setText('Ready')

    def _building(self):
        return getattr(self, 'building_page', None)

    def _new_project(self):
        page = self._building()
        if page is not None:
            page.new_model()
        self.go('Building Model')

    def _open_project(self):
        page = self._building()
        if page is not None:
            page.open_model()
        self.go('Building Model')

    def _open_recent_file(self, path):
        page = self._building()
        if page is not None:
            page.open_model_path(path)
        self.go('Building Model')

    def _save_project_file(self):
        page = self._building()
        if page is not None:
            page.save_model()

    def _save_project_as(self):
        page = self._building()
        if page is not None:
            page.save_model_as()

    def _undo(self):
        if self._building() is not None:
            self.building_page.undo_model()

    def _redo(self):
        if self._building() is not None:
            self.building_page.redo_model()

    def _cut(self):
        if self._building() is not None:
            self.building_page.cut_selected()

    def _copy(self):
        if self._building() is not None:
            self.building_page.copy_selected()

    def _paste(self):
        if self._building() is not None:
            self.building_page.paste_members()

    def _delete(self):
        if self._building() is not None:
            self.building_page.delete_selected()

    def _select_all(self):
        if self._building() is not None:
            self.building_page._select_all_members()

    def _select_by_type(self):
        page = self._building()
        if page is None:
            return
        kinds = [(thai, key) for key, thai in page.member_kind_names()]
        labels = [thai for thai, _key in kinds]
        label, ok = QInputDialog.getItem(self, 'Select Member',
                                         'เลือกประเภท Member ในระดับที่กำลังเขียน',
                                         labels, 0, False)
        if ok and label:
            key = next(key for thai, key in kinds if thai == label)
            page.select_kind_on_current_level(key)

    def _toggle_other_levels(self, shown):
        page = self._building()
        if page is not None:
            page.other_levels_button.setChecked(bool(shown))

    def _toggle_true_scale(self, shown):
        page = self._building()
        if page is not None:
            page.true_scale_check.setChecked(bool(shown))

    def _toggle_member_label(self, kind, shown):
        page = self._building()
        if page is not None:
            page.member_label_checks[kind].setChecked(bool(shown))

    def _build_status_bar(self):
        frame = QFrame(); frame.setObjectName('statusBar'); frame.setFixedHeight(24)
        layout = QHBoxLayout(frame); layout.setContentsMargins(8, 0, 8, 0)
        self.status_ready = QLabel('Ready'); self.status_ready.setObjectName('statusText'); layout.addWidget(self.status_ready)
        layout.addStretch(1)
        for text in ('Units: Metric (cm, kg)', 'ACI 318M-19', 'RC CodePro Desktop'):
            label = QLabel(text); label.setObjectName('statusText'); layout.addWidget(label); layout.addSpacing(12)
        return frame

    # ---- header -----------------------------------------------------------
    def _build_header(self):
        bar = QFrame()
        bar.setObjectName("header")
        bar.setFixedHeight(66)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(12)

        mark = QLabel()
        mark.setPixmap(svg_pixmap("building", 26))
        lay.addWidget(mark)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        t = QLabel("RC CodePro")
        t.setObjectName("brandTitle")
        s = QLabel("Reinforced Concrete Design · Strength Design Method")
        s.setObjectName("brandSub")
        brand.addWidget(t)
        brand.addWidget(s)
        lay.addLayout(brand)
        lay.addStretch(1)

        self.proj_chip = QLabel(self.project["name"])
        self.proj_chip.setObjectName("projChip")
        self.proj_chip.setFocusPolicy(Qt.NoFocus)
        lay.addWidget(self.proj_chip)
        lay.addSpacing(6)

        for label, target in [("ข้อมูลโครงการ", "Project"),
                              ("พารามิเตอร์", "Parameters"),
                              ("แนะนำการใช้งาน", "Help")]:
            b = QPushButton(label)
            b.setObjectName("headerBtn")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=target: self.go(name))
            lay.addWidget(b)
        return bar

    def _build_crumb(self):
        bar = QFrame()
        bar.setObjectName("crumbBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(28, 10, 24, 2)
        lay.setSpacing(8)
        self.crumb_home = QPushButton("หน้าหลัก")
        self.crumb_home.setObjectName("crumbBtn")
        self.crumb_home.setCursor(Qt.PointingHandCursor)
        self.crumb_home.clicked.connect(lambda: self.go("Home"))
        self.crumb_sep = QLabel("/")
        self.crumb_here = QLabel("")
        self.crumb_here.setObjectName("crumbHere")
        lay.addWidget(self.crumb_home)
        lay.addWidget(self.crumb_sep)
        lay.addWidget(self.crumb_here)
        lay.addStretch(1)
        self.crumb_bar = bar
        return bar

    # ---- navigation -----------------------------------------------------
    def _register(self, name, widget):
        self._pages[name] = widget
        self.pages.addWidget(widget)

    def go(self, name):
        """Switch to a page by name. Unknown names are ignored."""
        widget = self._pages.get(name)
        if widget is None:
            return
        self.pages.setCurrentWidget(widget)
        on_home = name == "Home"
        if on_home:
            widget.refresh()
        immersive_workspace = name == "Footing"
        detail_workspace = name in {"Beam", "Column", "Slab", "Footing", "Stair", "Wall", "Help"}
        self.menu_strip.setVisible(not on_home and not immersive_workspace)
        self.ribbon.setVisible(not on_home and not immersive_workspace)
        self.project_browser.setVisible(not on_home and not detail_workspace)
        self.inspector.setVisible(not on_home and not detail_workspace)
        if not detail_workspace and not on_home:
            self.inspector_stack.setCurrentWidget(
                self.building_page.tool_side if name == 'Building Model'
                else self.inspector_stack.widget(0))
        if name == 'Building Model':
            self.display_actions['Show Other Levels'].setChecked(
                self.building_page.other_levels_button.isChecked())
            self.display_actions['True Scale Members'].setChecked(
                self.building_page.true_scale_check.isChecked())
            for text, kind in (('Beam Labels', 'beam'), ('Column Labels', 'column'),
                               ('Footing Labels', 'footing')):
                self.display_actions[text].setChecked(
                    self.building_page.member_label_checks[kind].isChecked())
        self.work_status.setVisible(not on_home and not immersive_workspace)
        if not on_home:
            self.status_ready.setText(f'Ready · {name}')
        self.proj_chip.setText(self.project["name"])

    def current_page(self):
        return self.pages.currentWidget()

    # ---- project ------------------------------------------------------
    def _project_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.addWidget(QLabel("<h1>ข้อมูลโครงการ</h1>"))
        form = QFormLayout()
        self.name = QLineEdit(self.project["name"])
        self.location = QLineEdit(self.project["location"])
        self.engineer = QLineEdit(self.project["engineer"])
        form.addRow("ชื่อโครงการ", self.name)
        form.addRow("สถานที่", self.location)
        form.addRow("วิศวกร", self.engineer)
        layout.addLayout(form)
        save = QPushButton("บันทึกข้อมูลโครงการ")
        save.setObjectName("headerBtn")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self.save_project)
        layout.addWidget(save)
        layout.addStretch(1)
        return page

    def save_project(self):
        self.project.update(name=self.name.text(), location=self.location.text(),
                            engineer=self.engineer.text())
        self.proj_chip.setText(self.project["name"])


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RC CodePro")
    load_fonts()
    window = DesktopWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
