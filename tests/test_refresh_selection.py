"""Partial refreshes that can be chosen by season and league, and a refresh that does not follow redirects it can avoid (#924).

``--only`` chose competitions by name; the FBCYL groups are named by the text of each group and a season cannot be chosen at all. Now ``--season`` and ``--league`` too, and ``--force-check``
checks the closed collections anyway. The workflow passes all of it from inputs. FEB's own links say ``http://`` and answer 301 to ``https://``: the client goes to ``https`` directly.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.scraper.web_client import WebClient  # noqa: E402
from src.services import competition_refresh as cr  # noqa: E402
from src.services.competition_refresh import RefreshEntry, select_entries  # noqa: E402


def _feb(name, season, **over):
    return RefreshEntry(competition_url=f"https://x/{name}", season_value=season, competition_label=name, season_label=f"{season}/{int(season) + 1}", group_value="1", group_label="A", year=season, **over)


def _fbcyl(group, season):
    return RefreshEntry(competition_url="", season_value=season, competition_label=group, season_label=season, league="fbcyl", fbcyl={"competition_id": "7242", "category": "1130"})


ENTRIES = [_feb("LF ENDESA", "2026"), _feb("PRIMERA FEB", "2026"), _feb("LF ENDESA", "2025"), _feb("TERCERA FEB", "2025"), _feb("TERCERA FEB", "2024"), _fbcyl("LIGA UEMC G7242", "2026"), _fbcyl("LIGA UEMC G7244", "2025")]


def _names(entries):
    return [(e.competition_label, e.season_value) for e in entries]


class TestSelectEntries:
    def test_no_filter_keeps_every_entry_in_order(self):
        assert select_entries(ENTRIES, [], [], None) == ENTRIES

    def test_a_season_keeps_the_entries_of_that_season_of_every_league(self):
        assert _names(select_entries(ENTRIES, [], ["2025"], None)) == [("LF ENDESA", "2025"), ("TERCERA FEB", "2025"), ("LIGA UEMC G7244", "2025")]

    def test_several_seasons_add_up(self):
        assert len(select_entries(ENTRIES, [], ["2024", "2025"], None)) == 4

    def test_a_league_keeps_only_its_entries_and_fbcyl_becomes_choosable(self):
        assert _names(select_entries(ENTRIES, [], [], "fbcyl")) == [("LIGA UEMC G7242", "2026"), ("LIGA UEMC G7244", "2025")]
        assert all(e.league == "feb" for e in select_entries(ENTRIES, [], [], "feb"))

    def test_the_filters_combine_with_the_competition_names(self):
        assert _names(select_entries(ENTRIES, ["tercera feb"], ["2025"], "feb")) == [("TERCERA FEB", "2025")]
        assert _names(select_entries(ENTRIES, ["lf endesa"], [], None)) == [("LF ENDESA", "2026"), ("LF ENDESA", "2025")]

    def test_a_season_with_no_entry_is_an_error_not_an_empty_refresh_and_it_names_the_ones_that_have_none(self):
        with pytest.raises(ValueError, match="1999"):
            select_entries(ENTRIES, [], ["1999"], None)
        with pytest.raises(ValueError) as error:
            select_entries(ENTRIES, [], ["2025", "2024", "1999"], "fbcyl")           # 2024 exists, but not in FBCYL
        assert "2024" in str(error.value) and "1999" in str(error.value) and "2025" not in str(error.value)
        with pytest.raises(ValueError, match="2025"):
            select_entries(ENTRIES, ["primera feb"], ["2025"], None)               # the competition exists, not in that season

    def test_filters_that_leave_nothing_are_an_error(self):
        with pytest.raises(ValueError, match="nothing"):
            select_entries([_fbcyl("LIGA UEMC G7242", "2026")], [], [], "feb")

    def test_an_unknown_league_or_competition_is_an_error(self):
        with pytest.raises(ValueError, match="league"):
            select_entries(ENTRIES, [], [], "acb")
        with pytest.raises(ValueError, match="unknown competition"):
            select_entries(ENTRIES, ["nope"], [], None)

    def test_it_does_not_change_the_entries_it_gets(self):
        before = list(ENTRIES)
        select_entries(ENTRIES, [], ["2025"], "feb")
        assert ENTRIES == before


class TestCli:
    def _main(self, monkeypatch, argv, entries=None):
        calls = {}
        monkeypatch.setattr(cr, "load_config", lambda path: list(entries if entries is not None else ENTRIES))

        class _Db:
            def is_connected(self):
                return True

        monkeypatch.setattr("src.database.MongoDBHandler", _Db)

        def fake(db, chosen, **kw):
            calls.update(entries=chosen, **kw)
            return []

        monkeypatch.setattr(cr, "refresh_all", fake)
        return cr.main(argv), calls

    def test_season_league_and_force_check_reach_the_refresh(self, monkeypatch):
        code, calls = self._main(monkeypatch, ["--season", "2025", "--league", "feb", "--force-check"])
        assert code == 0 and _names(calls["entries"]) == [("LF ENDESA", "2025"), ("TERCERA FEB", "2025")] and calls["force"] is True

    def test_seasons_may_be_comma_separated_like_the_competitions_and_force_is_off_by_default(self, monkeypatch):
        code, calls = self._main(monkeypatch, ["--season", "2024,2025", "--only", "tercera feb"])
        assert code == 0 and _names(calls["entries"]) == [("TERCERA FEB", "2025"), ("TERCERA FEB", "2024")] and calls["force"] is False

    def test_a_season_that_does_not_exist_ends_with_a_message_and_a_failure(self, monkeypatch, capsys):
        code, _ = self._main(monkeypatch, ["--season", "1999"])
        assert code == 2 and "1999" in capsys.readouterr().err


def test_the_workflow_passes_season_league_and_force_from_its_inputs_without_putting_them_in_the_command():
    import yaml

    wf = yaml.safe_load(Path(".github/workflows/archive-refresh.yml").read_text(encoding="utf-8"))
    inputs = wf[True]["workflow_dispatch"]["inputs"]
    assert {"only", "season", "league", "force"} <= set(inputs) and inputs["force"]["type"] == "boolean"
    run = [s for s in next(iter(wf["jobs"].values()))["steps"] if "run_refresh.py" in s.get("run", "")][0]
    assert {"ONLY", "SEASON", "LEAGUE", "FORCE"} <= set(run["env"]) and "${{" not in run["run"]
    for flag in ('${SEASON:+--season "$SEASON"}', '${LEAGUE:+--league "$LEAGUE"}', "${FORCE:+--force-check}"):
        assert flag in run["run"]
    assert "'true'" in run["env"]["FORCE"]                                          # a boolean input says "false" too: only "true" turns it on


class TestHttpsUpgrade:
    """FEB's pages link to ``http://baloncestoenvivo.feb.es/series/<id>`` and the server answers 301 to ``https``: 26 of 87 requests of a collection were that hop."""

    def _client(self):
        client = WebClient()
        client.session = MagicMock()
        client.session.get.return_value.status_code = 200
        client.session.post.return_value.status_code = 200
        return client

    @pytest.mark.parametrize("url", ["http://baloncestoenvivo.feb.es/series/43119", "http://www.fbcyl.es/buscar_competicion", "HTTP://baloncestoenvivo.feb.es/calendario/x/1/2024"])
    def test_known_hosts_are_asked_over_https_straight_away(self, url):
        client = self._client()
        client.get(url)
        asked = client.session.get.call_args.args[0]
        assert asked.lower().startswith("https://") and asked.split("://", 1)[1] == url.split("://", 1)[1]

    def test_post_too_and_https_urls_are_left_alone(self):
        client = self._client()
        client.post("http://baloncestoenvivo.feb.es/resultados.aspx", data={"a": 1})
        assert client.session.post.call_args.args[0] == "https://baloncestoenvivo.feb.es/resultados.aspx"
        client.get("https://baloncestoenvivo.feb.es/ya/seguro")
        assert client.session.get.call_args.args[0] == "https://baloncestoenvivo.feb.es/ya/seguro"

    @pytest.mark.parametrize("url, final", [
        ("https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2024&nm=segundafeb", "https://baloncestoenvivo.feb.es/calendario/segundafeb/2/2024"),
        ("https://baloncestoenvivo.feb.es/resultados.aspx?g=1&t=2025&nm=lf2", "https://baloncestoenvivo.feb.es/resultados/lf2/1/2025"),
        ("http://baloncestoenvivo.feb.es/calendario.aspx?nm=lfendesa&g=4&t=2026", "https://baloncestoenvivo.feb.es/calendario/lfendesa/4/2026"),        # any order of the parameters
        ("https://baloncestoenvivo.feb.es/Series.aspx?f=43119", "https://baloncestoenvivo.feb.es/series/43119"),
        ("https://baloncestoenvivo.feb.es/series.aspx?f=7", "https://baloncestoenvivo.feb.es/series/7"),
    ])
    def test_the_pages_feb_redirects_to_its_canonical_address_through_http_are_asked_at_that_address(self, url, final):
        """FEB answers 301 to http://.../calendario/<nm>/<g>/<t> and that one 301 to https: three requests for one page (measured, 13/11/2026)."""
        client = self._client()
        client.get(url)
        assert client.session.get.call_args.args[0] == final

    @pytest.mark.parametrize("url", [
        "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2024",                                  # a parameter missing: left as it is
        "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2024&nm=segundafeb&extra=1",           # one more: left as it is
        "https://baloncestoenvivo.feb.es/calendario.aspx?g=dos&t=2024&nm=segundafeb", "https://baloncestoenvivo.feb.es/calendario.aspx?g=2&t=2024&nm=../etc",
        "https://baloncestoenvivo.feb.es/Series.aspx?f=abc", "https://baloncestoenvivo.feb.es/Series.aspx", "https://baloncestoenvivo.feb.es/otra.aspx?g=2&t=2024&nm=x",
        "https://otro.example/calendario.aspx?g=2&t=2024&nm=segundafeb",
    ])
    def test_anything_that_is_not_exactly_one_of_those_pages_keeps_its_address(self, url):
        client = self._client()
        client.get(url)
        assert client.session.get.call_args.args[0] == url

    def test_a_post_to_the_aspx_keeps_its_address_the_form_posts_there(self):
        client = self._client()
        client.post("https://baloncestoenvivo.feb.es/resultados.aspx", data={"a": 1})
        assert client.session.post.call_args.args[0] == "https://baloncestoenvivo.feb.es/resultados.aspx"

    @pytest.mark.parametrize("url", ["http://localhost:8765/feb", "http://127.0.0.1:9/x", "http://otra.example.org/x", "http://baloncestoenvivo.feb.es.evil.example/x"])
    def test_other_hosts_are_never_rewritten_a_local_fake_server_keeps_working(self, url):
        client = self._client()
        client.get(url)
        assert client.session.get.call_args.args[0] == url
