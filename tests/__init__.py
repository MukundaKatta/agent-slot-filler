"""Test package for agent_slot_filler.

Ensures the ``src/`` layout is importable when the test suite is run directly
(e.g. ``python -m unittest discover -s tests``) without first installing the
package, while remaining a no-op when the package is already importable.
"""

from __future__ import annotations

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)
