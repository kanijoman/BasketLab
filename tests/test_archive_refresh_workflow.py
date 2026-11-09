"""The refresh of the archive without Atlas (issue #724, step 3): ONE workflow brings the games up to date and is the ONLY writer of the private archive.

Before, ``web-data.yml`` did both things (scraped into its ephemeral Mongo, built the web data for an hour and saved the archive at the end) and was triggered by the Atlas refresh. A
long job that also writes the archive cannot share it with a second writer (the push replaces the last commit), and a refresh that waits behind an hour-long publication is a
refresh that does not happen. So the scrape and the save live in ``archive-refresh.yml`` (minutes) and ``web-data.yml`` only restores the archive and builds from it.
"""
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _load(name):
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(workflow):
    return workflow.get("on") or workflow.get(True)               # YAML 1.1 reads the key `on` as True


def _runs(workflow):
    return "\n".join(step.get("run", "") for job in workflow["jobs"].values() for step in job["steps"])


def _step(workflow, name):
    return next(step for job in workflow["jobs"].values() for step in job["steps"] if step.get("name", "").startswith(name))


class TestTheRefresh:
    wf = _load("archive-refresh.yml")

    def test_it_runs_on_its_own_schedule_by_hand_and_validates_on_pull_requests(self):
        triggers = _triggers(self.wf)
        assert triggers["schedule"] and "workflow_dispatch" in triggers and "pull_request" in triggers
        assert "only" in triggers["workflow_dispatch"]["inputs"]                  # the first load of a competition is heavy: by hand and one at a time
        assert "config/competitions.json" in triggers["pull_request"]["paths"]

    def test_it_restores_the_archive_scrapes_the_active_competitions_of_the_catalogue_fills_derived_and_saves(self):
        runs = _runs(self.wf)
        order = [runs.index(s) for s in ("run_refresh.py --config config/competitions.json",
                                         "run_backfill_derived.py", "run_archive.py dump --out archive --no-shrink", "run_archive.py push")]
        assert order == sorted(order)

    def test_a_failed_scrape_does_not_stop_the_save_but_leaves_the_run_red(self):
        scrape = _step(self.wf, "Scrape")
        assert scrape.get("continue-on-error") is True and scrape["id"] == "scrape"
        save, fail = _step(self.wf, "Save the archive"), _step(self.wf, "Fail")
        assert "cancelled()" in save["if"]                                        # the new games are worth keeping even if the scrape reported a problem
        assert "steps.scrape.outcome == 'failure'" in fail["if"] and "exit 1" in fail["run"]
        steps = [s.get("name", "") for s in self.wf["jobs"]["refresh"]["steps"]]
        assert steps.index(save["name"]) < steps.index(fail["name"])              # and the red comes after the save

    def test_two_refreshes_never_run_at_once_and_a_running_one_is_not_cancelled(self):
        assert self.wf["concurrency"]["cancel-in-progress"] is False and self.wf["concurrency"]["group"] == "archive-refresh"

    def test_the_job_has_room_for_a_heavy_first_load(self):
        assert self.wf["jobs"]["refresh"]["timeout-minutes"] >= 60

    def test_it_only_reads_the_repository_and_writes_the_archive_through_its_own_key(self):
        assert self.wf["permissions"] == {"contents": "read"}
        assert "ARCHIVE_DEPLOY_KEY" in str(self.wf)


class TestTheSingleWriter:
    def test_only_the_refresh_and_the_purge_push_the_archive_and_they_never_run_at_once(self):
        writers = [p.name for p in sorted(WORKFLOWS.glob("*.yml")) if "run_archive.py push" in p.read_text(encoding="utf-8")]
        assert writers == ["archive-purge.yml", "archive-refresh.yml"]
        groups = {_load(name)["concurrency"]["group"] for name in writers}
        assert groups == {"archive-refresh"}                                       # one group: a purge waits for a refresh and the other way round
        assert all(_load(name)["concurrency"]["cancel-in-progress"] is False for name in writers)

    def test_the_publication_restores_the_archive_and_builds_from_it_without_scraping_or_saving(self):
        web = _load("web-data.yml")
        runs = _runs(web)
        assert "restore-archive" in str(web) and "run_web_data.py" in runs
        assert "run_refresh.py --config" not in runs and "run_backfill_derived.py" not in runs and "run_archive.py dump" not in runs

    def test_the_publication_waits_for_the_refresh_and_the_purge_and_no_longer_for_the_atlas_one(self):
        runs = _triggers(_load("web-data.yml"))["workflow_run"]
        assert runs["workflows"] == ["Archive refresh", "Archive purge"] and runs["types"] == ["completed"]       # a purge changes what is published too

    def test_a_red_refresh_does_not_stop_the_publication_but_a_cancelled_one_does(self):
        condition = _load("web-data.yml")["jobs"]["publish"]["if"]
        assert "cancelled" in condition


class TestTheGuardsOfTheWriter:
    """The job rewrites the only copy of the games (#646): what ``web-data.yml`` guarded when it was the writer is guarded here."""

    steps = {s["name"]: s for s in _load("archive-refresh.yml")["jobs"]["refresh"]["steps"] if "name" in s}

    def test_the_archive_is_saved_only_after_a_complete_restore_and_never_with_fewer_games(self):
        save = self.steps["Save the archive"]
        assert "steps.restore.outcome == 'success'" in save["if"] and "!cancelled()" in save["if"]
        assert "--no-shrink" in save["run"]

    def test_a_failed_download_or_restore_stops_everything_that_would_use_the_empty_database(self):
        assert self.steps["Restore the archive"]["id"] == "restore" and self.steps["Restore the archive"]["if"] == "github.event_name != 'pull_request'"
        assert "steps.restore.outcome == 'success'" in self.steps["Scrape the new games"]["if"]
        assert "steps.restore.outcome == 'success'" in self.steps["Fill DERIVED in the games"]["if"]
        assert "continue-on-error" not in self.steps["Restore the archive"]       # a red restore must turn the run red

    def test_everything_works_on_the_ephemeral_mongo_and_nothing_touches_atlas(self):
        wf = _load("archive-refresh.yml")
        assert wf["jobs"]["refresh"]["services"]["mongo"]["image"].startswith("mongo:")
        for name in ("Scrape the new games", "Fill DERIVED in the games", "Save the archive"):
            assert "EPHEMERAL_MONGO" in self.steps[name]["env"]["MONGODB_CONNECTION_STRING"]
        assert "secrets.ATLAS" not in (WORKFLOWS / "archive-refresh.yml").read_text(encoding="utf-8")

    def test_the_download_is_the_shared_action_whose_key_handling_is_tested_there(self):
        step = self.steps["Restore the archive"]
        assert step["uses"] == "./.github/actions/restore-archive" and step["with"]["deploy-key"] == "${{ secrets.ARCHIVE_DEPLOY_KEY }}"


class TestThePurgeWorkflow:
    """``archive-purge.yml`` (issue #724): the deliberate order that deletes a competition from the archive. By hand only, a dry run without the confirmation."""

    wf = _load("archive-purge.yml")
    steps = {s["name"]: s for s in wf["jobs"]["purge"]["steps"] if "name" in s}

    def test_it_runs_only_by_hand_and_asks_for_the_competition_the_season_and_a_confirmation(self):
        triggers = _triggers(self.wf)
        assert list(triggers) == ["workflow_dispatch"]
        inputs = triggers["workflow_dispatch"]["inputs"]
        assert inputs["competition"]["required"] is True and inputs["season"]["required"] is True
        assert inputs["confirm"]["required"] is False and inputs["league"]["options"] == ["feb", "fbcyl"]

    def test_the_inputs_reach_the_command_through_the_environment_not_the_script_text(self):
        step = self.steps["Purge"]
        assert "${{" not in step["run"], "an input interpolated into the script would allow command injection"
        assert {"COMPETITION", "SEASON", "LEAGUE", "CONFIRM"} <= set(step["env"])
        assert "run_archive.py purge" in step["run"] and '--confirm "$CONFIRM"' in step["run"]

    def test_without_the_confirmation_nothing_is_saved_and_the_plan_goes_to_the_summary(self):
        assert self.steps["Save the archive"]["if"] == "inputs.confirm != ''"
        assert "GITHUB_STEP_SUMMARY" in self.steps["Purge"]["run"]

    def test_the_order_is_download_purge_save_and_a_failed_purge_stops_the_save(self):
        names = [s.get("name", "") for s in self.wf["jobs"]["purge"]["steps"]]
        order = ["Download the archive", "Purge", "Save the archive"]
        assert [names.index(n) for n in order] == sorted(names.index(n) for n in order)
        assert "continue-on-error" not in self.steps["Purge"] and "!cancelled()" not in self.steps["Save the archive"]["if"]

    def test_it_pushes_with_the_deploy_key_that_the_download_leaves_in_the_environment(self):
        assert self.steps["Download the archive"]["uses"] == "./.github/actions/restore-archive"
        assert "run_archive.py push" in self.steps["Save the archive"]["run"] and "GIT_SSH_COMMAND" in self.steps["Save the archive"]["run"]

    def test_it_does_not_touch_the_database_or_atlas(self):
        text = (WORKFLOWS / "archive-purge.yml").read_text(encoding="utf-8")
        assert "MONGODB_CONNECTION_STRING" not in text and "secrets.ATLAS" not in text


# --- the weekend (feedback of the 0.5.2) -------------------------------------------------------------------------------------------------------------------------------

def _field(spec, value):
    """Whether a value matches one field of a cron expression (``*``, ``*/n``, ``a-b``, ``a,b``: what the schedules use)."""
    for part in spec.split(","):
        if part == "*" or (part.startswith("*/") and value % int(part[2:]) == 0):
            return True
        low, _, high = part.partition("-")
        if int(low) <= value <= int(high or low):
            return True
    return False


def _runs_between(start, end):
    """Every minute (UTC) a schedule of the refresh starts between ``start`` and ``end``, once per schedule that matches it."""
    from datetime import timedelta
    crons, out, t = [s["cron"].split() for s in _triggers(TestTheRefresh.wf)["schedule"]], [], start
    while t <= end:
        out += [t for minute, hour, dom, month, dow in crons
                if _field(minute, t.minute) and _field(hour, t.hour) and _field(dom, t.day) and _field(month, t.month) and _field(dow, t.isoweekday() % 7)]
        t += timedelta(minutes=1)
    return out


class TestTheWeekend:
    """«Aumentar la tasa de refresco de datos web durante el fin de semana para tener antes estadísticas. Desde las 18:00 del sábado hasta las 23:30 del domingo el refresco debería
    ser cada hora.» The schedules of GitHub are in UTC: the window must hold in Madrid both in winter (UTC+1) and in summer (UTC+2) time. ``web-data.yml`` follows every refresh."""

    @staticmethod
    def _madrid_weekend(saturday):
        from datetime import datetime, timedelta, timezone
        from zoneinfo import ZoneInfo
        madrid = ZoneInfo("Europe/Madrid")
        start = datetime(saturday.year, saturday.month, saturday.day, 18, 0, tzinfo=madrid)
        end = start + timedelta(days=1, hours=5, minutes=30)                               # Sunday 23:30
        runs = _runs_between((start - timedelta(hours=2)).astimezone(timezone.utc).replace(tzinfo=None), (end + timedelta(hours=2)).astimezone(timezone.utc).replace(tzinfo=None))
        return [r.replace(tzinfo=timezone.utc).astimezone(madrid) for r in runs], start, end

    def test_from_saturday_18_00_to_sunday_23_30_in_madrid_the_refresh_runs_every_hour_in_winter_and_in_summer(self):
        from datetime import date, timedelta
        for saturday in (date(2026, 11, 14), date(2027, 4, 17)):                          # winter time, summer time
            runs, start, end = self._madrid_weekend(saturday)
            inside = [r for r in runs if start <= r <= end]
            points = [start, *inside, end]
            assert max(b - a for a, b in zip(points, points[1:])) <= timedelta(hours=1), saturday
            assert inside[-1] >= end - timedelta(hours=1)                                   # the last one of Sunday night, not before

    def test_no_minute_starts_two_refreshes(self):
        from datetime import datetime
        runs = _runs_between(datetime(2026, 11, 9), datetime(2026, 11, 16))                 # a whole week
        assert len(runs) == len(set(runs))

    def test_from_monday_to_friday_it_stays_at_three_a_day(self):
        from datetime import datetime
        runs = _runs_between(datetime(2026, 11, 9), datetime(2026, 11, 13, 23, 59))         # Monday to Friday, UTC
        assert len(runs) == 5 * 3
