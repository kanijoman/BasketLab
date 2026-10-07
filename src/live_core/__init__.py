"""Live-game engine core: pure functions, standard library only.

Runs on the Android tablet (Pyodide) as well as under pytest. No I/O, no database, no
numpy: FEB / Drive access lives in the app shell, season data arrives in a
``PreparationPackage``. Enforced by ``tests/test_live_core_boundary.py``.
"""
