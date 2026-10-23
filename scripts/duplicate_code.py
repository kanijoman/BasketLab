"""Duplicate-code report (issue #452): blocks of identical normalised lines in different places.

The quality issues of the repo measure size and complexity, none measures duplicated functionality. This takes ``src/`` and the frontends (not tests, dependencies or build output),
drops blank lines, comments, imports and indentation, and reports every maximal run of at least ``--min-lines`` identical lines that appears in two or more places.
``python scripts/duplicate_code.py [--root .] [--min-lines 8] [--top 12]``: informative (always exit 0); it writes a markdown summary to ``$GITHUB_STEP_SUMMARY`` when it is set,
so the CI shows the baseline and its trend. Standard library only.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

LANGUAGES = {"python": (("*.py",), "#"), "typescript": (("*.ts", "*.tsx"), "//")}
SKIP_PARTS = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build", "tests", "JSON_samples", "pyodide", "public", ".git"}
SKIP_NAME_MARKERS = (".test.", ".spec.", ".d.ts")
NOISE = {"{", "}", ")", "]", "},", "),", "],", "(", "[", "else:", "try:", "pass"}
PYTHON_SKIPPED_STARTS = ('"""', "'''", "import ", "from ")


@dataclass(frozen=True)
class Place:
    file: str
    start: int
    end: int


@dataclass
class Block:
    length: int
    places: List[Place]

    @property
    def across_files(self) -> bool:
        return len({p.file for p in self.places}) > 1


def _source_files(root: Path, suffixes: Sequence[str]) -> Iterator[Path]:
    for suffix in suffixes:
        for path in sorted(root.rglob(suffix)):
            relative = path.relative_to(root)
            if SKIP_PARTS & set(relative.parts[:-1]) or any(marker in path.name for marker in SKIP_NAME_MARKERS):
                continue
            yield path


def _normalised(path: Path, comment: str, python: bool) -> List[Tuple[int, str]]:
    """``(line number, text)`` of the lines that carry code: no blanks, comments, imports or lone brackets; whitespace collapsed."""
    lines = []
    for number, raw in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith(comment) or text in NOISE or (python and text.startswith(PYTHON_SKIPPED_STARTS)):
            continue
        lines.append((number, re.sub(r"\s+", " ", text)))
    return lines


def _extend(files: List[List[Tuple[int, str]]], places: List[Tuple[int, int]], length: int) -> int:
    """How long the run is once it is grown line by line while every place keeps agreeing."""
    while True:
        nexts = [files[f][k + length][1] if k + length < len(files[f]) else None for f, k in places]
        if None in nexts or len(set(nexts)) != 1:
            return length
        length += 1


def _blocks(files: List[Tuple[str, List[Tuple[int, str]]]], min_lines: int) -> List[Block]:
    texts = [lines for _, lines in files]
    windows: Dict[tuple, List[Tuple[int, int]]] = defaultdict(list)
    for f, lines in enumerate(texts):
        for k in range(len(lines) - min_lines + 1):
            windows[tuple(t for _, t in lines[k:k + min_lines])].append((f, k))
    covered, found = set(), []
    for f, lines in enumerate(texts):
        for k in range(len(lines) - min_lines + 1):
            places = windows[tuple(t for _, t in lines[k:k + min_lines])]
            if len(places) < 2 or (f, k) in covered:
                continue
            length = _extend(texts, places, min_lines)
            covered.update((pf, pk + d) for pf, pk in places for d in range(length - min_lines + 1))
            found.append(Block(length, [Place(files[pf][0], texts[pf][pk][0], texts[pf][pk + length - 1][0]) for pf, pk in places]))
    return sorted(found, key=lambda b: -b.length)


def find_duplicates(root: Path, min_lines: int = 8) -> Dict[str, List[Block]]:
    root = Path(root)
    result = {}
    for language, (suffixes, comment) in LANGUAGES.items():
        files = [(path.relative_to(root).as_posix(), _normalised(path, comment, language == "python")) for path in _source_files(root, suffixes)]
        result[language] = _blocks(files, min_lines)
    return result


def summarize(found: Dict[str, List[Block]]) -> Dict[str, Dict[str, int]]:
    return {language: {"blocks": len(blocks), "redundant_lines": sum(b.length * (len(b.places) - 1) for b in blocks),
                       "across_files": sum(b.across_files for b in blocks), "within_file": sum(not b.across_files for b in blocks)}
            for language, blocks in found.items()}


def report(found: Dict[str, List[Block]], min_lines: int, top: int) -> str:
    summary = summarize(found)
    if not any(s["blocks"] for s in summary.values()):
        return f"## Código duplicado\n\nsin bloques duplicados de {min_lines} líneas o más."
    lines = ["## Código duplicado (informativo)", "", f"Bloques de {min_lines} o más líneas idénticas (sin comentarios, imports ni sangrado; sin tests).", "",
             "| Lenguaje | Bloques | Líneas redundantes | Entre ficheros | Dentro de un fichero |", "|---|---|---|---|---|"]
    lines += [f"| {lang} | {s['blocks']} | {s['redundant_lines']} | {s['across_files']} | {s['within_file']} |" for lang, s in summary.items()]
    for language, blocks in found.items():
        across = [b for b in blocks if b.across_files][:top]
        if across:
            lines += ["", f"### {language}: los {len(across)} mayores entre ficheros", ""]
            lines += [f"- {b.length} líneas × {len(b.places)}: " + " · ".join(f"`{p.file}:{p.start}-{p.end}`" for p in b.places[:4]) for b in across]
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Duplicate-code report (informative)")
    parser.add_argument("--root", default=".")
    parser.add_argument("--min-lines", type=int, default=8)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args(argv)
    text = report(find_duplicates(Path(args.root), args.min_lines), args.min_lines, args.top)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
