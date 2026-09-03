"""Regression golden values — modules/beam.py design helpers.

_beta1_ksc, _rho_max_ksc, _flex_ksc, _required_as, _shear_check,
_section_calc.  All are plain functions (no Streamlit).  Golden values are
from the current implementation.
"""

from _helpers import approx
import modules.beam as BM


def test_beta1_ksc():
    assert BM._beta1_ksc(240.0) == approx(0.85)
    assert BM._beta1_ksc(280.0) == approx(0.85)
    assert BM._beta1_ksc(350.0) == approx(0.7999999999999999)


def test_rho_max_ksc():
    assert BM._rho_max_ksc(240.0, 4000.0) == approx(0.01625625)


def test_flex_ksc():
    a, Mn, phiMn = BM._flex_ksc(15.0, 4000.0, 240.0, 30.0, 50.0)
    assert a == approx(9.803921568627452)
    assert Mn == approx(27058.823529411762)
    assert phiMn == approx(24352.941176470587)


def test_required_as_feasible():
    As, Rn, rho, feasible = BM._required_as(150.0, 300.0, 500.0, 28.0, 420.0)
    assert As == approx(834.6274384126312)
    assert Rn == approx(2.2222222222222223)
    assert rho == approx(0.005564182922750875)
    assert feasible is True


def test_required_as_infeasible():
    As, Rn, rho, feasible = BM._required_as(1.0e9, 300.0, 100.0, 28.0, 420.0)
    assert As is None
    assert Rn == approx(370370370.3703704)
    assert rho is None
    assert feasible is False


def test_shear_check():
    r = BM._shear_check(120.0, 300.0, 500.0, 28.0, 280.0, "RB9", 150.0)
    assert r["Vu"] == approx(120000.0)
    assert r["phiVc"] == approx(101199.98764822062)
    assert r["Vs"] == approx(118757.33333333333)
    assert r["Vs_max"] == approx(523858.759590789)
    assert r["phiVs"] == approx(89068.0)
    assert r["phiVn"] == approx(190267.98764822062)
    assert r["s_max"] == approx(250.0)
    assert r["ok"] is True


def test_section_calc_over_reinforced_fails_ductility():
    """EV-03 regression — a section whose PROVIDED steel exceeds the
    tension-controlled maximum (As > As_max, eps_t < 0.005, here < 0.004)
    must FAIL, even though flexural strength, As_min and shear are all
    satisfied.  ACI 318M-08 10.3.4 / 10.3.5.

    Before the EV-03 fix `_section_calc` had no ductility check and
    returned ``passed = True`` for this section (non-conservative false
    PASS).  See docs/ENGINEERING_VALIDATION.md finding VF-11 / EV-03.
    """
    sec_in = {
        "label": "OverReinf", "top_size": "DB20", "bot_size": "DB32",
        "stirrup_size": "RB9", "Mu_top": 30.0, "Mu_bot": 150.0, "Vu": 80.0,
        "top_qty": 4, "bot_qty": 6, "stirrup_sp_cm": 15.0,
    }
    r = BM._section_calc(sec_in, 400.0, 600.0, 40.0, 24.0, 420.0)

    # the non-ductility checks are all satisfied for this section ...
    assert r["bot_req_ok"] is True
    assert r["bot_min_ok"] is True
    assert r["shear_ok"] is True
    # ... but the provided steel is past the tension-controlled ceiling ...
    assert r["As_bot_prov"] > r["As_max_bot"]
    assert r["bot_ductile_ok"] is False
    # ... so the section must NOT pass.
    assert r["passed"] is False


def test_section_calc_tension_controlled_ductile_ok():
    """EV-03 regression — a normal tension-controlled section keeps
    ``passed = True`` and reports the new ductility flags as True (guards
    against the EV-03 fix over-tightening the verdict)."""
    sec_in = {
        "label": "Mid", "top_size": "DB20", "bot_size": "DB20",
        "stirrup_size": "RB9", "Mu_top": 90.0, "Mu_bot": 110.0, "Vu": 120.0,
        "top_qty": 4, "bot_qty": 3, "stirrup_sp_cm": 15.0,
    }
    r = BM._section_calc(sec_in, 300.0, 500.0, 40.0, 24.0, 420.0)
    assert r["top_ductile_ok"] is True
    assert r["bot_ductile_ok"] is True
    assert r["As_bot_prov"] < r["As_max_bot"]
    assert r["passed"] is True


def test_section_calc():
    sec_in = {
        "label": "Mid", "top_size": "DB20", "bot_size": "DB20",
        "stirrup_size": "RB9", "Mu_top": 90.0, "Mu_bot": 110.0, "Vu": 120.0,
        "top_qty": 4, "bot_qty": 3, "stirrup_sp_cm": 15.0,
    }
    r = BM._section_calc(sec_in, 300.0, 500.0, 40.0, 24.0, 420.0)
    assert r["d_top"] == approx(441.0)
    assert r["d_bot"] == approx(441.0)
    assert r["As_top_req"] == approx(564.7117039173106)
    assert r["As_bot_req"] == approx(697.7585267014773)
    assert r["As_min"] == approx(441.0)
    assert r["As_top_prov"] == approx(1256.64)
    assert r["As_bot_prov"] == approx(942.48)
    assert r["feas_top"] is True
    assert r["feas_bot"] is True
    assert r["top_req_ok"] is True
    assert r["bot_req_ok"] is True
    assert r["top_min_ok"] is True
    assert r["bot_min_ok"] is True
    assert r["phiVc_kN"] == approx(82.63721070740468)
    assert r["phiVs_kN"] == approx(117.836964)
    assert r["phiVn_kN"] == approx(200.4741747074047)
    assert r["Vs_max_kN"] == approx(427.7690907206831)
    assert r["s_max_mm"] == approx(220.5)
    assert r["shear_ok"] is True
    assert r["passed"] is True
    assert r["top_dia"] == approx(20.0)
    assert r["bot_dia"] == approx(20.0)
    assert r["stir_dia"] == approx(9.0)
