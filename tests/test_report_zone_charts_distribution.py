"""The zone charts of the weekly report and of the individual scouting rate against the right reference (issue #765): the team's zones against the teams, a player's against the players."""
import io
import zipfile
from unittest.mock import MagicMock

import matplotlib

matplotlib.use("Agg")

from src.services import individual_scouting_service as scouting  # noqa: E402
from src.services import weekly_report_service as weekly  # noqa: E402


def _shots(n):
    """n shots of one player, spread over the court (the heat map needs shots that are not in a line)."""
    return [{"x": 4.0 + (i % 7), "y": 1.0 + ((i * i) % 5) * 1.3 + i * 0.01, "m": i % 2, "team": "0", "player_id": "7", "player_dorsal": "7", "player_name": "A"} for i in range(n)]


def test_weekly_report_asks_for_teams_for_the_team_chart_and_for_players_for_the_player_charts(monkeypatch):
    asked = []

    def distribution(analyzer, coll, fbcyl=False, by="team"):
        asked.append(by)
        return [{key: {"made": 1, "total": 2} for key in analyzer.zones.zones}] * 3

    monkeypatch.setattr(weekly, "league_zone_distribution", distribution)
    monkeypatch.setattr(weekly, "_extract_shots", lambda db, collection, team_id: (_shots(12), {}, False))
    service = weekly.WeeklyReportService(MagicMock())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        service._gen_shot_charts(zf, "FEB_X", "1", "Team", "folder")
    assert asked == ["team", "player"]


def test_the_weekly_report_does_not_scan_the_players_when_none_has_enough_shots(monkeypatch):
    asked = []
    monkeypatch.setattr(weekly, "league_zone_distribution", lambda analyzer, coll, fbcyl=False, by="team": asked.append(by_ := by) or None)
    monkeypatch.setattr(weekly, "_extract_shots", lambda db, collection, team_id: (_shots(4), {}, False))
    service = weekly.WeeklyReportService(MagicMock())
    with zipfile.ZipFile(io.BytesIO(), "w") as zf:
        service._gen_shot_charts(zf, "FEB_X", "1", "Team", "folder")
    assert asked == ["team"]


def test_the_individual_scouting_rates_a_player_against_the_players(monkeypatch):
    asked = []
    import src.shotcharts.league_zones as league_zones

    monkeypatch.setattr(league_zones, "league_zone_distribution", lambda analyzer, coll, fbcyl=False, by="team": asked.append(by) or [])
    assert scouting.IndividualScoutingDocxBuilder._load_league_zones(MagicMock()) == []
    assert asked == ["player"]
    assert scouting.IndividualScoutingDocxBuilder._load_league_zones(None) is None
