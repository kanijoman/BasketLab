"""The duplicate-code report (issue #452): blocks of identical normalised lines in different places, as a baseline in the CI summary (informative, never blocks).

``scripts/duplicate_code.py`` was a throw-away detector that measured 88 Python and 21 TypeScript duplicated blocks; these tests fix its criterion so the figures can be compared over time.
"""
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import duplicate_code as dc  # noqa: E402


def body(prefix, n=10):
    return "\n".join(f"    {prefix}_{i} = compute({i}) + {i}" for i in range(n))


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


def twin(root, a="src/a.py", b="src/b.py", lines=10):
    block = body("same", lines)
    write(root, a, f"def one():\n{block}\n")
    write(root, b, f"def other():\n{block}\n")


def test_a_block_that_two_files_share_is_found_with_both_places(tmp_path):
    twin(tmp_path)
    (block,) = dc.find_duplicates(tmp_path, min_lines=8)["python"]
    assert block.length == 10 and {p.file for p in block.places} == {"src/a.py", "src/b.py"} and block.across_files


def test_a_run_shorter_than_the_minimum_is_not_a_duplicate(tmp_path):
    twin(tmp_path, lines=7)
    assert dc.find_duplicates(tmp_path, min_lines=8)["python"] == []


def test_one_long_block_is_one_finding_not_one_per_window(tmp_path):
    twin(tmp_path, lines=15)
    blocks = dc.find_duplicates(tmp_path, min_lines=8)["python"]
    assert [b.length for b in blocks] == [15]


def test_indentation_blank_lines_comments_and_imports_do_not_hide_a_duplicate(tmp_path):
    write(tmp_path, "src/a.py", "import os\n\n" + "\n".join(f"x_{i} = f({i})  " for i in range(9)) + "\n")
    write(tmp_path, "src/b.py", "from sys import path\n# note\n" + "\n".join(f"\t\tx_{i}   =   f({i})\n# comment" for i in range(9)) + "\n")
    (block,) = dc.find_duplicates(tmp_path, min_lines=8)["python"]
    assert block.length == 9


def test_a_block_repeated_inside_one_file_is_reported_as_within_file(tmp_path):
    block = body("again")
    write(tmp_path, "src/a.py", f"def one():\n{block}\n\ndef two():\n{block}\n")
    (found,) = dc.find_duplicates(tmp_path, min_lines=8)["python"]
    assert not found.across_files and len(found.places) == 2


def test_tests_dependencies_and_build_output_are_not_counted(tmp_path):
    for folder in ("tests", "node_modules/pkg", "frontend/dist", "src/__pycache__"):
        twin(tmp_path, a=f"{folder}/a.py", b=f"{folder}/b.py")
    write(tmp_path, "src/x.test.ts", body("same") + "\n")
    write(tmp_path, "src/y.test.ts", body("same") + "\n")
    assert dc.find_duplicates(tmp_path, min_lines=8) == {"python": [], "typescript": []}


def test_typescript_is_read_with_its_own_comment_marker(tmp_path):
    block = "\n".join(f"  const v{i} = compute({i})" for i in range(9))
    write(tmp_path, "frontend/src/A.tsx", f"// header\nexport function A() {{\n{block}\n}}\n")
    write(tmp_path, "frontend/src/B.tsx", f"export function B() {{\n// other\n{block}\n}}\n")
    (found,) = dc.find_duplicates(tmp_path, min_lines=8)["typescript"]
    assert found.length == 9 and found.across_files


def test_the_summary_counts_the_redundant_lines_of_each_language(tmp_path):
    twin(tmp_path, lines=10)
    summary = dc.summarize(dc.find_duplicates(tmp_path, min_lines=8))["python"]
    assert summary == {"blocks": 1, "redundant_lines": 10, "across_files": 1, "within_file": 0}
    assert dc.summarize(dc.find_duplicates(tmp_path, min_lines=8))["typescript"]["blocks"] == 0


def test_the_report_is_informative_it_exits_zero_and_writes_the_markdown_summary(tmp_path, monkeypatch, capsys):
    twin(tmp_path)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert dc.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Código duplicado" in out and "src/a.py" in out and "src/b.py" in out
    assert "Código duplicado" in summary.read_text(encoding="utf-8")


def test_a_clean_tree_says_so(tmp_path, capsys):
    write(tmp_path, "src/a.py", "x = 1\n")
    assert dc.main(["--root", str(tmp_path)]) == 0
    assert "sin bloques duplicados" in capsys.readouterr().out
