"""Time helpers."""
from datetime import datetime, time, timezone


def utc_now_naive() -> datetime:
    """Current UTC time without tzinfo (what MongoDB stores; replaces ``datetime.utcnow``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def end_of_day(iso_date: str) -> datetime:
    """The last instant of the day ``YYYY-MM-DD`` (issue #643): the upper bound of a range of dates that is documented as inclusive. FEB writes a game with
    its time, so a bound at midnight left out the games of the last day; the pipelines of FBCYL (which keep only the day) normalise it back to the day."""
    return datetime.combine(datetime.fromisoformat(iso_date).date(), time.max)


def fbcyl_game_day(raw_time) -> str:
    """The day ``YYYY-MM-DD`` of a FBCYL game from its ``stats.time`` (#681), or ``""`` when it cannot be read.

    FBCYL writes ``Oct 3, 2026, 6:30:00 PM`` today (a comma after the year and a narrow no-break space, U+202F, before the meridiem) and wrote ``Oct 4, 2025 7:00:00 PM``
    before: both give their day. (``stats.startDate`` is not in the documents.)
    """
    if not raw_time:
        return ""
    words = str(raw_time).replace(" ", " ").split()
    if len(words) < 3:
        return ""
    try:
        return datetime.strptime(f"{words[0]} {words[1]} {words[2].rstrip(',')}", "%b %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""
