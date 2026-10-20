"""The notes of each quarter stick to that quarter's data (issue #419).

Found reviewing Leon-Unibasket: the end of Q3 and of Q4 said "Remontada: de -9 a +12 / de -9 a +9", but the -9 was a point of the 2nd
quarter. A key of a period measures the period (from where it started to where it went), and the pace of the quarter is data in the
summary (against the quarters before and the usual one of both teams) instead of a recommendation to "keep the pace" nobody measured.
"""
from src.live_core.advice import AdviceEngine
from tests.test_live_core_advice import OWN, RIVAL
from tests.test_live_core_closing import by_id, end_of, flat, pts

STARTS = {1: 0, 2: 600, 3: 1200, 4: 1800}


def run(team, start, n, step=20, value=2):
    return flat(*[pts(team, start + step * i, value) for i in range(n)])


def scored(team, start, n, value=2):
    """Points with no shot attempt attached: the result of a quarter without touching its possessions."""
    return [[start + 20 * i, team, "pts", value, "p1"] for i in range(n)]


def attempts(team, period, fga, tov=0, orb=0, fta=0):
    """Events of ``team`` inside ``period`` that give ``fga - orb + tov + 0.44 fta`` possessions."""
    t0 = STARTS[period] + 10
    events = [[t0 + i, team, "fg2", 0, "p1"] for i in range(fga)]
    events += [[t0 + 50 + i, team, "tov", 1, "p1"] for i in range(tov)]
    events += [[t0 + 100 + i, team, "orb", 1, "p1"] for i in range(orb)]
    events += [[t0 + 150 + i, team, "ft", 0, "p1"] for i in range(fta)]
    return events


def summary(period, log, **kw):
    engine = AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, **kw)
    [alert] = by_id(engine.evaluate(end_of(period, [log])), "period_summary")
    return alert


# --- the keys measure the period ----------------------------------------------------------------------------------------------

def test_a_deficit_of_an_earlier_quarter_is_not_a_comeback_of_this_one_regression():
    """Down 9 in Q2, level at the end of the half and +12 at the end of Q3: Q3 started -0, so its story is the +12 of the quarter."""
    first_half = flat(run(RIVAL, 100, 5, 100), run(OWN, 700, 5, 100))            # Q1 -10, Q2 back to level
    q3 = run(OWN, 1210, 6, 40)                                                    # +12 in Q3 from level
    alert = summary(3, flat(first_half, q3))
    assert "comeback" not in alert.evidence["keys"] and "-9" not in alert.message and "-10" not in alert.message
    assert "Parcial del cuarto: +12" in alert.message


def test_the_first_half_is_summarised_with_its_own_trough():
    log = flat(run(RIVAL, 100, 5, 40), run(OWN, 300, 8, 60))                      # -10, then +6 inside the half
    alert = summary(2, log)
    assert "Remontada en la 1.ª parte: de -10 a +6" in alert.message


def test_a_quarter_that_starts_behind_and_ends_ahead_is_measured_from_where_it_started():
    log = flat(run(RIVAL, 100, 5, 100), run(OWN, 1210, 11, 40))                  # -10 at the start of Q3, +12 at the end
    assert "Remontada en el cuarto: de -10 a +12" in summary(3, log).message


# --- the pace of the quarter is data -----------------------------------------------------------------------------------------

def both(period, fga, **kw):
    return flat(attempts(OWN, period, fga, **kw), attempts(RIVAL, period, fga, **kw))


def test_the_summary_says_the_pace_of_the_quarter_against_the_quarters_before():
    log = flat(both(1, 15), both(2, 15), both(3, 20))                            # 60 per 40 min in the first half, 80 in Q3
    alert = summary(3, flat(log, scored(OWN, 1250, 2)))
    assert "Ritmo: 80 posesiones por 40 min frente a 60 antes" in alert.message
    assert alert.evidence["pace"] == {"per40": 80.0, "before40": 60.0, "own_habit40": None, "rival_habit40": None}


def test_and_against_the_usual_pace_of_both_teams_when_the_package_has_it():
    alert = summary(1, both(1, 17), team_baselines={"pace_own_per_40": 70.0, "pace_rival_per_40": 64.0})     # 68 per 40 min
    assert "Ritmo: 68 posesiones por 40 min (habitual: 70 el nuestro y 64 el rival)" in alert.message
    assert alert.evidence["pace"]["own_habit40"] == 70.0 and alert.evidence["pace"]["before40"] is None


def test_a_much_faster_quarter_that_we_won_says_to_keep_the_pace_with_the_numbers():
    alert = summary(3, flat(both(1, 15), both(2, 15), both(3, 20), scored(OWN, 1250, 3)))
    assert "pace" in alert.evidence["keys"]
    assert "Mantener el ritmo alto" in alert.message and "Ritmo: 80 posesiones por 40 min frente a 60 antes" in alert.message


def test_a_slower_quarter_that_we_lost_asks_for_a_faster_one():
    alert = summary(3, flat(both(1, 20), both(2, 20), both(3, 14), scored(RIVAL, 1250, 3)))
    assert "pace" in alert.evidence["keys"] and "Subir el ritmo" in alert.message


def test_a_change_of_pace_that_does_not_match_the_result_is_data_not_a_key():
    alert = summary(3, flat(both(1, 15), both(2, 15), both(3, 20), scored(RIVAL, 1250, 3)))      # faster, and lost
    assert "pace" not in alert.evidence["keys"] and "Ritmo: 80 posesiones por 40 min" in alert.message
    assert "Mantener el ritmo" not in alert.message


def test_the_comeback_no_longer_claims_anything_about_the_pace():
    alert = summary(3, flat(run(RIVAL, 100, 5, 100), run(OWN, 1210, 11, 40)))
    assert "Remontada" in alert.message and "ritmo" not in alert.message.lower()


def test_without_enough_play_in_the_window_there_is_no_pace_line_and_no_claim_about_it():
    alert = summary(1, run(OWN, 100, 6))
    assert "Ritmo" not in alert.message and "ritmo" not in alert.message.lower()
