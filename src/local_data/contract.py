"""The contract of ``web-data`` (#328): what the browser reads, declared ONCE.

``index.json`` (``WebDataManifest``) and the index of the reports of each competition (``ReportIndex``) are what a client needs before it opens a sealed
file. This module is their single description: the exporter writes them, ``validate_*`` checks a publication against it and ``render_typescript``
generates ``frontend/src/webdata/contract.generated.ts`` (``python run_web_contract.py``; a test fails when the file is behind). The rows (``export``)
and the reports' own shape are pinned by the committed publication and the parity vectors instead, not by this module.
"""
# no ``from __future__ import annotations``: with postponed annotations a TypedDict cannot see which keys are ``NotRequired``
import typing
from typing import Any, List, Literal, NotRequired, TypedDict, get_args, get_origin, get_type_hints

SCHEMA = 1


class Wrap(TypedDict):
    """The key of a sealed file, wrapped for one scope (``abierto``, ``club:<id>``, ``competicion:<collection>``...)."""
    scope: str
    iv: str
    key: str


class FileEntry(TypedDict):
    """A file of the publication: its path, its size and the sha256 of its content (the name carries the start of the hash)."""
    file: str
    bytes: int
    sha256: str


class RowsEntry(FileEntry):
    """The sealed rows of a competition (``rows/``), or its sealed ``DERIVED`` per game (``derived/``, #676), its shots (``shots/``, #685) or the rotation analysis of its teams
    (``rotations/``, #684; ``games`` counts its teams) the list and analysis of its matches (``matches/``, #677), or the possessions page (``possessions/``) and its per-possession CSV (``possession_csv/``, #679): same entry, other content."""
    collection: str
    league: Literal["feb", "fbcyl"]
    games: int
    wraps: List[Wrap]


class ReportIndexEntry(FileEntry):
    """The (plain) index of the sealed reports of a competition (``reports/``)."""
    collection: str
    teams: int


class WebDataManifest(TypedDict):
    """``index.json``: the only file that keeps its name. ``v`` and ``open_key`` are those of the live packages' index (the key of the ``abierto`` scope)."""
    schema: int
    v: int
    open_key: NotRequired[str]
    rows: List[RowsEntry]
    derived: NotRequired[List[RowsEntry]]
    shots: NotRequired[List[RowsEntry]]
    rotations: NotRequired[List[RowsEntry]]
    matches: NotRequired[List[RowsEntry]]
    possessions: NotRequired[List[RowsEntry]]
    possession_csv: NotRequired[List[RowsEntry]]
    reports: List[ReportIndexEntry]


class ReportEntry(FileEntry):
    """One sealed report: its team, its mode and the wraps of its key. ``scouting`` is the full scouting of the rival (#638) and then ``scope`` says which
    games it counts: ``liga`` (the league), ``copa`` (the cups of the season) or ``todo`` (both)."""
    team_id: str
    team: str
    mode: Literal["own", "rival", "scouting"]
    scope: NotRequired[Literal["liga", "copa", "todo"]]
    wraps: List[Wrap]


class ReportIndex(TypedDict):
    """The index of the reports of one competition."""
    collection: str
    reports: List[ReportEntry]


MODELS = (Wrap, FileEntry, RowsEntry, ReportIndexEntry, WebDataManifest, ReportEntry, ReportIndex)


class ContractError(ValueError):
    """A publication that does not satisfy the contract; the message says where."""


def _check(value: Any, hint: Any, path: str) -> None:
    origin = get_origin(hint)
    if origin is Literal:
        if value not in get_args(hint):
            raise ContractError(f"{path}: {value!r} is not one of {list(get_args(hint))}")
    elif origin in (list, List):
        if not isinstance(value, list):
            raise ContractError(f"{path}: a list was expected, not {type(value).__name__}")
        for i, item in enumerate(value):
            _check(item, get_args(hint)[0], f"{path}[{i}]")
    elif typing.is_typeddict(hint):
        if not isinstance(value, dict):
            raise ContractError(f"{path}: an object was expected, not {type(value).__name__}")
        hints = get_type_hints(hint)
        for key in hint.__required_keys__:
            if key not in value:
                raise ContractError(f"{path}: the key {key!r} is missing")
        for key, item in value.items():
            if key in hints:
                _check(item, hints[key], f"{path}.{key}")
    elif hint is bool:
        if not isinstance(value, bool):
            raise ContractError(f"{path}: a boolean was expected")
    elif hint is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ContractError(f"{path}: an integer was expected, not {type(value).__name__} ({value!r})")
    elif hint is str:
        if not isinstance(value, str):
            raise ContractError(f"{path}: a string was expected, not {type(value).__name__}")


def validate_manifest(manifest: Any) -> None:
    """Raise ``ContractError`` unless ``manifest`` is a ``WebDataManifest`` of the current ``SCHEMA``."""
    _check(manifest, WebDataManifest, "manifest")
    if manifest["schema"] != SCHEMA:
        raise ContractError(f"manifest.schema: {manifest['schema']} is not the schema {SCHEMA} of this contract")


def validate_report_index(index: Any) -> None:
    _check(index, ReportIndex, "report index")


def _ts_type(hint: Any) -> str:
    origin = get_origin(hint)
    if origin is Literal:
        return " | ".join(f"'{value}'" for value in get_args(hint))
    if origin in (list, List):
        inner = _ts_type(get_args(hint)[0])
        return f"({inner})[]" if " | " in inner else f"{inner}[]"
    if typing.is_typeddict(hint):
        return hint.__name__
    return {str: "string", int: "number", float: "number", bool: "boolean"}[hint]


def render_typescript() -> str:
    """The TypeScript types of the contract (every interface flattened: the browser has no use for the inheritance of the Python side)."""
    out = ["// AUTO-GENERATED by run_web_contract.py from src/local_data/contract.py: do not edit (a test fails when it is behind).",
           f"// The shape of what the web reads of `web-data` before it opens a sealed file (issue #328). Schema {SCHEMA}.", "",
           f"export const WEB_DATA_SCHEMA = {SCHEMA}", ""]
    for model in MODELS:
        out.append(f"/** {(model.__doc__ or '').strip()} */")
        out.append(f"export interface {model.__name__} {{")
        for key, hint in get_type_hints(model).items():
            out.append(f"  {key}{'' if key in model.__required_keys__ else '?'}: {_ts_type(hint)}")
        out += ["}", ""]
    return "\n".join(out)
