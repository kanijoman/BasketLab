"""Download a competition's games to a local folder of ``*.json.gz`` (issue #301), the input of the evaluators."""

import gzip
import json

from src.live_prep.download_games import download_season, main
from src.live_prep.eval_source import games_from_dir

URL = "https://example.test/calendario.aspx?g=67&t=2026&nm=lfchallenge"


def doc(code, pbp=True, start="10-10-2025 - 17:00"):
    return {"HEADER": {"starttime": start, "game_code": code, "TEAM": []},
            "PLAYBYPLAY": {"LINES": [{"num": 1}] if pbp else []}}


class FakeScraper:
    """What ``download_season`` needs from ``FEBWebScraper``: groups, match codes and the full document of a match."""

    def __init__(self, groups, matches, docs):
        self.groups, self.matches, self.docs = groups, matches, docs
        self.fetched = []

    def get_groups_for_season(self, url, season):
        return self.groups

    def get_page_content(self, year):
        return None, "session"

    def get_matches(self, season, group, year, session, url=None):
        return self.matches[group]

    def fetch_boxscore(self, code, session):
        self.fetched.append(code)
        value = self.docs[code]
        if isinstance(value, Exception):
            raise value
        return value


def scraper():
    return FakeScraper(
        [("Liga Regular Único", "1"), ("PLAY-OFF Final", "2")],
        {"1": ["100", "101", "102", "103"], "2": ["200"]},
        {"100": doc("100"), "101": doc("101", pbp=False), "102": None, "103": RuntimeError("boom"), "200": doc("200")})


def files(folder):
    return sorted(p.name for p in folder.iterdir())


def test_writes_one_gzipped_file_per_game_with_play_by_play(tmp_path):
    result = download_season(scraper(), URL, "2025", tmp_path)
    assert files(tmp_path) == ["100.json.gz", "200.json.gz"]
    assert json.loads(gzip.decompress((tmp_path / "100.json.gz").read_bytes()))["_id"] == "100"
    assert (result["saved"], result["no_pbp"], result["missing"], result["errors"]) == (2, 1, 1, 1)


def test_the_folder_is_what_the_evaluators_read(tmp_path):
    download_season(scraper(), URL, "2025", tmp_path)
    assert [g["_id"] for g in games_from_dir(tmp_path)] == ["100", "200"]


def test_a_second_run_does_not_download_again_what_it_has(tmp_path):
    download_season(scraper(), URL, "2025", tmp_path)
    again = scraper()
    result = download_season(again, URL, "2025", tmp_path)
    assert "100" not in again.fetched and "200" not in again.fetched
    assert result["skipped"] == 2 and result["saved"] == 0


def test_only_the_groups_asked_for(tmp_path):
    s = scraper()
    result = download_season(s, URL, "2025", tmp_path, groups=["regular"])
    assert files(tmp_path) == ["100.json.gz"] and "200" not in s.fetched
    assert result["groups"] == ["Liga Regular Único"]


def test_a_season_without_groups_is_reported_not_a_crash(tmp_path):
    result = download_season(FakeScraper([], {}, {}), URL, "2019", tmp_path)
    assert result["saved"] == 0 and result["groups"] == []


def test_cli_takes_several_seasons_into_one_folder_each(tmp_path, monkeypatch):
    import src.live_prep.download_games as module

    monkeypatch.setattr(module, "_scraper", lambda: scraper())
    assert main(["--url", URL, "--season", "2025", "--season", "2024", "--out", str(tmp_path), "--delay", "0"]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2024", "2025"]
    assert files(tmp_path / "2025") == ["100.json.gz", "200.json.gz"]
