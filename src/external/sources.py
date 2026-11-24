"""The external sources that really exist (#887): what ``run_external_refresh.py --source X`` registers before it runs.

FIBA (D3), ACB (D2), NCAA (D4) and the Euroleague (D6) have a scraper; a source without one is ``pending`` (``refresh_source``), which is not a failure. A source already registered is never
replaced: the tests register their own, and a caller that wants another client says so first.
"""
from __future__ import annotations

from typing import Optional

from src.external import registry
from src.external.acb_client import AcbClient
from src.external.acb_source import DEFAULT_BUDGET as ACB_BUDGET
from src.external.acb_source import AcbSource
from src.external.euroleague_client import EuroleagueClient
from src.external.euroleague_source import DEFAULT_BUDGET as EUROLEAGUE_BUDGET
from src.external.euroleague_source import EuroleagueSource
from src.external.ncaa_client import NcaaClient
from src.external.ncaa_source import DEFAULT_BUDGET as NCAA_BUDGET
from src.external.ncaa_source import NcaaSource
from src.external.fiba_client import FibaClient
from src.external.fiba_source import DEFAULT_BUDGET, FibaSource


def make_client() -> FibaClient:
    """The client of the real site of FIBA (the tests replace it with the fake one)."""
    return FibaClient()


def default_source(name: str, budget: Optional[int] = None):
    """The source of ``name`` with its client, or ``None`` when it has no scraper yet. ``budget``: how many games a run may ask for (the default of the source when absent)."""
    if name == "fiba":
        return FibaSource(make_client(), budget=budget or DEFAULT_BUDGET)
    if name == "acb":
        return AcbSource(AcbClient(max_requests=budget or ACB_BUDGET))
    if name == "euroleague":
        return EuroleagueSource(EuroleagueClient(max_requests=budget or EUROLEAGUE_BUDGET))
    if name == "ncaa":
        return NcaaSource(NcaaClient(max_requests=budget or NCAA_BUDGET))
    return None


def register_defaults(name: str, budget: Optional[int] = None) -> None:
    """Register the source of ``name`` unless it already is (or has no scraper yet)."""
    if name in registry.SOURCES:
        return
    source = default_source(name, budget)
    if source is not None:
        registry.register(source)
