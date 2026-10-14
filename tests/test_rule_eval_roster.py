"""The rule evaluator with the FEB roster (issue #278): the illegal-lineup rule (#272) needs to know who is a "formación" player,
so without a roster it does nothing in the evaluator's packages and its false alarms cannot be measured.

The roster is the CURRENT one (an approximation that is valid for the season in progress), given as a table (``--roster-file``)
or asked of FEB once per team (``--roster``).
"""
import json

import pytest

from src.live_prep.eval_report import build_report
from src.live_prep.rule_evaluation import ConfigSpec, evaluate, main
from tests.test_rule_evaluation import A, B, C, dated, remap

FORMATION = "formation_lineup"


@pytest.fixture(scope="module")
def season(feb_game_doc):
    return [dated(feb_game_doc, "G0", "01-10-2025 - 12:00"), dated(feb_game_doc, "G1", "05-10-2025 - 12:30"),
            dated(remap(feb_game_doc, {B: C}), "G2", "10-10-2025 - 12:00")]


def roster_of(doc, formacion):
    """A roster table from the box score of a game: ``formacion(player_id, team_id)`` says who is a "formación" player."""
    return {p["id"]: {"team_id": t["id"], "name": p["name"], "formacion": formacion(p["id"], t["id"])}
            for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"]}


def formation_rows(ev, config="base"):
    return [r for r in ev.rows if r["id"] == FORMATION and r["config"] == config]


def test_without_a_roster_the_illegal_lineup_rule_does_nothing(season):
    assert not formation_rows(evaluate(season))


def test_with_a_roster_without_formacion_players_the_rule_fires_for_the_sides_that_have_it(season, feb_game_doc):
    ev = evaluate(season, roster=roster_of(feb_game_doc, lambda pid, tid: False))
    rows = formation_rows(ev)
    assert rows and {r["team"] for r in rows} <= {A, B}
    assert all(r["severity"] == "critical" and r["category"] == "alineacion" for r in rows)


def test_with_enough_formacion_players_it_is_quiet(season, feb_game_doc):
    assert not formation_rows(evaluate(season, roster=roster_of(feb_game_doc, lambda pid, tid: True)))


def test_other_minimums_are_compared_through_the_configurations(season, feb_game_doc):
    configs = [ConfigSpec("base"), ConfigSpec("sin_regla", {"formation_min_on_court": 0}), ConfigSpec("tres", {"formation_min_on_court": 3})]
    ev = evaluate(season, configs=configs, roster=roster_of(feb_game_doc, lambda pid, tid: False))
    assert formation_rows(ev) and not formation_rows(ev, "sin_regla") and len(formation_rows(ev, "tres")) >= len(formation_rows(ev))
    assert ev.params["formation_min"] == {"base": 2, "sin_regla": 0, "tres": 3}


def test_a_side_only_gets_the_players_of_its_own_game(season, feb_game_doc):
    table = roster_of(feb_game_doc, lambda pid, tid: False)
    table["999"] = {"team_id": "000000", "name": "Otra", "formacion": True}          # a player of a team that never plays
    ev = evaluate(season, roster=table)
    assert formation_rows(ev) and ev.params["roster"] == {"players": len(table) - 1, "teams": 2}      # the rosters that were served to a package


def test_the_roster_can_be_asked_lazily_once_per_team_and_a_failure_leaves_the_rule_off(season, feb_game_doc):
    table, calls = roster_of(feb_game_doc, lambda pid, tid: False), []

    def source(team_id):
        calls.append(team_id)
        return {pid: e for pid, e in table.items() if e["team_id"] == team_id}

    ev = evaluate(season, roster_source=source)
    assert sorted(calls) == sorted(set(calls)) and set(calls) <= {A, B, C} and formation_rows(ev)
    assert not formation_rows(evaluate(season, roster_source=lambda team_id: None))


def test_the_report_says_how_many_alerts_and_which_sides_and_that_the_roster_is_the_current_one(season, feb_game_doc):
    configs = [ConfigSpec("base"), ConfigSpec("sin_regla", {"formation_min_on_court": 0})]
    ev = evaluate(season, configs=configs, roster=roster_of(feb_game_doc, lambda pid, tid: False))
    data, text = build_report(ev)
    assert "Alineación indebida" in text and "plantilla actual" in text and "formation_lineup" in text
    assert data["formation"]["base"]["alerts"] == len(formation_rows(ev)) > 0
    assert data["formation"]["base"]["min_on_court"] == 2 and data["formation"]["sin_regla"]["alerts"] == 0
    assert 0 < data["formation"]["base"]["sides"] <= len(ev.team_games)


def test_without_a_roster_the_report_says_the_rule_is_off(season):
    data, text = build_report(evaluate(season))
    assert "Sin plantilla" in text and "--roster" in text and data["formation"] is None


# --- the command line ---------------------------------------------------------------------------------------------------

@pytest.fixture()
def games_dir(tmp_path, season):
    folder = tmp_path / "games"
    folder.mkdir()
    for game in season:
        (folder / f"{game['_id']}.json").write_text(json.dumps(game), encoding="utf-8")
    return folder


def test_a_roster_file_gives_the_roster_without_network(games_dir, tmp_path, feb_game_doc):
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps(roster_of(feb_game_doc, lambda pid, tid: False)), encoding="utf-8")
    out = tmp_path / "out"
    assert main(["--games-dir", str(games_dir), "--roster-file", str(roster), "--out", str(out), "--min-prior-games", "0"]) == 0
    data = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    assert data["formation"]["base"]["alerts"] > 0 and "Alineación indebida" in (out / "report.md").read_text(encoding="utf-8")


def test_roster_asks_feb_once_per_team_and_keeps_going_if_one_fails(games_dir, tmp_path, feb_game_doc, monkeypatch):
    table, asked = roster_of(feb_game_doc, lambda pid, tid: False), []

    def fake(team_id, *args, **kwargs):
        asked.append(str(team_id))
        return None if str(team_id) == C else {pid: e for pid, e in table.items() if e["team_id"] == str(team_id)}

    monkeypatch.setattr("src.live_prep.roster_fetcher.fetch_team_roster", fake)
    out = tmp_path / "out"
    assert main(["--games-dir", str(games_dir), "--roster", "--out", str(out), "--min-prior-games", "0"]) == 0
    assert sorted(asked) == sorted(set(asked)) and set(asked) <= {A, B, C}
    assert json.loads((out / "evaluation.json").read_text(encoding="utf-8"))["formation"]["base"]["alerts"] > 0


@pytest.mark.parametrize("content", ["[1, 2]", '{"1": {"name": "sin equipo"}}', "no es json"])
def test_a_roster_file_that_is_not_a_roster_stops_the_run_with_a_clear_message(games_dir, tmp_path, content, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(content, encoding="utf-8")
    assert main(["--games-dir", str(games_dir), "--roster-file", str(bad), "--out", str(tmp_path / "o")]) == 2
    assert "roster" in capsys.readouterr().err.lower() and not (tmp_path / "o").exists()
