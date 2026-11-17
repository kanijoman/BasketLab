"""The external sources that exist, by name (#884). A source is an object with a ``name`` (``acb``, ``fiba``, ``ncaa``) and ``fetch(entry, since)``: the games of one competition of the catalogue, in the
canonical format (``market.canonical``), changed or new since ``since`` (``YYYY-MM-DD``; ``None`` the first time: the whole history). Each block D2 to D4 registers its own; until then none is registered and
the refresh of a source says it is pending, which is not a failure.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Protocol

from src.utils.collection_utils import EXTERNAL_SOURCES


class Source(Protocol):
    name: str

    def fetch(self, entry: Dict[str, Any], since: Optional[str]) -> Iterable[Dict[str, Any]]: ...


SOURCES: Dict[str, Source] = {}


def register(source: Source) -> Source:
    """Register a source under its name; one that is not an external source, or is registered twice, is a mistake."""
    if source.name not in EXTERNAL_SOURCES:
        raise ValueError(f"unknown source {source.name!r} (one of {EXTERNAL_SOURCES})")
    if source.name in SOURCES:
        raise ValueError(f"{source.name} is already registered")
    SOURCES[source.name] = source
    return source
