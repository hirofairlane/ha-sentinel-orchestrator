"""Shared test fixtures / path setup.

The add-on source under `ha-addon/src` uses src-rooted imports
(`from config import ...`, `from utils import ...`), so the tests put that
directory on `sys.path` exactly the way `run.sh`/Docker does (`python /app/src/main.py`).
No module performs network or process I/O at import time, so importing here is safe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "ha-addon" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Signal "testing" to any code that wants to skip side effects (none currently
# does at import time, but keep the contract from the shared QA/CI standard).
os.environ.setdefault("SENTINEL_TESTING", "1")
