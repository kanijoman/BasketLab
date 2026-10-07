"""PreparationPackage: season data prepared by BasketLab for the live engine.

A package is a canonical JSON document wrapped in an envelope with a SHA-256 checksum,
so a tablet can detect corruption/tampering and incompatible schema versions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

SCHEMA_VERSION = 1

_REQUIRED = ("collection", "season", "team", "rival", "tables", "created_at")


class PackageError(ValueError):
    """The package is malformed."""


class IncompatibleSchemaError(PackageError):
    """The package was written with a schema version this engine does not support."""


class ChecksumMismatchError(PackageError):
    """The package content does not match its checksum."""


def make_package_id(collection: str, team_id: str, season: str) -> str:
    """Deterministic id: re-publishing the same match context replaces the old file."""
    return f"{collection}:{team_id}:{season}"


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class PreparationPackage:
    collection: str
    season: str
    team: Dict[str, Any]
    rival: Dict[str, Any]
    tables: Dict[str, Any]
    created_at: str
    competition_meta: Dict[str, Any] = field(default_factory=dict)
    baselines: Dict[str, Any] = field(default_factory=dict)
    rule_config: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    @property
    def package_id(self) -> str:
        return make_package_id(self.collection, str(self.team.get("id")), self.season)

    def _body(self) -> str:
        return _canonical(asdict(self))

    def checksum(self) -> str:
        return hashlib.sha256(self._body().encode("utf-8")).hexdigest()

    def dumps(self) -> str:
        return _canonical({"checksum": self.checksum(), "package": asdict(self)})

    @classmethod
    def loads(cls, text: str) -> "PreparationPackage":
        try:
            envelope = json.loads(text)
            body, checksum = envelope["package"], envelope["checksum"]
        except (ValueError, KeyError, TypeError) as exc:
            raise PackageError(f"Invalid package envelope: {exc}") from exc

        if hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest() != checksum:
            raise ChecksumMismatchError("Package checksum mismatch (corrupted or modified).")

        version = body.get("schema_version")
        if version != SCHEMA_VERSION:
            raise IncompatibleSchemaError(
                f"Package schema version {version} is not supported "
                f"(this engine reads version {SCHEMA_VERSION})."
            )
        missing = [k for k in _REQUIRED if k not in body]
        if missing:
            raise PackageError(f"Package is missing required fields: {missing}")
        return cls(**body)
