"""Backward-compatible alias: this module moved to ``src.pbp.possession_core``.

The module object is replaced in ``sys.modules`` so every name (including private
ones) is the *same object* as in the new location.
"""
import sys

from importlib import import_module

sys.modules[__name__] = import_module("src.pbp.possession_core")
