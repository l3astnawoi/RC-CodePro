"""EV validation package — collection guard.

At EV-01 this directory holds only *placeholders*.  None of them contain an
executable validation case yet: every planned case needs an independent
reference value (hand calc / independent tool / ACI text) that does not
exist until EV-03, so each placeholder carries ``Reference: REFERENCE
REQUIRED`` and ``Status: NOT VALIDATED``.

To keep the regression baseline at exactly **73 passed, 0 skipped**, the
``test_*_validation.py`` placeholders are excluded from pytest collection
here.  EV-03 removes a filename from this list when it replaces that stub
with an executable case that asserts against a real independent reference.

This file adds no fixtures and changes no behaviour of the existing
``tests/`` suite.
"""

collect_ignore_glob = ["test_*_validation.py"]
