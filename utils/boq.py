"""Building-wide Bill of Quantities (BOQ) estimation.

A quick, budget-stage take-off of the primary structural frame from the
Building Modeler grid: concrete volume (m3), formwork area (m2) and an
approximate reinforcement weight (kg) for columns, beams and the slab.

All section dimensions are in **centimetres**; the storey height is in
**metres**.  Results are metric throughout (m3, m2, kg).
"""

# Standard budget-stage reinforcement ratios (kg of steel per m3 of concrete)
REBAR_RATIO_COLUMN = 150.0
REBAR_RATIO_BEAM = 120.0
REBAR_RATIO_SLAB = 90.0


def _beam_length_m(x_coords, y_coords, void_panels):
    """Total length of beams running along every grid line that bounds a
    solid (non-void) slab panel.  Shared edges between two solid panels are
    counted once.
    """
    xs = [float(v) for v in x_coords]
    ys = [float(v) for v in y_coords]
    voids = {(int(i), int(j)) for i, j in (void_panels or [])}

    h_edges = set()   # (i, j) -> horizontal seg on y = ys[j], x in xs[i]..xs[i+1]
    v_edges = set()   # (i, j) -> vertical seg on x = xs[i], y in ys[j]..ys[j+1]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            if (i, j) in voids:
                continue
            h_edges.add((i, j))
            h_edges.add((i, j + 1))
            v_edges.add((i, j))
            v_edges.add((i + 1, j))

    total = sum(xs[i + 1] - xs[i] for i, _ in h_edges)
    total += sum(ys[j + 1] - ys[j] for _, j in v_edges)
    return total


def estimate_building_boq(active_columns, void_panels, x_coords, y_coords,
                          floor_height_m, col_b, col_h, beam_b, beam_h, slab_t,
                          *, rebar_ratio_col=REBAR_RATIO_COLUMN,
                          rebar_ratio_beam=REBAR_RATIO_BEAM,
                          rebar_ratio_slab=REBAR_RATIO_SLAB):
    """Estimate the structural BOQ for one storey of the modelled grid.

    Parameters
    ----------
    active_columns : iterable of (x, y)
        Node coordinates that carry a column.
    void_panels : iterable of (i, j)
        Panel indices to treat as openings (no slab, no bounding beams).
    x_coords, y_coords : list of float
        Absolute grid-line coordinates (m).
    floor_height_m : float
        Storey height (m).
    col_b, col_h, beam_b, beam_h, slab_t : float
        Average section dimensions (cm).  Beam web depth below the slab is
        ``beam_h - slab_t``.

    Returns
    -------
    dict
        ``columns`` / ``beams`` / ``slab`` / ``total`` sub-dicts plus a
        ``table`` list of rows ready for ``st.dataframe`` and the ``ratios``
        used.
    """
    fh = float(floor_height_m)
    cb, ch = float(col_b) / 100.0, float(col_h) / 100.0
    bb = float(beam_b) / 100.0
    st_m = float(slab_t) / 100.0
    web = max(float(beam_h) / 100.0 - st_m, 0.0)

    xs = [float(v) for v in x_coords]
    ys = [float(v) for v in y_coords]
    voids = {(int(i), int(j)) for i, j in (void_panels or [])}

    # ---- columns ----------------------------------------------------
    n_col = len(list(active_columns))
    col_conc = n_col * cb * ch * fh
    col_form = n_col * 2.0 * (cb + ch) * fh
    col_rebar = col_conc * float(rebar_ratio_col)

    # ---- beams ----------------------------------------------------
    beam_len = _beam_length_m(xs, ys, voids)
    beam_conc = beam_len * bb * web
    beam_form = beam_len * 2.0 * web
    beam_rebar = beam_conc * float(rebar_ratio_beam)

    # ---- slab ----------------------------------------------------
    grid_area = ((xs[-1] - xs[0]) * (ys[-1] - ys[0])) if len(xs) > 1 and \
        len(ys) > 1 else 0.0
    void_area = sum((xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
                    for (i, j) in voids
                    if i + 1 < len(xs) and j + 1 < len(ys))
    slab_area = max(grid_area - void_area, 0.0)
    slab_conc = slab_area * st_m
    slab_form = slab_area                       # soffit (bottom) only
    slab_rebar = slab_conc * float(rebar_ratio_slab)

    columns = {"count": n_col, "concrete_m3": col_conc,
               "formwork_m2": col_form, "rebar_kg": col_rebar}
    beams = {"length_m": beam_len, "concrete_m3": beam_conc,
             "formwork_m2": beam_form, "rebar_kg": beam_rebar}
    slab = {"area_m2": slab_area, "concrete_m3": slab_conc,
            "formwork_m2": slab_form, "rebar_kg": slab_rebar}
    total = {
        "concrete_m3": col_conc + beam_conc + slab_conc,
        "formwork_m2": col_form + beam_form + slab_form,
        "rebar_kg": col_rebar + beam_rebar + slab_rebar,
    }

    table = [
        _row("เสา (Columns)", columns),
        _row("คาน (Beams)", beams),
        _row("พื้น (Slab)", slab),
        _row("รวมทั้งหมด (Grand Total)", total),
    ]

    return {
        "columns": columns,
        "beams": beams,
        "slab": slab,
        "total": total,
        "table": table,
        "ratios": {
            "column_kg_per_m3": float(rebar_ratio_col),
            "beam_kg_per_m3": float(rebar_ratio_beam),
            "slab_kg_per_m3": float(rebar_ratio_slab),
        },
    }


def _row(name, part):
    return {
        "หมวดงาน": name,
        "ปริมาตรคอนกรีต (ลบ.ม.)": round(part["concrete_m3"], 2),
        "พื้นที่ไม้แบบ (ตร.ม.)": round(part["formwork_m2"], 1),
        "น้ำหนักเหล็กเสริม (กก.)": round(part["rebar_kg"], 0),
    }
