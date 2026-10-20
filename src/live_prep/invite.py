"""Invitations to a scope (issue #410): ``python -m src.live_prep.invite --scope club:1008631 [--scope ...] [--expires 2027-06-30]``.

Run with ``PACKAGE_MASTER_KEY`` (or the existing ``PACKAGE_PASSWORD``) in the environment: the key of a scope is derived from it, so nothing is
stored. It prints, for every scope, the link ``basketlab-live://invite#<token>`` (opens the app) and the token alone (the app's *Pegar clave o
enlace* takes either). Anyone who has the token can open that scope's packages: send it only to who should have access.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from .package_scopes import invite_link, invite_token
from .package_sealing import MIN_SECRET


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate invitations to one or more scopes of the live packages")
    parser.add_argument("--scope", action="append", required=True, help="club:<id>, competicion:<collection>, temporada:<year>, mensual:<YYYY-MM>...")
    parser.add_argument("--expires", help="date shown by the app as the end of the access (YYYY-MM-DD); the real cut is rotating the scope")
    args = parser.parse_args(argv)
    secret = os.environ.get("PACKAGE_MASTER_KEY") or os.environ.get("PACKAGE_PASSWORD", "")
    if len(secret) < MIN_SECRET:
        print(f"PACKAGE_MASTER_KEY (or PACKAGE_PASSWORD) must have at least {MIN_SECRET} characters", file=sys.stderr)
        return 2
    for scope in args.scope:
        token = invite_token(secret, scope, args.expires)
        print(f"{scope}\n  enlace: {invite_link(token)}\n  clave:  {token}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
