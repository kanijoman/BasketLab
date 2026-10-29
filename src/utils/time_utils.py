"""Time helpers."""
from datetime import datetime, time, timezone


def utc_now_naive() -> datetime:
    """Current UTC time without tzinfo (what MongoDB stores; replaces ``datetime.utcnow``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def end_of_day(iso_date: str) -> datetime:
    """The last instant of the day ``YYYY-MM-DD`` (issue #643): the upper bound of a range of dates that is documented as inclusive. FEB writes a game with
    its time, so a bound at midnight left out the games of the last day; the pipelines of FBCYL (which keep only the day) normalise it back to the day."""
    return datetime.combine(datetime.fromisoformat(iso_date).date(), time.max)
