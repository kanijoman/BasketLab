"""Player foul alerts. A player is eliminated with 5 fouls, so warnings fire early
enough to act: threshold = min(period + 1, 3); 4 fouls is critical; the 5th foul
is never alerted (it is already a fact)."""

import pytest

from src.live_core.rules_fouls import evaluate_player_fouls, warn_threshold


@pytest.mark.parametrize("period, expected", [(1, 2), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3)])
def test_warn_threshold_by_period(period, expected):
    assert warn_threshold(period) == expected


@pytest.mark.parametrize(
    "pf, period, fires",
    [(1, 1, False), (2, 1, True), (1, 2, False), (2, 2, False), (3, 2, True),
     (2, 3, False), (3, 3, True), (2, 4, False), (3, 4, True)],
)
def test_warning_fires_at_threshold(pf, period, fires):
    alert = evaluate_player_fouls("p1", "Ana", pf, period)
    assert (alert is not None) == fires
    if fires:
        assert alert.severity == "warning"
        assert alert.player_id == "p1" and alert.pf == pf


@pytest.mark.parametrize("period", [1, 2, 3, 4])
def test_four_fouls_is_critical_in_any_period(period):
    alert = evaluate_player_fouls("p1", "Ana", 4, period)
    assert alert is not None and alert.severity == "critical"


@pytest.mark.parametrize("pf", [5, 6])
def test_fifth_foul_is_never_alerted(pf):
    assert evaluate_player_fouls("p1", "Ana", pf, 4) is None
    assert evaluate_player_fouls("p1", "Ana", pf, 1) is None


def test_no_repeat_for_the_same_foul_count():
    first = evaluate_player_fouls("p1", "Ana", 3, 2)
    assert first is not None
    assert evaluate_player_fouls("p1", "Ana", 3, 2, last_alerted_pf=3) is None


def test_new_foul_alerts_again_and_escalates():
    assert evaluate_player_fouls("p1", "Ana", 4, 3, last_alerted_pf=3).severity == "critical"
    assert evaluate_player_fouls("p1", "Ana", 3, 3, last_alerted_pf=2).severity == "warning"


def test_message_is_in_spanish_and_has_evidence():
    alert = evaluate_player_fouls("p1", "Ana", 2, 1)
    assert "Ana" in alert.message and "2" in alert.message
    assert "faltas" in alert.message.lower()
