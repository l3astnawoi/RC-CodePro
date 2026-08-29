"""Visual detailing — automatic RC cross-section drawings (matplotlib).

`draw_rc_section()` renders a rectangular concrete section with the tie /
stirrup outline and the main bars, and returns a PNG image in an
``io.BytesIO`` buffer.  All dimensions are in millimetres.
"""

import io

import matplotlib
matplotlib.use("Agg")            # headless backend (Streamlit / servers)
import matplotlib.pyplot as plt
import matplotlib.patches as patches


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


def _save_buf(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


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


def draw_rc_section(b_mm, h_mm, covering_mm, rebar_dia_mm, qty,
                    section_type="beam"):
    """Draw an RC rectangular cross-section.

    Parameters
    ----------
    b_mm, h_mm      : overall section width / height (mm)
    covering_mm     : clear cover to the tie / stirrup (mm)
    rebar_dia_mm    : main-bar diameter (mm)
    qty             : number of main bars
    section_type    : 'beam' (bottom row) or 'column' (perimeter)

    Returns
    -------
    io.BytesIO  -- PNG image buffer, positioned at 0.
    """
    b = float(b_mm)
    h = float(h_mm)
    cov = float(covering_mm)
    r = float(rebar_dia_mm) / 2.0
    n = max(int(qty), 1)

    fig, ax = plt.subplots(figsize=(4.0, 4.0))

    # Concrete outline
    ax.add_patch(patches.Rectangle(
        (0.0, 0.0), b, h,
        edgecolor="black", facecolor="#f0f0f0", linewidth=1.8))

    # Tie / stirrup — inner rectangle offset by the cover
    inner_x, inner_y = cov, cov
    inner_w = max(b - 2.0 * cov, 0.0)
    inner_h = max(h - 2.0 * cov, 0.0)
    ax.add_patch(patches.Rectangle(
        (inner_x, inner_y), inner_w, inner_h,
        edgecolor="#404040", facecolor="none", linewidth=1.2))

    # Main-bar centre positions (kept a bar radius inside the tie)
    x0, x1 = inner_x + r, inner_x + inner_w - r
    y0, y1 = inner_y + r, inner_y + inner_h - r
    if x1 < x0:
        x0 = x1 = (inner_x + inner_w / 2.0)
    if y1 < y0:
        y0 = y1 = (inner_y + inner_h / 2.0)

    if section_type == "column":
        centres = _column_positions(n, x0, x1, y0, y1)
    else:
        centres = _beam_positions(n, x0, x1, y0, y1)

    for cx, cy in centres:
        ax.add_patch(patches.Circle((cx, cy), r,
                                    facecolor="black", edgecolor="black"))

    # Framing
    mx, my = 0.1 * b, 0.1 * h
    ax.set_xlim(-mx, b + mx)
    ax.set_ylim(-my, h + my)
    plt.axis("equal")
    plt.axis("off")
    fig.tight_layout(pad=0.3)
    return _save_buf(fig)


def draw_footing_plan(B_mm, c_mm, covering_mm, qty):
    """Plan view of a square isolated footing with the column and a bar grid.

    Parameters
    ----------
    B_mm        : footing side (mm)
    c_mm        : square column side (mm)
    covering_mm : cover to the outermost bar (mm)
    qty         : bars per direction (draws `qty` lines each way)

    Returns
    -------
    io.BytesIO  -- PNG image buffer, positioned at 0.
    """
    B = float(B_mm)
    c = float(c_mm)
    cov = float(covering_mm)
    n = max(int(qty), 2)

    fig, ax = plt.subplots(figsize=(4.0, 4.0))

    # Footing outline (plan)
    ax.add_patch(patches.Rectangle(
        (0.0, 0.0), B, B,
        edgecolor="black", facecolor="#f0f0f0", linewidth=1.8))

    # Centred column
    ax.add_patch(patches.Rectangle(
        (B / 2.0 - c / 2.0, B / 2.0 - c / 2.0), c, c,
        edgecolor="black", facecolor="#d0d0d0", linewidth=1.4))

    # Reinforcement grid between the covers
    lo, hi = cov, B - cov
    if hi <= lo:
        lo = hi = B / 2.0
    for x in _even_spread(lo, hi, n):
        ax.plot([x, x], [lo, hi], color="#4a6fa5", linewidth=1.0)
    for y in _even_spread(lo, hi, n):
        ax.plot([lo, hi], [y, y], color="#4a6fa5", linewidth=1.0)

    m = 0.08 * B
    ax.set_xlim(-m, B + m)
    ax.set_ylim(-m, B + m)
    plt.axis("equal")
    plt.axis("off")
    fig.tight_layout(pad=0.3)
    return _save_buf(fig)


def draw_slab_strip(t_mm, covering_mm, main_dia_mm, temp_dia_mm,
                    main_spacing_mm, temp_spacing_mm):
    """Cross-section of a 1 m wide slab / stair strip showing the main
    (bottom) bars and the temperature bars resting on top of them.

    Returns
    -------
    io.BytesIO  -- PNG image buffer, positioned at 0.
    """
    W = 1000.0
    t = float(t_mm)
    cov = float(covering_mm)
    md = float(main_dia_mm)
    td = float(temp_dia_mm)

    fig, ax = plt.subplots(figsize=(8.0, max(8.0 * t / W, 1.3)))

    # Concrete strip
    ax.add_patch(patches.Rectangle(
        (0.0, 0.0), W, t,
        edgecolor="black", facecolor="#f0f0f0", linewidth=1.8))

    # Main bars along the bottom
    y_main = cov + md / 2.0
    for x in _bars_by_spacing(W, main_spacing_mm):
        ax.add_patch(patches.Circle((x, y_main), md / 2.0,
                                    facecolor="black", edgecolor="black"))

    # Temperature bars sitting on top of the main bars
    y_temp = cov + md + td / 2.0
    for x in _bars_by_spacing(W, temp_spacing_mm):
        ax.add_patch(patches.Circle((x, y_temp), td / 2.0,
                                    facecolor="#808080", edgecolor="#606060"))

    mx, my = 0.03 * W, max(0.25 * t, 10.0)
    ax.set_xlim(-mx, W + mx)
    ax.set_ylim(-my, t + my)
    plt.axis("equal")
    plt.axis("off")
    fig.tight_layout(pad=0.3)
    return _save_buf(fig)


def draw_pile_cap_plan(W_mm, L_mm, c_mm, pile_dia_mm, pile_positions,
                       col_pos=None):
    """Plan view of a pile cap.

    Parameters
    ----------
    W_mm, L_mm      : cap width / length (mm)
    c_mm            : square column side (mm)
    pile_dia_mm     : pile diameter (mm)
    pile_positions  : list of (x, y) pile centres relative to the
                      bottom-left corner (0, 0) of the cap (mm)
    col_pos         : optional (x, y) column centre relative to the
                      bottom-left corner.  Defaults to the cap centre.

    Returns
    -------
    io.BytesIO  -- PNG image buffer, positioned at 0.
    """
    W = float(W_mm)
    L = float(L_mm)
    c = float(c_mm)
    r = float(pile_dia_mm) / 2.0

    if col_pos is None:
        col_cx, col_cy = W / 2.0, L / 2.0
    else:
        col_cx, col_cy = float(col_pos[0]), float(col_pos[1])

    fig, ax = plt.subplots(figsize=(4.0, 4.0 * (L / W if W else 1.0)))

    # Cap outline
    ax.add_patch(patches.Rectangle(
        (0.0, 0.0), W, L,
        edgecolor="black", facecolor="#f0f0f0", linewidth=1.8))

    # Column (centred, or at col_pos when eccentric)
    ax.add_patch(patches.Rectangle(
        (col_cx - c / 2.0, col_cy - c / 2.0), c, c,
        edgecolor="black", facecolor="#d0d0d0", linewidth=1.4))

    # Piles — dashed red circles with a centre cross
    tick = max(r * 0.4, 1.0)
    for (px, py) in pile_positions:
        ax.add_patch(patches.Circle(
            (px, py), r,
            facecolor="white", edgecolor="red",
            linewidth=1.3, linestyle="--"))
        ax.plot([px - tick, px + tick], [py, py], color="red", linewidth=1.0)
        ax.plot([px, px], [py - tick, py + tick], color="red", linewidth=1.0)

    mx, my = 0.08 * W, 0.08 * L
    ax.set_xlim(-mx, W + mx)
    ax.set_ylim(-my, L + my)
    plt.axis("equal")
    plt.axis("off")
    fig.tight_layout(pad=0.3)
    return _save_buf(fig)
