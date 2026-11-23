"""Issue #1052: every scheduled `Archive refresh` came out red after the load of 2021 and 2020 (20/11/2026).

Bug: the catalogue held the Mini clubs championships (`C ESP CLUBES MINI FEM|MASC`) for 2021/22 and 2020/21 as active `groups: all`, but the federation lists NO group for them before 2022
(measured on 23/11/2026: 15 groups for 2022, none for 2021 and 2020; the page answers 500), so `expand_entries` raised on each of the four, and the whole refresh ended in failure forever
although every other competition was saved.
"""
import pytest

from src.services.competition_refresh import expand_entries, load_config

# What the federation answers for the competitions that do not exist before 2022: the groups of a season, nothing earlier.
FIRST_SEASON = {"C ESP CLUBES MINI FEM": 2022, "C ESP CLUBES MINI MASC": 2022}


class Federation:
    """The groups page of the federation, as measured: a competition has groups only from its first season."""

    def get_groups_for_season(self, url, season_value):
        entry = next(e for e in self.entries if e.competition_url == url)
        return [("Group A", "1")] if int(season_value) >= FIRST_SEASON.get(entry.competition_label, 0) else []


def test_no_active_competition_of_the_catalogue_is_one_the_federation_lists_no_groups_for():
    entries = load_config()
    federation = Federation()
    federation.entries = entries
    expand_entries([e for e in entries if e.competition_label in FIRST_SEASON], federation)         # raises «FEB no lista grupos…» for a season that does not exist


@pytest.mark.parametrize("label", sorted(FIRST_SEASON))
def test_the_seasons_that_do_exist_are_still_refreshed(label):
    seasons = {e.season_value for e in load_config() if e.competition_label == label}
    assert {"2022", "2023", "2024", "2025"} <= seasons
