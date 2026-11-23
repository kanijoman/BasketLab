"""Who is on court at an instant is worked out ONCE per team and instant, however many lineups ask (found on 23/11/2026 profiling the publication of NCAA).

``LineupStatsCalculator._get_lineup_segments`` walks every instant of the game (every 5 s) for EACH lineup and asks the extractor who is on court; the answer depends on the team and the instant, never on
the lineup, so a game with 264 lineups worked out the same 480 instants 264 times, each one walking every player and every segment of his: 3,9 million calls for 30 real games, 84 % of the time of
``web-data-ext`` (the sections ``lineups`` and ``inout``) and the same cost in ``web-data`` of FEB. The answers must not change: the golden files of the lineups and of the in-out keep proving it.
"""
import itertools

from src.database.lineup_extractor import LineupExtractor
from src.database.lineup_stats_calculator import LineupStatsCalculator


class CountingSegments(list):
    """The segments of a player, counting how many times somebody walks them."""

    walks = 0

    def __iter__(self):
        CountingSegments.walks += 1
        return super().__iter__()


class FakeAnalyzer:
    is_fbcyl = False
    game_data = {}

    def __init__(self, segments):
        self._segments = segments

    def parse_substitutions(self):
        return []

    def get_player_court_segments(self, player_id):
        return self._segments[player_id]


def extractor(teams, segments):
    ex = LineupExtractor(FakeAnalyzer(segments))
    ex.calls_to_players = 0

    def players(team_id):
        ex.calls_to_players += 1
        return set(teams[team_id])

    ex._get_team_players = players
    ex._get_game_duration = lambda: 2400
    return ex


# a 40-minute game of one team of ten: five start, and every 4 minutes one of them is replaced (the segments are inclusive, as the real ones)
def game():
    names = [f"p{i}" for i in range(1, 11)]
    segments = {n: [] for n in names}
    on = names[:5]
    bench = names[5:]
    for n in on:
        segments[n].append([0, 2400])
    for minute in range(4, 40, 4):
        out, came = on[(minute // 4) % 5], bench[(minute // 4) % 5]
        seconds = minute * 60
        for n, s in segments.items():
            if n == out and s and s[-1][1] == 2400:
                s[-1][1] = seconds
        segments[came].append([seconds, 2400])
        on[on.index(out)] = came
        bench[bench.index(came)] = out
    return {"T": names, "R": []}, {n: CountingSegments(map(tuple, s)) for n, s in segments.items()}


def reference(ex, team_id, timestamp):
    """What the method gave before the memo (the algorithm of the day it was written), as the golden answer."""
    on_court = {}
    for player_id in ex._get_team_players(team_id):
        for start, end in ex.analyzer.get_player_court_segments(player_id):
            if start <= timestamp <= end:
                on_court[player_id] = start
                break
    if len(on_court) <= 5:
        return set(on_court)
    return set(sorted(on_court, key=lambda pid: (on_court[pid], str(pid)))[:5])


def test_the_answer_for_every_instant_of_the_game_is_the_same_as_before():
    teams, segments = game()
    ex = extractor(teams, segments)
    assert all(ex.get_lineup_at_timestamp("T", t) == reference(ex, "T", t) for t in range(0, 2405, 5))


def test_asking_the_same_instant_again_does_not_walk_the_players_again():
    teams, segments = game()
    ex = extractor(teams, segments)
    ex.get_lineup_at_timestamp("T", 600)
    CountingSegments.walks = 0
    for _ in range(50):
        ex.get_lineup_at_timestamp("T", 600)
    assert CountingSegments.walks == 0 and ex.calls_to_players == 1                         # the team of a game does not change either


def test_every_lineup_of_a_game_asks_for_the_same_instants_and_the_work_is_done_once():
    """264 lineups, as in a real game of NCAA: the cost does not depend on how many lineups there are."""
    teams, segments = game()
    ex = extractor(teams, segments)
    calculator = LineupStatsCalculator.__new__(LineupStatsCalculator)
    lineups = [frozenset(c) for c in itertools.islice(itertools.combinations(teams["T"], 5), 252)] + [frozenset(c) for c in itertools.islice(itertools.combinations(teams["T"], 4), 12)]
    assert len(lineups) == 264
    CountingSegments.walks = 0
    found = [calculator._get_lineup_segments(ex, "T", lineup) for lineup in lineups]
    assert CountingSegments.walks <= 481 * len(teams["T"])                                   # one walk of each player per instant, not per instant and lineup
    assert sum(1 for f in found if f) > 0


def test_the_segments_of_a_lineup_are_the_ones_the_unmemoised_algorithm_gave():
    teams, segments = game()
    ex = extractor(teams, segments)
    calculator = LineupStatsCalculator.__new__(LineupStatsCalculator)
    starters = frozenset(f"p{i}" for i in range(1, 6))
    got = calculator._get_lineup_segments(ex, "T", starters)
    expected, start = [], None
    for t in range(0, 2400, 5):
        matches = starters == frozenset(reference(ex, "T", t))
        if matches and start is None:
            start = t
        elif not matches and start is not None:
            expected.append((start, t))
            start = None
    if start is not None:
        expected.append((start, 2400))
    assert got == expected and got


def test_a_caller_that_changes_the_set_it_gets_does_not_change_the_next_answer():
    teams, segments = game()
    ex = extractor(teams, segments)
    first = ex.get_lineup_at_timestamp("T", 600)
    first.clear()
    first.add("intruder")
    assert "intruder" not in ex.get_lineup_at_timestamp("T", 600) and len(ex.get_lineup_at_timestamp("T", 600)) == 5


def test_two_teams_never_share_an_answer():
    teams, segments = game()
    teams["R"] = ["p1", "p2"]                                                                  # another team made of other players of the same dictionary
    ex = extractor(teams, segments)
    assert ex.get_lineup_at_timestamp("T", 100) == reference(ex, "T", 100) and ex.get_lineup_at_timestamp("R", 100) == {"p1", "p2"}
    assert ex.get_lineup_at_timestamp("T", 100) != ex.get_lineup_at_timestamp("R", 100)
