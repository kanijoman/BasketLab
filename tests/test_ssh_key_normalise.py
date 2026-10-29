"""The deploy key of the private archive (#646) reaches the workflow through a secret that someone saved by hand: whatever mangled it on the way
(Windows line endings, a BOM, spaces or a literal ``\n`` instead of newlines, quotes, no final newline) must not stop the refresh with OpenSSH's
opaque ``error in libcrypto``. ``normalise_key`` rebuilds the standard file from the base64 body; ssh-keygen itself is the judge.
"""
import shutil
import sys
import subprocess

import pytest

from src.local_data.ssh_key import normalise_key

pytestmark = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen is needed to judge the keys")


@pytest.fixture(scope="module")
def key(tmp_path_factory):
    path = tmp_path_factory.mktemp("key") / "k"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True)
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _public(tmp_path, text):
    target = tmp_path / "candidate"
    target.write_bytes(text.encode("utf-8"))
    target.chmod(0o600)
    result = subprocess.run(["ssh-keygen", "-y", "-f", str(target)], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


MANGLES = {
    "as is": lambda k: k,
    "windows line endings": lambda k: k.replace("\n", "\r\n"),
    "bom and windows line endings": lambda k: "\ufeff" + k.replace("\n", "\r\n"),
    "no final newline": lambda k: k.rstrip("\n"),
    "newlines turned into spaces": lambda k: k.replace("\n", " "),
    "newlines written as backslash n": lambda k: k.replace("\n", "\n"),
    "wrapped in quotes": lambda k: '"' + k.rstrip("\n") + '"',
    "surrounded by blank lines and indentation": lambda k: "\n\n  " + k.replace("\n", "\n  ") + "\n\n",
    "utf-16 text decoded as utf-8 leaves nulls": lambda k: k.replace("\n", "\r\n").replace("A", "A\x00"),
}


@pytest.mark.parametrize("name", [n for n in MANGLES if "nulls" not in n])
def test_every_common_way_of_mangling_the_key_still_gives_the_same_key(key, tmp_path, name):
    want = _public(tmp_path, key)
    assert want and _public(tmp_path, normalise_key(MANGLES[name](key))) == want


def test_a_key_with_stray_nulls_is_cleaned_too(key, tmp_path):
    """What PowerShell leaves when it pipes UTF-16 text to a program that reads bytes."""
    utf16 = key.replace("\n", "\r\n").encode("utf-16-le").decode("latin-1")
    assert _public(tmp_path, normalise_key(utf16)) == _public(tmp_path, key)


@pytest.mark.parametrize("text", ["", "   ", "not a key", "-----BEGIN OPENSSH PRIVATE KEY-----", "ssh-ed25519 AAAAC3Nza public-key-only"])
def test_something_that_is_not_a_private_key_is_refused_with_a_hint(text):
    with pytest.raises(ValueError, match="BEGIN header"):
        normalise_key(text)


def test_the_error_describes_the_secret_without_printing_it():
    secret = "AAAAB3NzaC1lZDI1NTE5AAAAIPRIVATEPRIVATE"
    with pytest.raises(ValueError) as error:
        normalise_key(secret)
    assert secret not in str(error.value) and str(len(secret)) in str(error.value)


def test_the_command_line_writes_the_key_with_unix_newlines_on_every_platform(key, tmp_path):
    """The workflow pipes through ``python -m src.local_data.ssh_key``; a text-mode stdout would turn the newlines into CRLF on Windows."""
    mangled = key.replace("\n", "\r\n").replace("\r\n", " ")
    done = subprocess.run([sys.executable, "-m", "src.local_data.ssh_key"], input=mangled.encode("utf-8"), capture_output=True, check=True)
    assert b"\r" not in done.stdout and _public(tmp_path, done.stdout.decode("ascii")) == _public(tmp_path, key)
