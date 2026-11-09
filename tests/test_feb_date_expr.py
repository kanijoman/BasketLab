"""The FEB start date expression is written once (issue #452, block 4)."""
from datetime import datetime

from src.database.aggregation.feb_date_expr import feb_start_date
from src.database.aggregation.pipeline_opponent_stats import OpponentStatsPipelineMixin
from src.database.aggregation.pipeline_team_stats import TeamStatsPipelineMixin

EXPECTED = {"$dateFromString": {"dateString": "$HEADER.starttime", "format": "%d-%m-%Y - %H:%M", "onError": None, "onNull": None}}


def test_expression_reads_feb_start_time_and_gives_none_when_unreadable():
    assert feb_start_date() == EXPECTED


def test_each_call_is_a_new_dict_so_one_stage_cannot_change_another():
    first = feb_start_date()
    first["$dateFromString"]["timezone"] = "UTC"
    assert feb_start_date() == EXPECTED


def test_team_and_opponent_pipelines_parse_the_date_with_it_and_group_the_same_way():
    flt = {"$gte": datetime(2024, 1, 1)}
    team = TeamStatsPipelineMixin.build_team_stats_pipeline(flt)
    opp = OpponentStatsPipelineMixin.build_opponent_stats_pipeline(flt)
    for pipeline in (team, opp):
        assert pipeline[0] == {"$addFields": {"parsedDate": EXPECTED}}
    assert TeamStatsPipelineMixin._group_by_team() == OpponentStatsPipelineMixin._group_opponent_by_team()
