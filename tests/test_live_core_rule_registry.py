"""Rule registry and the per-rule switch (issue #236).

Every rule has an id; ``RuleConfig.rules_off`` (a package ``rule_config`` entry) turns rules off without a new app
build and lets the evaluator compare configurations. Nothing is off by default and the stock behaviour must not change.
"""
import json
from pathlib import Path

import pytest

from src.live_core.advice import RULES, AdviceEngine
from src.live_core.config import RULE_IDS, RuleConfig, unknown_rule_ids
from tests.test_live_core_advice import BASE, OWN, RIVAL, _player, _stats, ff_snap, snap
from tests.test_live_core_rival_alerts import BASELINES as RIVAL_BASELINES, rival_snap
from tests.test_live_core_players import basket as pl_basket, impact as pl_impact, pl_snap, player as pl_player
from tests.test_live_core_closing import end_of as cl_end_of, finish as cl_finish, pace_snap as cl_pace_snap, pts as cl_pts
from tests.test_live_core_sanctions import player as sa_player, snapshot as sa_evaluate_snap
from tests.test_live_core_streaks import free_throws, shots
from tests.test_live_core_rest import TABLE as REST_TABLE, decided as rest_decided
from tests.test_live_core_rival_zones import zsnap

EXPECTED_IDS = ("foul_trouble", "rival_foul_trouble", "formation_lineup", "team_fouls", "rival_run", "turnover_streak",
                "fatigue_high", "four_factors_lever", "rival_hot_player", "rival_zone", "rest_starters",
                "cold_shooting", "rival_hot_shooting", "free_throw_cold",
                "scoring_drought", "long_run", "game_flow_windows",
                "rival_player_form", "own_player_form", "rival_star_bench",
                "disqualification", "timeout_budget", "key_fouls_close", "rival_foul_pair",
                "closing_briefing", "period_summary", "advantage_management", "pace_control")


def _engine(rules_off=(), **kw):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, config=RuleConfig(rules_off=tuple(rules_off)), **kw)


def _fouls():
    players = {"p1": _player("Ana", OWN, pf=3), "r1": _player("Rival Uno", RIVAL, pf=3)}
    # both teams scored a minute ago: a game with no scoring at all would (rightly) raise the drought alerts
    log = [[500, team, kind, value, "p1"] for team in (OWN, RIVAL) for kind, value in (("fg2", 1), ("pts", 2))]
    return in_play(snap(period=3, players=players, log=log))


def _bonus():
    return snap(period=2, fouls_by_period={OWN: {"2": 4}, RIVAL: {"2": 4}})


def in_play(snapshot):
    """The default test snapshot has the clock at 0:00 (the end of a period, when the period summary is said): mid-period here."""
    snapshot["remaining"] = 300
    return snapshot


def _run():
    return in_play(snap(elapsed=1110, log=[[880, OWN, "fg2", 1, "p1"], [880, OWN, "pts", 2, "p1"],   # our last basket, before the run window
                               [1000, RIVAL, "pts", 3], [1040, RIVAL, "pts", 2], [1100, RIVAL, "pts", 3]]))


def _turnovers():
    return snap(elapsed=1100, log=[[1000 + 10 * i, OWN, "tov", 1] for i in range(4)])


def _fatigue():
    return snap(elapsed=1200, players={"p1": _player("Ana", OWN, stint=720, minutes=1100)})


def _zone():
    s = zsnap({"left_corner_three": {"a": 8, "m": 6, "pts": 18}})
    return s


def _formation():
    players = {f"f{i}": _player(f"Jug {i}", OWN) for i in range(1, 6)}
    return snap(period=3, players=players)


FORMATION_ROSTER = {f"f{i}": {"team_id": OWN, "formacion": False} for i in range(1, 6)}

# rule id -> (builder of a snapshot where it fires, advice ids it emits, extra engine kwargs)
SCENARIOS = {
    "foul_trouble": (_fouls, {"foul_trouble"}, {}),
    "rival_foul_trouble": (_fouls, {"rival_foul_trouble"}, {}),
    "formation_lineup": (_formation, {"formation_lineup"}, {"roster": FORMATION_ROSTER}),
    "team_fouls": (_bonus, {"team_fouls_bonus", "rival_near_bonus"}, {}),
    "rival_run": (_run, {"rival_run"}, {}),
    "turnover_streak": (_turnovers, {"turnover_streak"}, {}),
    "fatigue_high": (_fatigue, {"fatigue_high"}, {"baselines": BASE}),
    "four_factors_lever": (lambda: ff_snap(_stats(tov=22), _stats()), {"four_factors_lever"}, {}),
    "rival_hot_player": (lambda: rival_snap({"orb": 4}), {"rival_hot_player"}, {"rival_baselines": RIVAL_BASELINES}),
    "rival_zone": (_zone, {"rival_zone"}, {}),
    "rest_starters": (rest_decided, {"rest_starters"}, {"baselines": REST_TABLE}),
    "cold_shooting": (lambda: snap(elapsed=400, log=shots(OWN, [0] * 8)), {"cold_fg_streak"}, {}),
    "rival_hot_shooting": (lambda: snap(elapsed=400, log=shots(RIVAL, [1] * 8)), {"rival_hot_streak"}, {}),
    "free_throw_cold": (lambda: snap(elapsed=400, log=free_throws(OWN, [0] * 8)), {"ft_cold"}, {}),
    "scoring_drought": (lambda: snap(elapsed=400, log=[[100, OWN, "pts", 2, "p1"]]), {"own_drought", "fg_drought", "rival_drought"}, {}),
    "long_run": (lambda: snap(elapsed=330, log=[[t, RIVAL, "pts", 2, "p1"] for t in (100, 140, 180, 220, 260, 300)]), {"long_run"}, {}),
    "rival_player_form": (lambda: pl_snap({"r1": pl_player("Rita", RIVAL)}, [pl_basket(RIVAL, "r1", 250, 3), pl_basket(RIVAL, "r1", 310, 2),
                                                                         pl_basket(RIVAL, "r1", 380, 2)]), {"rival_hot_run"}, {}),
    "own_player_form": (lambda: pl_snap({"p1": pl_player("Ana", OWN)}, [pl_basket(OWN, "p1", 250, 3), pl_basket(OWN, "p1", 310, 2),
                                                                      pl_basket(OWN, "p1", 380, 2)]), {"own_hot_player"}, {}),
    "rival_star_bench": (lambda: [snap(elapsed=300, players={"r1": pl_player("Rita", RIVAL)}),
                                  snap(elapsed=330, players={"r1": pl_player("Rita", RIVAL, on_court=False)})],
                         {"rival_star_out"}, {"rival_baselines": {"r1": {"name": "Rita", "avg_min": 1500, "impact40": pl_impact(24.0)}}}),
    "disqualification": (lambda: snap(elapsed=400, players={"p1": sa_player("Ana", OWN, unsportsmanlike=1)}), {"disqualification_risk"}, {}),
    "timeout_budget": (lambda: sa_evaluate_snap(period=4, elapsed=2200, remaining=200), {"timeout_budget"}, {}),
    "key_fouls_close": (lambda: sa_evaluate_snap(period=4, elapsed=2200, remaining=200, score={OWN: 60, RIVAL: 58},
                                                 players={"g1": sa_player("Guard Uno", OWN, pf=4)}), {"key_fouls_close"}, {"baselines": REST_TABLE}),
    "rival_foul_pair": (lambda: snap(elapsed=400, players={"r1": sa_player("Rita", RIVAL, pf=3), "r2": sa_player("Rosa", RIVAL, pf=4)}),
                        {"rival_foul_pair"}, {}),
    "closing_briefing": (lambda: cl_finish(), {"closing_briefing"}, {}),
    "period_summary": (lambda: cl_end_of(1, [cl_pts(OWN, 100)]), {"period_summary"}, {}),
    "advantage_management": (lambda: cl_finish(remaining=280, margin=10), {"advantage_management"}, {}),
    "pace_control": (lambda: cl_pace_snap(), {"pace_control"}, {"team_baselines": {"pace_own_per_40": 80.0, "pace_rival_per_40": 72.0}}),
    "game_flow_windows": (lambda: snap(elapsed=350, log=[[t, RIVAL, "orb", 1, "p1"] for t in (250, 300, 340)]), {"rival_orb_window"}, {}),
}


def _ids(engine, snapshot):
    """Ids emitted by evaluating the snapshot twice (an alert that asks for confirmation needs two evaluations). A list of
    snapshots is evaluated in order (a rule that remembers the previous evaluation needs a change to say something)."""
    snapshots = snapshot if isinstance(snapshot, list) else [snapshot]
    return {a.id for _ in range(2) for s in snapshots for a in engine.evaluate(s)}


def test_every_rule_has_a_unique_id_and_the_registry_matches_the_known_ids():
    assert tuple(rule_id for rule_id, _ in RULES) == EXPECTED_IDS
    assert RULE_IDS == EXPECTED_IDS


def test_nothing_is_off_by_default():
    assert RuleConfig().rules_off == ()
    for rule_id, (build, emits, kw) in SCENARIOS.items():
        assert emits <= _ids(_engine(**kw), build()), f"{rule_id} should fire in its scenario"


@pytest.mark.parametrize("rule_id", EXPECTED_IDS)
def test_turning_a_rule_off_silences_only_its_alerts(rule_id):
    build, emits, kw = SCENARIOS[rule_id]
    before = _ids(_engine(**kw), build())
    after = _ids(_engine([rule_id], **kw), build())
    assert emits <= before
    assert not (emits & after)
    assert after == before - emits, "no other rule may change"


def test_own_and_rival_foul_alerts_switch_independently():
    off_own = _ids(_engine(["foul_trouble"]), _fouls())
    assert "foul_trouble" not in off_own and "rival_foul_trouble" in off_own
    off_rival = _ids(_engine(["rival_foul_trouble"]), _fouls())
    assert "foul_trouble" in off_rival and "rival_foul_trouble" not in off_rival


def test_the_output_order_does_not_change_with_the_registry_split():
    """Own fouls (warning) and rival fouls (info) used to come from one rule: the sorted output must be the same."""
    out = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL).evaluate(_fouls())
    assert [(a.id, a.severity) for a in out] == [("foul_trouble", "warning"), ("rival_foul_trouble", "info")]


def test_a_package_rule_config_switches_rules_off_from_json():
    config = RuleConfig.from_dict(json.loads('{"rules_off": ["rival_run", "turnover_streak"], "run_points": 6}'))
    assert config.rules_off == ("rival_run", "turnover_streak") and config.run_points == 6
    assert not config.enabled("rival_run") and config.enabled("fatigue_high")
    hash(config)  # frozen dataclass: the list of the JSON became a tuple


def test_unknown_ids_are_ignored_by_the_engine_but_reported_for_validation():
    """A package written for a newer engine may name a rule this one does not know: it must not crash the app."""
    config = RuleConfig.from_dict({"rules_off": ["rival_run", "does_not_exist"]})
    assert _ids(_engine(config.rules_off), _run()) == set()
    assert unknown_rule_ids(config.rules_off) == ("does_not_exist",)
    assert unknown_rule_ids(["rival_run"]) == ()


def test_a_non_list_rules_off_is_ignored_instead_of_breaking_the_package():
    assert RuleConfig.from_dict({"rules_off": "rival_run"}).rules_off == ()
    assert RuleConfig.from_dict({"rules_off": None}).rules_off == ()


def test_the_rules_off_switch_travels_in_the_package_and_reaches_the_engine():
    from src.live_core.package import PreparationPackage

    package = PreparationPackage(
        collection="c", season="s", team={"id": OWN, "name": "A"}, rival={"id": RIVAL, "name": "B"},
        tables={"players": {}}, created_at="2026-10-14T00:00:00Z", rule_config={"rules_off": ["rival_run"]},
    )
    engine = AdviceEngine.from_package(PreparationPackage.loads(package.dumps()))
    assert "rival_run" not in _ids(engine, _run())
    assert "turnover_streak" in _ids(AdviceEngine.from_package(package), _turnovers())
