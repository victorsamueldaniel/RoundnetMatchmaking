"""conftest.py — adds the project root to sys.path so test files can resolve
package imports (e.g. `from core.main import ...`, `from core.fine_tuning_functions import *`)
after being moved into the tests/ subdirectory."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)
