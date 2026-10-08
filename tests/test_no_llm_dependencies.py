"""Guard: BasketLab does not use external LLMs (Gemini / OpenAI / Groq).

Reports are generated deterministically; a rule-based report engine is planned (see
docs/ROADMAP.md). This test fails if an LLM SDK, key or the removed ``src/ai`` package
creeps back into the code, the frontend or the deployment configuration.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = re.compile(r"openai|google[._-]?generativeai|\bgroq\b|sse[_-]starlette|gemini", re.IGNORECASE)

SCANNED = [
    ("src", {".py"}),
    ("frontend/src", {".ts", ".tsx"}),
]
SCANNED_FILES = ["requirements.txt", "render.yaml", ".env.example", "frontend/package.json"]


def _offenders():
    found = []
    for folder, suffixes in SCANNED:
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in suffixes and path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore")
                if FORBIDDEN.search(text):
                    found.append(str(path.relative_to(ROOT)))
    for name in SCANNED_FILES:
        path = ROOT / name
        if path.exists() and FORBIDDEN.search(path.read_text(encoding="utf-8", errors="ignore")):
            found.append(name)
    return sorted(found)


def test_no_llm_sdk_or_provider_is_referenced():
    assert _offenders() == []


def test_the_removed_ai_package_and_router_are_gone():
    assert not (ROOT / "src" / "ai").exists() or not list((ROOT / "src" / "ai").glob("*.py"))
    assert not (ROOT / "src" / "api" / "routers" / "ai.py").exists()
    assert not (ROOT / "frontend" / "src" / "pages" / "AIAnalysisPage.tsx").exists()


def test_the_ai_url_prefix_is_not_served():
    from fastapi.testclient import TestClient

    from src.api.app import app

    client = TestClient(app)
    assert client.get("/api/v1/ai/analyze/stream").status_code == 404
