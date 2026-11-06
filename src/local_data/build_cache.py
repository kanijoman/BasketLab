"""What the last publication was made of (#700, #783), so a refresh computes only what changed.

``build-cache.json`` sits in the publication next to the manifest and holds, per competition, a fingerprint of its inputs (the sha of its sealed rows and of its derived figures),
the sections that had something to publish and **the version of the code of each section**. It has hashes only, nothing readable. A section of a competition whose fingerprint and
section version are the same reuses its sealed file; anything else (new or corrected game, new code of that section, a missing or unreadable memory, a file that is gone) is computed
again.

The version of a section is the hash of the modules it really depends on: the transitive imports of its exporter, read from the source (``module_files``). Before #783 there was one
version for all of ``src/``, so adding a section, or touching one exporter, recomputed every section of every competition (about half an hour). A module that cannot be analysed
makes the section depend on the whole tree: it can only recompute more, never keep something stale.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

CACHE = "build-cache.json"
EPOCH = 1                            # raise it to make the next publication compute everything again (a change in how sections are sealed, a doubt about the memory)
_REPO = Path(__file__).resolve().parent.parent.parent
_OUT_OF_THE_BUILD = {"api"}          # the routers do not shape a published file (the exporters call the same service functions the routers do)


# --------------------------------------------------------------------------------------------- the import graph
def _resolve(name: str, root: Path) -> Optional[Path]:
    """The file of a module of the repository: ``src.a.b`` and, as the entry points that put ``src`` on the path import it, ``a.b``."""
    for base in (root, root / "src"):
        target = base.joinpath(*name.split("."))
        if target.with_suffix(".py").is_file():
            return target.with_suffix(".py")
        if (target / "__init__.py").is_file():
            return target / "__init__.py"
    return None


def _out_of_the_build(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return len(parts) > 1 and parts[0] == "src" and parts[1] in _OUT_OF_THE_BUILD


def _everything(root: Path) -> Set[Path]:
    return {p for p in (root / "src").rglob("*.py") if "__pycache__" not in p.parts and not _out_of_the_build(p, root)}


def _module_of(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path, root: Path) -> Optional[List[str]]:
    """The modules a file imports, wherever the import is (top level or inside a function); ``None`` when the file cannot be read or parsed."""
    try:
        tree = ast.parse(path.read_bytes().decode("utf-8-sig", errors="replace"))     # a BOM or a stray byte of another encoding must not make the file «unreadable»
    except (OSError, SyntaxError, ValueError):
        return None
    module = _module_of(path, root)
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")
                anchor = anchor[:len(anchor) - (node.level - 1)] if node.level > 1 else anchor
                base = ".".join([p for p in anchor if p] + ([node.module] if node.module else []))
            if base:
                found.append(base)
                found.extend(f"{base}.{alias.name}" for alias in node.names if alias.name != "*")      # ``from pkg import module``
    return found


def module_files(module: str, root: Optional[Path] = None) -> Set[Path]:
    """The files ``module`` depends on: itself, everything it imports (transitively, wherever the import is) and the ``__init__`` of every package on the way.
    Only the repository counts (the standard library and the installed packages do not); the routers (``src/api``) do not either. Empty when ``module`` is not found.

    The ``__init__`` of a package that is only on the way to a module (``src/services/__init__.py`` for ``src.services.assist_links``) counts as a file (its text is hashed) but its own
    imports are not followed: those files re-export the whole package, and following them would make every section depend on everything. The ``__init__`` of a package that is
    imported itself (``from src.database import MongoDBHandler``) is followed: its members really come from there."""
    root = Path(root) if root is not None else _REPO
    if _resolve(module, root) is None:
        return set()                                                          # not found: the caller decides (the whole tree)
    files: Set[Path] = set()
    followed: Set[Path] = set()
    pending = [module]
    seen: Set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            path = _resolve(".".join(parts[:i]), root)
            if path is None or _out_of_the_build(path, root):
                continue
            files.add(path)
            if i == len(parts) and path not in followed:                      # the module itself (or the package imported by name): what it imports counts
                followed.add(path)
                imported = _imports(path, root)
                if imported is None:                                          # cannot analyse it: depend on everything
                    return _everything(root)
                pending.extend(imported)
    return files


def section_versions(modules: Mapping[str, Union[str, Sequence[str]]], root: Optional[Path] = None) -> Dict[str, str]:
    """``{section: version}`` for ``{section: module or modules of its exporter}``: the hash of the files each one depends on (line endings do not count). A section lists, next to its
    exporter, what it uses WITHOUT importing it (the exporters are handed the database handler and call its methods): those modules count as its dependencies too."""
    root = Path(root) if root is not None else _REPO
    by_modules: Dict[Tuple[str, ...], str] = {}
    versions: Dict[str, str] = {}
    for section, declared in modules.items():
        names = (declared,) if isinstance(declared, str) else tuple(declared)
        if names not in by_modules:
            found = [module_files(name, root) for name in names]
            files = set().union(*found) if all(found) else _everything(root)   # one not found (renamed, declared wrongly): the whole tree, the safe side
            digest = hashlib.sha256()
            for path in sorted(files):
                digest.update(path.relative_to(root).as_posix().encode("utf-8"))
                digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
            by_modules[names] = digest.hexdigest()[:16]
        versions[section] = by_modules[names]
    return versions


# ------------------------------------------------------------------------------------------------- the memory
def fingerprint(rows_sha: str, derived_sha: Optional[str]) -> str:
    return hashlib.sha256(f"{rows_sha}|{derived_sha or ''}".encode("utf-8")).hexdigest()


def load(out_dir: Path) -> Dict[str, Any]:
    """The memory of the previous publication; empty when it is missing, is not what this code writes or is of another ``EPOCH``/format (the first publication after #783 computes everything once)."""
    empty: Dict[str, Any] = {"epoch": None, "competitions": {}}
    try:
        data = json.loads((Path(out_dir) / CACHE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict) or not isinstance(data.get("competitions"), dict):
        return empty
    return {"epoch": data.get("epoch"), "competitions": {k: v for k, v in data["competitions"].items() if isinstance(v, dict)}}


def save(out_dir: Path, competitions: Dict[str, Dict[str, Any]]) -> bytes:
    return (json.dumps({"epoch": EPOCH, "competitions": {k: competitions[k] for k in sorted(competitions)}}, indent=1) + "\n").encode("utf-8")
