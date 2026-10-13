"""Proposals are not only substitutions (issue #240): a rule can propose a timeout or a tactic.

The engine keeps what the rule proposes, adds the recommender's substitutions after it, and completes a timeout
proposal with the timeouts the own team has left.
"""
import json

import pytest

import src.live_core.advice as advice_module
from live_helpers import OWN, RIVAL, TABLE, snap
from src.live_core.advice import AdviceEngine
from src.live_core.advice_types import Advice
from src.live_core.proposals import tactic_proposal, timeout_proposal


def engine(table=TABLE):
    return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, baselines=table)


def only_rule(monkeypatch, rule_id, proposal, **evidence):
    """Make ``rule_id`` the only rule, emitting one alert that carries ``proposal``."""
    def rule(s, ctx):
        return [Advice(key=f"{rule_id}:x", id=rule_id, severity="warning", category="rotacion", message="m",
                       evidence=evidence, proposal=list(proposal))]
    monkeypatch.setattr(advice_module, "RULES", [(rule_id, rule)])


def test_a_timeout_proposal_names_the_type_and_the_timeouts_left():
    assert timeout_proposal(2) == {"type": "timeout", "left": 2, "message": "Tiempo muerto · quedan 2"}
    assert timeout_proposal(1)["message"] == "Tiempo muerto · queda 1"
    assert timeout_proposal(0)["message"] == "Tiempo muerto · no quedan"


def test_a_tactic_proposal_has_a_message_and_an_optional_target_player():
    assert tactic_proposal("Defensa en zona") == {"type": "tactic", "message": "Defensa en zona"}
    p = tactic_proposal("Ayudas sobre ella", player_id="r1", player_name="Rita")
    assert p == {"type": "tactic", "message": "Ayudas sobre ella", "player_id": "r1", "player_name": "Rita"}


def test_the_substitutions_are_added_after_what_the_rule_proposed_not_instead_of_it(monkeypatch):
    """Regression: the recommender used to replace the proposals a rule already carried."""
    only_rule(monkeypatch, "foul_trouble", [tactic_proposal("Cambia a zona")], player_id="b1")
    s = snap(period=2, overrides={"b1": {"pf": 3}})
    [alert] = engine().evaluate(s)
    assert alert.proposal[0] == tactic_proposal("Cambia a zona")
    assert [p["type"] for p in alert.proposal[1:]] and all(p["type"] == "sub" for p in alert.proposal[1:])


def test_what_the_rule_proposed_survives_without_baselines_to_recommend_from(monkeypatch):
    only_rule(monkeypatch, "foul_trouble", [tactic_proposal("Cambia a zona")], player_id="b1")
    [alert] = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL).evaluate(snap(period=2))
    assert alert.proposal == [tactic_proposal("Cambia a zona")]


def test_a_rule_that_proposes_nothing_still_gets_the_substitutions(monkeypatch):
    only_rule(monkeypatch, "foul_trouble", [], player_id="b1")
    [alert] = engine().evaluate(snap(period=2, overrides={"b1": {"pf": 3}}))
    assert alert.proposal and all(p["type"] == "sub" for p in alert.proposal)


def test_a_timeout_proposal_without_a_count_is_completed_with_the_timeouts_left(monkeypatch):
    only_rule(monkeypatch, "rival_run", [{"type": "timeout"}])
    [alert] = engine().evaluate(snap(period=1))
    [p] = alert.proposal
    assert p["type"] == "timeout" and p["left"] == 2 and p["message"] == "Tiempo muerto · quedan 2"


def test_a_timeout_proposal_that_already_has_a_count_is_left_alone(monkeypatch):
    only_rule(monkeypatch, "rival_run", [timeout_proposal(1)])
    [alert] = engine().evaluate(snap(period=1))
    assert alert.proposal == [timeout_proposal(1)]


@pytest.mark.parametrize("proposal", [timeout_proposal(2), tactic_proposal("x", player_id="r1", player_name="Rita")])
def test_every_kind_of_proposal_is_json_serialisable(proposal):
    assert json.loads(json.dumps(proposal)) == proposal
