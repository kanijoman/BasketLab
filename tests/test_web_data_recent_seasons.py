"""``web-data`` publishes only the current season and the previous one (#991, decided 19/11/2026): the older ones stay in the private archive and in ``talent-data``.

209 MB with two historical batches loaded; the season is the leading years of the collection name and each league writes it differently (FEB ``2026_2027``, FBCYL's ``2026``), so each has its own
two newest. A collection that does not say its season is kept, never guessed to be old."""
import json
import sys
from pathlib import Path

import mongomock
import pymongo
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fbcyl_games  # noqa: E402
import games  # noqa: E402
from src.local_data.images_export import recent_season_collections  # noqa: E402

FEB = ["PRIMERA_FEB_2023_2024_Liga_Regular_Unico", "PRIMERA_FEB_2024_2025_Liga_Regular_Unico", "PRIMERA_FEB_2025_2026_Liga_Regular_Unico", "PRIMERA_FEB_2026_2027_Liga_Regular_Unico",
       "COPA_ESPANA_2024_2025_Play-offs_Final", "COPA_ESPANA_2026_2027_FASE_DE_GRUPOS_A"]
FBCYL = ["FBCYL_1ª_FASE-GRUPO_A-1_2024_", "FBCYL_1ª_FASE-GRUPO_A-1_2025_", "FBCYL_1ª_FASE-GRUPO_A-1_2026_"]


def test_the_two_newest_seasons_of_each_league_are_kept_and_the_older_ones_are_left_out():
    kept = recent_season_collections(FEB + FBCYL, 2)
    assert kept == {"PRIMERA_FEB_2025_2026_Liga_Regular_Unico", "PRIMERA_FEB_2026_2027_Liga_Regular_Unico", "COPA_ESPANA_2026_2027_FASE_DE_GRUPOS_A",
                    "FBCYL_1ª_FASE-GRUPO_A-1_2025_", "FBCYL_1ª_FASE-GRUPO_A-1_2026_"}


def test_a_competition_that_stopped_before_the_previous_season_is_not_kept_by_its_own_newest_season():
    """The Copa of 2024/25 is two seasons old: «the previous season» is the league's, not each competition's own newest."""
    assert "COPA_ESPANA_2024_2025_Play-offs_Final" not in recent_season_collections(FEB, 2)


def test_each_league_counts_its_own_seasons_so_the_year_of_fbcyl_does_not_push_feb_out():
    assert recent_season_collections(["PRIMERA_FEB_2025_2026_X", "FBCYL_X_2026_"], 2) == {"PRIMERA_FEB_2025_2026_X", "FBCYL_X_2026_"}


def test_with_a_single_season_in_the_archive_it_is_kept_and_an_empty_archive_is_empty():
    assert recent_season_collections(["FBCYL_X_2025_"], 2) == {"FBCYL_X_2025_"} and recent_season_collections([], 2) == set()


def test_a_collection_that_says_no_season_is_kept_not_guessed_to_be_old():
    assert "SIN_TEMPORADA" in recent_season_collections(FEB + ["SIN_TEMPORADA"], 2)


def test_the_answer_does_not_depend_on_the_order_of_the_names():
    import random

    names = FEB + FBCYL
    expected = recent_season_collections(names, 2)
    for _ in range(5):
        random.shuffle(names)
        assert recent_season_collections(names, 2) == expected


def test_one_season_is_what_the_images_and_the_calendar_already_use():
    from src.local_data.images_export import current_season_collections

    assert recent_season_collections(FEB + FBCYL, 1) == current_season_collections(FEB + FBCYL)


@pytest.fixture()
def handler(monkeypatch):
    from src.api import deps

    monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    deps._create_handler.cache_clear()
    handler = deps._create_handler()
    db = handler.connection.client["BASKETBALL"]
    for name in ("L_F_-2_2023_2024_Liga_Regular_B", "L_F_-2_2024_2025_Liga_Regular_B", "L_F_-2_2025_2026_Liga_Regular_B"):
        db[name].insert_many(games.build_games())
    for name in ("FBCYL_1ª_FASE-GRUPO_A-1_2024_", "FBCYL_1ª_FASE-GRUPO_A-1_2026_"):
        db[name].insert_many(fbcyl_games.build_games())
    yield handler
    deps._create_handler.cache_clear()


def test_the_entry_point_publishes_the_two_newest_seasons_and_an_explicit_collection_is_published_as_asked(handler, tmp_path, monkeypatch):
    import run_web_data

    monkeypatch.setenv("PACKAGE_MASTER_KEY", "a-master-secret-for-the-tests")
    flags = ["--no-images", "--no-calendar", "--no-scouting"]
    assert run_web_data.main(["--out", str(tmp_path / "all"), *flags]) == 0
    published = sorted(r["collection"] for r in json.loads((tmp_path / "all" / "index.json").read_text(encoding="utf-8"))["rows"])
    assert published == ["FBCYL_1ª_FASE-GRUPO_A-1_2024_", "FBCYL_1ª_FASE-GRUPO_A-1_2026_", "L_F_-2_2024_2025_Liga_Regular_B", "L_F_-2_2025_2026_Liga_Regular_B"]
    assert run_web_data.main(["--out", str(tmp_path / "one"), "--collection", "L_F_-2_2023_2024_Liga_Regular_B", *flags]) == 0
    assert [r["collection"] for r in json.loads((tmp_path / "one" / "index.json").read_text(encoding="utf-8"))["rows"]] == ["L_F_-2_2023_2024_Liga_Regular_B"]


def test_a_season_change_drops_the_season_of_two_years_ago_from_the_published_branch_and_its_files(handler, tmp_path, monkeypatch):
    """The purge of the branch is the publication itself (#991): the folder mirrors the chosen collections, so when a new season arrives the one of two years ago disappears (manifest and files)
    and the branch does not grow for ever. The archive and ``talent-data`` keep it."""
    import run_web_data

    monkeypatch.setenv("PACKAGE_MASTER_KEY", "a-master-secret-for-the-tests")
    flags = ["--no-images", "--no-calendar", "--no-scouting"]
    out = tmp_path / "branch"

    def listed():
        return sorted(r["collection"] for r in json.loads((out / "index.json").read_text(encoding="utf-8"))["rows"] if r["collection"].startswith("L_F_-2_"))

    def files_of(season):
        return sorted(str(p.relative_to(out)) for p in out.rglob("*.json") if season in p.name)

    assert run_web_data.main(["--out", str(out), *flags]) == 0
    assert listed() == ["L_F_-2_2024_2025_Liga_Regular_B", "L_F_-2_2025_2026_Liga_Regular_B"]
    handler.connection.client["BASKETBALL"]["L_F_-2_2026_2027_Liga_Regular_B"].insert_many(games.build_games())                   # the new season starts
    assert run_web_data.main(["--out", str(out), *flags]) == 0
    assert listed() == ["L_F_-2_2025_2026_Liga_Regular_B", "L_F_-2_2026_2027_Liga_Regular_B"]
    manifest = json.loads((out / "index.json").read_text(encoding="utf-8"))

    from src.local_data.web_data import _referenced              # what the sweep itself keeps: the manifest, its files and those listed by each report index

    referenced = _referenced(out, manifest)
    on_disk = {str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*.json") if p.parent != out and p.name not in ("vercel.json", "index.json")}
    assert on_disk == referenced - {"index.json", "frontend/vercel.json"} and on_disk                              # nothing of the season that left stays in the branch, orphan, after the change
    assert "2024_2025" not in json.dumps(manifest)
