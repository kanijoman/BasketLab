"""Guards of ``web-data.yml`` (#646): the job rewrites the only copy of the games, so the order and conditions of its steps are part of the contract.

The workflow itself only runs on GitHub (secrets, SSH, a service container): these tests fix what can go wrong silently when someone edits it.
"""
from pathlib import Path

import yaml

WORKFLOW = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github" / "workflows" / "web-data.yml").read_text(encoding="utf-8"))
NAMED = [step for step in WORKFLOW["jobs"]["publish"]["steps"] if "name" in step]      # checkout and setup-python have none
STEPS = {step["name"]: step for step in NAMED}
ORDER = [step["name"] for step in NAMED]


def test_the_archive_is_saved_only_after_a_complete_restore_and_never_with_fewer_games():
    save = STEPS["Save the archive"]
    assert "steps.restore.outcome == 'success'" in save["if"] and "!cancelled()" in save["if"]
    assert "--no-shrink" in save["run"]


def test_a_failed_download_or_restore_stops_everything_that_would_use_the_empty_database():
    assert STEPS["Restore the archive into the ephemeral Mongo"]["if"] == "steps.pull.outcome == 'success'"
    assert "steps.restore.outcome == 'success'" in STEPS["Scrape the new games into the ephemeral Mongo"]["if"]
    assert "continue-on-error" not in STEPS["Restore the archive into the ephemeral Mongo"]       # a red restore must turn the run red


def test_the_order_is_download_restore_scrape_build_publish_save():
    names = ["Download the archive", "Restore the archive into the ephemeral Mongo", "Scrape the new games into the ephemeral Mongo",
             "Build the artifacts", "Publish to the web-data branch", "Save the archive"]
    assert [ORDER.index(n) for n in names] == sorted(ORDER.index(n) for n in names)


def test_without_the_archive_secret_it_reads_atlas_as_before():
    build = STEPS["Build the artifacts"]["env"]["MONGODB_CONNECTION_STRING"]
    assert "ATLAS_READ_URI" in build and "ATLAS_WRITE_URI" in build and "EPHEMERAL_MONGO" in build


def test_the_ephemeral_mongo_is_a_service_container_and_nothing_scrapes_atlas():
    assert WORKFLOW["jobs"]["publish"]["services"]["mongo"]["image"].startswith("mongo:")
    for name in ("Scrape the new games into the ephemeral Mongo", "Fill DERIVED in the new games", "Restore the archive into the ephemeral Mongo"):
        assert "EPHEMERAL_MONGO" in STEPS[name]["env"]["MONGODB_CONNECTION_STRING"]


def test_the_deploy_key_is_normalised_and_checked_before_it_is_used_regression():
    """A key saved from Windows (PowerShell) reaches the secret with CRLF line endings or a BOM and OpenSSH refuses it with the opaque
    ``error in libcrypto``: the step must strip both and fail with a message that names the secret."""
    run = STEPS["Download the archive"]["run"]
    assert "tr -d '\r'" in run and "\xEF\xBB\xBF" in run
    assert "ssh-keygen -y -f" in run and "ARCHIVE_DEPLOY_KEY" in run.split("ssh-keygen -y -f", 1)[1]
    assert run.index("ssh-keygen -y -f") < run.index("run_archive.py pull")
