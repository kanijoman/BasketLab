"""Invitation generator (issue #410): ``python -m src.live_prep.invite --scope club:1008631`` for the people who keep access when the key is on."""
import pytest

from src.live_prep.invite import main
from src.live_prep.package_scopes import parse_invite, scope_key

MASTER = "clave-maestra-de-prueba"


def test_it_prints_a_token_and_a_link_for_every_scope(capsys, monkeypatch):
    monkeypatch.setenv("PACKAGE_MASTER_KEY", MASTER)
    assert main(["--scope", "club:1", "--scope", "temporada:2026-27", "--expires", "2027-06-30"]) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if "basketlab-live://" in line]
    assert len(lines) == 2
    parsed = [parse_invite(line.split()[-1]) for line in lines]
    assert [p["scope"] for p in parsed] == ["club:1", "temporada:2026-27"]
    assert parsed[0]["key"] == scope_key(MASTER, "club:1") and parsed[0]["expires"] == "2027-06-30"


def test_the_existing_password_is_the_master_when_there_is_no_master_key(capsys, monkeypatch):
    monkeypatch.delenv("PACKAGE_MASTER_KEY", raising=False)
    monkeypatch.setenv("PACKAGE_PASSWORD", MASTER)
    assert main(["--scope", "club:1"]) == 0
    assert parse_invite(capsys.readouterr().out.split()[-1])["key"] == scope_key(MASTER, "club:1")


def test_without_a_long_enough_secret_or_a_scope_it_fails(monkeypatch):
    monkeypatch.delenv("PACKAGE_MASTER_KEY", raising=False)
    monkeypatch.setenv("PACKAGE_PASSWORD", "corta")
    assert main(["--scope", "club:1"]) == 2
    monkeypatch.setenv("PACKAGE_MASTER_KEY", MASTER)
    with pytest.raises(SystemExit):
        main([])
