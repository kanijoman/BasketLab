"""Decisions of the weekly Android release (issue #279): which version, and is there anything to publish?

Every Friday morning ``live-android-release.yml`` publishes the app with everything integrated since the last release;
the staff updates from the app (#227). This script holds the decisions in plain Python so they are tested::

    python scripts/live_android_release.py decide [--version X.Y.Z] [--force]   # writes release/version/... outputs
    python scripts/live_android_release.py notes < generated-notes.md           # short notes for the app's notice

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
    args = parser.parse_args(argv)

    if args.command == "notes":
        print(summarize_notes(sys.stdin.read()))
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
