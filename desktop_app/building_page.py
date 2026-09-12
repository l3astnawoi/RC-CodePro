"""Native Building Model — a free-draw 2D plan authoring page.

This round: the page opens EMPTY (no model). The user draws members on a
2D plan (Column / Beam / Slab / Footing / Stair) and assigns a named
section + material from the per-kind library ("C1 · 20x20 cm · 240 ksc").
Drawn members feed a read-only 3D preview, an auditable initial gravity
load-path calculation, and the .rcmodel file.  The gravity takedown is kept
separate from the legacy grid-frame stiffness engine.
"""
import math
import json
from copy import deepcopy
from pathlib import Path

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QLabel, QPushButton, QSplitter, QFileDialog, QComboBox, QTabWidget,
    QToolButton, QButtonGroup, QStackedWidget, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QCheckBox, QFrame, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QSizePolicy, QStyle,
    QInputDialog)
from PySide6.QtCore import Qt, QSaveFile, QIODevice, QSize, QRectF
from PySide6.QtGui import QIcon, QShortcut, QKeySequence, QColor, QPainter, QPalette, QPen, QBrush
from matplotlib.figure import Figure
from matplotlib.ticker import AutoLocator
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from desktop_app.home import icon_path
from desktop_app.steel_catalog import STEEL_SECTIONS
from desktop_app.plan_canvas import (PlanCanvas, KIND_TH, KIND_COLOR,
                                     POINT_KINDS, LINE_KINDS)
from desktop_app import recent_files

KN_TO_KG = 1000.0 / 9.80665


def _tinted_icon(icon, color='#60a5fa'):
    pixmap = icon.pixmap(32, 32)
    if pixmap.isNull():
        return icon
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()
    return QIcon(pixmap)


def positive_list(text):
    values = [float(v.strip()) for v in text.split(',')]
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('ระยะและความสูงต้องเป็นตัวเลขมากกว่า 0 คั่นด้วย comma')
    return values


# --- named-section library ------------------------------------------------
SECTION_SPEC = {
    'wall': [('t', 'หนา (cm)', 5, 100, 1, 15.0), ('fc', "f′c (ksc)", 100, 700, 0, 240.0)],
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
REBAR_SPEC = {
    'column': [('main_n', 'เหล็กยืน จำนวน', 4, 40, 0, 4), ('main_db', 'เหล็กยืน DB (mm)', 9, 40, 0, 16),
               ('tie_db', 'เหล็กปลอก RB/DB (mm)', 6, 20, 0, 9), ('tie_spacing', 'ระยะปลอก (cm)', 5, 40, 1, 15),
               ('cover', 'ระยะหุ้ม (cm)', 2, 10, 1, 4)],
    'beam': [('top_n', 'เหล็กบน จำนวน', 2, 20, 0, 2), ('top_db', 'เหล็กบน DB (mm)', 9, 40, 0, 16),
             ('bottom_n', 'เหล็กล่าง จำนวน', 2, 20, 0, 2), ('bottom_db', 'เหล็กล่าง DB (mm)', 9, 40, 0, 16),
             ('stirrup_db', 'เหล็กปลอก RB/DB (mm)', 6, 20, 0, 9), ('stirrup_spacing', 'ระยะปลอก (cm)', 5, 40, 1, 20),
             ('cover', 'ระยะหุ้ม (cm)', 2, 10, 1, 4)],
    'slab': [('main_db', 'เหล็กหลัก DB (mm)', 6, 25, 0, 12), ('main_spacing', 'ระยะเหล็กหลัก (cm)', 5, 40, 1, 20),
             ('distribution_db', 'เหล็กเสริม DB (mm)', 6, 25, 0, 9), ('distribution_spacing', 'ระยะเหล็กเสริม (cm)', 5, 40, 1, 20),
             ('cover', 'ระยะหุ้ม (cm)', 1.5, 8, 1, 2.5)],
    'wall': [('vertical_db', 'เหล็กตั้ง DB (mm)', 6, 32, 0, 12), ('vertical_spacing', 'ระยะเหล็กตั้ง (cm)', 5, 40, 1, 20),
             ('horizontal_db', 'เหล็กนอน DB (mm)', 6, 32, 0, 9), ('horizontal_spacing', 'ระยะเหล็กนอน (cm)', 5, 40, 1, 20),
             ('cover', 'ระยะหุ้ม (cm)', 2, 10, 1, 3)],
    'footing': [('bottom_db', 'เหล็กล่าง DB (mm)', 9, 40, 0, 16), ('bottom_spacing', 'ระยะเหล็กล่าง (cm)', 5, 40, 1, 20),
                ('cover', 'ระยะหุ้ม (cm)', 4, 15, 1, 7.5)],
    'stair': [('main_db', 'เหล็กหลัก DB (mm)', 6, 25, 0, 12), ('main_spacing', 'ระยะเหล็กหลัก (cm)', 5, 40, 1, 15),
              ('distribution_db', 'เหล็กกันร้าว DB (mm)', 6, 25, 0, 9), ('distribution_spacing', 'ระยะเหล็กกันร้าว (cm)', 5, 40, 1, 20),
              ('cover', 'ระยะหุ้ม (cm)', 1.5, 8, 1, 2.5)],
}


def rebar_summary(kind, values):
    if kind == 'beam':
        return f"บน {int(values.get('top_n', 2))}-DB{values.get('top_db', 16):g} · ล่าง {int(values.get('bottom_n', 2))}-DB{values.get('bottom_db', 16):g}"
    if kind == 'column':
        return f"{int(values.get('main_n', 4))}-DB{values.get('main_db', 16):g} · ปลอก DB{values.get('tie_db', 9):g}@{values.get('tie_spacing', 15):g} cm"
    if kind == 'footing':
        return f"ล่าง DB{values.get('bottom_db', 16):g}@{values.get('bottom_spacing', 20):g} cm"
    if kind == 'wall':
        return f"ตั้ง DB{values.get('vertical_db', 12):g}@{values.get('vertical_spacing', 20):g} · นอน DB{values.get('horizontal_db', 9):g}@{values.get('horizontal_spacing', 20):g} cm"
    return f"หลัก DB{values.get('main_db', 12):g}@{values.get('main_spacing', 20):g} · เสริม DB{values.get('distribution_db', 9):g}@{values.get('distribution_spacing', 20):g} cm"
DEFAULT_SECTIONS = {
    'wall': [{'name': 'W1', 't': 15.0, 'fc': 240.0, 'vertical_db': 12, 'vertical_spacing': 20,
              'horizontal_db': 9, 'horizontal_spacing': 20, 'cover': 3}],
    'column': [{'name': 'C1', 'b': 20.0, 'h': 20.0, 'fc': 240.0, 'main_n': 4, 'main_db': 16,
                'tie_db': 9, 'tie_spacing': 15, 'cover': 4}],
    'beam': [{'name': 'B1', 'b': 20.0, 'h': 40.0, 'fc': 240.0, 'top_n': 2, 'top_db': 16,
              'bottom_n': 2, 'bottom_db': 16, 'stirrup_db': 9, 'stirrup_spacing': 20, 'cover': 4}],
    'slab': [{'name': 'S1', 't': 12.0, 'fc': 240.0, 'main_db': 12, 'main_spacing': 20,
              'distribution_db': 9, 'distribution_spacing': 20, 'cover': 2.5}],
    'footing': [{'name': 'F1', 'Lx': 150.0, 'Ly': 150.0, 'depth': 40.0, 'fc': 240.0,
                 'bottom_db': 16, 'bottom_spacing': 20, 'cover': 7.5}],
    'stair': [{'name': 'ST1', 'waist': 15.0, 'steps': 12.0, 'fc': 240.0, 'main_db': 12,
               'main_spacing': 15, 'distribution_db': 9, 'distribution_spacing': 20, 'cover': 2.5}],
}
DEFAULT_PILE_SECTIONS = [
    {'name': 'P1', 'shape': 'square', 'b_cm': 30.0, 'h_cm': 30.0,
     'length_m': 12.0, 'capacity_kn': 600.0},
]
TOOLS = [('เลือก', 'select'), ('View', 'view'), ('กริด', 'grid'), ('ฐานราก', 'footing'),
         ('เสา', 'column'), ('คาน', 'beam'), ('พื้น', 'slab'), ('บันได', 'stair'),
         ('กำแพง', 'wall')]
EDIT_RAIL = [('Select', 'select', 'select'), ('Move', 'move', 'transform-move'),
             ('Copy', 'copy', 'edit-copy'), ('Cut', 'cut', 'edit-cut'),
             ('Delete', 'delete', 'edit-delete'), ('Rotate', 'rotate', 'object-rotate-right'),
             ('Undo', 'undo', 'edit-undo'), ('Redo', 'redo', 'edit-redo')]


def section_label(kind, s):
    if s.get('material') == 'steel':
        return f"เหล็ก · {s['name']} mm · {s['weight_kg_m']:g} kg/m"
    if kind in ('column', 'beam'):
        return f"{s['name']} · {s['b']:g}×{s['h']:g} cm · {s['fc']:g} ksc"
    if kind in ('slab', 'wall'):
        return f"{s['name']} · t {s['t']:g} cm · {s['fc']:g} ksc"
    if kind == 'footing':
        return f"{s['name']} · {s['Lx']:g}×{s['Ly']:g} cm · d {s['depth']:g} · {s['fc']:g} ksc"
    return f"{s['name']} · ท้องพื้น {s['waist']:g} cm · {s['steps']:g} ขั้น · {s['fc']:g} ksc"


class SectionPreview(QWidget):
    def __init__(self, dialog):
        super().__init__(dialog); self.dialog = dialog
        self.setMinimumSize(320, 330)

    def paintEvent(self, _event):
        d = self.dialog; values = {k: w.value() for k, w in d.inputs.items()}
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#101419'))
        margin = 44; area = self.rect().adjusted(margin, margin, -margin, -80)
        kind = d.kind
        if kind in ('column', 'beam'):
            width, height = values['b'], values['h']
        elif kind == 'footing':
            width, height = values['Lx'], values['depth']
        else:
            width, height = max(values.get('t', values.get('waist', 15)) * 5, 80), values.get('t', values.get('waist', 15))
        scale = min(area.width()/max(width, 1), area.height()/max(height, 1))
        rw, rh = width*scale, height*scale
        concrete = QRectF(area.center().x()-rw/2, area.center().y()-rh/2, rw, rh)
        painter.setPen(QPen(QColor('#60a5fa'), 3)); painter.setBrush(QBrush(QColor('#dbeafe')))
        painter.drawRect(concrete)
        cover = min(values.get('cover', 3)*scale, min(rw, rh)/4)
        inner = concrete.adjusted(cover, cover, -cover, -cover)
        painter.setPen(QPen(QColor('#f59e0b'), 2, Qt.DashLine)); painter.setBrush(Qt.NoBrush)
        painter.drawRect(inner)
        painter.setPen(QPen(QColor('#dc2626'), 2)); painter.setBrush(QBrush(QColor('#ef4444')))
        if kind == 'beam':
            for n, y in ((int(values['top_n']), inner.top()), (int(values['bottom_n']), inner.bottom())):
                for i in range(max(n, 1)):
                    x = inner.center().x() if n == 1 else inner.left()+i*inner.width()/(n-1)
                    painter.drawEllipse(QRectF(x-5, y-5, 10, 10))
        elif kind == 'column':
            n = max(4, int(values['main_n']))
            perimeter = [(inner.left(), inner.top()), (inner.right(), inner.top()),
                         (inner.right(), inner.bottom()), (inner.left(), inner.bottom())]
            for i in range(n):
                edge = i*4/n; j = int(edge) % 4; t = edge-int(edge)
                a, b = perimeter[j], perimeter[(j+1) % 4]
                x, y = a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t
                painter.drawEllipse(QRectF(x-5, y-5, 10, 10))
        else:
            count = 7
            y = inner.bottom()
            for i in range(count):
                x = inner.left()+i*inner.width()/(count-1)
                painter.drawEllipse(QRectF(x-4, y-4, 8, 8))
        painter.setPen(QColor('#e2e8f0'))
        painter.drawText(QRectF(12, 8, self.width()-24, 28), Qt.AlignCenter, f'หน้าตัด{KIND_TH[kind]}')
        painter.drawText(QRectF(12, self.height()-62, self.width()-24, 50), Qt.AlignCenter | Qt.TextWordWrap,
                         d.rebar_summary(values))


class SectionDialog(QDialog):
    def __init__(self, kind, initial=None, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle(f"หน้าตัด{KIND_TH[kind]}")
        root = QHBoxLayout(self); editor = QWidget(); form = QFormLayout(editor); root.addWidget(editor, 1)
        self.name = QLineEdit((initial or {}).get('name', ''))
        self.name.setPlaceholderText(kind[0].upper() + '1')
        form.addRow('ชื่อหน้าตัด', self.name)
        self.inputs = {}
        for key, label, mn, mx, dp, dv in SECTION_SPEC[kind]:
            w = QDoubleSpinBox(); w.setRange(mn, mx); w.setDecimals(dp)
            w.setValue(float((initial or {}).get(key, dv)))
            self.inputs[key] = w
            form.addRow(label, w)
        form.addRow(QLabel('<b>เหล็กเสริม</b>'))
        for key, label, mn, mx, dp, dv in REBAR_SPEC[kind]:
            w = QDoubleSpinBox(); w.setRange(mn, mx); w.setDecimals(dp); w.setSingleStep(1 if dp == 0 else 0.5)
            w.setValue(float((initial or {}).get(key, dv))); self.inputs[key] = w; form.addRow(label, w)
        self.preview = SectionPreview(self); root.addWidget(self.preview, 1)
        for widget in self.inputs.values():
            widget.valueChanged.connect(self.preview.update)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        form.addRow(box)
        self.resize(760, 520)

    def rebar_summary(self, values=None):
        v = values or {k: w.value() for k, w in self.inputs.items()}
        if self.kind == 'beam':
            return f"บน {int(v['top_n'])}-DB{v['top_db']:g} · ล่าง {int(v['bottom_n'])}-DB{v['bottom_db']:g}\nปลอก DB{v['stirrup_db']:g} @ {v['stirrup_spacing']:g} cm"
        if self.kind == 'column':
            return f"{int(v['main_n'])}-DB{v['main_db']:g} · ปลอก DB{v['tie_db']:g} @ {v['tie_spacing']:g} cm"
        if self.kind == 'footing':
            return f"เหล็กล่าง DB{v['bottom_db']:g} @ {v['bottom_spacing']:g} cm สองทิศทาง"
        if self.kind == 'wall':
            return f"ตั้ง DB{v['vertical_db']:g}@{v['vertical_spacing']:g} · นอน DB{v['horizontal_db']:g}@{v['horizontal_spacing']:g} cm"
        return f"หลัก DB{v['main_db']:g}@{v['main_spacing']:g} · เสริม DB{v['distribution_db']:g}@{v['distribution_spacing']:g} cm"

    def value(self):
        out = {'name': self.name.text().strip() or self.name.placeholderText()}
        out.update({k: w.value() for k, w in self.inputs.items()})
        return out


def pile_section_label(spec):
    size = (f"Ø {spec['b_cm']:g} cm" if spec.get('shape') == 'circular'
            else f"{spec['b_cm']:g}×{spec['h_cm']:g} cm")
    return (f"{spec['name']} · {size} · L {spec['length_m']:g} m · "
            f"Qa {spec['capacity_kn'] * KN_TO_KG:,.0f} kg/ต้น")


class PileSectionDialog(QDialog):
    def __init__(self, initial=None, parent=None):
        super().__init__(parent); initial = initial or {}
        self.setWindowTitle('หน้าตัดและกำลังรับแรงเสาเข็ม')
        form = QFormLayout(self)
        self.name = QLineEdit(str(initial.get('name', 'P1'))); form.addRow('ชื่อหน้าตัด', self.name)
        self.shape = QComboBox(); self.shape.addItem('สี่เหลี่ยม', 'square'); self.shape.addItem('กลม', 'circular')
        self.shape.setCurrentIndex(max(0, self.shape.findData(initial.get('shape', 'square')))); form.addRow('รูปทรง', self.shape)
        self.b = QDoubleSpinBox(); self.b.setRange(10, 300); self.b.setValue(float(initial.get('b_cm', 30))); self.b.setSuffix(' cm')
        self.h = QDoubleSpinBox(); self.h.setRange(10, 300); self.h.setValue(float(initial.get('h_cm', 30))); self.h.setSuffix(' cm')
        self.length = QDoubleSpinBox(); self.length.setRange(0.5, 100); self.length.setDecimals(2); self.length.setValue(float(initial.get('length_m', 12))); self.length.setSuffix(' m')
        self.capacity = QDoubleSpinBox(); self.capacity.setRange(1, 10_000_000)
        self.capacity.setValue(float(initial.get('capacity_kn', 600)) * KN_TO_KG); self.capacity.setSuffix(' kg/ต้น')
        form.addRow('กว้าง / Diameter', self.b); form.addRow('สูง', self.h)
        form.addRow('ความยาวเสาเข็ม', self.length); form.addRow('กำลังรับแรงอนุญาต Qa', self.capacity)
        self.shape.currentIndexChanged.connect(lambda: self.h.setEnabled(self.shape.currentData() != 'circular'))
        self.h.setEnabled(self.shape.currentData() != 'circular')
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject); form.addRow(box)

    def value(self):
        b = self.b.value()
        return {'name': self.name.text().strip() or 'P1', 'shape': self.shape.currentData(),
                'b_cm': b, 'h_cm': b if self.shape.currentData() == 'circular' else self.h.value(),
                'length_m': self.length.value(), 'capacity_kn': self.capacity.value() / KN_TO_KG}


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


def _style_dark_combo_popup(combo):
    """Keep native Windows combo popups readable with the dark app theme."""
    popup = combo.view()
    palette = popup.palette()
    palette.setColor(QPalette.Base, QColor('#222831'))
    palette.setColor(QPalette.AlternateBase, QColor('#222831'))
    palette.setColor(QPalette.Text, QColor('#f8fafc'))
    palette.setColor(QPalette.Highlight, QColor('#1673d3'))
    palette.setColor(QPalette.HighlightedText, QColor('#ffffff'))
    popup.setPalette(palette)


class BuildingPage(QWidget):
    def __init__(self, project=None):
        super().__init__()
        self.project = project
        self.model = None            # user plan dict, or None when empty
        self.result = None
        self.sections = {k: [dict(s) for s in v] for k, v in DEFAULT_SECTIONS.items()}
        for kind in ('column', 'beam'):
            self.sections[kind].extend(dict(s) for s in STEEL_SECTIONS)
        self.applied = {k: 0 for k in SECTION_SPEC}
        self.pile_sections = [dict(s) for s in DEFAULT_PILE_SECTIONS]
        self._pickers = {}
        self.material_pickers = {}; self.family_pickers = {}; self.section_info = {}; self.section_buttons = {}
        # drawing levels / elevations (item: "ระดับฐานราก -1.50", "พื้นชั้น 1 +0.55")
        self.levels = [{'name': 'พื้นชั้น 1', 'elev': 0.0}]
        self.current_level_idx = 0
        self.current_model_path = None
        self.member_clipboard = []
        self._paste_generation = 0
        self.tool_side_external = False

        root = QVBoxLayout(self)
        self.workspace_title = QLabel('<h2>Building Model · แปลน 2D</h2>')
        root.addWidget(self.workspace_title)

        self.member_toolbar = QFrame()
        bar = QHBoxLayout(self.member_toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(QLabel('ระดับ Cut Plan (m)'))
        self.cut_plan = QDoubleSpinBox(); self.cut_plan.setRange(-50.0, 200.0)
        self.cut_plan.setDecimals(2); self.cut_plan.setSingleStep(0.10); self.cut_plan.setValue(0.0)
        self.cut_plan.setToolTip('ระดับตัดเทียบจากระดับที่กำลังเขียน และมองลงด้านล่าง')
        bar.addWidget(self.cut_plan)
        # Commands remain available from File/Edit and the left edit rail.
        self.undo_button = QPushButton('ย้อนกลับ'); self.undo_button.clicked.connect(self.undo_model)
        self.redo_button = QPushButton('ทำซ้ำ'); self.redo_button.clicked.connect(self.redo_model)
        self.delete_button = QPushButton('ลบที่เลือก'); self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected)
        bar.addStretch(1)
        bar.addWidget(QLabel('ระดับที่กำลังเขียน'))
        self.level_box = QComboBox(); self.level_box.setMinimumWidth(150)
        self.level_box.setObjectName('workspaceLevel')
        _style_dark_combo_popup(self.level_box)
        self.level_box.currentIndexChanged.connect(self._on_level_change)
        bar.addWidget(self.level_box)
        self.snap_check = QCheckBox('Snap กริด / Member')
        self.snap_check.setObjectName('workspaceSnap'); self.snap_check.setChecked(True)
        self.snap_check.toggled.connect(self._on_snap)
        bar.addWidget(self.snap_check)
        bar.addWidget(QLabel('ความสูงชั้น (m)'))
        self.storey_h = QDoubleSpinBox(); self.storey_h.setRange(1.5, 10.0)
        self.storey_h.setValue(3.0); self.storey_h.setSingleStep(0.1)
        self.storey_h.valueChanged.connect(lambda _=0: (self.record_edit(), self._refresh_3d()))
        bar.addWidget(self.storey_h)
        root.addWidget(self.member_toolbar)

        split = QSplitter(Qt.Horizontal); root.addWidget(split, 1)
        self.workspace_splitter = split
        self.tool_side = self._build_toolside()
        split.addWidget(self.tool_side)

        self.view_tabs = QTabWidget()
        self.canvas = PlanCanvas()
        self.cut_plan.valueChanged.connect(self.canvas.set_cut_plane)
        self.canvas.member_height = self.storey_h.value
        self.canvas.drawing_properties = lambda kind: dict(self.draw_properties[kind].defaults or {})
        self.canvas.set_section_lookup(self._active_section_label)
        self.canvas.set_section_spec_lookup(self._section_spec_for_canvas)
        self.canvas.changed.connect(self._on_canvas_changed)
        self.canvas.picked.connect(self._on_pick_member)
        self.canvas.mode_changed.connect(self._on_canvas_mode)
        plan = QWidget(); plan_layout = QVBoxLayout(plan); plan_layout.setContentsMargins(0, 0, 0, 0)
        plan_layout.addWidget(self.canvas)
        level_row = QHBoxLayout(); level_row.addWidget(QLabel('ระดับวาด (Elevation)'))
        self.plan_level_box = QComboBox()
        _style_dark_combo_popup(self.plan_level_box)
        self.plan_level_box.currentIndexChanged.connect(self._on_level_change)
        level_row.addWidget(self.plan_level_box, 1); plan_layout.addLayout(level_row)
        self.other_levels_button = QPushButton('แสดงชั้นอื่น: เปิด')
        self.other_levels_button.setCheckable(True); self.other_levels_button.setChecked(True)
        self.other_levels_button.setToolTip('เปิด: แสดงต่างระดับจาง ๆ · ปิด: แสดงเฉพาะระดับที่กำลังวาด')
        self.other_levels_button.toggled.connect(self.canvas.set_show_other_levels)
        self.other_levels_button.toggled.connect(lambda on: self.other_levels_button.setText('แสดงชั้นอื่น: เปิด' if on else 'แสดงชั้นอื่น: ปิด'))
        level_row.addWidget(self.other_levels_button)
        self.view_tabs.addTab(plan, 'แปลน 2D')

        view3d = QWidget(); v3 = QVBoxLayout(view3d); v3.setContentsMargins(0, 0, 0, 0); v3.setSpacing(3)
        self.view3d_layout = v3; self.fullscreen_dialog = None
        self.figure = Figure(); self.canvas3d = FigureCanvasQTAgg(self.figure)
        self.figure.set_layout_engine(None); self.figure.patch.set_facecolor('#101419')
        self.canvas3d.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        from desktop_app.model_interaction import ModelInteraction
        self.model_interaction = ModelInteraction(self)
        self.view_name = '3D'
        vb = QHBoxLayout()
        for name in ('3D', 'บน XY', 'หน้า XZ', 'ข้าง YZ'):
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, s=name: self.set_view(s))
            vb.addWidget(b)
        v3.addLayout(vb)
        fit_button = QPushButton('Fit Model'); fit_button.clicked.connect(self.fit_model)
        vb.addWidget(fit_button)
        fullscreen_button = QPushButton('Full Screen'); fullscreen_button.clicked.connect(self.show_3d_fullscreen)
        vb.addWidget(fullscreen_button)
        v3.addWidget(self.canvas3d, 1)
        self.view_tabs.addTab(view3d, 'โมเดล 3D')
        side = QWidget(); side_layout = QVBoxLayout(side); side_layout.setContentsMargins(0,0,0,0)
        side_bar = QHBoxLayout(); side_bar.addWidget(QLabel('Side View บนกริด'))
        self.side_grid_box = QComboBox(); self.side_grid_box.setMinimumWidth(220)
        self.side_grid_box.currentIndexChanged.connect(self._on_side_grid)
        side_bar.addWidget(self.side_grid_box, 1)
        side_layout.addLayout(side_bar)
        from desktop_app.side_view import SideViewCanvas
        self.side_canvas = SideViewCanvas(self); side_layout.addWidget(self.side_canvas, 1)
        self.view_tabs.addTab(side, 'Side View 2D')

        self.view_tabs.currentChanged.connect(self._on_view_tab)
        split.addWidget(self.view_tabs); split.setStretchFactor(1, 1)
        split.setSizes([310, 900])

        self.status = QLabel(); self.status.setWordWrap(True); root.addWidget(self.status)

        self._refresh_section_pickers()
        self._refresh_level_widgets()
        # Seed the framework with grid A (vertical) and grid 1 (horizontal)
        # crossing at the origin (X, Y = 0, 0).
        self.canvas.add_grid('v', 0.0, emit=False)
        self.canvas.add_grid('h', 0.0, emit=False)
        self._refresh_side_grids()
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

    @staticmethod
    def member_kind_names():
        return [(key, KIND_TH[key]) for key in
                ('beam', 'column', 'slab', 'footing', 'stair', 'wall')]

    def select_kind_on_current_level(self, kind):
        level = self.levels[self.current_level_idx]['name']
        self.canvas.set_mode('select')
        self.canvas.select_members([m for m in self.canvas.members
                                    if m.get('kind') == kind and m.get('level') == level])

    def copy_selected(self):
        selected_ids = {id(member) for member in self.canvas.selected_set
                        if member.get('kind') != 'grid'}
        state_members = self.canvas.to_state().get('members', [])
        self.member_clipboard = [deepcopy(raw) for member, raw in
                                 zip(self.canvas.members, state_members)
                                 if id(member) in selected_ids]
        self._paste_generation = 0
        return len(self.member_clipboard)

    def cut_selected(self):
        if self.copy_selected():
            self.canvas.delete_selected()

    def paste_members(self):
        if not self.member_clipboard:
            return []
        self._paste_generation += 1
        offset = 30.0 * self._paste_generation
        pasted = []
        for raw in deepcopy(self.member_clipboard):
            kind = raw.get('kind')
            if kind not in KIND_TH or kind == 'grid':
                continue
            points = [(float(p[0]) + offset, float(p[1]) + offset)
                      for p in raw.get('points', [])]
            if not points:
                continue
            member = self.canvas.add_member(
                kind, points, raw.get('section'), emit=False, level=raw.get('level'))
            for key in ('z', 'z_start', 'z_end', 'slab_type', 'slab_direction',
                        'wall_role', 'wall_connection', 'support_type',
                        'foundation_system', 'q_allow_kn_m2', 'pile_section',
                        'pile_count'):
                if key in raw:
                    member[key] = deepcopy(raw[key])
            if kind == 'slab':
                self.canvas._slab_symbol(member)
            pasted.append(member)
        if pasted:
            self.canvas.select_members(pasted)
            self.canvas.changed.emit()
        return pasted

    # ---- gravity load path -----------------------------------------
    def _build_load_transfer_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        title = QLabel('<b>การถ่ายแรงแนวดิ่ง · ACI 318M-19</b>')
        layout.addWidget(title)
        note = QLabel('คำนวณน้ำหนักตัวเองและถ่ายแรง พื้น → คาน/ผนัง → เสา/ผนัง → ฐานราก\n'
                      'D และ L เป็นค่าบรรทุกใช้งานของโครงการ; U = 1.2D + 1.6L ต้องตรวจสอบกับกฎหมายอาคารที่ใช้')
        note.setWordWrap(True); layout.addWidget(note)
        form = QFormLayout(); layout.addLayout(form)
        self.load_density = QDoubleSpinBox(); self.load_density.setRange(1.0, 100000.0)
        self.load_density.setDecimals(2); self.load_density.setValue(24.0 * KN_TO_KG); self.load_density.setSuffix(' kg/m³')
        self.load_sdl = QDoubleSpinBox(); self.load_sdl.setRange(0.0, 100000.0)
        self.load_sdl.setDecimals(2); self.load_sdl.setValue(1.0 * KN_TO_KG); self.load_sdl.setSuffix(' kg/m²')
        self.load_live = QDoubleSpinBox(); self.load_live.setRange(0.0, 100000.0)
        self.load_live.setDecimals(2); self.load_live.setValue(2.0 * KN_TO_KG); self.load_live.setSuffix(' kg/m²')
        self.load_wind = QDoubleSpinBox(); self.load_wind.setRange(0.0, 100000.0)
        self.load_wind.setDecimals(2); self.load_wind.setValue(0.0); self.load_wind.setSuffix(' kg/m²')
        self.load_wind.setToolTip('ค่าความดันลมของโครงการ เก็บไว้สำหรับการวิเคราะห์แรงด้านข้าง')
        form.addRow('คอนกรีต γ', self.load_density)
        form.addRow('Dead Load · SDL เพิ่มเติม', self.load_sdl)
        form.addRow('Live Load', self.load_live)
        form.addRow('Wind Load', self.load_wind)
        wind_note = QLabel('Wind Load บันทึกเป็นแรงด้านข้างของโครงการ และยังไม่รวมในผลการถ่ายแรงแนวดิ่ง')
        wind_note.setWordWrap(True); layout.addWidget(wind_note)
        for spin in (self.load_density, self.load_sdl, self.load_live, self.load_wind):
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self._invalidate_load_result)
        run = QPushButton('คำนวณการถ่ายแรง'); run.clicked.connect(self.run_load_transfer)
        layout.addWidget(run)
        self.load_summary = QLabel('ยังไม่ได้คำนวณ'); self.load_summary.setWordWrap(True)
        layout.addWidget(self.load_summary)
        self.load_table = QTableWidget(0, 9)
        self.load_table.setHorizontalHeaderLabels(['Member', 'ประเภท', 'ระบบ', 'หน้าตัด', 'D (kg)', 'L (kg)', 'U (kg)', 'Mu (kg·m)', 'ส่งต่อไป'])
        self.load_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.load_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.load_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.load_table.cellClicked.connect(self._select_load_member)
        layout.addWidget(self.load_table, 1)
        layout.addWidget(QLabel('<b>Diagnostics / จุดที่ต้องแก้ในโมเดล</b>'))
        self.load_diagnostics = QListWidget(); self.load_diagnostics.setMaximumHeight(130)
        layout.addWidget(self.load_diagnostics)
        return page

    def _select_load_member(self, row, column):
        if column != 0 or not self.result:
            return
        item = self.load_table.item(row, 0)
        member_id = item.data(Qt.UserRole) if item is not None else None
        counters = {}
        target = None
        for member in self.canvas.members:
            if member.get('kind') == 'grid':
                continue
            kind = member.get('kind'); counters[kind] = counters.get(kind, 0) + 1
            if f"{str(kind).upper()}-{counters[kind]:03d}" == member_id:
                target = member; break
        if target is None:
            return
        self.view_tabs.setCurrentIndex(0)
        level_index = next((i for i, level in enumerate(self.levels)
                            if level['name'] == target.get('level')), None)
        if level_index is not None and level_index != self.current_level_idx:
            self._on_level_change(level_index)
        self.canvas.set_mode('select')
        self.canvas.select_member(target)
        self.canvas.ensureVisible(target['item'], 80, 80)

    def _load_settings(self):
        if not hasattr(self, 'load_density'):
            return {'concrete_density_kn_m3': 24.0, 'sdl_kn_m2': 1.0,
                    'live_kn_m2': 2.0, 'wind_kn_m2': 0.0}
        return {'concrete_density_kn_m3': self.load_density.value() / KN_TO_KG,
                'sdl_kn_m2': self.load_sdl.value() / KN_TO_KG,
                'live_kn_m2': self.load_live.value() / KN_TO_KG,
                'wind_kn_m2': self.load_wind.value() / KN_TO_KG}

    def _set_load_settings(self, settings):
        if not isinstance(settings, dict) or not hasattr(self, 'load_density'):
            return
        for widget, key in ((self.load_density, 'concrete_density_kn_m3'),
                            (self.load_sdl, 'sdl_kn_m2'),
                            (self.load_live, 'live_kn_m2'),
                            (self.load_wind, 'wind_kn_m2')):
            value = settings.get(key)
            if isinstance(value, (int, float)):
                widget.blockSignals(True); widget.setValue(float(value) * KN_TO_KG); widget.blockSignals(False)

    def _invalidate_load_result(self, _value=None):
        self.result = None
        if hasattr(self, 'load_summary'):
            self.load_summary.setText('ข้อมูลเปลี่ยนแล้ว — กดคำนวณการถ่ายแรงอีกครั้ง')
        if hasattr(self, 'history'):
            self.record_edit(); self._update_status()

    def _section_library(self):
        library = {section_label(kind, spec): dict(spec)
                   for kind, rows in self.sections.items() for spec in rows}
        library.update({spec['name']: dict(spec) for spec in self.pile_sections})
        return library

    def _section_spec_for_canvas(self, kind, label):
        return next((dict(spec) for spec in self.sections.get(kind, [])
                     if section_label(kind, spec) == label), {})

    def _set_true_scale_view(self, enabled):
        self.canvas.set_true_scale_members(enabled)
        if hasattr(self, 'history'):
            self.record_edit()

    def _set_member_label_view(self, kind, visible):
        self.canvas.set_member_labels(kind, visible)
        if hasattr(self, 'history'):
            self.record_edit()

    def _sync_view_controls(self):
        if not hasattr(self, 'true_scale_check'):
            return
        self.true_scale_check.blockSignals(True)
        self.true_scale_check.setChecked(self.canvas.true_scale_members)
        self.true_scale_check.blockSignals(False)
        self.cut_plan.blockSignals(True)
        self.cut_plan.setValue(self.canvas.cut_plane_offset)
        self.cut_plan.blockSignals(False)
        for kind, check in self.member_label_checks.items():
            check.blockSignals(True)
            check.setChecked(self.canvas.member_label_visibility.get(kind, True))
            check.blockSignals(False)

    def run_load_transfer(self):
        from utils.free_draw_load_transfer import run_free_draw_load_transfer
        self._sync_model()
        self.result = run_free_draw_load_transfer(
            self.canvas.to_state(), self._section_library(), self._load_settings())
        self._render_load_result()
        self._update_status()

    def _render_load_result(self):
        result = self.result or {}; summary = result.get('summary', {})
        kg = lambda value: float(value or 0.0) * KN_TO_KG
        self.load_summary.setText(
            f"สถานะ: {result.get('status', '—')} · มาตรฐานคอนกรีต: {result.get('design_standard', '—')}\n"
            f"แรงที่ใส่ D = {kg(summary.get('applied_D_kn')):,.2f} kg, L = {kg(summary.get('applied_L_kn')):,.2f} kg · "
            f"ถึงฐาน D = {kg(summary.get('base_D_kn')):,.2f} kg, L = {kg(summary.get('base_L_kn')):,.2f} kg · "
            f"U ที่ฐาน = {kg(summary.get('factored_base_U_kn')):,.2f} kg\n"
            f"แรงที่เส้นทางยังไม่ครบ D = {kg(summary.get('unresolved_D_kn')):,.2f} kg, "
            f"L = {kg(summary.get('unresolved_L_kn')):,.2f} kg · "
            f"Wind ที่บันทึก = {self.load_wind.value():,.2f} kg/m² (ไม่รวมในแรงแนวดิ่ง)")
        rows = result.get('members', [])
        self.load_table.setRowCount(len(rows))
        for row, member in enumerate(rows):
            system = {'cantilever': 'คานยื่น', 'two_end_supported': 'รองรับ 2 ปลาย',
                      'unsupported': 'ไม่มีจุดรองรับ', 'invalid_ambiguous': 'จุดรองรับกำกวม'}.get(
                          member.get('support_condition'), '—')
            if member.get('kind') == 'wall':
                system = ('Structural Wall' if member.get('wall_role') == 'structural'
                          else 'Non-bearing Wall')
            if member.get('kind') == 'footing':
                support = 'Fixed' if member.get('support_type') == 'fixed' else 'Pin'
                if member.get('foundation_system') == 'pile':
                    util = member.get('capacity_utilization')
                    system = f"{support} · เสาเข็ม {member.get('pile_count', 1)} ต้น"
                    if util is not None:
                        system += f" · ใช้ {util*100:.0f}%"
                else:
                    pressure = member.get('service_pressure_kn_m2')
                    system = f"{support} · ฐานแผ่"
                    if pressure is not None and math.isfinite(pressure):
                        system += f" · q={pressure * KN_TO_KG:,.1f} kg/m²"
            values = (member.get('member_id', ''), KIND_TH.get(member.get('kind'), member.get('kind', '')),
                      system, member.get('section', ''), f"{kg(member.get('dead_kn')):,.2f}",
                      f"{kg(member.get('live_kn')):,.2f}", f"{kg(member.get('factored_u_kn')):,.2f}",
                      f"{kg(member.get('factored_Mu_knm')):,.2f}",
                      ', '.join(member.get('transfers_to', [])) or '—')
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, member.get('member_id'))
                    item.setForeground(QColor('#2563eb'))
                    font = item.font(); font.setUnderline(True); item.setFont(font)
                    item.setToolTip('คลิกเพื่อเลือก Member นี้ใน Plan 2D')
                self.load_table.setItem(row, col, item)
        self.load_diagnostics.clear()
        diagnostics = result.get('diagnostics', [])
        if not diagnostics:
            self.load_diagnostics.addItem('✓ เส้นทางแรงครบตามขอบเขตการคำนวณเริ่มต้น')
        for item in diagnostics:
            icon = '⛔' if item.get('severity') == 'BLOCKING' else '⚠'
            self.load_diagnostics.addItem(f"{icon} {item.get('code')}: {item.get('message')}")

    # ---- left rail ---------------------------------------------------
    def _build_toolside(self):
        self.draw_properties = {}
        wrap = QWidget(); lay = QHBoxLayout(wrap); lay.setContentsMargins(0, 0, 0, 0)
        rail = QVBoxLayout(); rail.setSpacing(4)
        self.tool_group = QButtonGroup(self); self.tool_group.setExclusive(True)
        self.detail = QStackedWidget()
        self.detail_indices = {}
        for i, (label, key) in enumerate(TOOLS):
            self.detail_indices[key] = self.detail.addWidget(self._detail_page(key))
        self.load_detail_index = self.detail.addWidget(self._detail_page('load'))
        self.edit_buttons = {}
        standard_icons = {
            'move': QStyle.SP_ArrowRight, 'copy': QStyle.SP_FileLinkIcon,
            'cut': QStyle.SP_DialogDiscardButton, 'delete': QStyle.SP_TrashIcon,
            'rotate': QStyle.SP_BrowserReload, 'undo': QStyle.SP_ArrowLeft,
            'redo': QStyle.SP_ArrowRight,
        }
        for i, (label, key, theme_icon) in enumerate(EDIT_RAIL):
            btn = QToolButton(); btn.setObjectName('toolRailBtn')
            btn.setCheckable(key == 'select')
            if key == 'select':
                icon = QIcon(icon_path('select'))
            else:
                icon = QIcon.fromTheme(theme_icon, self.style().standardIcon(standard_icons[key]))
            btn.setText(label); btn.setIcon(_tinted_icon(icon))
            btn.setIconSize(QSize(22, 22)); btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setFixedSize(72, 54); btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, command=key: self._run_edit_command(command))
            self.edit_buttons[key] = btn
            if key == 'select':
                self.tool_group.addButton(btn, 0)
            rail.addWidget(btn)
        rail.addStretch(1)
        railw = QWidget(); railw.setLayout(rail); railw.setFixedWidth(82)
        lay.addWidget(railw); lay.addWidget(self.detail, 1)
        self.tool_group.button(0).setChecked(True)
        return wrap

    def _select_tool(self, key, idx=None):
        detail_index = self.detail_indices.get(key, idx)
        if detail_index is not None:
            self.detail.setCurrentIndex(detail_index)
        if key == 'grid':
            self.canvas.set_mode('grid')
        elif key in ('load', 'view'):
            self.canvas.set_mode('select')
        else:
            self.canvas.set_mode(key if key in KIND_TH else 'select')
        self.side_canvas.set_mode(self.canvas.mode)

    def select_tool(self, key):
        if key == 'select':
            self.edit_buttons['select'].setChecked(True)
        self._select_tool(key, self.detail_indices.get(key, 0))

    def _return_to_select(self):
        self.edit_buttons['select'].setChecked(True)
        self.canvas.set_mode('select')

    def _run_edit_command(self, command):
        if command == 'select':
            self.select_tool('select'); return
        if command == 'move':
            self.move_selected_dialog()
        elif command == 'copy':
            if self.copy_selected():
                self.paste_members()
        elif command == 'cut':
            self.cut_selected()
        elif command == 'delete':
            self.delete_selected()
        elif command == 'rotate':
            self.rotate_selected_dialog()
        elif command == 'undo':
            self.undo_model()
        elif command == 'redo':
            self.redo_model()
        self._return_to_select()

    def move_selected(self, dx_m, dy_m):
        targets = [m for m in self.canvas.selected_set if self.canvas.is_editable(m)]
        if not targets:
            return False
        dx, dy = float(dx_m) * 100.0, float(dy_m) * 100.0
        grid_changed = False
        for member in targets:
            member['points'] = [(x + dx, y + dy) for x, y in member['points']]
            if member['kind'] == 'grid':
                grid_changed = True
            else:
                self.canvas._update_member_item(member)
        if grid_changed:
            self.canvas._rebuild_grid_annotations()
        self.canvas.select_members(targets)
        self.canvas.changed.emit()
        return True

    def move_selected_dialog(self):
        if not self.canvas.selected_set:
            return False
        text, ok = QInputDialog.getText(self, 'Move Member',
                                        'ระยะเลื่อน X, Y (m) เช่น 1.50, -0.50',
                                        text='0.00, 0.00')
        if not ok:
            return False
        try:
            dx, dy = (float(part.strip()) for part in text.split(','))
        except (TypeError, ValueError):
            self.status.setText('Move ไม่สำเร็จ — กรุณากรอก X, Y เป็นเมตร เช่น 1.50, -0.50')
            return False
        return self.move_selected(dx, dy)

    def rotate_selected(self, angle_deg):
        targets = [m for m in self.canvas.selected_set
                   if m.get('kind') != 'grid' and self.canvas.is_editable(m)]
        points = [point for member in targets for point in member['points']]
        if not points:
            return False
        cx = sum(x for x, _y in points) / len(points)
        cy = sum(y for _x, y in points) / len(points)
        angle = math.radians(float(angle_deg)); cosine, sine = math.cos(angle), math.sin(angle)
        for member in targets:
            member['points'] = [(cx + (x-cx)*cosine - (y-cy)*sine,
                                 cy + (x-cx)*sine + (y-cy)*cosine)
                                for x, y in member['points']]
            self.canvas._update_member_item(member)
        self.canvas.select_members(targets)
        self.canvas.changed.emit()
        return True

    def rotate_selected_dialog(self):
        if not self.canvas.selected_set:
            return False
        angle, ok = QInputDialog.getDouble(self, 'Rotate Member', 'มุมหมุน (องศา)',
                                            90.0, -360.0, 360.0, 2)
        return self.rotate_selected(angle) if ok else False

    def show_load_panel(self, field='transfer'):
        self.canvas.set_mode('select')
        self.detail.setCurrentIndex(self.load_detail_index)
        self.edit_buttons['select'].setChecked(True)
        target = {'dead': self.load_sdl, 'live': self.load_live,
                  'wind': self.load_wind}.get(field)
        if target is not None:
            target.setFocus(Qt.OtherFocusReason)

    def _on_view_tab(self, index):
        # The 3D workspace follows the reference workbench: the model owns the
        # central canvas while project navigation and properties stay outside.
        if not self.tool_side_external:
            self.tool_side.setVisible(index != 1)
        self.member_toolbar.setVisible(index != 1)
        titles = {0: 'Building Model · แปลน 2D', 1: 'Building Model · Model 3D',
                  2: 'Building Model · Side View 2D'}
        self.workspace_title.setText(f'<h2>{titles.get(index, "Building Model")}</h2>')
        if index == 1:
            if self.workspace_splitter.count() > 1:
                self.workspace_splitter.setSizes([0, 1200])
            self._refresh_3d()
        elif index == 2:
            if self.workspace_splitter.count() > 1:
                self.workspace_splitter.setSizes([310, 900])
            self._refresh_side_grids()
            self.side_canvas.refresh()
        else:
            if self.workspace_splitter.count() > 1:
                self.workspace_splitter.setSizes([310, 900])

    def _refresh_side_grids(self):
        if not hasattr(self, 'side_grid_box'):
            return
        current = self.side_canvas.grid
        grids = [m for m in self.canvas.members if m['kind']=='grid' and not m.get('minor')]
        self.side_grid_box.blockSignals(True); self.side_grid_box.clear()
        for grid in grids:
            axis = grid.get('axis','v'); coord = self.canvas._grid_coord(grid)/100
            direction = 'X' if axis=='v' else 'Y'
            self.side_grid_box.addItem(f"กริด {grid.get('label','?')} · {direction} = {coord:.2f} m", grid)
        index = next((i for i,g in enumerate(grids) if g is current), 0 if grids else -1)
        self.side_grid_box.setCurrentIndex(index); self.side_grid_box.blockSignals(False)
        self.side_canvas.set_grid(grids[index] if 0 <= index < len(grids) else None)

    def _on_side_grid(self, index):
        self.side_canvas.set_grid(self.side_grid_box.itemData(index) if index >= 0 else None)

    def _add_grid_by_spacing(self):
        # axis follows whatever the canvas last inferred (mouse / Tab)
        self.canvas.add_next_grid(self.grid_spacing.value())

    def _detail_page(self, key):
        if key == 'load':
            return self._build_load_transfer_tab()
        page = QWidget(); v = QVBoxLayout(page)
        if key == 'select':
            self.pick_info = QLabel(); self.pick_info.setVisible(False)
            from desktop_app.member_properties import MemberProperties
            self.properties = MemberProperties(self)
            v.addWidget(self.properties)
        elif key == 'view':
            v.addWidget(QLabel('<b>View · การแสดงผล Plan 2D</b>'))
            self.true_scale_check = QCheckBox('แสดงขนาดหน้าตัดจริงตาม Scale')
            self.true_scale_check.setToolTip('เสา 20×20 cm แสดงกว้าง 20×20 cm; คาน ผนัง และฐานรากแสดงขนาดจริง')
            self.true_scale_check.toggled.connect(self._set_true_scale_view)
            v.addWidget(self.true_scale_check)
            v.addWidget(QLabel('<b>แสดงเบอร์ Member</b>'))
            self.member_label_checks = {}
            for kind, text in (('beam', 'เบอร์คาน'), ('column', 'เบอร์เสา'),
                               ('footing', 'เบอร์ฐานราก')):
                check = QCheckBox(text); check.setChecked(True)
                check.toggled.connect(lambda shown, k=kind: self._set_member_label_view(k, shown))
                self.member_label_checks[kind] = check; v.addWidget(check)
        elif key == 'grid':
            v.addWidget(QLabel('<b>สร้างเส้นกริด</b>'))
            form = QFormLayout(); v.addLayout(form)
            self.grid_spacing = QDoubleSpinBox(); self.grid_spacing.setRange(0.10, 100.0)
            self.grid_spacing.setDecimals(2); self.grid_spacing.setValue(4.00)
            self.grid_spacing.setSingleStep(0.10)
            form.addRow('ระยะถัดไป (m)', self.grid_spacing)
            self.minor_grid_check = QCheckBox('กริดย่อย — ไม่แสดงบับเบิล')
            self.minor_grid_check.toggled.connect(lambda on: setattr(self.canvas, 'grid_minor', on))
            v.addWidget(self.minor_grid_check)
            add_grid_btn = QPushButton('เพิ่มกริดตามระยะนี้')
            add_grid_btn.clicked.connect(self._add_grid_by_spacing)
            v.addWidget(add_grid_btn)
            line = QFrame(); line.setFrameShape(QFrame.HLine); v.addWidget(line)
            v.addWidget(QLabel('<b>ระดับ / ชั้น</b>'))
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
            if key in ('column', 'beam'):
                material = QComboBox(); material.addItem('คอนกรีต', 'concrete'); material.addItem('เหล็ก', 'steel')
                self.material_pickers[key] = material
                material.activated.connect(lambda _=0, k=key: self._change_material_filter(k))
                v.addWidget(material)
                family = QComboBox()
                for title, value in [('เหล็กกล่องจัตุรัส · SHS', 'SHS'), ('เหล็กกล่องแบน · RHS', 'RHS'), ('H-Sections', 'H')]:
                    family.addItem(title, value)
                self.family_pickers[key] = family
                family.activated.connect(lambda _=0, k=key: self._change_material_filter(k))
                v.addWidget(family)
            picker = QComboBox()
            picker.setMinimumContentsLength(24); picker.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            picker.currentIndexChanged.connect(lambda _=0, k=key: self._on_pick_section(k))
            self._pickers[key] = picker
            v.addWidget(picker)
            self.section_info[key] = QLabel(); self.section_info[key].setWordWrap(True)
            v.addWidget(self.section_info[key])
            btns = QHBoxLayout()
            self.section_buttons[key] = []
            for lbl, slot in [('เพิ่มหน้าตัด', lambda: self._section_add(key)),
                              ('แก้ไข', lambda: self._section_edit(key)),
                              ('ลบ', lambda: self._section_remove(key))]:
                b = QPushButton(lbl); b.clicked.connect(slot); btns.addWidget(b)
                self.section_buttons[key].append(b)
            v.addLayout(btns)
            from desktop_app.member_properties import DrawingProperties
            props = DrawingProperties(self, key)
            self.draw_properties[key] = props
            v.addWidget(props)
            if key == 'footing':
                pile_buttons = QHBoxLayout()
                for text, slot in (('สร้างหน้าตัดเข็ม', self._pile_add),
                                   ('แก้หน้าตัดเข็ม', self._pile_edit),
                                   ('ลบหน้าตัดเข็ม', self._pile_remove)):
                    button = QPushButton(text); button.clicked.connect(slot); pile_buttons.addWidget(button)
                v.addLayout(pile_buttons)
            if key in ('footing', 'stair', 'wall'):
                v.addWidget(QLabel('ยังไม่รวมในการวิเคราะห์โครงข้อแข็ง'))
        v.addStretch(1)
        return page

    # ---- section library -------------------------------------------
    def _refresh_section_pickers(self):
        for kind, picker in self._pickers.items():
            active = self.sections[kind][min(self.applied[kind], len(self.sections[kind])-1)]
            steel = active.get('material') == 'steel'
            if kind in self.material_pickers:
                material = self.material_pickers[kind]; material.setCurrentIndex(1 if steel else 0)
                family = self.family_pickers[kind]; family.setVisible(steel)
                if steel:
                    family.setCurrentIndex(family.findData(active['family']))
            picker.blockSignals(True); picker.clear()
            for i, s in enumerate(self.sections[kind]):
                if kind in self.material_pickers and ((s.get('material') == 'steel') != steel
                        or (steel and s.get('family') != active['family'])):
                    continue
                picker.addItem(section_label(kind, s), i)
            picker.setCurrentIndex(picker.findData(self.applied[kind]))
            picker.blockSignals(False)
            self._update_section_info(kind)
        if (hasattr(self, 'properties') and hasattr(self, 'canvas')
                and self.canvas.selected_set):
            self.properties.show_members(self.canvas.selected_set)

    def _change_material_filter(self, kind):
        steel = self.material_pickers[kind].currentData() == 'steel'
        family = self.family_pickers[kind].currentData()
        self.applied[kind] = next(i for i, s in enumerate(self.sections[kind])
            if (s.get('material') == 'steel') == steel and (not steel or s['family'] == family))
        self._refresh_section_pickers(); self.record_edit()

    def _update_section_info(self, kind):
        s = self.sections[kind][self.applied[kind]]
        steel = s.get('material') == 'steel'
        for button in self.section_buttons[kind]:
            button.setEnabled(not steel)
        if steel:
            text = (f"A {s['area_cm2']:g} cm² · Ix {s['ix_cm4']:g} / Iy {s['iy_cm4']:g} cm⁴\n"
                    f"Zx {s['zx_cm3']:g} / Zy {s['zy_cm3']:g} cm³\n"
                    f"จาก {s['source']} หน้า {s['source_page']}")
            self.section_info[kind].setText(text)
            self.section_info[kind].setToolTip('ค่าตามตารางต้นฉบับ · PDF ไม่ได้กำหนดเกรดหรือ Fy ของเหล็ก')
        else:
            self.section_info[kind].setText('หน้าตัดคอนกรีต · ' + rebar_summary(kind, s))
            self.section_info[kind].setToolTip('')

    def _on_pick_section(self, kind):
        self.applied[kind] = self._pickers[kind].currentData() or 0
        self._update_section_info(kind)
        self.record_edit()

    def _active_section_label(self, kind):
        s = self.sections[kind][min(self.applied[kind], len(self.sections[kind]) - 1)]
        return section_label(kind, s)

    @staticmethod
    def section_text(kind, spec):
        return section_label(kind, spec)

    def _section_add(self, kind):
        dlg = SectionDialog(kind, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.sections[kind].append(dlg.value())
            self.applied[kind] = len(self.sections[kind]) - 1
            self._refresh_section_pickers(); self.record_edit()

    def _section_edit(self, kind):
        idx = min(self.applied[kind], len(self.sections[kind]) - 1)
        if self.sections[kind][idx].get('material') == 'steel':
            return
        old_label = section_label(kind, self.sections[kind][idx])
        dlg = SectionDialog(kind, self.sections[kind][idx], parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.sections[kind][idx] = dlg.value()
            new_label = section_label(kind, self.sections[kind][idx])
            for member in self.canvas.members:
                if member.get('kind') == kind and member.get('section') == old_label:
                    member['section'] = new_label
            if self.canvas.true_scale_members:
                self.canvas._rebuild_member_items()
            self._refresh_section_pickers(); self.canvas.changed.emit()

    def _section_remove(self, kind):
        if (sum(s.get('material') != 'steel' for s in self.sections[kind]) <= 1
                or self.sections[kind][self.applied[kind]].get('material') == 'steel'):
            return
        removed = self.sections[kind][min(self.applied[kind], len(self.sections[kind]) - 1)]
        removed_label = section_label(kind, removed)
        del self.sections[kind][min(self.applied[kind], len(self.sections[kind]) - 1)]
        self.applied[kind] = 0
        replacement = section_label(kind, self.sections[kind][0])
        for member in self.canvas.members:
            if member.get('kind') == kind and member.get('section') == removed_label:
                member['section'] = replacement
        if self.canvas.true_scale_members:
            self.canvas._rebuild_member_items()
        self._refresh_section_pickers(); self.canvas.changed.emit()

    @staticmethod
    def pile_section_text(spec):
        return pile_section_label(spec)

    def _refresh_pile_properties(self, selected_name=None):
        for props in [getattr(self, 'properties', None), self.draw_properties.get('footing')]:
            if props is None or props.member is None or props.member.get('kind') != 'footing':
                continue
            name = selected_name or props.pile_section.currentData() or self.pile_sections[0]['name']
            props.pile_section.blockSignals(True); props.pile_section.clear()
            for spec in self.pile_sections:
                props.pile_section.addItem(pile_section_label(spec), spec['name'])
            props.pile_section.setCurrentIndex(max(0, props.pile_section.findData(name)))
            props.pile_section.blockSignals(False)
            if selected_name and props.defaults is not None:
                props.defaults['pile_section'] = selected_name

    def _pile_add(self):
        dlg = PileSectionDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            spec = dlg.value(); self.pile_sections.append(spec)
            self._refresh_pile_properties(spec['name']); self.record_edit()

    def _pile_edit(self):
        props = self.draw_properties.get('footing')
        name = props.pile_section.currentData() if props else None
        index = next((i for i, s in enumerate(self.pile_sections) if s['name'] == name), 0)
        old_name = self.pile_sections[index]['name']
        dlg = PileSectionDialog(self.pile_sections[index], self)
        if dlg.exec() == QDialog.Accepted:
            self.pile_sections[index] = dlg.value(); new_name = self.pile_sections[index]['name']
            for member in self.canvas.members:
                if member.get('kind') == 'footing' and member.get('pile_section') == old_name:
                    member['pile_section'] = new_name
            self._refresh_pile_properties(new_name); self.canvas.changed.emit()

    def _pile_remove(self):
        if len(self.pile_sections) <= 1:
            return
        props = self.draw_properties.get('footing')
        name = props.pile_section.currentData() if props else self.pile_sections[0]['name']
        index = next((i for i, s in enumerate(self.pile_sections) if s['name'] == name), 0)
        del self.pile_sections[index]; replacement = self.pile_sections[0]['name']
        for member in self.canvas.members:
            if member.get('kind') == 'footing' and member.get('pile_section') == name:
                member['pile_section'] = replacement
        self._refresh_pile_properties(replacement); self.canvas.changed.emit()

    def section_state(self):
        return {'sections': {k: [dict(s) for s in v] for k, v in self.sections.items()},
                'applied': dict(self.applied),
                'pile_sections': [dict(s) for s in self.pile_sections]}

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
                if kind in ('column', 'beam') and r.get('material') == 'steel':
                    match = next((s for s in STEEL_SECTIONS if s['name'] == r.get('name')), None)
                    if match:
                        keep.append(dict(match))
                    continue
                entry = {'name': str(r.get('name', kind[0].upper() + '1'))}
                for key, _l, _mn, _mx, _dp, dv in spec:
                    v = r.get(key, dv)
                    entry[key] = float(v) if isinstance(v, (int, float)) else dv
                for key, _l, _mn, _mx, _dp, dv in REBAR_SPEC[kind]:
                    v = r.get(key, dv)
                    entry[key] = float(v) if isinstance(v, (int, float)) else dv
                keep.append(entry)
            clean[kind] = keep or [dict(s) for s in DEFAULT_SECTIONS[kind]]
            if kind in ('column', 'beam'):
                names = {s['name'] for s in clean[kind] if s.get('material') == 'steel'}
                clean[kind].extend(dict(s) for s in STEEL_SECTIONS if s['name'] not in names)
        self.sections = clean
        self.applied = {k: (applied.get(k) if isinstance(applied.get(k), int)
                            and 0 <= applied.get(k) < len(self.sections[k]) else 0)
                        for k in SECTION_SPEC}
        piles = (state or {}).get('pile_sections', [])
        clean_piles = []
        for raw in piles if isinstance(piles, list) else []:
            if not isinstance(raw, dict):
                continue
            try:
                clean_piles.append({'name': str(raw.get('name') or 'P1'),
                    'shape': 'circular' if raw.get('shape') == 'circular' else 'square',
                    'b_cm': float(raw.get('b_cm', 30)), 'h_cm': float(raw.get('h_cm', 30)),
                    'length_m': float(raw.get('length_m', 12)),
                    'capacity_kn': float(raw.get('capacity_kn', 600))})
            except (TypeError, ValueError):
                continue
        self.pile_sections = clean_piles or [dict(s) for s in DEFAULT_PILE_SECTIONS]
        self._refresh_section_pickers()
        self._refresh_pile_properties()
        if hasattr(self, 'canvas') and self.canvas.true_scale_members:
            self.canvas._rebuild_member_items()

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
        self._sync_plan_level()

    def _sync_plan_level(self):
        for box in (self.level_box, self.plan_level_box):
            box.blockSignals(True); box.clear()
            for level in self.levels:
                box.addItem(self._level_text(level))
            box.setCurrentIndex(self.current_level_idx); box.blockSignals(False)

    def _apply_current_level(self):
        l = self.levels[self.current_level_idx]
        self.canvas.set_current_level(l['name'], l['elev'])
        for props in self.draw_properties.values():
            props.refresh()
        if hasattr(self, 'side_canvas'):
            self.side_canvas.refresh()

    def _on_level_change(self, idx):
        if not (0 <= idx < len(self.levels)):
            return
        self.current_level_idx = idx
        self._sync_plan_level()
        if hasattr(self, 'level_list') and self.level_list.currentRow() != idx:
            self.level_list.blockSignals(True)
            self.level_list.setCurrentRow(idx)
            self.level_list.blockSignals(False)
        self._apply_current_level()
        self.record_edit()
        if self.view_tabs.currentIndex() == 1:
            self._refresh_3d()
        elif self.view_tabs.currentIndex() == 2:
            self.side_canvas.refresh()

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
        self.result = None
        if self.properties.member is not None and self.properties.member not in self.canvas.members:
            self.properties.show_member(None)
        self._sync_model()
        self.record_edit()
        self._update_status()
        self._refresh_side_grids()
        if self.view_tabs.currentIndex() == 1:
            self._refresh_3d()
        elif self.view_tabs.currentIndex() == 2:
            self.side_canvas.refresh()

    def _on_pick_member(self, member):
        n = len(self.canvas.selected_set)
        self.delete_button.setEnabled(n > 0)
        self.properties.show_members(self.canvas.selected_set)
        if n > 0:
            self.detail.setCurrentIndex(0)
            self.tool_group.button(0).setChecked(True)
        if n == 0:
            self.pick_info.setText('ยังไม่ได้เลือก')
        elif n > 1:
            self.pick_info.setText(f'เลือก {n} ชิ้น')
        else:
            self.pick_info.setText(f"{KIND_TH[member['kind']]} · {member['section']}")
        if self.view_tabs.currentIndex() == 1:
            self._refresh_3d()
        elif self.view_tabs.currentIndex() == 2:
            self.side_canvas.refresh()

    def _reassign_selected(self):
        """Compatibility action: apply the drawing palette section.

        The visible workflow now uses the section combo in Properties, but
        existing callers and saved UI automation can still invoke this.
        """
        if self.canvas.selected is not None and self.canvas.selected.get('kind') in self.sections:
            self.canvas.set_selected_section(
                self._active_section_label(self.canvas.selected['kind']))
            self._on_pick_member(self.canvas.selected)

    def _on_canvas_mode(self, mode):
        if hasattr(self, 'side_canvas'):
            self.side_canvas.set_mode(mode)
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
        self.properties.show_member(None)
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
            if self.result:
                summary = self.result.get('summary', {})
                self.status.setText(f"{n} member บนแปลน ({parts}) — การถ่ายแรง {self.result.get('status')} · "
                                    f"แรงประลัยที่ฐาน {summary.get('factored_base_U_kn', 0) * KN_TO_KG:,.2f} kg")
            else:
                self.status.setText(f'{n} member บนแปลน ({parts}) — ยังไม่ได้คำนวณการถ่ายแรง')

    # ---- history -----------------------------------------------
    def state_snapshot(self):
        return {'plan': self.canvas.to_state(), 'storey_h': self.storey_h.value(),
                'sections': self.section_state(),
                'levels': [dict(l) for l in self.levels],
                'current_level_idx': self.current_level_idx,
                'load_settings': self._load_settings()}

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
        self.properties.show_member(None)
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
        self._set_load_settings(snap.get('load_settings'))
        self._sync_view_controls()
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
        from desktop_app.member_properties import member_elevations
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        from matplotlib.font_manager import FontProperties
        from desktop_app.home import resource_root
        level_font = FontProperties(fname=str(Path(resource_root()) / 'fonts' / 'THSarabunNew.ttf'), size=12)
        old_ax = self.figure.axes[0] if self.figure.axes else None
        camera = (old_ax.elev, old_ax.azim, old_ax.get_xlim(), old_ax.get_ylim(), old_ax.get_zlim()) if old_ax else None
        geometry_state = (self.canvas.to_state(), [dict(level) for level in self.levels])
        same_geometry = geometry_state == getattr(self, '_last_3d_geometry', None)
        self._last_3d_geometry = geometry_state
        self.figure.clear()
        self.model_interaction.geometry = []
        if not self.canvas.members:
            self.canvas3d.draw_idle(); return
        ax = self.figure.add_axes([0.0, 0.0, 1.0, 1.0], projection='3d')
        ax.set_facecolor('#101419')
        ax.disable_mouse_rotation()
        ax.set_axis_off()
        h = self.storey_h.value()
        xs, ys = [], []
        for m in self.canvas.members:
            if m['kind'] == 'grid':
                continue
            pts_m = [(x / 100.0, y / 100.0) for x, y in m['points']]
            for x, y in pts_m:
                xs.append(x); ys.append(y)
            color = '#f59e0b' if m in self.canvas.selected_set else KIND_COLOR[m['kind']]
            if not self.canvas.is_editable(m):
                color = '#d3dce5'
            base = float(m.get('z', 0.0))          # level elevation (m)
            start_z, end_z = member_elevations(m, h)
            vertices = [(x, y, start_z) for x, y in pts_m]
            if m['kind'] in POINT_KINDS or m['kind'] in LINE_KINDS:
                vertices = [(pts_m[0][0], pts_m[0][1], start_z), (pts_m[-1][0], pts_m[-1][1], end_z)]
            if m['kind'] == 'wall':
                vertices = [(*pts_m[0], start_z), (*pts_m[1], start_z), (*pts_m[1], end_z), (*pts_m[0], end_z)]
            self.model_interaction.geometry.append((m, vertices, m['kind'] in ('wall', 'slab')))
            if m['kind'] in POINT_KINDS:
                x, y = pts_m[0]
                if m['kind'] == 'footing':
                    marker = 's' if m.get('support_type', 'fixed') == 'fixed' else '^'
                    ax.scatter([x], [y], [start_z], color=color, edgecolors='#0f172a',
                               marker=marker, s=80, depthshade=False)
                else:
                    ex, ey = pts_m[-1]
                    ax.plot([x, ex], [y, ey], [start_z, end_z], color=color, lw=3)
            elif m['kind'] == 'wall':
                (x1, y1), (x2, y2) = pts_m
                face = [(x1,y1,start_z), (x2,y2,start_z), (x2,y2,end_z), (x1,y1,end_z)]
                ax.add_collection3d(Poly3DCollection([face], facecolors=color, edgecolors=color, alpha=0.45))
                closed = face+[face[0]]
                ax.plot(*zip(*closed), color=color, lw=1.5)
            elif m['kind'] in LINE_KINDS:
                (x1, y1), (x2, y2) = pts_m
                ax.plot([x1, x2], [y1, y2], [start_z, end_z], color=color, lw=2.5)
            else:
                ax.add_collection3d(Poly3DCollection([vertices], facecolors=color, edgecolors=color, alpha=0.35))
                px = [p[0] for p in pts_m] + [pts_m[0][0]]
                py = [p[1] for p in pts_m] + [pts_m[0][1]]
                ax.plot(px, py, [start_z] * len(px), color=color, lw=2)
        for level in self.levels:
            z = level['elev']
            for grid in self.canvas.members:
                if grid['kind'] != 'grid':
                    continue
                points = [(x/100, y/100, z) for x, y in grid['points']]
                ax.plot(*zip(*points), color='#cbd5e1', lw=0.7, ls=':' if grid.get('minor') else '--')
                if not grid.get('minor'):
                    ax.text(*points[0], grid.get('label', ''), color='#64748b', fontsize=8)
            ax.text(min(xs, default=0), min(ys, default=0), z, self._level_text(level), fontproperties=level_font)
        if xs and ys:
            sx = max(max(xs) - min(xs), 1.0)
            sy = max(max(ys) - min(ys), 1.0)
            zs = [p[2] for _, vertices, _ in self.model_interaction.geometry for p in vertices] + [l['elev'] for l in self.levels]
            ax.set_box_aspect((sx, sy, max(max(zs)-min(zs), 1.0)), zoom=1.18)
        self.canvas3d.draw_idle()
        self.set_view(self.view_name, fit=False)
        if camera:
            ax.view_init(elev=camera[0], azim=camera[1])
            if same_geometry:
                ax.set_xlim(camera[2]); ax.set_ylim(camera[3]); ax.set_zlim(camera[4])
        if not same_geometry:
            self._fit_limits = (ax.get_xlim(), ax.get_ylim(), ax.get_zlim())
            self.fit_model()

    def fit_model(self):
        if not self.figure.axes:
            return
        ax = self.figure.axes[0]
        points = [p for _, vertices, _ in self.model_interaction.geometry for p in vertices]
        for level in self.levels:
            points.extend((x/100, y/100, level['elev']) for m in self.canvas.members if m['kind'] == 'grid' for x, y in m['points'])
        if points:
            for axis_index, name in enumerate(('x', 'y', 'z')):
                values = [point[axis_index] for point in points]
                lo, hi = min(values), max(values)
                span = hi - lo
                pad = max(0.25, span * 0.08)
                if span < 1e-9:
                    pad = 0.5
                getattr(ax, 'set_'+name+'lim')(lo-pad, hi+pad)
            spans = [max(getattr(ax, 'get_'+name+'lim')()[1] - getattr(ax, 'get_'+name+'lim')()[0], 1.0)
                     for name in ('x', 'y', 'z')]
            ax.set_box_aspect(spans, zoom=1.18)
            ax.set_position([0.0, 0.0, 1.0, 1.0])
        self.canvas3d.draw_idle()

    def show_3d_fullscreen(self):
        if self.fullscreen_dialog is not None:
            return
        dialog = QDialog(self); dialog.setWindowTitle('Model 3D · Full Screen')
        layout = QVBoxLayout(dialog)
        close = QPushButton('ออกจาก Full Screen (Esc)'); close.clicked.connect(dialog.reject)
        layout.addWidget(close); layout.addWidget(self.canvas3d, 1)
        self.fullscreen_dialog = dialog
        def restore(_):
            self.view3d_layout.addWidget(self.canvas3d, 1)
            self.fullscreen_dialog = None
            dialog.deleteLater()
            self.fit_model()
        dialog.finished.connect(restore)
        dialog.showFullScreen()
        self.fit_model()

    def set_view(self, name, fit=True):
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
            if fit:
                self.fit_model()

    # ---- files -------------------------------------------------
    def new_model(self):
        self.properties.show_member(None)
        self.canvas.clear()
        self.levels = [{'name': 'พื้นชั้น 1', 'elev': 0.0}]
        self.current_level_idx = 0
        self.canvas.add_grid('v', 0.0, emit=False)
        self.canvas.add_grid('h', 0.0, emit=False)
        self.current_model_path = None
        self.result = None
        self._refresh_level_widgets()
        self._refresh_side_grids()
        self._sync_model(); self._update_status(); self._refresh_3d()
        self.history = [self.state_snapshot()]
        self.history_index = 0
        self.history_buttons()

    def write_model(self, path):
        if not self.canvas.members:
            raise ValueError('แปลนยังว่าง ยังไม่มีอะไรให้บันทึก')
        data = json.dumps({'format': 'rc-codepro-plan', 'version': 1,
                           'plan': self.canvas.to_state(),
                           'storey_h': self.storey_h.value(),
                           'sections': self.section_state(),
                           'levels': [dict(l) for l in self.levels],
                           'current_level_idx': self.current_level_idx,
                           'load_settings': self._load_settings()},
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
        self.properties.show_member(None)
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
            self._sync_view_controls()
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
            self._set_load_settings(data.get('load_settings'))
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
        if self.current_model_path:
            try:
                self.write_model(self.current_model_path)
                recent_files.add(self.current_model_path)
                self.status.setText('บันทึกแล้ว: ' + self.current_model_path)
            except (ValueError, OSError, TypeError) as exc:
                self.status.setText('บันทึกไม่สำเร็จ: ' + str(exc))
            return
        self.save_model_as()

    def save_model_as(self):
        path, _ = QFileDialog.getSaveFileName(self, 'บันทึกโมเดล', '', 'RC CodePro model (*.rcmodel)')
        if not path:
            return
        if not path.lower().endswith('.rcmodel'):
            path += '.rcmodel'
        try:
            self.write_model(path)
            self.current_model_path = path
            recent_files.add(path)
            self.status.setText('บันทึกแล้ว: ' + path)
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText('บันทึกไม่สำเร็จ: ' + str(exc))

    def open_model(self):
        path, _ = QFileDialog.getOpenFileName(self, 'เปิดโมเดล', '', 'RC CodePro model (*.rcmodel)')
        if not path:
            return
        self.open_model_path(path)

    def open_model_path(self, path):
        """Load a specific .rcmodel path (used by File > Open and Home's
        Recent Projects list) and record it in the recent-files list."""
        try:
            self.read_model(path)
            self.current_model_path = path
            recent_files.add(path)
        except (ValueError, OSError, TypeError) as exc:
            self.status.setText('เปิดไม่สำเร็จ: ' + str(exc))

    def overview_data(self):
        """A small, honest snapshot of the current model for the Home page's
        Project Overview panel -- counts and statuses are read directly off
        the canvas / load-transfer result, never invented."""
        counts = {}
        for m in self.canvas.members:
            if m['kind'] == 'grid':
                continue
            counts[m['kind']] = counts.get(m['kind'], 0) + 1
        has_model = bool(counts)
        if self.result:
            analysis_status = str(self.result.get('status') or 'เสร็จสิ้น')
        else:
            analysis_status = 'ยังไม่คำนวณ'
        return {
            'has_model': has_model,
            'levels': len(self.levels),
            'counts': counts,
            'model_status': 'พร้อมใช้งาน' if has_model else 'ยังไม่มีข้อมูล',
            'analysis_status': analysis_status,
            'design_status': 'ยังไม่เริ่ม',
        }
