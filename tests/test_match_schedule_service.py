"""Upcoming / live matches of a team from the FEB calendar (issue #119)."""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from db_helpers import new_mock_db

from src.scraper.calendar_parser import parse_calendar
from src.services.match_schedule_service import MatchScheduleService, normalize_name

HTML = (Path(__file__).parent / "fixtures" / "feb_calendar_snippet.html").read_bytes()
ALL = parse_calendar(HTML)
SCHED = [m for m in ALL if m.kind == "scheduled"]
TEAM = SCHED[0].home_id                      # plays one of the scheduled matches
NOW = datetime.fromisoformat(SCHED[0].start)  # kick-off of the first scheduled match


def _db(competition="LF CHALLENGE", season="2026", codes=(2524697, 2524698, 2524699), meta=None):
    games = new_mock_db()["LF_CHALLENGE_2026"]
    if codes:
        games.insert_many([{"_id": c, "_competition": competition, "_season": season} for c in codes])
    metas = new_mock_db()["COLLECTION_META"]
    if meta:
        metas.insert_one(meta)
    db = MagicMock()
    db.repository.connection.get_collection.side_effect = lambda name: metas if name == "COLLECTION_META" else games
    return db


COMPETITIONS = [
    {"name": "LF ENDESA", "results_url": "https://baloncestoenvivo.feb.es/calendario.aspx?g=4&t=2026&nm=lfendesa"},
    {"name": "LF CHALLENGE", "results_url": "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"},
]


def _service(db=None, calendar=ALL, status=None, now=NOW, competitions=COMPETITIONS):
    return MatchScheduleService(
        db or _db(), fetch_calendar=lambda url: calendar,
        match_status=status or (lambda code: "scheduled"), now=lambda: now,
        competitions=lambda: competitions)


class TestCalendarUrl:
    @pytest.mark.parametrize("name, norm", [("LF CHALLENGE", "lfchallenge"), ("LF2", "lf2"), ("Liga Endesa", "ligaendesa"),
                                            ("LEB  ORO", "leboro"), ("Primera FEB", "primerafeb")])
    def test_names_are_compared_without_case_spaces_or_accents(self, name, norm):
        assert normalize_name(name) == norm

    def test_looked_up_by_competition_name_in_febs_list_with_the_games_season(self):
        """FEB's calendar address needs its internal competition id (g=67), not derivable from our games."""
        url = _service().calendar_url("LF_CHALLENGE_2026")
        assert url == "https://baloncestoenvivo.feb.es/calendario.aspx?g=67&t=2026&nm=lfchallenge"

    def test_the_season_comes_from_the_collection_not_from_the_current_one(self):
        url = _service(_db(season="2024")).calendar_url("LF_CHALLENGE_2026")
        assert "t=2024" in url and "g=67" in url

    def test_stored_metadata_wins_over_the_lookup(self):
        meta = {"_id": "LF_CHALLENGE_2026", "competition_url": "https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2030&nm=otra"}
        assert _service(_db(meta=meta)).calendar_url("LF_CHALLENGE_2026").endswith("nm=otra")

    def test_unknown_when_the_competition_is_not_in_febs_list(self):
        assert _service(competitions=[COMPETITIONS[0]]).calendar_url("LF_CHALLENGE_2026") is None

    def test_unknown_when_febs_list_cannot_be_read(self):
        def boom():
            raise ConnectionError("feb down")

        svc = MatchScheduleService(_db(), fetch_calendar=lambda u: ALL, competitions=boom, now=lambda: NOW)
        assert svc.calendar_url("LF_CHALLENGE_2026") is None

    def test_unknown_when_the_collection_has_no_games_or_metadata(self):
        assert _service(_db(codes=())).calendar_url("LF_CHALLENGE_2026") is None


class TestUpcoming:
    def test_lists_the_scheduled_matches_of_the_team(self):
        out = _service().upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["warning"] is None
        m = out["matches"][0]
        assert m["code"] == SCHED[0].code and m["status"] == "scheduled"
        assert m["opponent"] == {"id": SCHED[0].away_id, "name": SCHED[0].away_name} and m["is_home"] is True
        assert m["start"] == SCHED[0].start and m["starts_in_min"] == 0

    def test_other_teams_matches_are_not_listed(self):
        out = _service().upcoming("LF_CHALLENGE_2026", TEAM)
        assert all(TEAM in (m["home"]["id"], m["away"]["id"]) for m in out["matches"])

    def test_sorted_by_kick_off_and_limited(self):
        cal = [type(m)(**{**m.__dict__, "start": f"2027-0{i + 1}-10T18:00"}) for i, m in enumerate(SCHED)]
        # make the same team play all three
        cal = [type(m)(**{**m.__dict__, "home_id": TEAM}) for m in cal]
        out = _service(calendar=cal, now=datetime(2026, 12, 1)).upcoming("LF_CHALLENGE_2026", TEAM, limit=2)
        assert [m["start"][:7] for m in out["matches"]] == ["2027-01", "2027-02"]

    def test_matches_that_started_long_ago_are_dropped(self):
        out = _service(now=datetime(2030, 1, 1)).upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"] == []

    def test_a_match_that_just_started_is_kept(self):
        out = _service(now=NOW.replace(minute=(NOW.minute + 30) % 60)).upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"]

    def test_a_result_row_not_in_the_database_is_checked_and_listed_when_live(self):
        cal = [type(m)(**{**m.__dict__, "home_id": TEAM}) for m in ALL]  # round-1 results involve TEAM too
        calls = []

        def status(code):
            calls.append(code)
            return "live" if code == "2524699" else "finished"

        db = _db(codes=(2524697, 2524698))  # 2524699 is not stored yet
        out = _service(db, calendar=cal, status=status).upcoming("LF_CHALLENGE_2026", TEAM)
        live = [m for m in out["matches"] if m["status"] == "live"]
        assert [m["code"] for m in live] == ["2524699"] and out["matches"][0]["status"] == "live"
        assert "2524697" not in calls and "2524698" not in calls  # already in the DB: never asked

    def test_status_lookups_are_capped_and_failures_tolerated(self):
        cal = [type(m)(**{**m.__dict__, "home_id": TEAM}) for m in ALL[:3]] * 5
        calls = []

        def status(code):
            calls.append(code)
            raise ConnectionError("feb down")

        out = _service(_db(codes=()), calendar=cal, status=status).upcoming("LF_CHALLENGE_2026", TEAM)
        assert len(calls) <= 3 and out["matches"] == [] or all(m["status"] != "live" for m in out["matches"])

    # -- issue #118: during the real Zamora - Leon match the calendar row stayed "scheduled" (no score) from kick-off
    # until well after the final whistle, so a match in progress looked like an upcoming one with negative minutes.

    def _started(self, minutes_after, status):
        calls = []

        def ask(code):
            calls.append(code)
            if isinstance(status, Exception):
                raise status
            return status

        now = NOW + __import__("datetime").timedelta(minutes=minutes_after)
        out = _service(now=now, status=ask).upcoming("LF_CHALLENGE_2026", TEAM)
        return out["matches"], calls

    def test_a_scheduled_row_that_already_kicked_off_is_live_when_febs_api_says_so_regression(self):
        matches, calls = self._started(45, "live")
        assert matches[0]["code"] == SCHED[0].code and matches[0]["status"] == "live"
        assert calls == [SCHED[0].code]

    def test_a_finished_match_that_the_calendar_still_shows_as_scheduled_is_dropped_regression(self):
        matches, _ = self._started(150, "finished")
        assert SCHED[0].code not in [m["code"] for m in matches]

    def test_a_match_whose_start_is_delayed_stays_scheduled(self):
        matches, _ = self._started(10, "scheduled")  # FEB answers 404: not started yet
        assert matches[0]["code"] == SCHED[0].code and matches[0]["status"] == "scheduled"

    def test_if_febs_api_fails_the_row_stays_scheduled_instead_of_disappearing(self):
        matches, _ = self._started(45, ConnectionError("feb down"))
        assert matches[0]["code"] == SCHED[0].code and matches[0]["status"] == "scheduled"

    def test_matches_that_have_not_started_never_trigger_a_lookup(self):
        matches, calls = self._started(-60, "live")
        assert calls == [] and all(m["status"] == "scheduled" for m in matches)

    def test_calendar_failure_is_reported_as_a_warning_not_raised(self):
        def boom(url):
            raise ConnectionError("calendario no disponible")

        svc = MatchScheduleService(_db(), fetch_calendar=boom, match_status=lambda c: "scheduled", now=lambda: NOW)
        out = svc.upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"] == [] and "calendario" in out["warning"].lower()

    def test_team_missing_from_the_calendar_warns(self):
        out = _service().upcoming("LF_CHALLENGE_2026", "999")
        assert out["matches"] == [] and "no aparece" in out["warning"].lower()

    def test_unknown_calendar_url_warns(self):
        out = _service(_db(codes=())).upcoming("LF_CHALLENGE_2026", TEAM)
        assert out["matches"] == [] and out["warning"]

    def test_fbcyl_collections_are_not_supported(self):
        out = _service().upcoming("FBCYL_1A_2026", TEAM)
        assert out["matches"] == [] and "FEB" in out["warning"]


class TestNextRound:
    """Every match of the next round of a competition, not only the club's (issues #286, #172)."""

    def test_the_matches_of_the_earliest_round_that_has_matches_to_play(self):
        out = _service().next_round("LF_CHALLENGE_2026")
        upcoming = [m for m in SCHED if m.start and datetime.fromisoformat(m.start) >= NOW - timedelta(hours=3)]
        first = min(m.round_index for m in upcoming)
        expected = [m.code for m in upcoming if m.round_index == first]
        assert out["round"] == first and [m["code"] for m in out["matches"]] == expected
        assert out["warning"] is None and out["calendar_url"]

    def test_a_match_has_what_the_package_and_the_index_need(self):
        match = _service().next_round("LF_CHALLENGE_2026")["matches"][0]
        assert set(match) == {"code", "start", "round", "home", "away"}
        assert match["home"]["id"] and match["home"]["name"] and match["away"]["id"]

    def test_played_matches_are_not_listed(self):
        calendar = [m for m in ALL if m.kind == "result"] + SCHED
        out = _service(calendar=calendar).next_round("LF_CHALLENGE_2026")
        assert all(m["code"] in {s.code for s in SCHED} for m in out["matches"])

    def test_without_a_calendar_it_is_empty_with_a_warning_and_never_raises(self):
        def boom(url):
            raise ConnectionError("calendario no disponible")

        svc = MatchScheduleService(_db(), fetch_calendar=boom, now=lambda: NOW, competitions=lambda: COMPETITIONS)
        out = svc.next_round("LF_CHALLENGE_2026")
        assert out["round"] is None and out["matches"] == [] and "calendario" in out["warning"].lower()
        assert _service(_db(codes=())).next_round("LF_CHALLENGE_2026")["matches"] == []
        assert _service().next_round("FBCYL_1A_2026")["matches"] == []


class TestGroupCalendar:
    """A competition page shows ONE group (2ª FEB: the A one, whatever the group of the collection) (issue #449).

    Found checking 2ª FEB and 3ª FEB: ``competition_url`` is the same for groups A and B, so the calendar of the collection of group B was the
    one of group A and ``next_round`` would have published the wrong round. The calendar of a collection with a stored group is read selecting
    that group (``season_value`` / ``group_value`` of ``COLLECTION_META``); collections without it keep reading the page as it is.
    """

    URL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2026&nm=segundafeb"
    META = {"_id": "LF_CHALLENGE_2026", "competition_url": URL, "season_value": "2026", "group_value": "90000"}

    @staticmethod
    def service(db, default=(), groups=None, calls=None):
        def group(url, season, group_value):
            if calls is not None:
                calls.append((url, season, group_value))
            if isinstance(groups, Exception):
                raise groups
            return groups[group_value]

        return MatchScheduleService(db, fetch_calendar=lambda url: list(default), fetch_group_calendar=group,
                                    match_status=lambda code: "scheduled", now=lambda: NOW, competitions=lambda: COMPETITIONS)

    def test_a_collection_with_a_group_reads_the_calendar_of_that_group_not_the_default_one(self):
        calls = []
        svc = self.service(_db(meta=self.META), default=[], groups={"90000": ALL}, calls=calls)
        found = svc.upcoming("LF_CHALLENGE_2026", TEAM)
        assert found["matches"] and found["warning"] is None
        assert calls == [(self.URL, "2026", "90000")]
        assert found["calendar_url"] == self.URL                        # the link for people stays the one of the competition

    def test_next_round_of_the_group_is_the_round_of_that_group(self):
        other = [m for m in ALL if m.kind != "scheduled"]
        svc = self.service(_db(meta=self.META), default=ALL, groups={"90000": other})
        assert svc.next_round("LF_CHALLENGE_2026")["matches"] == []     # the default calendar (ALL) would have given matches

    def test_a_collection_without_a_stored_group_reads_the_page_as_before(self):
        meta = {"_id": "LF_CHALLENGE_2026", "competition_url": self.URL}
        calls = []
        svc = self.service(_db(meta=meta), default=ALL, groups={}, calls=calls)
        assert svc.upcoming("LF_CHALLENGE_2026", TEAM)["matches"] and calls == []
        assert self.service(_db(), default=ALL, groups={}, calls=calls).next_round("LF_CHALLENGE_2026")["matches"] and calls == []

    def test_a_group_that_cannot_be_read_is_a_warning_and_never_the_calendar_of_another_group(self):
        svc = self.service(_db(meta=self.META), default=ALL, groups=ConnectionError("feb down"))
        found = svc.upcoming("LF_CHALLENGE_2026", TEAM)
        assert found["matches"] == [] and "No se pudo leer el calendario" in found["warning"]
        assert svc.next_round("LF_CHALLENGE_2026")["matches"] == []


def _cm(code, rnd, start, kind="scheduled", home=None, away=None):
    from src.scraper.calendar_parser import CalendarMatch

    return CalendarMatch(code=str(code), kind=kind, round_index=rnd, home_id=str(home or f"h{code}"), home_name=f"H{code}",
                         away_id=str(away or f"a{code}"), away_name=f"A{code}", start=start, score="70-60" if kind == "result" else None)


def _rounds(calendar, now="2026-10-21T10:00"):
    out = _service(calendar=calendar, now=datetime.fromisoformat(now)).next_rounds("LF_CHALLENGE_2026")
    return {r["round"]: [m["code"] for m in r["matches"]] for r in out["rounds"]}, out


class TestNextRounds:
    """The next matches grouped by round: postponed AND advanced matches count (issue #450).

    Found with the real calendars of 2ª FEB B (a round-1 match postponed to December won ``next_round`` over round 4, which would have published
    1 match) and LF Challenge (round 4 carried a match of 21/12). A round is the pending matches of ONE round that are no more than
    ``ROUND_GAP_DAYS`` (3) apart from each other (a match weeks later is a postponement of its own); the rounds published are those whose
    first match starts within ``ROUND_START_DAYS`` (5) of the next kick-off: advanced and midweek rounds come along, the round of the next
    weekend (6-7 days later) does not, not even partly.
    """

    WEEKEND = [_cm(i, 4, f"2026-10-24T{17 + i % 3}:00") for i in range(1, 6)] + [_cm(6, 4, "2026-10-25T12:00"), _cm(7, 4, "2026-10-25T18:00")]

    def test_a_normal_weekend_is_one_round(self):
        rounds, out = _rounds(self.WEEKEND)
        assert rounds == {4: ["1", "2", "3", "4", "5", "6", "7"]} and out["warning"] is None and out["calendar_url"]

    def test_a_match_postponed_to_weeks_later_is_not_the_round_regression(self):
        """2ª FEB B on 21/10/2026: a round-1 match postponed to 09/12 and round 4 on 24-25/10."""
        rounds, _ = _rounds(self.WEEKEND + [_cm(90, 1, "2026-12-09T20:00")])
        assert rounds == {4: ["1", "2", "3", "4", "5", "6", "7"]}

    def test_a_match_of_the_round_postponed_to_weeks_later_is_left_out_of_it_regression(self):
        """LF Challenge on 21/10/2026: round 4 with a match on 21/12."""
        rounds, _ = _rounds(self.WEEKEND + [_cm(91, 4, "2026-12-21T20:45")])
        assert rounds == {4: ["1", "2", "3", "4", "5", "6", "7"]}

    def test_the_next_weekend_round_is_not_published_not_even_partly_regression(self):
        """A window of 7 days from the first match reached the first two matches of the following round (2ª FEB A: 'round 5: 2 matches')."""
        next_weekend = [_cm(20, 5, "2026-10-31T18:00"), _cm(21, 5, "2026-10-31T19:00"), _cm(22, 5, "2026-11-01T12:00")]
        rounds, _ = _rounds(self.WEEKEND + next_weekend)
        assert list(rounds) == [4]

    def test_matches_advanced_to_the_same_weekend_are_their_own_round(self):
        """Teams that play two rounds in a weekend to save a long trip: round 12 with 2 matches next to round 4; the rest of round 12 is later."""
        advanced = [_cm(40, 12, "2026-10-24T20:00"), _cm(41, 12, "2026-10-25T12:00"), _cm(42, 12, "2026-12-12T18:00"), _cm(43, 12, "2026-12-12T19:00")]
        rounds, _ = _rounds(self.WEEKEND + advanced)
        assert rounds == {4: ["1", "2", "3", "4", "5", "6", "7"], 12: ["40", "41"]}

    def test_a_postponed_match_a_few_days_before_the_weekend_comes_along_as_its_own_round(self):
        rounds, _ = _rounds([_cm(90, 1, "2026-10-21T20:00")] + self.WEEKEND)
        assert list(rounds) == [1, 4] and rounds[1] == ["90"]

    def test_a_midweek_round_and_the_weekend_round_after_it_are_published_together(self):
        midweek = [_cm(i, 3, "2026-10-20T20:00") for i in range(60, 64)] + [_cm(64, 3, "2026-10-21T20:30")]
        rounds, _ = _rounds(midweek + self.WEEKEND, now="2026-10-20T10:00")
        assert list(rounds) == [3, 4]

    def test_the_midweek_round_after_a_weekend_comes_with_it_but_the_following_weekend_does_not(self):
        midweek = [_cm(i, 5, "2026-10-28T20:00") for i in range(60, 64)]
        later = [_cm(i, 6, "2026-10-31T18:00") for i in range(70, 74)]
        rounds, _ = _rounds(self.WEEKEND + midweek + later)
        assert list(rounds) == [4, 5]

    def test_a_tournament_of_a_few_days_with_several_rounds_is_published_whole(self):
        """Copa de España, group stage: 4 teams, 3 rounds of 2 matches in the same weekend."""
        cup = [_cm(1, 1, "2026-10-24T10:00"), _cm(2, 1, "2026-10-24T12:00"), _cm(3, 2, "2026-10-24T17:00"), _cm(4, 2, "2026-10-24T19:00"),
               _cm(5, 3, "2026-10-25T10:00"), _cm(6, 3, "2026-10-25T12:00")]
        rounds, _ = _rounds(cup)
        assert rounds == {1: ["1", "2"], 2: ["3", "4"], 3: ["5", "6"]}

    def test_a_round_from_thursday_to_monday_is_not_cut(self):
        spread = [_cm(1, 4, "2026-10-22T21:00"), _cm(2, 4, "2026-10-24T18:00"), _cm(3, 4, "2026-10-25T12:00"), _cm(4, 4, "2026-10-26T21:00")]
        rounds, _ = _rounds(spread)
        assert rounds == {4: ["1", "2", "3", "4"]}

    def test_the_rounds_are_listed_by_the_kick_off_of_their_first_match(self):
        out = _rounds(self.WEEKEND + [_cm(40, 12, "2026-10-23T20:00")])[1]
        assert [r["round"] for r in out["rounds"]] == [12, 4]

    def test_played_matches_and_matches_without_a_date_are_not_listed(self):
        calendar = self.WEEKEND + [_cm(50, 4, None), _cm(51, 4, None, kind="result"), _cm(52, 4, "2026-10-01T18:00", kind="result")]
        rounds, _ = _rounds(calendar)
        assert rounds == {4: ["1", "2", "3", "4", "5", "6", "7"]}

    def test_a_match_that_kicked_off_long_ago_counts_as_played(self):
        rounds, _ = _rounds(self.WEEKEND + [_cm(53, 3, "2026-10-21T01:00")])
        assert list(rounds) == [4]

    def test_nothing_to_play_is_a_warning_and_a_failing_calendar_too(self):
        rounds, out = _rounds([_cm(1, 4, "2026-10-01T18:00", kind="result")])
        assert rounds == {} and "No quedan partidos" in out["warning"] and out["rounds"] == []
        svc = MatchScheduleService(_db(), fetch_calendar=lambda u: (_ for _ in ()).throw(ConnectionError("down")), now=lambda: NOW,
                                   competitions=lambda: COMPETITIONS)
        assert svc.next_rounds("LF_CHALLENGE_2026")["rounds"] == [] and "calendario" in svc.next_rounds("LF_CHALLENGE_2026")["warning"].lower()
        assert _service().next_rounds("FBCYL_1A_2026")["rounds"] == []

    def test_each_match_has_what_the_package_and_the_index_need(self):
        _, out = _rounds(self.WEEKEND)
        match = out["rounds"][0]["matches"][0]
        assert set(match) == {"code", "start", "round", "home", "away"} and match["round"] == 4

    def test_next_round_is_the_biggest_of_them_and_the_earliest_on_a_tie(self):
        svc = _service(calendar=[_cm(90, 1, "2026-10-21T20:00")] + self.WEEKEND, now=datetime.fromisoformat("2026-10-21T10:00"))
        assert svc.next_round("LF_CHALLENGE_2026")["round"] == 4
        tie = _service(calendar=[_cm(1, 1, "2026-10-21T20:00"), _cm(2, 4, "2026-10-24T20:00")], now=datetime.fromisoformat("2026-10-21T10:00"))
        assert tie.next_round("LF_CHALLENGE_2026")["round"] == 1
