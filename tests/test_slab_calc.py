"""Regression golden values — modules/slab.py design helpers.

_temp_steel_ratio, _as_flexure_ksc, _spacing_for, _required_as_flexure,
_beta1_ksc, _rho_max_ksc (EV-04).
"""

from _helpers import approx
import modules.slab as S
from utils.aci_318m import bar_area


def test_beta1_ksc():
    """EV-04 — MKS stress-block factor (ACI 318M-08 10.2.7.3)."""
    assert S._beta1_ksc(240.0) == approx(0.85)
    assert S._beta1_ksc(280.0) == approx(0.85)               # boundary
    assert S._beta1_ksc(350.0) == approx(0.7999999999999999)


def test_rho_max_ksc():
    """EV-04 — tension-controlled maximum reinforcement ratio (ACI 10.3.4).
    Wired into the _render_slab_design verdict so an over-reinforced slab
    (eps_t < 0.005, and < 0.004 violating 10.3.5) now FAILs instead of
    receiving a non-conservative PASS.  Same value as modules/beam.py."""
    assert S._rho_max_ksc(240.0, 4000.0) == approx(0.01625625)
    assert S._rho_max_ksc(280.0, 4000.0) == approx(0.85 * 0.85 * 280.0 / 4000.0
                                                   * 0.003 / 0.008)


def test_temp_steel_ratio():
    assert S._temp_steel_ratio(300.0) == approx(0.002)
    assert S._temp_steel_ratio(350.0) == approx(0.002)      # boundary
    assert S._temp_steel_ratio(420.0) == approx(0.0018)
    assert S._temp_steel_ratio(500.0) == approx(0.001512)


def test_as_flexure_ksc_feasible():
    As, feasible = S._as_flexure_ksc(800.0, 100.0, 10.0, 240.0, 4000.0)
    assert As == approx(2.2728686116930024)
    assert feasible is True


def test_as_flexure_ksc_zero_moment():
    assert S._as_flexure_ksc(0.0, 100.0, 10.0, 240.0, 4000.0) == (0.0, True)


def test_as_flexure_ksc_infeasible():
    As, feasible = S._as_flexure_ksc(1.0e6, 100.0, 5.0, 240.0, 4000.0)
    assert As is None
    assert feasible is False


def test_spacing_for():
    ab = bar_area("DB12") / 100.0
    S_cm, As_prov = S._spacing_for(ab, 5.0, 25.0)
    assert S_cm == approx(22.5)
    assert As_prov == approx(5.026666666666666)


def test_spacing_for_zero_requirement_uses_s_max():
    ab = bar_area("DB12") / 100.0
    S_cm, As_prov = S._spacing_for(ab, 0.0, 25.0)
    assert S_cm == approx(25.0)
    assert As_prov == approx(4.524)


def test_required_as_flexure():
    As, Rn, rho, feasible = S._required_as_flexure(60.0, 1000.0, 100.0, 24.0, 420.0)
    assert As == approx(1998.4131390850227)
    assert Rn == approx(6.666666666666667)
    assert rho == approx(0.019984131390850226)
    assert feasible is True
