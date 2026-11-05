"""Guards of ``web-data.yml`` (#646, #724): the job builds the web data from the archive, so the order and conditions of its steps are part of the contract.

Since #724 it no longer scrapes or saves the archive (``archive-refresh.yml`` does, see ``test_archive_refresh_workflow.py``): it restores it and builds from it.
The workflow itself only runs on GitHub (secrets, SSH, a service container): these tests fix what can go wrong silently when someone edits it.
"""
from pathlib import Path

import yaml

WORKFLOW = yaml.safe_load((Path(__file__).resolve().parent.parent / ".github" / "workflows" / "web-data.yml").read_text(encoding="utf-8"))
NAMED = [step for step in WORKFLOW["jobs"]["publish"]["steps"] if "name" in step]      # checkout and setup-python have none
STEPS = {step["name"]: step for step in NAMED}
ORDER = [step["name"] for step in NAMED]


def test_a_failed_download_or_restore_stops_everything_that_would_use_the_empty_database():
    assert STEPS["Restore the archive into the ephemeral Mongo"]["if"] == "steps.pull.outcome == 'success'"
    assert "continue-on-error" not in STEPS["Restore the archive into the ephemeral Mongo"]       # a red restore must turn the run red


def test_the_order_is_download_restore_build_publish():
    names = ["Download the archive", "Restore the archive into the ephemeral Mongo", "Build the artifacts", "Publish to the web-data branch"]
    assert [ORDER.index(n) for n in names] == sorted(ORDER.index(n) for n in names)


def test_it_neither_scrapes_nor_saves_the_archive():
    assert not [n for n in ORDER if n.startswith(("Scrape", "Fill DERIVED", "Save the archive"))]


def test_the_build_reads_the_ephemeral_mongo_and_never_atlas():
    build = STEPS["Build the artifacts"]["env"]["MONGODB_CONNECTION_STRING"]
    assert build == "${{ env.EPHEMERAL_MONGO }}"


def test_the_ephemeral_mongo_is_a_service_container_and_the_build_reads_it():
    assert WORKFLOW["jobs"]["publish"]["services"]["mongo"]["image"].startswith("mongo:")
    assert "EPHEMERAL_MONGO" in STEPS["Restore the archive into the ephemeral Mongo"]["env"]["MONGODB_CONNECTION_STRING"]


def test_the_deploy_key_is_rebuilt_and_checked_before_it_is_used_regression():
    """A key saved by hand reaches the secret with CRLF, a BOM, spaces for newlines...: OpenSSH refuses it with the opaque ``error in libcrypto``.
    The step rebuilds it from its base64 body (``src.local_data.ssh_key``, tested against ssh-keygen) and names the secret if it is not a key."""
    run = STEPS["Download the archive"]["run"]
    assert "python -m src.local_data.ssh_key" in run and "ssh-keygen -y -f" in run
    assert run.index("python -m src.local_data.ssh_key") < run.index("ssh-keygen -y -f") < run.index("run_archive.py pull")
    assert "ARCHIVE_DEPLOY_KEY" in run.split("ssh_key", 1)[1].split("exit 1", 1)[0]
