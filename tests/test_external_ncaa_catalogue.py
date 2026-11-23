"""The NCAA D1 competitions of the catalogue (#888, D4; #966): one competition per conference, season and sex, paused, from what ESPN lists for the season.

The competition is named by its sex («D1 Men» / «D1 Women»): a collection name has no gender (`NCAA_D1_2025_SEC`) and the SEC of both sexes would be one collection. The season is the year it
STARTS in, as FEB's (2025 = 2025/26); ESPN's is the year it ends in. Real answers: the conferences of 2025/26 and 2026/27 (a new Pac-12 in the second one).
"""
import json

from ncaa_helpers import Clock, Site, text

from src.external.ncaa_catalogue import new_entries
from src.external.ncaa_client import NcaaClient, NcaaFetchError
from src.services.competition_catalogue import external_collections, load_catalogue

TODAY = "23/11/2026"


def site():
    return Site({"/mens-college-basketball/scoreboard/conferences?season=2026": text("conferences_mens_2026"), "/womens-college-basketball/scoreboard/conferences?season=2026": text("conferences_womens_2026"),
                 "/mens-college-basketball/scoreboard/conferences?season=2027": text("conferences_mens_2027"), "/womens-college-basketball/scoreboard/conferences?season=2027": text("conferences_womens_2027")})


def entries(seasons, existing=(), fake=None):
    clock = Clock()
    fake = fake or site()
    return new_entries(NcaaClient(fetch=fake.fetch, sleep=clock.sleep, clock=clock.time), list(existing), TODAY, seasons)


def test_a_season_gives_one_paused_entry_per_conference_and_sex():
    found, report = entries([2025])
    assert len(found) == 62 and all(e["active"] is False and e["league"] == "ncaa" and e["division"] == "D1" for e in found)
    assert {e["gender"] for e in found} == {"M", "F"} and {e["competition"] for e in found} == {"D1 Men", "D1 Women"}
    assert report["failed"] == {}


def test_the_entry_says_its_season_the_way_feb_does_and_keeps_the_id_of_its_conference():
    found, _ = entries([2025])
    acc = next(e for e in found if e["gender"] == "F" and e["conference"] == "ACC")
    assert (acc["season_label"], acc["season_value"]) == ("2025/2026", "2025") and acc["ncaa"] == {"conference_id": "2"}


def test_the_summit_league_has_the_id_of_each_sex_but_is_one_conference_by_name():
    """Real finding (#966): ESPN says 49 for the men and 47 for the women: the entry keeps the id of its sex and the conference text is the same."""
    found, _ = entries([2025])
    summit = {e["gender"]: e for e in found if e["conference"] == "Summit"}
    assert (summit["M"]["ncaa"]["conference_id"], summit["F"]["ncaa"]["conference_id"]) == ("49", "47")


def test_a_conference_that_did_not_exist_yet_has_no_entry_in_the_earlier_season_and_has_it_in_the_later_one():
    """The new Pac-12 (id 21) exists in 2026/27 only: realignments do not rewrite the past (#966)."""
    old, _ = entries([2025])
    new, _ = entries([2026])
    assert not [e for e in old if e["conference"] == "Pac-12"] and {e["gender"] for e in new if e["conference"] == "Pac-12"} == {"M", "F"}
    assert len(new) == 64


def test_the_men_and_the_women_of_a_conference_are_two_different_collections():
    found, _ = entries([2025])
    names = list(external_collections([{**e, "active": True} for e in found]).keys())            # only the active ones have a collection
    assert len(names) == len(set(names)) == 62 and sum(1 for n in names if n.endswith("_SEC")) == 2


def test_what_the_catalogue_already_has_is_left_alone_and_not_even_asked_for():
    first, _ = entries([2025])
    fake = site()
    again, report = entries([2025], existing=first, fake=fake)
    assert again == [] and len(report["already"]) == 62 and len(fake.requests) == 2           # the conferences of each sex, once: nothing else


def test_a_sex_that_cannot_be_read_is_reported_and_the_other_one_is_added():
    fake = Site({"/mens-college-basketball/scoreboard/conferences?season=2026": text("conferences_mens_2026"),
                 "/womens-college-basketball/scoreboard/conferences?season=2026": NcaaFetchError("down")})
    found, report = entries([2025], fake=fake)
    assert {e["gender"] for e in found} == {"M"} and "F" in report["failed"] and "down" in report["failed"]["F"]


def test_the_entries_pass_the_validation_of_the_catalogue(tmp_path):
    found, _ = entries([2025])
    path = tmp_path / "competitions.json"
    path.write_text(json.dumps({"competitions": found}, ensure_ascii=False), encoding="utf-8")
    assert len(load_catalogue(path)) == 62                 # `conference` is required in NCAA and two entries of a season with another conference are other competitions


class TestTheScriptThatAddsThem:
    """``python run_ncaa_catalogue.py --season 2025 [--dry-run]``: it adds what is missing, paused, and a second run does not move a byte."""

    def run(self, path, *argv, fake=None):
        import run_ncaa_catalogue

        clock = Clock()
        fake = fake or site()
        return run_ncaa_catalogue.main(["--catalogue", str(path), *argv], client=NcaaClient(fetch=fake.fetch, sleep=clock.sleep, clock=clock.time), today=TODAY)

    def catalogue(self, tmp_path):
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": [{"competition": "PRIMERA FEB", "season_label": "2025/2026", "season_value": "2025", "league": "feb"}]}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_it_adds_the_paused_entries_after_what_was_there_and_touches_nothing_else(self, tmp_path, capsys):
        path = self.catalogue(tmp_path)
        assert self.run(path, "--season", "2025") == 0
        data = json.loads(path.read_text(encoding="utf-8"))["competitions"]
        assert data[0]["competition"] == "PRIMERA FEB" and len(data) == 63 and all(e["active"] is False for e in data[1:])
        assert "adds: 62" in capsys.readouterr().out

    def test_a_second_run_does_not_change_a_byte(self, tmp_path):
        path = self.catalogue(tmp_path)
        self.run(path, "--season", "2025")
        before = path.read_bytes()
        assert self.run(path, "--season", "2025") == 0 and path.read_bytes() == before

    def test_a_dry_run_says_what_it_would_add_and_writes_nothing(self, tmp_path, capsys):
        path = self.catalogue(tmp_path)
        before = path.read_bytes()
        assert self.run(path, "--season", "2025", "--dry-run") == 0 and path.read_bytes() == before
        assert "would add: 62" in capsys.readouterr().out

    def test_a_sex_that_fails_is_said_and_the_exit_code_is_one_while_what_could_be_added_is_added(self, tmp_path, capsys):
        path = self.catalogue(tmp_path)
        fake = Site({"/mens-college-basketball/scoreboard/conferences?season=2026": text("conferences_mens_2026"), "/womens-college-basketball/scoreboard/conferences?season=2026": NcaaFetchError("down")})
        assert self.run(path, "--season", "2025", fake=fake) == 1
        assert len(json.loads(path.read_text(encoding="utf-8"))["competitions"]) == 32 and "FAILED: F" in capsys.readouterr().out
