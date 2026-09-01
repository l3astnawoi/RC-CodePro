"""Visual detailing — CAD-style RC drawings (matplotlib).

Every public ``draw_*`` helper returns a PNG image in an ``io.BytesIO``
buffer (positioned at 0) and works entirely in millimetres unless a
parameter name says otherwise.

The drawings imitate shop-drawing conventions:

* **Dimension lines** — bidirectional ``<->`` arrows placed *outside* the
  concrete outline, with thin witness lines back to the measured face and
  the dimension text centred on the line (spans in metres, section sizes
  in centimetres).
* **Rebar call-outs** — a red ``->`` leader from the text to the exact bar
  it describes, e.g. ``11 - DB16 @ 20 cm``.
* **Dual views** — the footing and two-way-slab helpers draw a Plan view
  and a Side / Elevation view stacked vertically.
"""

import io
import math
import os

import matplotlib
matplotlib.use("Agg")            # headless backend (Streamlit / servers)
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import font_manager as _fm

# ---------------------------------------------------------------------------
# Thai text — register THSarabunNew.ttf so call-out labels render correctly
# (matplotlib's default DejaVu Sans has no Thai glyphs).  Latin / mathtext
# fall back to DejaVu.
# ---------------------------------------------------------------------------
_FONT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fonts", "THSarabunNew.ttf",
)
if os.path.isfile(_FONT_PATH):
    try:
        _fm.fontManager.addfont(_FONT_PATH)
        _THAI_FAMILY = _fm.FontProperties(fname=_FONT_PATH).get_name()
        plt.rcParams["font.family"] = [_THAI_FAMILY, "DejaVu Sans"]
        plt.rcParams["font.size"] = 12.0
    except Exception:            # pragma: no cover - never break drawing
        pass

# ---------------------------------------------------------------------------
# Palette / style
# ---------------------------------------------------------------------------
_CONC_FILL = "#eef0f2"
_CONC_EDGE = "#1b1b1b"
_COL_FILL = "#d5d8dc"
_STEEL = "#c0392b"          # primary reinforcement (red)
_STEEL2 = "#8e44ad"         # secondary direction
_DIM = "#3b3b3b"            # dimension lines & text
_GRID_X = "#2f5d8a"         # bar grid, one way
_GRID_Y = "#c0504d"         # bar grid, other way

_DIM_FS = 12.0
_NOTE_FS = 11.5
_TITLE_FS = 13.0

# --- A4-portrait layout for the true-scale detail sheets --------------------
# figsize maps 7.0 x 9.5 in onto an A4 page; dpi 300 exports crisply into PDF.
_A4_FIGSIZE = (7.0, 9.5)
_A4_DPI = 300
_A4_ADJUST = dict(hspace=0.40, top=0.92, bottom=0.08, left=0.10, right=0.90)
# smaller annotation type so callouts stay proportional on the larger sheet
_A4_DIM_FS = 9.5
_A4_NOTE_FS = 9.0
_A4_TITLE_FS = 11.0


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _even_spread(a, b, k):
    """k points from a to b inclusive (k == 1 -> midpoint)."""
    if k <= 1:
        return [(a + b) / 2.0]
    step = (b - a) / (k - 1)
    return [a + i * step for i in range(k)]


def _interior(a, b, k):
    """k points strictly between a and b (empty if k <= 0)."""
    if k <= 0:
        return []
    step = (b - a) / (k + 1)
    return [a + step * (i + 1) for i in range(k)]


def _bars_by_spacing(width, spacing):
    """Centre x-positions of bars laid out at `spacing` across `width`,
    centred so the outermost bars sit symmetrically inside the edges."""
    spacing = max(float(spacing), 1.0)
    n = max(int(width // spacing) + 1, 2)
    span = (n - 1) * spacing
    start = (width - span) / 2.0
    return [start + i * spacing for i in range(n)]


def _count_by_spacing(length, spacing):
    """Number of bars fitting across `length` at centre-to-centre `spacing`."""
    spacing = max(float(spacing), 1.0)
    return max(int(round(length / spacing)) + 1, 2)


def _save_buf(fig, *, dpi=150, tight=True):
    buf = io.BytesIO()
    kw = dict(format="png", dpi=dpi)
    if tight:                       # crop surrounding whitespace (default)
        kw["bbox_inches"] = "tight"
    fig.savefig(buf, **kw)          # otherwise keep the explicit A4 margins
    plt.close(fig)
    buf.seek(0)
    return buf


def fig_to_png_buf(fig, *, dpi=150):
    """Render a Matplotlib figure to a PNG ``BytesIO`` (0-seeked) and close
    it.  For helpers that hand back a live ``Figure`` (so the caller can
    ``st.pyplot`` it) but still need a buffer for the PDF report."""
    return _save_buf(fig, dpi=dpi, tight=True)


def _apply_true_scale(ax, x_lo, x_hi, y_lo, y_hi):
    """Lock an axis to a data window at strict 1:1 (equal) aspect and hide it.

    When two stacked subplots are given the *same* x-window and heights that
    are proportional to their y-windows, `adjustable='box'` renders both at
    an identical mm-per-inch scale -> the real proportions between L, W and h
    are preserved across the Plan and the Side / Section view.
    """
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_lo, y_hi)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")


# ---------------------------------------------------------------------------
# CAD annotation primitives
# ---------------------------------------------------------------------------
def _hdim(ax, x1, x2, y_dim, y_face, text, *, below=True, fs=_DIM_FS):
    """Horizontal dimension: witness lines from the measured face
    (``y_face``) out to ``y_dim``, a ``<->`` line between x1 and x2, and the
    dimension text centred just outside the line."""
    for x in (x1, x2):
        ax.plot([x, x], [y_face, y_dim], color=_DIM, lw=0.7, zorder=5)
    ax.annotate("", xy=(x1, y_dim), xytext=(x2, y_dim),
                arrowprops=dict(arrowstyle="<->", color=_DIM, lw=1.0,
                                shrinkA=0, shrinkB=0), zorder=6)
    dy = -1.0 if below else 1.0
    ax.text((x1 + x2) / 2.0, y_dim + dy * abs(y_dim - y_face) * 0.28, text,
            ha="center", va="top" if below else "bottom",
            fontsize=fs, color=_DIM,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"),
            zorder=7)


def _vdim(ax, y1, y2, x_dim, x_face, text, *, left=False, fs=_DIM_FS):
    """Vertical dimension line, mirror of :func:`_hdim`."""
    for y in (y1, y2):
        ax.plot([x_face, x_dim], [y, y], color=_DIM, lw=0.7, zorder=5)
    ax.annotate("", xy=(x_dim, y1), xytext=(x_dim, y2),
                arrowprops=dict(arrowstyle="<->", color=_DIM, lw=1.0,
                                shrinkA=0, shrinkB=0), zorder=6)
    dx = -1.0 if left else 1.0
    ax.text(x_dim + dx * abs(x_dim - x_face) * 0.28, (y1 + y2) / 2.0, text,
            ha="right" if left else "left", va="center", rotation=90,
            fontsize=fs, color=_DIM,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"),
            zorder=7)


def _callout(ax, target_xy, label_xy, text, *, color=_STEEL, fs=_NOTE_FS,
             ha="center"):
    """Red leader arrow from the text box to the exact bar it annotates."""
    ax.annotate(text, xy=target_xy, xytext=label_xy,
                arrowprops=dict(arrowstyle="->", color=color, lw=1.2,
                                shrinkA=1, shrinkB=1,
                                connectionstyle="arc3,rad=-0.15"),
                fontsize=fs, color=color,
                ha=ha, va="center",
                bbox=dict(boxstyle="round,pad=0.28", fc="white",
                          ec=color, lw=1.0),
                zorder=8)


def _frame(ax, x0, x1, y0, y1, *, l=0.12, r=0.12, b=0.12, t=0.12):
    """Set limits with fractional padding on each side; hide the axes."""
    w = max(x1 - x0, 1.0)
    hh = max(y1 - y0, 1.0)
    ax.set_xlim(x0 - l * w, x1 + r * w)
    ax.set_ylim(y0 - b * hh, y1 + t * hh)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")


def _m(mm):
    """mm -> metres, trimmed."""
    return f"{mm / 1000.0:.2f}"


def _cm(mm):
    """mm -> centimetres, trimmed."""
    v = mm / 10.0
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}"


# ---------------------------------------------------------------------------
# Bar-position helpers (single-section drawings)
# ---------------------------------------------------------------------------
def _beam_positions(n, x0, x1, y0, y1):
    """Single bottom row of `n` bars along the inner bottom edge."""
    return [(x, y0) for x in _even_spread(x0, x1, n)]


def _column_positions(n, x0, x1, y0, y1):
    """`n` bars around the perimeter: four corners first, then the
    remainder split as evenly as possible over bottom/right/top/left."""
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if n <= 4:
        return corners[:n]

    remaining = n - 4
    per_side = [remaining // 4] * 4
    for i in range(remaining % 4):
        per_side[i] += 1

    pts = list(corners)
    pts += [(x, y0) for x in _interior(x0, x1, per_side[0])]   # bottom
    pts += [(x1, y) for y in _interior(y0, y1, per_side[1])]   # right
    pts += [(x, y1) for x in _interior(x0, x1, per_side[2])]   # top
    pts += [(x0, y) for y in _interior(y0, y1, per_side[3])]   # left
    return pts


def _beam_bar_row(ax, n, dia, x_lo, x_hi, y):
    """Draw `n` filled bars of diameter `dia` along a row at height `y`."""
    n = max(int(n), 1)
    r = float(dia) / 2.0
    if x_hi < x_lo:
        x_lo = x_hi = (x_lo + x_hi) / 2.0
    xs = ([(x_lo + x_hi) / 2.0] if n == 1
          else [x_lo + i * (x_hi - x_lo) / (n - 1) for i in range(n)])
    for x in xs:
        ax.add_patch(patches.Circle((x, y), r, facecolor="black",
                                    edgecolor="black", zorder=4))
    return xs


# ===========================================================================
# Beam — single cross-section
# ===========================================================================
def draw_rc_section(b_mm, h_mm, covering_mm, rebar_dia_mm, qty,
                    section_type="beam", *, bar_label=None,
                    stirrup_label=None, top_label=None):
    """RC rectangular cross-section with b / h dimension lines and rebar
    call-outs.

    bar_label     : e.g. "3 - DB20"  (main / bottom bars)
    stirrup_label : e.g. "RB9 @ 15 cm"
    top_label     : optional "2 - DB12" for a top compression row (beam)
    """
    b = float(b_mm)
    h = float(h_mm)
    cov = float(covering_mm)
    r = float(rebar_dia_mm) / 2.0
    n = max(int(qty), 1)

    fig, ax = plt.subplots(figsize=(4.6, 4.8))

    ax.add_patch(patches.Rectangle((0.0, 0.0), b, h, edgecolor=_CONC_EDGE,
                                   facecolor=_CONC_FILL, linewidth=1.8))

    inner_w = max(b - 2.0 * cov, 0.0)
    inner_h = max(h - 2.0 * cov, 0.0)
    ax.add_patch(patches.Rectangle((cov, cov), inner_w, inner_h,
                                   edgecolor="#404040", facecolor="none",
                                   linewidth=1.2))

    x0, x1 = cov + r, cov + inner_w - r
    y0, y1 = cov + r, cov + inner_h - r
    if x1 < x0:
        x0 = x1 = b / 2.0
    if y1 < y0:
        y0 = y1 = h / 2.0

    if section_type == "column":
        centres = _column_positions(n, x0, x1, y0, y1)
    else:
        centres = _beam_positions(n, x0, x1, y0, y1)
    for cx, cy in centres:
        ax.add_patch(patches.Circle((cx, cy), r, facecolor="black",
                                    edgecolor="black", zorder=4))

    top_centres = []
    if top_label and section_type != "column":
        top_centres = [(x, y1) for x in _even_spread(x0, x1, 2)]
        for cx, cy in top_centres:
            ax.add_patch(patches.Circle((cx, cy), r, facecolor="black",
                                        edgecolor="black", zorder=4))

    # ---- dimension lines ----
    _hdim(ax, 0.0, b, -0.22 * h, 0.0, f"$b = {_cm(b)}$ cm")
    _vdim(ax, 0.0, h, b + 0.20 * b, b, f"$h = {_cm(h)}$ cm")

    # ---- call-outs ----
    if bar_label:
        _callout(ax, (centres[0][0], centres[0][1]),
                 (-0.30 * b, -0.05 * h), bar_label, ha="right")
    if top_label and top_centres:
        _callout(ax, top_centres[-1], (1.28 * b, 1.05 * h), top_label,
                 ha="left")
    if stirrup_label:
        _callout(ax, (cov, h * 0.5), (-0.30 * b, h * 0.62),
                 stirrup_label, color=_STEEL2, ha="right")

    _frame(ax, 0, b, 0, h, l=0.42, r=0.42, b=0.30, t=0.24)
    fig.tight_layout(pad=0.4)
    return _save_buf(fig)


# ===========================================================================
# Beam — three cross-sections
# ===========================================================================
def draw_beam_3_sect(b_mm, h_mm, covering_mm, left_rebar, mid_rebar,
                     right_rebar):
    """Three beam cross-sections (Left Support / Mid Span / Right Support).

    Each *_rebar dict: top_dia, top_qty, bot_dia, bot_qty, stirrup_dia and
    optionally top_size, bot_size, stirrup_size, stirrup_sp_cm (for labels).
    """
    b = float(b_mm)
    h = float(h_mm)
    cov = float(covering_mm)

    data = [(left_rebar, "Left Support"), (mid_rebar, "Mid Span"),
            (right_rebar, "Right Support")]

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 5.0))
    for ax, (rb, title) in zip(axes, data):
        ax.add_patch(patches.Rectangle((0.0, 0.0), b, h, edgecolor=_CONC_EDGE,
                                       facecolor=_CONC_FILL, linewidth=1.6))
        iw = max(b - 2.0 * cov, 0.0)
        ih = max(h - 2.0 * cov, 0.0)
        ax.add_patch(patches.Rectangle((cov, cov), iw, ih, edgecolor="#404040",
                                       facecolor="none", linewidth=1.0))

        td = float(rb.get("top_dia", 12.0))
        bd = float(rb.get("bot_dia", 12.0))
        tq = int(rb.get("top_qty", 2) or 0)
        bq = int(rb.get("bot_qty", 2) or 0)
        top_xs = _beam_bar_row(ax, max(tq, 1), td, cov + td / 2.0,
                               cov + iw - td / 2.0, cov + ih - td / 2.0)
        bot_xs = _beam_bar_row(ax, max(bq, 1), bd, cov + bd / 2.0,
                               cov + iw - bd / 2.0, cov + bd / 2.0)

        _hdim(ax, 0.0, b, -0.24 * h, 0.0, f"$b={_cm(b)}$")
        _vdim(ax, 0.0, h, b + 0.22 * b, b, f"$h={_cm(h)}$")

        if tq > 0:
            lbl = rb.get("top_size") and f"{tq} - {rb['top_size']}" or f"{tq} bars"
            _callout(ax, (top_xs[-1], cov + ih - td / 2.0),
                     (0.5 * b, 1.30 * h), lbl, ha="center")
        if bq > 0:
            lbl = rb.get("bot_size") and f"{bq} - {rb['bot_size']}" or f"{bq} bars"
            _callout(ax, (bot_xs[0], cov + bd / 2.0),
                     (-0.05 * b, -0.32 * h), lbl, ha="center")
        ss = rb.get("stirrup_size")
        if ss:
            s_txt = f"{ss}"
            if rb.get("stirrup_sp_cm"):
                s_txt += f" @ {rb['stirrup_sp_cm']:.0f} cm"
            _callout(ax, (cov, h * 0.55), (-0.42 * b, h * 0.62), s_txt,
                     color=_STEEL2, ha="right")

        _frame(ax, 0, b, 0, h, l=0.5, r=0.5, b=0.42, t=0.40)
        ax.set_title(title, fontsize=_TITLE_FS)

    fig.tight_layout(pad=0.8)
    return _save_buf(fig)


# ===========================================================================
# Beam — commercial-grade detail : cross-section + side elevation
# ===========================================================================
def draw_beam_detail(b_mm, h_mm, covering_mm, *, top_size="DB16", top_qty=2,
                     bot_size="DB16", bot_qty=3, stirrup_size="DB10",
                     stirrup_sp_cm=15.0, seg_len_mm=None):
    """Two-view RC beam detail.

    View 1 (Cross-Section): concrete b x h, a closed rectangular stirrup
    offset by the cover, top + bottom longitudinal bars as dots in the
    stirrup corners, b / h dimension lines and bar / stirrup call-outs.

    View 2 (Side Elevation): a beam segment with the longitudinal top and
    bottom bars as horizontal lines and the stirrups as vertical lines
    spaced at S, with an "S = ... cm" dimension.

    Blue = main longitudinal bars, green = stirrups.  Returns the live
    Matplotlib ``Figure`` (use ``st.pyplot`` to show it, or
    ``fig_to_png_buf`` for the PDF report).
    """
    b = float(b_mm)
    h = float(h_mm)
    cov = float(covering_mm)
    sd = float(str(stirrup_size)[2:] or 10.0)          # stirrup bar dia (mm)
    td = float(str(top_size)[2:] or 16.0)              # top bar dia (mm)
    btd = float(str(bot_size)[2:] or 16.0)             # bottom bar dia (mm)
    ntop = max(int(top_qty), 2)
    nbot = max(int(bot_qty), 2)
    sp = max(float(stirrup_sp_cm), 1.0) * 10.0         # spacing S (mm)
    seg = float(seg_len_mm) if seg_len_mm else max(5.0 * sp, 2.4 * h, 900.0)

    _MAIN = "#1f5fd0"      # blue  — main longitudinal bars
    _STIR = "#2e7d32"      # green — stirrups

    fig, (axc, axe) = plt.subplots(
        1, 2, figsize=(9.6, 5.6), gridspec_kw={"width_ratios": [1.0, 2.3]})

    # bar-row positions (shared by both views) --------------------------
    bx0 = cov + sd + max(td, btd) / 2.0
    bx1 = b - cov - sd - max(td, btd) / 2.0
    if bx1 <= bx0:
        bx0 = bx1 = b / 2.0
    y_top = h - cov - sd - td / 2.0
    y_bot = cov + sd + btd / 2.0

    # ---------------- View 1 : Cross-Section --------------------------
    axc.add_patch(patches.Rectangle((0, 0), b, h, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.8))
    axc.add_patch(patches.Rectangle((cov, cov), b - 2.0 * cov, h - 2.0 * cov,
                                    edgecolor=_STIR, facecolor="none",
                                    linewidth=1.8, joinstyle="miter",
                                    zorder=4))
    for cx in _even_spread(bx0, bx1, ntop):
        axc.add_patch(patches.Circle((cx, y_top), td / 2.0, facecolor=_MAIN,
                                     edgecolor=_MAIN, zorder=6))
    for cx in _even_spread(bx0, bx1, nbot):
        axc.add_patch(patches.Circle((cx, y_bot), btd / 2.0, facecolor=_MAIN,
                                     edgecolor=_MAIN, zorder=6))
    _hdim(axc, 0.0, b, -0.22 * h, 0.0, f"$b = {_cm(b)}$ cm", fs=_DIM_FS)
    _vdim(axc, 0.0, h, b + 0.24 * b, b, f"$h = {_cm(h)}$ cm", fs=_DIM_FS)
    _callout(axc, (bx1, y_top), (b + 0.34 * b, h * 1.05),
             f"{ntop} - {top_size}", color=_MAIN, ha="left", fs=_NOTE_FS)
    _callout(axc, (bx0, y_bot), (-0.34 * b, -0.16 * h),
             f"{nbot} - {bot_size}", color=_MAIN, ha="right", fs=_NOTE_FS)
    _callout(axc, (cov, h * 0.55), (-0.34 * b, h * 0.72),
             f"{stirrup_size} @ {_cm(sp)} cm", color=_STIR, ha="right",
             fs=_NOTE_FS)
    axc.set_xlim(-0.60 * b, 1.75 * b)
    axc.set_ylim(-0.34 * h, 1.30 * h)
    axc.set_aspect("equal", adjustable="box")
    axc.axis("off")
    axc.set_title("Cross-Section", fontsize=_TITLE_FS)

    # ---------------- View 2 : Side Elevation ------------------------
    axe.add_patch(patches.Rectangle((0, 0), seg, h, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.8))
    for yy in (y_bot, y_top):
        axe.plot([cov, seg - cov], [yy, yy], color=_MAIN, linewidth=2.2,
                 zorder=5)
    xs_stir = []
    x = cov
    while x <= seg - cov + 1.0e-6:
        axe.plot([x, x], [cov, h - cov], color=_STIR, linewidth=1.5, zorder=4)
        xs_stir.append(x)
        x += sp
    _vdim(axe, 0.0, h, seg + 0.07 * seg, seg, f"$h = {_cm(h)}$ cm",
          fs=_DIM_FS)
    if len(xs_stir) >= 2:
        _hdim(axe, xs_stir[0], xs_stir[1], -0.24 * h, 0.0,
              f"S = {_cm(sp)} cm", fs=_DIM_FS)
    _callout(axe, (0.5 * seg, y_top), (0.5 * seg, h * 1.22),
             f"{ntop} - {top_size} (บน)", color=_MAIN, ha="center",
             fs=_NOTE_FS)
    _callout(axe, (0.62 * seg, y_bot), (0.62 * seg, -0.44 * h),
             f"{nbot} - {bot_size} (ล่าง)", color=_MAIN, ha="center",
             fs=_NOTE_FS)
    _callout(axe, (xs_stir[len(xs_stir) // 2] if xs_stir else 0.4 * seg,
                   h * 0.5), (-0.02 * seg, h * 1.22),
             f"{stirrup_size} @ {_cm(sp)} cm", color=_STIR, ha="center",
             fs=_NOTE_FS)
    axe.set_xlim(-0.12 * seg, 1.22 * seg)
    axe.set_ylim(-0.60 * h, 1.46 * h)
    axe.set_aspect("equal", adjustable="box")
    axe.axis("off")
    axe.set_title("Side Elevation", fontsize=_TITLE_FS)

    fig.tight_layout(pad=1.0)
    return fig


# ===========================================================================
# Column — cross-section + P-M interaction diagram
# ===========================================================================
def draw_column_pm_and_section(b_mm, h_mm, cover_to_bar_mm, bar_dia_mm, bar_xy,
                               curve_x_dsn, curve_y_dsn, Pu_kN, Mux_kNm,
                               Muy_kNm, phiPn_max_kN, *, bar_label=None,
                               tie_label=None, tie_cover_mm=None):
    """Two-panel figure: annotated column cross-section + P-M diagram."""
    b = float(b_mm)
    h = float(h_mm)
    cc = float(cover_to_bar_mm)
    r = float(bar_dia_mm) / 2.0

    fig, (ax_s, ax_g) = plt.subplots(1, 2, figsize=(10.6, 5.2))

    # ---- cross-section (origin at centroid) ----
    ax_s.add_patch(patches.Rectangle((-b / 2.0, -h / 2.0), b, h,
                                     edgecolor=_CONC_EDGE, facecolor=_CONC_FILL,
                                     linewidth=1.6))
    inset = float(tie_cover_mm) if tie_cover_mm else max(cc - r,
                                                         min(b, h) * 0.08)
    ax_s.add_patch(patches.Rectangle((-b / 2.0 + inset, -h / 2.0 + inset),
                                     b - 2.0 * inset, h - 2.0 * inset,
                                     edgecolor=_STEEL2, facecolor="none",
                                     linewidth=1.1))
    for (x, y) in bar_xy:
        ax_s.add_patch(patches.Circle((x, y), r, facecolor="black",
                                      edgecolor="black", zorder=4))

    _hdim(ax_s, -b / 2.0, b / 2.0, -h / 2.0 - 0.24 * h, -h / 2.0,
          f"$b = {_cm(b)}$ cm")
    _vdim(ax_s, -h / 2.0, h / 2.0, b / 2.0 + 0.22 * b, b / 2.0,
          f"$h = {_cm(h)}$ cm")

    if bar_label and bar_xy:
        corner = max(bar_xy, key=lambda p: (p[0], p[1]))
        _callout(ax_s, corner, (b * 0.95, h * 0.92), bar_label, ha="left")
    if tie_label:
        _callout(ax_s, (-b / 2.0 + inset, 0.0), (-b * 1.0, h * 0.15),
                 tie_label, color=_STEEL2, ha="right")

    _frame(ax_s, -b / 2.0, b / 2.0, -h / 2.0, h / 2.0,
           l=0.46, r=0.46, b=0.34, t=0.30)
    ax_s.set_title("Cross Section", fontsize=_TITLE_FS)

    # ---- interaction diagram ----
    for curve, lbl, col in ((curve_x_dsn, "About X", "#1f5fb0"),
                            (curve_y_dsn, "About Y", "#c0504d")):
        ms = [pt[0] for pt in curve]
        ps = [pt[1] for pt in curve]
        ax_g.plot(ms, ps, color=col, linewidth=1.7, label=lbl)
    ax_g.axhline(phiPn_max_kN, color="gray", linestyle="--", linewidth=1.0,
                 label="phiPn,max")
    ax_g.axhline(0.0, color="black", linewidth=0.6)
    if Mux_kNm > 0:
        ax_g.plot([Mux_kNm], [Pu_kN], "o", color="red", markersize=7,
                  label="(Mux, Pu)")
    if Muy_kNm > 0:
        ax_g.plot([Muy_kNm], [Pu_kN], "s", color="red", markersize=6,
                  label="(Muy, Pu)")
    ax_g.set_xlabel("phiMn (kgf-m)")
    ax_g.set_ylabel("phiPn (kgf)")
    ax_g.set_title("P-M Interaction Diagram", fontsize=_TITLE_FS)
    ax_g.grid(True, alpha=0.3)
    ax_g.legend(fontsize=7, loc="upper right")

    fig.tight_layout(pad=0.8)
    return _save_buf(fig)


# ===========================================================================
# Column — CAD cross-section (tied rectangular / spiral circular)
# ===========================================================================
def _perimeter_pts(x0, y0, x1, y1, n):
    """``n`` points equally spaced around the rectangle perimeter, starting
    at (x0, y0).  n = 4 -> the corners; n = 8 -> corners + edge midpoints."""
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    seg = [x1 - x0, y1 - y0, x1 - x0, y1 - y0]
    per = sum(seg) or 1.0
    out = []
    for i in range(max(int(n), 1)):
        d = per * i / n
        for s in range(4):
            if d <= seg[s] or s == 3:
                (ax, ay), (bx, by) = corners[s], corners[(s + 1) % 4]
                t = (d / seg[s]) if seg[s] else 0.0
                out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
                break
            d -= seg[s]
    return out


def draw_column_detail(*, shape="rect", b_mm=400.0, h_mm=400.0, D_mm=None,
                       covering_mm=40.0, main_size="DB20", n_bars=8,
                       tie_size="DB10", tie_sp_cm=15.0):
    """RC column cross-section (plan view).

    shape = "rect"  -> b x h grey box, closed green tie, main bars spread
                       around the perimeter inside the tie.
    shape = "circ"  -> grey circle Ø D, dashed green spiral, main bars in a
                       polar array inside the spiral.

    Blue = main bars, green = tie / spiral.  Returns a Matplotlib ``Figure``.
    """
    circ = str(shape).lower().startswith("c")
    cov = float(covering_mm)
    md = float(str(main_size)[2:] or 20.0)        # main bar dia (mm)
    tdd = float(str(tie_size)[2:] or 10.0)        # tie / spiral dia (mm)
    n = max(int(n_bars), 4)
    _MAIN, _TIE = "#1f5fd0", "#2e7d32"

    fig, ax = plt.subplots(figsize=(5.2, 5.4))

    if circ:
        D = float(D_mm if D_mm else b_mm)
        R = D / 2.0
        ax.add_patch(patches.Circle((0, 0), R, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.8))
        R_sp = R - cov - tdd / 2.0                # spiral centre-line radius
        ax.add_patch(patches.Circle((0, 0), R_sp, edgecolor=_TIE,
                                    facecolor="none", linewidth=1.8,
                                    linestyle=(0, (5, 4)), zorder=4))
        R_b = R - cov - tdd - md / 2.0            # main-bar circle radius
        for k in range(n):
            ang = math.pi / 2.0 - 2.0 * math.pi * k / n
            ax.add_patch(patches.Circle((R_b * math.cos(ang),
                                         R_b * math.sin(ang)), md / 2.0,
                                        facecolor=_MAIN, edgecolor=_MAIN,
                                        zorder=6))
        _hdim(ax, -R, R, -R - 0.24 * D, -R, f"$D = {_cm(D)}$ cm", fs=_DIM_FS)
        _callout(ax, (0.0, R_b), (1.05 * D, 0.9 * D), f"{n} - {main_size}",
                 color=_MAIN, ha="left", fs=_NOTE_FS)
        _callout(ax, (R_sp * 0.71, R_sp * 0.71), (-1.1 * D, 0.9 * D),
                 f"{tie_size} เกลียว @ {tie_sp_cm:.0f} cm", color=_TIE,
                 ha="right", fs=_NOTE_FS)
        lim = 0.85 * D
        ax.set_xlim(-lim, 1.55 * lim)
        ax.set_ylim(-1.15 * lim, 1.15 * lim)
        ax.set_title("Column Cross-Section (Circular / Spiral)",
                     fontsize=_TITLE_FS)
    else:
        b, h = float(b_mm), float(h_mm)
        ax.add_patch(patches.Rectangle((-b / 2.0, -h / 2.0), b, h,
                                       edgecolor=_CONC_EDGE,
                                       facecolor=_CONC_FILL, linewidth=1.8))
        tx0, ty0 = -b / 2.0 + cov, -h / 2.0 + cov
        tx1, ty1 = b / 2.0 - cov, h / 2.0 - cov
        ax.add_patch(patches.Rectangle((tx0, ty0), tx1 - tx0, ty1 - ty0,
                                       edgecolor=_TIE, facecolor="none",
                                       linewidth=1.8, joinstyle="miter",
                                       zorder=4))
        off = tdd / 2.0 + md / 2.0                # bar centre inset from tie
        for (bx, by) in _perimeter_pts(tx0 + off, ty0 + off,
                                       tx1 - off, ty1 - off, n):
            ax.add_patch(patches.Circle((bx, by), md / 2.0, facecolor=_MAIN,
                                        edgecolor=_MAIN, zorder=6))
        _hdim(ax, -b / 2.0, b / 2.0, -h / 2.0 - 0.22 * h, -h / 2.0,
              f"$b = {_cm(b)}$ cm", fs=_DIM_FS)
        _vdim(ax, -h / 2.0, h / 2.0, b / 2.0 + 0.24 * b, b / 2.0,
              f"$h = {_cm(h)}$ cm", fs=_DIM_FS)
        _callout(ax, (tx1 - off, ty1 - off), (b * 0.9, h * 1.0),
                 f"{n} - {main_size}", color=_MAIN, ha="left", fs=_NOTE_FS)
        _callout(ax, (tx0, 0.0), (-b * 0.95, h * 0.62),
                 f"{tie_size} @ {tie_sp_cm:.0f} cm", color=_TIE, ha="right",
                 fs=_NOTE_FS)
        ax.set_xlim(-1.05 * b, 1.55 * b)
        ax.set_ylim(-0.95 * h, 1.35 * h)
        ax.set_title("Column Cross-Section (Rectangular / Tied)",
                     fontsize=_TITLE_FS)

    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.tight_layout(pad=0.8)
    return fig


# ===========================================================================
# Slab — CAD top plan with the bottom reinforcement grid
# ===========================================================================
def draw_slab_plan(Lx_m, Ly_m, *, main_label="Main", main_sp_cm=15.0,
                   temp_label="Temp", temp_sp_cm=20.0, two_way=False):
    """Top plan of an Lx (short, X) x Ly (long, Y) slab with its bottom bars.

    Main bars run in the short (X) direction -> drawn as lines parallel to
    X, stepped along Y at ``main_sp_cm``.  Temperature bars run in Y ->
    lines parallel to Y, stepped along X at ``temp_sp_cm``.

    Blue = main bars; green = temperature bars (a 2nd blue when two_way).
    Returns a Matplotlib ``Figure``.
    """
    Lx = float(Lx_m) * 100.0                       # cm
    Ly = float(Ly_m) * 100.0
    msp = max(float(main_sp_cm), 1.0)
    tsp = max(float(temp_sp_cm), 1.0)
    _MAIN = "#1f5fd0"
    _TEMP = "#3f7fd8" if two_way else "#2e7d32"

    fig, ax = plt.subplots(figsize=(6.8, 6.4))
    ax.add_patch(patches.Rectangle((0.0, 0.0), Lx, Ly, edgecolor=_CONC_EDGE,
                                   facecolor=_CONC_FILL, linewidth=1.8))
    edge = min(Lx, Ly) * 0.045
    yy = edge
    while yy <= Ly - edge + 1.0e-6:
        ax.plot([edge, Lx - edge], [yy, yy], color=_MAIN, lw=0.9, zorder=3)
        yy += msp
    xx = edge
    while xx <= Lx - edge + 1.0e-6:
        ax.plot([xx, xx], [edge, Ly - edge], color=_TEMP, lw=0.9, zorder=3)
        xx += tsp

    _hdim(ax, 0.0, Lx, -0.13 * Ly, 0.0, f"$L_x = {Lx / 100.0:.2f}$ m",
          fs=_DIM_FS)
    _vdim(ax, 0.0, Ly, Lx + 0.15 * Lx, Lx, f"$L_y = {Ly / 100.0:.2f}$ m",
          fs=_DIM_FS)
    _callout(ax, (Lx * 0.5, Ly - edge - msp), (Lx * 0.5, Ly * 1.20),
             main_label, color=_MAIN, ha="center", fs=_NOTE_FS)
    _callout(ax, (edge + tsp, Ly * 0.5), (-0.30 * Lx, Ly * 0.5),
             temp_label, color=_TEMP, ha="right", fs=_NOTE_FS)

    ax.set_xlim(-0.44 * Lx, 1.34 * Lx)
    ax.set_ylim(-0.30 * Ly, 1.36 * Ly)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.set_title("Slab Plan — Bottom Reinforcement", fontsize=_TITLE_FS)
    fig.tight_layout(pad=0.8)
    return fig


# ===========================================================================
# Isolated footing — Plan + Elevation
# ===========================================================================
def draw_footing_plan(B_mm, L_mm, h_mm, cx_mm, cy_mm, covering_mm, bar_size,
                      qty, qty_y=None, *, col_shape="rect", Dc_mm=None,
                      bar_size_y=None):
    """Dual-view isolated-footing detail.

    B_mm, L_mm  : footing width (X) / length (Y)
    h_mm        : footing thickness
    cx_mm, cy_mm: column dimension // X and // Y (for a circular column both
                  hold the equivalent square side)
    covering_mm : clear cover to the outer bar
    bar_size    : size of the bars drawn as vertical grid lines (spread over B)
    bar_size_y  : size of the bars drawn as horizontal grid lines (spread over
                  L); defaults to `bar_size`
    qty         : bars in the X direction (vertical lines, across B)
    qty_y       : bars in the Y direction (horizontal lines, across L)
    col_shape   : "rect" or "circ"
    Dc_mm       : circular-column diameter (drawn to scale when col_shape="circ")
    """
    B = float(B_mm)
    L = float(L_mm)
    h = float(h_mm)
    cx = float(cx_mm)
    cy = float(cy_mm)
    circular = str(col_shape).lower().startswith("circ") and Dc_mm
    Dc = float(Dc_mm) if Dc_mm else max(cx, cy)
    cov = float(covering_mm)
    bar_size_y = bar_size_y or bar_size
    nx = max(int(qty), 2)
    ny = max(int(qty_y if qty_y is not None else qty), 2)

    lox, hix = cov, B - cov
    loy, hiy = cov, L - cov
    if hix <= lox:
        lox, hix = B * 0.1, B * 0.9
    if hiy <= loy:
        loy, hiy = L * 0.1, L * 0.9
    sx = (hix - lox) / (nx - 1)
    sy = (hiy - loy) / (ny - 1)

    stub = min(max(h * 0.7, 250.0), h * 1.4)      # pedestal above the footing

    # --- shared data windows so Plan & Side render at one true scale --------
    x_lo, x_hi = -0.42 * B, 1.24 * B
    plan_y = (-0.28 * L, 1.32 * L)
    side_y = (-1.35 * h, (h + stub) + 0.15 * h)
    fig, (axp, axe) = plt.subplots(
        2, 1, figsize=_A4_FIGSIZE, dpi=_A4_DPI,
        gridspec_kw={"height_ratios": [plan_y[1] - plan_y[0],
                                       side_y[1] - side_y[0]]})

    # ---------------- Plan ----------------
    axp.add_patch(patches.Rectangle((0.0, 0.0), B, L, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.6))
    if circular:
        axp.add_patch(patches.Circle((B / 2.0, L / 2.0), Dc / 2.0,
                                     edgecolor=_CONC_EDGE, facecolor=_COL_FILL,
                                     linewidth=1.3, zorder=3))
    else:
        axp.add_patch(patches.Rectangle(
            (B / 2.0 - cx / 2.0, L / 2.0 - cy / 2.0), cx, cy,
            edgecolor=_CONC_EDGE, facecolor=_COL_FILL, linewidth=1.3,
            zorder=3))

    xs = _even_spread(lox, hix, nx)
    ys = _even_spread(loy, hiy, ny)
    for x in xs:
        axp.plot([x, x], [loy, hiy], color=_GRID_X, linewidth=0.8, zorder=2)
    for y in ys:
        axp.plot([lox, hix], [y, y], color=_GRID_Y, linewidth=0.8, zorder=2)

    _hdim(axp, 0.0, B, -0.16 * L, 0.0, f"$B = {_m(B)}$ m", fs=_A4_DIM_FS)
    _vdim(axp, 0.0, L, B + 0.13 * B, B, f"$L = {_m(L)}$ m", fs=_A4_DIM_FS)
    _callout(axp, (xs[max(1, nx // 2)], hiy), (B * 0.5, L * 1.18),
             f"{nx} - {bar_size}  (S = {_cm(sx)} cm)", ha="center",
             fs=_A4_NOTE_FS)
    _callout(axp, (lox, ys[max(1, ny // 2)]), (-0.34 * B, L * 0.5),
             f"{ny} - {bar_size_y}  (S = {_cm(sy)} cm)", ha="right",
             fs=_A4_NOTE_FS)

    _apply_true_scale(axp, x_lo, x_hi, *plan_y)
    axp.set_title("Plan View", fontsize=_A4_TITLE_FS)

    # ---------------- Side View / Elevation ----------------
    stub_w = Dc if circular else cx               # stump width matches the view
    axe.add_patch(patches.Rectangle((0.0, 0.0), B, h, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.6))
    axe.add_patch(patches.Rectangle((B / 2.0 - stub_w / 2.0, h), stub_w, stub,
                                    edgecolor=_CONC_EDGE, facecolor=_COL_FILL,
                                    linewidth=1.3))

    y_bar = cov + float(str(bar_size)[2:] or 16) / 2.0
    axe.plot([lox, hix], [y_bar, y_bar], color=_GRID_Y, linewidth=1.4, zorder=3)
    axe.plot(xs, [y_bar] * len(xs), marker="o", ms=3.4, mfc="black",
             mec="black", ls="", zorder=4)

    _vdim(axe, 0.0, h, B + 0.06 * B, B, f"$h = {_cm(h)}$ cm", fs=_A4_DIM_FS)
    _bar_note = (f"เหล็กล่าง {nx} - {bar_size} (S = {_cm(sx)} cm)"
                 if bar_size == bar_size_y else
                 f"เหล็กล่าง {nx}-{bar_size} (S={_cm(sx)}) / "
                 f"{ny}-{bar_size_y} (S={_cm(sy)})")
    _callout(axe, (xs[max(1, nx // 2)], y_bar), (B * 0.5, -0.95 * h),
             _bar_note, ha="center", fs=_A4_NOTE_FS)

    _apply_true_scale(axe, x_lo, x_hi, *side_y)
    axe.set_title("Side View", fontsize=_A4_TITLE_FS)

    fig.subplots_adjust(**_A4_ADJUST)
    return _save_buf(fig, dpi=_A4_DPI, tight=False)


# ===========================================================================
# Two-way slab — Plan + Section
# ===========================================================================
def draw_twoway_slab_plan(Lx_m, Ly_m, t_mm, covering_mm, size_x, spacing_x_mm,
                          size_y, spacing_y_mm):
    """Dual-view two-way-slab panel detail (Plan + Section)."""
    Lx = float(Lx_m) * 1000.0
    Ly = float(Ly_m) * 1000.0
    t = float(t_mm)
    cov = float(covering_mm)
    sx = max(float(spacing_x_mm), 10.0)
    sy = max(float(spacing_y_mm), 10.0)
    nx = _count_by_spacing(Lx, sx)
    ny = _count_by_spacing(Ly, sy)

    # --- shared data windows so Plan & Section render at one true scale ----
    x_lo, x_hi = -0.44 * Lx, 1.20 * Lx
    plan_y = (-0.28 * Ly, 1.32 * Ly)
    sect_y = (-9.0 * t, 5.0 * t)
    fig, (axp, axs) = plt.subplots(
        2, 1, figsize=_A4_FIGSIZE, dpi=_A4_DPI,
        gridspec_kw={"height_ratios": [plan_y[1] - plan_y[0],
                                       sect_y[1] - sect_y[0]]})

    # ---------------- Plan ----------------
    axp.add_patch(patches.Rectangle((0.0, 0.0), Lx, Ly, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.6))
    xs = [i * sx for i in range(1, nx) if i * sx < Lx]
    ys = [j * sy for j in range(1, ny) if j * sy < Ly]
    for x in xs:
        axp.plot([x, x], [0.0, Ly], color=_GRID_X, linewidth=0.6, zorder=3)
    for y in ys:
        axp.plot([0.0, Lx], [y, y], color=_GRID_Y, linewidth=0.6, zorder=3)

    _hdim(axp, 0.0, Lx, -0.16 * Ly, 0.0, f"$L_x = {_m(Lx)}$ m", fs=_A4_DIM_FS)
    _vdim(axp, 0.0, Ly, Lx + 0.13 * Lx, Lx, f"$L_y = {_m(Ly)}$ m", fs=_A4_DIM_FS)

    if xs:
        _callout(axp, (xs[len(xs) // 2], Ly * 0.72), (Lx * 0.5, Ly * 1.18),
                 f"{nx} - {size_x} @ {_cm(sx)} cm  (ทิศทางสั้น X)",
                 ha="center", fs=_A4_NOTE_FS)
    if ys:
        _callout(axp, (Lx * 0.28, ys[len(ys) // 2]), (-0.36 * Lx, Ly * 0.5),
                 f"{ny} - {size_y} @ {_cm(sy)} cm  (ทิศทางยาว Y)",
                 ha="right", fs=_A4_NOTE_FS)

    _apply_true_scale(axp, x_lo, x_hi, *plan_y)
    axp.set_title("Plan View", fontsize=_A4_TITLE_FS)

    # ---------------- Section (true 1:1 scale — a thin slab reads thin) -----
    axs.add_patch(patches.Rectangle((0.0, 0.0), Lx, t, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.6))
    y_x = cov + 6.0
    y_y = t - cov - 6.0
    axs.plot(_bars_by_spacing(Lx, sx), [y_x] * len(_bars_by_spacing(Lx, sx)),
             marker="o", ms=3.0, mfc="black", mec="black", ls="", zorder=4)
    axs.plot([cov, Lx - cov], [y_y, y_y], color=_GRID_Y, linewidth=1.3,
             zorder=3)

    _vdim(axs, 0.0, t, -0.05 * Lx, 0.0, f"$t = {_cm(t)}$ cm", left=True,
          fs=_A4_DIM_FS)
    _callout(axs, (Lx * 0.5, y_x), (Lx * 0.5, -6.5 * t),
             f"ล่าง: {size_x} (X)  ·  บน: {size_y} (Y)", ha="center",
             fs=_A4_NOTE_FS)

    _apply_true_scale(axs, x_lo, x_hi, *sect_y)
    axs.set_title("Section", fontsize=_A4_TITLE_FS)

    fig.subplots_adjust(**_A4_ADJUST)
    return _save_buf(fig, dpi=_A4_DPI, tight=False)


# ===========================================================================
# Slab / straight-stair — 1 m strip cross-section
# ===========================================================================
def draw_slab_strip(t_mm, covering_mm, main_dia_mm, temp_dia_mm,
                    main_spacing_mm, temp_spacing_mm, *, main_label=None,
                    temp_label=None, span_m=None):
    """Cross-section of a 1 m wide slab / stair strip with a thickness
    dimension line and rebar call-outs."""
    W = 1000.0
    t = float(t_mm)
    cov = float(covering_mm)

    # True 1:1 scale — a 1 m strip reads correctly against its ~0.15 m depth.
    fig, ax = plt.subplots(figsize=(9.0, 5.0), dpi=_A4_DPI)

    ax.add_patch(patches.Rectangle((0.0, 0.0), W, t, edgecolor=_CONC_EDGE,
                                   facecolor=_CONC_FILL, linewidth=1.6))

    y_main = cov + 6.0
    main_xs = _bars_by_spacing(W, main_spacing_mm)
    ax.plot(main_xs, [y_main] * len(main_xs), marker="o", ms=4.5, mfc="black",
            mec="black", ls="", zorder=4)
    y_temp = t - cov - 6.0
    ax.plot([cov, W - cov], [y_temp, y_temp], color=_GRID_Y, linewidth=1.5,
            zorder=3)

    _hdim(ax, 0.0, W, -1.6 * t, 0.0, "1.00 m (แถบออกแบบ)", fs=_A4_DIM_FS)
    _vdim(ax, 0.0, t, W + 0.03 * W, W, f"$t = {_cm(t)}$ cm", fs=_A4_DIM_FS)

    _callout(ax, (main_xs[len(main_xs) // 2], y_main), (W * 0.32, -3.4 * t),
             main_label or f"เหล็กหลัก @ {_cm(main_spacing_mm)} cm",
             ha="center", fs=_A4_NOTE_FS)
    _callout(ax, (W * 0.72, y_temp), (W * 0.70, t + 2.8 * t),
             temp_label or f"เหล็กกันร้าว @ {_cm(temp_spacing_mm)} cm",
             color=_STEEL2, ha="center", fs=_A4_NOTE_FS)
    top = 4.2 * t
    if span_m:
        top = 5.6 * t
        ax.text(W * 0.5, 4.6 * t, f"ช่วงพาด L = {float(span_m):.2f} m",
                ha="center", va="bottom", fontsize=_A4_DIM_FS, color=_DIM)

    ax.set_xlim(-0.05 * W, 1.13 * W)
    ax.set_ylim(-4.4 * t, top)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    fig.subplots_adjust(top=0.94, bottom=0.06, left=0.06, right=0.94)
    return _save_buf(fig, dpi=_A4_DPI, tight=True)


# ===========================================================================
# Pile cap — Plan + Side View
# ===========================================================================
def _isection_pts(px, py, r):
    """Plan outline of an I-section pile centred on (px, py); overall size 2r."""
    a = r                    # half flange width / half depth
    ft = 0.30 * a            # flange thickness
    hw = 0.22 * a            # half web width
    return [
        (px - a, py - a), (px + a, py - a), (px + a, py - a + ft),
        (px + hw, py - a + ft), (px + hw, py + a - ft),
        (px + a, py + a - ft), (px + a, py + a), (px - a, py + a),
        (px - a, py + a - ft), (px - hw, py + a - ft),
        (px - hw, py - a + ft), (px - a, py - a + ft),
    ]


def _pile_patch(ax, px, py, r, shape, **kw):
    """Add one pile outline (matching the selected shape) at (px, py)."""
    if shape.startswith("squ"):
        ax.add_patch(patches.Rectangle((px - r, py - r), 2.0 * r, 2.0 * r, **kw))
    elif shape.startswith("hex"):
        ax.add_patch(patches.RegularPolygon((px, py), numVertices=6, radius=r,
                                            orientation=math.pi / 6.0, **kw))
    elif shape.startswith("i"):          # I-Section
        ax.add_patch(patches.Polygon(_isection_pts(px, py, r), closed=True,
                                     **kw))
    else:
        ax.add_patch(patches.Circle((px, py), r, **kw))


def draw_pile_cap_plan(W_mm, L_mm, h_mm, c_mm, pile_dia_mm, pile_positions,
                       covering_mm, bar_size, qty, col_pos=None, *,
                       qty_y=None, spacing_mm=None, pile_shape="circ",
                       bar_size_y=None, side_axis="x", pile_embed_mm=None,
                       basket=False, tie_label=None, pile_cap_kgf=None,
                       pile_shape_th=None):
    """Dual-view pile-cap / eccentric-footing detail (Plan + Side View).

    W_mm, L_mm      : cap plan width (X) / length (Y)
    h_mm            : cap thickness
    c_mm            : square column side
    pile_dia_mm     : pile width / diameter / width-across-flats
    pile_positions  : list of (x, y) pile centres in cap coords (0..W, 0..L)
    covering_mm     : side clear cover to the outer bar
    bar_size        : bars drawn as vertical grid lines (across W)
    bar_size_y      : bars drawn as horizontal grid lines (across L); default
                      = bar_size
    qty / qty_y     : bottom bars across W / across L (qty_y defaults to qty)
    col_pos         : (x, y) column centre in cap coords — already shifted by
                      the eccentricity (ex, ey); defaults to the cap centre
    pile_shape      : "square" | "circ" | "hex" | "isec"
    side_axis       : "x" cuts the Side View along W; "y" cuts it along the
                      axis connecting the piles (used for a 2-pile cap so the
                      elevation shows pile-column-pile along the length L).
    pile_embed_mm   : pile penetration up into the cap (drawn as a solid stub
                      inside the concrete); falls back to a nominal value.
    basket          : single-pile cap with basket reinforcement — switches
                      both views to the full CAD detail: sub-grade layers
                      (lean concrete 5 cm + compacted sand 10 cm), U-bars
                      anchored up into the column, tie dots on the legs, and
                      a 3-line pile spec block.
    tie_label       : call-out text for the basket tie bar (e.g. "4 - DB12 รัดรอบ").
    pile_cap_kgf    : safe pile capacity (kgf) — 3rd line of the spec block.
    pile_shape_th   : Thai pile-shape word for the spec block.
    """
    W = float(W_mm)
    L = float(L_mm)
    h = float(h_mm)
    c = float(c_mm)
    r = float(pile_dia_mm) / 2.0
    cov = float(covering_mm)                 # FOOTING clear cover (all faces)
    shape = str(pile_shape).lower()
    bar_size_y = bar_size_y or bar_size
    bd = float(str(bar_size)[2:] or 16)
    nx = max(int(qty), 2)
    ny = max(int(qty_y if qty_y is not None else qty), 2)
    cut_y = str(side_axis).lower().startswith("y")
    n_piles = len(pile_positions)

    # The single-pile cap now uses the SAME standard CAD style as the
    # multi-pile caps (red dashed piles, rebar grid, bottom-mat call-outs).
    # The basket / tie detail stays in the PDF reinforcement summary only.
    basket = False

    col_cx, col_cy = (W / 2.0, L / 2.0) if col_pos is None else (
        float(col_pos[0]), float(col_pos[1]))

    lox, hix = cov, W - cov
    loy, hiy = cov, L - cov
    if hix <= lox:
        lox, hix = W * 0.1, W * 0.9
    if hiy <= loy:
        loy, hiy = L * 0.1, L * 0.9
    sx = (hix - lox) / (nx - 1)
    sy = (hiy - loy) / (ny - 1)
    xs = _even_spread(lox, hix, nx)
    ys = _even_spread(loy, hiy, ny)

    stub = min(max(h * 0.7, 250.0), h * 1.2)          # column pedestal height
    embed = (float(pile_embed_mm) if pile_embed_mm
             else min(0.45 * h, 160.0))               # pile penetration into cap
    embed = min(embed, 0.85 * h)                       # keep it inside the cap
    proj = max(1.4 * (2.0 * r), 0.7 * h)              # pile length shown below

    # single-pile basket detail: fixed-thickness sub-grade layers, and the
    # U-bars anchor up into the column pedestal.
    t_lean = 50.0                                      # lean concrete (5 cm)
    t_sand = 100.0                                     # compacted sand (10 cm)
    La = min(0.40 * stub, 25.0 * bd, 0.45 * h)        # U-bar anchorage into col
    pile_show = max(1.6 * (2.0 * r), 0.75 * h)        # pile length below sand

    # --- shared data windows so Plan & Side render at one true scale --------
    ext = L if cut_y else W                            # Side-View horizontal span
    span = max(W, L, ext)
    # the single-pile basket elevation carries side call-outs, sub-grade
    # layers below and a 3-line spec block at the bottom -> widen both windows
    x_lo = -(0.52 if basket else 0.42) * span
    x_hi = (1.40 if basket else 1.22) * span
    if basket:
        plan_y = (-0.30 * L, 1.24 * L)
        side_y = (-(t_lean + t_sand) - pile_show - 0.95 * h,
                  max(h + La, h + stub) + 0.14 * h)
    else:
        plan_y = (-0.42 * L, 1.32 * L)
        side_y = (-proj - 1.70 * h, (h + stub) + 0.15 * h)
    px0 = (span - W) / 2.0                             # centre the Plan
    sx0 = (span - ext) / 2.0                           # centre the Side View
    fig, (axp, axe) = plt.subplots(
        2, 1, figsize=_A4_FIGSIZE, dpi=_A4_DPI,
        gridspec_kw={"height_ratios": [plan_y[1] - plan_y[0],
                                       side_y[1] - side_y[0]]})

    # ---------------- Plan ----------------
    axp.add_patch(patches.Rectangle((px0, 0.0), W, L, edgecolor=_CONC_EDGE,
                                    facecolor=_CONC_FILL, linewidth=1.6))
    if not basket:                        # the basket detail replaces the grid
        for x in xs:
            axp.plot([px0 + x, px0 + x], [loy, hiy], color=_GRID_X,
                     linewidth=0.7, zorder=2)
        for y in ys:
            axp.plot([px0 + lox, px0 + hix], [y, y], color=_GRID_Y,
                     linewidth=0.7, zorder=2)

    for i, (px, py) in enumerate(pile_positions, start=1):
        _pile_patch(axp, px0 + px, py, r, shape, facecolor="none",
                    edgecolor="red", linewidth=1.2, linestyle="--", zorder=4)
        axp.plot([px0 + px], [py], marker="+", ms=8, mec="red", mew=1.3,
                 zorder=5)                       # red '+' at the pile centre
        if n_piles > 1:
            axp.text(px0 + px + r * 1.15, py + r * 1.15, f"P{i}",
                     fontsize=_A4_NOTE_FS - 1.5, color=_CONC_EDGE, ha="left",
                     va="bottom", zorder=6)

    axp.add_patch(patches.Rectangle((px0 + col_cx - c / 2.0, col_cy - c / 2.0),
                                    c, c, edgecolor=_CONC_EDGE,
                                    facecolor=_COL_FILL, linewidth=1.3,
                                    alpha=0.85, zorder=6))
    axp.plot([px0 + col_cx], [col_cy], marker="+", ms=8, mec=_CONC_EDGE,
             mew=1.4, zorder=7)

    _hdim(axp, px0, px0 + W, -0.16 * L, 0.0, f"$W = {_m(W)}$ m", fs=_A4_DIM_FS)
    _vdim(axp, 0.0, L, px0 + W + 0.13 * W, px0 + W, f"$L = {_m(L)}$ m",
          fs=_A4_DIM_FS)
    if not basket:
        _callout(axp, (px0 + xs[max(1, nx // 2)], hiy),
                 (px0 + W * 0.5, L * 1.18),
                 f"{nx} - {bar_size} (S = {_cm(sx)} cm)", ha="center",
                 fs=_A4_NOTE_FS)
        _callout(axp, (px0 + lox, ys[max(1, ny // 2)]),
                 (px0 - 0.34 * W, L * 0.5),
                 f"{ny} - {bar_size_y} (S = {_cm(sy)} cm)", ha="right",
                 fs=_A4_NOTE_FS)
    if spacing_mm and n_piles > 1:
        axp.text(px0 + W * 0.5, -0.30 * L,
                 f"ระยะห่างเสาเข็ม S = {_cm(spacing_mm)} cm", ha="center",
                 va="top", fontsize=_A4_NOTE_FS, color=_STEEL)

    # --- single-pile basket detail in plan: the MAIN bottom bars run both
    #     ways at the FOOTING cover and turn up at the four footing faces;
    #     เหล็กรัดรอบ ties the up-turned legs just inside that cover --------
    if basket:
        _BK = "#1f3fd0"
        _BK_T = "#2e7d32"
        gx0, gy0 = px0 + cov, cov                  # FOOTING cover, not column
        gx1, gy1 = px0 + W - cov, L - cov
        for xx in _even_spread(gx0, gx1, max(nx, 5)):
            axp.plot([xx, xx], [gy0, gy1], color=_GRID_X, lw=0.5, zorder=2)
        for yy in _even_spread(gy0, gy1, max(ny, 5)):
            axp.plot([gx0, gx1], [yy, yy], color=_GRID_Y, lw=0.5, zorder=2)
        axp.add_patch(patches.Rectangle(
            (gx0, gy0), gx1 - gx0, gy1 - gy0, edgecolor=_BK_T, facecolor="none",
            linewidth=1.5, linestyle=(0, (6, 4)), zorder=6))
        _legs = [(gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1),
                 (0.5 * (gx0 + gx1), gy0), (gx1, 0.5 * (gy0 + gy1)),
                 (0.5 * (gx0 + gx1), gy1), (gx0, 0.5 * (gy0 + gy1))]
        for (lx, ly) in _legs:
            axp.plot([lx], [ly], marker="o", ms=5.0, mfc=_BK, mec=_BK,
                     zorder=7)
        _hdim(axp, px0 + col_cx - c / 2.0, px0 + col_cx + c / 2.0,
              L + 0.12 * L, L, f"${_cm(c)}$", fs=_A4_DIM_FS - 0.5)
        axp.text(px0 + col_cx, -0.05 * L,
                 "เหล็กเมน + เหล็กรัดรอบตะกร้อ", fontsize=_A4_NOTE_FS - 1.0,
                 color=_BK, ha="center", va="top", zorder=6)

    _apply_true_scale(axp, x_lo, x_hi, *plan_y)
    axp.set_title("Plan View", fontsize=_A4_TITLE_FS)

    # ---------------- Side View / Elevation ------------------------------
    # Pick the cut axis: "y" -> along the pile line (length L); "x" -> W.
    if cut_y:
        # view runs along L -> longitudinal bars = the vertical-plan-line bars
        # (bar_size / nx / sx); the transverse bars (ny) show as dots.
        pile_axis = sorted(round(py, 1) for (_px, py) in pile_positions)
        col_axis = col_cy
        lo_ax, hi_ax = loy, hiy
        n_ax = ny
        dim_label = f"$L = {_m(L)}$ m"
        long_bar, long_n, long_sp = bar_size, nx, sx
    else:
        # view runs along W -> longitudinal bars = the horizontal-plan-line
        # bars (bar_size_y / ny / sy); the transverse bars (nx) show as dots.
        pile_axis = sorted(round(px, 1) for (px, _py) in pile_positions)
        col_axis = col_cx
        lo_ax, hi_ax = lox, hix
        n_ax = nx
        dim_label = f"$W = {_m(W)}$ m"
        long_bar, long_n, long_sp = bar_size_y, ny, sy
    pile_axis = sorted(set(pile_axis))

    y_bar = cov + bd / 2.0

    if basket:
        # =============================================================
        # Single-pile cap with basket reinforcement — full CAD detail
        # =============================================================
        _BK = "#1f3fd0"            # basket main bars / tie dots (blue)
        _BK_T = "#2e7d32"          # transverse tie bars, into the page (green)
        cax = sx0 + col_axis
        colL, colR = cax - c / 2.0, cax + c / 2.0
        pax = sx0 + (pile_axis[0] if pile_axis else col_axis)
        y_lean_b = -t_lean
        y_sand_b = -t_lean - t_sand
        y_pile_b = y_sand_b - pile_show
        lyr_x0, lyr_w = sx0 - 0.06 * ext, ext * 1.12

        # --- sub-grade layers: lean concrete (5 cm) then compacted sand ---
        axe.add_patch(patches.Rectangle((lyr_x0, y_lean_b), lyr_w, t_lean,
                                        facecolor="#d9dcdf", edgecolor="#8a8f94",
                                        linewidth=0.8, zorder=2))
        axe.add_patch(patches.Rectangle((lyr_x0, y_sand_b), lyr_w, t_sand,
                                        facecolor="#efe3c2", edgecolor="#c9a227",
                                        linewidth=0.8, hatch="....", zorder=2))
        axe.text(lyr_x0 - 0.05 * ext, -0.5 * t_lean, f"{_cm(t_lean)} ซม.",
                 ha="right", va="center", fontsize=_A4_DIM_FS - 1.0,
                 color=_DIM, zorder=6)
        axe.text(lyr_x0 - 0.05 * ext, y_lean_b - 0.5 * t_sand,
                 f"{_cm(t_sand)} ซม.", ha="right", va="center",
                 fontsize=_A4_DIM_FS - 1.0, color=_DIM, zorder=6)

        # --- concrete: FOOTING (solid, crisp outline) + column pedestal ----
        axe.add_patch(patches.Rectangle((sx0, 0.0), ext, h, edgecolor=_CONC_EDGE,
                                        facecolor=_CONC_FILL, linewidth=1.8,
                                        alpha=0.92, zorder=3))
        axe.plot([sx0, sx0 + ext], [0.0, 0.0], color=_CONC_EDGE, lw=1.8,
                 zorder=6)                                   # crisp footing base
        axe.plot([sx0, sx0 + ext], [h, h], color=_CONC_EDGE, lw=1.8, zorder=6)
        axe.add_patch(patches.Rectangle((colL, h), c, stub, edgecolor=_CONC_EDGE,
                                        facecolor=_COL_FILL, linewidth=1.3,
                                        alpha=0.55, zorder=3))
        _bk = h + stub
        axe.plot([colL, colL + 0.28 * c, colL + 0.40 * c, colL + 0.60 * c,
                  colL + 0.72 * c, colR],
                 [_bk, _bk, _bk + 0.05 * h, _bk - 0.05 * h, _bk, _bk],
                 color=_CONC_EDGE, lw=1.3, zorder=6)
        # column centre-line
        axe.plot([cax, cax], [y_sand_b, _bk], color=_CONC_EDGE, lw=0.7,
                 linestyle=(0, (8, 3, 1, 3)), zorder=5)

        # --- pile: cuts up through both sub-grade layers and PENETRATES the
        #     cap by `embed`.  The buried shaft is drawn first (behind the
        #     translucent cap); the embedded head is redrawn on top with a
        #     bold outline so the penetration reads clearly. ----------------
        axe.add_patch(patches.Rectangle(
            (pax - r, y_pile_b), 2.0 * r, (0.0 - y_pile_b),
            edgecolor="#9c6a1f", facecolor="#f2a54a", linewidth=1.2, zorder=4))
        axe.add_patch(patches.Rectangle(
            (pax - r, 0.0), 2.0 * r, embed, edgecolor="#7a4d13",
            facecolor="#e8933a", linewidth=1.6, zorder=6))
        axe.plot([pax - r, pax + r], [embed, embed], color="#7a4d13",
                 lw=1.6, zorder=6)

        # --- MAIN footing bars = the basket ------------------------------
        #  เหล็กเมน: a wide run along the FOOTING BOTTOM cover, turning up at
        #  the FOOTING SIDE cover into short inward hooks under the top.
        #  เหล็กรัดรอบ: horizontal ties around the up-turned legs -> shown as
        #  green dots on the legs + a faint green line at each tie level.
        yb = cov + bd / 2.0                         # FOOTING bottom cover
        ux0, ux1 = sx0 + cov, sx0 + ext - cov       # FOOTING side cover
        y_leg_top = h - cov                         # FOOTING top cover
        hk = min(0.16 * (ux1 - ux0), 0.40 * (y_leg_top - yb))
        axe.plot([ux0 + hk, ux0, ux0, ux1, ux1, ux1 - hk],
                 [y_leg_top, y_leg_top, yb, yb, y_leg_top, y_leg_top],
                 color=_BK, lw=2.6, solid_capstyle="round",
                 solid_joinstyle="round", zorder=8)
        # main bottom bars of the other direction, seen end-on
        for xx in _even_spread(ux0 + hk, ux1 - hk, max(n_ax, 6)):
            axe.plot([xx], [yb], marker="o", ms=3.8, mfc=_BK, mec=_BK,
                     zorder=9)

        # เหล็กรัดรอบ (perimeter ties) up the two vertical legs
        n_tie = min(8, max(4, int((y_leg_top - yb) / max(3.0 * bd, 90.0)) + 1))
        for k in range(1, n_tie):                   # k=0 is the bottom main bar
            yy = yb + (y_leg_top - yb) * k / (n_tie - 1)
            axe.plot([ux0, ux1], [yy, yy], color=_BK_T, lw=1.0,
                     linestyle=(0, (4, 4)), zorder=6)
            for legx in (ux0, ux1):
                axe.plot([legx], [yy], marker="o", ms=4.6, mfc=_BK_T,
                         mec=_BK_T, zorder=9)

        # --- dimensions: cap thickness on the left (layers labelled inline) -
        _vdim(axe, 0.0, h, sx0 - 0.07 * ext, sx0,
              f"$h = {_cm(h)}$ cm", left=True, fs=_A4_DIM_FS)

        # --- leader call-outs (right margin, spread vertically) -----------
        rx = sx0 + ext + 0.12 * ext
        _callout(axe, (0.5 * (ux0 + ux1), yb), (rx, 0.80 * h),
                 f"{long_n}-{long_bar}# (เหล็กเมน)", ha="left",
                 fs=_A4_NOTE_FS)
        if tie_label:
            axe.annotate(
                str(tie_label),
                xy=(ux1, yb + 0.45 * (y_leg_top - yb)),
                xytext=(rx, 0.45 * h),
                arrowprops=dict(arrowstyle="->", color=_STEEL2, lw=1.2,
                                connectionstyle="arc3,rad=0.15"),
                fontsize=_A4_NOTE_FS, color="#5b3b00", ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.3", fc="#ffe89a",
                          ec="#c9a227", lw=1.0), zorder=10)
        _callout(axe, (lyr_x0 + lyr_w, -0.5 * t_lean), (rx, -0.02 * h),
                 "คอนกรีตหยาบ", color=_DIM, ha="left", fs=_A4_NOTE_FS)
        _callout(axe, (lyr_x0 + lyr_w, y_lean_b - 0.5 * t_sand),
                 (rx, -t_lean - t_sand - 0.10 * h),
                 "ทรายอัดแน่น", color=_DIM, ha="left", fs=_A4_NOTE_FS)

        # --- pile specification block (3 lines, centred at the bottom) ------
        _psz = _cm(2.0 * r)
        _sp1 = f"เสาเข็มตอก{pile_shape_th or ''} จำนวน 1 ต้น"
        _sp2 = (f"หน้าตัด I-{_psz} ขนาด {_psz} ซม." if shape.startswith("i")
                else f"หน้าตัดขนาด {_psz} ซม.")
        _sp3 = ""
        if pile_cap_kgf:
            _ton = float(pile_cap_kgf) / 1000.0
            _tt = f"{_ton:.1f}".rstrip("0").rstrip(".")
            _sp3 = f"น้ำหนักบรรทุกปลอดภัย {_tt} ตัน / ต้น"
        lines = "\n".join(s for s in (_sp1, _sp2, _sp3) if s)
        axe.text(sx0 + 0.5 * ext, y_pile_b - 0.30 * h, lines, ha="center",
                 va="top", fontsize=_A4_NOTE_FS, color=_CONC_EDGE, zorder=8)

    else:
        # -------- generic pile cap: flat bottom mat + piles --------------
        # concrete first (translucent) so the red dashed piles show through
        axe.add_patch(patches.Rectangle((sx0, 0.0), ext, h, edgecolor=_CONC_EDGE,
                                        facecolor=_CONC_FILL, linewidth=1.6,
                                        alpha=0.55, zorder=3))
        # each pile: ONE red dashed rectangle, from below grade up INTO the
        # footing by the embedment depth (penetration shown in the cut)
        for pa in pile_axis:
            axe.add_patch(patches.Rectangle(
                (sx0 + pa - r, -proj), 2.0 * r, proj + embed, edgecolor="red",
                facecolor="none", linewidth=1.2, linestyle="--", zorder=5))
        axe.add_patch(patches.Rectangle((sx0 + col_axis - c / 2.0, h), c, stub,
                                        edgecolor=_CONC_EDGE,
                                        facecolor=_COL_FILL, linewidth=1.3,
                                        zorder=6))
        axe.plot([sx0 + col_axis], [h + stub / 2.0], marker="+", ms=8,
                 mec=_CONC_EDGE, mew=1.4, zorder=7)
        # embedment dimension — far left, outside the footing
        _vdim(axe, 0.0, embed, sx0 - 0.11 * ext, sx0,
              f"ฝัง {_cm(embed)} cm", left=True, fs=_A4_DIM_FS)

        # bottom main bars drawn as their true shape: a U — horizontal run
        # along the footing bottom cover, 90-deg turn-up at both ends, and a
        # short 90-deg end hook bent inward.
        y_hook = h - cov                                  # top of the turn-ups
        hk = min(12.0 * bd, 0.14 * (hi_ax - lo_ax))       # end-hook length
        axe.plot(
            [sx0 + lo_ax + hk, sx0 + lo_ax, sx0 + lo_ax,
             sx0 + hi_ax, sx0 + hi_ax, sx0 + hi_ax - hk],
            [y_hook, y_hook, y_bar, y_bar, y_hook, y_hook],
            color=_GRID_Y, linewidth=1.8, solid_capstyle="round",
            solid_joinstyle="miter", zorder=8)
        for k in range(n_ax):
            xk = lo_ax + (hi_ax - lo_ax) * k / max(n_ax - 1, 1)
            axe.plot([sx0 + xk], [y_bar], marker="o", ms=3.4, mfc="black",
                     mec="black", zorder=8)

        _vdim(axe, 0.0, h, sx0 + ext + 0.05 * ext, sx0 + ext,
              f"$h = {_cm(h)}$ cm", fs=_A4_DIM_FS)
        if len(pile_axis) == 2:
            _hdim(axe, sx0 + pile_axis[0], sx0 + pile_axis[1], -0.32 * h, 0.0,
                  f"$S = {_m(pile_axis[1] - pile_axis[0])}$ m", fs=_A4_DIM_FS)
        _hdim(axe, sx0, sx0 + ext, -proj - 0.55 * h, -proj, dim_label,
              fs=_A4_DIM_FS)
        _callout(axe, (sx0 + 0.5 * (lo_ax + hi_ax), y_bar),
                 (sx0 + ext * 0.5, -proj - 1.25 * h),
                 f"เหล็กหลักตามยาว {long_n} - {long_bar} "
                 f"(S = {_cm(long_sp)} cm)", ha="center", fs=_A4_NOTE_FS)

    _apply_true_scale(axe, x_lo, x_hi, *side_y)
    axe.set_title("Side View" + (" (ตามแนวยาว)" if cut_y else ""),
                  fontsize=_A4_TITLE_FS)

    adj = dict(_A4_ADJUST)
    if basket:                       # tall asymmetric detail -> tighten the gap
        adj["hspace"] = 0.16
    fig.subplots_adjust(**adj)
    return _save_buf(fig, dpi=_A4_DPI, tight=False)


# ===========================================================================
# U-shape stair — side elevation
# ===========================================================================
def draw_u_stair_elevation(T_cm, R_cm, N, L_land_m, t_cm, *, span_m=None,
                           main_label=None):
    """Side elevation of one flight of a U-shape stair + landing, with
    tread / riser / span dimension lines and a rebar call-out."""
    T = float(T_cm)
    R = float(R_cm)
    n = max(int(N), 1)
    Lland = float(L_land_m) * 100.0        # cm
    t = float(t_cm)

    theta = math.atan2(R, T) if (T or R) else 0.0
    st_, ct = math.sin(theta), math.cos(theta)

    pts = [(0.0, 0.0), (0.0, R)]
    for i in range(1, n):
        pts.append((i * T, i * R))
        pts.append((i * T, (i + 1) * R))
    pts.append((n * T, n * R))
    top_x, top_y = n * T, n * R
    pts.append((top_x + Lland, top_y))
    pts.append((top_x + Lland, top_y - t))

    A = (t * st_, -t * ct)
    if abs(st_) > 1.0e-9:
        s = (top_y - t - A[1]) / st_
        x_C = A[0] + s * ct
    else:
        x_C = top_x
    pts.append((x_C, top_y - t))
    pts.append(A)

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    ax.add_patch(patches.Polygon(pts, closed=True, edgecolor=_CONC_EDGE,
                                 facecolor=_CONC_FILL, linewidth=1.6))

    # rebar following the soffit (schematic)
    ax.plot([A[0], x_C], [A[1], top_y - t], color=_GRID_Y, linewidth=1.6,
            zorder=3)
    ax.plot([x_C, top_x + Lland], [top_y - t, top_y - t], color=_GRID_Y,
            linewidth=1.6, zorder=3)

    x_span = max(xs) - min(xs)
    y_span = max(ys) - min(ys)

    # tread & riser on the first step
    _hdim(ax, 0.0, T, -0.22 * y_span, 0.0, f"$T = {T:.0f}$ cm")
    _vdim(ax, 0.0, R, -0.14 * x_span, 0.0, f"$R = {R:.0f}$ cm", left=True)
    # overall horizontal span
    _hdim(ax, 0.0, top_x + Lland, -0.40 * y_span, 0.0,
          f"ช่วงพาดรวม = {(top_x + Lland) / 100.0:.2f} m")
    # waist thickness (perpendicular-ish, shown vertically at mid-flight)
    _vdim(ax, (n * R) / 2.0 - t, (n * R) / 2.0,
          (n * T) / 2.0 + 0.10 * x_span, (n * T) / 2.0,
          f"$t = {t:.0f}$ cm")

    _callout(ax, ((A[0] + x_C) / 2.0, (A[1] + top_y - t) / 2.0),
             (x_span * 0.15, y_span * 1.05),
             main_label or "เหล็กหลักตามท้องบันได", ha="center")

    _frame(ax, min(xs), max(xs), min(ys), max(ys),
           l=0.24, r=0.14, b=0.48, t=0.28)
    fig.tight_layout(pad=0.5)
    return _save_buf(fig)


# ===========================================================================
# Straight stair — CAD side elevation (inclined one-way slab)
# ===========================================================================
def draw_stair_elevation(*, R_cm, T_cm, N, t_cm, covering_cm,
                         main_label="Main", temp_label="Temp"):
    """2D side elevation of a straight stair flight.

    Top surface  = a zig-zag of ``N`` steps (riser R, tread T).
    Bottom (waist) = a straight line parallel to the pitch line, offset ``t``
    perpendicular to the slope.
    Main rebar  = blue line parallel to the waist, offset by the cover.
    Temp rebar  = green dots spread along the main rebar.
    Dimension   = the horizontal span Lx.  Returns a Matplotlib ``Figure``.
    """
    R = float(R_cm)
    T = float(T_cm)
    n = max(int(N), 1)
    t = float(t_cm)
    cov = float(covering_cm)
    _MAIN, _TEMP = "#1f5fd0", "#2e7d32"

    th = math.atan2(R, T)
    s, c = math.sin(th), math.cos(th)
    Lx, Ht = n * T, n * R

    # top zig-zag (walking surface)
    top = [(0.0, 0.0)]
    for i in range(n):
        top.append((i * T, (i + 1) * R))
        top.append(((i + 1) * T, (i + 1) * R))

    # waist soffit — pitch line (0,0)->(Lx,Ht) shifted perpendicular by t
    px, py = s * t, -c * t
    sof_a = (0.0 + px, 0.0 + py)
    sof_b = (Lx + px, Ht + py)
    outline = top + [sof_b, sof_a, (0.0, 0.0)]

    fig, ax = plt.subplots(figsize=(8.0, 5.8))
    ax.add_patch(patches.Polygon(outline, closed=True, edgecolor=_CONC_EDGE,
                                 facecolor=_CONC_FILL, linewidth=1.8))

    # main rebar: soffit line offset toward the concrete by cover + bar radius
    md = 1.2
    ox, oy = -s * (cov + md), c * (cov + md)
    ra = (sof_a[0] + ox, sof_a[1] + oy)
    rb = (sof_b[0] + ox, sof_b[1] + oy)
    ax.plot([ra[0], rb[0]], [ra[1], rb[1]], color=_MAIN, linewidth=2.4,
            zorder=5, solid_capstyle="round")
    for k in range(n + 2):                    # temp bars end-on = green dots
        f = k / (n + 1)
        ax.plot([ra[0] + (rb[0] - ra[0]) * f], [ra[1] + (rb[1] - ra[1]) * f],
                marker="o", ms=5.0, mfc=_TEMP, mec=_TEMP, zorder=6)

    _hdim(ax, 0.0, Lx, -0.24 * Ht - t, py, f"$L_x = {Lx / 100.0:.2f}$ m",
          fs=_DIM_FS)
    _callout(ax, (0.5 * (ra[0] + rb[0]), 0.5 * (ra[1] + rb[1])),
             (0.12 * Lx, 1.16 * Ht), main_label, color=_MAIN, ha="left",
             fs=_NOTE_FS)
    _callout(ax, (ra[0] + (rb[0] - ra[0]) * 0.72,
                  ra[1] + (rb[1] - ra[1]) * 0.72),
             (0.60 * Lx, -0.44 * Ht - t), temp_label, color=_TEMP,
             ha="center", fs=_NOTE_FS)
    ax.text(0.5 * Lx, Ht * 1.02,
            f"N = {n} ขั้น · R {R:.1f} / T {T:.1f} cm · t {t:.0f} cm",
            ha="center", va="bottom", fontsize=_NOTE_FS - 1.0,
            color=_CONC_EDGE)

    ax.set_xlim(-0.14 * Lx, 1.16 * Lx)
    ax.set_ylim(-0.58 * Ht - t, 1.30 * Ht)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    ax.set_title("Stair Side Elevation", fontsize=_TITLE_FS)
    fig.tight_layout(pad=0.8)
    return fig
