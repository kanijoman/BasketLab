"""Numeric utility functions for safe type conversions.

Re-exports the canonical implementations from src.utils.numeric_utils.
Kept here for backward compatibility with existing ``from .numeric_utils import``
calls throughout src/ui/.
"""

from src.utils.numeric_utils import safe_int, safe_float  # noqa: F401

__all__ = ["safe_int", "safe_float"]
