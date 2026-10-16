"""Season possessions of a team from the games' play-by-play (#351): repository sums and the /possessions entry."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from database.repository_possession import PossessionRepositoryMixin
from src.services._possession_stats_builder import apply_exact_fields, base_possession_entry


class _Repo(PossessionRepositoryMixin):
    def __init__(self, games):
        self.connection = MagicMock()
        self.connection.is_connected.return_value = True
        self._games = games

    def get_games_for_team(self, collection_name, team_id, only_with_playbyplay=False, projection=None):
        return self._games


def _game(home_pts=10, away_pts=10, extra_overtime=False, unreliable=False):
    """10 alternating baskets (5 possessions each), optionally an overtime basket or a team scoring 12 in a row."""
    def line(i, team, period="1", clock=None):
        seconds = 590 - 10 * i
        return {"num": str(i + 1), "idTeam": team, "idPlayer": "p", "action": "shoot", "text": "(X) P: TIRO DE 2 ANOTADO (Puntos: 2)",
                "quarter": period, "time": clock or f"{seconds // 60:02d}:{seconds % 60:02d}", "deleted": None}

    lines = [line(i, "H" if unreliable or i % 2 == 0 else "V") for i in range(12 if unreliable else 10)]
    if extra_overtime:
        lines.append(line(10, "H", "5", "04:00"))
    box = {"p2a": 5, "p2m": 5, "p3a": 0, "p3m": 0, "p1a": 0, "p1m": 0, "ro": 0, "rd": 0, "to": 0}
    return {
        "HEADER": {"TEAM": [{"id": "H", "name": "Home"}, {"id": "V", "name": "Visitor"}]},
        "BOXSCORE": {"TEAM": [{"id": "H", "TOTAL": {**{k: str(v) for k, v in box.items()}, "pts": str(home_pts)}},
                              {"id": "V", "TOTAL": {**{k: str(v) for k, v in box.items()}, "pts": str(away_pts)}}]},
        "PLAYBYPLAY": {"LINES": lines},
    }


def test_exact_season_figures_are_summed_over_the_games_with_pbp():
    stats = _Repo([_game(), _game(home_pts=20, away_pts=10)]).get_team_possession_stats("FEB_LF2_2025_A", "H")["exact"]

    assert stats["games"] == 2 and stats["possessions_per_game"] == 5.0 and stats["pace"] == 5.0
    assert stats["oer"] == 300.0 and stats["der"] == 200.0 and stats["net_rating"] == 100.0
    assert stats["games_by_source"] == {"pbp": 2} and stats["games_by_quality"] == {"ok": 2}


def test_pace_is_normalised_to_40_minutes_so_overtimes_do_not_inflate_it():
    stats = _Repo([_game(extra_overtime=True)]).get_team_possession_stats("FEB_LF2_2025_A", "H")["exact"]

    assert stats["pace"] == round(stats["possessions_per_game"] * 40 / 45, 2)


def test_games_without_a_reliable_feed_use_the_estimate_and_are_counted_as_such():
    stats = _Repo([_game(), _game(unreliable=True)]).get_team_possession_stats("FEB_LF2_2025_A", "H")["exact"]

    assert stats["games_by_source"] == {"pbp": 1, "estimate": 1} and stats["games_by_quality"] == {"ok": 1, "unreliable": 1}
    assert stats["possessions_source"] == "mixed"


def test_no_exact_block_without_play_by_play():
    doc = _game()
    doc["PLAYBYPLAY"] = {"LINES": []}

    assert "exact" not in _Repo([doc]).get_team_possession_stats("FEB_LF2_2025_A", "H")


def test_entry_takes_pace_and_ratings_from_the_exact_figures_and_reports_their_source():
    entry = base_possession_entry({"team_name": "Home", "possessions_per_game": 70.0, "offensive_rating": 100.0,
                                   "defensive_rating": 99.0, "net_rating": 1.0, "total_games": 2}, "H")
    exact = {"games": 2, "possessions_per_game": 5.0, "pace": 5.0, "oer": 300.0, "der": 200.0, "net_rating": 100.0,
             "orb_pct": 25.0, "drb_pct": 75.0, "possessions_source": "pbp", "games_by_source": {"pbp": 2}, "games_by_quality": {"ok": 2}}

    apply_exact_fields(entry, {"exact": exact})

    assert (entry["pace"], entry["possessions_per_game"], entry["oer"], entry["der"], entry["net_rating"]) == (5.0, 5.0, 300.0, 200.0, 100.0)
    assert entry["possessions_source"] == "pbp" and entry["games_by_quality"] == {"ok": 2}
    assert (entry["offensive_rebound_pct"], entry["defensive_rebound_pct"]) == (25.0, 75.0)


def test_entry_keeps_the_box_score_figures_without_exact_data():
    entry = base_possession_entry({"team_name": "Home", "possessions_per_game": 70.0, "offensive_rating": 100.0}, "H")

    apply_exact_fields(entry, {})
    apply_exact_fields(entry, None)

    assert entry["pace"] == 70.0 and "possessions_source" not in entry
