"""Decisions of the weekly Android release (issue #279): which version, and is there anything to publish?

Every Friday morning ``live-android-release.yml`` publishes the app with everything integrated since the last release;
the staff updates from the app (#227). This script holds the decisions in plain Python so they are tested::

    python scripts/live_android_release.py decide [--version X.Y.Z] [--force]   # writes release/version/... outputs
    python scripts/live_android_release.py notes < generated-notes.md           # short notes for the app's notice
    python scripts/live_android_release.py play-summary --version X --code N --repo R --tag T < notes.md   # for the manual upload to Play

Standard library only: it runs in CI without installing anything.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Mapping, Optional, Sequence, Tuple

TAG_PREFIX = "live-android-v"
_TAG = re.compile(r"^live-android-v(\d+)\.(\d+)\.(\d+)$")
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# What goes into the APK (the app, the engine it runs, the design tokens, its demo data and reference vectors).
APP_PATHS = ("apps/live-android/", "src/live_core/", "design/", "tests/live_vectors/", "tests/recordings/")
APP_FILES = ("src/JSON_samples/feb_game.json",)
# Inside those paths, what does not change the APK: docs and tests.
_IGNORED_SUFFIXES = (".md", ".test.ts", ".test.tsx", ".test.mjs", ".spec.ts")
_IGNORED_PARTS = ("/e2e/", "/test-results/")

Version = Tuple[int, int, int]


def _tag_version(tag: str) -> Optional[Version]:
    match = _TAG.match(tag.strip())
    return (int(match.group(1)), int(match.group(2)), int(match.group(3))) if match else None


def last_release_tag(tags: Sequence[str]) -> Optional[str]:
    """The tag of the highest released version (numeric comparison: 0.10.0 is newer than 0.9.0)."""
    versions = {t.strip(): v for t in tags if (v := _tag_version(t)) is not None}
    return max(versions, key=versions.get) if versions else None


def next_version(last_tag: Optional[str], override: Optional[str] = None) -> str:
    """The version to publish: the minor number of the last release plus one, or a forced one that is newer."""
    last = _tag_version(last_tag) if last_tag else None
    if override is not None:
        match = _VERSION.fullmatch(override)
        if not match:
            raise ValueError(f"La versión {override!r} no tiene el formato X.Y.Z")
        wanted = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if last is not None and wanted <= last:
            raise ValueError(f"La versión {override} no es posterior a la última publicada ({last_tag})")
        return override
    return "0.1.0" if last is None else f"{last[0]}.{last[1] + 1}.0"


def changed_app_files(files: Sequence[str]) -> List[str]:
    """The changed files that end up in the APK, in their order (blank lines ignored)."""
    out = []
    for raw in files:
        path = raw.strip()
        if not path or path.endswith(_IGNORED_SUFFIXES) or any(part in path for part in _IGNORED_PARTS):
            continue
        if path.startswith(APP_PATHS) or path in APP_FILES:
            out.append(path)
    return out


@dataclass(frozen=True)
class Decision:
    release: bool
    version: Optional[str]
    previous_tag: Optional[str]
    reason: str
    files: List[str]


def decide(tags: Sequence[str], changed_files: Sequence[str], override: Optional[str] = None, force: bool = False) -> Decision:
    last = last_release_tag(tags)
    files = changed_app_files(changed_files)
    version = next_version(last, override)  # raises for a bad forced version, even if nothing would be published
    if override is not None:
        return Decision(True, version, last, f"versión {version} forzada", files)
    if last is None:
        return Decision(True, version, None, "primera versión de la app", files)
    if files:
        return Decision(True, version, last, f"{len(files)} archivos de la app han cambiado desde {last}", files)
    if force:
        return Decision(True, version, last, f"publicación forzada sin cambios en la app desde {last}", files)
    return Decision(False, None, last, f"sin cambios en la app desde {last}", files)


_AUTHOR_SUFFIX = re.compile(r"\s+by\s+@\S+\s+in\s+\S+\s*$")


def summarize_notes(body: str, max_items: int = 8, max_chars: int = 600) -> str:
    """Short notes for the app's update notice from GitHub's generated release notes: one bullet per merged PR."""
    titles: List[str] = []
    for line in body.splitlines():
        if line.startswith(("* ", "- ")):
            title = _AUTHOR_SUFFIX.sub("", line[2:]).strip()
            if title and title not in titles:
                titles.append(title)
    if not titles:
        return ""
    lines = [f"• {t}" for t in titles[:max_items]]
    if len(titles) > max_items:
        lines.append(f"… y {len(titles) - max_items} cambios más")
    text = "\n".join(lines)
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


_LIVE_TITLE = re.compile(r"\blive\b|live-app", re.I)          # a pull request that only shares code with the app (src/live_core, vectors) is news for its staff only if it says so
_FIELD, _RECORD = "\x1f", "\x1e"           # separators of the fields and of the records of ``git log`` (they are not in a commit message)
PLAY_NOTES_LIMIT = 500                     # characters Play Console accepts in the notes of a release, per language
PLAY_NOTES_FALLBACK = "• Mejoras internas y de estabilidad."
_PLUMBING = re.compile(r"^(chore|ci|docs|build|test|refactor|style)(\([^)]*\))?!?:", re.I)
_PREFIX = re.compile(r"^[a-z]+(\([^)]*\))?!?:\s*", re.I)
_PR_REF = re.compile(r"\s*\(#\d+\)\s*$")
_VERSION_CODE = re.compile(r"versionCode\s+(\d+)")


def play_notes(notes: str, limit: int = PLAY_NOTES_LIMIT) -> str:
    """The notes of a release as Play Console takes them: what the staff notices (not dependencies, CI, docs or tests), without the commit prefix or the PR number, and in ``limit`` characters with no bullet cut in
    the middle (the ones that do not fit are counted in a last line). ``PLAY_NOTES_FALLBACK`` when there was only plumbing."""
    items: List[str] = []
    for line in notes.splitlines():
        if not line.lstrip().startswith(("• ", "* ", "- ")):          # the headings and the link to the changelog of the generated notes are not changes
            continue
        text = _AUTHOR_SUFFIX.sub("", line.strip()[2:]).strip()
        if not text or text.startswith("… y ") or text.endswith("…") or _PLUMBING.match(text):          # a bullet the source cut in the middle is not a whole one
            continue
        text = _PR_REF.sub("", _PREFIX.sub("", text)).strip()
        if text:
            items.append(f"• {text[0].upper()}{text[1:]}")
    if not items:
        return PLAY_NOTES_FALLBACK
    kept: List[str] = []
    for item in items:
        if len("\n".join([*kept, item])) <= limit - 24:          # room for the line that counts the rest
            kept.append(item)
    if not kept:
        kept = [items[0][: limit - 1].rstrip() + "…"]
    rest = len(items) - len(kept)
    return "\n".join([*kept, f"… y {rest} cambios más"]) if rest else "\n".join(kept)


def parse_version_code(body: str) -> Optional[int]:
    """The ``versionCode`` a release of the app says in its body (``versionCode 48``), or ``None``."""
    found = _VERSION_CODE.search(body or "")
    return int(found.group(1)) if found else None


def play_summary(version: str, version_code: int, repo: str, tag: str, notes: str, previous_code: Optional[int]) -> str:
    """What whoever uploads the bundle to Play Console needs, as markdown for the summary of the run: the link to the ``.aab``, its ``versionCode`` (and whether Play will take it: it must be higher than the
    last one uploaded; the one of the previous release is the best we know) and the notes ready to paste."""
    url = f"https://github.com/{repo}/releases/download/{tag}/basketlab-live-{version}.aab"
    if previous_code is None:
        check = f"El de la release anterior no consta: comprueba en Play Console que {version_code} es mayor que el último subido."
    elif version_code > previous_code:
        check = f"Es mayor que el de la release anterior ({previous_code}): Play lo aceptará si esa fue la última que se subió."
    else:
        check = f"**Play lo rechazará**: no es mayor que el de la release anterior ({previous_code}). Hay que subir un `versionCode` más alto."
    text = play_notes(notes)
    return "\n".join([
        f"## Subida manual a Play Console: versión {version}", "",
        f"- **Bundle**: [basketlab-live-{version}.aab]({url})",
        f"- **versionCode**: {version_code}. {check}", "",
        f"**Notas de la versión** (pegar en Play Console, {len(text)} de {PLAY_NOTES_LIMIT} caracteres):", "", "```text", text, "```", ""])


def app_pull_requests(run_git: Callable[..., str], since: Optional[str], until: str = "HEAD") -> List[str]:
    """The titles, oldest first, of the pull requests merged in ``since..until`` that touched what goes into the APK (``changed_app_files``): the notes of a release are about the app, not about the
    Analytics, Talent, data or docs changes that travel in the same weeks, nor the plumbing (dependencies, CI, ruff). A PR counts if it touched the app itself (``apps/live-android/``) or, when it only
    touched code shared with it (the engine, the vectors), if its title says live. A merge commit says the title of its pull request in the body, a squash one in its subject."""
    out = run_git("log", "--first-parent", f"--format=%H{_FIELD}%s{_FIELD}%b{_RECORD}", f"{since}..{until}" if since else until)
    titles: List[str] = []
    for record in reversed([r for r in out.split(_RECORD) if r.strip()]):
        commit, subject, body = (record.strip("\n").split(_FIELD, 2) + ["", ""])[:3]
        files = changed_app_files(run_git("diff", "--name-only", f"{commit.strip()}^1", commit.strip()).splitlines())
        if not files:
            continue
        title = next((line.strip() for line in body.splitlines() if line.strip()), "") if subject.startswith("Merge pull request") else subject.strip()
        in_the_app = any(path.startswith("apps/live-android/") for path in files)
        if title and title not in titles and not _PLUMBING.match(title) and (in_the_app or _LIVE_TITLE.search(title)):
            titles.append(title)
    return titles


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, encoding="utf-8").stdout


def _emit(values: Mapping[str, str], env: Mapping[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    path = env.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))


def main(argv: Optional[Sequence[str]] = None, run_git: Optional[Callable[..., str]] = _git,
         env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(description="Decisions of the weekly Android release")
    sub = parser.add_subparsers(dest="command", required=True)
    decide_parser = sub.add_parser("decide", help="is there anything to publish and which version")
    decide_parser.add_argument("--version", default=None, help="force this version (X.Y.Z, newer than the last one)")
    decide_parser.add_argument("--force", action="store_true", help="publish even without changes in the app")
    sub.add_parser("notes", help="short notes from GitHub's generated release notes (stdin)")
    app_parser = sub.add_parser("app-notes", help="the titles of the pull requests that touched the app since a tag, as bullets (what the notes of the release are made of)")
    app_parser.add_argument("--since", default=None, help="the tag of the previous release (empty: the whole history)")
    app_parser.add_argument("--until", default="HEAD")
    play_parser = sub.add_parser("play-summary", help="what to upload the bundle to Play Console: link, versionCode and notes to paste (the notes on stdin)")
    play_parser.add_argument("--version", required=True)
    play_parser.add_argument("--code", type=int, required=True, help="the versionCode of the bundle")
    play_parser.add_argument("--repo", required=True)
    play_parser.add_argument("--tag", required=True)
    play_parser.add_argument("--previous-code", type=int, default=None, help="the versionCode of the previous release, if it is known")
    args = parser.parse_args(argv)

    if args.command == "notes":
        print(summarize_notes(sys.stdin.read()))
        return 0
    if args.command == "app-notes":
        for title in app_pull_requests(run_git, args.since or None, args.until):
            print(f"* {title}")
        return 0
    if args.command == "play-summary":
        print(play_summary(args.version, args.code, args.repo, args.tag, sys.stdin.read(), args.previous_code))
        return 0
    try:
        tags = run_git("tag", "--list", f"{TAG_PREFIX}*").splitlines()
        last = last_release_tag(tags)
        changed = run_git("diff", "--name-only", last, "HEAD").splitlines() if last else []
        decision = decide(tags, changed, override=args.version or None, force=args.force)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Versión {decision.version}: {decision.reason}" if decision.release else f"Sin publicación: {decision.reason}")
    _emit({"release": str(decision.release).lower(), "version": decision.version or "",
           "previous_tag": decision.previous_tag or "", "reason": decision.reason}, env)
    return 0


if __name__ == "__main__":
    sys.exit(main())
