"""Free-draw 2D plan editor for the native Building Model page.

World units are centimetres (1 m = 100). Members are stored as plain dicts
``{'kind', 'points': [(x, y), ...], 'section': <label str>}`` plus their
QGraphicsItem.

Grid lines (``kind='grid'``) are finite, axis-aligned segments with two
editable endpoints (``points = [(x1, y1), (x2, y2)]``): for a vertical grid
both x are equal (the grid coordinate) and y1..y2 is its length; for a
horizontal grid both y are equal and x1..x2 is its length. They carry an
auto label (A, B, C… / 1, 2, 3…) and automatic dimension strings between
consecutive lines. During creation the length follows a click-drag (or a
typed distance + Enter); afterwards either endpoint handle can be dragged
freely to change the length and shift the line.

Nothing here analyses forces -- it is an authoring surface only.
"""
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QLineF, QEvent
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF, QFont
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
                               QGraphicsLineItem, QGraphicsPolygonItem,
                               QGraphicsRectItem, QGraphicsSimpleTextItem, QMenu)

POINT_KINDS = ('column', 'footing')
LINE_KINDS = ('beam', 'stair')
POLY_KINDS = ('slab',)
KIND_TH = {'column': 'เสา', 'beam': 'คาน', 'slab': 'พื้น',
           'footing': 'ฐานราก', 'stair': 'บันได', 'grid': 'กริด'}
KIND_COLOR = {'column': '#d97706', 'beam': '#2563eb', 'slab': '#0ea5e9',
              'footing': '#16a34a', 'stair': '#7c3aed', 'grid': '#94a3b8'}
_SNAP_PICK_CM = 18.0
_GRID_LINE = '#94a3b8'
_GRID_BUBBLE = '#475569'
_DIM_COLOR = '#2563eb'
_HANDLE = '#2563eb'


def _num(s):
    try:
        v = float(s)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _label_seq(axis, i):
    if axis == 'v':
        s = ''
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    return str(i + 1)


class PlanCanvas(QGraphicsView):
    changed = Signal()
    picked = Signal(object)
    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(-8000, -8000, 16000, 16000, self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.scale(1, -1)

        self.setFocusPolicy(Qt.StrongFocus)
        self.mode = 'select'
        self.grid_axis = 'v'
        self.snap = True
        self.grid_cm = 100.0
        self.members = []
        self.selected = None
        self.selected_set = []
        self._band_origin = None         # left-drag rubber-band select origin
        self._pending = []
        self._section_lookup = lambda kind: kind.upper()
        self._cursor_items = []
        self._dim_items = []
        self._last_grid = {'v': None, 'h': None}
        self._type_buffer = ''
        self._last_cursor = None
        self._grid_ref = None            # (axis, ref_coord_or_None, direction)
        self._grid_start = None          # first endpoint (x, y) while drawing a grid
        self._grid_press = None          # press screen pos, to tell click from drag
        self._axis_override = None       # user pressed Tab to fix the grid axis
        self._drag_handle = None         # (grid_member, endpoint_index) while editing
        self._linked = []                # (grid, endpoint_index) that follow the drag
        self.current_level = None        # {'name', 'elev'} being drawn on, or None
        self._pt_axis_override = None    # Tab-fixed offset axis for point placement
        self._pt_target = None           # live (x, y) while hovering a point/line tool
        self.scale(0.55, 0.55)
        self.centerOn(200, 200)

    # ---- configuration ------------------------------------------------
    def set_mode(self, mode):
        self.mode = mode
        self._pending = []
        self._last_grid = {'v': None, 'h': None}
        self._type_buffer = ''
        self._grid_ref = None
        self._grid_start = None
        self._axis_override = None
        self._pt_axis_override = None
        self._pt_target = None
        self._drag_handle = None
        self._linked = []
        self._band_origin = None
        self._clear_cursor()
        self.setCursor(Qt.ArrowCursor if mode == 'select' else Qt.CrossCursor)
        if mode != 'select':
            self.setFocus()
        self.mode_changed.emit(mode)

    def set_current_level(self, name, elev):
        self.current_level = {'name': name, 'elev': float(elev)}
        self._apply_level_visibility()

    def _apply_level_visibility(self):
        cur = self.current_level['name'] if self.current_level else None
        for m in self.members:
            if m['kind'] == 'grid':
                continue
            faded = cur is not None and m.get('level') not in (None, cur)
            m['item'].setOpacity(0.25 if faded else 1.0)

    def _exit_to_select(self):
        self._pending = []
        self._type_buffer = ''
        self._grid_start = None
        self._clear_cursor()
        self.set_mode('select')

    def set_grid_axis(self, axis):
        self.grid_axis = 'h' if axis == 'h' else 'v'
        self._grid_start = None
        self._clear_cursor()

    def set_section_lookup(self, fn):
        self._section_lookup = fn

    def set_snap(self, on):
        self.snap = bool(on)
        self.viewport().update()

    # ---- grid geometry helpers -----------------------------------
    @staticmethod
    def _grid_coord(m):
        return m['points'][0][0] if m['axis'] == 'v' else m['points'][0][1]

    @staticmethod
    def _grid_span(m):
        i = 1 if m['axis'] == 'v' else 0
        a, b = m['points'][0][i], m['points'][1][i]
        return (min(a, b), max(a, b))

    def _grid_coords(self, axis):
        return sorted(self._grid_coord(m) for m in self.members
                      if m['kind'] == 'grid' and m.get('axis') == axis)

    def _default_grid_span(self, axis):
        # a new grid line matches the extent of the grid lines already on
        # its own axis, so consecutive lines line up end-to-end.
        sames = [m for m in self.members if m['kind'] == 'grid' and m.get('axis') == axis]
        if sames:
            los = [self._grid_span(m)[0] for m in sames]
            his = [self._grid_span(m)[1] for m in sames]
            return (min(los), max(his))
        vals = []
        other = 'h' if axis == 'v' else 'v'
        for m in self.members:
            if m['kind'] == 'grid':
                if m.get('axis') == other:
                    vals.append(self._grid_coord(m))
                continue
            for (px, py) in m['points']:
                vals.append(py if axis == 'v' else px)
        if not vals:
            return (-100.0, 600.0)
        lo, hi = min(vals), max(vals)
        pad = max(120.0, (hi - lo) * 0.15)
        lo, hi = lo - pad, hi + pad
        if hi - lo < 500.0:
            mid = (lo + hi) / 2.0
            lo, hi = mid - 250.0, mid + 250.0
        return (lo, hi)

    def _snap_coord(self, value, axis):
        """Snap a perpendicular coordinate to an existing grid line, else 1 cm."""
        for c in self._grid_coords(axis):
            if abs(c - value) <= _SNAP_PICK_CM:
                return float(c)
        return float(round(value))

    def _snap_along(self, value, axis):
        """Snap the free (length) direction to another grid's endpoint span."""
        other = 'h' if axis == 'v' else 'v'
        for m in self.members:
            if m['kind'] == 'grid' and m.get('axis') == axis:
                for lo_hi in (self._grid_span(m),):
                    for c in lo_hi:
                        if abs(c - value) <= _SNAP_PICK_CM:
                            return float(c)
        for c in self._grid_coords(other):
            if abs(c - value) <= _SNAP_PICK_CM:
                return float(c)
        return float(round(value))

    def _snap_grid_pt(self, sp, axis):
        if axis == 'v':
            return (self._snap_coord(sp.x(), 'v'), self._snap_along(sp.y(), 'v'))
        return (self._snap_along(sp.x(), 'h'), self._snap_coord(sp.y(), 'h'))

    def _snap_point(self, sp):
        x, y = sp.x(), sp.y()
        for m in self.members:
            if m['kind'] == 'grid':
                continue
            for (px, py) in m['points']:
                if abs(px - x) <= _SNAP_PICK_CM and abs(py - y) <= _SNAP_PICK_CM:
                    return (px, py)
        gv = self._grid_coords('v')
        gh = self._grid_coords('h')
        for gx in gv:
            if abs(gx - x) <= _SNAP_PICK_CM:
                x = gx
        for gy in gh:
            if abs(gy - y) <= _SNAP_PICK_CM:
                y = gy
        if self.snap and self.grid_cm > 0:
            if x not in gv:
                x = round(x / self.grid_cm) * self.grid_cm
            if y not in gh:
                y = round(y / self.grid_cm) * self.grid_cm
        return (float(x), float(y))

    def _content_span(self):
        xs, ys = [], []
        for m in self.members:
            if m['kind'] == 'grid':
                continue
            for (px, py) in m['points']:
                xs.append(px); ys.append(py)
        if not xs:
            return (-200.0, 600.0, -200.0, 600.0)
        return (min(xs) - 200, max(xs) + 200, min(ys) - 200, max(ys) + 200)

    def _scene_tol(self):
        m11 = abs(self.transform().m11()) or 1.0
        return max(18.0, 15.0 / m11)

    # ---- member construction --------------------------------------
    def _make_item(self, kind, points):
        color = QColor(KIND_COLOR[kind])
        if kind in POINT_KINDS:
            x, y = points[0]
            r = 11.0
            it = QGraphicsEllipseItem(QRectF(x - r, y - r, 2 * r, 2 * r))
            it.setBrush(QBrush(color if kind == 'column' else QColor('#ffffff')))
            it.setPen(QPen(color, 3))
        elif kind in LINE_KINDS:
            (x1, y1), (x2, y2) = points
            it = QGraphicsLineItem(QLineF(x1, y1, x2, y2))
            pen = QPen(color, 6)
            if kind == 'stair':
                pen.setStyle(Qt.DashLine)
            it.setPen(pen)
        else:
            it = QGraphicsPolygonItem(QPolygonF([QPointF(x, y) for x, y in points]))
            it.setPen(QPen(color, 3))
            fill = QColor(color); fill.setAlpha(45)
            it.setBrush(QBrush(fill))
        it.setZValue(10 if kind in POINT_KINDS else 5)
        self._scene.addItem(it)
        return it

    def add_member(self, kind, points, section=None, *, emit=True, level=None):
        section = section or self._section_lookup(kind)
        lvl = level if level is not None else self.current_level
        member = {'kind': kind, 'points': [tuple(map(float, p)) for p in points],
                  'section': section, 'item': self._make_item(kind, points),
                  'level': (lvl['name'] if isinstance(lvl, dict) else lvl),
                  'z': (float(lvl['elev']) if isinstance(lvl, dict) else 0.0)}
        self.members.append(member)
        self._apply_level_visibility()
        if emit:
            self.changed.emit()
        return member

    # ---- grid lines ---------------------------------------------
    def add_grid(self, axis, coord, span=None, *, emit=True):
        axis = 'h' if axis == 'h' else 'v'
        a, b = span if span else self._default_grid_span(axis)
        a, b = float(min(a, b)), float(max(a, b))
        coord = float(coord)
        pts = [(coord, a), (coord, b)] if axis == 'v' else [(a, coord), (b, coord)]
        member = {'kind': 'grid', 'axis': axis, 'label': '?', 'section': '',
                  'points': pts, 'item': None}
        member['item'] = self._make_grid_item(member)
        self.members.append(member)
        self._last_grid[axis] = coord
        self._rebuild_grid_annotations()
        if emit:
            self.changed.emit()
        return member

    def add_grid_seg(self, axis, p1, p2, *, emit=True):
        axis = 'h' if axis == 'h' else 'v'
        if axis == 'v':
            return self.add_grid(axis, p1[0], (p1[1], p2[1]), emit=emit)
        return self.add_grid(axis, p1[1], (p1[0], p2[0]), emit=emit)

    def add_next_grid(self, spacing_m, axis=None):
        axis = axis or self.grid_axis
        coords = self._grid_coords(axis)
        if not coords:
            return self.add_grid(axis, 0.0)
        return self.add_grid(axis, coords[-1] + float(spacing_m) * 100.0)

    def _make_grid_item(self, member):
        line = QGraphicsLineItem()
        pen = QPen(QColor(_GRID_LINE), 0); pen.setStyle(Qt.DashDotLine)
        line.setPen(pen); line.setZValue(1)
        self._scene.addItem(line)
        member['item'] = line
        r = 60.0
        bub = QGraphicsEllipseItem(QRectF(-r, -r, 2 * r, 2 * r))
        bub.setPen(QPen(QColor(_GRID_BUBBLE), 0)); bub.setBrush(QBrush(QColor('#ffffff')))
        bub.setZValue(2); self._scene.addItem(bub)
        txt = QGraphicsSimpleTextItem(member['label'])
        f = QFont(); f.setPointSizeF(26); f.setBold(True); txt.setFont(f)
        txt.setBrush(QBrush(QColor(_GRID_BUBBLE)))
        txt.setTransform(txt.transform().scale(1, -1))
        txt.setZValue(3); self._scene.addItem(txt)
        handles = []
        for _ in range(2):
            h = QGraphicsRectItem(QRectF(-8, -8, 16, 16))
            h.setPen(QPen(QColor(_HANDLE), 0)); h.setBrush(QBrush(QColor('#ffffff')))
            h.setZValue(8); self._scene.addItem(h)
            handles.append(h)
        member['_bubble'] = bub
        member['_text'] = txt
        member['_handles'] = handles
        self._resize_grid_line(member)
        return line

    def _resize_grid_line(self, member):
        (x1, y1), (x2, y2) = member['points']
        member['item'].setLine(QLineF(x1, y1, x2, y2))
        for h, (hx, hy) in zip(member['_handles'], member['points']):
            h.setRect(QRectF(hx - 8, hy - 8, 16, 16))
        self._place_grid_bubble(member)

    # dimension / bubble stack offsets, measured from the framework edge
    _DIM_CHAIN_OFF = 110.0
    _DIM_TOTAL_OFF = 230.0
    _BUBBLE_OFF = 370.0

    def _place_grid_bubble(self, member):
        axis = member['axis']
        flo, fhi = self._grid_axis_extent(axis)
        coord = self._grid_coord(member)
        r = 60.0
        if axis == 'v':
            # A, B, C -- bubbles sit below the framework
            bx, by = coord, flo - self._BUBBLE_OFF
        else:
            # 1, 2, 3 -- bubbles sit to the left of the framework
            bx, by = flo - self._BUBBLE_OFF, coord
        member['_bubble'].setRect(QRectF(bx - r, by - r, 2 * r, 2 * r))
        tb = member['_text'].boundingRect()
        member['_text'].setPos(bx - tb.width() / 2, by + tb.height() / 2)

    def _clear_grid_dims(self):
        for it in self._dim_items:
            self._scene.removeItem(it)
        self._dim_items = []

    def _rebuild_grid_annotations(self):
        self._clear_grid_dims()
        for axis in ('v', 'h'):
            grids = sorted((m for m in self.members if m['kind'] == 'grid'
                            and m.get('axis') == axis), key=self._grid_coord)
            for i, m in enumerate(grids):
                m['label'] = _label_seq(axis, i)
                m['_text'].setText(m['label'])
                self._resize_grid_line(m)
            for a, b in zip(grids, grids[1:]):
                self._add_dim(axis, a, b)
            if len(grids) >= 2:
                self._add_dim(axis, grids[0], grids[-1], total=True)

    def _add_dim(self, axis, a, b, *, transient=False, total=False):
        ca = self._grid_coord(a) if isinstance(a, dict) else float(a)
        cb = self._grid_coord(b) if isinstance(b, dict) else float(b)
        flo, fhi = self._grid_axis_extent(axis)
        off = self._DIM_TOTAL_OFF if total else self._DIM_CHAIN_OFF
        if axis == 'v':
            dy = flo - off
            p1, p2 = QPointF(ca, dy), QPointF(cb, dy)
            mid = QPointF((ca + cb) / 2, dy + 26)
        else:
            dx = flo - off
            p1, p2 = QPointF(dx, ca), QPointF(dx, cb)
            mid = QPointF(dx - 26, (ca + cb) / 2)
        if transient:
            col = QColor('#94a3b8')
        elif total:
            col = QColor('#1e3a8a')
        else:
            col = QColor(_DIM_COLOR)
        line = QGraphicsLineItem(QLineF(p1, p2))
        pen = QPen(col, 0)
        if transient:
            pen.setStyle(Qt.DashLine)
        line.setPen(pen); line.setZValue(4); self._scene.addItem(line)
        dist_m = abs(cb - ca) / 100.0
        txt = QGraphicsSimpleTextItem(f"{dist_m:.2f}")
        f = QFont(); f.setPointSizeF(20 if not transient else 18)
        f.setBold(not transient)
        txt.setFont(f); txt.setBrush(QBrush(col))
        txt.setTransform(txt.transform().scale(1, -1))
        tb = txt.boundingRect()
        txt.setPos(mid.x() - tb.width() / 2, mid.y() + tb.height() / 2)
        txt.setZValue(5); self._scene.addItem(txt)
        bucket = self._cursor_items if transient else self._dim_items
        bucket.extend((line, txt))
        for p in (p1, p2):
            t = QGraphicsLineItem(p.x() - 6, p.y() - 6, p.x() + 6, p.y() + 6)
            t.setPen(QPen(col, 0)); t.setZValue(4); self._scene.addItem(t)
            bucket.append(t)

    # ---- lifecycle -------------------------------------------------
    def delete_member(self, member):
        if member not in self.members:
            return
        self._scene.removeItem(member['item'])
        for k in ('_bubble', '_text'):
            if member.get(k) is not None:
                self._scene.removeItem(member[k])
        for h in member.get('_handles', []):
            self._scene.removeItem(h)
        self.members.remove(member)
        self.selected_set = [m for m in self.selected_set if m is not member]
        if self.selected is member:
            self.selected = self.selected_set[-1] if self.selected_set else None
        if member['kind'] == 'grid':
            self._rebuild_grid_annotations()
        self.changed.emit()

    def delete_selected(self):
        targets = list(self.selected_set) or ([self.selected] if self.selected else [])
        self.select_member(None)
        for m in targets:
            self.delete_member(m)

    def select_member(self, member):
        self.select_members([member] if member is not None else [])

    def select_members(self, members):
        self.selected_set = [m for m in members if m in self.members]
        self.selected = self.selected_set[-1] if self.selected_set else None
        for m in self.members:
            self._restyle(m, m in self.selected_set)
        self.picked.emit(self.selected)

    def set_selected_section(self, section):
        touched = False
        for m in self.selected_set:
            if m['kind'] != 'grid':
                m['section'] = section
                touched = True
        if touched:
            self.changed.emit()

    def _restyle(self, m, on):
        it = m['item']
        base = QColor(KIND_COLOR[m['kind']])
        hi = QColor('#dc2626')
        if m['kind'] == 'grid':
            pen = it.pen(); pen.setColor(hi if on else QColor(_GRID_LINE))
            pen.setWidth(2 if on else 0); it.setPen(pen)
            for h in m.get('_handles', []):
                h.setPen(QPen(hi if on else QColor(_HANDLE), 0))
                h.setBrush(QBrush(QColor('#fee2e2') if on else QColor('#ffffff')))
        elif isinstance(it, QGraphicsEllipseItem):
            it.setPen(QPen(hi if on else base, 4 if on else 3))
        elif isinstance(it, QGraphicsLineItem):
            pen = it.pen(); pen.setColor(hi if on else base); pen.setWidth(9 if on else 6)
            it.setPen(pen)
        else:
            it.setPen(QPen(hi if on else base, 4 if on else 3))

    def clear(self):
        for m in self.members:
            self._scene.removeItem(m['item'])
            for k in ('_bubble', '_text'):
                if m.get(k) is not None:
                    self._scene.removeItem(m[k])
            for h in m.get('_handles', []):
                self._scene.removeItem(h)
        self._clear_grid_dims()
        self.members = []
        self.selected = None
        self.selected_set = []
        self._pending = []
        self._last_grid = {'v': None, 'h': None}
        self._type_buffer = ''
        self._grid_ref = None
        self._grid_start = None
        self._axis_override = None
        self._pt_axis_override = None
        self._pt_target = None
        self._drag_handle = None
        self._linked = []
        self._band_origin = None
        self._clear_cursor()

    # ---- serialization -------------------------------------------
    def to_state(self):
        out = []
        for m in self.members:
            e = {'kind': m['kind'], 'points': [list(p) for p in m['points']],
                 'section': m['section']}
            if m['kind'] == 'grid':
                e['axis'] = m.get('axis', 'v')
                e['label'] = m.get('label', '?')
            else:
                e['level'] = m.get('level')
                e['z'] = m.get('z', 0.0)
            out.append(e)
        return {'grid_cm': self.grid_cm, 'snap': self.snap, 'members': out}

    def from_state(self, state):
        self.clear()
        if not isinstance(state, dict):
            return
        self.grid_cm = float(state.get('grid_cm', 100.0) or 100.0)
        self.snap = bool(state.get('snap', True))
        for raw in state.get('members', []):
            if not isinstance(raw, dict):
                continue
            kind = raw.get('kind')
            pts = raw.get('points')
            if kind not in KIND_TH or not isinstance(pts, list) or not pts:
                continue
            try:
                points = [(float(p[0]), float(p[1])) for p in pts]
            except (TypeError, ValueError, IndexError):
                continue
            if kind == 'grid':
                axis = 'h' if raw.get('axis') == 'h' else 'v'
                if len(points) >= 2:
                    self.add_grid_seg(axis, points[0], points[1], emit=False)
                else:
                    coord = points[0][0] if axis == 'v' else points[0][1]
                    self.add_grid(axis, coord, emit=False)
                continue
            need = 1 if kind in POINT_KINDS else (2 if kind in LINE_KINDS else 3)
            if len(points) < need:
                continue
            lvl = raw.get('level')
            zz = raw.get('z', 0.0)
            m = self.add_member(kind, points, str(raw.get('section', kind.upper())), emit=False)
            m['level'] = lvl if isinstance(lvl, str) else None
            m['z'] = float(zz) if isinstance(zz, (int, float)) else 0.0
        self._rebuild_grid_annotations()
        self._apply_level_visibility()
        self._scene.update()

    # ---- interaction --------------------------------------------
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def _hit_grid_handle(self, sp):
        tol = self._scene_tol()
        for m in self.members:
            if m['kind'] != 'grid':
                continue
            for idx, (hx, hy) in enumerate(m['points']):
                if abs(hx - sp.x()) <= tol and abs(hy - sp.y()) <= tol:
                    return (m, idx)
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._pan_last = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.RightButton:
            self._show_context_menu(event)
            return
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        sp = self.mapToScene(event.position().toPoint())
        if self.mode == 'select':
            hit = self._hit_grid_handle(sp)
            if hit is not None:
                self._drag_handle = hit
                self._linked = self._linked_endpoints(*hit)
                self.select_member(hit[0])
                self._band_origin = None
                return
            m = self._member_at(sp)
            if m is not None:
                self.select_member(m)
                self._band_origin = None
            else:
                self._band_origin = sp
            return
        if self.mode == 'grid':
            self._grid_press = event.position()
            if self._grid_start is None:
                self._grid_start = self._snap_grid_pt(sp, self.grid_axis)
            else:
                self._commit_grid_segment(sp)
            return
        if self.mode in POINT_KINDS:
            x, y = self._pt_target if self._pt_target is not None else self._snap_point(sp)
            self.add_member(self.mode, [(x, y)])
            self._type_buffer = ''
            self._pt_target = None
            self._clear_cursor()
        elif self.mode in LINE_KINDS:
            if not self._pending:
                x, y = self._pt_target if self._pt_target is not None else self._snap_point(sp)
                self._type_buffer = ''
                self._pt_target = None
            else:
                x, y = self._snap_point(sp)
            self._pending.append((x, y))
            if len(self._pending) == 2:
                self.add_member(self.mode, self._pending)
                self._pending = []
                self._clear_cursor()
        else:
            x, y = self._snap_point(sp)
            self._pending.append((x, y))
            self._draw_cursor_poly()

    def _commit_grid_segment(self, sp):
        axis = self.grid_axis
        start = self._grid_start
        end = self._snap_grid_pt(sp, axis)
        if axis == 'v':
            end = (start[0], end[1])
        else:
            end = (end[0], start[1])
        if abs((end[1] - start[1]) if axis == 'v' else (end[0] - start[0])) < 1.0:
            lo, hi = self._default_grid_span(axis)
            end = (start[0], hi) if axis == 'v' else (hi, start[1])
            start = (start[0], lo) if axis == 'v' else (lo, start[1])
        self.add_grid_seg(axis, start, end)
        self._grid_start = None
        self._clear_cursor()

    def mouseDoubleClickEvent(self, event):
        if self.mode in POLY_KINDS and len(self._pending) >= 3:
            self.add_member(self.mode, self._pending)
            self._pending = []
            self._clear_cursor()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_pan_last', None) is not None and (event.buttons() & Qt.MiddleButton):
            delta = event.position() - self._pan_last
            self._pan_last = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            return
        sp = self.mapToScene(event.position().toPoint())
        if self.mode == 'select' and self._drag_handle is not None:
            self._drag_grid_handle(sp)
        elif self.mode == 'select' and self._band_origin is not None and (event.buttons() & Qt.LeftButton):
            self._draw_band(self._band_origin, sp)
        elif self.mode == 'grid':
            self._last_cursor = sp
            self.grid_axis = self._resolve_grid_axis(sp)
            if self._grid_start is not None:
                self._grid_seg_preview(sp)
            else:
                self._grid_preview(sp)
        elif self.mode in LINE_KINDS and len(self._pending) == 1:
            x, y = self._snap_point(sp)
            self._draw_cursor_line(self._pending[0], (x, y))
        elif self.mode in POINT_KINDS or self.mode in LINE_KINDS:
            self._last_cursor = sp
            self._point_preview(sp)
        super().mouseMoveEvent(event)

    def _grid_axis_extent(self, axis):
        grids = [m for m in self.members if m['kind'] == 'grid' and m.get('axis') == axis]
        if not grids:
            return (-100.0, 600.0)
        los = [self._grid_span(m)[0] for m in grids]
        his = [self._grid_span(m)[1] for m in grids]
        return (min(los), max(his))

    def _resolve_grid_axis(self, sp):
        """Which axis the next grid line runs along -- inferred from the
        pointer (or the current drag), unless the user fixed it with Tab."""
        if self._axis_override in ('v', 'h'):
            return self._axis_override
        if self._grid_start is not None:
            dx = abs(sp.x() - self._grid_start[0])
            dy = abs(sp.y() - self._grid_start[1])
            return 'v' if dy >= dx else 'h'
        # before the first click: a line dropped to the side of the frame is
        # vertical (A, B, C); one dropped above/below is horizontal (1, 2, 3).
        vg = [self._grid_coord(m) for m in self.members
              if m['kind'] == 'grid' and m['axis'] == 'v']
        hg = [self._grid_coord(m) for m in self.members
              if m['kind'] == 'grid' and m['axis'] == 'h']
        if vg and (sp.x() < min(vg) - _SNAP_PICK_CM or sp.x() > max(vg) + _SNAP_PICK_CM):
            return 'v'
        if hg and (sp.y() < min(hg) - _SNAP_PICK_CM or sp.y() > max(hg) + _SNAP_PICK_CM):
            return 'h'
        return self.grid_axis

    def toggle_grid_axis(self):
        self._axis_override = 'h' if self.grid_axis == 'v' else 'v'
        self.grid_axis = self._axis_override
        self._refresh_grid_preview()

    def _linked_endpoints(self, grid, idx):
        """Every other same-axis grid endpoint currently sharing this
        endpoint's along-position -- they move together when it is dragged."""
        axis = grid['axis']
        j = 1 if axis == 'v' else 0
        v0 = grid['points'][idx][j]
        out = []
        for m in self.members:
            if m['kind'] == 'grid' and m is not grid and m.get('axis') == axis:
                for k in (0, 1):
                    if abs(m['points'][k][j] - v0) <= _SNAP_PICK_CM:
                        out.append((m, k))
        return out

    def _drag_grid_handle(self, sp):
        m, idx = self._drag_handle
        axis = m['axis']
        if axis == 'v':
            coord = self._snap_coord(sp.x(), 'v')
            along = self._snap_along(sp.y(), 'v')
            m['points'][idx] = (coord, along)
            m['points'][1 - idx] = (coord, m['points'][1 - idx][1])
            for (lm, lk) in self._linked:
                lm['points'][lk] = (lm['points'][lk][0], along)
        else:
            coord = self._snap_coord(sp.y(), 'h')
            along = self._snap_along(sp.x(), 'h')
            m['points'][idx] = (along, coord)
            m['points'][1 - idx] = (m['points'][1 - idx][0], coord)
            for (lm, lk) in self._linked:
                lm['points'][lk] = (along, lm['points'][lk][1])
        self._rebuild_grid_annotations()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._pan_last = None
            self.setCursor(Qt.ArrowCursor if self.mode == 'select' else Qt.CrossCursor)
            return
        if event.button() == Qt.LeftButton:
            if self.mode == 'select' and self._drag_handle is not None:
                self._drag_handle = None
                self._linked = []
                self.changed.emit()
                return
            if self.mode == 'select' and self._band_origin is not None:
                sp = self.mapToScene(event.position().toPoint())
                if (sp - self._band_origin).manhattanLength() > 6:
                    self._select_in_rect(self._band_origin, sp)
                else:
                    self.select_member(None)
                self._band_origin = None
                self._clear_cursor()
                return
            if self.mode == 'grid' and self._grid_start is not None and self._grid_press is not None:
                moved = (event.position() - self._grid_press).manhattanLength()
                if moved > 6:
                    self._commit_grid_segment(self.mapToScene(event.position().toPoint()))
        super().mouseReleaseEvent(event)

    def event(self, e):
        # grab Tab before the focus system does, while drawing a grid or
        # while aiming a point/line member off a grid line
        if e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key_Tab:
            if self.mode == 'grid':
                self.toggle_grid_axis()
                return True
            if self.mode in POINT_KINDS or (self.mode in LINE_KINDS and not self._pending):
                self._toggle_point_axis()
                return True
        return super().event(e)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._pending = []
            self._type_buffer = ''
            self._grid_start = None
            self._pt_target = None
            self._pt_axis_override = None
            self._clear_cursor()
            if self.mode != 'select':
                self._exit_to_select()           # leave any create tool
            else:
                self.select_member(None)
            event.accept(); return
        if self.mode == 'grid':
            if event.key() == Qt.Key_Tab:
                self.toggle_grid_axis(); event.accept(); return
            t = event.text()
            if t and (t.isdigit() or t == '.'):
                self._grid_type_key(t); event.accept(); return
            if event.key() == Qt.Key_Backspace and self._type_buffer:
                self._grid_type_backspace(); event.accept(); return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._grid_confirm_typed(); event.accept(); return
        if self.mode in POINT_KINDS or (self.mode in LINE_KINDS and not self._pending):
            if event.key() == Qt.Key_Tab:
                self._toggle_point_axis(); event.accept(); return
            t = event.text()
            if t and (t.isdigit() or t == '.'):
                self._point_type_key(t); event.accept(); return
            if event.key() == Qt.Key_Backspace and self._type_buffer:
                self._type_buffer = self._type_buffer[:-1]
                self._refresh_point_preview(); event.accept(); return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._point_confirm_typed(); event.accept(); return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
        else:
            super().keyPressEvent(event)

    # ---- grid preview / typed input --------------------------------
    def _grid_preview(self, sp):
        self._clear_cursor()
        self._last_cursor = sp
        axis = self.grid_axis
        raw = self._snap_coord(sp.x() if axis == 'v' else sp.y(), axis)
        coords = self._grid_coords(axis)
        ref = self._last_grid[axis]
        if ref is None and coords:
            ref = min(coords, key=lambda c: abs(c - raw))
        direction = 1.0 if (ref is None or raw >= ref) else -1.0
        typed = _num(self._type_buffer)
        target = ref + direction * abs(typed) * 100.0 if (typed is not None and ref is not None) else raw
        self._grid_ref = (axis, ref, direction)
        x = target if axis == 'v' else sp.x()
        y = target if axis == 'h' else sp.y()
        self._draw_cross(x, y)
        if ref is not None and abs(target - ref) > 1e-6:
            a = {'points': [(ref, 0.0), (ref, 300.0)] if axis == 'v'
                 else [(0.0, ref), (300.0, ref)], 'axis': axis}
            self._add_dim(axis, a, target, transient=True)
        if self._type_buffer:
            self._draw_type_hint(x, y)

    def _grid_seg_preview(self, sp):
        self._clear_cursor()
        axis = self.grid_axis
        start = self._grid_start
        end = self._snap_grid_pt(sp, axis)
        end = (start[0], end[1]) if axis == 'v' else (end[0], start[1])
        it = QGraphicsLineItem(QLineF(start[0], start[1], end[0], end[1]))
        it.setPen(QPen(QColor('#db2777'), 0, Qt.DashLine)); it.setZValue(9)
        self._scene.addItem(it); self._cursor_items.append(it)
        self._draw_cross(end[0], end[1])
        length = abs((end[1] - start[1]) if axis == 'v' else (end[0] - start[0])) / 100.0
        txt = QGraphicsSimpleTextItem(
            (self._type_buffer + " m" if self._type_buffer else f"ยาว {length:.2f} m") + "  (คลิก/Enter)")
        f = QFont(); f.setPointSizeF(20); f.setBold(True); txt.setFont(f)
        txt.setBrush(QBrush(QColor('#db2777')))
        txt.setTransform(txt.transform().scale(1, -1))
        txt.setPos(end[0] + 30, end[1] + 26)
        txt.setZValue(10); self._scene.addItem(txt); self._cursor_items.append(txt)

    def _draw_cross(self, x, y):
        for a, b, c, d in ((x - 24, y - 24, x + 24, y + 24), (x - 24, y + 24, x + 24, y - 24)):
            it = QGraphicsLineItem(a, b, c, d)
            it.setPen(QPen(QColor('#db2777'), 0)); it.setZValue(9)
            self._scene.addItem(it); self._cursor_items.append(it)

    def _draw_type_hint(self, x, y):
        txt = QGraphicsSimpleTextItem(f"{self._type_buffer} m  (Enter)")
        f = QFont(); f.setPointSizeF(22); f.setBold(True); txt.setFont(f)
        txt.setBrush(QBrush(QColor('#db2777')))
        txt.setTransform(txt.transform().scale(1, -1))
        txt.setPos(x + 34, y + 30)
        txt.setZValue(10); self._scene.addItem(txt)
        self._cursor_items.append(txt)

    def _refresh_grid_preview(self):
        if self.mode != 'grid':
            return
        sp = self._last_cursor if self._last_cursor is not None else QPointF(0.0, 0.0)
        if self._grid_start is not None:
            self._grid_seg_preview(sp)
        else:
            self._grid_preview(sp)

    def _grid_type_key(self, ch):
        if ch.isdigit() or (ch == '.' and '.' not in self._type_buffer):
            self._type_buffer += ch
            self._refresh_grid_preview()

    def _grid_type_backspace(self):
        self._type_buffer = self._type_buffer[:-1]
        self._refresh_grid_preview()

    def _grid_confirm_typed(self):
        val = _num(self._type_buffer)
        self._type_buffer = ''
        if val is None:
            self._refresh_grid_preview()
            return
        axis = self.grid_axis
        if self._grid_start is not None:
            # typed value = the grid LENGTH, extended along the last drag direction
            start = self._grid_start
            cur = self._last_cursor or QPointF(start[0] + 100, start[1] + 100)
            along_cur = cur.y() if axis == 'v' else cur.x()
            along_start = start[1] if axis == 'v' else start[0]
            sgn = 1.0 if along_cur >= along_start else -1.0
            end_along = along_start + sgn * abs(val) * 100.0
            end = (start[0], end_along) if axis == 'v' else (end_along, start[1])
            self.add_grid_seg(axis, start, end)
            self._grid_start = None
            self._clear_cursor()
            return
        ref = self._grid_ref[1] if self._grid_ref else self._last_grid[axis]
        direction = self._grid_ref[2] if self._grid_ref else 1.0
        if ref is None:
            coords = self._grid_coords(axis)
            ref = coords[-1] if coords else None
        coord = (abs(val) * 100.0) if ref is None else (ref + direction * abs(val) * 100.0)
        self.add_grid(axis, coord)
        self._clear_cursor()

    # ---- off-grid point / line placement -------------------------
    def _nearest_grid(self, axis, value):
        coords = self._grid_coords(axis)
        if not coords:
            return None
        return min(coords, key=lambda c: abs(c - value))

    def _resolve_point_axis(self, sp):
        """Which offset a typed distance dials in: 'x' = distance from the
        nearest vertical grid, 'y' = distance from the nearest horizontal
        grid. Inferred from whichever offset is larger, unless Tab fixed it."""
        if self._pt_axis_override in ('x', 'y'):
            return self._pt_axis_override
        nv = self._nearest_grid('v', sp.x())
        nh = self._nearest_grid('h', sp.y())
        if nv is None:
            return 'y' if nh is not None else 'x'
        if nh is None:
            return 'x'
        return 'x' if abs(sp.x() - nv) >= abs(sp.y() - nh) else 'y'

    def _toggle_point_axis(self):
        cur = self._resolve_point_axis(self._last_cursor or QPointF(0.0, 0.0))
        self._pt_axis_override = 'y' if cur == 'x' else 'x'
        self._refresh_point_preview()

    def _point_type_key(self, ch):
        if ch.isdigit() or (ch == '.' and '.' not in self._type_buffer):
            self._type_buffer += ch
            self._refresh_point_preview()

    def _refresh_point_preview(self):
        if self.mode in POINT_KINDS or (self.mode in LINE_KINDS and not self._pending):
            sp = self._last_cursor if self._last_cursor is not None else QPointF(0.0, 0.0)
            self._point_preview(sp)

    def _point_preview(self, sp):
        self._clear_cursor()
        nv = self._nearest_grid('v', sp.x())
        nh = self._nearest_grid('h', sp.y())
        active = self._resolve_point_axis(sp)
        typed = _num(self._type_buffer)
        if typed is None:
            x, y = self._snap_point(sp)
        else:
            if active == 'x' and nv is not None:
                x = nv + (1.0 if sp.x() >= nv else -1.0) * abs(typed) * 100.0
            else:
                x = self._snap_coord(sp.x(), 'v')
            if active == 'y' and nh is not None:
                y = nh + (1.0 if sp.y() >= nh else -1.0) * abs(typed) * 100.0
            else:
                y = self._snap_coord(sp.y(), 'h')
        self._pt_target = (float(x), float(y))
        self._draw_cross(x, y)
        strong = active if typed is not None else None
        if nv is not None and abs(x - nv) > 1e-6:
            self._draw_measure((nv, y), (x, y), horizontal=True, strong=(strong == 'x'))
        if nh is not None and abs(y - nh) > 1e-6:
            self._draw_measure((x, nh), (x, y), horizontal=False, strong=(strong == 'y'))
        if self._type_buffer:
            self._draw_type_hint(x, y)

    def _draw_measure(self, p1, p2, *, horizontal, strong):
        col = QColor('#db2777' if strong else '#f472b6')
        ln = QGraphicsLineItem(QLineF(p1[0], p1[1], p2[0], p2[1]))
        pen = QPen(col, 0); pen.setStyle(Qt.DashLine)
        ln.setPen(pen); ln.setZValue(9)
        self._scene.addItem(ln); self._cursor_items.append(ln)
        for (px, py) in (p1, p2):
            t = QGraphicsLineItem(px - 6, py - 6, px + 6, py + 6)
            t.setPen(QPen(col, 0)); t.setZValue(9)
            self._scene.addItem(t); self._cursor_items.append(t)
        dist = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5 / 100.0
        txt = QGraphicsSimpleTextItem(f"{dist:.2f}")
        f = QFont(); f.setPointSizeF(19); f.setBold(bool(strong)); txt.setFont(f)
        txt.setBrush(QBrush(col))
        txt.setTransform(txt.transform().scale(1, -1))
        mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
        tb = txt.boundingRect()
        if horizontal:
            txt.setPos(mx - tb.width() / 2.0, my + tb.height() + 10)
        else:
            txt.setPos(mx + 14, my + tb.height() / 2.0)
        txt.setZValue(10); self._scene.addItem(txt); self._cursor_items.append(txt)

    def _point_confirm_typed(self):
        sp = self._last_cursor if self._last_cursor is not None else QPointF(0.0, 0.0)
        self._point_preview(sp)                 # fold the typed buffer into _pt_target
        target = self._pt_target
        self._type_buffer = ''
        self._pt_target = None
        if target is None:
            self._clear_cursor()
            return
        if self.mode in POINT_KINDS:
            self.add_member(self.mode, [target])
            self._clear_cursor()
        elif self.mode in LINE_KINDS and not self._pending:
            self._pending.append(target)
            self._clear_cursor()

    def _member_at(self, sp):
        best, best_d = None, _SNAP_PICK_CM * 2
        for m in self.members:
            if m['kind'] == 'grid':
                continue
            for (px, py) in m['points']:
                d = ((px - sp.x()) ** 2 + (py - sp.y()) ** 2) ** 0.5
                if d < best_d:
                    best_d, best = d, m
        if best is None:
            for m in self.members:
                if m['kind'] in LINE_KINDS:
                    (x1, y1), (x2, y2) = m['points']
                    if _dist_to_seg(sp.x(), sp.y(), x1, y1, x2, y2) < _SNAP_PICK_CM:
                        best = m
                        break
        if best is None:
            for m in self.members:
                if m['kind'] == 'grid':
                    (x1, y1), (x2, y2) = m['points']
                    if _dist_to_seg(sp.x(), sp.y(), x1, y1, x2, y2) < _SNAP_PICK_CM * 1.5:
                        best = m
                        break
        return best

    def _pick_at(self, sp):
        self.select_member(self._member_at(sp))

    def _select_in_rect(self, a, b):
        rx0, rx1 = sorted((a.x(), b.x()))
        ry0, ry1 = sorted((a.y(), b.y()))
        hits = [m for m in self.members
                if all(rx0 <= px <= rx1 and ry0 <= py <= ry1 for (px, py) in m['points'])]
        self.select_members(hits)

    def _draw_band(self, a, sp):
        self._clear_cursor()
        rx0, rx1 = sorted((a.x(), sp.x()))
        ry0, ry1 = sorted((a.y(), sp.y()))
        it = QGraphicsRectItem(QRectF(rx0, ry0, rx1 - rx0, ry1 - ry0))
        it.setPen(QPen(QColor('#2563eb'), 0, Qt.DashLine))
        fill = QColor('#2563eb'); fill.setAlpha(28)
        it.setBrush(QBrush(fill)); it.setZValue(9)
        self._scene.addItem(it); self._cursor_items.append(it)

    # ---- right-click context menu ---------------------------------
    def _build_context_menu(self, sp):
        menu = QMenu(self)
        hit = self._member_at(sp)
        if hit is None:
            hit = self._grid_at(sp)
        if hit is not None and hit not in self.selected_set:
            menu.addAction('เลือกชิ้นนี้', lambda h=hit: self.select_member(h))
        if self.selected_set:
            n = len(self.selected_set)
            menu.addAction(f'ลบที่เลือก ({n})' if n > 1 else 'ลบที่เลือก', self.delete_selected)
            menu.addAction('ยกเลิกการเลือก', lambda: self.select_member(None))
        elif hit is not None:
            menu.addAction('ลบชิ้นนี้', lambda h=hit: self.delete_member(h))
        if self.mode != 'select':
            menu.addSeparator()
            menu.addAction('ออกจากโหมดสร้าง (เลือก/แก้ไข)', self._exit_to_select)
        return menu

    def _grid_at(self, sp):
        for m in self.members:
            if m['kind'] == 'grid':
                (x1, y1), (x2, y2) = m['points']
                if _dist_to_seg(sp.x(), sp.y(), x1, y1, x2, y2) < _SNAP_PICK_CM * 1.5:
                    return m
        return None

    def _show_context_menu(self, event):
        sp = self.mapToScene(event.position().toPoint())
        menu = self._build_context_menu(sp)
        if not menu.isEmpty():
            menu.exec(event.globalPosition().toPoint())

    # ---- transient previews -------------------------------------
    def _clear_cursor(self):
        for it in self._cursor_items:
            self._scene.removeItem(it)
        self._cursor_items = []

    def _draw_cursor_line(self, a, b):
        self._clear_cursor()
        it = QGraphicsLineItem(QLineF(a[0], a[1], b[0], b[1]))
        it.setPen(QPen(QColor('#94a3b8'), 3, Qt.DashLine))
        it.setZValue(1); self._scene.addItem(it)
        self._cursor_items.append(it)
        d = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 / 100.0
        txt = QGraphicsSimpleTextItem(f"{d:.2f}")
        fnt = QFont(); fnt.setPointSizeF(18); txt.setFont(fnt)
        txt.setBrush(QBrush(QColor('#475569')))
        txt.setTransform(txt.transform().scale(1, -1))
        txt.setPos((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        txt.setZValue(9); self._scene.addItem(txt)
        self._cursor_items.append(txt)

    def _draw_cursor_poly(self):
        self._clear_cursor()
        if len(self._pending) < 2:
            return
        it = QGraphicsPolygonItem(QPolygonF([QPointF(x, y) for x, y in self._pending]))
        it.setPen(QPen(QColor('#94a3b8'), 2, Qt.DashLine))
        it.setZValue(1); self._scene.addItem(it)
        self._cursor_items.append(it)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor('#f8fafc'))
        # the background grid comes and goes with snap mode
        if self.snap and self.grid_cm > 0:
            step = self.grid_cm
            left = int(rect.left() - (rect.left() % step))
            top = int(rect.top() - (rect.top() % step))
            painter.setPen(QPen(QColor('#e2e8f0'), 0))
            x = left
            while x < rect.right():
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                x += step
            y = top
            while y < rect.bottom():
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                y += step
        painter.setPen(QPen(QColor('#cbd5e1'), 0))
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))


def _dist_to_seg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    cx, cy = x1 + t * dx, y1 + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
