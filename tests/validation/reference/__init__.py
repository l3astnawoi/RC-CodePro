"""EV-02 — Independent Engineering Reference calculators.

Independent validation reference — NOT production calculation code.

Every module in this package computes an *expected* engineering result
from first principles (ACI 318M-08 equations + explicit arithmetic), with
**no import of any RC CodePro production calculation function**
(`utils.aci_318m`, `utils.analysis`, `utils.boq`, `modules.*`).

Allowed imports: the Python standard library, `math`, and `numpy`.

These references are consumed by `tests/validation/run_ev02_validation.py`,
which is the only place a production engine function may be called (to
obtain the *actual* result for comparison).
"""
