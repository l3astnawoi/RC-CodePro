"""Regression golden values — modules/footing.py directly-callable helpers.

_temp_steel_ratio, _flexure_as, _pile_coords.

NOTE (see docs/REGRESSION_BASELINE.md): the punching-shear, one-way-shear,
soil-pressure, moment and elastic pile-reaction blocks live as nested
functions inside `_render_isolated_footing` / `_render_pile_cap` and cannot
be unit-tested without extracting them.  Extraction is explicitly out of
scope for the regression step — those are BLOCKED, not skipped silently.
"""

import math

from _helpers import approx
import modules.footing as F


def test_temp_steel_ratio():
    assert F._temp_steel_ratio(300.0) == approx(0.002)
    assert F._temp_steel_ratio(420.0) == approx(0.0018)
    assert F._temp_steel_ratio(500.0) == approx(0.001512)


def test_flexure_as_feasible():
    As, Rn, rho, feasible = F._flexure_as(50.0e6, 1000.0, 400.0, 24.0, 420.0)
    assert As == approx(333.55104426844775)
    assert Rn == approx(0.3472222222222222)
    assert rho == approx(0.0008338776106711194)
    assert feasible is True


def test_flexure_as_infeasible_returns_inf():
    As, Rn, rho, feasible = F._flexure_as(1.0e12, 1000.0, 50.0, 24.0, 420.0)
    assert As == math.inf
    assert Rn == approx(444444.44444444444)
    assert rho is None
    assert feasible is False


def test_flexure_as_zero_depth():
    As, Rn, rho, feasible = F._flexure_as(10.0e6, 1000.0, 0.0, 24.0, 420.0)
    assert As == math.inf
    assert Rn == approx(0.0)
    assert rho is None
    assert feasible is False


def test_pile_coords_degenerate_moment_resistance():
    """EV-05 — the elastic pile-group distribution can only carry a moment
    about an axis with pile offset in the perpendicular direction
    (R_i = P/n + M_y x_i/Sx2 + M_x y_i/Sy2).

    n = 1  : Sx2 = Sy2 = 0  -> resists NO moment
    n = 2  : piles colinear on Y, Sx2 = 0  -> resists NO moment about Y
    n >= 3 : Sx2 > 0 and Sy2 > 0            -> resists both

    `_render_pile_cap` now gates the verdict on this (``ecc_resolvable_ok``):
    an applied column eccentricity about an un-resisted axis must FAIL, not
    silently PASS.  These asserts pin the geometry that gate relies on.
    """
    S = 900.0

    one = F._pile_coords(1, S)
    assert sum(px * px for (px, py) in one) == 0.0
    assert sum(py * py for (px, py) in one) == 0.0

    two = F._pile_coords(2, S)
    assert sum(px * px for (px, py) in two) == 0.0        # no X offset
    assert sum(py * py for (px, py) in two) > 0.0         # has Y offset

    for n in (3, 4, 5, 6, 7, 8, 9):
        pts = F._pile_coords(n, S)
        assert sum(px * px for (px, py) in pts) > 0.0, n
        assert sum(py * py for (px, py) in pts) > 0.0, n


def test_pile_coords_layouts():
    assert F._pile_coords(1, 900.0) == [(approx(0.0), approx(0.0))]
    assert F._pile_coords(2, 900.0) == [
        (approx(0.0), approx(-450.0)), (approx(0.0), approx(450.0))]
    assert F._pile_coords(4, 900.0) == [
        (approx(-450.0), approx(-450.0)), (approx(450.0), approx(-450.0)),
        (approx(450.0), approx(450.0)), (approx(-450.0), approx(450.0))]

    tri = F._pile_coords(3, 900.0)
    assert tri[0] == (approx(0.0), approx(519.6152422706632))
    assert tri[1] == (approx(450.0), approx(-259.8076211353316))
    assert tri[2] == (approx(-450.0), approx(-259.8076211353316))

    hept = F._pile_coords(7, 900.0)
    assert hept[0] == (approx(0.0), approx(0.0))
    assert hept[1] == (approx(900.0), approx(0.0))
    assert hept[2] == (approx(450.0), approx(779.4228634059948))

    assert len(F._pile_coords(9, 900.0)) == 9
    assert F._pile_coords(9, 900.0)[-1] == (approx(0.0), approx(0.0))
