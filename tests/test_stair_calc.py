"""Regression golden values — modules/stair.py design helpers.

_temp_steel_ratio, _required_as_flexure, _as_flexure_ksc, _spacing_for,
_beta1_ksc, _rho_max_ksc (EV-07).
(These mirror the slab helpers but are independent copies in stair.py.)
"""

from _helpers import approx
import modules.stair as ST
from utils.aci_318m import bar_area


def test_beta1_ksc():
    """EV-07 — MKS stress-block factor (ACI 318M-08 10.2.7.3)."""
    assert ST._beta1_ksc(240.0) == approx(0.85)
    assert ST._beta1_ksc(280.0) == approx(0.85)               # boundary
    assert ST._beta1_ksc(350.0) == approx(0.7999999999999999)


def test_rho_max_ksc():
    """EV-07 — tension-controlled maximum reinforcement ratio (ACI 10.3.4),
    wired into the _render_straight_stair verdict so an over-reinforced
    flight (eps_t < 0.005, and < 0.004 violating 10.3.5) now FAILs instead
    of receiving a non-conservative PASS.  Same value as beam / slab."""
    assert ST._rho_max_ksc(240.0, 4000.0) == approx(0.01625625)
    assert ST._rho_max_ksc(280.0, 4000.0) == approx(0.85 * 0.85 * 280.0 / 4000.0
                                                    * 0.003 / 0.008)


def test_temp_steel_ratio():
    assert ST._temp_steel_ratio(300.0) == approx(0.002)
    assert ST._temp_steel_ratio(420.0) == approx(0.0018)
    assert ST._temp_steel_ratio(500.0) == approx(0.001512)


def test_required_as_flexure():
    As, Rn, rho, feasible = ST._required_as_flexure(8.0, 1000.0, 100.0, 24.0, 420.0)
    assert As == approx(216.4636773040955)
    assert Rn == approx(0.8888888888888888)
    assert rho == approx(0.002164636773040955)
    assert feasible is True


def test_as_flexure_ksc():
    As, feasible = ST._as_flexure_ksc(600.0, 100.0, 12.0, 240.0, 4000.0)
    assert As == approx(1.4050169328563151)
    assert feasible is True


def test_as_flexure_ksc_zero_moment():
    assert ST._as_flexure_ksc(0.0, 100.0, 12.0, 240.0, 4000.0) == (0.0, True)


def test_spacing_for():
    ab = bar_area("DB10") / 100.0
    S_cm, As_prov = ST._spacing_for(ab, 4.0, 20.0)
    assert S_cm == approx(17.5)
    assert As_prov == approx(4.488)
