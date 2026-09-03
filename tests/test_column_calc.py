"""Regression golden values — modules/column.py P-M helpers (LIVE set).

_beta1_col_ksc, _col_bar_xy, _whitney_area_centroid, _calculate_pm_curve,
_point_in_poly.  Graphs are not rendered; the numeric curve data behind
them is checked instead.
"""

from _helpers import approx
import modules.column as C
from utils.aci_318m import bar_area

# rectangular 40x40 cm, cover 4, tie RB9 (0.9), 8 x DB20 (2.0), matches UI default
BARS_RECT = C._col_bar_xy("rect", 40.0, 40.0, None, 4.0, 0.9, 2.0, 8)
AB_DB20 = bar_area("DB20") / 100.0


def test_beta1_col_ksc():
    assert C._beta1_col_ksc(240.0) == approx(0.85)
    assert C._beta1_col_ksc(280.0) == approx(0.85)
    assert C._beta1_col_ksc(350.0) == approx(0.7999999999999999)


def test_col_bar_xy_rect():
    assert BARS_RECT == [
        (approx(-14.1), approx(-14.1)),
        (approx(0.0), approx(-14.1)),
        (approx(14.1), approx(-14.1)),
        (approx(14.1), approx(0.0)),
        (approx(14.1), approx(14.1)),
        (approx(0.0), approx(14.1)),
        (approx(-14.1), approx(14.1)),
        (approx(-14.1), approx(0.0)),
    ]


def test_col_bar_xy_circ():
    pts = C._col_bar_xy("circ", 45.0, 45.0, 45.0, 4.0, 0.9, 2.0, 8)
    expected = [
        (0.0, 16.6),
        (11.73797256769669, 11.73797256769669),
        (16.6, 0.0),
        (11.73797256769669, -11.73797256769669),
        (0.0, -16.6),
        (-11.737972567696689, -11.73797256769669),
        (-16.6, 0.0),
        (-11.737972567696692, 11.737972567696689),
    ]
    for (gx, gy), (ex, ey) in zip(pts, expected):
        assert gx == approx(ex)
        assert gy == approx(ey)


def test_whitney_area_centroid_rect():
    area, ybar = C._whitney_area_centroid("rect", 10.0, 40.0, None, 40.0)
    assert area == approx(400.0)
    assert ybar == approx(15.0)


def test_whitney_area_centroid_rect_full_depth_clamped():
    area, ybar = C._whitney_area_centroid("rect", 999.0, 40.0, None, 40.0)
    assert area == approx(1600.0)
    assert ybar == approx(0.0)


def test_whitney_area_centroid_circ():
    area, ybar = C._whitney_area_centroid("circ", 15.0, None, 45.0, 45.0)
    assert area == approx(464.0741792617941)
    assert ybar == approx(13.71324093230553)


def test_whitney_area_centroid_circ_zero():
    assert C._whitney_area_centroid("circ", 0.0, None, 45.0, 45.0) == (0.0, 0.0)


def test_calculate_pm_curve_rect_anchor_points():
    Mn, Pn, phiMn, phiPn = C._calculate_pm_curve(
        shape="rect", b=40.0, h=40.0, D=None, fc=240.0, fy=4000.0,
        bars=BARS_RECT, Ab=AB_DB20, spiral=False)
    assert len(Mn) == 46
    # pure-compression cap (Po) and design cap (alpha*phi*Po)
    assert float(Pn[0]) == approx(421804.1088)
    assert float(phiPn[0]) == approx(219338.136576)
    assert float(Mn[0]) == approx(0.0)
    assert float(phiMn[0]) == approx(0.0)
    # pure-tension anchor (-fy*Ast) and 0.9 * Pt
    assert float(Pn[-1]) == approx(-100531.20000000001)
    assert float(phiPn[-1]) == approx(-90478.08000000002)
    assert float(Mn[-1]) == approx(0.0)
    # a mid-curve balanced-ish point
    mid = len(Mn) // 2
    assert float(Mn[mid]) == approx(21700.10216963306)
    assert float(Pn[mid]) == approx(240706.25034467474)
    assert float(phiMn[mid]) == approx(14105.06641026149)
    assert float(phiPn[mid]) == approx(156459.06272403858)
    assert float(Mn.max()) == approx(26270.218353278913)


def test_point_in_poly():
    Mn, Pn, phiMn, phiPn = C._calculate_pm_curve(
        shape="rect", b=40.0, h=40.0, D=None, fc=240.0, fy=4000.0,
        bars=BARS_RECT, Ab=AB_DB20, spiral=False)
    assert C._point_in_poly(6000.0, 180000.0, phiMn, phiPn) is True
    assert C._point_in_poly(0.0, 900000.0, phiMn, phiPn) is False
    assert C._point_in_poly(50000.0, 180000.0, phiMn, phiPn) is False
