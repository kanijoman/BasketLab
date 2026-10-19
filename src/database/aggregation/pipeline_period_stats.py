"""Season sums per team and period of the figures stored in ``DERIVED[].periods`` (#353).

Q1-Q4 are their own bucket; every overtime goes to ``OT``. Games that are not reliable (#390: more than 10 % of their points of unknown origin, or a possession count more than 10 % off the estimate) contribute nothing but
are listed (``unreliable``), so the service can say how many were left out.
"""
from typing import Dict, List

from src.pbp.period_stats import COUNTERS

from .possession_expr import DOUBTFUL_USED, RELIABLE_GAME

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
        "doubtful": {"$addToSet": {"$cond": [DOUBTFUL_USED, "$_id", None]}},
    }
    for field in COUNTERS:
        group[field] = {"$sum": used(f"$all.periods.{field}")}
        group[f"opp_{field}"] = {"$sum": used(f"$all.periods.opp_{field}")}
    return [
        {"$match": {"DERIVED.v": {"$gte": min_version}}},
        {"$project": {"all": "$DERIVED.TEAM", "names": "$HEADER.TEAM.name"}},
        {"$unwind": {"path": "$all", "includeArrayIndex": "i"}},
        {"$addFields": {"name": {"$arrayElemAt": ["$names", "$i"]}, "used": RELIABLE_GAME}},
        {"$unwind": "$all.periods"},
        {"$addFields": {"bucket": {"$cond": [{"$lte": ["$all.periods.p", 4]}, {"$toString": "$all.periods.p"}, BUCKET_OT]}}},
        {"$group": group},
    ]
