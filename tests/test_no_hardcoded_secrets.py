"""Regression: no API key may be hardcoded in the source tree.

Bug: ``AnalysisConfig.GROQ_API_KEY`` shipped with a literal Groq key as its class
default, so the secret lived in the repository (and its git history). Keys must come
from the environment (``GROQ_API_KEY``) or ``~/.basketlab/config.txt`` only.

The class defaults are checked statically (AST) because ``config.py`` loads the keys
at import time, so runtime values depend on the machine running the tests.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Provider key shapes: Groq (gsk_), Google (AIza), OpenAI (sk-...).
SECRET_PATTERNS = [
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
]


def test_no_api_key_literals_in_source_regression():
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(p.search(text) for p in SECRET_PATTERNS):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"Hardcoded API key literal found in: {sorted(offenders)}"


def test_analysis_config_key_defaults_are_none():
    tree = ast.parse((SRC / "ai" / "config.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AnalysisConfig")
    defaults = {}
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.endswith("_API_KEY"):
                defaults[node.target.id] = ast.literal_eval(node.value)
    assert set(defaults) == {"GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY"}
    assert all(v is None for v in defaults.values()), defaults.keys()
