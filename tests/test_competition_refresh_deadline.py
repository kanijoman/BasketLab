"""A time limit for the refresh of FEB and FBCYL (#1067): when the scrape runs out of time the work is saved and what is left waits for the next run, instead of the job being cut and everything lost.

Before it, the job had a limit of 90 minutes and the step that saves the archive does not run when the job is cancelled (``!cancelled()``): a run that took too long lost everything it had scraped, and a
run that always needs more than the limit (a big first load, or FEB slow for hours) would have failed for ever. Now ``refresh_all`` takes a ``deadline``: before starting each competition (a group of FEB or
of FBCYL, never in the middle of one) it looks at the clock and, if the time is up, it leaves the rest as ``deferred``. A deferred competition is not an error (the next run takes it up where this one left
it: the stored games are skipped), and it says so in the summary.
"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from test_competition_refresh import ENTRY, _db, _scraper

from src.services.competition_refresh import RefreshEntry, main, needs_attention, refresh_all, to_markdown

NOW = datetime(2026, 11, 23, 12, 0)


def groups(*labels):
    return [RefreshEntry(**{**ENTRY, "group_label": label, "group_value": str(i)}) for i, label in enumerate(labels, start=1)]


def fresh(collection):
    return {"collection": collection, "up_to_date": True, "missing_codes": [], "games_in_db": 2, "calendar_results": 2, "last_game": "2026-11-20T12:00", "warning": None}


class Clock:
    """A clock that moves ``step`` seconds every time it is read, so that the competitions take 'time'."""

    def __init__(self, step):
        self.now, self.step = 0.0, step

    def __call__(self):
        value = self.now
        self.now += self.step
        return value


def run(db, entries, deadline=None, clock=None, scraper=None, **extra):
    return refresh_all(db, entries, scraper=scraper or _scraper(["1", "2"]), freshness=fresh, now=lambda: NOW, deadline=deadline, clock=clock or (lambda: 0.0), **extra)


def stored(db):
    return sorted(db.stored)


class TestWhenTheTimeIsUp:
    def test_the_competitions_after_the_deadline_are_left_for_the_next_run_and_the_others_are_done(self):
        db = _db()
        report = run(db, groups("A", "B", "C", "D"), deadline=2.5, clock=Clock(1.0))              # it is read before each competition: 0, 1, 2 start; 3 is over 2.5
        done = [r["collection"] for r in report if not r.get("deferred")]
        later = [r["collection"] for r in report if r.get("deferred")]
        assert len(done) == 3 and len(later) == 1 and later[0].endswith("/D") and len(stored(db)) == 3

    def test_what_was_scraped_before_the_deadline_is_kept_and_what_comes_after_is_not_asked_for(self):
        db = _db()
        scraper = _scraper(["1", "2"])
        run(db, groups("A", "B", "C"), deadline=1.5, clock=Clock(1.0), scraper=scraper)
        assert len(stored(db)) == 2 and scraper.fetch_boxscore.call_count == 4                      # two competitions of two games; the third was not touched

    def test_a_competition_is_never_cut_in_the_middle(self):
        """The clock only matters between competitions: one that started finishes whatever time it takes."""
        db = _db()
        report = run(db, groups("A", "B"), deadline=0.5, clock=Clock(1.0))
        assert [bool(r.get("deferred")) for r in report] == [False, True] and report[0]["job"]["total"] == 2

    def test_the_deadline_itself_is_already_late(self):
        report = run(_db(), groups("A", "B"), deadline=1.0, clock=Clock(1.0))                        # the second is read at exactly 1.0
        assert [bool(r.get("deferred")) for r in report] == [False, True]

    def test_without_a_deadline_nothing_is_deferred_as_always(self):
        report = run(_db(), groups("A", "B", "C"), clock=Clock(1000.0))
        assert not any(r.get("deferred") for r in report) and len(report) == 3


class TestItIsNotAnErrorAndItSaysSo:
    def test_a_deferred_competition_does_not_turn_the_run_red(self):
        report = run(_db(), groups("A", "B", "C"), deadline=1.5, clock=Clock(1.0))
        assert any(r.get("deferred") for r in report) and needs_attention(report) is False

    def test_the_summary_lists_what_is_left_for_the_next_run(self):
        report = run(_db(), groups("A", "B", "C", "D"), deadline=1.5, clock=Clock(1.0))
        text = to_markdown(report)
        assert "Aplazadas por tiempo: 2" in text and "/C" in text and "/D" in text and "siguiente refresco" in text

    def test_a_deferred_one_has_the_same_shape_as_the_others_so_nothing_reading_the_report_breaks(self):
        report = run(_db(), groups("A", "B"), deadline=0.5, clock=Clock(1.0))
        later = report[1]
        assert later["fatal"] is None and later["job"] is None and later["freshness"] is None and later["deferred"] is True


class TestTheNextRunGoesOnWhereThisOneStopped:
    def test_the_deferred_competitions_are_done_the_next_time_without_asking_again_for_what_is_stored(self):
        db = _db()
        entries = groups("A", "B", "C")
        scraper = _scraper(["1", "2"])
        first = run(db, entries, deadline=1.5, clock=Clock(1.0), scraper=scraper)
        assert sum(1 for r in first if r.get("deferred")) == 1 and len(stored(db)) == 2
        again = _scraper(["1", "2"])
        second = run(db, entries, scraper=again)
        assert not any(r.get("deferred") for r in second) and len(stored(db)) == 3
        assert again.fetch_boxscore.call_count == 2                                                  # only the competition that was left: the other two had everything

    def test_a_run_that_always_needs_more_than_its_time_still_gets_to_the_end_in_a_few_runs(self):
        """The loop of before: a load longer than the limit failed every time. With the deadline each run does its part. Time is spent by the games that are downloaded (one second each): a competition
        that already has everything costs nothing, as in real life, so the next run goes through what is done in no time and reaches what was left. 8 competitions of 2 games, 2 per run: 4 runs."""
        db = _db()
        entries = groups(*"ABCDEFGH")
        clock = Clock(0.0)
        runs = 0
        while len(stored(db)) < 8 and runs < 10:
            clock.now = 0.0
            scraper = _scraper(["1", "2"])
            real = scraper.fetch_boxscore.side_effect
            scraper.fetch_boxscore.side_effect = lambda code, session, real=real: (setattr(clock, "now", clock.now + 1.0), real(code, session))[1]
            run(db, entries, deadline=2.5, clock=clock, scraper=scraper)
            runs += 1
        assert len(stored(db)) == 8 and runs == 4


class TestFbcyl:
    def test_the_groups_of_fbcyl_are_deferred_the_same_way_and_never_asked_for(self):
        fbcyl = RefreshEntry(**{**ENTRY, "league": "fbcyl", "fbcyl": {"competition_id": "7298", "category": "1129"}})
        fb_scraper = MagicMock()
        report = refresh_all(_db(), [fbcyl], scraper=None, freshness=fresh, fbcyl_scraper=fb_scraper, now=lambda: NOW, deadline=0.0, clock=Clock(1.0))
        assert report[0]["deferred"] is True and fb_scraper.mock_calls == []


class TestTheCommandLine:
    def test_max_minutes_becomes_a_deadline_counted_from_the_start(self, monkeypatch, tmp_path):
        import src.services.competition_refresh as module

        seen = {}
        monkeypatch.setenv("MONGODB_CONNECTION_STRING", "mongodb://x")
        monkeypatch.setattr("src.database.MongoDBHandler", lambda: MagicMock(is_connected=lambda: True))
        monkeypatch.setattr(module, "load_config", lambda path: groups("A"))
        monkeypatch.setattr(module, "refresh_all", lambda db, entries, **kw: seen.update(kw) or [])
        monkeypatch.setattr(module.time, "monotonic", lambda: 1000.0)
        assert main(["--config", "x", "--max-minutes", "75"]) == 0
        assert seen["deadline"] == 1000.0 + 75 * 60 and seen["clock"]() == 1000.0

    @pytest.mark.parametrize("bad", ["0", "-5", "abc"])
    def test_a_limit_that_is_not_a_positive_number_of_minutes_is_refused(self, bad):
        with pytest.raises(SystemExit):
            main(["--max-minutes", bad])

    def test_without_the_option_there_is_no_deadline(self, monkeypatch):
        import src.services.competition_refresh as module

        seen = {}
        monkeypatch.setenv("MONGODB_CONNECTION_STRING", "mongodb://x")
        monkeypatch.setattr("src.database.MongoDBHandler", lambda: MagicMock(is_connected=lambda: True))
        monkeypatch.setattr(module, "load_config", lambda path: groups("A"))
        monkeypatch.setattr(module, "refresh_all", lambda db, entries, **kw: seen.update(kw) or [])
        assert main(["--config", "x"]) == 0 and seen["deadline"] is None
