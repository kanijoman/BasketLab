"""Pytest configuration for MetricsForAll tests."""

import sys
from pathlib import Path

# Add src/ to Python path so imports work correctly
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
