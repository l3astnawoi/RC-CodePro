"""Home launcher, shared theme and small UI helpers for the native shell.

The window navigation is a plain QStackedWidget driven by ``DesktopWindow.go``
(see ``desktop_app/main.py``); this module only provides the landing page,
the category card widget, the "coming soon" placeholder and the stylesheet.
No calculation engine is touched here.
"""
import os
import sys
import time
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QPixmap, QPainter, QFontDatabase, QIcon, QFont, QDesktopServices
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu,
                               QApplication, QPushButton, QScrollArea, QSizePolicy,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from desktop_app import recent_files
from desktop_app.plan_canvas import KIND_TH


ACCENT = "#2563eb"

# Ordered exactly as requested: 1 Building Model … 6 Stair, 7 Wall.
CATEGORIES = [
    ("Building Model", "โมเดลอาคาร", "building", False),
    ("Beam", "คาน", "beam", False),
    ("Column", "เสา", "column", False),
    ("Slab", "พื้น", "slab", False),
    ("Footing", "ฐานราก", "footing", False),
    ("Stair", "บันได", "stair", False),
    ("Wall", "ผนัง", "wall", True),        # coming soon
]


def resource_root():
    """Repo root when run from source, or the PyInstaller bundle dir."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def icon_path(name):
    return os.path.join(resource_root(), "assets", "desktop_icons", f"{name}.svg")


def svg_pixmap(name, px, dpr=2.0):
    """Render an SVG asset to a crisp transparent QPixmap."""
    renderer = QSvgRenderer(icon_path(name))
    side = max(1, int(px * dpr))
    pm = QPixmap(side, side)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def load_fonts():
    """Make the bundled Thai font available so offscreen/packaged runs render
    Thai labels (the offscreen platform does not enumerate system fonts)."""
    ttf = os.path.join(resource_root(), "fonts", "THSarabunNew.ttf")
    if os.path.exists(ttf):
        QFontDatabase.addApplicationFont(ttf)
    # Qt's offscreen and packaged font discovery can omit Windows fallback
    # families. Arial Unicode MS is present on the target workstation and
    # covers both Thai and Latin UI strings.
    unicode_font = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'ARIALUNI.TTF')
    if os.path.exists(unicode_font):
        font_id = QFontDatabase.addApplicationFont(unicode_font)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app = QApplication.instance()
            if app is not None:
                app.setFont(QFont(families[0], 10))


def _relative_time(mtime):
    """A short, human Thai relative-time string for a file mtime."""
    delta = max(0.0, time.time() - mtime)
    if delta < 60:
        return "เมื่อสักครู่"
    if delta < 3600:
        return f"{int(delta // 60)} นาทีที่แล้ว"
    if delta < 86400:
        return f"{int(delta // 3600)} ชั่วโมงที่แล้ว"
    days = int(delta // 86400)
    if days < 7:
        return f"{days} วันที่แล้ว"
    return datetime.fromtimestamp(mtime).strftime("%d %b %Y")


THEME_QSS = """
* { font-family: "Arial Unicode MS"; }
QWidget { font-size: 14px; color: #1e293b; }
QMainWindow, QWidget#root { background: #15191f; }
QDialog { background: #15191f; }

QFrame#menuBar, QFrame#ribbon, QFrame#projectBrowser, QFrame#inspector,
QFrame#statusBar { background: #171b21; border-color: #303640; }
QFrame#menuBar { border-bottom: 1px solid #2b313a; }
QFrame#ribbon { background: #20252d; border-bottom: 1px solid #353c47; }
QFrame#projectBrowser { border-left: 1px solid #303640; }
QFrame#inspector { border-right: 1px solid #303640; }
QFrame#statusBar { border-top: 1px solid #303640; }
QLabel#panelTitle { color: #f1f5f9; font-size: 13px; font-weight: 700; }
QLabel#statusText, QLabel#panelMuted { color: #94a3b8; font-size: 11px; }
QPushButton#menuBtn { background: transparent; border: none; color: #d8dee9; padding: 5px 10px; }
QPushButton#menuBtn:hover, QPushButton#menuBtn:checked { background: #2d3541; color: white; }
QMenuBar#mainMenu { background: transparent; color: #d8dee9; border: none; }
QMenuBar#mainMenu::item { background: transparent; padding: 6px 10px; }
QMenuBar#mainMenu::item:selected, QMenuBar#mainMenu::item:pressed { background: #2d3541; color: white; }
QMenu { background: #20252d; color: #e2e8f0; border: 1px solid #3a4350; padding: 4px; }
QMenu::item { padding: 7px 34px 7px 24px; }
QMenu::item:selected { background: #1673d3; color: white; }
QMenu::separator { height: 1px; background: #3a4350; margin: 4px 8px; }
QMenu::indicator:checked { background: #1673d3; border: 1px solid #60a5fa; }
QTabBar#ribbonTabs { background: transparent; }
QTabBar#ribbonTabs::tab {
    background: #171b21; color: #aeb8c6; border: 1px solid #343c48;
    border-bottom: none; min-width: 125px; padding: 5px 14px;
}
QTabBar#ribbonTabs::tab:selected { background: #20252d; color: #ffffff; border-top: 2px solid #2f9bff; }
QTabBar#ribbonTabs::tab:hover { color: #ffffff; background: #29313c; }
QToolButton#ribbonBtn { background: transparent; border: 1px solid transparent; color: #e2e8f0; padding: 5px; }
QToolButton#ribbonBtn:hover { background: #2b3440; border-color: #3b82f6; }
QLabel#ribbonGroup { color: #738198; font-size: 10px; }
QTreeWidget { background: #171b21; color: #cbd5e1; border: none; outline: 0; }
QTreeWidget::item { height: 24px; }
QTreeWidget::item:selected { background: #1673d3; color: white; }
QGroupBox { color: #dce3ed; border: 1px solid #343b46; margin-top: 9px; padding-top: 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }

QFrame#header { background: #101318; border-bottom: 1px solid #303640; }
QLabel#brandTitle { font-size: 18px; font-weight: 700; color: #f8fafc; }
QLabel#brandSub { font-size: 11px; color: #94a3b8; }
QLabel#projChip {
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 13px;
    padding: 4px 14px; color: #1d4ed8; font-weight: 600;
}
QPushButton#headerBtn {
    background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 9px;
    padding: 8px 16px; color: #334155; font-weight: 600; outline: 0;
}
QPushButton#headerBtn:hover { background: #e2e8f0; border-color: #cbd5e1; }
QPushButton#headerBtn:pressed { background: #dbeafe; }
QPushButton#headerBtn:focus { outline: 0; }

QFrame#crumbBar { background: transparent; }
QPushButton#crumbBtn {
    background: transparent; border: none; color: #2563eb;
    font-weight: 600; padding: 6px 2px;
}
QPushButton#crumbBtn:hover { color: #1d4ed8; }
QLabel#crumbHere { color: #475569; font-weight: 600; }

QWidget#homeRoot, QWidget#homeBody, QScrollArea#homeScroll, QScrollArea#homeScroll QWidget#qt_scrollarea_viewport { border: none; background: #171b21; }
QFrame#homeSide { background: #123354; border-right: 1px solid #2d76ad; }
QLabel#homeBrand { color: white; font-size: 20px; font-weight: 700; }
QLabel#homeTitle { font-size: 25px; font-weight: 700; color: #f8fafc; }
QLabel#homeSub { font-size: 14px; color: #aab4c3; }
QLabel#sectionLabel { color: #9ca9ba; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
QToolButton#homeAction { background: #173f65; color: white; border: 1px solid #3977a8; border-radius: 10px; padding: 12px 6px; font-size: 12px; font-weight: 700; }
QToolButton#homeAction:hover { background: #1c527f; border-color: #61a9dd; }
QPushButton#homeLink { background: transparent; color: #d9e9f6; border: none; text-align: left; padding: 7px 4px; }
QPushButton#homeLink:hover { color: white; background: #19466d; }

QFrame#card { background: #22272f; border: 1px solid #343b46; border-radius: 8px; }
QFrame#card:hover { border: 1px solid #3694e8; background: #282f39; }
QLabel#cardTitle { font-size: 15px; font-weight: 700; color: #f1f5f9; }
QLabel#cardSub { font-size: 12px; color: #9ca3af; }
QFrame#recentCard { background: #242a32; border: 1px solid #343b46; border-radius: 8px; }
QFrame#recentCard:hover { border-color: #3694e8; }
QLabel#recentTitle { color: #f8fafc; font-size: 14px; font-weight: 700; }
QLabel#recentMeta { color: #9ca3af; font-size: 11px; }
QToolButton#recentMenuBtn { background: transparent; border: none; color: #9ca3af; font-size: 15px; padding: 2px 6px; }
QToolButton#recentMenuBtn:hover { color: #f8fafc; background: #343b46; border-radius: 4px; }
QToolButton#recentMenuBtn::menu-indicator { image: none; width: 0; }

QFrame#heroCard { background: #17385c; border: 1px solid #2d76ad; border-radius: 10px; }
QFrame#heroCard:hover { border-color: #61a9dd; }
QLabel#heroTitle { color: #ffffff; font-size: 17px; font-weight: 700; }
QLabel#heroSub { color: #c3d7ea; font-size: 12px; }
QPushButton#heroButton { background: #2563eb; color: white; border: none; border-radius: 7px; padding: 10px 18px; font-weight: 700; }
QPushButton#heroButton:hover { background: #1d4ed8; }

QFrame#overviewCard { background: #1b2028; border: 1px solid #343b46; border-radius: 8px; }
QLabel#cardBadge {
    background: #fef9c3; color: #a16207; border-radius: 7px;
    padding: 2px 9px; font-size: 11px; font-weight: 700;
}

QLabel#phTitle { font-size: 22px; font-weight: 700; color: #f8fafc; }
QLabel#phNote { font-size: 15px; color: #cbd5e1; }

QToolButton#toolRailBtn {
    background: transparent; border: 1px solid transparent; border-radius: 10px;
    color: #93c5fd; font-size: 11px; padding: 4px 2px;
}
QToolButton#toolRailBtn:hover { background: #26303a; color: #ffffff; border-color: #3b82f6; }
QToolButton#toolRailBtn:checked {
    background: #eff6ff; border: 1px solid #bfdbfe; color: #1d4ed8; font-weight: 700;
}
QTabWidget::pane { border: 1px solid #303640; background: #171b21; }
QTabBar::tab { background: #20252d; color: #aab4c3; padding: 8px 14px; border: 1px solid #303640; }
QTabBar::tab:selected { color: white; background: #1f6fb2; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #222831; color: #eef2f7; border: 1px solid #3b4350; border-radius: 3px; padding: 4px; }
QComboBox QAbstractItemView {
    background: #222831; color: #f8fafc; border: 1px solid #64748b;
    selection-background-color: #1673d3; selection-color: #ffffff;
    outline: 0; padding: 3px;
}
QComboBox QAbstractItemView::item { min-height: 26px; padding: 4px 8px; }
QCheckBox { color: #e2e8f0; spacing: 7px; }
QCheckBox#workspaceSnap { color: #f8fafc; font-weight: 600; }
QCheckBox#workspaceSnap:disabled { color: #94a3b8; }
QPushButton#gridLock { font-family: "Segoe MDL2 Assets"; font-size: 18px; padding: 4px; }
QPushButton { background: #26303a; color: #e8edf4; border: 1px solid #3d4856; border-radius: 4px; padding: 6px 10px; }
QPushButton:hover { background: #304052; border-color: #3d8ed0; }
QLabel { color: #dce3eb; }
QTableWidget, QListWidget { background: #171b21; color: #dce3eb; gridline-color: #343b46; border: 1px solid #343b46; }
QHeaderView::section { background: #252b34; color: #dce3eb; border: 1px solid #343b46; padding: 5px; }
"""


class CategoryCard(QFrame):
    """A clickable launcher tile: icon + English title + Thai subtitle."""

    clicked = Signal(str)

    def __init__(self, title, subtitle, icon_name, coming_soon=False, parent=None):
        super().__init__(parent)
        self.title = title
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(190, 92)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 13, 16, 12)
        lay.setSpacing(5)

        icon = QLabel()
        icon.setPixmap(svg_pixmap(icon_name, 28))
        icon.setFixedHeight(30)
        lay.addWidget(icon)

        row = QHBoxLayout()
        row.setSpacing(10)
        name = QLabel(title)
        name.setObjectName("cardTitle")
        row.addWidget(name, 0, Qt.AlignVCenter)
        if coming_soon:
            badge = QLabel("กำลังพัฒนา")
            badge.setObjectName("cardBadge")
            row.addWidget(badge, 0, Qt.AlignVCenter)
        row.addStretch(1)
        lay.addLayout(row)

        sub = QLabel(subtitle)
        sub.setObjectName("cardSub")
        lay.addWidget(sub)
        lay.addStretch(1)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.title)
        super().mouseReleaseEvent(event)


class RecentProjectCard(QFrame):
    """One real recently-opened .rcmodel file: preview, name, modified time,
    a ⋮ menu (open / show in folder / remove from this list), and a click
    anywhere else on the card opens it -- no double-click needed."""

    clicked = Signal()
    open_requested = Signal()
    reveal_requested = Signal()
    remove_requested = Signal()

    def __init__(self, title, meta, image_path, parent=None):
        super().__init__(parent); self.setObjectName('recentCard')
        self.setAttribute(Qt.WA_StyledBackground, True); self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(245, 178); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 10); layout.setSpacing(5)
        preview = QLabel(); preview.setFixedHeight(122); preview.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(image_path)
        preview.setPixmap(pixmap.scaled(440, 122, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        layout.addWidget(preview)
        row = QHBoxLayout(); row.setContentsMargins(10, 0, 4, 0); row.setSpacing(2)
        name = QLabel(title); name.setObjectName('recentTitle')
        row.addWidget(name, 1)
        menu_btn = QToolButton(); menu_btn.setText("⋮")
        menu_btn.setObjectName('recentMenuBtn'); menu_btn.setCursor(Qt.PointingHandCursor)
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(menu_btn)
        menu.addAction('เปิดโปรเจกต์', self.open_requested.emit)
        menu.addAction('แสดงตำแหน่งไฟล์', self.reveal_requested.emit)
        menu.addSeparator()
        menu.addAction('ลบออกจากรายการล่าสุด', self.remove_requested.emit)
        menu_btn.setMenu(menu)
        row.addWidget(menu_btn, 0, Qt.AlignRight)
        layout.addLayout(row)
        info = QLabel(meta); info.setObjectName('recentMeta'); info.setContentsMargins(10, 0, 10, 0)
        layout.addWidget(info)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HeroCard(QFrame):
    """The single, prominent 'Continue Designing' entry point into the full
    Building Model workflow -- deliberately bigger than the standalone
    member tools below it."""

    clicked = Signal()

    def __init__(self, title, subtitle, icon_name, button_text, parent=None):
        super().__init__(parent)
        self.setObjectName('heroCard')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 16, 22, 16)
        lay.setSpacing(18)
        icon = QLabel(); icon.setPixmap(svg_pixmap(icon_name, 40))
        icon.setFixedSize(48, 48); icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon, 0, Qt.AlignVCenter)
        text_col = QVBoxLayout(); text_col.setSpacing(4)
        t = QLabel(title); t.setObjectName('heroTitle'); text_col.addWidget(t)
        s = QLabel(subtitle); s.setObjectName('heroSub'); s.setWordWrap(True); text_col.addWidget(s)
        lay.addLayout(text_col, 1)
        btn = QPushButton(button_text); btn.setObjectName('heroButton')
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.clicked.emit)
        lay.addWidget(btn, 0, Qt.AlignVCenter)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HomePage(QWidget):
    """The landing page: real Recent Projects (backed by a small on-disk MRU
    list, not demo rows), a single prominent Building Model entry point,
    the standalone member tools below it, and a Project Overview panel that
    only shows numbers actually read off the current model.

    ``on_open`` receives a category / page name (unchanged contract with
    ``CategoryCard``). ``on_open_file`` receives a .rcmodel path from the
    Recent Projects list. ``get_project`` and ``get_building`` are lazy
    callables (Home is built before BuildingPage exists) returning the
    project dict and the BuildingPage instance respectively.
    """

    def __init__(self, on_open, on_open_file=None, get_project=None, get_building=None, parent=None):
        super().__init__(parent)
        self.setObjectName('homeRoot')
        self.on_open = on_open
        self._on_open_file = on_open_file
        self._get_project = get_project
        self._get_building = get_building

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        side = QFrame(); side.setObjectName('homeSide'); side.setFixedWidth(158)
        side_layout = QVBoxLayout(side); side_layout.setContentsMargins(18, 20, 18, 18); side_layout.setSpacing(10)
        brand = QLabel('RC CodePro'); brand.setObjectName('homeBrand'); side_layout.addWidget(brand)
        side_layout.addSpacing(10)
        new_project = QToolButton(); new_project.setText('New Project'); new_project.setObjectName('homeAction')
        new_project.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        new_project.setIcon(QIcon(icon_path('building'))); new_project.setIconSize(QSize(20, 20))
        new_project.clicked.connect(lambda: on_open('Project')); side_layout.addWidget(new_project)
        open_project = QToolButton(); open_project.setText('Open Project'); open_project.setObjectName('homeAction')
        open_project.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        open_project.setIcon(QIcon(icon_path('project'))); open_project.setIconSize(QSize(20, 20))
        open_project.clicked.connect(lambda: on_open('Building Model')); side_layout.addWidget(open_project)
        side_layout.addSpacing(8)
        recent_link = QPushButton('Recent'); recent_link.setObjectName('homeLink')
        recent_link.clicked.connect(lambda: self._scroll_to(self._recent_label))
        side_layout.addWidget(recent_link)
        side_layout.addStretch(1)
        for text, target in [('Getting Started', 'Help'), ('Tutorials', 'Help'), ('Support', 'Help')]:
            button = QPushButton(text); button.setObjectName('homeLink')
            button.clicked.connect(lambda _=False, name=target: on_open(name)); side_layout.addWidget(button)
        settings_link = QPushButton('Settings'); settings_link.setObjectName('homeLink')
        settings_link.clicked.connect(lambda: on_open('Parameters'))
        side_layout.addWidget(settings_link)
        outer.addWidget(side)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("homeScroll")
        self._scroll.setWidgetResizable(True)
        outer.addWidget(self._scroll, 1)

        body = QWidget()
        body.setObjectName('homeBody')
        self._scroll.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(24, 18, 24, 26)
        col.setSpacing(6)

        title = QLabel("Welcome to RC Code Pro")
        title.setObjectName("homeTitle")
        col.addWidget(title)
        self.home_subtitle = QLabel("")
        self.home_subtitle.setObjectName("homeSub")
        col.addWidget(self.home_subtitle)
        col.addSpacing(16)

        self._recent_label = QLabel('RECENT PROJECTS'); self._recent_label.setObjectName('sectionLabel')
        col.addWidget(self._recent_label)
        self._recent_grid = QGridLayout(); self._recent_grid.setSpacing(14)
        col.addLayout(self._recent_grid)
        self._recent_empty = QLabel('ยังไม่มีโปรเจกต์ที่เปิดหรือบันทึกไว้ — เริ่มจาก Building Model ด้านล่าง')
        self._recent_empty.setObjectName('cardSub')
        col.addWidget(self._recent_empty)
        col.addSpacing(18)

        continue_label = QLabel('CONTINUE DESIGNING'); continue_label.setObjectName('sectionLabel')
        col.addWidget(continue_label)
        hero_name, hero_thai, hero_icon, _soon = CATEGORIES[0]           # Building Model
        hero = HeroCard(hero_name,
                        f'สร้างโมเดลอาคารทั้งหลัง ({hero_thai}) — กริด, โมเดล, ถ่ายแรง, ออกแบบ',
                        hero_icon, 'เริ่ม Building Model  →')
        hero.clicked.connect(lambda: on_open(hero_name))
        col.addWidget(hero)
        col.addSpacing(18)

        tools_label = QLabel('STANDALONE DESIGN TOOLS'); tools_label.setObjectName('sectionLabel')
        col.addWidget(tools_label)
        tools_grid = QGridLayout()
        tools_grid.setSpacing(12)
        tools_grid.setContentsMargins(0, 0, 0, 0)
        standalone = CATEGORIES[1:]
        tools_cols = 4                                       # wrap, same as before -- 6 cards never fit one row
        for i in range(tools_cols):
            tools_grid.setColumnStretch(i, 1)
        for idx, (name, thai, icon, soon) in enumerate(standalone):
            card = CategoryCard(name, thai, icon, soon)
            card.clicked.connect(on_open)
            tools_grid.addWidget(card, idx // tools_cols, idx % tools_cols)
        col.addLayout(tools_grid)
        col.addSpacing(18)

        self._overview_stack = self._build_overview_panel()
        col.addWidget(self._overview_stack)
        col.addStretch(1)

        self.refresh()

    def _scroll_to(self, widget):
        self._scroll.ensureWidgetVisible(widget)

    # ---- Project Overview / Getting Started -------------------------
    def _build_overview_panel(self):
        card = QFrame(); card.setObjectName('overviewCard'); card.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(card); outer.setContentsMargins(20, 16, 20, 18); outer.setSpacing(0)
        stack = QStackedWidget()
        outer.addWidget(stack)

        getting_started = QWidget(); gs = QVBoxLayout(getting_started); gs.setSpacing(6)
        gs.setContentsMargins(0, 0, 0, 0)
        head = QLabel('GETTING STARTED'); head.setObjectName('sectionLabel'); gs.addWidget(head)
        for line in ("1. เริ่มจาก “Continue Designing” ด้านบน เพื่อสร้างกริดและโมเดลอาคาร",
                     "2. วาดเสา คาน พื้น และฐานราก ลงบนแปลน 2D",
                     "3. กด Run Load Path เพื่อคำนวณการถ่ายแรงเบื้องต้น",
                     "4. บันทึกโปรเจกต์ (.rcmodel) เพื่อให้ขึ้นในรายการล่าสุด"):
            lbl = QLabel(line); lbl.setObjectName('cardSub'); gs.addWidget(lbl)
        stack.addWidget(getting_started)

        overview = QWidget(); ov = QVBoxLayout(overview); ov.setSpacing(6)
        ov.setContentsMargins(0, 0, 0, 0)
        ov_head = QLabel('PROJECT OVERVIEW'); ov_head.setObjectName('sectionLabel'); ov.addWidget(ov_head)
        self._overview_counts = QLabel(''); self._overview_counts.setObjectName('cardSub')
        self._overview_counts.setWordWrap(True)
        self._overview_status = QLabel(''); self._overview_status.setObjectName('cardSub')
        ov.addWidget(self._overview_counts)
        ov.addWidget(self._overview_status)
        stack.addWidget(overview)

        self._overview_pages = stack
        return card

    def _refresh_overview(self):
        building = self._get_building() if self._get_building else None
        data = building.overview_data() if building is not None else None
        if not data or not data.get('has_model'):
            self._overview_pages.setCurrentIndex(0)
            return
        self._overview_pages.setCurrentIndex(1)
        counts_txt = '  ·  '.join(f"{KIND_TH.get(k, k)} {c}" for k, c in data['counts'].items())
        self._overview_counts.setText(f"องค์ประกอบ: {counts_txt or '—'}   ·   ระดับ: {data['levels']}")
        self._overview_status.setText(
            f"โมเดล: {data['model_status']}   ·   การถ่ายแรง: {data['analysis_status']}   ·   ออกแบบ: {data['design_status']}")

    # ---- Recent Projects (real MRU) ----------------------------------
    def _refresh_recent(self):
        while self._recent_grid.count():
            item = self._recent_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Detach immediately (deleteLater alone leaves it a live
                # child, still visible to findChildren, until the event
                # loop gets around to the deferred delete).
                widget.setParent(None)
                widget.deleteLater()
        paths = recent_files.load()
        self._recent_empty.setVisible(not paths)
        preview_path = os.path.join(resource_root(), 'assets', 'project_previews', 'concrete-frame.png')
        for i, path in enumerate(paths[:4]):
            try:
                meta = f"แก้ไขล่าสุด: {_relative_time(os.path.getmtime(path))}"
            except OSError:
                meta = ''
            title = os.path.splitext(os.path.basename(path))[0]
            card = RecentProjectCard(title, meta, preview_path)
            card.clicked.connect(lambda _=False, p=path: self._open_recent(p))
            card.open_requested.connect(lambda p=path: self._open_recent(p))
            card.reveal_requested.connect(lambda p=path: self._reveal_in_folder(p))
            card.remove_requested.connect(lambda p=path: self._remove_recent(p))
            self._recent_grid.addWidget(card, 0, i); self._recent_grid.setColumnStretch(i, 1)

    def _open_recent(self, path):
        if self._on_open_file is not None:
            self._on_open_file(path)
        else:
            self.on_open('Building Model')

    def _reveal_in_folder(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path) or '.'))

    def _remove_recent(self, path):
        recent_files.remove(path)
        self._refresh_recent()

    # ---- called whenever the user navigates back to Home -------------
    def refresh(self):
        project = self._get_project() if self._get_project else {}
        name = (project or {}).get('name')
        self.home_subtitle.setText(
            f"{name} · ACI 318M-19 · Metric (cm · kg)" if name else "Structural Design & Analysis")
        self._refresh_recent()
        self._refresh_overview()


class PlaceholderPage(QWidget):
    """Centered 'coming soon' page for Wall / Parameters / Help."""

    def __init__(self, title, note, icon_name="tools", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        icon = QLabel()
        icon.setPixmap(svg_pixmap(icon_name, 64))
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)
        lay.addSpacing(14)
        head = QLabel(title)
        head.setObjectName("phTitle")
        head.setAlignment(Qt.AlignCenter)
        lay.addWidget(head)
        body = QLabel(note)
        body.setObjectName("phNote")
        body.setAlignment(Qt.AlignCenter)
        body.setWordWrap(True)
        lay.addWidget(body)
        lay.addStretch(2)
