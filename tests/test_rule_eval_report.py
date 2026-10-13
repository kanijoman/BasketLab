"""The report of the rule evaluator and its command line (issue #238)."""
import json

import pytest

from src.live_prep.eval_report import build_report
from src.live_prep.rule_evaluation import Evaluation, main

OWN = "T1"


def row(rule="fatigue_high", config="base", game="G1", e=100, key=None, label=None, delay=None, severity="warning", **extra):
    return {"game": game, "team": OWN, "rival": "T2", "config": config, "prior": 4, "id": rule, "key": key or f"{rule}:{e}",
            "severity": severity, "category": "rotacion", "message": "m", "elapsed": e, "shown": e + 30, "evidence": {"player_id": "p1"},
            "proposal": [], "label": label, "delay": delay, "action_at": None,
            "outcome": {"net_before": 0, "net_after": 2, "net_delta": 2, "measure": None}, **extra}


def evaluation(extra_rows=()):
    rows = [row(label="seguida", delay=40), row(e=900, key="b", label="no"),
            row("rival_run", severity="critical", label="seguida", delay=20),
            row(config="sin_fatiga", game="G1", key="x", e=400)] + list(extra_rows)
    games = [{"game": "G1", "team": OWN, "rival": "T2", "prior": 4, "duration_s": 2400, "timing": "game_clock",
              "polls": 300, "timeouts": [140]}]
    coach = [{"timeouts": [{"team": OWN, "elapsed": 140, "opp_150": 9, "own_150": 0, "own_tov_300": 4}],
              "stints": [{"team": OWN, "stint_s": 300, "period": 1}], "foul_cases": [{"pf": 3, "period": 4, "subbed_120": False}],
              "droughts": [{"team": OWN, "start": 0, "length": 300, "timeout": True}]}]
    simulation = [{"spec": "8 sin respuesta en 150 s", "fires": 1, "per_team_game": 0.5, "followed": 1.0, "covered": 0.5}]
    return Evaluation(rows=rows, team_games=games, coach=coach, simulation=simulation, configs=["base", "sin_fatiga"],
                      params={"latency_s": 40, "poll_s": 10, "min_prior_games": 3, "follow_s": 120, "games": 1, "team": None})


def test_the_report_has_the_numbers_of_each_rule_in_spanish():
    data, text = build_report(evaluation())
    assert text.startswith("# Evaluación de reglas del motor live")
    assert "1 partido" in text and "1 equipo-partido" in text
    assert "Configuración «base»" in text and "fatigue_high" in text and "rival_run" in text
    assert "Duplicados" in text and "Cobertura" in text
    assert data["metrics"]["base"]["fatigue_high"]["alerts"] == 2
    assert data["metrics"]["base"]["all"]["alerts"] == 3


def test_the_other_configurations_are_compared_with_the_baseline():
    data, text = build_report(evaluation())
    assert "Comparación con la línea base" in text and "sin_fatiga" in text
    assert data["metrics"]["sin_fatiga"]["fatigue_high"]["alerts"] == 1


def test_coach_behaviour_and_the_run_simulation_are_in_the_report():
    data, text = build_report(evaluation())
    assert "Comportamiento de los entrenadores" in text and "Simulación del parcial rival" in text
    assert "8 sin respuesta en 150 s" in text
    assert data["coach"]["timeouts"]["total"] == 1 and data["simulation"][0]["fires"] == 1
    assert "5:00" in text   # the voluntary stint, as minutes:seconds


def test_the_staff_answers_have_their_own_table_only_when_there_is_feedback():
    assert "Respuesta del staff" not in build_report(evaluation())[1]
    fed = evaluation([row(e=2000, key="c", feedback=True, verdict="seguida")])
    _, text = build_report(fed)
    assert "Respuesta del staff" in text and "obediencia" in text.lower()


def test_an_empty_evaluation_still_gives_a_report():
    data, text = build_report(Evaluation(configs=["base"], params={"games": 0, "follow_s": 120}))
    assert "Sin alertas" in text and data["metrics"]["base"]["all"]["alerts"] == 0


# --- the command line --------------------------------------------------------------------

@pytest.fixture()
def games_dir(tmp_path, feb_game_doc):
    folder = tmp_path / "games"
    folder.mkdir()
    for code, start in (("G0", "01-10-2025 - 12:00"), ("G1", "05-10-2025 - 12:30")):
        doc = json.loads(json.dumps(feb_game_doc))
        doc["_id"], doc["HEADER"]["starttime"] = code, start
        (folder / f"{code}.json").write_text(json.dumps(doc), encoding="utf-8")
    return folder


def test_the_command_line_writes_the_three_outputs(games_dir, tmp_path, capsys):
    out = tmp_path / "out"
    assert main(["--games-dir", str(games_dir), "--out", str(out), "--min-prior-games", "0"]) == 0
    data = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    lines = [json.loads(l) for l in (out / "alerts.jsonl").read_text(encoding="utf-8").splitlines()]
    report = (out / "report.md").read_text(encoding="utf-8")
    assert data["params"]["games"] == 2 and "base" in data["metrics"]
    assert lines and all({"game", "id", "label", "outcome"} <= set(l) for l in lines)
    assert report.startswith("# Evaluación") and report in capsys.readouterr().out


def test_a_second_configuration_file_is_compared_with_the_stock_one(games_dir, tmp_path):
    cfg = tmp_path / "sin_faltas.json"
    cfg.write_text(json.dumps({"rules_off": ["foul_trouble"]}), encoding="utf-8")
    named = tmp_path / "otra.json"
    named.write_text(json.dumps({"name": "umbral", "rule_config": {"run_points": 6}}), encoding="utf-8")
    out = tmp_path / "out"
    assert main(["--games-dir", str(games_dir), "--out", str(out), "--min-prior-games", "0",
                 "--config", str(cfg), "--config", str(named)]) == 0
    data = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))
    assert list(data["metrics"]) == ["base", "sin_faltas", "umbral"]


def test_a_typo_in_a_configuration_stops_the_run_with_a_clear_message(games_dir, tmp_path, capsys):
    cfg = tmp_path / "bad.json"
    cfg.write_text(json.dumps({"rules_off": ["rival_runn"]}), encoding="utf-8")
    assert main(["--games-dir", str(games_dir), "--out", str(tmp_path / "o"), "--config", str(cfg)]) == 2
    assert "rival_runn" in capsys.readouterr().err
    assert not (tmp_path / "o").exists()


def test_two_configurations_cannot_share_a_name(games_dir, tmp_path, capsys):
    cfg = tmp_path / "base.json"
    cfg.write_text("{}", encoding="utf-8")
    assert main(["--games-dir", str(games_dir), "--out", str(tmp_path / "o"), "--config", str(cfg)]) == 2
    assert "base" in capsys.readouterr().err


def test_a_source_is_required_and_only_one(tmp_path, games_dir, capsys):
    with pytest.raises(SystemExit):
        main(["--out", str(tmp_path / "o")])
    with pytest.raises(SystemExit):
        main(["--games-dir", str(games_dir), "--collection", "FEB_X", "--out", str(tmp_path / "o")])


def test_the_report_is_added_to_the_github_step_summary(games_dir, tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["--games-dir", str(games_dir), "--out", str(tmp_path / "o"), "--min-prior-games", "0"]) == 0
    assert summary.read_text(encoding="utf-8").startswith("# Evaluación")


def test_the_staff_feedback_files_are_joined_and_unmatched_entries_reported(games_dir, tmp_path, capsys):
    fb = tmp_path / "fb.json"
    fb.write_text(json.dumps({"context": "live:G1", "entries": [{"key": "no-such-key", "verdict": "seguida"}]}), encoding="utf-8")
    out = tmp_path / "out"
    assert main(["--games-dir", str(games_dir), "--out", str(out), "--min-prior-games", "0", "--feedback", str(fb)]) == 0
    assert "1 entradas de feedback sin alerta" in capsys.readouterr().err
    assert "Respuesta del staff" in (out / "report.md").read_text(encoding="utf-8")
