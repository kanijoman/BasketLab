"""What the live state keeps for the box score tab (issue #593): the fouls a player draws and the last action that changed a box score.

The FEB line of a foul carries, in ``logParam4``, the licence of whoever suffers it, and the licence of a player is known from the other lines he appears in
(``idLicense``): the engine resolves the fouled player from them, whatever the order in which the lines arrive. The box score of the official PDF has the column
(``Rec`` of the fouls), and the figures of 4 real matches agree with it (``test_live_core_boxscore_pdf``).
"""
from src.live_core.events import parse_line
from tests.builders import OWN, RIVAL, Match


def line(num, action, text, team, player, license_, clock="09:00", **extra):
    return {"num": str(num), "quarter": "1", "time": clock, "action": action, "text": text, "idTeam": team, "idPlayer": player, "idLicense": license_, "deleted": None, **extra}


class TestFoulsDrawn:
    def test_the_licence_of_the_fouled_player_is_read_from_the_foul_line(self):
        event = parse_line(line(1, "foul", "(A) X: FALTA Personal (Faltas: 1. Faltas de equipo: 1)", "A", "p1", "L1", logParam4="L9"))
        assert (event.license, event.fouled) == ("L1", "L9")

    def test_a_foul_without_a_receiver_has_none(self):
        event = parse_line(line(1, "foul", "(A) X: FALTA Tecnica (Faltas: 1. Faltas de equipo: 1)", "A", "p1", "L1"))
        assert event.fouled is None

    def test_the_fouled_player_is_credited_with_a_foul_drawn(self):
        m = Match().lineup(OWN, ["p1", "p2"], at=0).lineup(RIVAL, ["r1"], at=0)
        snap = m.foul(RIVAL, "r1", at=60, drawn_by="p2").snapshot()
        assert snap["players"]["p2"]["fd"] == 1 and snap["players"]["p1"]["fd"] == 0
        assert snap["players"]["r1"]["pf"] == 1 and snap["players"]["r1"]["fd"] == 0     # the one who commits it does not draw it

    def test_it_does_not_depend_on_the_order_the_licences_arrive_in(self):
        """The fouled player had not done anything yet when the foul was written: the foul is his as soon as his licence is known."""
        m = Match().lineup(RIVAL, ["r1"], at=0)
        m.foul(RIVAL, "r1", at=60, drawn_by="late")
        m.lineup(OWN, ["late"], at=70)
        assert m.snapshot()["players"]["late"]["fd"] == 1

    def test_two_fouls_two_players_each_the_same_amount_that_was_suffered(self):
        m = Match().lineup(OWN, ["p1", "p2"], at=0).lineup(RIVAL, ["r1", "r2"], at=0)
        m.foul(RIVAL, "r1", at=60, drawn_by="p1").foul(RIVAL, "r2", at=70, drawn_by="p1").foul(OWN, "p2", at=80, drawn_by="r1")
        players = m.snapshot()["players"]
        assert [players[p]["fd"] for p in ("p1", "p2", "r1", "r2")] == [2, 0, 1, 0]


class TestLastStat:
    def test_the_last_action_names_the_player_and_what_changed(self):
        snap = Match().lineup(OWN, ["p1"], at=0).score(OWN, 3, at=30, player="p1").snapshot()
        last = snap["last_stat"]
        assert (last["player_id"], last["team_id"]) == ("p1", OWN) and set(last["keys"]) >= {"pts", "fg3m", "fg3a"}

    def test_it_counts_the_actions_the_log_does_not_hold(self):
        m = Match().lineup(OWN, ["p1", "p2"], at=0).score(OWN, 2, at=30, player="p1")
        assert m.assist(OWN, at=30, player="p2").snapshot()["last_stat"]["keys"] == ["ast"]
        assert m.block(OWN, at=40, player="p2").snapshot()["last_stat"]["keys"] == ["blk"]

    def test_a_substitution_changes_who_is_on_court(self):
        m = Match().lineup(OWN, ["p1", "p2"], at=0)
        last = m.substitution(OWN, "p1", "p3", at=50).snapshot()["last_stat"]
        assert (last["player_id"], last["keys"]) == ("p3", ["on_court"])

    def test_every_action_moves_the_sequence_so_the_screen_can_tell_one_from_the_next(self):
        m = Match().lineup(OWN, ["p1"], at=0)
        first = m.score(OWN, 2, at=30, player="p1").snapshot()["last_stat"]["seq"]
        second = m.score(OWN, 2, at=40, player="p1").snapshot()["last_stat"]["seq"]
        assert second > first

    def test_what_changes_nothing_is_not_a_box_score_action(self):
        """A timeout, a period mark or a line without a player leave the last action where it was."""
        m = Match().lineup(OWN, ["p1"], at=0).score(OWN, 2, at=30, player="p1")
        before = m.snapshot()["last_stat"]
        assert m.timeout(OWN, at=40).snapshot()["last_stat"] == before

    def test_nothing_happened_yet(self):
        assert Match().snapshot()["last_stat"] is None

    def test_the_foul_belongs_to_who_commits_it_and_the_one_drawn_is_one_more_change(self):
        """The foul belongs to who commits it: his box score is the one that changes (pf); the one drawn is one more key, on the player who suffers it."""
        m = Match().lineup(OWN, ["p1"], at=0).lineup(RIVAL, ["r1"], at=0)
        last = m.foul(RIVAL, "r1", at=60, drawn_by="p1").snapshot()["last_stat"]
        assert last["player_id"] == "r1" and last["keys"] == ["pf"] and last["also"] == [{"player_id": "p1", "team_id": OWN, "keys": ["fd"]}]


class TestPlusMinusOfAStarterSeenLate:
    """A player whose first line is not «enters» was on court since the tip-off (the five of the start are not in the feed), but the engine learns it when it first sees him.
    His plus/minus is that of the team from the beginning, not from the moment he is seen: found comparing the engine with the PDF in 4 real matches, where a third of
    the players of one of them were off by 2 to 4 points (issue #593)."""

    def test_a_starter_first_seen_late_has_the_plus_minus_of_the_whole_game(self):
        m = Match().score(OWN, 2, at=10, player="p1").score(RIVAL, 3, at=20, player="r1").score(RIVAL, 2, at=30, player="r1")
        m.miss(OWN, at=40, player="p2")                              # p2 and r2 have done nothing until now: they were on court
        m.rebound(RIVAL, at=41, player="r2")
        players = m.snapshot()["players"]
        assert players["p2"]["pm"] == 2 - 5 and players["r2"]["pm"] == 5 - 2

    def test_what_the_player_does_in_the_line_that_reveals_him_counts_once(self):
        m = Match().score(OWN, 2, at=10, player="p1").score(RIVAL, 3, at=20, player="r1")
        m.score(OWN, 3, at=40, player="p2")                          # his first line is a basket: the 3 points are before him and now
        assert m.snapshot()["players"]["p2"]["pm"] == 2 - 3 + 3

    def test_a_player_who_comes_in_gets_only_what_happens_from_then(self):
        m = Match().lineup(OWN, ["p1"], at=0).score(OWN, 2, at=10, player="p1").score(RIVAL, 3, at=20, player="r1")
        m.lineup(OWN, ["p3"], at=30)
        m.score(OWN, 2, at=40, player="p1")
        assert m.snapshot()["players"]["p3"]["pm"] == 2

    def test_the_stint_starts_with_the_same_figure(self):
        m = Match().score(OWN, 2, at=10, player="p1").score(RIVAL, 3, at=20, player="r1").miss(OWN, at=40, player="p2")
        player = m.snapshot()["players"]["p2"]
        assert player["stint_pm"] == player["pm"] == 2 - 3
