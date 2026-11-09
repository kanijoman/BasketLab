"""The start date of a FEB game in Mongo expressions (#452).

FEB writes ``HEADER.starttime`` as ``dd-mm-yyyy - hh:mm``; every pipeline that filters or sorts by date parses it with the same ``$dateFromString``
(``None`` when it cannot be read). It is written once here; each call returns a new dict so a stage can be changed without touching another.
"""
from typing import Any, Dict


def feb_start_date() -> Dict[str, Any]:
    """The expression that turns ``$HEADER.starttime`` into a date (``None`` if missing or unreadable)."""
    return {"$dateFromString": {"dateString": "$HEADER.starttime", "format": "%d-%m-%Y - %H:%M", "onError": None, "onNull": None}}
