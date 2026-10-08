"""Rule-based team reports (own-team analysis and rival scouting).

Pure functions, no I/O or database: season data comes in as plain dicts. Replaces the
retired LLM analysis; same pattern as the live alert engine (rules -> findings -> text).
"""
from .config import ReportConfig
from .engine import MODES, build_team_report

__all__ = ["MODES", "ReportConfig", "build_team_report"]
