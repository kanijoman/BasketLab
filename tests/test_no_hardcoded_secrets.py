"""Regression: no API key may be hardcoded in the source tree.

History: a Groq API key was once committed as a class default (since rotated and the LLM
code removed). Secrets must never be literals in source: they come from the environment.
"""

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
