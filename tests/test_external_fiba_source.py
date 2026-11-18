"""The FIBA source (#887, D3b): what the daily refresh registers for ``fiba``.

It asks the event of each entry for its games, takes the FINISHED ones it does not have yet (a played game never changes, so ``known`` ids are not asked again), reads each page with the polite client and hands
over the canonical document. A game it cannot get is skipped and said (``notes``), never a reason to stop the rest; a site that changed its format (every game fails to read) is a failed run. The site is the fake of
``tests/fiba_helpers`` serving the REAL pages of ``tests/fixtures/fiba``: the event page of the U18 EuroBasket 2025 (56 games) and the real pages of three of its games; every other page is a 404.
"""
import json
import urllib.error
from datetime import datetime, timezone

import pytest

import market_helpers  # noqa: F401  (it puts tests/local_vectors on the path)

from db_helpers import new_mock_db
from fiba_helpers import Clock, Site, flight, html_of
from mongomock_handler import mongomock_handler

from src.external import registry
from src.external.fiba_client import FibaClient, FibaFetchError
from src.external.fiba_page import FibaPageError
from src.external.fiba_source import FibaSource
from src.external.publish import publish_external
from src.external.refresh import refresh_source
from src.live_prep.package_sealing import ScopedSealer
from src.market.canonical import validate_game
from src.services.competition_catalogue import load_catalogue

NOW = datetime(2026, 11, 18, 7, 0, tzinfo=timezone.utc)
EVENT = "fiba-u18-eurobasket-2025"
REAL_GAMES = {"125809": "125809-FRA-AUT", "125803": "125803-ITA-GER", "125812": "125812-SWE-FRA"}          # the three games of the event whose real page is in the fixtures
NOT_FOUND = urllib.error.HTTPError("u", 404, "Not Found", {}, None)


def entry(tmp_path, event=EVENT, gender="M", cap=None, competition="U18 EuroBasket", **over):
    raw = {"competition": competition, "season_label": "2025", "season_value": "2025", "league": "fiba", "division": "U18", "gender": gender, "category": "formacion", "age_group": "U18",
           "label": "FIBA U18 EuroBasket", "fiba": {"event": event, **({"max_games": cap} if cap else {})}, **over}
    path = tmp_path / f"competitions-{len(list(tmp_path.glob('competitions-*.json')))}.json"
    path.write_text(json.dumps({"competitions": [raw]}), encoding="utf-8")
    return load_catalogue(path)


def site(event=EVENT, listing=None, games=None):
    pages = {f"/en/events/{event}": html_of(flight(listing or "fiba-u18-eurobasket-2025"))}
    pages.update({f"/games/{slug}": html_of(flight(name)) for name, slug in (games if games is not None else REAL_GAMES).items()})
    return Site(pages, default=NOT_FOUND)


def source(fake, budget=300):
    clock = Clock()
    return FibaSource(FibaClient(fetch=fake.fetch, sleep=clock.sleep, clock=clock.time), budget=budget)


def game_requests(fake):
    return [url.rsplit("/", 1)[1] for url, _ in fake.requests if "/games/" in url]


@pytest.fixture(autouse=True)
def clean_registry():
    saved = dict(registry.SOURCES)
    registry.SOURCES.clear()
    yield
    registry.SOURCES.clear()
    registry.SOURCES.update(saved)


class TestWhatItAsksFor:
    def test_it_hands_over_the_canonical_document_of_every_game_it_could_get_and_says_what_it_could_not(self, tmp_path):
        fake, [cat] = site(), entry(tmp_path)
        src = source(fake)
        docs = list(src.fetch(cat, None, frozenset()))
        assert sorted(d["_id"] for d in docs) == ["fiba:125803", "fiba:125809", "fiba:125812"]
        assert all(d["_league"] == "fiba" and validate_game(d, "M") == [] for d in docs)
        assert len(src.notes) == 53 and all("not found" in n.lower() for n in src.notes)

    def test_it_asks_the_games_in_the_order_they_are_played_and_each_once(self, tmp_path):
        fake, [cat] = site(), entry(tmp_path)
        list(source(fake).fetch(cat, None, frozenset()))
        asked = game_requests(fake)
        assert asked == [g["slug"] for g in __import__("src.external.fiba_page", fromlist=["parse_event_games"]).parse_event_games(flight("fiba-u18-eurobasket-2025"))] and len(set(asked)) == 56

    def test_it_does_not_ask_again_for_a_game_it_already_has(self, tmp_path):
        fake, [cat] = site(), entry(tmp_path)
        list(source(fake).fetch(cat, None, frozenset({"fiba:125809", "fiba:125803"})))
        asked = game_requests(fake)
        assert "125809-FRA-AUT" not in asked and "125803-ITA-GER" not in asked and "125812-SWE-FRA" in asked and len(asked) == 54

    def test_it_does_not_ask_for_a_game_that_is_still_to_play(self, tmp_path):
        qualifiers = "fiba-basketball-world-cup-2027-european-qualifiers"
        fake = site(event=qualifiers, listing=qualifiers, games={})
        [cat] = entry(tmp_path, event=qualifiers)
        list(source(fake).fetch(cat, None, frozenset()))
        assert len(game_requests(fake)) == 120                                       # 168 games listed, 48 of them to play

    def test_the_budget_of_a_run_is_shared_by_every_entry_and_counts_the_games_it_asked_for(self, tmp_path):
        fake, [cat] = site(), entry(tmp_path)
        src = source(fake, budget=10)
        list(src.fetch(cat, None, frozenset()))
        list(src.fetch(cat, None, frozenset({"fiba:125809"})))                      # a second entry in the same run finds the budget spent
        assert len(game_requests(fake)) == 10 and src.remaining == 0

    def test_an_entry_can_cap_its_own_games(self, tmp_path):
        fake, [cat] = site(), entry(tmp_path, cap=5)
        list(source(fake).fetch(cat, None, frozenset()))
        assert len(game_requests(fake)) == 5

    def test_the_games_of_a_woman_event_are_not_published_as_men_s(self, tmp_path):
        fake, [cat] = site(), entry(tmp_path, gender="F")
        src = source(fake)
        assert list(src.fetch(cat, None, frozenset())) == []
        assert sum("gender" in n.lower() for n in src.notes) == 3

    def test_it_says_nothing_to_hand_over_when_the_event_has_no_games_to_ask_for(self, tmp_path):
        fake, [cat] = site(), entry(tmp_path)
        src = source(fake)
        assert list(src.fetch(cat, None, frozenset(f"fiba:{g}" for g in range(125800, 125900)))) == [] and game_requests(fake) == []


class TestWhenSomethingGoesWrong:
    def test_an_event_that_cannot_be_listed_fails_the_run(self, tmp_path):
        fake = Site({f"/en/events/{EVENT}": urllib.error.HTTPError("u", 503, "Unavailable", {}, None)})
        [cat] = entry(tmp_path)
        with pytest.raises(FibaFetchError):
            list(source(fake).fetch(cat, None, frozenset()))

    def test_a_game_that_fails_is_skipped_and_said_and_the_others_still_come(self, tmp_path):
        text = flight("125812").replace('"gameDetails":{"c":', '"gameDetails":{"d":', 1)
        fake = site()
        fake.pages["/games/125812-SWE-FRA"] = [html_of(text)]
        [cat] = entry(tmp_path)
        src = source(fake)
        assert sorted(d["_id"] for d in src.fetch(cat, None, frozenset())) == ["fiba:125803", "fiba:125809"]
        assert any("125812-SWE-FRA" in n for n in src.notes)

    def test_a_site_that_changed_its_format_is_a_failed_run_not_an_empty_one(self, tmp_path):
        broken = {k: html_of(flight(k).replace('"gameDetails":{"c":', '"gameDetails":{"d":', 1)) for k in REAL_GAMES}
        fake = site(games={})
        fake.pages.update({f"/games/{slug}": [broken[name]] for name, slug in REAL_GAMES.items()})
        [cat] = entry(tmp_path, cap=3)
        with pytest.raises(FibaPageError):
            list(source(fake).fetch(cat, None, frozenset()))


def test_the_whole_chain_from_the_site_to_the_published_rows(tmp_path):
    """The daily refresh of the fiba source against the fake site, then the publication of web-data-ext: three real games, all reliable, under their own league."""
    fake, cat = site(), entry(tmp_path)
    registry.register(source(fake))
    db = new_mock_db("BASKETBALL")
    status = refresh_source("fiba", cat, db, tmp_path / "archive-ext", NOW)
    assert status["ok"] is True and status["games"] == 3 and status["unreliable"] == 0 and status["rejected"] == []
    assert status["notes_total"] == 53 and len(status["notes"]) == 20
    manifest = publish_external(tmp_path / "archive-ext", tmp_path / "web-ext", cat, mongomock_handler(), ScopedSealer("fiba-chain-secret", open_access=True))
    [row] = manifest["rows"]
    assert (row["collection"], row["league"], row["gender"], row["games"], row["category"], row["age_group"]) == ("FIBA_U18_EuroBasket_2025_", "fiba", "M", 3, "formacion", "U18")
    assert manifest["sources"][0]["published"] == 3 and manifest["sources"][0]["unreliable"] == 0
    before = len(fake.requests)
    again = refresh_source("fiba", cat, db, tmp_path / "archive-ext", NOW)
    assert again["new"] == 0 and again["games"] == 3
    asked = [url.rsplit("/", 1)[1] for url, _ in fake.requests[before:] if "/games/" in url]
    assert not set(asked) & set(REAL_GAMES.values()) and len(asked) == 53                  # the three it has are not asked again; the 53 that were not found are, as they may appear


class TestTheRealSourceOfTheRefresh:
    """``run_external_refresh.py --source fiba`` registers the real source with a real client; the tests give it the fake site."""

    def test_the_default_sources_are_the_ones_that_exist_and_the_others_have_none(self):
        from src.external import sources

        assert isinstance(sources.default_source("fiba", budget=7), FibaSource) and sources.default_source("fiba", budget=7).remaining == 7
        assert sources.default_source("fiba").remaining == 300
        assert sources.default_source("ncaa") is None and sources.default_source("acb") is None

    def test_it_registers_the_source_once_and_never_over_one_that_is_already_there(self):
        from src.external import sources

        sources.register_defaults("fiba")
        first = registry.SOURCES["fiba"]
        sources.register_defaults("fiba")
        assert registry.SOURCES["fiba"] is first
        registry.SOURCES.clear()
        mine = registry.register(FibaSource(FibaClient(fetch=lambda url, agent: ""), budget=1))
        sources.register_defaults("fiba")
        assert registry.SOURCES["fiba"] is mine

    def test_the_entry_point_runs_it_with_the_budget_it_is_given(self, tmp_path, monkeypatch):
        import sys
        from pathlib import Path

        from src.external import sources

        fake = site()
        clock = Clock()
        monkeypatch.setattr(sources, "make_client", lambda: FibaClient(fetch=fake.fetch, sleep=clock.sleep, clock=clock.time))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_external_refresh

        raw = entry(tmp_path)[0]
        catalogue = tmp_path / "competitions.json"
        catalogue.write_text(json.dumps({"competitions": [{k: v for k, v in raw.items() if k not in ("source", "groups", "conference", "packages", "record", "packages_groups", "recheck_days", "active")}]}), encoding="utf-8")
        db = new_mock_db("BASKETBALL")
        assert run_external_refresh.main(["--source", "fiba", "--catalogue", str(catalogue), "--out", str(tmp_path / "out"), "--budget", "2"], db=db, now=NOW) == 0
        assert len(game_requests(fake)) == 2
        assert json.loads((tmp_path / "out" / "fiba" / "status.json").read_text(encoding="utf-8"))["ok"] is True

    def test_a_budget_that_is_not_a_positive_whole_number_is_refused(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import run_external_refresh

        for bad in ("0", "-5", "ten"):
            with pytest.raises(SystemExit):
                run_external_refresh.main(["--source", "fiba", "--budget", bad])
