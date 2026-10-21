"""The demos of the teams of interest (issue #441): Cultural y Deportiva Leonesa, Llíria and CAJA RURAL RDL, made with ``demo_builder``.

Each is a recording the app replays as if it were live and the package its team would have had before the match. They must stay readable by the
CURRENT engine and package schema (regenerate them with ``python -m src.live_prep.demo_builder`` when the schema grows, like the Zamora-Leon demo).
"""
from pathlib import Path

import pytest

from src.live_core.package import PreparationPackage
from src.live_core.recorded_feed import RecordedFeed
from src.live_core.session import LiveSession

RECORDINGS = Path(__file__).parent / "recordings"
DEMOS = {      # code: (team id of interest, collection)
    "2536133": ("1008857", "SEGUNDA_FEB_2026_2027_Liga_Regular_A"),
    "2536311": ("1008978", "SEGUNDA_FEB_2026_2027_Liga_Regular_B"),
    "2536851": ("1010490", "TERCERA_FEB_2026_2027_Liga_Regular_A-B"),
}


def package(code):
    return PreparationPackage.loads((RECORDINGS / f"{code}.package.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("code", DEMOS)
def test_the_package_is_of_the_team_of_interest_in_its_competition(code):
    team, collection = DEMOS[code]
    p = package(code)
    assert p.team["id"] == team and p.collection == collection
    assert p.competition_meta["match"]["code"] == code


@pytest.mark.parametrize("code", DEMOS)
def test_the_package_has_history_and_the_current_schema(code):
    p = package(code)
    assert p.baselines["sample_games"]["own"] >= 1 and p.baselines["sample_games"]["league"] >= 5
    assert {"net_rtg_prior", "fg3_rate_own", "ft_league_pct"} <= set(p.baselines)
    assert p.tables["lineups"] and set(p.tables["zones"]) >= {"league", "rival", "own", "rival_conceded"}


@pytest.mark.parametrize("code", DEMOS)
def test_the_package_carries_the_roster_of_both_teams_with_the_formation_mark(code):
    p = package(code)
    roster = p.tables["roster"]
    assert {p.team["id"], p.rival["id"]} <= {row["team_id"] for row in roster.values()}
    assert any(row.get("formacion") is True for row in roster.values())


@pytest.mark.parametrize("code", DEMOS)
def test_the_recording_replays_through_the_session_to_the_final_score(code):
    session = LiveSession((RECORDINGS / f"{code}.package.json").read_text(encoding="utf-8"))
    session.load_recording((RECORDINGS / f"{code}.rec.json.gz").read_bytes())
    feed = RecordedFeed.load(RECORDINGS / f"{code}.rec.json.gz")
    last = None
    for t in range(0, int(feed.duration) + 30, 30):
        result = session.play(t)
        last = result["output"] or last
    assert last is not None and last["snapshot"]["elapsed"] > 2000
    final = feed.document_at(feed.duration)
    assert str(final["HEADER"]["status"]) == "3"


@pytest.mark.parametrize("code", DEMOS)
def test_each_demo_is_small_enough_to_ship_in_the_app(code):
    assert (RECORDINGS / f"{code}.rec.json.gz").stat().st_size < 60_000 and (RECORDINGS / f"{code}.package.json").stat().st_size < 60_000


FBCYL_DEMO = ("264803", "39609")      # Universidad de León (UNILEON B.F.LEÓN), 1ª División Femenina grupo A-1 (issue #445)


def test_the_fbcyl_demo_is_the_package_of_unileon_marked_as_experimental():
    p = package(FBCYL_DEMO[0])
    assert p.team["id"] == FBCYL_DEMO[1] and "UNILEON" in p.team["name"].upper()
    assert p.collection.startswith("FBCYL_") and p.competition_meta["data_quality"] == "experimental"
    assert p.baselines["sample_games"]["own"] >= 1 and p.tables["players"] and p.tables["rival_players"]
    assert "roster" not in p.tables           # FBCYL has no "formación" roster: the formation rule stays off


def test_the_fbcyl_demo_replays_through_the_session_to_the_final_score():
    code = FBCYL_DEMO[0]
    session = LiveSession((RECORDINGS / f"{code}.package.json").read_text(encoding="utf-8"))
    session.load_recording((RECORDINGS / f"{code}.rec.json.gz").read_bytes())
    feed = RecordedFeed.load(RECORDINGS / f"{code}.rec.json.gz")
    last = None
    for t in range(0, int(feed.duration) + 30, 30):
        last = session.play(t)["output"] or last
    assert last["snapshot"]["elapsed"] >= 2400 and last["snapshot"]["score"] == {"40083": 45, "39609": 59}
    assert str(feed.document_at(feed.duration)["HEADER"]["status"]) == "3"
    assert (RECORDINGS / f"{code}.rec.json.gz").stat().st_size < 60_000
