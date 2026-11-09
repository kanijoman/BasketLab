"""The packages of FBCYL matches (issue #446, PR 2 of 3: the packages; the engine is #806 and the client of the app comes next).

Until now the publisher was FEB only: ``next_rounds`` said «solo FEB» for a FBCYL collection, the catalogue left FBCYL out of the packages and the index had no round of FBCYL, so the app had no
FBCYL match to follow. Rows of the real calendar of the group (``tests/fixtures/fbcyl_calendar_7298.json.gz``, 1ª División Femenina grupo A-1, read from the ESB API on 9/11/2026):

* a row becomes the same ``CalendarMatch`` as a FEB one: its code is ``fbcyl-<idMatch>`` (the ``adGameId`` the live feed needs only exists when the match is about to start: none of the 121 pending
  rows had it), its kick-off is ``matchDay`` (Madrid) and its teams the stable ids of the games;
* the next rounds are chosen with the same rule as in FEB (time decides, not the round);
* the packages are built without asking FEB for a roster: FBCYL team ids are not FEB team ids, and a roster fetched for them would be another team's;
* the index says the league and the competition of each round, as the FEB ones do, so the app lists it with the same filters.
"""
import gzip
import json
from datetime import datetime
from pathlib import Path

import pytest

from src.scraper.fbcyl_calendar import calendar_matches
from src.services.competition_catalogue import DEFAULT_CATALOGUE, fbcyl_groups, load_catalogue
from src.services.match_schedule_service import MatchScheduleService

FIXTURE = Path(__file__).parent / "fixtures" / "fbcyl_calendar_7298.json.gz"
NOW = datetime(2026, 11, 9, 12, 0)                                  # Madrid, the day the fixture was read
COLLECTION = "FBCYL_1ª_FASE-GRUPO_A-1_2026_"


@pytest.fixture(scope="module")
def rows():
    return json.loads(gzip.open(FIXTURE).read())["rows"]


def service(rows, **kw):
    return MatchScheduleService(object(), fetch_fbcyl_calendar=lambda group: calendar_matches(rows), fbcyl_groups={COLLECTION: "7298"}, now=lambda: NOW, **kw)


class TestTheCalendarOfAGroup:
    def test_every_row_is_a_match_with_the_code_the_kick_off_and_the_stable_team_ids(self, rows):
        matches = calendar_matches(rows)
        assert len(matches) == len(rows) == 156
        row = next(r for r in rows if str(r["state"]) != "1")
        match = next(m for m in matches if m.code == f"fbcyl-{row['idMatch']}")
        assert (match.home_id, match.away_id) == (str(row["idLocalTeam"]), str(row["idVisitorTeam"]))
        assert (match.home_name, match.away_name) == (row["nameLocalTeam"].strip(), row["nameVisitorTeam"].strip())
        assert match.kind == "scheduled" and match.start == row["matchDay"][:16].replace(" ", "T") and match.round_index == int(row["round"])

    def test_a_played_match_is_a_result_with_its_score(self, rows):
        played = next(r for r in rows if str(r["state"]) == "1")
        match = next(m for m in calendar_matches(rows) if m.code == f"fbcyl-{played['idMatch']}")
        assert match.kind == "result" and match.score == f"{played['localScore']}-{played['visitorScore']}"

    def test_the_codes_are_unique_and_never_look_like_a_feb_code(self, rows):
        codes = [m.code for m in calendar_matches(rows)]
        assert len(set(codes)) == len(codes) and all(c.startswith("fbcyl-") and not c.isdigit() for c in codes)

    def test_a_row_without_kick_off_is_left_without_start_and_the_calendar_still_reads(self, rows):
        odd = [{**r, "matchDay": None} if i == 0 else r for i, r in enumerate(rows)]
        assert calendar_matches(odd)[0].start is None and len(calendar_matches(odd)) == len(rows)


class TestTheNextRounds:
    def test_a_fbcyl_collection_has_next_rounds_chosen_like_the_feb_ones(self, rows):
        found = service(rows).next_rounds(COLLECTION)
        assert found["warning"] is None and found["rounds"]
        matches = [m for r in found["rounds"] for m in r["matches"]]
        starts = sorted(datetime.fromisoformat(m["start"]) for m in matches)
        assert starts[0] >= NOW and (starts[-1] - starts[0]).days < 5                  # the next block, not the whole season
        assert all(m["code"].startswith("fbcyl-") and m["home"]["id"].isdigit() and m["away"]["name"] for m in matches)

    def test_the_played_matches_are_not_listed(self, rows):
        played = {f"fbcyl-{r['idMatch']}" for r in rows if str(r["state"]) == "1"}
        assert not played & {m["code"] for r in service(rows).next_rounds(COLLECTION)["rounds"] for m in r["matches"]}

    def test_a_fbcyl_collection_the_catalogue_does_not_know_has_no_rounds_and_says_why(self, rows):
        found = service(rows).next_rounds("FBCYL_OTRA_2026_")
        assert found["rounds"] == [] and found["warning"]

    def test_a_calendar_that_cannot_be_read_is_a_warning_not_an_error(self, rows):
        def broken(_group):
            raise RuntimeError("ESB down")

        found = MatchScheduleService(object(), fetch_fbcyl_calendar=broken, fbcyl_groups={COLLECTION: "7298"}, now=lambda: NOW).next_rounds(COLLECTION)
        assert found["rounds"] == [] and "ESB down" in found["warning"]


class TestTheCatalogue:
    def test_the_active_fbcyl_groups_of_the_catalogue_are_listed_by_the_name_of_their_collection(self):
        groups = fbcyl_groups(load_catalogue(DEFAULT_CATALOGUE))
        assert sorted(groups.values()) == ["7298", "7299"]
        assert all(name.startswith("FBCYL_") for name in groups)


# --- the publisher ------------------------------------------------------------------------------------------------------------------------------------------------------------------

PASSWORD = "clave-larga-de-prueba"
CLUB = "1008631"                                                    # the FEB club of the staff: a FBCYL team id is never it


class _Rounds:
    """The service of a publication: the next rounds of each collection (the real one for FBCYL, a fixed answer for the others)."""

    def __init__(self, real, fixed=None):
        self._real, self._fixed = real, fixed or {}

    def next_rounds(self, collection):
        return self._fixed[collection] if collection in self._fixed else self._real.next_rounds(collection)


def _build(calls):
    from unittest.mock import MagicMock

    def build(db, collection, matches, club_team_id=None, roster_source=None, season=None, **rules):
        calls.append((collection, [m["code"] for m in matches]))
        package = MagicMock()
        package.dumps.return_value = json.dumps({"c": collection})
        return [{"match": {k: m[k] for k in ("code", "start", "round", "home", "away")}, "own_id": m["home"]["id"], "rival_id": m["away"]["id"], "is_club": False, "package": package}
                for m in matches]
    return build


class TestThePublisher:
    def test_a_fbcyl_round_is_published_with_its_codes_and_its_league_and_competition(self, rows, tmp_path):
        from src.live_prep.competition_info import fbcyl_infos, public
        from src.live_prep.publisher import publish_round_bundles

        infos = fbcyl_infos({COLLECTION: "7298"}, load_catalogue(DEFAULT_CATALOGUE), lambda group: rows, [CLUB])
        calls = []
        entries = publish_round_bundles(object(), tmp_path, PASSWORD, [COLLECTION], CLUB, service=service(rows), build=_build(calls), competitions=infos)
        assert entries and all(e["collection"] == COLLECTION and (tmp_path / e["file"]).exists() for e in entries)
        assert all(m["code"].startswith("fbcyl-") for e in entries for m in e["matches"]) and not any(e["club"] for e in entries)
        assert entries[0]["competition"]["league"] == "FBCYL" and entries[0]["competition"] == public(infos[COLLECTION])

    def test_the_packages_of_fbcyl_are_built_without_a_roster_from_feb_and_the_feb_ones_with_it(self, rows, tmp_path, monkeypatch):
        from src.live_prep import publisher
        from src.live_prep.roster_fetcher import fetch_rosters

        asked = {}

        def fake(handler, collection, matches, club_team_id=None, roster_source=None, **kw):
            asked[collection] = roster_source
            return []

        monkeypatch.setattr("src.live_prep.round_packages.build_round_packages_from_db", fake)
        feb = {"round": 4, "calendar_url": "u", "warning": None, "matches": [{"code": "1", "start": "2026-11-14T17:00", "round": 4, "home": {"id": "9001", "name": "A"}, "away": {"id": "9002", "name": "B"}}]}
        rounds = _Rounds(service(rows), {"LF_X": {"rounds": [feb], "calendar_url": "u", "warning": None}})
        publisher.publish_round_bundles(object(), tmp_path, PASSWORD, [COLLECTION, "LF_X"], CLUB, service=rounds)
        assert asked[COLLECTION] is None and asked["LF_X"] is fetch_rosters       # FBCYL team ids are not FEB team ids: a roster fetched for them would be another team's

    def test_only_the_fbcyl_collections_that_are_in_the_archive_are_published(self):
        from unittest.mock import MagicMock

        from src.live_prep.publisher import fbcyl_round_collections

        present = {sorted(fbcyl_groups(load_catalogue(DEFAULT_CATALOGUE)))[0]}                # one of the two groups has been scraped, the other not yet
        db = MagicMock()
        db.repository.connection.get_collection.side_effect = lambda name: MagicMock(find_one=MagicMock(return_value={"_id": 1} if name in present else None))
        assert fbcyl_round_collections(db, load_catalogue(DEFAULT_CATALOGUE)) == sorted(present)


class TestTheCompetitionOfAFbcylRound:
    def test_the_index_says_the_category_the_group_the_season_the_gender_and_the_league(self, rows):
        from src.live_prep.competition_info import fbcyl_infos, public

        info = fbcyl_infos({COLLECTION: "7298"}, load_catalogue(DEFAULT_CATALOGUE), lambda group: rows, [CLUB])[COLLECTION]
        assert (info["competition"], info["group"], info["season"]) == ("1ª DIVISION FEMENINA", "1ª FASE GRUPO A-1", "2026")
        assert (info["league"], info["gender"], info["level"], info["key"]) == ("FBCYL", "F", None, COLLECTION)
        assert info["rule_config"] == {"gender": "F"} and "clubs" not in public(info) and "rule_config" not in public(info)

    def test_a_calendar_that_cannot_be_read_still_gives_an_info_with_the_name_of_the_collection(self):
        from src.live_prep.competition_info import fbcyl_infos

        def broken(_group):
            raise RuntimeError("ESB down")

        info = fbcyl_infos({COLLECTION: "7298"}, load_catalogue(DEFAULT_CATALOGUE), broken, [CLUB])[COLLECTION]
        assert info["league"] == "FBCYL" and info["label"] == COLLECTION

    def test_a_feb_info_says_feb(self):
        from unittest.mock import MagicMock

        from src.live_prep.competition_info import competition_infos, normalize_catalog

        db = MagicMock()
        db.repository.connection.get_collection.return_value.find_one.return_value = None
        assert competition_infos(db, ["LF_X"], normalize_catalog([]), [CLUB])["LF_X"]["league"] == "FEB"
