"""Per-collection metadata stored at scrape time (``COLLECTION_META``, one document per collection).

The calendar URL of a competition cannot be derived reliably from the games alone, so the scrape
job records the selection it used; the live match list reads it (issue #119).
"""
from datetime import datetime, timezone
from typing import Any

COLLECTION_META = "COLLECTION_META"


def save_feb_meta(db: Any, collection_name: str, params: Any) -> None:
    """Upsert the FEB scrape selection (``FEBScrapeParams``) for ``collection_name``."""
    doc = {
        "league": "FEB",
        "competition_url": params.competition_url, "season_value": params.season_value,
        "group_value": params.group_value, "year": params.year,
        "competition_label": params.competition_label, "season_label": params.season_label,
        "group_label": params.group_label,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    db.repository.connection.get_collection(COLLECTION_META).replace_one({"_id": collection_name}, doc, upsert=True)
