"""A decided game shows only what is about fatigue and rotation, and favours the bench (issue #320).

"Decided" is the existing criterion (|margin| >= decided_margin with less than decided_remaining_s left of the 4th period).
"""

import dataclasses

from live_helpers import OWN, RIVAL, TABLE, snap as bench_snap
from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from src.live_core.game_context import PHASE_SHIFT, kept_when_decided
from src.live_core.rules_rotation import fatigue_index
from tests.builders import _player, engine, snap


def level(s, margin):
    s["period"], s["remaining"], s["score"] = 4, 120, {OWN: 40, RIVAL: 40 + margin}
    return s


def players(stint=780):    # fatigue index ~86: above the alert of 80 (#426)
    return {"own": _player("Ana", OWN, minutes=1500, stint=stint, on_court=True),
            "rival": _player("Rival", RIVAL, pf=4)}


def ids(advices):
    return {a.id for a in advices}


def test_a_game_that_is_not_decided_keeps_everything():
    out = engine().evaluate(level(snap(elapsed=2300, players=players()), margin=4))
    assert {"fatigue_high", "rival_foul_trouble"} <= ids(out)


def test_a_decided_game_shows_only_fatigue_and_rotation():
    out = engine().evaluate(level(snap(elapsed=2300, players=players()), margin=30))
    assert "fatigue_high" in ids(out)
    assert "rival_foul_trouble" not in ids(out)
    assert all(a.category in ("rotacion", "descanso") for a in out), [(a.id, a.category) for a in out]


def test_what_is_kept_when_decided():
    from src.live_core.advice_types import Advice

    def adv(id_, category):
        return Advice(key=id_, id=id_, severity="info", category=category, message="x")

    assert kept_when_decided(adv("fatigue_high", "rotacion")) and kept_when_decided(adv("rest_starters", "descanso"))
    assert kept_when_decided(adv("disqualification_risk", "faltas")) and kept_when_decided(adv("formation_lineup", "alineacion"))
    assert not kept_when_decided(adv("rival_hot_player", "rival")) and not kept_when_decided(adv("foul_trouble", "faltas"))


def test_the_filter_can_be_switched_off():
    out = engine(config=RuleConfig(decided_only_rotation=False)).evaluate(level(snap(elapsed=2300, players=players()), margin=30))
    assert "rival_foul_trouble" in ids(out) or any(a.category not in ("rotacion", "descanso") for a in out)


def test_what_was_silenced_comes_back_if_the_game_reopens():
    eng = engine()
    first = eng.evaluate(level(snap(elapsed=2300, players=players()), margin=30))
    assert "rival_foul_trouble" not in ids(first)
    later = eng.evaluate(level(snap(elapsed=2330, players=players()), margin=3))      # the rival scored: no longer decided
    assert "rival_foul_trouble" in ids(later)


def test_fatigue_alerts_earlier_in_a_decided_game():
    stint = next(s for s in range(60, 1500, 30) if 65 <= fatigue_index(s, 1500, 2300, None)[0] < 78)
    assert "fatigue_high" not in ids(engine().evaluate(level(snap(elapsed=2300, players=players(stint)), margin=3)))
    assert "fatigue_high" in ids(engine().evaluate(level(snap(elapsed=2300, players=players(stint)), margin=30)))


def test_fatigue_is_not_lowered_a_level_in_a_decided_game():
    assert "rotacion" not in PHASE_SHIFT["decided"]
    normal = [a for a in engine().evaluate(level(snap(elapsed=2300, players=players(900)), margin=12)) if a.id == "fatigue_high"]
    decided_ = [a for a in engine().evaluate(level(snap(elapsed=2300, players=players(900)), margin=30)) if a.id == "fatigue_high"]
    assert normal and decided_ and decided_[0].severity == normal[0].severity


def test_the_relief_goes_first_to_who_has_played_least():
    overrides = {"g1": {"stint": 1800, "minutes": 2100}, "g2": {"minutes": 600}, "b2": {"minutes": 500}, "b3": {"minutes": 0}}
    eng = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=TABLE)

    def first_in(margin):
        s = bench_snap(period=4, elapsed=2200, overrides=overrides)
        s["remaining"], s["score"] = 120, {OWN: 40, RIVAL: 40 + margin}
        [alert] = [a for a in eng.evaluate(s) if a.id == "fatigue_high" and a.evidence["player_id"] == "g1"]
        return [p for p in alert.proposal if p["type"] == "sub"][0]["in_id"]

    assert first_in(12) == "g2"         # not decided: the closest role
    assert first_in(30) == "b3"         # decided: the bench goes first, who has not played
