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


# --- the manual upload to Google Play (the .aab is uploaded by hand to Play Console) -----------------------------------

NOTES = "• feat(live): alerta de alineación indebida (#272)\n• chore(deps): Bump actions/download-artifact from 4 to 8\n• CI: web-data con 240 min para un recálculo completo\n• fix(live): el aviso de falta no se descartaba (#301)\n• docs: guía del staff"


def test_the_play_notes_keep_what_the_staff_notices_and_drop_the_plumbing():
    text = release.play_notes(NOTES)
    assert "Alerta de alineación indebida" in text and "El aviso de falta no se descartaba" in text and "feat" not in text and "#272" not in text
    assert "deps" not in text and "web-data" not in text and "guía del staff" not in text


def test_the_play_notes_are_in_the_limit_of_play_console_with_nothing_cut_in_the_middle_of_a_bullet():
    many = "\n".join(f"• feat(live): cambio número {i} con una descripción bastante larga para llenar el espacio" for i in range(30))
    text = release.play_notes(many)
    assert len(text) <= release.PLAY_NOTES_LIMIT == 500
    assert all(line.startswith("• ") or line.startswith("… y ") for line in text.splitlines())


def test_the_play_notes_say_something_even_when_everything_was_plumbing():
    assert release.play_notes("• chore(deps): Bump x\n• ci: y") == release.PLAY_NOTES_FALLBACK
    assert release.play_notes("") == release.PLAY_NOTES_FALLBACK


@pytest.mark.parametrize("body, code", [("notas\nversionCode 41\nmás", 41), ("versionCode 7", 7), ("sin marca", None), ("", None), ("versionCode abc", None)])
def test_the_version_code_of_a_release_is_read_back_from_its_body(body, code):
    assert release.parse_version_code(body) == code


def summary(**over):
    args = dict(version="0.7.0", version_code=48, repo="kanijoman/BasketLab", tag="live-android-v0.7.0", notes=NOTES, previous_code=41)
    return release.play_summary(**{**args, **over})


def test_the_summary_links_the_bundle_and_says_the_version_code_and_the_notes_to_paste():
    text = summary()
    assert "https://github.com/kanijoman/BasketLab/releases/download/live-android-v0.7.0/basketlab-live-0.7.0.aab" in text
    assert "0.7.0" in text and "48" in text and "Notas de la versión" in text
    assert release.play_notes(NOTES) in text


def test_the_summary_says_if_play_will_accept_the_version_code():
    assert "mayor que el de la release anterior (41)" in summary()
    assert "Play lo rechazará" in summary(version_code=41) and "Play lo rechazará" in summary(version_code=12)
    assert "anterior no consta" in summary(previous_code=None) and "Play lo rechazará" not in summary(previous_code=None)


def test_the_summary_counts_the_characters_of_the_notes_against_the_limit():
    assert f"{len(release.play_notes(NOTES))} de 500" in summary()


def test_the_play_summary_subcommand_prints_it_from_the_notes_on_stdin(capsys, monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(NOTES))
    argv = ["play-summary", "--version", "0.7.0", "--code", "48", "--repo", "kanijoman/BasketLab", "--tag", "live-android-v0.7.0", "--previous-code", "41"]
    assert release.main(argv, run_git=None, env={}) == 0
    out = capsys.readouterr().out
    assert "basketlab-live-0.7.0.aab" in out and "Alerta de alineación indebida" in out
    monkeypatch.setattr(sys, "stdin", io.StringIO(NOTES))
    assert release.main(argv[:-2], run_git=None, env={}) == 0 and "anterior no consta" in capsys.readouterr().out


def test_the_play_notes_read_the_generated_body_of_the_release_as_it_is_with_no_author_urls_or_headings():
    """Regression: the summary of the run piped the body through the short notes of the app first, which cut the last bullet in the middle («Tarjet…»); the notes for Play come from the body itself."""
    text = release.play_notes(GENERATED)
    assert text.splitlines() == ["• Alerta de alineación indebida", "• El check post-despliegue ya no falla", "• Versión instalada y botón de actualizar"]
    assert "@" not in text and "http" not in text and "Changed" not in text and "Changelog" not in text


def test_a_bullet_the_source_already_cut_is_not_kept_as_if_it_were_whole():
    assert release.play_notes("• feat(live): alerta completa\n• feat(live): una que acaba cor…") == "• Alerta completa"

# --- the notes of the release are those of the pull requests that touched the app (not the Analytics, Talent or data ones) -----------------

SEP, END = "\x1f", "\x1e"


def history(*prs):
    """A fake ``git`` with the first-parent history ``prs`` (newest first): each is ``(hash, subject, body, files)``."""
    files = {h: f for h, _, _, f in prs}

    def run(*args):
        if args[0] == "log":
            assert "--first-parent" in args and args[-1] == "live-android-v0.6.0..HEAD", args
            return "".join(f"{h}{SEP}{s}{SEP}{b}{END}" for h, s, b, _ in prs)
        if args[0] == "diff":
            assert args[1] == "--name-only" and args[2].endswith("^1"), args
            return "\n".join(files[args[3]])
        raise AssertionError(args)
    return run


PRS = (
    ("c4", "Merge pull request #1031 from u/play", "feat(app): resumen para la subida manual a Play Console\n", [".github/workflows/live-android.yml", "scripts/live_android_release.py"]),
    ("c3", "Merge pull request #1030 from u/acb", "feat(talent): ACB paso 2 (#886)\n", ["src/external/acb_catalogue.py", "config/competitions.json"]),
    ("c2", "Merge pull request #1020 from u/live", "Live: feedback del partido 2536159 (faltas, fatiga)\n", ["src/live_core/rules_closing.py", "tests/live_vectors/rules.json"]),
    ("c1", "feat(live-app): botón de actualizar (#227)", "", ["apps/live-android/src/App.tsx"]),
    ("c0", "Merge pull request #1000 from u/docs", "docs: guía del staff\n", ["docs/LIVE.md", "apps/live-android/README.md"]),
)


def test_only_the_pull_requests_that_touched_the_app_are_notes_oldest_first():
    assert release.app_pull_requests(history(*PRS), "live-android-v0.6.0", "HEAD") == ["feat(live-app): botón de actualizar (#227)", "Live: feedback del partido 2536159 (faltas, fatiga)"]


def test_a_merge_commit_says_its_title_in_the_body_and_a_squash_one_in_its_subject():
    got = release.app_pull_requests(history(*PRS[2:4]), "live-android-v0.6.0", "HEAD")
    assert "Merge pull request" not in " ".join(got) and got[0].startswith("feat(live-app)") and got[1].startswith("Live:")


def test_a_pull_request_that_only_touched_docs_or_tests_of_the_app_is_not_a_note():
    only_ignored = (("c9", "Merge pull request #9 from u/x", "test(live): más casos\n", ["apps/live-android/src/App.test.tsx", "apps/live-android/e2e/layout.spec.ts", "docs/LIVE.md"]),)
    assert release.app_pull_requests(history(*only_ignored), "live-android-v0.6.0", "HEAD") == []


def test_a_pull_request_that_only_shares_code_with_the_app_is_a_note_only_if_it_says_live_and_plumbing_never_is():
    """Real cases of 0.7.0: the web-data one changed ``src/live_core`` (shared) and the dependencies and ruff ones touched files of the app, and none is news for the staff of the app."""
    shared = (
        ("a4", "Merge pull request #945 from u/wd", "web-data: no recalcular por un ajuste de reglas (#945)\n", ["src/live_core/advice.py", "src/live_core/four_factors.py"]),
        ("a3", "Merge pull request #960 from u/deps", "chore(deps): Bump the live-app group\n", ["apps/live-android/package.json"]),
        ("a2", "Merge pull request #955 from u/ruff", "chore(calidad): ruff con solo las reglas F\n", ["tests/live_vectors/generate.py"]),
        ("a1", "Merge pull request #970 from u/rule", "feat(live): nueva regla de cierre (#970)\n", ["src/live_core/rules_closing.py"]),
        ("a0", "Merge pull request #971 from u/ui", "Pantalla de avisos más clara\n", ["apps/live-android/src/ui/AlertList.tsx"]),
    )
    assert release.app_pull_requests(history(*shared), "live-android-v0.6.0", "HEAD") == ["Pantalla de avisos más clara", "feat(live): nueva regla de cierre (#970)"]


def test_the_same_title_is_one_note_and_nothing_touching_the_app_is_no_notes():
    twice = (PRS[2], ("cx", "Merge pull request #1021 from u/live2", "Live: feedback del partido 2536159 (faltas, fatiga)\n", ["src/live_core/a.py"]))
    assert release.app_pull_requests(history(*twice), "live-android-v0.6.0", "HEAD") == ["Live: feedback del partido 2536159 (faltas, fatiga)"]
    assert release.app_pull_requests(history(PRS[1]), "live-android-v0.6.0", "HEAD") == []


def test_the_app_notes_subcommand_prints_them_as_bullets_the_other_subcommands_read(capsys):
    assert release.main(["app-notes", "--since", "live-android-v0.6.0"], run_git=history(*PRS), env={}) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == ["* feat(live-app): botón de actualizar (#227)", "* Live: feedback del partido 2536159 (faltas, fatiga)"]
    assert release.play_notes(out).splitlines() == ["• Botón de actualizar", "• Feedback del partido 2536159 (faltas, fatiga)"]
    assert release.summarize_notes(out).count("•") == 2


def test_the_first_release_has_no_since_and_looks_at_the_whole_history(capsys):
    def run(*args):
        if args[0] == "log":
            assert args[-1] == "HEAD", args
            return f"c1{SEP}feat(live): algo{SEP}{END}"
        return "src/live_core/a.py"
    assert release.main(["app-notes"], run_git=run, env={}) == 0 and capsys.readouterr().out == "* feat(live): algo\n"
