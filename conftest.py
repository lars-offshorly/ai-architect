"""Root conftest — adds src/ to sys.path so 'agents', 'api', etc. are importable."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
