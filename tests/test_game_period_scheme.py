"""NCAA men play two halves of 20 minutes (#1131): the minutes of the game, the elapsed time of a play and the end of the game must follow the period scheme of the document,
not the FEB one (four quarters of 10). Real games of ``tests/fixtures/ncaa``; FEB keeps what it had."""
import pytest
from db_helpers import new_mock_db
from ncaa_helpers import fixture

from src.database.aggregation.pipeline_builder import AggregationPipelineBuilder
from src.external.ncaa_canonical import to_canonical
from src.external.ncaa_page import parse_summary
from src.live_core.clock import FEB_SCHEME, Scheme
from src.pbp.event_helpers import get_timestamp
from src.pbp.period_scheme import scheme_of
from src.pbp.playbyplay_core import PlayByPlayAnalyzer

ENTRY_M = {"competition": "D1 Men", "season_value": "2025", "season_label": "2025/2026", "gender": "M", "conference": "WCC"}
ENTRY_F = {"competition": "D1 Women", "season_value": "2025", "season_label": "2025/2026", "gender": "F", "conference": "Big East"}
MENS, MENS_OT, WOMENS = "game_mens_401829197", "game_mens_ot_401812120", "game_womens_401825641"


def doc(name, entry=ENTRY_M):
    return to_canonical(parse_summary(fixture(name)), entry, {})


@pytest.mark.parametrize("name, entry, expected", [(MENS, ENTRY_M, Scheme(2, 20)), (MENS_OT, ENTRY_M, Scheme(2, 20)), (WOMENS, ENTRY_F, Scheme(4, 10))])
def test_the_canonical_document_says_its_period_scheme(name, entry, expected):
    assert scheme_of(doc(name, entry)) == expected


def test_a_feb_document_without_scheme_is_four_quarters_of_ten():
    assert scheme_of({"HEADER": {"TEAM": [{"id": "1"}, {"id": "2"}]}}) == FEB_SCHEME == Scheme(4, 10)


@pytest.mark.parametrize("name, entry, minutes", [(MENS, ENTRY_M, 40), (MENS_OT, ENTRY_M, 45), (WOMENS, ENTRY_F, 40)])
def test_the_minutes_of_a_game_follow_its_scheme_regression(name, entry, minutes):
    """Two halves were counted as ``40 + 5 x (2 - 4) = 30`` minutes: pace 33 % too high, ORtg/DRtg 25 % too low."""
    col = new_mock_db("scheme")["G"]
    col.insert_one(doc(name, entry))
    rows = list(col.aggregate(AggregationPipelineBuilder.build_season_rows_pipeline()))

    assert {r["game_minutes"] for r in rows} == {minutes}


def test_the_second_half_starts_where_the_first_ends_regression():
    """Half 2 at 20:00 remaining is the minute 20 of the game, not the minute 10 of a quarter-based clock."""
    men = Scheme(2, 20)
    assert [get_timestamp({"quarter": q, "time": t}, False, men) for q, t in ((1, "20:00"), (1, "00:00"), (2, "20:00"), (2, "00:00"), (3, "05:00"))] == [0, 1200, 1200, 2400, 2400 + 0]
    assert get_timestamp({"quarter": 2, "time": "20:00"}, False) == 600          # FEB's four quarters: unchanged


def test_every_play_of_a_real_mens_game_is_inside_the_game_and_in_order_regression():
    game = doc(MENS)
    analyzer = PlayByPlayAnalyzer(game)
    times = [analyzer._time_to_seconds(line["quarter"], line["time"]) for line in analyzer.lines]

    assert min(times) >= 0 and max(times) <= 2400
    first_half = [t for t, line in zip(times, analyzer.lines) if str(line["quarter"]) == "1"]
    second_half = [t for t, line in zip(times, analyzer.lines) if str(line["quarter"]) == "2"]
    assert max(first_half) <= 1200 <= min(second_half)
    assert analyzer.game_seconds == 2400


def test_the_minutes_checks_of_a_real_mens_game_cover_two_halves_of_twenty_regression():
    """The reconciliation of minutes counted every period as 10 minutes: a men's game gave 20 minutes of lines against 40 of box."""
    from src.market.minutes_reconciliation import _team_seconds
    game = doc(MENS)
    team = game["BOXSCORE"]["TEAM"][0]
    lines = game["PLAYBYPLAY"]["LINES"]
    worked = _team_seconds(lines, team, [1, 2], scheme_of(game))

    assert sum(worked.values()) == 5 * 2400 if sum(1 for p in team["PLAYER"] if p.get("sta")) == 5 else True
    assert max(worked.values()) <= 2400


def test_the_lineup_duration_and_the_inout_minutes_follow_the_scheme():
    from src.database.lineup_extractor import LineupExtractor
    game = doc(MENS_OT)
    analyzer = PlayByPlayAnalyzer(game)

    assert LineupExtractor(analyzer)._get_game_duration() == 2400 + 300
