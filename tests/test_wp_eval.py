"""Calibration of the win probability on finished games (issue #255)."""

import pytest

from src.live_core.config import RuleConfig
from src.live_prep.wp_eval import VARIANTS, collect_samples, compare, grid_search, score_samples


@pytest.fixture()
def samples(feb_game_doc):
    return collect_samples([feb_game_doc], cut_s=300, min_prior_games=0)


def test_one_sample_per_side_and_cut_of_the_game(samples):
    assert samples
    assert len({s["team"] for s in samples}) == 2
    cuts = sorted({s["cut"] for s in samples})
    assert cuts[0] == 300 and all(c % 300 == 0 for c in cuts) and cuts[-1] < 2400
    assert len([s for s in samples if s["team"] == samples[0]["team"]]) == len(cuts)


def test_the_outcome_is_the_final_score_seen_from_each_side(samples):
    a, b = (next(s for s in samples if s["team"] == t) for t in sorted({s["team"] for s in samples}))
    assert a["final_margin"] == -b["final_margin"]
    assert a["won"] == (a["final_margin"] > 0)
    assert all(s["snap"]["elapsed"] >= s["cut"] for s in samples)


def test_games_with_too_few_earlier_games_are_skipped(feb_game_doc):
    assert collect_samples([feb_game_doc], cut_s=300, min_prior_games=3) == []


def test_the_prior_only_sees_earlier_games(feb_game_doc):
    import copy

    first_doc, later = copy.deepcopy(feb_game_doc), copy.deepcopy(feb_game_doc)
    first_doc["HEADER"]["starttime"], later["HEADER"]["starttime"] = "10-10-2026 - 17:00", "17-10-2026 - 17:00"
    two = collect_samples([first_doc, later], cut_s=300, min_prior_games=0)
    first = [s for s in two if s["index"] == 0]
    second = [s for s in two if s["index"] == 1]
    assert all("net_rtg_prior" in s["baselines"] for s in first + second)
    assert all(s["baselines"]["net_rtg_prior"] == 0.0 for s in first)
    assert any(s["baselines"]["net_rtg_prior"] != 0.0 for s in second)


def test_score_gives_every_metric_for_each_variant(samples):
    assert set(VARIANTS) == {"full", "prior_only", "score_time"}
    for variant in VARIANTS:
        out = score_samples(samples, RuleConfig(), variant)
        assert set(out) >= {"n", "brier", "log_loss", "mae", "reliability", "max_gap"}
        assert out["n"] == len(samples) and 0 <= out["brier"] <= 1


def test_score_time_ignores_everything_but_score_and_clock(samples):
    base = score_samples(samples, RuleConfig(), "score_time")
    shifted = [{**s, "baselines": {**s["baselines"], "net_rtg_prior": 50.0}} for s in samples]
    assert score_samples(shifted, RuleConfig(), "score_time") == base
    assert score_samples(shifted, RuleConfig(), "prior_only") != score_samples(samples, RuleConfig(), "prior_only")


def test_grid_search_ranks_by_log_loss_and_reports_every_combination(samples):
    ranked = grid_search(samples, {"wp_sigma": [8.0, 12.0], "wp_n0": [30.0, 60.0]})
    assert len(ranked) == 4
    assert [r["log_loss"] for r in ranked] == sorted(r["log_loss"] for r in ranked)
    assert set(ranked[0]["params"]) == {"wp_sigma", "wp_n0"}


def test_compare_lists_the_variants_with_the_default_config(samples):
    assert set(compare(samples, RuleConfig())) == set(VARIANTS)


def test_report_says_whether_the_app_criterion_is_met_and_lists_the_deciles(samples):
    from src.live_prep.wp_cli import build_report

    cfg = RuleConfig()
    text = build_report(compare(samples, cfg), grid_search(samples, {"wp_sigma": [10.0, 12.0]}), samples, cfg)
    assert "Solo marcador y tiempo" in text and "Solo valor previo" in text
    assert "Criterio para mostrarla en la app" in text and ("cumplido" in text)
    assert "Fiabilidad del modelo completo" in text and "`wp_sigma=12.0`" in text


def test_cli_needs_enough_earlier_games(tmp_path, feb_game_doc, capsys):
    import json

    from src.live_prep.wp_cli import main

    (tmp_path / "g.json").write_text(json.dumps(feb_game_doc), encoding="utf-8")
    assert main(["--games-dir", str(tmp_path)]) == 2
    assert "suficientes partidos previos" in capsys.readouterr().err
    out = tmp_path / "r.md"
    assert main(["--games-dir", str(tmp_path), "--min-prior-games", "0", "--out", str(out)]) == 0
    assert "Calibración de la probabilidad de victoria" in out.read_text(encoding="utf-8")


def test_cli_pools_several_season_folders_without_mixing_their_priors(tmp_path, feb_game_doc, capsys):
    """#301: each folder is a season (its own accumulator); the samples of all of them are scored together."""
    import json

    from src.live_prep.wp_cli import main

    for season in ("2024", "2025"):
        (tmp_path / season).mkdir()
        (tmp_path / season / "g.json").write_text(json.dumps(feb_game_doc), encoding="utf-8")
    assert main(["--games-dir", str(tmp_path / "2024"), "--games-dir", str(tmp_path / "2025"), "--min-prior-games", "0"]) == 0
    one = capsys.readouterr().out.split(" cortes de ")[0].split()[-1]
    assert main(["--games-dir", str(tmp_path / "2025"), "--min-prior-games", "0"]) == 0
    single = capsys.readouterr().out.split(" cortes de ")[0].split()[-1]
    assert int(one) == 2 * int(single)


def test_a_held_out_season_checks_the_parameters_tuned_on_the_others(tmp_path, feb_game_doc, capsys):
    """#301: ``--validate-dir`` scores the default and the best parameters of the grid on a season that was not used to tune."""
    import json

    from src.live_prep.wp_cli import main

    for season in ("2024", "2025"):
        (tmp_path / season).mkdir()
        (tmp_path / season / "g.json").write_text(json.dumps(feb_game_doc), encoding="utf-8")
    out = tmp_path / "r.md"
    assert main(["--games-dir", str(tmp_path / "2024"), "--validate-dir", str(tmp_path / "2025"),
                 "--min-prior-games", "0", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "## Validación en una temporada aparte" in text
    assert "Parámetros por defecto" in text and "Parámetros ajustados" in text and "wp_sigma" in text


def test_a_game_the_engine_cannot_score_is_left_out(feb_game_doc):
    """Old seasons write the points in another way (``(13 Pts)``): the engine reads 0-0 and every forecast would be a lie."""
    import copy

    unreadable = copy.deepcopy(feb_game_doc)
    lines = unreadable["PLAYBYPLAY"]["LINES"]
    unreadable["PLAYBYPLAY"]["LINES"] = [l for l in lines if "ANOTADO" not in (l.get("text") or "").upper()]
    assert collect_samples([unreadable], cut_s=300, min_prior_games=0) == []
    assert collect_samples([feb_game_doc], cut_s=300, min_prior_games=0)

# -- the criterion to show the probability in the app (agreed with the user on 2026-10-14, issue #255) -------------

def _variant(log_loss, rows):
    return {"log_loss": log_loss, "reliability": rows}


def _bins(gap_points, n=500):
    return [{"bin": 3, "n": n, "mean_p": 0.35, "freq": 0.35 + gap_points / 100}]


def test_criterion_met_when_it_beats_score_and_time_stays_with_the_prior_and_deciles_are_close():
    from src.live_prep.wp_eval import app_criterion

    result = app_criterion({"full": _variant(0.370, _bins(4.0)), "prior_only": _variant(0.368, []), "score_time": _variant(0.420, [])})
    assert result["met"] is True and result["gap"] == pytest.approx(4.0)


def test_criterion_allows_a_log_loss_up_to_half_a_thousandth_worse_than_the_prior_but_not_more():
    from src.live_prep.wp_eval import app_criterion

    def met(full):
        return app_criterion({"full": _variant(full, _bins(1.0)), "prior_only": _variant(0.368, []), "score_time": _variant(0.420, [])})["met"]

    assert met(0.3729) is True and met(0.3731) is False


def test_criterion_fails_if_it_does_not_beat_score_and_time_or_the_deciles_are_far():
    from src.live_prep.wp_eval import app_criterion

    assert app_criterion({"full": _variant(0.430, _bins(1.0)), "prior_only": _variant(0.368, []), "score_time": _variant(0.420, [])})["met"] is False
    assert app_criterion({"full": _variant(0.370, _bins(6.4)), "prior_only": _variant(0.368, []), "score_time": _variant(0.420, [])})["met"] is False


def test_criterion_ignores_deciles_with_fewer_than_400_cuts_and_fails_without_any():
    from src.live_prep.wp_eval import app_criterion

    base = {"prior_only": _variant(0.368, []), "score_time": _variant(0.420, [])}
    assert app_criterion({"full": _variant(0.370, _bins(9.0, n=399)), **base})["met"] is False   # no decile is trustworthy: not shown
    mixed = _bins(9.0, n=399) + [{"bin": 8, "n": 800, "mean_p": 0.85, "freq": 0.86}]
    assert app_criterion({"full": _variant(0.370, mixed), **base})["gap"] == pytest.approx(1.0)


def test_the_validation_section_applies_the_agreed_criterion_to_the_held_out_season(tmp_path, feb_game_doc):
    """#261: the held-out season is judged with the same criterion (not with the noisy deciles of a handful of cuts)."""
    import json

    from src.live_prep.wp_cli import main

    for season in ("2024", "2025"):
        (tmp_path / season).mkdir()
        (tmp_path / season / "g.json").write_text(json.dumps(feb_game_doc), encoding="utf-8")
    out = tmp_path / "r.md"
    assert main(["--games-dir", str(tmp_path / "2024"), "--validate-dir", str(tmp_path / "2025"),
                 "--min-prior-games", "0", "--out", str(out)]) == 0
    section = out.read_text(encoding="utf-8").split("## Validación en una temporada aparte")[1]
    assert "Criterio en la validación" in section and ("Cumplido" in section or "NO cumplido" in section)
