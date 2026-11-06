"""A version of the code per section of ``web-data`` (issue #783).

The cache of #700 kept ONE version for all of ``src``: any change recomputed every section of every competition (about half an hour). Each section now has the version of the modules
it really depends on (the transitive imports of its exporter, read from the source), so a new section, or a change in one exporter, recomputes only that section.
"""
from pathlib import Path

import pytest

from src.local_data import build_cache
from src.local_data.build_cache import module_files, section_versions
from src.local_data.web_data import SECTION_MODULES, SECTIONS

REPO = Path(__file__).resolve().parents[1]


def tree(tmp_path, files):
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def names(files, root):
    return sorted(p.relative_to(root).as_posix() for p in files)


# ------------------------------------------------------------------------------------------------ the import graph
def test_the_closure_follows_top_level_lazy_relative_and_submodule_imports(tmp_path):
    root = tree(tmp_path, {
        "src/__init__.py": "", "src/pkg/__init__.py": "from .helper import h\n",
        "src/pkg/helper.py": "import json\nVALUE = 1\n", "src/pkg/service.py": "def f():\n    from src.pkg import lazy\n    return lazy\n",
        "src/pkg/lazy.py": "from src.other.deep import thing\n", "src/other/__init__.py": "", "src/other/deep.py": "thing = 1\n",
        "src/exporter.py": "import src.pkg.service as service\n", "src/unrelated.py": "x = 1\n",
    })
    assert names(module_files("src.exporter", root), root) == [
        "src/__init__.py", "src/exporter.py", "src/other/__init__.py", "src/other/deep.py", "src/pkg/__init__.py", "src/pkg/helper.py", "src/pkg/lazy.py", "src/pkg/service.py"]


def test_importing_a_package_member_that_is_a_module_pulls_the_module_and_the_packages_on_the_way(tmp_path):
    root = tree(tmp_path, {"src/__init__.py": "", "src/a/__init__.py": "", "src/a/b/__init__.py": "", "src/a/b/c.py": "", "src/e.py": "from src.a.b import c\n"})
    assert names(module_files("src.e", root), root) == ["src/__init__.py", "src/a/__init__.py", "src/a/b/__init__.py", "src/a/b/c.py", "src/e.py"]


def test_the_standard_library_third_party_packages_and_unknown_names_are_not_part_of_it(tmp_path):
    root = tree(tmp_path, {"src/__init__.py": "", "src/e.py": "import json, os\nimport numpy\nfrom pymongo import MongoClient\nimport src.missing\n"})
    assert names(module_files("src.e", root), root) == ["src/__init__.py", "src/e.py"]


def test_modules_imported_without_the_src_prefix_resolve_under_src_too(tmp_path):
    """The app puts ``src`` on the path in some entry points (``from utils.x import y``)."""
    root = tree(tmp_path, {"src/__init__.py": "", "src/utils/__init__.py": "", "src/utils/x.py": "", "src/e.py": "from utils.x import y\n"})
    assert "src/utils/x.py" in names(module_files("src.e", root), root)


def test_an_import_cycle_ends(tmp_path):
    root = tree(tmp_path, {"src/__init__.py": "", "src/a.py": "import src.b\n", "src/b.py": "import src.a\n"})
    assert names(module_files("src.a", root), root) == ["src/__init__.py", "src/a.py", "src/b.py"]


def test_a_file_that_does_not_parse_makes_it_depend_on_the_whole_tree_the_safe_side(tmp_path):
    root = tree(tmp_path, {"src/__init__.py": "", "src/e.py": "def broken(:\n", "src/other.py": "x = 1\n"})
    assert "src/other.py" in names(module_files("src.e", root), root)


# --------------------------------------------------------------------------------------------------- the versions
MODULES = {"alpha": "src.alpha", "beta": "src.beta"}
BASE = {"src/__init__.py": "", "src/alpha.py": "from src.shared import s\n", "src/beta.py": "import src.shared\n", "src/shared.py": "S = 1\n", "src/only_alpha.py": "A = 1\n"}


def test_a_change_in_a_dependency_changes_only_the_versions_of_the_sections_that_use_it(tmp_path):
    files = {**BASE, "src/alpha.py": "from src.shared import s\nimport src.only_alpha\n"}
    root = tree(tmp_path, files)
    before = section_versions(MODULES, root)
    (root / "src/only_alpha.py").write_text("A = 2\n", encoding="utf-8")
    after = section_versions(MODULES, root)
    assert after["alpha"] != before["alpha"] and after["beta"] == before["beta"]
    (root / "src/shared.py").write_text("S = 2\n", encoding="utf-8")
    assert section_versions(MODULES, root) != after and all(section_versions(MODULES, root)[k] != after[k] for k in MODULES)


def test_a_file_that_no_section_imports_changes_no_version(tmp_path):
    root = tree(tmp_path, BASE)
    before = section_versions(MODULES, root)
    (root / "src/unused.py").write_text("U = 1\n", encoding="utf-8")
    assert section_versions(MODULES, root) == before


def test_the_line_endings_do_not_change_a_version(tmp_path):
    root = tree(tmp_path, BASE)
    before = section_versions(MODULES, root)
    (root / "src/shared.py").write_bytes(b"S = 1\r\n")
    assert section_versions(MODULES, root) == before


def test_two_sections_on_the_same_module_share_its_version_and_it_is_stable_between_calls(tmp_path):
    root = tree(tmp_path, BASE)
    versions = section_versions({"a": "src.alpha", "b": "src.alpha"}, root)
    assert versions["a"] == versions["b"] == section_versions({"a": "src.alpha"}, root)["a"]


def test_a_section_can_depend_on_several_modules_and_its_version_covers_all_of_them(tmp_path):
    """The exporters get the database handler as an argument and call its methods without importing it: those modules are declared next to the exporter."""
    root = tree(tmp_path, {**BASE, "src/handler.py": "H = 1\n"})
    before = section_versions({"a": ["src.alpha", "src.handler"], "b": "src.alpha"}, root)
    (root / "src/handler.py").write_text("H = 2\n", encoding="utf-8")
    after = section_versions({"a": ["src.alpha", "src.handler"], "b": "src.alpha"}, root)
    assert after["a"] != before["a"] and after["b"] == before["b"]


def test_a_section_whose_module_cannot_be_found_gets_the_version_of_the_whole_tree(tmp_path):
    """Declared wrongly or renamed: it must recompute whenever anything changes, never go stale."""
    root = tree(tmp_path, BASE)
    before = section_versions({"x": "src.nowhere"}, root)["x"]
    (root / "src/shared.py").write_text("S = 3\n", encoding="utf-8")
    assert section_versions({"x": "src.nowhere"}, root)["x"] != before


def test_the_routers_do_not_count_in_any_section(tmp_path):
    root = tree(tmp_path, {**BASE, "src/api/__init__.py": "", "src/api/r.py": "x = 1\n"})
    before = section_versions({"a": "src.alpha"}, root)
    (root / "src/api/r.py").write_text("x = 2\n", encoding="utf-8")
    assert section_versions({"a": "src.alpha"}, root) == before


# -------------------------------------------------------------------------------------------------- the real tree
def test_every_section_of_the_publication_declares_the_module_of_its_exporter():
    assert set(SECTION_MODULES) == set(SECTIONS) - {"derived"}, "a new section must say which module computes it, or its cache would never notice a change"
    for module in {m for modules in SECTION_MODULES.values() for m in ([modules] if isinstance(modules, str) else modules)}:
        assert (REPO / (module.replace(".", "/") + ".py")).is_file() or (REPO / module.replace(".", "/") / "__init__.py").is_file(), module


def test_the_real_dependencies_of_the_sections_are_the_ones_each_exporter_uses():
    closure = {s: {p.relative_to(REPO).as_posix() for m in ([ms] if isinstance(ms, str) else ms) for p in module_files(m)} for s, ms in SECTION_MODULES.items()}
    assert "src/services/assist_links.py" in closure["assist_connections"]
    assert "src/services/assist_links.py" not in closure["rotations"]
    assert "src/services/rotation_service.py" in closure["rotations"]
    assert "src/services/rotation_service.py" not in closure["assist_connections"]
    assert all(f"src/local_data/{s}_export.py" in closure[s] or s in {"possession_csv"} for s in SECTION_MODULES)
    for section, files in closure.items():
        if section == "shots":
            continue                                                       # it reads the games' collection itself, not through the handler
        assert "src/database/repository.py" in files, f"{section}: the exporters call the database handler they are given, so its code is a dependency"
    assert "src/live_core/engine.py" not in closure["assist_connections"], "the live engine is nothing of the assist connections"


def test_the_real_versions_are_stable_and_one_per_section():
    first = section_versions(SECTION_MODULES)
    assert set(first) == set(SECTION_MODULES) and first == section_versions(dict(SECTION_MODULES))
    assert first["assist_connections"] != first["rotations"], "different exporters, different dependencies"
    assert first["possessions"] == first["possession_csv"], "the same exporter module"
    assert build_cache.EPOCH >= 1
