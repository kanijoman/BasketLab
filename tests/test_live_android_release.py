"""Weekly release of the Android app (issue #279): which version, and is there anything to publish?

Every Friday morning a workflow publishes the app with everything integrated since the last release (the staff updates
from the app, #227). ``scripts/live_android_release.py`` holds the decisions, in plain Python so they are tested.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "live_android_release.py"
spec = importlib.util.spec_from_file_location("live_android_release", SCRIPT)
release = importlib.util.module_from_spec(spec)
sys.modules["live_android_release"] = release  # dataclasses resolves its module by name
spec.loader.exec_module(release)

TAGS = ["live-android-v0.1.0", "live-android-v0.2.0", "live-android-latest", "v9.9.9", "live-android-v1.2", "web-v3.0.0"]


# --- which tag and which version ---------------------------------------------------------

def test_the_last_release_is_the_highest_version_not_the_latest_by_name_or_date():
    assert release.last_release_tag(TAGS) == "live-android-v0.2.0"
    assert release.last_release_tag(["live-android-v0.9.0", "live-android-v0.10.0", "live-android-v0.2.0"]) == "live-android-v0.10.0"


def test_tags_that_are_not_a_release_of_the_app_are_ignored():
    assert release.last_release_tag(["live-android-latest", "v1.0.0", "live-android-v1.0", "live-android-v1.0.0-rc1"]) is None
    assert release.last_release_tag([]) is None


def test_the_next_version_raises_the_minor_number_and_resets_the_patch():
    assert release.next_version("live-android-v0.2.0") == "0.3.0"
    assert release.next_version("live-android-v0.2.7") == "0.3.0"
    assert release.next_version("live-android-v1.9.4") == "1.10.0"


def test_the_first_release_ever_is_0_1_0():
    assert release.next_version(None) == "0.1.0"


def test_a_version_can_be_forced_if_it_is_well_formed_and_newer():
    assert release.next_version("live-android-v0.2.0", "0.2.1") == "0.2.1"
    assert release.next_version("live-android-v0.2.0", "1.0.0") == "1.0.0"
    assert release.next_version(None, "0.5.0") == "0.5.0"


@pytest.mark.parametrize("bad", ["0.2.0", "0.1.9", "0.3", "v0.3.0", "0.3.0-rc1", "tres", "0.3.0 "])
def test_a_forced_version_that_is_not_newer_or_not_a_version_is_rejected(bad):
    with pytest.raises(ValueError):
        release.next_version("live-android-v0.2.0", bad)


# --- is there anything to publish --------------------------------------------------------

@pytest.mark.parametrize("path", [
    "apps/live-android/src/ui/App.tsx", "apps/live-android/package.json", "apps/live-android/package-lock.json",
    "apps/live-android/android/app/build.gradle", "src/live_core/advice.py", "design/tokens.css",
    "tests/live_vectors/vectors.json", "tests/recordings/2524470.rec.json.gz", "src/JSON_samples/feb_game.json",
])
def test_what_goes_into_the_apk_is_a_change_of_the_app(path):
    assert release.changed_app_files([path]) == [path]


@pytest.mark.parametrize("path", [
    "docs/LIVE.md", "README.md", "src/live_prep/rule_evaluation.py", "src/services/game_prediction_service.py",
    "apps/live-android/README.md", "apps/live-android/src/ui/App.test.tsx", "apps/live-android/src/about/update.test.ts",
    "apps/live-android/scripts/lib/manifest.test.mjs", "apps/live-android/e2e/live.spec.ts", ".github/workflows/ci.yml",
    "tests/test_live_core_advice.py", "frontend/src/App.tsx",
])
def test_what_does_not_change_the_apk_is_not_a_reason_to_publish(path):
    assert release.changed_app_files([path]) == []


def test_changed_files_keep_their_order_and_ignore_blank_lines():
    files = ["docs/x.md", "src/live_core/a.py", "", "design/tokens.css", "  "]
    assert release.changed_app_files(files) == ["src/live_core/a.py", "design/tokens.css"]


def test_nothing_new_in_the_app_means_no_release_and_says_why():
    d = release.decide(TAGS, ["docs/LIVE.md", "src/live_prep/x.py"])
    assert d.release is False and d.version is None and d.previous_tag == "live-android-v0.2.0"
    assert "sin cambios" in d.reason and "live-android-v0.2.0" in d.reason


def test_changes_in_the_app_mean_the_next_minor_version():
    d = release.decide(TAGS, ["src/live_core/advice.py", "docs/LIVE.md", "apps/live-android/src/ui/App.tsx"])
    assert (d.release, d.version, d.previous_tag) == (True, "0.3.0", "live-android-v0.2.0")
    assert d.files == ["src/live_core/advice.py", "apps/live-android/src/ui/App.tsx"]


def test_force_publishes_even_without_changes():
    d = release.decide(TAGS, ["docs/LIVE.md"], force=True)
    assert d.release is True and d.version == "0.3.0" and "forzada" in d.reason


def test_a_forced_version_publishes_even_without_changes():
    d = release.decide(TAGS, [], override="0.2.1")
    assert (d.release, d.version) == (True, "0.2.1")


def test_a_bad_forced_version_is_an_error_not_a_silent_skip():
    with pytest.raises(ValueError):
        release.decide(TAGS, ["src/live_core/a.py"], override="0.1.0")


def test_with_no_previous_release_everything_counts_and_it_starts_at_0_1_0():
    d = release.decide([], [])
    assert (d.release, d.version, d.previous_tag) == (True, "0.1.0", None)


# --- release notes ------------------------------------------------------------------------

GENERATED = """## What's Changed
* feat(live): alerta de alineación indebida (#272) by @kanijoman in https://github.com/kanijoman/BasketLab/pull/277
* fix(ci): el check post-despliegue ya no falla (#269) by @kanijoman in https://github.com/kanijoman/BasketLab/pull/270
* feat(live-app): versión instalada y botón de actualizar (#227) by @kanijoman in https://github.com/kanijoman/BasketLab/pull/280

**Full Changelog**: https://github.com/kanijoman/BasketLab/compare/live-android-v0.2.0...live-android-v0.3.0
"""


def test_the_notes_are_the_titles_of_the_merged_pull_requests_without_the_noise():
    assert release.summarize_notes(GENERATED) == (
        "• feat(live): alerta de alineación indebida (#272)\n"
        "• fix(ci): el check post-despliegue ya no falla (#269)\n"
        "• feat(live-app): versión instalada y botón de actualizar (#227)")


def test_long_notes_are_cut_with_a_count_of_what_is_left():
    body = "\n".join(f"* cambio número {i} by @u in https://x/pull/{i}" for i in range(1, 15))
    notes = release.summarize_notes(body, max_items=5)
    assert notes.count("•") == 5 and notes.endswith("… y 9 cambios más")


def test_notes_have_a_maximum_length_for_the_apps_notice():
    body = "\n".join(f"* {'palabra ' * 30}{i} by @u in https://x/pull/{i}" for i in range(1, 6))
    assert len(release.summarize_notes(body, max_chars=200)) <= 200


def test_no_changes_listed_gives_no_notes():
    assert release.summarize_notes("") == "" and release.summarize_notes("## What's Changed\n\n**Full Changelog**: x") == ""


# --- the command line ---------------------------------------------------------------------

def fake_git(tags, files):
    def run(*args):
        if args[0] == "tag":
            return "\n".join(tags)
        if args[0] == "diff":
            assert args[-2:] == ("live-android-v0.2.0", "HEAD"), args
            return "\n".join(files)
        raise AssertionError(args)
    return run


def read_output(path):
    return dict(line.split("=", 1) for line in Path(path).read_text(encoding="utf-8").splitlines() if "=" in line)


def test_decide_writes_the_outputs_the_workflow_reads(tmp_path, capsys):
    out = tmp_path / "out"
    code = release.main(["decide"], run_git=fake_git(TAGS, ["src/live_core/advice.py"]), env={"GITHUB_OUTPUT": str(out)})
    assert code == 0
    assert read_output(out) == {"release": "true", "version": "0.3.0", "previous_tag": "live-android-v0.2.0",
                                "reason": "1 archivos de la app han cambiado desde live-android-v0.2.0"}
    assert "0.3.0" in capsys.readouterr().out


def test_decide_with_nothing_to_publish_says_so(tmp_path):
    out = tmp_path / "out"
    release.main(["decide"], run_git=fake_git(TAGS, ["docs/LIVE.md"]), env={"GITHUB_OUTPUT": str(out)})
    got = read_output(out)
    assert got["release"] == "false" and got["version"] == "" and "sin cambios" in got["reason"]


def test_decide_takes_the_forced_version_and_force_from_the_arguments(tmp_path):
    out = tmp_path / "out"
    release.main(["decide", "--version", "0.2.1"], run_git=fake_git(TAGS, []), env={"GITHUB_OUTPUT": str(out)})
    assert read_output(out)["version"] == "0.2.1"
    release.main(["decide", "--force"], run_git=fake_git(TAGS, []), env={"GITHUB_OUTPUT": str(out)})
    assert read_output(out)["release"] == "true"


def test_a_bad_forced_version_stops_with_a_clear_message(tmp_path, capsys):
    code = release.main(["decide", "--version", "0.1.0"], run_git=fake_git(TAGS, []), env={"GITHUB_OUTPUT": str(tmp_path / "o")})
    assert code == 2 and "0.1.0" in capsys.readouterr().err


def test_without_a_github_output_file_the_outputs_go_to_the_console(capsys):
    release.main(["decide"], run_git=fake_git(TAGS, ["src/live_core/a.py"]), env={})
    assert "release=true" in capsys.readouterr().out


def test_the_notes_subcommand_reads_the_generated_body_from_stdin(capsys, monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(GENERATED))
    assert release.main(["notes"], run_git=None, env={}) == 0
    assert capsys.readouterr().out.startswith("• feat(live): alerta de alineación indebida (#272)")
