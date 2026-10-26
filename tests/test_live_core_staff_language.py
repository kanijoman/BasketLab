"""The alerts speak the staff's language (feedback 0.4.0, #566): «eFG 60 vs 75» did not say whose it was, with respect to what, and mentioned the adjustment to the history.

A guard for ANY text the engine writes, present or future: no string of ``src/live_core`` that can reach the staff (docstrings and comments do not count) uses the jargon of the analysis
(acronyms of the four factors, per-100 units, «ajustar al histórico», «neto», «esperado», «índice», «experimental»). Say it with the words of the bench: ours / the rival's, «lo habitual», «de diferencia».
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = sorted(p for p in (ROOT / "src" / "live_core").glob("*.py") if p.name not in {"config.py", "vectors.py", "version.py", "lexicon.py"})

# word -> what to say instead
BANNED = {
    "eFG": "acierto de tiro", "TOV%": "pérdidas", "ORB%": "rebote ofensivo", "pts/100": "puntos cada 100 posesiones", "histórico": "lo habitual",
    "sin ajustar": "", "% de victoria": "una palanca es un diagnóstico, no promete probabilidad (#567)", "si vuelve a su nivel habitual": "", "esperado": "lo habitual", "esperados": "lo habitual", "experimental": "estimación", "índice": "", " neto": "de diferencia", "netos": "de diferencia",
}


def strings(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            docstrings.add(id(node.body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.lineno, node.value


def test_the_guard_reads_the_engine():
    assert len(FILES) > 30 and sum(1 for f in FILES for _ in strings(f)) > 500


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_text_of_the_engine_uses_the_jargon_of_the_analysis(path):
    found = [f"{path.name}:{line}: «{word.strip()}» in {text[:70]!r}" for line, text in strings(path) for word in BANNED if word in text]
    assert not found, "say it with the words of the bench:\n" + "\n".join(found)
