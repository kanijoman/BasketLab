"""A NCAA game of ESPN as the canonical document of an external source (#888, D4): the FEB document with ``_league: ncaa`` and every id prefixed (``ncaa:265``), like FIBA's.

Real games (``tests/fixtures/ncaa``): a men's one (two halves of 20 minutes), a women's one (four quarters), an overtime of each, a visitor that is not Division I and a game whose play by play came empty.
The game is kept COMPLETE (both teams, the box of both and every play) and each team says whether it is Division I and the conference it played in that day (#966): which players to keep is decided
later by who reads the document, not by throwing the rest away.
"""
import copy

import pytest

from ncaa_helpers import fixture

from src.external.ncaa_canonical import to_canonical
from src.external.ncaa_page import parse_summary
from src.market.canonical import validate_game

MENS, WOMENS = "game_mens_401829197", "game_womens_401825641"
ENTRY_M = {"competition": "D1 Men", "season_value": "2025", "season_label": "2025/2026", "gender": "M", "conference": "WCC"}
ENTRY_F = {"competition": "D1 Women", "season_value": "2025", "season_label": "2025/2026", "gender": "F", "conference": "Big East"}
NAMES = {"29": "West Coast Conference", "4": "Big East Conference", "14": "Mid-American Conference"}


def doc(name, entry=ENTRY_M):
    return to_canonical(parse_summary(fixture(name)), entry, NAMES)


def lines(name, entry=ENTRY_M):
    return doc(name, entry)["PLAYBYPLAY"]["LINES"]


class TestTheDocument:
    @pytest.mark.parametrize("name,entry,gender", [(MENS, ENTRY_M, "M"), ("game_mens_ot_401812120", ENTRY_M, "M"), (WOMENS, ENTRY_F, "F"), ("game_womens_ot_401827769", ENTRY_F, "F"),
                                                   ("game_mens_nond1_401823428", ENTRY_M, "M"), ("game_womens_noplays_401830444", ENTRY_F, "F")])
    def test_every_real_game_passes_the_validation_of_the_canonical_format(self, name, entry, gender):
        assert validate_game(doc(name, entry), gender) == []

    def test_it_is_the_game_of_ncaa_with_its_season_and_its_prefixed_ids(self):
        d = doc(MENS)
        assert (d["_id"], d["_league"], d["_season"]) == ("ncaa:401829197", "ncaa", "2025")
        assert [t["id"] for t in d["HEADER"]["TEAM"]] == ["ncaa:265", "ncaa:2250"] and d["HEADER"]["game_code"] == "401829197"

    def test_the_header_has_the_kick_off_the_score_and_the_periods_home_team_first(self):
        header = doc(MENS)["HEADER"]
        assert header["starttime"] == "16-01-2026 - 03:15" and header["competition"] == "D1 Men"       # the time ESPN gives, UTC
        assert [(t["name"], t["pts"]) for t in header["TEAM"]] == [("Washington State Cougars", "65"), ("Gonzaga Bulldogs", "86")]
        assert header["QUARTERS"]["QUARTER"] == [{"n": "1", "scoreA": "33", "scoreB": "43"}, {"n": "2", "scoreA": "32", "scoreB": "43"}]

    def test_the_men_have_two_halves_the_women_four_quarters_and_an_overtime_is_one_more_period(self):
        count = lambda name, entry: len(doc(name, entry)["HEADER"]["QUARTERS"]["QUARTER"])
        assert (count(MENS, ENTRY_M), count("game_mens_ot_401812120", ENTRY_M), count(WOMENS, ENTRY_F), count("game_womens_ot_401827769", ENTRY_F)) == (2, 3, 4, 5)

    def test_each_team_says_the_conference_it_played_in_that_day_and_whether_it_is_division_i(self):
        washington, gonzaga = doc(MENS)["HEADER"]["TEAM"]
        assert (washington["conference_id"], washington["conference"], washington["division1"]) == ("29", "West Coast Conference", True) and gonzaga["conference_id"] == "29"

    def test_a_visitor_that_is_not_division_i_stays_in_the_game_flagged_with_its_box_and_its_plays(self):
        d = doc("game_mens_nond1_401823428")
        buffalo, rit = d["HEADER"]["TEAM"]
        assert (buffalo["division1"], buffalo["conference_id"]) == (True, "14") and (rit["division1"], rit["conference_id"], rit["conference"]) == (False, None, None)
        box = {t["id"]: t for t in d["BOXSCORE"]["TEAM"]}
        assert box["ncaa:178"]["division1"] is False and len(box["ncaa:178"]["PLAYER"]) == 17 and any(line["idTeam"] == "ncaa:178" for line in d["PLAYBYPLAY"]["LINES"])

    def test_the_conversion_changes_nothing_of_what_was_read_and_gives_the_same_document_every_time(self):
        game = parse_summary(fixture(MENS))
        before = copy.deepcopy(game)
        assert to_canonical(game, ENTRY_M, NAMES) == to_canonical(game, ENTRY_M, NAMES) and game == before


class TestTheBox:
    def players(self, name=MENS, team="ncaa:4703396"):
        return {p["id"]: p for t in doc(name)["BOXSCORE"]["TEAM"] for p in t["PLAYER"]}

    def test_a_player_has_the_official_numbers_with_the_minutes_in_seconds_and_the_starter_mark(self):
        ike = self.players()["ncaa:4703396"]
        assert (ike["name"], ike["no"], ike["min"], ike["sta"]) == ("Graham Ike", "15", "2160", "*")
        assert {k: ike[k] for k in ("pts", "p1m", "p1a", "p2m", "p2a", "p3m", "p3a", "fgm", "fga", "assist", "st", "to", "bs", "ro", "rd", "rt", "pf")} == {
            "pts": "23", "p1m": "1", "p1a": "1", "p2m": "11", "p2a": "15", "p3m": "0", "p3a": "0", "fgm": "11", "fga": "15", "assist": "5", "st": "2", "to": "2", "bs": "0", "ro": "6", "rd": "5", "rt": "11", "pf": "1"}

    def test_the_total_of_a_team_adds_its_players_and_what_the_team_itself_did_goes_apart(self):
        gonzaga = next(t for t in doc(MENS)["BOXSCORE"]["TEAM"] if t["id"] == "ncaa:2250")
        assert gonzaga["win_lose"] == "W" and gonzaga["TOTAL"]["pts"] == "86" and gonzaga["TOTAL"]["fgm"] == "34"
        own = gonzaga["TEAMACTIONS"]
        assert own["rt"] == str(43 - int(gonzaga["TOTAL"]["rt"])) and own["to"] == "0"          # team rebounds are what the box of the team has over the sum of its players

    def test_the_turnovers_of_the_total_include_the_ones_of_the_team_itself_as_the_official_box_counts_them(self):
        """The women's game of Villanova at UConn: Villanova (222) has 24 turnovers of its players and 2 of the team, and the official total is 26: the play by play counts all 26."""
        villanova = next(t for t in doc(WOMENS, ENTRY_F)["BOXSCORE"]["TEAM"] if t["id"] == "ncaa:222")
        assert villanova["TOTAL"]["to"] == "26" and villanova["TEAMACTIONS"]["to"] == "2" and sum(int(p["to"]) for p in villanova["PLAYER"] if p["to"]) == 24

    def test_a_player_who_did_not_play_is_in_the_box_without_numbers(self):
        benched = [p for t in doc(WOMENS, ENTRY_F)["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if p["min"] is None]
        assert benched and all(p["pts"] is None for p in benched)


class TestThePlayByPlay:
    def test_a_missed_three_is_a_line_with_the_player_the_period_the_clock_and_the_score(self):
        line = next(l for l in lines(MENS) if l["text"].endswith("Ace Glass: TIRO DE 3 FALLADO"))
        assert (line["action"], line["quarter"], line["time"], line["idTeam"], line["idPlayer"]) == ("shoot", "1", "19:44", "ncaa:265", "ncaa:5313054")
        assert line["text"] == "(Washington State Cougars) Ace Glass: TIRO DE 3 FALLADO" and (line["scoreA"], line["scoreB"]) == ("0", "0")

    def test_made_shots_free_throws_and_dunks_say_so(self):
        texts = [l["text"] for l in lines(MENS)]
        assert any("TIRO DE 2 ANOTADO" in t for t in texts) and any("TIRO DE 1 ANOTADO" in t for t in texts) and any("MATE ANOTADO" in t for t in texts)
        assert {l["action"] for l in lines(MENS) if "TIRO DE 1" in l["text"]} == {"fthrow"}

    def test_rebounds_say_offensive_or_defensive_and_a_team_rebound_has_no_player(self):
        rebounds = [l for l in lines(MENS) if l["action"] == "rebound"]
        assert any(l["text"].endswith("REBOTE OFENSIVO") and l["idPlayer"] for l in rebounds) and any(l["text"].endswith("REBOTE DEFENSIVO") for l in rebounds)
        team = next(l for l in rebounds if l["idPlayer"] is None)
        assert "REBOTE DE EQUIPO" in team["text"] and team["idTeam"]

    def test_steals_turnovers_blocks_and_fouls_with_the_fouls_of_the_player_counted(self):
        by_action = {}
        for line in lines(MENS):
            by_action.setdefault(line["action"], []).append(line)
        assert all(k in by_action for k in ("recovery", "lose", "blockshot", "foul", "subst", "timeout", "period"))
        okafor = [l["text"] for l in by_action["foul"] if "ND Okafor" in l["text"]]
        assert okafor[0].endswith("FALTA PERSONAL. Faltas: 1.") and okafor[1].endswith("Faltas: 2.")

    def test_a_substitution_says_who_comes_in_and_who_goes_out(self):
        subs = [l["text"] for l in lines(MENS) if l["action"] == "subst"]
        assert any(t.endswith("Emmanuel Ugbo: SALE DE PISTA") for t in subs) and any(t.endswith("ENTRA A PISTA") for t in subs)

    def test_the_end_of_each_period_is_a_line_and_a_half_is_not_called_a_quarter(self):
        men = [l["text"] for l in lines(MENS) if l["action"] == "period"]
        women = [l["text"] for l in lines(WOMENS, ENTRY_F) if l["action"] == "period"]
        assert "Fin de la Parte 1" in men and "Fin de la Parte 2" in men and "Fin del Cuarto 3" in women
        assert "Fin de la Prórroga 1" in [l["text"] for l in lines("game_mens_ot_401812120") if l["action"] == "period"]

    def test_nothing_of_the_play_by_play_is_lost_and_lines_are_numbered_in_order(self):
        game = parse_summary(fixture(MENS))
        out = to_canonical(game, ENTRY_M, NAMES)["PLAYBYPLAY"]["LINES"]
        assists = sum(1 for p in game["plays"] if p["assist_id"])
        assert assists == 26 and len(out) == len(game["plays"]) + assists and [l["num"] for l in out] == [str(i) for i in range(1, len(out) + 1)]

    def test_a_made_shot_with_an_assist_is_followed_by_the_assist_line_of_the_other_player(self):
        """ESPN gives the assist as the second participant of the made shot («Eemeli Yalaho makes 23-foot three point jumper (Jerone Morton assists)»): 26 of them, as many as the box says."""
        out = lines(MENS)
        index = next(i for i, l in enumerate(out) if "Eemeli Yalaho: TIRO DE 3 ANOTADO" in l["text"])
        shot, assist = out[index], out[index + 1]
        assert shot["idPlayer"] == "ncaa:5175078" and assist["action"] == "assist" and assist["idPlayer"] == "ncaa:5177358" and assist["idTeam"] == shot["idTeam"]
        assert assist["text"].endswith("Jerone Morton: ASISTENCIA") and (assist["quarter"], assist["time"], assist["scoreA"]) == (shot["quarter"], shot["time"], shot["scoreA"])

    def test_an_event_that_is_not_known_stays_as_a_line_of_other(self):
        game = parse_summary(fixture(WOMENS))
        game["plays"][3] = {**game["plays"][3], "type": "SomethingNew", "text": "Something new happened.", "shooting": False, "scoring": False}
        line = to_canonical(game, ENTRY_F, NAMES)["PLAYBYPLAY"]["LINES"][3]
        assert line["action"] == "other" and "Something new happened." in line["text"]

    def test_a_game_whose_play_by_play_came_empty_has_no_lines_and_is_still_a_document(self):
        d = doc("game_womens_noplays_401830444", ENTRY_F)
        assert d["PLAYBYPLAY"]["LINES"] == [] and d["BOXSCORE"]["TEAM"][0]["PLAYER"] and d["SHOTCHART"] == {"SHOTS": [], "TEAM": []}


class TestTheReconciliationOfTheCommonCriterion:
    """The criterion of #884 for every external source, with the shared reconciliation (``market.box_reconciliation``, the one the refresh applies): the play by play of the document must match its box in
    the nine core statistics. Measured on real games, 23/11/2026: the six normal ones match; the one whose play by play came empty does not, and is kept marked as not reliable."""

    @pytest.mark.parametrize("name,entry", [(MENS, ENTRY_M), ("game_mens_ot_401812120", ENTRY_M), ("game_mens_nond1_401823428", ENTRY_M), (WOMENS, ENTRY_F), ("game_womens_ot_401827769", ENTRY_F),
                                            ("game_womens_nond1_401817303", ENTRY_F)])
    def test_the_real_games_match_in_the_core_statistics(self, name, entry):
        from src.market.box_reconciliation import CORE_STATS, reconcile_game

        result = reconcile_game(doc(name, entry))
        assert result.reliable is True and not result.mismatches(CORE_STATS)

    def test_the_game_whose_play_by_play_came_empty_is_not_reliable_in_every_core_statistic(self):
        from src.market.box_reconciliation import CORE_STATS, reconcile_game

        result = reconcile_game(doc("game_womens_noplays_401830444", ENTRY_F))
        assert result.reliable is False and {c.stat for c in result.mismatches(CORE_STATS)} == set(CORE_STATS)

    @pytest.mark.parametrize("name,entry", [(MENS, ENTRY_M), ("game_womens_nond1_401817303", ENTRY_F), ("game_mens_ot_401812120", ENTRY_M), (WOMENS, ENTRY_F), ("game_womens_ot_401827769", ENTRY_F)])
    def test_the_turnovers_match_in_every_real_game_and_the_assists_in_nearly_all(self, name, entry):
        """Real finding (23/11/2026): the turnovers match once the team's own are counted; the assists match in most games but in two of the six (the overtime of Bryant and Villanova at UConn) the official
        box has ONE assist more than the play by play of ESPN itself (13 of 14 and 21 of 22): an information statistic, so the game is not discarded."""
        from src.market.box_reconciliation import reconcile_game

        result = reconcile_game(doc(name, entry))
        assert not result.mismatches(("TOV",)) and result.reliable is True
        off_by_one = {"game_mens_ot_401812120", WOMENS}
        assert bool(result.mismatches(("AST",))) is (name in off_by_one)
        assert all(abs(c.official - c.pbp) == 1 for c in result.mismatches(("AST",)))

    def test_a_play_that_ESPN_lost_makes_the_game_not_reliable_and_the_statistic_is_named(self):
        from src.market.box_reconciliation import reconcile_game

        game = parse_summary(fixture(WOMENS))
        made = next(i for i, p in enumerate(game["plays"]) if p["scoring"] and p["points_attempted"] == 2)
        del game["plays"][made]
        result = reconcile_game(to_canonical(game, ENTRY_F, NAMES))
        assert result.reliable is False and {"PTS", "FGM", "FGA"} <= {c.stat for c in result.mismatches(("PTS", "FGM", "FGA"))}
