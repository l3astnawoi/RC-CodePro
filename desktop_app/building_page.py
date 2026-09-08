"""Native Building Model — a free-draw 2D plan authoring page.

This round: the page opens EMPTY (no model). The user draws members on a
2D plan (Column / Beam / Slab / Footing / Stair) and assigns a named
section + material from the per-kind library ("C1 · 20x20 cm · 240 ksc").
Drawn members feed a read-only 3D preview and the .rcmodel file.

Force analysis of a freely-drawn model is NOT wired here -- the frame
engine (utils/analytical_model, utils/building_analysis) is unchanged and
untouched. `self.result` stays None; a later round adds analysis once the
engine accepts an arbitrary member list.
"""
import math
import json
from pathlib import Path

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QLabel, QPushButton, QSplitter, QFileDialog, QComboBox, QTabWidget,
    QToolButton, QButtonGroup, QStackedWidget, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QCheckBox, QFrame, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, QSaveFile, QIODevice, QSize
from PySide6.QtGui import QIcon, QShortcut, QKeySequence
from matplotlib.figure import Figure
from matplotlib.ticker import AutoLocator
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from desktop_app.home import icon_path
from desktop_app.plan_canvas import (PlanCanvas, KIND_TH, KIND_COLOR,
                                     POINT_KINDS, LINE_KINDS)


def positive_list(text):
    values = [float(v.strip()) for v in text.split(',')]
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('ระยะและความสูงต้องเป็นตัวเลขมากกว่า 0 คั่นด้วย comma')
    return values


# --- named-section library ------------------------------------------------
SECTION_SPEC = {
    'column': [('b', 'b (cm)', 5, 400, 1, 20.0), ('h', 'h (cm)', 5, 400, 1, 20.0),
               ('fc', "f′c (ksc)", 100, 700, 0, 240.0)],
    'beam': [('b', 'b (cm)', 5, 400, 1, 20.0), ('h', 'h (cm)', 5, 400, 1, 40.0),
             ('fc', "f′c (ksc)", 100, 700, 0, 240.0)],
    'slab': [('t', 't (cm)', 5, 60, 1, 12.0), ('fc', "f′c (ksc)", 100, 700, 0, 240.0)],
    'footing': [('Lx', 'Lx (cm)', 40, 600, 0, 150.0), ('Ly', 'Ly (cm)', 40, 600, 0, 150.0),
                ('depth', 'ความลึก (cm)', 20, 200, 0, 40.0), ('fc', "f′c (ksc)", 100, 700, 0, 240.0)],
    'stair': [('waist', 'ท้องพื้น t (cm)', 8, 40, 1, 15.0), ('steps', 'จำนวนขั้น', 4, 30, 0, 12.0),
              ('fc', "f′c (ksc)", 100, 700, 0, 240.0)],
}
DEFAULT_SECTIONS = {
    'column': [{'name': 'C1', 'b': 20.0, 'h': 20.0, 'fc': 240.0}],
    'beam': [{'name': 'B1', 'b': 20.0, 'h': 40.0, 'fc': 240.0}],
    'slab': [{'name': 'S1', 't': 12.0, 'fc': 240.0}],
    'footing': [{'name': 'F1', 'Lx': 150.0, 'Ly': 150.0, 'depth': 40.0, 'fc': 240.0}],
    'stair': [{'name': 'ST1', 'waist': 15.0, 'steps': 12.0, 'fc': 240.0}],
}
TOOLS = [('เลือก', 'select'), ('กริด', 'grid'), ('ฐานราก', 'footing'),
         ('เสา', 'column'), ('คาน', 'beam'), ('พื้น', 'slab'), ('บันได', 'stair')]


def section_label(kind, s):
    if kind in ('column', 'beam'):
        return f"{s['name']} · {s['b']:g}×{s['h']:g} cm · {s['fc']:g} ksc"
    if kind == 'slab':
        return f"{s['name']} · t {s['t']:g} cm · {s['fc']:g} ksc"
    if kind == 'footing':
        return f"{s['name']} · {s['Lx']:g}×{s['Ly']:g} cm · d {s['depth']:g} · {s['fc']:g} ksc"
    return f"{s['name']} · ท้องพื้น {s['waist']:g} cm · {s['steps']:g} ขั้น · {s['fc']:g} ksc"


class SectionDialog(QDialog):
    def __init__(self, kind, initial=None, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle(f"หน้าตัด{KIND_TH[kind]}")
        form = QFormLayout(self)
        self.name = QLineEdit((initial or {}).get('name', ''))
        self.name.setPlaceholderText(kind[0].upper() + '1')
        form.addRow('ชื่อหน้าตัด', self.name)
        self.inputs = {}
        for key, label, mn, mx, dp, dv in SECTION_SPEC[kind]:
            w = QDoubleSpinBox(); w.setRange(mn, mx); w.setDecimals(dp)
            w.setValue(float((initial or {}).get(key, dv)))
            self.inputs[key] = w
            form.addRow(label, w)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        form.addRow(box)

    def value(self):
        out = {'name': self.name.text().strip() or self.name.placeholderText()}
        out.update({k: w.value() for k, w in self.inputs.items()})
        return out


class LevelDialog(QDialog):
    """Name + elevation (m) for a drawing level, e.g. 'ระดับฐานราก' -1.50."""
    def __init__(self, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ระดับ / ชั้น')
        form = QFormLayout(self)
        self.name = QLineEdit((initial or {}).get('name', ''))
        self.name.setPlaceholderText('พื้นชั้น 1')
        form.addRow('ชื่อระดับ', self.name)
        self.elev = QDoubleSpinBox()
        self.elev.setRange(-50.0, 200.0); self.elev.setDecimals(2)
        self.elev.setSingleStep(0.05); self.elev.setSuffix(' m')
        self.elev.setValue(float((initial or {}).get('elev', 0.0)))
        form.addRow('ระดับ (m)', self.elev)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        form.addRow(box)

    def value(self):
        return {'name': self.name.text().strip() or self.name.placeholderText(),
                'elev': float(self.elev.value())}


def _clean_levels(raw):
    out = []
    for r in (raw if isinstance(raw, list) else []):
        if not isinstance(r, dict):
            continue
        name = str(r.get('name', '')).strip()
        elev = r.get('elev', 0.0)
        if not name or not isinstance(elev, (int, float)):
            continue
        out.append({'name': name, 'elev': float(elev)})
    return out or [{'name': 'พื้นชั้น 1', 'elev': 0.0}]


class BuildingPage(QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self.model = None            # user plan dict, or None when empty
        self.result = None           # no force analysis this round
        self.sections = {k: [dict(s) for s in v] for k, v in DEFAULT_SECTIONS.items()}
        self.applied = {k: 0 for k in SECTION_SPEC}
        self._pickers = {}
        # drawing levels / elevations (item: "ระดับฐานราก -1.50", "พื้นชั้น 1 +0.55")
        self.levels = [{'name': 'พื้นชั้น 1', 'elev': 0.0}]
        self.current_level_idx = 0

        root = QVBoxLayout(self)
        root.addWidget(QLabel('<h2>Building Model · แปลน 2D</h2>'))
        note = QLabel('เริ่มจากแปลนเปล่า — เลือกเครื่องมือด้านซ้าย แล้วคลิกวาด member ลงบนแปลน\n'
            'ทุกชิ้นเลือกหน้าตัด/วัสดุ (f′c) จากคลังได้ · เมาส์กลางลาก = เลื่อนมุมมอง · ล้อเมาส์ = ซูม · คลิกขวา = เมนู · ESC = ออกจากโหมดสร้าง\n'
            'รอบนี้ยังไม่วิเคราะห์แรงจากโมเดลที่วาด (เอนจินโครงข้อแข็งไม่ถูกแก้)')
        note.setWordWrap(True); root.addWidget(note)

        bar = QHBoxLayout()
        for title, cb in [('เปิดโมเดล', self.open_model), ('บันทึกโมเดล', self.save_model)]:
            b = QPushButton(title); b.clicked.connect(cb); bar.addWidget(b)
        self.undo_button = QPushButton('ย้อนกลับ'); self.undo_button.clicked.connect(self.undo_model)
        self.redo_button = QPushButton('ทำซ้ำ'); self.redo_button.clicked.connect(self.redo_model)
        bar.addWidget(self.undo_button); bar.addWidget(self.redo_button)
        self.delete_button = QPushButton('ลบที่เลือก'); self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected); bar.addWidget(self.delete_button)
        clear_btn = QPushButton('ล้างแปลน'); clear_btn.clicked.connect(self.clear_plan)
        bar.addWidget(clear_btn)
        bar.addStretch(1)
        bar.addWidget(QLabel('ระดับที่กำลังเขียน'))
        self.level_box = QComboBox(); self.level_box.setMinimumWidth(150)
        self.level_box.currentIndexChanged.connect(self._on_level_change)
        bar.addWidget(self.level_box)
        self.snap_check = QCheckBox('snap กริด'); self.snap_check.setChecked(True)
        self.snap_check.toggled.connect(self._on_snap)
        bar.addWidget(self.snap_check)
        bar.addWidget(QLabel('ความสูงชั้น (m)'))
        self.storey_h = QDoubleSpinBox(); self.storey_h.setRange(1.5, 10.0)
        self.storey_h.setValue(3.0); self.storey_h.setSingleStep(0.1)
        self.storey_h.valueChanged.connect(lambda _=0: (self.record_edit(), self._refresh_3d()))
        bar.addWidget(self.storey_h)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal); root.addWidget(split, 1)
        split.addWidget(self._build_toolside())

        self.view_tabs = QTabWidget()
        self.canvas = PlanCanvas()
        self.canvas.set_section_lookup(self._active_section_label)
        self.canvas.changed.connect(self._on_canvas_changed)
        self.canvas.picked.connect(self._on_pick_member)
        self.canvas.mode_changed.connect(self._on_canvas_mode)
        self.view_tabs.addTab(self.canvas, 'แปลน 2D')

        view3d = QWidget(); v3 = QVBoxLayout(view3d)
        self.figure = Figure(); self.canvas3d = FigureCanvasQTAgg(self.figure)
        self.view_name = '3D'
        vb = QHBoxLayout()
        for name in ('3D', 'บน XY', 'หน้า XZ', 'ข้าง YZ'):
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, s=name: self.set_view(s))
            vb.addWidget(b)
        v3.addLayout(vb)
        v3.addWidget(NavigationToolbar2QT(self.canvas3d, self))
        v3.addWidget(self.canvas3d)
        self.view_tabs.addTab(view3d, 'โมเดล 3D')
        self.view_tabs.currentChanged.connect(lambda i: i == 1 and self._refresh_3d())
        split.addWidget(self.view_tabs); split.setStretchFactor(1, 1)

        self.status = QLabel(); self.status.setWordWrap(True); root.addWidget(self.status)

        self._refresh_section_pickers()
        self._refresh_level_widgets()
        # Seed the framework with grid A (vertical) and grid 1 (horizontal)
        # crossing at the origin (X, Y = 0, 0).
        self.canvas.add_grid('v', 0.0, emit=False)
        self.canvas.add_grid('h', 0.0, emit=False)
        self._sync_model()
        self.history = [self.state_snapshot()]; self.history_index = 0
        self._update_status()

        # ---- keyboard shortcuts ----
        for seq, slot in ((QKeySequence.StandardKey.Undo, self.undo_model),
                          (QKeySequence.StandardKey.Redo, self.redo_model),
                          (QKeySequence('Ctrl+Y'), self.redo_model),
                          (QKeySequence.StandardKey.SelectAll, self._select_all_members)):
            sc = QShortcut(seq, self); sc.activated.connect(slot)

    def _select_all_members(self):
        self.canvas.select_members([m for m in self.canvas.members
                                    if m['kind'] != 'grid'])

    # ---- left rail ---------------------------------------------------
    def _build_toolside(self):
        wrap = QWidget(); lay = QHBoxLayout(wrap); lay.setContentsMargins(0, 0, 0, 0)
        rail = QVBoxLayout(); rail.setSpacing(4)
        self.tool_group = QButtonGroup(self); self.tool_group.setExclusive(True)
        self.detail = QStackedWidget()
        for i, (label, key) in enumerate(TOOLS):
            btn = QToolButton(); btn.setObjectName('toolRailBtn'); btn.setCheckable(True)
            btn.setText(label); btn.setIcon(QIcon(icon_path(key if key != 'grid' else 'grid')))
            btn.setIconSize(QSize(22, 22)); btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setFixedSize(62, 54); btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key, idx=i: self._select_tool(k, idx))
            self.tool_group.addButton(btn, i)
            rail.addWidget(btn)
            self.detail.addWidget(self._detail_page(key))
        rail.addStretch(1)
        railw = QWidget(); railw.setLayout(rail); railw.setFixedWidth(72)
        lay.addWidget(railw); lay.addWidget(self.detail, 1)
        self.tool_group.button(0).setChecked(True)
        return wrap

    def _select_tool(self, key, idx=None):
        if idx is not None:
            self.detail.setCurrentIndex(idx)
        if key == 'grid':
            self.canvas.set_mode('grid')
        else:
            self.canvas.set_mode(key if key in KIND_TH else 'select')

    def _add_grid_by_spacing(self):
        # axis follows whatever the canvas last inferred (mouse / Tab)
        self.canvas.add_next_grid(self.grid_spacing.value())

    def _detail_page(self, key):
        page = QWidget(); v = QVBoxLayout(page)
        if key == 'select':
            v.addWidget(QLabel('<b>เลือก / แก้ไข</b>'))
            v.addWidget(QLabel('คลิกที่ member เพื่อเลือก · ลากคลุมบนที่ว่าง = เลือกหลายชิ้น\n'
                               'ปุ่ม "ลบที่เลือก" / Del = ลบ · คลิกขวา = เมนู (เลือก/ลบ/ออกจากโหมด)\n'
                               'ปลายเส้นกริดลากได้ · เมาส์กลางลาก = เลื่อน · ล้อเมาส์ = ซูม'))
            self.pick_info = QLabel('ยังไม่ได้เลือก'); self.pick_info.setWordWrap(True)
            v.addWidget(self.pick_info)
            self.reassign_btn = QPushButton('ใช้หน้าตัดที่เลือกกับ member นี้')
            self.reassign_btn.setEnabled(False)
            self.reassign_btn.clicked.connect(self._reassign_selected)
            v.addWidget(self.reassign_btn)
        elif key == 'grid':
            v.addWidget(QLabel('<b>สร้างเส้นกริด</b>'))
            v.addWidget(QLabel('ไม่ต้องเลือกแกน — โปรแกรมดูจากตำแหน่ง/ทิศเมาส์เองว่าเป็น\n'
                               'แกน A, B, C (แนวตั้ง) หรือ 1, 2, 3 (แนวนอน)\n'
                               'กด Tab เพื่อสลับแกนที่โปรแกรมเดา'))
            form = QFormLayout(); v.addLayout(form)
            self.grid_spacing = QDoubleSpinBox(); self.grid_spacing.setRange(0.10, 100.0)
            self.grid_spacing.setDecimals(2); self.grid_spacing.setValue(4.00)
            self.grid_spacing.setSingleStep(0.10)
            form.addRow('ระยะถัดไป (m)', self.grid_spacing)
            add_grid_btn = QPushButton('เพิ่มกริดตามระยะนี้')
            add_grid_btn.clicked.connect(self._add_grid_by_spacing)
            v.addWidget(add_grid_btn)
            v.addWidget(QLabel('หรือวาดเอง: คลิกปลายด้านหนึ่ง แล้วลาก/คลิกอีกปลาย = ความยาวเส้นกริด\n'
                               '• ระหว่างเล็งจุดแรก: พิมพ์ระยะ (m) + Enter = ตำแหน่งเส้นกริด\n'
                               '• หลังคลิกจุดแรก: พิมพ์ระยะ (m) + Enter = ความยาวเส้นกริด\n'
                               'แก้ทีหลังได้: เครื่องมือ "เลือก" แล้วลากที่ปลายเส้นกริด (ขึ้นลง/ซ้ายขวาอิสระ)\n'
                               'เส้นบอกระยะระหว่างเส้นกริดขึ้นเองอัตโนมัติ'))
            line = QFrame(); line.setFrameShape(QFrame.HLine); v.addWidget(line)
            v.addWidget(QLabel('<b>ระดับ / ชั้น</b>'))
            v.addWidget(QLabel('เช่น ระดับฐานราก -1.50 · พื้นชั้น 1 +0.55'))
            self.level_list = QListWidget(); self.level_list.setMaximumHeight(120)
            self.level_list.currentRowChanged.connect(self._on_level_row)
            v.addWidget(self.level_list)
            lbtns = QHBoxLayout()
            for lbl, slot in [('เพิ่มระดับ', self._level_add),
                              ('แก้ไข', self._level_edit),
                              ('ลบ', self._level_remove)]:
                b = QPushButton(lbl); b.clicked.connect(slot); lbtns.addWidget(b)
            v.addLayout(lbtns)
            line2 = QFrame(); line2.setFrameShape(QFrame.HLine); v.addWidget(line2)
            form2 = QFormLayout(); v.addLayout(form2)
            self.grid_step = QDoubleSpinBox(); self.grid_step.setRange(10, 2000)
            self.grid_step.setValue(100.0); self.grid_step.setSingleStep(10.0)
            self.grid_step.valueChanged.connect(self._on_grid_step)
            form2.addRow('ระยะ snap พื้นหลัง (cm)', self.grid_step)
        else:
            v.addWidget(QLabel(f'<b>หน้าตัด{KIND_TH[key]} & วัสดุ</b>'))
            hint = {'column': 'คลิก 1 จุดบนแปลนเพื่อวางเสา',
                    'footing': 'คลิก 1 จุดเพื่อวางฐานราก',
                    'beam': 'คลิก 2 จุด (ต้น–ปลาย) เพื่อวางคาน',
                    'stair': 'คลิก 2 จุดเพื่อวางแนวบันได',
                    'slab': 'คลิกหลายจุด แล้วดับเบิลคลิกเพื่อปิดรูปพื้น'}[key]
            v.addWidget(QLabel(hint))
            if key in ('column', 'footing', 'beam', 'stair'):
                v.addWidget(QLabel('ระหว่างเล็ง (ยังไม่คลิก) จะมีเส้นบอกระยะจากกริดที่ใกล้ที่สุด\n'
                                   'พิมพ์ระยะ (m) + Enter เพื่อวางห่างจากกริดเป๊ะ ๆ · Tab สลับแกน X/Y'))
            picker = QComboBox()
            picker.currentIndexChanged.connect(lambda _=0, k=key: self._on_pick_section(k))
            self._pickers[key] = picker
            v.addWidget(picker)
            btns = QHBoxLayout()
            for lbl, slot in [('เพิ่มหน้าตัด', lambda: self._section_add(key)),
                              ('แก้ไข', lambda: self._section_edit(key)),
                              ('ลบ', lambda: self._section_remove(key))]:
                b = QPushButton(lbl); b.clicked.connect(slot); btns.addWidget(b)
            v.addLayout(btns)
            if key in ('footing', 'stair'):
                v.addWidget(QLabel('ยังไม่รวมในการวิเคราะห์โครงข้อแข็ง'))
        v.addStretch(1)
        return page

    # ---- section library -------------------------------------------
    def _refresh_section_pickers(self):
        for kind, picker in self._pickers.items():
            picker.blockSignals(True); picker.clear()
            for i, s in enumerate(self.sections[kind]):
                picker.addItem(section_label(kind, s), i)
            picker.setCurrentIndex(min(self.applied[kind], len(self.sections[kind]) - 1))
            picker.blockSignals(False)

    def _on_pick_section(self, kind):
        self.applied[kind] = self._pickers[kind].currentData() or 0
        self.record_edit()

    def _active_section_label(self, kind):
        s = self.sections[kind][min(self.applied[kind], len(self.sections[kind]) - 1)]
        return section_label(kind, s)

    def _section_add(self, kind):
        dlg = SectionDialog(kind, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.sections[kind].append(dlg.value())
            self.applied[kind] = len(self.sections[kind]) - 1
            self._refresh_section_pickers(); self.record_edit()

    def _section_edit(self, kind):
        idx = min(self.applied[kind], len(self.sections[kind]) - 1)
        dlg = SectionDialog(kind, self.sections[kind][idx], parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.sections[kind][idx] = dlg.value()
            self._refresh_section_pickers(); self.record_edit()

    def _section_remove(self, kind):
        if len(self.sections[kind]) <= 1:
            return
        del self.sections[kind][min(self.applied[kind], len(self.sections[kind]) - 1)]
        self.applied[kind] = 0
        self._refresh_section_pickers(); self.record_edit()

    def section_state(self):
        return {'sections': {k: [dict(s) for s in v] for k, v in self.sections.items()},
                'applied': dict(self.applied)}

    def load_section_state(self, state):
        secs = (state or {}).get('sections'); applied = (state or {}).get('applied')
        if not isinstance(secs, dict) or not isinstance(applied, dict):
            return
        clean = {}
        for kind, spec in SECTION_SPEC.items():
            rows = secs.get(kind)
            keep = []
            for r in (rows if isinstance(rows, list) else []):
                if not isinstance(r, dict):
                    continue
                entry = {'name': str(r.get('name', kind[0].upper() + '1'))}
                for key, _l, _mn, _mx, _dp, dv in spec:
                    v = r.get(key, dv)
                    entry[key] = float(v) if isinstance(v, (int, float)) else dv
                keep.append(entry)
            clean[kind] = keep or [dict(s) for s in DEFAULT_SECTIONS[kind]]
        self.sections = clean
        self.applied = {k: (applied.get(k) if isinstance(applied.get(k), int)
                            and 0 <= applied.get(k) < len(self.sections[k]) else 0)
                        for k in SECTION_SPEC}
        self._refresh_section_pickers()

    # ---- drawing levels -----------------------------------------
    @staticmethod
    def _level_text(l):
        return f"{l['name']}   {l['elev']:+.2f} m"

    def _refresh_level_widgets(self):
        self.current_level_idx = max(0, min(self.current_level_idx, len(self.levels) - 1))
        if hasattr(self, 'level_box'):
            self.level_box.blockSignals(True)
            self.level_box.clear()
            for l in self.levels:
                self.level_box.addItem(self._level_text(l))
            self.level_box.setCurrentIndex(self.current_level_idx)
            self.level_box.blockSignals(False)
        if hasattr(self, 'level_list'):
            self.level_list.blockSignals(True)
            self.level_list.clear()
            for l in self.levels:
                self.level_list.addItem(QListWidgetItem(self._level_text(l)))
            self.level_list.setCurrentRow(self.current_level_idx)
            self.level_list.blockSignals(False)
        self._apply_current_level()

    def _apply_current_level(self):
        l = self.levels[self.current_level_idx]
        self.canvas.set_current_level(l['name'], l['elev'])

    def _on_level_change(self, idx):
        if not (0 <= idx < len(self.levels)):
            return
        self.current_level_idx = idx
        if hasattr(self, 'level_list') and self.level_list.currentRow() != idx:
            self.level_list.blockSignals(True)
            self.level_list.setCurrentRow(idx)
            self.level_list.blockSignals(False)
        self._apply_current_level()
        self.record_edit()
        if self.view_tabs.currentIndex() == 1:
            self._refresh_3d()

    def _on_level_row(self, row):
        if 0 <= row < len(self.levels) and row != self.level_box.currentIndex():
            self.level_box.setCurrentIndex(row)

    def _level_add(self):
        dlg = LevelDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.levels.append(dlg.value())
            self.current_level_idx = len(self.levels) - 1
            self._refresh_level_widgets(); self.record_edit()

    def _level_edit(self):
        dlg = LevelDialog(self.levels[self.current_level_idx], parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.levels[self.current_level_idx] = dlg.value()
            self._refresh_level_widgets(); self.record_edit()

    def _level_remove(self):
        if len(self.levels) <= 1:
            return
        del self.levels[self.current_level_idx]
        self.current_level_idx = max(0, self.current_level_idx - 1)
        self._refresh_level_widgets(); self.record_edit()

    # ---- canvas events -------------------------------------------
    def _on_canvas_changed(self):
        self._sync_model()
        self.record_edit()
        self._update_status()
        if self.view_tabs.currentIndex() == 1:
            self._refresh_3d()

    def _on_pick_member(self, member):
        n = len(self.canvas.selected_set)
        self.delete_button.setEnabled(n > 0)
        if not hasattr(self, 'reassign_btn'):
            return
        self.reassign_btn.setEnabled(n > 0)
        if n == 0:
            self.pick_info.setText('ยังไม่ได้เลือก')
        elif n > 1:
            self.pick_info.setText(f'เลือก {n} ชิ้น')
        else:
            self.pick_info.setText(f"{KIND_TH[member['kind']]} · {member['section']}")

    def _reassign_selected(self):
        if self.canvas.selected is not None:
            self.canvas.set_selected_section(
                self._active_section_label(self.canvas.selected['kind']))
            self._on_pick_member(self.canvas.selected)

    def _on_canvas_mode(self, mode):
        if mode == 'select' and self.tool_group.button(0) is not None:
            self.tool_group.button(0).setChecked(True)
            self.detail.setCurrentIndex(0)

    def _on_snap(self, on):
        self.canvas.set_snap(on)

    def _on_grid_step(self, value):
        self.canvas.grid_cm = float(value)
        self.canvas.viewport().update()
        self.record_edit()

    def delete_selected(self):
        self.canvas.delete_selected()

    def clear_plan(self):
        self.canvas.clear()
        self._sync_model(); self.record_edit(); self._update_status(); self._refresh_3d()

    def _sync_model(self):
        self.model = self.canvas.to_state() if self.canvas.members else None

    def _update_status(self):
        n = len(self.canvas.members)
        by = {}
        for m in self.canvas.members:
            by[m['kind']] = by.get(m['kind'], 0) + 1
        if n == 0:
            self.status.setText('แปลนว่าง — เริ่มวาด member ได้เลย')
        else:
            parts = ', '.join(f"{KIND_TH[k]} {c}" for k, c in by.items())
            self.status.setText(f'{n} member บนแปลน ({parts}) — ยังไม่วิเคราะห์แรง')

    # ---- history -----------------------------------------------
    def state_snapshot(self):
        return {'plan': self.canvas.to_state(), 'storey_h': self.storey_h.value(),
                'sections': self.section_state(),
                'levels': [dict(l) for l in self.levels],
                'current_level_idx': self.current_level_idx}

    def history_buttons(self):
        if not hasattr(self, 'history'):
            return
        pending = self.state_snapshot() != self.history[self.history_index]
        self.undo_button.setEnabled(pending or self.history_index > 0)
        self.redo_button.setEnabled(not pending and self.history_index < len(self.history) - 1)

    def record_edit(self):
        if not hasattr(self, 'history'):
            return
        snap = self.state_snapshot()
        if snap != self.history[self.history_index]:
            self.history = self.history[:self.history_index + 1] + [snap]
            self.history = self.history[-50:]
            self.history_index = len(self.history) - 1
        self.history_buttons()

    def restore_state(self, snap):
        self.canvas.blockSignals(True)
        self.canvas.from_state(snap.get('plan'))
        self.canvas.blockSignals(False)
        self.storey_h.blockSignals(True)
        self.storey_h.setValue(float(snap.get('storey_h', 3.0)))
        self.storey_h.blockSignals(False)
        try:
            self.load_section_state(snap.get('sections'))
        except Exception:
            pass
        self.levels = _clean_levels(snap.get('levels'))
        self.current_level_idx = snap.get('current_level_idx', 0)
        self._refresh_level_widgets()
        self._sync_model(); self._update_status(); self._refresh_3d()

    def undo_model(self):
        self.record_edit()
        if self.history_index > 0:
            self.history_index -= 1
            self.restore_state(self.history[self.history_index])
            self.history_buttons()

    def redo_model(self):
        if self.state_snapshot() != self.history[self.history_index]:
            self.record_edit()
            return
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.restore_state(self.history[self.history_index])
            self.history_buttons()

    # ---- 3D preview ------------------------------------------
    def _refresh_3d(self):
        self.figure.clear()
        if not self.canvas.members:
            self.canvas3d.draw_idle(); return
        ax = self.figure.add_subplot(111, projection='3d')
        h = self.storey_h.value()
        xs, ys = [], []
        for m in self.canvas.members:
            if m['kind'] == 'grid':
                continue
            pts_m = [(x / 100.0, y / 100.0) for x, y in m['points']]
            for x, y in pts_m:
                xs.append(x); ys.append(y)
            color = KIND_COLOR[m['kind']]
            base = float(m.get('z', 0.0))          # level elevation (m)
            if m['kind'] in POINT_KINDS:
                x, y = pts_m[0]
                z1 = base
                z2 = base + (0.2 if m['kind'] == 'footing' else h)
                ax.plot([x, x], [y, y], [z1, z2], color=color, lw=3)
            elif m['kind'] in LINE_KINDS:
                (x1, y1), (x2, y2) = pts_m
                z = base + (h if m['kind'] == 'beam' else 0.0)
                ax.plot([x1, x2], [y1, y2], [z, z], color=color, lw=2.5)
            else:
                px = [p[0] for p in pts_m] + [pts_m[0][0]]
                py = [p[1] for p in pts_m] + [pts_m[0][1]]
                ax.plot(px, py, [base + h] * len(px), color=color, lw=2)
        ax.set(xlabel='X (m)', ylabel='Y (m)', zlabel='Z (m)')
        if xs and ys:
            sx = max(max(xs) - min(xs), 1.0)
            sy = max(max(ys) - min(ys), 1.0)
            ax.set_box_aspect((sx, sy, max(h, 1.0)))
        self.canvas3d.draw_idle()
        self.set_view(self.view_name)

    def set_view(self, name):
        self.view_name = name
        if self.figure.axes:
            ax = self.figure.axes[0]
            elev, azim = {'3D': (30, -60), 'บน XY': (90, -90),
                          'หน้า XZ': (0, -90), 'ข้าง YZ': (0, 0)}[name]
            ax.view_init(elev=elev, azim=azim)
            ax.set_proj_type('persp' if name == '3D' else 'ortho')
            hidden = {'บน XY': 'z', 'หน้า XZ': 'y', 'ข้าง YZ': 'x'}.get(name)
            for direction in ('x', 'y', 'z'):
                axis = getattr(ax, direction + 'axis')
                axis.pane.set_visible(name == '3D')
                if direction == hidden:
                    axis.set_ticks([])
                else:
                    axis.set_major_locator(AutoLocator())
            self.canvas3d.draw_idle()

    # ---- files -------------------------------------------------
    def write_model(self, path):
        if not self.canvas.members:
            raise ValueError('แปลนยังว่าง ยังไม่มีอะไรให้บันทึก')
        data = json.dumps({'format': 'rc-codepro-plan', 'version': 1,
                           'plan': self.canvas.to_state(),
                           'storey_h': self.storey_h.value(),
                           'sections': self.section_state(),
                           'levels': [dict(l) for l in self.levels],
                           'current_level_idx': self.current_level_idx},
                          ensure_ascii=False).encode('utf-8')
        out = QSaveFile(str(path))
        if not out.open(QIODevice.WriteOnly):
            raise OSError(out.errorString())
        if out.write(data) != len(data):
            out.cancelWriting(); raise OSError(out.errorString())
        if not out.commit():
            raise OSError(out.errorString())
        self.record_edit()

    def read_model(self, path):
        if Path(path).stat().st_size > 500_000:
            raise ValueError('ไฟล์โมเดลใหญ่เกินรูปแบบที่รองรับ')
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('ไฟล์ไม่ถูกต้อง')
        fmt, ver = data.get('format'), data.get('version')
        if fmt == 'rc-codepro-plan' and ver == 1:
            plan = data.get('plan')
            if not isinstance(plan, dict) or not isinstance(plan.get('members'), list):
                raise ValueError('ข้อมูลแปลนไม่ครบ')
            self.record_edit()
            self.canvas.from_state(plan)
            self.storey_h.blockSignals(True)
            self.storey_h.setValue(float(data.get('storey_h', 3.0) or 3.0))
            self.storey_h.blockSignals(False)
            secs = data.get('sections')
            if isinstance(secs, dict):
                try:
                    self.load_section_state(secs)
                except Exception:
                    pass
            if 'levels' in data:
                self.levels = _clean_levels(data.get('levels'))
                self.current_level_idx = data.get('current_level_idx', 0)
                self._refresh_level_widgets()
        elif fmt == 'rc-codepro-grid' and ver == 1:
            self.record_edit()
            self._import_legacy_grid(data.get('fields'))
        else:
            raise ValueError('ไม่รองรับรูปแบบหรือรุ่นของไฟล์นี้')
        self._sync_model(); self._update_status(); self._refresh_3d()
        self.record_edit()          # the loaded model is itself a history entry

    def _import_legacy_grid(self, fields):
        from desktop_app.building_grid import grid
        if not isinstance(fields, dict):
            raise ValueError('ไฟล์กริดเดิมไม่ครบ')
        try:
            xs = positive_list(fields['x']); ys = positive_list(fields['y'])
            hs = positive_list(fields['heights'])
            col = positive_list(fields['col']); beam = positive_list(fields['beam'])
        except (KeyError, ValueError):
            raise ValueError('ไฟล์กริดเดิมไม่ถูกต้อง')
        g = grid(x=','.join(map(str, xs)), y=','.join(map(str, ys)), n_floors=len(hs),
                 heights=hs, col=tuple(v / 100 for v in col[:2]),
                 beam=tuple(v / 100 for v in beam[:2]))
        self.canvas.from_state({'members': []})
        clbl = self._active_section_label('column')
        bbl = self._active_section_label('beam')
        for (px, py) in g['active_columns']:
            self.canvas.add_member('column', [(px * 100.0, py * 100.0)], clbl, emit=False)
        for b in g['beams']:
            (x1, y1), (x2, y2) = b['start'], b['end']
            self.canvas.add_member('beam', [(x1 * 100.0, y1 * 100.0),
                                            (x2 * 100.0, y2 * 100.0)], bbl, emit=False)
        self.canvas._scene.update()

    def save_model(self):
        path, _ = QFileDialog.getSaveFileName(self, 'บันทึกโมเดล', '', 'RC CodePro model (*.rcmodel)')
        if not path:
            return
        if not path.lower().endswith('.rcmodel'):
            path += '.rcmodel'
        try:
            self.write_model(path)
            self.status.setText('บันทึกแล้ว: ' + path)
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText('บันทึกไม่สำเร็จ: ' + str(exc))

    def open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, 'เปิดโมเดล', '', 'RC CodePro model (*.rcmodel)')
        if not path:
            return
        try:
            self.read_model(path)
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText('เปิดไม่สำเร็จ: ' + str(exc))
