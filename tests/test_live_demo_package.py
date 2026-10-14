"""The package of the recorded Zamora-Leon demo is of the CURRENT schema (issue #315).

The demo is what the staff sees first: with an old package the new rules cannot fire (no roster: no illegal-lineup watch and no
formation card; no lineups; no own and conceded zones). Regenerate it whenever the package schema grows:
the one-off script is described in docs/LIVE.md (*Partido por defecto*).
"""
from collections import Counter
from pathlib import Path

import pytest

from src.live_core.package import PreparationPackage
from src.live_core.session import LiveSession

RECORDINGS = Path(__file__).parent / "recordings"
CODE = "2524470"


@pytest.fixture(scope="module")
def package():
    return PreparationPackage.loads((RECORDINGS / f"{CODE}.package.json").read_text(encoding="utf-8"))


def test_it_carries_the_roster_of_both_teams_with_the_formation_mark(package):
    roster = package.tables["roster"]
    teams = {row["team_id"] for row in roster.values()}
    assert {package.team["id"], package.rival["id"]} <= teams
    assert any(row.get("formacion") is True for row in roster.values())


def test_it_carries_lineups_and_all_four_zone_tables(package):
    assert package.tables["lineups"]
    assert set(package.tables["zones"]) >= {"league", "rival", "own", "rival_conceded"}


def test_it_carries_the_baselines_of_the_newer_rules(package):
    assert {"net_rtg_prior", "fg3_rate_own", "fg3_rate_rival", "ft_league_pct"} <= set(package.baselines)


@pytest.fixture(scope="module")
def played():
    session = LiveSession((RECORDINGS / f"{CODE}.package.json").read_text(encoding="utf-8"))
    session.load_recording((RECORDINGS / f"{CODE}.rec.json.gz").read_bytes())
    alerts, formation = [], []
    for t in range(0, 7200, 30):
        result = session.play(t)
        if result["output"]:
            alerts += result["output"]["alerts"]
            formation.append(result["output"]["analysis"].get("formation"))
    return alerts, formation


def test_the_match_shows_the_formation_status(played):
    _, formation = played
    seen = [f for f in formation if f]
    assert seen and all(f["known"] for f in seen) and seen[0]["min"] == 2


def test_the_match_raises_alerts_about_zones_and_lineups(played):
    alerts, _ = played
    ids = Counter(a["id"] for a in alerts)
    assert any(i.startswith("own_zone") or i in ("rival_zone", "paint_battle", "rival_defence_zones") for i in ids), dict(ids)
    assert ids["lineup_net"] >= 1, dict(ids)
