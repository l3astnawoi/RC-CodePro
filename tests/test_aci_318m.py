"""Regression golden values — utils/aci_318m.py (SHARED CORE).

Values captured from the current implementation. They lock CURRENT
software behaviour, not an independent code check.
"""

import pytest

from _helpers import approx
from utils import aci_318m as A


# --- beta1 / get_beta1 -----------------------------------------------------
def test_beta1_representative():
    assert A.beta1(21.0) == approx(0.85)
    assert A.beta1(28.0) == approx(0.85)
    assert A.beta1(35.0) == approx(0.7999999999999999)
    assert A.get_beta1(24.0) == approx(0.85)


def test_beta1_boundary():
    assert A.beta1(56.0) == approx(0.65)
    assert A.beta1(100.0) == approx(0.65)          # clamped floor
    assert A.beta1(0.0) == approx(0.85)


# --- minimum / balanced / max flexural ratio ----------------------------
def test_rho_min_flexure():
    assert A.rho_min_flexure(24.0, 420.0) == approx(0.003333333333333333)
    assert A.rho_min_flexure(50.0, 500.0) == approx(0.0035355339059327377)


def test_as_min_flexure():
    assert A.as_min_flexure(28.0, 420.0, 1000.0, 450.0) == approx(1499.9999999999998)


def test_rho_balanced():
    assert A.rho_balanced(28.0, 420.0) == approx(0.02833333333333333)


def test_rho_max_flexure():
    assert A.rho_max_flexure(28.0, 420.0) == approx(0.018062499999999995)


def test_calc_As_min():
    assert A.calc_As_min(28.0, 420.0, 300.0, 500.0) == approx(499.99999999999994)


# --- phi (strain transition) ------------------------------------------
def test_phi_flexure_compression_controlled():
    assert A.phi_flexure(0.001) == approx(0.65)
    assert A.phi_flexure(0.002) == approx(0.65)          # at EPSILON_TY


def test_phi_flexure_transition():
    assert A.phi_flexure(0.0035) == approx(0.775)


def test_phi_flexure_tension_controlled():
    assert A.phi_flexure(0.006) == approx(0.9)
    assert A.phi_flexure(0.005) == approx(0.9)           # at EPSILON_TC


def test_phi_flexure_spiral():
    assert A.phi_flexure(0.0035, spiral=True) == approx(0.825)
    assert A.phi_flexure(0.001, spiral=True) == approx(0.75)


# --- shear ----------------------------------------------------------
def test_vc_beam():
    assert A.vc_beam(28.0, 300.0, 500.0) == approx(134933.31686429415)
    assert A.vc_beam(28.0, 300.0, 500.0, 0.75) == approx(101199.9876482206)


# --- MKS mirrors --------------------------------------------------
def test_rho_min_flexure_ksc():
    assert A.rho_min_flexure_ksc(240.0, 4000.0) == approx(0.0035)
    assert A.rho_min_flexure_ksc(500.0, 5000.0) == approx(0.0035777087639996636)


def test_as_min_flexure_ksc():
    assert A.as_min_flexure_ksc(240.0, 4000.0, 100.0, 45.0) == approx(15.750000000000002)


def test_vc_beam_ksc():
    assert A.vc_beam_ksc(240.0, 30.0, 45.0) == approx(11084.478336845628)


# --- rebar table ------------------------------------------------
def test_bar_area():
    assert A.bar_area("DB20") == approx(314.16)
    assert A.bar_area("DB16") == approx(201.06)
    assert A.bar_area("RB9") == approx(63.62)
    assert A.bar_area("RB6") == approx(28.27)
    assert A.bar_area("db20") == approx(314.16)          # case-insensitive


def test_bars_area():
    assert A.bars_area("DB16", 4) == approx(804.24)


def test_bar_area_unknown_raises():
    with pytest.raises(KeyError):
        A.bar_area("DB99")


# --- constants ------------------------------------------------
def test_constants_locked():
    assert A.EPSILON_CU == 0.003
    assert A.ES == 200000.0
    assert A.EPSILON_TY == 0.002
    assert A.EPSILON_TENSION_CONTROLLED == 0.005
    assert A.PHI == {
        "tension_controlled": 0.9,
        "compression_controlled_tied": 0.65,
        "compression_controlled_spiral": 0.75,
        "shear": 0.75,
        "torsion": 0.75,
        "bearing": 0.65,
    }
    assert A.phi == {
        "flexure": 0.9,
        "shear": 0.75,
        "compression_tied": 0.65,
        "compression_spiral": 0.75,
    }
