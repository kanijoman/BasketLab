"""How the publisher encrypts what it publishes (issue #410): by password (what the apps in the field read) or by scope.

``LegacySealer`` is the envelope v1 of always (PBKDF2 of the password, no extras). ``ScopedSealer`` is the envelope v2 of
``package_scopes``: the wraps of the key go to the index entry of the file and, while the beta is open, the index publishes the key of the
``abierto`` scope. The config (``config/package_publish.json`` → ``access``) chooses: ``legacy`` until the release of the app that reads
scopes is out, then ``scoped``.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .package_crypto import encrypt_package
from .package_scopes import SCOPE_OPEN, scope_key, seal

MIN_SECRET = 8
INDEX_VERSION_LEGACY = 1
INDEX_VERSION_SCOPED = 2


class LegacySealer:
    index_version = INDEX_VERSION_LEGACY

    def __init__(self, passphrase: str) -> None:
        self.passphrase = passphrase

    def seal(self, plaintext: str, scopes: Sequence[str] = (), compress: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """``(envelope, extra fields of the index entry)``; a password has no scopes."""
        return encrypt_package(plaintext, self.passphrase, compress=compress), {}

    def index_extra(self) -> Dict[str, Any]:
        return {}


class ScopedSealer:
    index_version = INDEX_VERSION_SCOPED

    def __init__(self, master: str, open_access: bool = True, extra_scopes: Sequence[str] = (), monthly: bool = False,
                 now: Optional[datetime] = None) -> None:
        self.master, self.open_access, self.extra_scopes, self.monthly = master, open_access, tuple(extra_scopes), monthly
        self.now = now or datetime.now(timezone.utc)

    def scopes_for(self, scopes: Sequence[str]) -> List[str]:
        """The scopes that wrap a package: the open one while the beta lasts, the ones of the package, the fixed ones and this month's."""
        found = ([SCOPE_OPEN] if self.open_access else []) + list(scopes) + list(self.extra_scopes)
        if self.monthly:
            found.append(f"mensual:{self.now:%Y-%m}")
        return list(dict.fromkeys(found))

    def seal(self, plaintext: str, scopes: Sequence[str] = (), compress: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        envelope, wraps = seal(plaintext, self.master, self.scopes_for(scopes), compress=compress)
        return envelope, {"wraps": wraps}

    def index_extra(self) -> Dict[str, Any]:
        """The key of the open scope, published in the index while the beta is open (the app finds it and opens by itself)."""
        if not self.open_access:
            return {}
        return {"open_key": base64.b64encode(scope_key(self.master, SCOPE_OPEN)).decode("ascii")}


Sealer = Union[LegacySealer, ScopedSealer]


def as_sealer(value: Union[str, Sealer]) -> Sealer:
    """A password is the legacy sealer (what the callers that predate scopes pass)."""
    return LegacySealer(value) if isinstance(value, str) else value


def make_sealer(access: Mapping[str, Any], env: Mapping[str, str], now: Optional[datetime] = None) -> Sealer:
    """The sealer of the config's ``access`` and the secrets in ``env`` (``PACKAGE_MASTER_KEY``, or the existing ``PACKAGE_PASSWORD``)."""
    if access.get("mode", "legacy") == "legacy":
        secret = env.get("PACKAGE_PASSWORD", "")
    else:
        secret = env.get("PACKAGE_MASTER_KEY") or env.get("PACKAGE_PASSWORD", "")
    if len(secret) < MIN_SECRET:
        raise ValueError(f"PACKAGE_PASSWORD (or PACKAGE_MASTER_KEY) must have at least {MIN_SECRET} characters")
    if access.get("mode", "legacy") == "legacy":
        return LegacySealer(secret)
    return ScopedSealer(secret, bool(access.get("open", True)), access.get("scopes", ()), bool(access.get("monthly", False)), now)
