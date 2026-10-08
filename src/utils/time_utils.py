"""Time helpers."""
from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Current UTC time without tzinfo (what MongoDB stores; replaces ``datetime.utcnow``)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
