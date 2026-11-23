"""The club competitions of FIBA in the catalogue (#1039, D6b of epic #872): the EuroLeague Women and the EuroCup Women.

The spike of 23/11/2026 found them in ``fiba.basketball`` under the SHORT name of the season (``euroleague-women-25-26``, not ``-2025-26``, which the page answers with its generic shell) and read by the
FIBA source that already exists. Only 3 seasons exist (2024/25 onwards). The pages here are the REAL ones (``tests/fixtures/fiba``): the event of the EuroLeague Women 2025/26 (110 games), the one of the
EuroCup Women 2025/26 (216) and the shell the site answers for a season that does not exist.
"""
import json
import sys
from pathlib import Path

import pytest
from fiba_helpers import Clock, Site, flight, html_of

from src.external.fiba_catalogue import candidate_club_events, new_entries
from src.external.fiba_client import FibaClient
from src.services.competition_catalogue import external_collections, load_catalogue

TODAY = "23/11/2026"
ROOT = Path(__file__).resolve().parents[1]


def real_site():
    """The real pages: two events that exist and, for anything else, the shell the site gives for a season that is not there."""
    return Site({"/events/euroleague-women-25-26": html_of(flight("euroleague-women-25-26")), "/events/eurocup-women-25-26": html_of(flight("eurocup-women-25-26"))},
                default=html_of(flight("euroleague-women-23-24")))


def client(site):
    clock = Clock()
    return FibaClient(fetch=site.fetch, sleep=clock.sleep, clock=clock.time)


class TestTheCandidates:
    def test_a_season_has_the_euroleague_women_and_the_eurocup_women_with_the_short_name_of_the_season(self):
        found = candidate_club_events([2025])
        assert [c["event"] for c in found] == ["euroleague-women-25-26", "eurocup-women-25-26"]
        assert [c["competition"] for c in found] == ["EuroLeague Women", "EuroCup Women"]
        assert all(c["gender"] == "F" and c["division"] == "Senior" and "category" not in c for c in found)

    def test_the_season_is_told_the_way_feb_does_by_the_year_it_starts_in(self):
        [first, _] = candidate_club_events([2025])
        assert (first["season_value"], first["season_label"]) == ("2025", "2025/2026")

    @pytest.mark.parametrize("year,slug", [(2024, "euroleague-women-24-25"), (2026, "euroleague-women-26-27"), (2009, "euroleague-women-09-10"), (2099, "euroleague-women-99-00"), (2000, "euroleague-women-00-01")])
    def test_the_short_name_is_two_digits_at_the_boundaries_too(self, year, slug):
        assert candidate_club_events([year])[0]["event"] == slug

    def test_several_seasons_come_in_a_stable_order(self):
        found = candidate_club_events([2024, 2025])
        assert len(found) == 4 and found == candidate_club_events([2024, 2025]) and found[0]["season_value"] == "2024" and found[-1]["season_value"] == "2025"


class TestWithTheRealPagesOfFiba:
    def test_the_events_that_exist_are_added_paused_with_their_real_number_of_games(self):
        entries, report = new_entries(client(real_site()), [], [], TODAY, club_seasons=[2025])
        assert [e["fiba"]["event"] for e in entries] == ["euroleague-women-25-26", "eurocup-women-25-26"] and all(e["active"] is False for e in entries)
        assert " 110 games" in entries[0]["note"] and " 216 games" in entries[1]["note"] and report["failed"] == {}

    def test_a_season_that_does_not_exist_gets_the_shell_of_the_page_and_adds_nothing(self):
        """The site answers a made-up season with a page of 5 «games» with no teams and no link, always the same: it is not an event."""
        entries, report = new_entries(client(real_site()), [], [], TODAY, club_seasons=[2023])
        assert entries == [] and sorted(report["empty"]) == ["eurocup-women-23-24", "euroleague-women-23-24"]

    def test_the_long_name_of_the_season_that_was_tried_first_is_the_shell_too(self):
        from fiba_helpers import Site as FibaSite

        shell = FibaSite({}, default=html_of(flight("euroleague-women-23-24")))
        [games] = [client(shell).event_games("euroleague-women-2025-26")]
        assert len(games) == 5 and not any(g["teams"] or g["slug"] for g in games)

    def test_the_entries_are_valid_ones_of_the_catalogue_and_the_two_sexes_of_fiba_do_not_clash(self, tmp_path):
        entries, _ = new_entries(client(real_site()), [], [], TODAY, club_seasons=[2025])
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": entries}, ensure_ascii=False), encoding="utf-8")
        loaded = load_catalogue(path)
        assert [e["gender"] for e in loaded] == ["F", "F"] and external_collections(loaded) == {}           # paused: nothing is read yet
        names = list(external_collections([{**e, "active": True} for e in loaded]))
        assert len(names) == len(set(names)) == 2 and all(n.startswith("FIBA_") and n.endswith("_2025_") for n in names)

    def test_what_is_already_in_the_catalogue_is_not_asked_for_again(self):
        entries, _ = new_entries(client(real_site()), [], [], TODAY, club_seasons=[2025])
        site = real_site()
        again, report = new_entries(client(site), entries, [], TODAY, club_seasons=[2025])
        assert again == [] and sorted(report["already"]) == ["eurocup-women-25-26", "euroleague-women-25-26"] and site.requests == []


class TestTheCommand:
    @pytest.fixture()
    def cli(self):
        sys.path.insert(0, str(ROOT))
        import run_fiba_catalogue

        return run_fiba_catalogue

    def catalogue(self, tmp_path):
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": []}, indent=2) + "\n", encoding="utf-8")
        return path

    def test_a_club_season_is_added_with_its_own_option_and_a_second_run_changes_nothing(self, cli, tmp_path):
        path = self.catalogue(tmp_path)
        assert cli.main(["--catalogue", str(path), "--club-season", "2025"], client=client(real_site()), today=TODAY) == 0
        data = json.loads(path.read_text(encoding="utf-8"))["competitions"]
        assert [e["fiba"]["event"] for e in data] == ["euroleague-women-25-26", "eurocup-women-25-26"]
        once = path.read_bytes()
        assert cli.main(["--catalogue", str(path), "--club-season", "2025"], client=client(real_site()), today=TODAY) == 0 and path.read_bytes() == once

    def test_a_dry_run_says_what_it_would_add_and_writes_nothing(self, cli, tmp_path, capsys):
        path = self.catalogue(tmp_path)
        before = path.read_bytes()
        assert cli.main(["--catalogue", str(path), "--club-season", "2025", "--dry-run"], client=client(real_site()), today=TODAY) == 0
        assert path.read_bytes() == before and "would add: euroleague-women-25-26" in capsys.readouterr().out

    def test_the_events_of_the_national_teams_and_the_club_seasons_can_go_together(self, cli, tmp_path):
        path = self.catalogue(tmp_path)
        assert cli.main(["--catalogue", str(path), "--year", "2031", "--club-season", "2025"], client=client(real_site()), today=TODAY) == 0
        assert len(json.loads(path.read_text(encoding="utf-8"))["competitions"]) == 2

    def test_it_needs_a_year_or_a_club_season(self, cli, tmp_path):
        with pytest.raises(SystemExit):
            cli.main(["--catalogue", str(self.catalogue(tmp_path))])


class TestTheyAreActivatedTheSameWayAsTheRest:
    """``run_catalogue_activate.py --league fiba``: the paused events of a season are turned on, nothing else (#1039)."""

    def test_the_tool_activates_the_paused_club_events_of_a_season_and_only_those(self, tmp_path):
        sys.path.insert(0, str(ROOT))
        import run_catalogue_activate

        entries, _ = new_entries(client(real_site()), [], [], TODAY, club_seasons=[2025])
        other = {"competition": "EuroBasket Women", "season_label": "2025", "season_value": "2025", "league": "fiba", "division": "Senior", "gender": "F", "active": False,
                 "fiba": {"event": "fiba-womens-eurobasket-2025"}}
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps({"competitions": [*entries, {**other, "season_value": "2026", "season_label": "2026", "fiba": {"event": "fiba-womens-eurobasket-2026"}}]}, ensure_ascii=False), encoding="utf-8")
        assert run_catalogue_activate.main(["--catalogue", str(path), "--season", "2025", "--league", "fiba"]) == 0
        loaded = {e["fiba"]["event"]: e["active"] for e in load_catalogue(path)}
        assert loaded == {"euroleague-women-25-26": True, "eurocup-women-25-26": True, "fiba-womens-eurobasket-2026": False}
