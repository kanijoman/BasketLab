"""The deploy key of the private archive (#646) as a file OpenSSH accepts, whatever happened to it on its way through a secret.

A key saved by hand in a GitHub secret arrives with Windows line endings, a BOM, NULs (UTF-16 piped as bytes), spaces or a literal ``\n`` instead
of newlines, quotes, or without the final newline, and OpenSSH answers ``error in libcrypto`` to all of them. The base64 body between the
BEGIN/END lines is all that matters: it is rebuilt in the standard layout. Errors describe the text (length, lines, header) and never repeat it.
"""
from __future__ import annotations

import re
import sys
import textwrap

_KEY = re.compile(r"-----BEGIN ([A-Z0-9 ]+)-----(.*?)-----END \1-----", re.DOTALL)
WIDTH = 70


def _describe(text: str) -> str:
    return (f"{len(text)} characters, {len(text.splitlines())} lines, BEGIN header: {'yes' if '-----BEGIN' in text else 'no'}, "
            f"END footer: {'yes' if '-----END' in text else 'no'}")


def normalise_key(text: str) -> str:
    """The private key in ``text`` in the standard layout (header, base64 in lines of 70, footer, final newline); ``ValueError`` if there is none."""
    cleaned = text.replace("\x00", "").replace("\ufeff", "")
    found = _KEY.search(cleaned)
    body = re.sub(r"[^A-Za-z0-9+/=]", "", found.group(2).replace("\n", "")) if found else ""
    if not body:
        raise ValueError(f"not a private key ({_describe(text)})")
    return f"-----BEGIN {found.group(1)}-----\n" + "\n".join(textwrap.wrap(body, WIDTH)) + f"\n-----END {found.group(1)}-----\n"


def main(argv=None) -> int:
    """``python -m src.local_data.ssh_key < raw > key``: the normalised key on stdout; exit 1 (with the description, not the text) if it is not one."""
    try:
        sys.stdout.buffer.write(normalise_key(sys.stdin.buffer.read().decode("utf-8", errors="replace")).encode("ascii"))   # bytes: a text stdout would write CRLF on Windows
    except ValueError as error:
        print(f"ARCHIVE_DEPLOY_KEY: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
