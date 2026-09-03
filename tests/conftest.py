"""Pytest bootstrap for the RC CodePro engineering regression suite.

Adds the repository root to ``sys.path`` so ``import utils.*`` / ``import
modules.*`` resolve when pytest is run from anywhere.  Importing the module
under test must not render a Streamlit page — every calc helper tested here
is a plain function; the modules only build widgets inside their
``render_*`` entry points, which the tests never call.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Headless matplotlib in case a module under test imports utils.drawing.
import matplotlib  # noqa: E402

matplotlib.use("Agg")
