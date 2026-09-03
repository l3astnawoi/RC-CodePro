"""EV-08 — Independent BUILDING MODEL / load-takedown validation reference.

Independent validation reference — NOT production calculation code.
Imports only ``math``.  No ``modules.*``, no ``utils.analysis``, no
production load / BOQ helper.

Re-derives, from first principles, what the Building Model computes:

  * grid coordinates from spacings
  * floor area = (X extent) * (Y extent) ; solid area = floor - voids
  * factored slab load  Wu = 1.2 (t/100 * 2400 + SDL) + 1.6 LL   (ACI 9.2)
  * TRIBUTARY column loads — every solid panel gives one quarter of its
    area to each of its four corner nodes; void panels give nothing;
    quarter-areas landing on a removed column are DROPPED (the engine's
    documented "simplified column takedown" -- Finding VF-05)
  * LOAD CONSERVATION checks
  * budget BOQ take-off (concrete / formwork / rebar for one storey)

MKS units: m / cm / kgf / kgf/m^2 / m^3 / m^2 / kg.
"""

import math

CONC_DENSITY_KGF_M3 = 2400.0
REBAR_RATIO_COLUMN = 150.0
REBAR_RATIO_BEAM = 120.0
REBAR_RATIO_SLAB = 90.0


# ---------------------------------------------------------------------------
def grid_coords(spacings):
    """Cumulative absolute grid-line coordinates from a list of bay spacings.
    ``[4, 5, 4]`` -> ``[0, 4, 9, 13]``."""
    xs = [0.0]
    for s in spacings:
        xs.append(xs[-1] + float(s))
    return xs


def floor_area(x_coords, y_coords):
    if len(x_coords) < 2 or len(y_coords) < 2:
        return 0.0
    return (x_coords[-1] - x_coords[0]) * (y_coords[-1] - y_coords[0])


def solid_area(x_coords, y_coords, void_panels):
    voids = {(int(i), int(j)) for i, j in (void_panels or [])}
    total = 0.0
    for i in range(len(x_coords) - 1):
        for j in range(len(y_coords) - 1):
            if (i, j) in voids:
                continue
            total += (x_coords[i + 1] - x_coords[i]) * (y_coords[j + 1] - y_coords[j])
    return total


def factored_slab_load(slab_t_cm, sdl_kgf_m2, ll_kgf_m2):
    """ACI 318M-08 9.2:  Wu = 1.2 (self-weight + SDL) + 1.6 LL.
    Self-weight = (t/100) m * 2400 kgf/m^3  (MKS literal, ~1.9% below
    24 kN/m^3 -- NOTE R8, identical to beam/slab/footing/stair)."""
    return (1.2 * (slab_t_cm / 100.0 * CONC_DENSITY_KGF_M3 + sdl_kgf_m2)
            + 1.6 * ll_kgf_m2)


def column_loads(x_coords, y_coords, active_columns, void_panels, wu_kgf_m2):
    """Independent reproduction of ``_calculate_column_loads``.

    Returns ``{(x, y): {"trib_area_m2": A, "Pu_kgf": A * Wu}}`` for every
    active column, and the totals + the "dropped" area.
    """
    xs = [round(float(v), 3) for v in x_coords]
    ys = [round(float(v), 3) for v in y_coords]
    voids = {(int(i), int(j)) for i, j in (void_panels or [])}
    active = {(round(float(px), 3), round(float(py), 3))
              for px, py in active_columns}

    trib = {k: 0.0 for k in active}
    dropped = 0.0
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            if (i, j) in voids:
                continue
            quarter = (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) / 4.0
            for cx, cy in ((xs[i], ys[j]), (xs[i + 1], ys[j]),
                           (xs[i], ys[j + 1]), (xs[i + 1], ys[j + 1])):
                key = (round(cx, 3), round(cy, 3))
                if key in trib:
                    trib[key] += quarter
                else:
                    dropped += quarter          # VF-05: quarter is lost

    loads = {k: {"trib_area_m2": a, "Pu_kgf": a * float(wu_kgf_m2)}
             for k, a in trib.items()}
    sum_area = sum(a for a in trib.values())
    return {
        "loads": loads,
        "sum_trib_area_m2": sum_area,
        "sum_Pu_kgf": sum_area * float(wu_kgf_m2),
        "dropped_area_m2": dropped,
        "solid_area_m2": solid_area(xs, ys, void_panels),
    }


def auto_group(column_loads_dict):
    """Rule-based clustering (NOT AI): ratio >= 0.75 -> C1, >= 0.45 -> C2,
    else C3.  ``column_loads_dict`` = ``{label: Pu_kgf}``."""
    if not column_loads_dict:
        return {}
    pmax = max(column_loads_dict.values()) or 1.0
    out = {}
    for lab, pu in column_loads_dict.items():
        r = pu / pmax
        out[lab] = "C1" if r >= 0.75 else "C2" if r >= 0.45 else "C3"
    return out


# ---------------------------------------------------------------------------
def beam_length_m(x_coords, y_coords, void_panels):
    """Total length of beams on every grid line bounding a solid panel;
    shared edges counted once.  Independent reproduction of
    ``utils.boq._beam_length_m``."""
    xs = [float(v) for v in x_coords]
    ys = [float(v) for v in y_coords]
    voids = {(int(i), int(j)) for i, j in (void_panels or [])}
    h_edges, v_edges = set(), set()
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            if (i, j) in voids:
                continue
            h_edges.add((i, j)); h_edges.add((i, j + 1))
            v_edges.add((i, j)); v_edges.add((i + 1, j))
    total = sum(xs[i + 1] - xs[i] for i, _ in h_edges)
    total += sum(ys[j + 1] - ys[j] for _, j in v_edges)
    return total


def boq(x_coords, y_coords, active_columns, void_panels, *, floor_height_m,
        col_b, col_h, beam_b, beam_h, slab_t):
    """Independent budget BOQ take-off for ONE storey.  cm section dims, m
    storey height; returns m3 / m2 / kg."""
    fh = float(floor_height_m)
    cb, ch = float(col_b) / 100.0, float(col_h) / 100.0
    bb = float(beam_b) / 100.0
    st_m = float(slab_t) / 100.0
    web = max(float(beam_h) / 100.0 - st_m, 0.0)

    n_col = len(list(active_columns))
    col_conc = n_col * cb * ch * fh
    col_form = n_col * 2.0 * (cb + ch) * fh
    col_rebar = col_conc * REBAR_RATIO_COLUMN

    blen = beam_length_m(x_coords, y_coords, void_panels)
    beam_conc = blen * bb * web
    beam_form = blen * 2.0 * web
    beam_rebar = beam_conc * REBAR_RATIO_BEAM

    s_area = solid_area(x_coords, y_coords, void_panels)
    slab_conc = s_area * st_m
    slab_form = s_area
    slab_rebar = slab_conc * REBAR_RATIO_SLAB

    return {
        "columns": {"count": n_col, "concrete_m3": col_conc,
                    "formwork_m2": col_form, "rebar_kg": col_rebar},
        "beams": {"length_m": blen, "concrete_m3": beam_conc,
                  "formwork_m2": beam_form, "rebar_kg": beam_rebar},
        "slab": {"area_m2": s_area, "concrete_m3": slab_conc,
                 "formwork_m2": slab_form, "rebar_kg": slab_rebar},
        "total": {
            "concrete_m3": col_conc + beam_conc + slab_conc,
            "formwork_m2": col_form + beam_form + slab_form,
            "rebar_kg": col_rebar + beam_rebar + slab_rebar,
        },
    }
