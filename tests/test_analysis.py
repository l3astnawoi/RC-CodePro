"""Regression golden values — utils/analysis.py : solve_continuous_beam.

Deterministic matrix-stiffness solver.  Reaction / span / total-load
quantities are exact; the governing +M sample (Mu_pos / M_max) depends on
the fixed sampling grid and is locked to its current sampled value.
"""

import numpy as np
import pytest

from _helpers import approx
from utils.analysis import solve_continuous_beam


def test_two_equal_spans():
    r = solve_continuous_beam([4.0, 4.0], 2480.0)
    assert r["reactions_kgf"] == [approx(3720.0), approx(12400.0), approx(3720.0)]
    assert r["x_supports_m"] == [approx(0.0), approx(4.0), approx(8.0)]
    assert r["L_total_m"] == approx(8.0)
    assert r["Mu_pos_kgfm"] == approx(2789.8042978712692)
    assert r["Mu_neg_kgfm"] == approx(4960.0)
    assert r["Vu_kgf"] == approx(6200.0)
    assert len(r["x"]) == 205
    assert float(r["x"][0]) == approx(0.0)
    assert float(r["x"][-1]) == approx(8.0)
    assert float(r["V"][0]) == approx(3720.0)
    assert float(r["V"][-1]) == approx(0.0)
    assert float(r["M"][0]) == approx(0.0)
    assert float(r["M"][-1]) == approx(0.0)
    assert float(r["M"].max()) == approx(2789.8042978712692)
    assert float(r["M"].min()) == approx(-4960.0)
    assert float(np.abs(r["V"]).max()) == approx(6200.0)
    # equilibrium: sum of reactions == total applied load
    assert sum(r["reactions_kgf"]) == approx(2480.0 * 8.0)


def test_three_spans():
    r = solve_continuous_beam([4.0, 5.0, 4.0], 3680.0)
    assert r["reactions_kgf"] == [
        approx(5470.0), approx(18450.0), approx(18450.0), approx(5470.0)]
    assert r["x_supports_m"] == [
        approx(0.0), approx(4.0), approx(9.0), approx(13.0)]
    assert r["L_total_m"] == approx(13.0)
    assert r["Mu_pos_kgfm"] == approx(4064.757094588713)
    assert r["Mu_neg_kgfm"] == approx(7560.0)
    assert r["Vu_kgf"] == approx(9250.0)
    assert len(r["x"]) == 248
    assert float(r["M"].min()) == approx(-7560.0)
    assert sum(r["reactions_kgf"]) == approx(3680.0 * 13.0)


def test_single_span():
    r = solve_continuous_beam([6.0], 2000.0)
    assert r["reactions_kgf"] == [approx(6000.0), approx(6000.0)]
    assert r["L_total_m"] == approx(6.0)
    assert r["Mu_pos_kgfm"] == approx(8999.772733011792)
    assert r["Mu_neg_kgfm"] == approx(0.0)          # note: current value is -0.0
    assert r["Vu_kgf"] == approx(6000.0)
    assert len(r["x"]) == 202
    assert float(r["M"].min()) == approx(0.0)
    assert sum(r["reactions_kgf"]) == approx(12000.0)


def test_empty_spans_raises():
    with pytest.raises(ValueError):
        solve_continuous_beam([], 1000.0)


def test_all_non_positive_spans_raises():
    with pytest.raises(ValueError):
        solve_continuous_beam([0.0, -1.0], 1000.0)


def test_non_positive_spans_are_filtered():
    # a zero span mixed with valid ones is dropped, not an error
    r = solve_continuous_beam([4.0, 0.0, 4.0], 2480.0)
    assert r["L_total_m"] == approx(8.0)
    assert len(r["reactions_kgf"]) == 3
