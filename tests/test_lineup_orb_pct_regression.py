"""ORB% of a combination over several games (#691).

Bug: ``_merge_lineup_stats`` summed the counters of each game and recomputed ORtg, DRtg, eFG%, FTr and TOV%, but not ORB%: a combination that had played several games showed
the ORB% of its FIRST game, and the table sorted by ORB% with it. ORB% = ORB / (ORB + opponent DRB) over the totals, so the opponent's defensive rebounds are summed too.
Built with the real sample games (FEB's and FBCYL's), cut after different periods so that the games of a combination differ.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from lineup_games import Repo, sample_games, team_of  # noqa: E402
from src.services.lineup_service import LineupService  # noqa: E402

PLAN = [{"day": "2025-10-05", "periods": 4}, {"day": "2025-10-12", "periods": 3}, {"day": "2025-10-19", "periods": 2}, {"day": "2025-10-26", "periods": 1}]


def _rows(kind, size):
    games = sample_games(kind, PLAN)
    repo = Repo(games, [{"id": team_of(kind, games), "name": "Team A"}], kind == "fbcyl")
    name = "L_F_-2_2025_2026_Liga_Regular_B" if kind == "feb" else "FBCYL_1ª_FASE-GRUPO_A-1_2026_"
    return LineupService(repo).get_lineup_analysis(name, repo.teams[0]["id"], "Team A", size, min_minutes=0, min_games=0, include_game_log=True)


@pytest.mark.parametrize("kind", ["feb", "fbcyl"])
@pytest.mark.parametrize("size", [2, 5])
def test_the_orb_pct_of_a_combination_is_over_the_totals_of_all_its_games_regression(kind, size):
    several = [r for r in _rows(kind, size) if r["games_played"] > 1]
    assert several, "the fixture has combinations that played several games"
    for row in several:
        chances = row["orb"] + row["opp_drb"]
        assert row["orb_pct"] == (round(row["orb"] / chances * 100, 1) if chances else row["orb_pct"])


def test_the_fixture_has_a_combination_whose_total_is_not_its_first_games_figure():
    """Teeth of the test above: with the bug every combination showed the first game's figure. FEB only: the sample FBCYL game has no rebounds in its lineups (0 of 0)."""
    rows = [r for r in _rows("feb", 2) if r["games_played"] > 1]
    assert any(r["orb_pct"] != r["game_log"][0]["orb_pct"] for r in rows)
