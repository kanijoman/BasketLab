"""What the reader of ESPN (#888, D4) takes from the real answers: the conferences of a season and the conference of each team in it (#966).

The fixtures are real: the conferences and the standings of 2025/26 and 2026/27 (ESPN season 2026 and 2027), between which 27 teams changed conference (the summer of 2026: a new Pac-12,
the Atlantic Sun teams that went to the United Athletic Conference...).
"""
import pytest

from ncaa_helpers import fixture

from src.external.ncaa_page import NcaaPageError, parse_conferences, parse_standings


class TestConferences:
    def test_the_division_is_not_a_conference_and_each_one_has_its_id_name_and_short_name(self):
        conferences = parse_conferences(fixture("conferences_mens_2026"))
        assert "50" not in {c["id"] for c in conferences}                         # 50 is «Division I», the group of all of them
        acc = next(c for c in conferences if c["id"] == "2")
        assert (acc["name"], acc["short"]) == ("Atlantic Coast Conference", "ACC")
        assert len(conferences) == 31 and len({c["id"] for c in conferences}) == 31

    def test_a_new_conference_appears_in_the_season_it_exists(self):
        before = {c["id"]: c["short"] for c in parse_conferences(fixture("conferences_mens_2026"))}
        after = {c["id"]: c["short"] for c in parse_conferences(fixture("conferences_mens_2027"))}
        assert {k: v for k, v in after.items() if k not in before} == {"21": "Pac-12"} and set(before) <= set(after)

    @pytest.mark.parametrize("bad", [{}, {"conferences": []}, {"conferences": [{"name": "no id"}]}, [], "text"])
    def test_an_answer_that_is_not_a_list_of_conferences_is_an_error_not_an_empty_season(self, bad):
        with pytest.raises(NcaaPageError):
            parse_conferences(bad)


class TestStandings:
    def test_each_team_has_the_conference_it_played_in_that_season(self):
        teams = parse_standings(fixture("standings_mens_2026"))
        assert len(teams) == 365 and teams["2066"] == {"name": "Binghamton Bearcats", "conference_id": "1", "conference": "America East Conference"}
        assert all(t["conference_id"] and t["conference"] for t in teams.values())

    def test_a_team_that_changed_conference_has_the_old_one_in_the_old_season_and_the_new_one_in_the_new_one(self):
        """A real realignment (#966): team 278 played in the Mountain West in 2025/26 and in the new Pac-12 in 2026/27; the past is not rewritten."""
        old, new = parse_standings(fixture("standings_mens_2026")), parse_standings(fixture("standings_mens_2027"))
        assert (old["278"]["conference"], new["278"]["conference"]) == ("Mountain West Conference", "Pac-12 Conference")
        assert new["278"]["conference_id"] == "21" and old["278"]["conference_id"] != "21"
        moved = [t for t in old if t in new and old[t]["conference_id"] != new[t]["conference_id"]]
        assert len(moved) == 27

    def test_the_women_have_their_own_standings_with_the_same_conferences_by_name_but_not_always_by_id(self):
        """Real finding (#966): ESPN gives the Summit League the id 49 for the men and 47 for the women, so a conference is the same one across sexes by NAME, not by id."""
        men, women = parse_standings(fixture("standings_mens_2026")), parse_standings(fixture("standings_womens_2026"))
        by_name = lambda teams: {t["conference"]: t["conference_id"] for t in teams.values()}
        assert set(by_name(women)) == set(by_name(men)) and len(women) == 363
        assert (by_name(men)["Summit League"], by_name(women)["Summit League"]) == ("49", "47")
        assert sum(1 for name in by_name(men) if by_name(men)[name] != by_name(women)[name]) == 1

    @pytest.mark.parametrize("bad", [{}, {"children": []}, {"children": [{"id": "1"}]}, "text"])
    def test_an_answer_without_standings_is_an_error(self, bad):
        with pytest.raises(NcaaPageError):
            parse_standings(bad)
