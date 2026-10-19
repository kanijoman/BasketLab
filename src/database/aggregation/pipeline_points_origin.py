"""Season sums of the points by origin stored in ``DERIVED`` (#352): per team, own figures and the rival's (``opp_``)."""
from typing import Dict, List

from .possession_expr import RELIABLE_GAME

SUMMED = ("pts_off_tov", "poss_off_tov", "pts_off_steal", "poss_off_steal", "pts_second_chance", "poss_second_chance",
          "pts_bench", "pts_paint", "pts")


def build_points_origin_pipeline(min_version: int) -> List[Dict]:
    """One row per team: games used and excluded (not reliable, #390: their possession origins cannot be trusted)."""
    def used(expr):
        return {"$cond": ["$used", expr, 0]}

    group: Dict[str, Dict] = {
        "_id": "$me.id",
        "team_name": {"$first": "$name"},
        "games": {"$sum": used(1)},
        "games_unreliable": {"$sum": {"$cond": ["$used", 0, 1]}},
        "games_paint": {"$sum": {"$cond": [{"$and": ["$used", {"$isNumber": "$me.pts_paint"}]}, 1, 0]}},
    }
    for field in SUMMED:
        group[field] = {"$sum": used(f"$me.{field}")}
        group[f"opp_{field}"] = {"$sum": used(f"$rival.{field}")}
    return [
        {"$match": {"DERIVED.v": {"$gte": min_version}}},
        {"$project": {"all": "$DERIVED.TEAM", "teams": "$DERIVED.TEAM", "names": "$HEADER.TEAM.name"}},
        {"$unwind": {"path": "$all", "includeArrayIndex": "i"}},
        {"$addFields": {
            "me": "$all",
            "rival": {"$arrayElemAt": ["$teams", {"$subtract": [1, "$i"]}]},
            "name": {"$arrayElemAt": ["$names", "$i"]},
            "used": RELIABLE_GAME,
        }},
        {"$group": group},
    ]
