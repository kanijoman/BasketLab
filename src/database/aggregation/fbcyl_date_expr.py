"""The date of a FBCYL game in Mongo expressions (#681).

FBCYL writes ``stats.time`` as ``Oct 3, 2026, 6:30:00 PM`` today (a comma after the year and a narrow no-break space, U+202F, before the meridiem) and wrote
``Oct 4, 2025 7:00:00 PM`` before. The pipelines used to split on spaces and parse ``%b %d, %Y``, which cannot read ``2026,``: every date filter answered no team.
Here the string is read once, for both writings: the year loses its comma and the narrow space counts as a space. ``$dateFromString`` has no ``%I`` / ``%p``, so the hour
of a full date is added by hand to the day.
"""
from typing import Any, Dict, List, Optional

NARROW_SPACE = " "


def _part(index: int) -> Dict[str, Any]:
    return {"$arrayElemAt": ["$timeParts", index]}


# ``Oct 3, 2026, 6:30:00 PM`` -> ["Oct", "3,", "2026,", "6:30:00", "PM"]; the older writing gives the same five parts (the year without comma)
YEAR = {"$trim": {"input": _part(2), "chars": ","}}


def _day_from_parts() -> Dict[str, Any]:
    return {"$dateFromString": {"dateString": {"$concat": [_part(0), " ", _part(1), " ", YEAR]}, "format": "%b %d, %Y", "onError": None, "onNull": None}}


def parse_stages(field: str, out: str, with_time: bool = False, timezone: Optional[str] = None) -> List[Dict[str, Any]]:
    """The stages that add ``out``: the date (or, with ``with_time``, the date and hour) of the game written in ``field`` (``$stats.time``), ``None`` if it cannot be read."""
    parts = {"$split": [{"$replaceAll": {"input": field, "find": NARROW_SPACE, "replacement": " "}}, " "]}
    day = _day_from_parts()
    if timezone:
        day["$dateFromString"]["timezone"] = timezone
    if not with_time:
        return [{"$addFields": {"timeParts": parts}}, {"$addFields": {out: day}}]
    def number(index: int) -> Dict[str, Any]:
        return {"$convert": {"input": {"$arrayElemAt": [{"$split": [_part(3), ":"]}, index]}, "to": "int", "onError": None, "onNull": None}}

    hour, minute = number(0), number(1)
    minutes = {"$add": [{"$multiply": [{"$add": [{"$mod": [hour, 12]}, {"$cond": [{"$eq": [_part(4), "PM"]}, 12, 0]}]}, 60]}, minute]}
    return [{"$addFields": {"timeParts": parts}}, {"$addFields": {out: {"$dateAdd": {"startDate": day, "unit": "minute", "amount": minutes}}}}]


def parse_day_stages(field: str, out: str, timezone: Optional[str] = None) -> List[Dict[str, Any]]:
    return parse_stages(field, out, False, timezone)


def parse_datetime_stages(field: str, out: str) -> List[Dict[str, Any]]:
    return parse_stages(field, out, True)
