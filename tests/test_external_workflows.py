"""The workflows of the external sources are independent of everything FEB runs on and run at least daily (#884, D0, PR B; the acceptance criteria of the issue and of the evaluation of 12/11/2026).

* ``archive-ext-refresh.yml``: one job per source (the matrix comes from the catalogue, not from a list), each with its own concurrency group, ``fail-fast: false`` so one source never stops another, a daily
  schedule, an automatic issue when a source fails, and it commits only the folder of its source (one writer per folder). It does not wait for, nor is it triggered by, the refresh of FEB.
* ``web-data-ext.yml``: its own branch (``web-data-ext``) and its own concurrency group: two writers on the branch of ``web-data`` would race, and a failure here must not stop the data of Analytics.
* The workflows of FEB (``archive-refresh``, ``live-packages``, ``web-data``, ``talent-data``) know nothing of the external ones.
"""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FEB_SIDE = ["archive-refresh", "live-packages", "web-data", "talent-data", "talent-rosters", "archive-purge", "rule-evaluation"]


def load(name):
    text = (WORKFLOWS / f"{name}.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    data["on"] = data.pop(True, data.get("on"))               # YAML reads the key ``on`` as True
    return data, text


def _is_daily_or_more(cron: str) -> bool:
    """A cron that runs every day (day of month, month and day of week free)."""
    fields = cron.split()
    return len(fields) == 5 and fields[2:] == ["*", "*", "*"]


class TestArchiveExtRefresh:
    @pytest.fixture(scope="class")
    def wf(self):
        return load("archive-ext-refresh")

    def test_it_runs_every_day_at_least(self, wf):
        crons = [s["cron"] for s in wf[0]["on"]["schedule"]]
        assert crons and any(_is_daily_or_more(c) for c in crons)

    def test_its_sources_come_from_the_catalogue_not_from_a_list(self, wf):
        data, text = wf
        assert "run_external_refresh.py --list-sources" in text
        matrix = data["jobs"]["refresh"]["strategy"]["matrix"]
        assert matrix["source"].startswith("${{ fromJSON(") and "needs.sources.outputs" in matrix["source"]
        assert not re.search(r"\b(ncaa|fiba|acb)\b", yaml.safe_dump(data["jobs"]["refresh"]["strategy"]), re.I)         # no source is written by hand in the matrix

    def test_one_source_never_stops_another_and_each_has_its_own_lane(self, wf):
        job = wf[0]["jobs"]["refresh"]
        assert job["strategy"]["fail-fast"] is False
        assert "matrix.source" in job["concurrency"]["group"] and job["concurrency"]["cancel-in-progress"] is False

    def test_it_has_nothing_to_do_without_sources_instead_of_failing(self, wf):
        assert "needs.sources.outputs" in wf[0]["jobs"]["refresh"]["if"] and "[]" in wf[0]["jobs"]["refresh"]["if"]

    def test_a_failing_source_opens_an_issue_by_itself(self, wf):
        data, text = wf
        assert data["permissions"]["issues"] == "write"
        step = next(s for s in data["jobs"]["refresh"]["steps"] if "gh issue" in s.get("run", ""))
        assert "failure()" in step["if"] and "matrix.source" in step["run"]

    def test_it_commits_only_the_folder_of_its_own_source(self, wf):
        run = "\n".join(s.get("run", "") for s in wf[0]["jobs"]["refresh"]["steps"])
        adds = re.findall(r"git add (.+)", run)
        assert adds and all("matrix.source" in a for a in adds) and "git add -A" not in run

    def test_it_neither_waits_for_nor_is_triggered_by_the_refresh_of_feb(self, wf):
        data, content = wf[0], yaml.safe_dump(wf[0])                   # what the workflow DOES, not what its comments say
        assert "workflow_run" not in data["on"]
        assert "Archive refresh" not in content and "restore-archive" not in content and "ARCHIVE_DEPLOY_KEY" not in content.replace("ARCHIVE_EXT_DEPLOY_KEY", "")     # it never reads nor writes the archive of FEB
        assert not any("needs" in job and "archive" in str(job["needs"]).lower() and job is not data["jobs"]["refresh"] for job in data["jobs"].values())

    def test_a_manual_run_can_say_how_many_games_to_ask_for_and_the_scheduled_one_uses_the_default(self, wf):
        data = wf[0]
        inputs = data["on"]["workflow_dispatch"]["inputs"]
        assert inputs["budget"]["required"] is False and not inputs["budget"].get("default")        # empty: the default of the source
        step = next(s for s in data["jobs"]["refresh"]["steps"] if "run_external_refresh.py --source" in s.get("run", ""))
        assert "--budget" in step["run"] and "BUDGET" in step["env"] and "inputs.budget" in step["env"]["BUDGET"]
        assert '${BUDGET:+--budget "$BUDGET"}' in step["run"]                                    # no --budget at all when it is empty

    def test_a_failed_run_still_reports_its_freshness(self, wf):
        run = "\n".join(s.get("run", "") for s in wf[0]["jobs"]["refresh"]["steps"])
        assert "status.json" in run or "--source" in run
        push = next(s for s in wf[0]["jobs"]["refresh"]["steps"] if "git push" in s.get("run", ""))
        assert "always()" in push["if"] or "!cancelled()" in push["if"]                      # the status of a failed run (last_ok kept) is committed too


class TestWebDataExt:
    @pytest.fixture(scope="class")
    def wf(self):
        return load("web-data-ext")

    def test_it_publishes_to_its_own_branch_and_never_to_the_ones_of_the_others(self, wf):
        text = yaml.safe_dump(wf[0])
        assert re.search(r"publish:web-data-ext\b", text)
        assert not re.search(r"publish:(web-data(?!-ext)|talent-data|live-packages)", text)

    def test_it_has_its_own_concurrency_group(self, wf):
        group = wf[0]["concurrency"]["group"]
        assert group == "web-data-ext" and group not in {load(n)[0].get("concurrency", {}).get("group") for n in ("web-data", "talent-data")}

    def test_it_runs_after_the_refresh_of_the_external_sources_and_on_its_own_code_only(self, wf):
        data, text = wf
        assert data["on"]["workflow_run"]["workflows"] == ["Archive ext refresh"]
        paths = data["on"]["push"]["paths"]
        assert "run_web_data_ext.py" in paths and "src/external/**" in paths

    def test_it_publishes_even_if_a_source_failed_but_not_if_the_refresh_was_cancelled(self, wf):
        assert "cancelled" in wf[0]["jobs"]["publish"]["if"]

    def test_it_reads_the_external_archive_with_its_own_key_and_not_the_one_of_feb(self, wf):
        text = yaml.safe_dump(wf[0])
        assert "ARCHIVE_EXT_DEPLOY_KEY" in text and "ARCHIVE_DEPLOY_KEY" not in text.replace("ARCHIVE_EXT_DEPLOY_KEY", "") and "restore-archive" not in text


@pytest.mark.parametrize("name", FEB_SIDE)
def test_the_workflows_of_feb_know_nothing_of_the_external_ones(name):
    text = yaml.safe_dump(load(name)[0])                      # their content, not their comments
    assert "archive-ext-refresh" not in text and "Archive ext refresh" not in text and "web-data-ext" not in text and "run_external_refresh" not in text


def test_no_workflow_of_feb_refreshes_an_external_source_from_the_catalogue():
    """The refresh of FEB reads ``refresh_entries`` and the packages ``package_entries``: both leave the external competitions out (``test_external_sources_catalogue.py``)."""
    for name in ("archive-refresh", "live-packages"):
        assert "external_entries" not in yaml.safe_dump(load(name)[0])
