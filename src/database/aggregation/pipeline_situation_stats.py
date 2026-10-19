"""Season sums per team of the situation figures stored in ``DERIVED`` (#354) and of its timeouts (#355).

Games that are not reliable (#390: more than 10 % of their points of unknown origin, or a possession count more than 10 % off the estimate) contribute nothing (they are counted for the situations).
"""
from typing import Dict, List

from .possession_expr import DOUBTFUL_USED, RELIABLE_GAME

EDGE_KEYS = ("pts", "opp_pts", "poss", "opp_poss", "tov", "opp_tov")
_PERIOD_TOTALS = ("pts", "poss", "tov", "opp_pts", "opp_poss", "opp_tov")


def _start(min_version: int) -> List[Dict]:
    return [
        {"$match": {"DERIVED.v": {"$gte": min_version}}},
        {"$project": {"all": "$DERIVED.TEAM", "names": "$HEADER.TEAM.name"}},
        {"$unwind": {"path": "$all", "includeArrayIndex": "i"}},
        {"$addFields": {"name": {"$arrayElemAt": ["$names", "$i"]}, "used": RELIABLE_GAME}},
    ]


def build_situations_pipeline(min_version: int) -> List[Dict]:
    """One row per team with the sums of ``ato_own``, ``ato_rival``, ``first_poss``, both edge windows and the period totals."""
    def used(expr):
        return {"$cond": ["$used", expr, 0]}

    totals = {f"tot_{k}": {"$sum": f"$all.periods.{k}"} for k in _PERIOD_TOTALS}
    group: Dict[str, Dict] = {
        "_id": "$all.id", "team_name": {"$first": "$name"},
        "games": {"$sum": used(1)}, "games_unreliable": {"$sum": {"$cond": ["$used", 0, 1]}},
        "games_doubtful": {"$sum": {"$cond": [DOUBTFUL_USED, 1, 0]}},
    }
    for block in ("ato_own", "ato_rival", "first_poss"):
        for key in ("n", "pts"):
            group[f"{block}_{key}"] = {"$sum": used(f"$all.{block}.{key}")}
    for window in ("start", "end"):
        for key in EDGE_KEYS:
            group[f"{window}_{key}"] = {"$sum": used(f"$all.edges.{window}.{key}")}
    for key in totals:
        group[key] = {"$sum": used(f"${key}")}
    return _start(min_version) + [{"$addFields": totals}, {"$group": group}]


def build_timeouts_pipeline(min_version: int) -> List[Dict]:
    """One row per team and caller (``own`` / ``rival``; a team with no analysable timeouts gets one row with no caller)."""
    def net(side):
        def ratio(num, den):
            return {"$cond": [{"$gt": [f"$all.timeouts.{side}.{den}", 0]}, {"$divide": [f"$all.timeouts.{side}.{num}", f"$all.timeouts.{side}.{den}"]}, 0]}
        return {"$multiply": [{"$subtract": [ratio("pts", "poss"), ratio("opp_pts", "opp_poss")]}, 100]}

    has_entry = {"$ne": [{"$ifNull": ["$all.timeouts.caller", None]}, None]}
    group: Dict[str, Dict] = {
        "_id": {"team": "$all.id", "caller": "$all.timeouts.caller"}, "team_name": {"$first": "$name"},
        "n": {"$sum": {"$cond": [has_entry, 1, 0]}},
        "doubtful": {"$addToSet": {"$cond": [DOUBTFUL_USED, "$_id", None]}},
        "net_before": {"$avg": "$pre_net"}, "net_after": {"$avg": "$post_net"},
        "improved": {"$sum": {"$cond": [{"$gt": ["$delta", 0]}, 1, 0]}},
        "worsened": {"$sum": {"$cond": [{"$lt": ["$delta", 0]}, 1, 0]}},
    }
    return _start(min_version) + [
        {"$match": {"used": True}},
        {"$unwind": {"path": "$all.timeouts", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"pre_net": net("pre"), "post_net": net("post")}},
        {"$addFields": {"delta": {"$subtract": ["$post_net", "$pre_net"]}}},
        {"$group": group},
    ]
