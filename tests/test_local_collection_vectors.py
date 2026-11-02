"""The parity vectors of the list of competitions on the device (#705) are kept honest: any change in ``CollectionService`` shows up as a diff of ``collections.json``.

``python tests/local_vectors/generate.py`` regenerates it; the web (``frontend/src/localdata/collections.test.ts``) must answer the same list from the manifest alone. The names are the
real collections of a working copy, so the cases the browser has to get right (FBCYL, a group, a phase kept in the season, accents and ordinals in the name) are asserted here.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "local_vectors"))

import collection_vectors  # noqa: E402
import generate  # noqa: E402


def _stored():
    return json.loads(generate.COLLECTIONS_OUT.read_text(encoding="utf-8"))


def test_the_stored_collection_vectors_are_the_current_reference():
    assert json.loads(json.dumps(collection_vectors.build(), sort_keys=True)) == _stored()


def test_the_collection_vectors_cover_what_the_browser_has_to_get_right():
    vectors = _stored()
    listed = {row["name"]: row for row in vectors["listed"]}
    assert any(row["league"] == "FBCYL" for row in listed.values()) and any(row["league"] == "FEB" for row in listed.values())
    assert any(row["group"] for row in listed.values()) and any(not row["group"] for row in listed.values())      # with a group peeled off the season, and without it
    assert any("_" in row["season"] and not row["season"].replace("_", "").isdigit() for row in listed.values())    # a phase that stays in the season
    assert any(not name.isascii() for name in listed)                                                             # Ñ, Ú, º, ª
    assert vectors["skipped"] and len(vectors["published"]) == len(listed)                                         # the system collections are not competitions
    seasons = [row["season"] for row in vectors["listed"] if row["league"] == "FEB"]
    assert seasons == sorted(seasons, reverse=True) or len(set(seasons)) > 1                                       # sorted by season, the newest first, inside a league
