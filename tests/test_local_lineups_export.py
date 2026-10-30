"""The lineups ("Combinaciones") of a competition, published for the web (#686): the raw counters of every combination in every game of each team, so that the browser merges
them as the service does (size, statistic, period, minimums and last game) with the figures of the API.

Built with the real sample games (FEB's and FBCYL's, with their play-by-play) played on different days: the service and the exporter read them the same way.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

from lineup_games import FBCYL, FEB, Repo, sample_games, team_of  # noqa: E402
from src.local_data.export import FORMAT  # noqa: E402
from src.local_data.lineups_export import COLUMNS, SIZES, export_lineups, game_at  # noqa: E402
from src.services.lineup_service import LineupService  # noqa: E402


def _repo(kind, days=(5, 12, 19)):
    games = sample_games(kind, [{"day": f"2025-10-{day:02d}"} for day in days])
    return Repo(games, [{"id": team_of(kind, games), "name": "Team A"}], kind == "fbcyl"), FEB if kind == "feb" else FBCYL


def _published(repo, name):
    payload = export_lineups(repo, name)
    return payload, payload["teams"][0]


@pytest.mark.parametrize("kind", ["feb", "fbcyl"])
def test_each_game_counter_adds_up_to_what_the_service_answers_regression(kind):
    """Bug it prevents: a published table whose sums do not give the API's lineup (minutes, possessions, points or any counter)."""
    repo, name = _repo(kind)
    payload, team = _published(repo, name)
    assert (payload["format"], payload["league"], payload["collection"]) == (FORMAT, kind, name)
    column = {c: i for i, c in enumerate(COLUMNS)}
    service = LineupService(repo)
    seen = 0
    for size in SIZES:
        api = {frozenset(r["player_ids"]): r for r in service.get_lineup_analysis(name, repo.teams[0]["id"], "Team A", size, min_minutes=0, min_games=0)}
        published = {frozenset(ids): rows for ids, rows in team["sizes"][str(size)]}
        assert set(published) == set(api)
        for key, rows in published.items():
            row = api[key]
            assert len(rows) == row["games_played"]
            assert sum(r[column["points_for"]] for r in rows) == row["points_for"]
            assert sum(r[column["points_against"]] for r in rows) == row["points_against"]
            assert sum(r[column["fga"]] for r in rows) == row["fga"] and sum(r[column["tov"]] for r in rows) == row["tov"]
            assert round(sum(r[column["minutes"]] for r in rows), 6) == round(row["minutes"], 6)
            assert round(sum(r[column["possessions"]] for r in rows), 6) == round(row["possessions"], 6)
            assert sum(r[column["segments"]] for r in rows) == row["segments_count"]
            seen += 1
    assert seen > 0


@pytest.mark.parametrize("kind", ["feb", "fbcyl"])
def test_games_are_listed_in_the_order_of_the_service_with_their_day_and_instant(kind):
    repo, name = _repo(kind, days=(19, 5, 12))                                                  # not in date order: the order of the collection is kept
    _, team = _published(repo, name)
    assert [g["date"][-2:] if kind == "fbcyl" else g["date"][:2] for g in team["games"]] == ["19", "05", "12"]
    assert [g["at"] for g in team["games"]] == [f"2025-10-{d:02d}T{'12:30' if kind == 'feb' else '18:00'}:00" for d in (19, 5, 12)]
    assert all(row[0] in (0, 1, 2) for rows in team["sizes"]["5"] for _, group in [rows] for row in group)


@pytest.mark.parametrize("kind", ["feb", "fbcyl"])
def test_the_file_is_deterministic_and_the_players_are_sorted_with_their_names(kind):
    repo, name = _repo(kind)
    first, second = export_lineups(repo, name), export_lineups(repo, name)
    assert json.dumps(first, sort_keys=False) == json.dumps(second, sort_keys=False)
    team = first["teams"][0]
    for size in SIZES:
        for ids, _ in team["sizes"][str(size)]:
            assert ids == sorted(ids) and len(ids) == size and all(i in team["players"] for i in ids)
    assert all(name_photo[0].startswith("Name ") for name_photo in team["players"].values())


def test_a_game_that_fails_is_skipped_but_still_counted_among_the_games():
    repo, name = _repo("feb")
    repo.games[1]["PLAYBYPLAY"] = "broken"
    _, team = _published(repo, name)
    assert len(team["games"]) == 3
    assert {row[0] for rows in team["sizes"]["5"] for _, group in [rows] for row in group} <= {0, 2}


@pytest.mark.parametrize("text, expected", [
    ("05-10-2025 - 12:30", "2025-10-05T12:30:00"), ("", None), (None, None), ("not a date", None),
])
def test_feb_game_instant_is_read_as_mongo_reads_it(text, expected):
    assert game_at(text, fbcyl=False) == expected


@pytest.mark.parametrize("text, expected", [
    ("Oct 3, 2026, 6:30:00\u202fPM", "2026-10-03T18:30:00"), ("Oct 4, 2025 7:00:00 PM", "2025-10-04T19:00:00"), ("Oct 4, 2025 12:05:00 AM", "2025-10-04T00:05:00"),
    ("Oct 4, 2025 12:05:00 PM", "2025-10-04T12:05:00"), ("", None), ("x", None),
])
def test_fbcyl_game_instant_has_the_hour_of_both_formats(text, expected):
    assert game_at(text, fbcyl=True) == expected


def test_a_team_with_no_play_by_play_is_not_published():
    repo, name = _repo("feb")
    repo.games = []
    assert export_lineups(repo, name)["teams"] == []
