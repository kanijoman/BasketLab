"""Documentation stays in sync with the code (the "docs sync" rule, enforced).

CLAUDE.md and docs/*.md are written for Claude: compact, accurate, and updated in the same
PR as the change they describe. This test fails when:
  * a link or a `path` quoted in the docs points to a file that no longer exists;
  * a new src package, API router or live_core module is not mentioned in the docs;
  * a removed technology (desktop UI, LLMs, ...) is described as if it still existed;
  * CLAUDE.md grows beyond a compact size or loses the definition-of-done rule.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

CORE_DOCS = ["ARCHITECTURE.md", "DATA_FORMATS.md", "LIVE.md", "TESTING.md", "ROADMAP.md", "OPERATIONS.md"]
CLAUDE = ROOT / "CLAUDE.md"
ALL_DOCS = [CLAUDE, ROOT / "README.md"] + [DOCS / name for name in CORE_DOCS]

LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)#\s]+)")
PATH = re.compile(r"`((?:src|tests|frontend/src|docs|scripts|\.github)/[A-Za-z0-9_./-]+\.(?:py|md|ts|tsx|yml|json|mjs|txt))`")
UNTRACKED_OK = {"src/database/db_credentials.txt"}  # git-ignored by design
REMOVED = re.compile(r"PyQt|StatsExporter|NumericTableWidgetItem|build_windows|DISTRIBUTION_GUIDE|"
                     r"copilot-instructions|Gemini|OpenAI|Groq|src/ui/", re.IGNORECASE)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_documentation_set_exists():
    missing = [str(p.relative_to(ROOT)) for p in ALL_DOCS if not p.exists()]
    assert not missing, f"missing documentation files: {missing}"


def test_markdown_links_resolve():
    broken = []
    for doc in ALL_DOCS:
        if not doc.exists():
            continue
        for target in LINK.findall(_text(doc)):
            if not (doc.parent / target).resolve().exists():
                broken.append(f"{doc.name} -> {target}")
    assert not broken, broken


def test_paths_quoted_in_the_docs_exist():
    broken = []
    for doc in ALL_DOCS:
        if not doc.exists():
            continue
        for path in PATH.findall(_text(doc)):
            if "*" not in path and path not in UNTRACKED_OK and not (ROOT / path).exists():
                broken.append(f"{doc.name}: {path}")
    assert not broken, broken


def test_claude_md_is_compact_and_has_the_definition_of_done():
    text = _text(CLAUDE)
    assert len(text.splitlines()) <= 170, "CLAUDE.md must stay compact: move detail to docs/"
    assert "Definición de hecho" in text
    for name in CORE_DOCS:
        assert f"docs/{name}" in text, f"CLAUDE.md must point to docs/{name}"


def test_pull_request_template_asks_for_the_docs_review():
    template = ROOT / ".github" / "pull_request_template.md"
    assert template.exists() and "Docs revisados" in _text(template)


def test_removed_technologies_are_not_described_as_current():
    offenders = []
    for doc in ALL_DOCS:
        if doc.exists() and doc.name != "ROADMAP.md":  # the roadmap may mention history
            for match in REMOVED.finditer(_text(doc)):
                offenders.append(f"{doc.name}: {match.group(0)}")
    assert not offenders, offenders


def test_every_src_package_is_documented_in_architecture():
    text = _text(DOCS / "ARCHITECTURE.md")
    packages = [p.name for p in (ROOT / "src").iterdir()
                if p.is_dir() and (p / "__init__.py").exists()]
    missing = [name for name in packages if f"src/{name}" not in text]
    assert not missing, f"undocumented src packages: {missing}"


def test_every_api_router_is_documented_in_architecture():
    text = _text(DOCS / "ARCHITECTURE.md")
    routers = [p.stem for p in (ROOT / "src" / "api" / "routers").glob("*.py") if p.stem != "__init__"]
    missing = [name for name in routers if name not in text]
    assert not missing, f"undocumented routers: {missing}"


def test_every_live_core_module_is_documented_in_live():
    text = _text(DOCS / "LIVE.md")
    modules = [p.stem for p in (ROOT / "src" / "live_core").glob("*.py") if p.stem != "__init__"]
    missing = [name for name in modules if name not in text]
    assert not missing, f"undocumented live_core modules: {missing}"


def test_obsolete_files_are_gone():
    gone = ["DISTRIBUTION_GUIDE.md", "build_windows.ps1", "install_dependencies.ps1", "test_results.txt",
            "coverage_summary.py", "DATABASE_CONFIG.md", "MANUAL_TESTING_PLAN.md", "claude.md",
            "resources", ".github/copilot-instructions.md", ".github/MANDATORY_CHECKS.md",
            ".github/WORKFLOW.md", ".github/workflows/build.yml", "src/utils.py",
            "scripts/possession_export.py", "tests/test_debug_tipoff.py"]
    # `claude.md` and `CLAUDE.md` are the same file on case-insensitive systems: compare exact names
    tracked = {p.name for p in ROOT.iterdir()}
    leftovers = [g for g in gone if "/" not in g and g in tracked] + \
                [g for g in gone if "/" in g and (ROOT / g).exists()]
    assert not leftovers, leftovers
