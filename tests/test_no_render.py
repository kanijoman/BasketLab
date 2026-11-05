"""BasketLab has no dependency on, and no integration with, Render (decision of 05/11/2026, #334).

The service was the host of the API and the target of the deploy of ``ci.yml``; the data and the web are now published by Actions (``web-data``, ``live-packages``) and Vercel, and the
account is no longer part of the project. These guards keep it that way: no file of the repository names the platform (the dated reports of ``docs/evaluaciones/`` are history and are left
as they were), the deploy job and its helper are gone, and the health endpoint does not read a variable only that platform sets.
"""
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ("docs/evaluaciones/",)
# the docs that RECORD the decision and explain how to clean up outside the repository may name the platform in prose; code, workflows and configuration may not
DECISION_DOCS = {"CLAUDE.md", "README.md", "docs/ARCHITECTURE.md", "docs/OPERATIONS.md", "docs/ROADMAP.md", "docs/TESTING.md"}
SKIP = {"tests/test_no_render.py", ".test_durations"}
# «render» as the verb or the type of the code (an HTML report, a React `Render` type, a `// Render` section), not the platform
VERB = {"src/api/routers/reports.py", "frontend/src/lib/weeklyReport.ts", "frontend/src/pages/LineupsPage.tsx", "frontend/src/pages/RotacionesPage.tsx"}
PLATFORM = re.compile(r"render\.yaml|onrender|render\.com|RENDER_|(?<![A-Za-z])Render(?![A-Za-z(])")
INTEGRATION = re.compile(r"onrender|render\.com|RENDER_(?!GIT_COMMIT|DEPLOY_HOOK_URL|SCRAPER_DEPLOY_HOOK_URL|API_URL)")   # a URL or a variable only the platform sets (the names of the secrets to delete may be quoted in the docs)


def _tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    return [p for p in out if p and not p.endswith(("package-lock.json", ".png", ".jpg", ".ico", ".gz", ".bpkg", ".bpkgz", ".pdf", ".woff2", ".jar"))]


def test_no_file_of_the_repository_names_the_platform():
    found = []
    for path in _tracked():
        if path in SKIP or path in VERB or path.startswith(HISTORY) or not (ROOT / path).is_file():
            continue
        text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        pattern = INTEGRATION if path in DECISION_DOCS else PLATFORM
        found += [f"{path}: {m.group(0)}" for m in pattern.finditer(text)][:2]
    assert not found, found


@pytest.mark.parametrize("path", ["render.yaml", "scripts/post_deploy_check.py", "tests/test_post_deploy_check.py"])
def test_the_files_of_the_integration_are_gone(path):
    assert not (ROOT / path).exists(), path


def test_the_pipeline_has_no_deploy_job_and_no_workflow_reads_a_platform_secret():
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    assert "deploy-backend" not in ci["jobs"]
    assert not [p.name for p in (ROOT / ".github" / "workflows").glob("*.yml") if "RENDER" in p.read_text(encoding="utf-8")]


def test_the_health_endpoint_reports_the_commit_only_from_the_neutral_variable(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.app import app

    monkeypatch.setenv("RENDER_GIT_COMMIT", "from-the-platform")
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert TestClient(app).get("/api/v1/health").json()["commit"] is None
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    assert TestClient(app).get("/api/v1/health").json()["commit"] == "abc123"
