"""«Parcial en contra: -19» in the halftime summary said nothing of where it came from (feedback 0.4.0, #565): now it says from which score to which and between which moments."""
from tests.builders import OWN, RIVAL
from tests.test_live_core_closing import pts
from tests.test_live_core_summary_block import summary


def test_the_conceded_run_says_from_what_to_what_and_when_regression():
    log = [pts(OWN, 100, 3)] + [pts(RIVAL, t, v) for t, v in ((700, 3), (800, 3), (900, 3), (950, 3), (1000, 3), (1050, 2), (1100, 2))]       # +3, then 19 against
    alert = summary(2, log)
    assert "Parcial en contra: -19 (de +3 a -16, del 1.er cuarto 8:20 al 2.º cuarto 1:40)" in alert.message


def test_a_run_inside_one_quarter_names_the_quarter_once():
    log = [pts(OWN, 50, 2)] + [pts(RIVAL, t, v) for t, v in ((100, 3), (150, 3), (200, 3), (250, 2))]
    alert = summary(1, log)
    assert "Parcial en contra: -11 (de +2 a -9, en el 1.er cuarto del 9:10 al 5:50)" in alert.message
