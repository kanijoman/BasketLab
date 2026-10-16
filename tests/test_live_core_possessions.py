"""Possession tracker: who has the ball, when a possession ends, and how reliable the play-by-play is (#350).

Scenarios are written as FEB lines (``parse_line`` builds the events) so they read like the real feed. Clock "09:50" of
period 1 is 10 elapsed seconds. Teams are "A" and "B"; a rebound without ``idPlayer`` is a team rebound.
"""
import random

import pytest

from src.live_core.events import parse_line
from src.live_core.possessions import PossessionTracker, level_for_breaks, track


def _line(num, team, player, action, text, clock, quarter="1"):
    return {"num": str(num), "quarter": quarter, "time": clock, "idTeam": team, "idPlayer": player, "action": action,
            "text": f"(X) {text}", "deleted": None}


class _Feed:
    """Builds consecutive lines with an auto-incremented ``num``."""

    def __init__(self, quarter="1"):
        self.n, self.q, self.lines = 0, quarter, []

    def add(self, team, action, text, clock, player="p"):
        self.n += 1
        self.lines.append(_line(self.n, team, player, action, text, clock, self.q))
        return self

    def made(self, team, clock, points=2, player="p"):
        return self.add(team, "shoot", f"A. P: TIRO DE {points} ANOTADO (Puntos: 8)", clock, player)

    def miss(self, team, clock, points=2, player="p"):
        return self.add(team, "shoot", f"A. P: TIRO DE {points} FALLADO", clock, player)

    def ft(self, team, clock, made=True, player="p"):
        return self.add(team, "fthrow", "A. P: TIRO DE 1 " + ("ANOTADO (Puntos: 5)" if made else "FALLADO"), clock, player)

    def reb(self, team, clock, player="p"):
        return self.add(team, "rebound", "A. P: REBOTE (Rebotes: 3)" if player else "REBOTE (Rebotes: 3)", clock, player)

    def tov(self, team, clock, player="p"):
        return self.add(team, "lose", "A. P: PÉRDIDA (Pérdidas: 1)", clock, player)

    def steal(self, team, clock, player="s"):
        return self.add(team, "recovery", "A. P: ROBO (Robos: 1)", clock, player)

    def foul(self, team, clock, kind="Personal", player="f"):
        return self.add(team, "foul", f"A. P: FALTA {kind} (Faltas: 1. Faltas de equipo: 1)", clock, player)

    def timeout(self, team, clock):
        return self.add(team, "timeout", "Tiempo muerto", clock, None)

    def period(self, text, clock, quarter=None):
        self.n += 1
        self.lines.append({"num": str(self.n), "quarter": quarter or self.q, "time": clock, "idTeam": None, "idPlayer": None,
                           "action": "period", "text": text, "deleted": None})
        return self


def _events(lines):
    return [e for e in (parse_line(l) for l in lines) if e is not None]


def _run(feed):
    tracker = PossessionTracker(["A", "B"])
    out = []
    for event in _events(feed.lines):
        out += tracker.feed(event)
    out += tracker.finish()
    return out, tracker


def _counted(possessions):
    return [(p.team_id, p.outcome) for p in possessions if p.counted]


# ---------------------------------------------------------------- alternation and origins

def test_made_baskets_alternate_and_carry_their_points():
    out, tracker = _run(_Feed().made("A", "09:50").made("B", "09:30").made("A", "09:10", 3))

    assert _counted(out) == [("A", "made_fg"), ("B", "made_fg"), ("A", "made_fg")]
    assert [p.points for p in out] == [2, 2, 3]
    assert [p.origin for p in out] == ["period_start", "made_basket", "made_basket"]
    assert (out[0].start_elapsed, out[0].end_elapsed) == (0, 10)      # the first possession starts with the period
    assert (out[1].start_elapsed, out[1].end_elapsed) == (10, 30)
    quality = tracker.quality()
    assert quality.counted == {"A": 2, "B": 1} and quality.breaks_raw == 0 and quality.level == "ok"


def test_offensive_rebound_keeps_the_possession_and_marks_second_chance_points():
    out, _ = _run(_Feed().miss("A", "09:50").reb("A", "09:49").made("A", "09:40"))

    assert len(out) == 1
    assert (out[0].outcome, out[0].points, out[0].orebs, out[0].second_chance_points) == ("made_fg", 2, 1, 2)


def test_points_before_the_offensive_rebound_are_not_second_chance_points():
    # free throw made, last one missed, offensive rebound, then a basket
    feed = _Feed().foul("B", "09:50").ft("A", "09:50", True).ft("A", "09:50", False).reb("A", "09:49").made("A", "09:40")
    out, _ = _run(feed)

    assert len(out) == 1
    assert (out[0].points, out[0].second_chance_points, out[0].orebs) == (3, 2, 1)


@pytest.mark.parametrize("player, origin", [("p", "def_rebound"), (None, "team_def_rebound")])
def test_defensive_rebound_ends_the_possession_and_starts_the_rivals(player, origin):
    out, tracker = _run(_Feed().miss("A", "09:50").reb("B", "09:49", player).made("B", "09:30"))

    assert _counted(out) == [("A", "missed_shot"), ("B", "made_fg")]
    assert out[1].origin == origin and out[1].start_elapsed == 11
    assert tracker.quality().breaks_raw == 0


@pytest.mark.parametrize("steal_first", [False, True])
def test_turnover_with_a_steal_gives_the_rival_a_steal_possession(steal_first):
    feed = _Feed()
    feed.steal("B", "09:50").tov("A", "09:50") if steal_first else feed.tov("A", "09:50").steal("B", "09:50")
    out, _ = _run(feed.made("B", "09:30"))

    assert _counted(out) == [("A", "turnover"), ("B", "made_fg")]
    assert out[1].origin == "steal" and out[0].steal is True


def test_turnover_without_a_steal_is_a_plain_turnover_origin():
    out, _ = _run(_Feed().tov("A", "09:50").made("B", "09:30"))

    assert out[1].origin == "turnover" and out[0].steal is False


def test_points_by_player_and_dunks_are_credited():
    feed = _Feed().add("A", "shoot", "A. P: MATE ANOTADO (Puntos: 12)", "09:50", "p1")
    out, _ = _run(feed)

    assert out[0].points == 2 and out[0].points_by_player == {"p1": 2}


# ---------------------------------------------------------------- free throws

def test_and_one_is_a_single_possession_ended_by_the_free_throw():
    feed = _Feed().made("A", "09:50").foul("B", "09:50").ft("A", "09:45", True).made("B", "09:30")
    out, tracker = _run(feed)

    assert _counted(out) == [("A", "ft_made"), ("B", "made_fg")]
    assert out[0].points == 3 and tracker.quality().breaks_raw == 0


def test_free_throw_trip_ends_the_possession_with_the_last_free_throw():
    out, _ = _run(_Feed().foul("B", "09:50").ft("A", "09:50", True).ft("A", "09:50", True).made("B", "09:30"))

    assert _counted(out) == [("A", "ft_made"), ("B", "made_fg")] and out[0].points == 2


def test_missed_last_free_throw_with_a_defensive_rebound_ends_the_possession():
    feed = _Feed().foul("B", "09:50").ft("A", "09:50", True).ft("A", "09:50", False).reb("B", "09:49").made("B", "09:30")
    out, _ = _run(feed)

    assert _counted(out) == [("A", "missed_shot"), ("B", "made_fg")] and out[0].points == 1


def test_shooting_foul_on_a_missed_shot_does_not_end_the_possession_at_the_miss():
    out, _ = _run(_Feed().miss("A", "09:50").foul("B", "09:49").ft("A", "09:49").ft("A", "09:49").made("B", "09:30"))

    assert _counted(out) == [("A", "ft_made"), ("B", "made_fg")] and out[0].points == 2


# ---------------------------------------------------------------- technical and unsportsmanlike fouls

def test_technical_free_throws_do_not_change_possession_and_are_not_a_possession():
    """The team with the ball gets a technical; the rival shoots; the ball goes back to the original team."""
    feed = (_Feed().tov("B", "09:55").foul("A", "09:40", "Técnica").ft("B", "09:40", True, "b").ft("B", "09:40", False, "b")
            .made("A", "09:30").made("B", "09:10"))
    out, tracker = _run(feed)

    assert _counted(out) == [("B", "turnover"), ("A", "made_fg"), ("B", "made_fg")]
    quality = tracker.quality()
    assert quality.technical_ft == 2 and quality.breaks_raw == 0
    assert tracker.technical_points == {"B": 1}


def test_technical_free_throw_points_are_kept_per_player_for_the_bench_count():
    """Bug (#352): the 1-2 points of a bench player's technical free throws belong to nobody, so the bench points fell short."""
    feed = _Feed().tov("B", "09:55").foul("A", "09:40", "Técnica").ft("B", "09:40", True, "b").ft("B", "09:40", True, "c")
    out, tracker = _run(feed)

    assert tracker.quality().technical_by_player == {"B": {"b": 1, "c": 1}}


def test_technical_between_a_miss_and_its_rebound_keeps_the_miss_pending():
    feed = _Feed().miss("A", "09:50").foul("B", "09:49", "Técnica").ft("A", "09:49", True).reb("B", "09:48").made("B", "09:30")
    out, _ = _run(feed)

    assert _counted(out) == [("A", "missed_shot"), ("B", "made_fg")]


def test_technical_on_the_shooter_does_not_hide_the_offensive_rebound():
    feed = _Feed().miss("A", "09:50").foul("A", "09:49", "Técnica").ft("B", "09:49", True).reb("A", "09:48").made("A", "09:30")
    out, _ = _run(feed)

    assert _counted(out) == [("A", "made_fg")] and out[0].orebs == 1


def test_unsportsmanlike_trip_is_a_possession_followed_by_a_consecutive_one_without_a_break():
    feed = (_Feed().foul("B", "09:50", "Antideportiva").ft("A", "09:50", True).ft("A", "09:50", False)
            .made("A", "09:30").made("B", "09:10"))
    out, tracker = _run(feed)

    assert _counted(out) == [("A", "trip"), ("A", "made_fg"), ("B", "made_fg")]
    assert out[1].origin == "trip" and tracker.quality().breaks_raw == 0


# ---------------------------------------------------------------- feed errors: gaps and repairs

def test_action_by_the_team_without_the_ball_closes_an_inferred_possession_and_flags_the_gap():
    out, tracker = _run(_Feed().made("A", "09:50").made("A", "09:30"))

    assert [(p.team_id, p.outcome, p.counted) for p in out] == [("A", "made_fg", True), ("B", "inferred", False), ("A", "made_fg", True)]
    assert out[1].repaired is True and out[2].gap_before is True
    quality = tracker.quality()
    assert quality.inferred == 1 and quality.breaks_raw == 1 and quality.counted == {"A": 2}


def test_rebound_without_a_missed_shot_opens_a_flagged_possession():
    out, _ = _run(_Feed().reb("A", "09:50").made("B", "09:30"))

    assert [(p.team_id, p.outcome, p.counted, p.repaired) for p in out] == [("A", "inferred", False, True), ("B", "made_fg", True, False)]


def test_misattributed_rebound_is_repaired_for_possessions_only():
    """A misses, the rebound is credited to B, but A acts next with nothing from B in between."""
    out, tracker = _run(_Feed().miss("A", "09:50").reb("B", "09:49").made("A", "09:40"))

    assert _counted(out) == [("A", "made_fg")]
    assert (out[0].orebs, out[0].repaired_orebs, out[0].second_chance_points, out[0].repaired) == (0, 1, 2, True)
    quality = tracker.quality()
    assert (quality.repaired_rebounds, quality.breaks_raw, quality.breaks) == (1, 1, 0)


def test_rebound_is_not_repaired_when_the_rival_acts_afterwards():
    out, tracker = _run(_Feed().miss("A", "09:50").reb("B", "09:49").made("B", "09:40"))

    assert _counted(out) == [("A", "missed_shot"), ("B", "made_fg")] and tracker.quality().repaired_rebounds == 0


# ---------------------------------------------------------------- periods, timeouts, ordering

def test_periods_start_with_their_own_possession_and_the_buzzer_possession_is_not_counted():
    feed = (_Feed().period("Comienzo del Cuarto 1", "10:00").made("A", "09:50").period("Fin del Cuarto 1", "00:00"))
    feed.q = "2"
    feed.period("Comienzo del Cuarto 2", "10:00").made("B", "09:50")
    out, _ = _run(feed)

    assert [(p.team_id, p.period, p.outcome, p.counted) for p in out] == [
        ("A", 1, "made_fg", True), ("B", 1, "period_end", False), ("B", 2, "made_fg", True)]
    assert [p.origin for p in out if p.counted] == ["period_start", "period_start"]


def test_a_miss_at_the_buzzer_ends_the_possession():
    feed = _Feed().miss("A", "00:02").period("Fin del Cuarto 1", "00:00")
    out, _ = _run(feed)

    assert _counted(out) == [("A", "missed_shot")]


def test_timeouts_are_attached_to_the_possession_they_precede():
    out, _ = _run(_Feed().made("A", "09:50").timeout("B", "09:40").made("B", "09:30"))

    assert out[1].timeouts == (("B", 20),) and out[0].timeouts == ()


def test_batch_tracking_sorts_by_clock_and_feeding_one_by_one_gives_the_same_result():
    feed = _Feed().miss("A", "09:50").reb("B", "09:49").made("B", "09:30").tov("A", "09:10").made("B", "08:50")
    events = _events(feed.lines)
    shuffled = events[:]
    random.Random(3).shuffle(shuffled)

    batch, quality = track(shuffled, ["A", "B"])
    tracker = PossessionTracker(["A", "B"])
    incremental = []
    for event in events:
        incremental += tracker.feed(event)
    incremental += tracker.finish()

    assert batch == incremental and quality.counted == tracker.quality().counted


# ---------------------------------------------------------------- quality of the source data

@pytest.mark.parametrize("breaks, level", [(0, "ok"), (4, "ok"), (5, "doubtful"), (7, "doubtful"), (8, "unreliable"), (20, "unreliable")])
def test_quality_levels_follow_the_agreed_thresholds(breaks, level):
    assert level_for_breaks(breaks) == level


def test_quality_reports_the_difference_between_teams():
    _, tracker = _run(_Feed().made("A", "09:50").made("B", "09:30").made("A", "09:10"))

    assert tracker.quality().difference == 1


# ---------------------------------------------------------------- kind of shot that closed the possession

@pytest.mark.parametrize("feed, kind", [
    (_Feed().made("A", "09:50", 3), "fg3"),
    (_Feed().made("A", "09:50", 2), "fg2"),
    (_Feed().add("A", "shoot", "A. P: MATE ANOTADO (Puntos: 12)", "09:50"), "dunk"),
    (_Feed().foul("B", "09:50").ft("A", "09:50").ft("A", "09:50"), "ft"),
    (_Feed().miss("A", "09:50", 3).reb("B", "09:49").made("B", "09:30"), "fg3"),
    (_Feed().foul("B", "09:50").ft("A", "09:50", False).reb("B", "09:49").made("B", "09:30"), "ft"),
])
def test_possession_records_the_kind_of_shot_that_closed_it(feed, kind):
    out, _ = _run(feed)

    assert out[0].shot_kind == kind


def test_turnover_has_no_shot_kind():
    out, _ = _run(_Feed().tov("A", "09:50"))

    assert out[0].shot_kind == ""


def test_missing_rebound_the_miss_closes_the_possession_and_the_rival_starts_at_the_miss():
    """No rebound line: the rival's next action shows it got the ball, but the shooter's possession ended at the miss."""
    out, _ = _run(_Feed().miss("A", "09:50").made("B", "09:30"))

    assert [(p.team_id, p.outcome, p.end_elapsed) for p in out] == [("A", "missed_shot", 10), ("B", "made_fg", 30)]
    assert out[1].start_elapsed == 10 and out[1].duration == 20


def test_a_miss_at_the_buzzer_ends_at_the_time_of_the_miss():
    out, _ = _run(_Feed().miss("A", "00:20").period("Fin del Cuarto 1", "00:00"))

    assert out[0].end_elapsed == 580
