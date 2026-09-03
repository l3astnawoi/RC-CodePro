"""Shared tolerance for golden-value comparisons.

Golden values are captured from the CURRENT implementation (see
docs/REGRESSION_BASELINE.md).  Tolerance is tight — ``rel=1e-9`` — so any
real change to a formula, constant or unit is caught.  ``abs=1e-9`` covers
values that are legitimately zero (e.g. a signed ``-0.0``).
"""

import pytest

REL = 1.0e-9
ABS = 1.0e-9


def approx(value):
    return pytest.approx(value, rel=REL, abs=ABS)
