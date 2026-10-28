"""Player foul alerts. A player is eliminated with 5 fouls, so warnings fire early
enough to act: threshold = min(period + 1, 3); 4 fouls is critical; the 5th foul
is never alerted (it is already a fact)."""

import pytest

from src.live_core.rules_fouls import evaluate_player_fouls, warn_threshold


@pytest.mark.parametrize("period, expected", [(1, 2), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3)])
def test_warn_threshold_by_period(period, expected):
    assert warn_threshold(period) == expected


@pytest.mark.parametrize(
    "pf, period, severity",
    [(1, 1, None), (2, 1, None), (1, 2, None), (2, 2, None), (3, 2, "info"),
     (2, 3, None), (3, 3, "warning"), (2, 4, None), (3, 4, "warning")],
)
def test_warning_fires_at_threshold(pf, period, severity):
    """Issue #241 (R4): two fouls never alert; three are information in the first half and a warning in the second."""
    alert = evaluate_player_fouls("p1", "Ana", pf, period)
    assert (alert.severity if alert else None) == severity
    if alert:
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
    alert = evaluate_player_fouls("p1", "Ana", 3, 3)
    assert "Ana" in alert.message and "3" in alert.message
    assert "faltas" in alert.message.lower()


# Issue #622 (feedback 0.4.2, Cultural–Melilla): the staff expected the notice of the 2nd foul before the 3rd in the first half. Decision of the user (28/10/2026):
# own players get an info at the 2nd foul in the 1st and 2nd quarters; the recommender keeps asking without it (a player with two fouls is still a swap).
@pytest.mark.parametrize("period, severity", [(1, "info"), (2, "info"), (3, None), (4, None), (5, None)])
def test_the_second_foul_is_an_info_of_the_first_half_when_asked(period, severity):
    alert = evaluate_player_fouls("p1", "Ana", 2, period, early_notice=True)
    assert (alert.severity if alert else None) == severity
    if alert:
        assert alert.pf == 2 and "2 faltas" in alert.message


@pytest.mark.parametrize("period", [1, 2, 3, 4])
def test_without_asking_two_fouls_still_say_nothing_so_the_recommender_is_unchanged(period):
    assert evaluate_player_fouls("p1", "Ana", 2, period) is None


def test_an_own_player_with_two_fouls_in_the_first_quarter_gets_the_info_before_the_third_regression():
    from tests.builders import OWN, RIVAL, Match

    m = Match().lineup(OWN, ["p1", "p2"], at=0).lineup(RIVAL, ["r1"], at=0)
    m.foul(OWN, "p1", at=120, drawn_by="r1").foul(OWN, "p1", at=300, drawn_by="r1")
    [alert] = [a for a in m.evaluate() if a.id == "foul_trouble"]
    assert alert.severity == "info" and alert.evidence["pf"] == 2
    m.foul(OWN, "p1", at=420, drawn_by="r1")
    assert [a.evidence["pf"] for a in m.evaluate() if a.id == "foul_trouble"] == [3]       # each count is new: the 3rd one is said as before
