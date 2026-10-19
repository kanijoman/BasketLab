"""Season sums per team and period of the figures stored in ``DERIVED[].periods`` (#353).

Q1-Q4 are their own bucket; every overtime goes to ``OT``. Games whose play-by-play is ``unreliable`` contribute nothing but
are listed (``unreliable``), so the service can say how many were left out.
"""
from typing import Dict, List

from src.pbp.period_stats import COUNTERS

BUCKET_OT = "OT"


def build_period_pipeline(min_version: int) -> List[Dict]:
    def used(expr):
        return {"$cond": ["$used", expr, 0]}

    group: Dict[str, Dict] = {
        "_id": {"team": "$all.id", "bucket": "$bucket"},
        "team_name": {"$first": "$name"},
        "minutes": {"$sum": used("$all.periods.minutes")},
        "games": {"$addToSet": {"$cond": ["$used", "$_id", None]}},
        "unreliable": {"$addToSet": {"$cond": ["$used", None, "$_id"]}},
    }
    for field in COUNTERS:
        group[field] = {"$sum": used(f"$all.periods.{field}")}
        group[f"opp_{field}"] = {"$sum": used(f"$all.periods.opp_{field}")}
    return [
        {"$match": {"DERIVED.v": {"$gte": min_version}}},
        {"$project": {"all": "$DERIVED.TEAM", "names": "$HEADER.TEAM.name"}},
        {"$unwind": {"path": "$all", "includeArrayIndex": "i"}},
        {"$addFields": {"name": {"$arrayElemAt": ["$names", "$i"]}, "used": {"$ne": ["$all.quality_level", "unreliable"]}}},
        {"$unwind": "$all.periods"},
        {"$addFields": {"bucket": {"$cond": [{"$lte": ["$all.periods.p", 4]}, {"$toString": "$all.periods.p"}, BUCKET_OT]}}},
        {"$group": group},
    ]
