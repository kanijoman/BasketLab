"""Assist → basket → zone links of one game (issue #773), FEB and FBCYL.

An assist is a line of its own that follows the basket it created, with the same clock (FEB) / the same team and clock (FBCYL). The link is read from the
play-by-play; a miss never has an assist, so only made field goals are linked and no accuracy is computed.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.services.assist_links import extract_links

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------------------------------------------- FEB
def _line(num, action, team, player, time="08:35", quarter="3", text=None, deleted=None):
    made = " ANOTADO" if action == "shoot" and text is None else ""
    return {"num": str(num), "action": action, "team": team, "idPlayer": player, "time": time, "quarter": quarter, "deleted": deleted,
            "text": text if text is not None else f"({team}) X: {action.upper()}{made}"}


def feb_doc(lines, shots=()):
    """A game with team slot 0 = id 10 (dorsals 4 → p1, 5 → p2) and slot 1 = id 20; lines in the descending order they are stored in."""
    return {
        "HEADER": {"TEAM": [{"id": "10"}, {"id": "20"}]},
        "BOXSCORE": {"TEAM": [{"PLAYER": [{"id": "p1", "name": "ANA"}, {"id": "p2", "name": "BEA"}]}, {"PLAYER": [{"id": "q1", "name": "EVA"}]}]},
        "SHOTCHART": {"TEAM": [{"PLAYER": [{"id": "p1", "no": "4"}, {"id": "p2", "no": "5"}]}, {"PLAYER": [{"id": "q1", "no": "9"}]}], "SHOTS": list(shots)},
        "PLAYBYPLAY": {"LINES": sorted(lines, key=lambda l: -int(l["num"]))},
    }


def shot(dorsal, x, y, team=0, made=1, time="08:35", quarter="3"):
    return {"m": str(made), "t": time, "x": str(x), "y": str(y), "team": str(team), "player": str(dorsal), "quarter": quarter}


def test_feb_an_assist_right_after_a_made_basket_links_passer_scorer_and_zone():
    doc = feb_doc([_line(1, "shoot", "1", "p2"), _line(2, "assist", "1", "p1")], [shot(5, 6, 50)])
    links = extract_links(doc, fbcyl=False)
    assert len(links.baskets) == 1
    b = links.baskets[0]
    assert (b["team_id"], b["scorer"], b["passer"]) == ("10", "p2", "p1")
    assert b["zone"] == "restricted_area"                       # x 6 %, y 50 %: under the rim (at 4 % it is behind the backboard: the engine says key_area)
    assert links.unlinked_assists == 0
    assert links.names == {"p1": "ANA", "p2": "BEA", "q1": "EVA"}


def test_feb_an_unlinked_assist_says_which_team_gave_it():
    links = extract_links(feb_doc([_line(1, "assist", "2", "q1")]), fbcyl=False)
    assert links.unlinked_team_ids == ["20"]


@pytest.mark.parametrize("text, points", [("(A) X: TIRO DE 2 ANOTADO (Puntos: 2)", 2), ("(A) X: TIRO DE 3 ANOTADO (Puntos: 3)", 3),
                                          ("(A) X: MATE ANOTADO (Puntos: 2)", 2), ("(A) X: MATE DE 3 ANOTADO (Puntos: 3)", 3)])
def test_feb_a_basket_knows_its_points(text, points):
    doc = feb_doc([_line(1, "shoot", "1", "p2", text=text)])
    assert extract_links(doc, fbcyl=False).baskets[0]["points"] == points


def test_feb_a_basket_without_assist_is_kept_with_no_passer():
    doc = feb_doc([_line(1, "shoot", "1", "p2")], [shot(5, 4, 50)])
    assert [(b["scorer"], b["passer"]) for b in extract_links(doc, fbcyl=False).baskets] == [("p2", None)]


def test_feb_missed_shots_and_free_throws_are_not_baskets():
    doc = feb_doc([_line(1, "shoot", "1", "p2", text="(A) X: TIRO DE 2 FALLADO"), _line(2, "fthrow", "1", "p2", text="(A) X: TIRO DE 1 ANOTADO (Puntos: 3)")])
    assert extract_links(doc, fbcyl=False).baskets == []


@pytest.mark.parametrize("name, lines", [
    ("after a free throw (assists logged there are not attributable)", [_line(1, "fthrow", "1", "p2", text="(A) X: TIRO DE 1 ANOTADO (Puntos: 1)"), _line(2, "assist", "1", "p1")]),
    ("the basket is the other team's", [_line(1, "shoot", "2", "q1"), _line(2, "assist", "1", "p1")]),
    ("another clock", [_line(1, "shoot", "1", "p2", time="08:40"), _line(2, "assist", "1", "p1")]),
    ("another quarter", [_line(1, "shoot", "1", "p2", quarter="2"), _line(2, "assist", "1", "p1")]),
    ("the passer is the scorer", [_line(1, "shoot", "1", "p1"), _line(2, "assist", "1", "p1")]),
    ("first line of the game", [_line(1, "assist", "1", "p1")]),
])
def test_feb_an_assist_that_cannot_be_tied_to_a_basket_is_counted_apart(name, lines):
    links = extract_links(feb_doc(lines), fbcyl=False)
    assert links.unlinked_assists == 1, name
    assert all(b["passer"] is None for b in links.baskets), name


def test_feb_a_basket_with_no_shotchart_shot_has_no_zone_but_still_counts():
    doc = feb_doc([_line(1, "shoot", "1", "p2"), _line(2, "assist", "1", "p1")])
    assert [(b["passer"], b["zone"]) for b in extract_links(doc, fbcyl=False).baskets] == [("p1", None)]


def test_feb_two_equal_shots_use_one_shotchart_shot_each_not_the_same_twice():
    doc = feb_doc([_line(1, "shoot", "1", "p2"), _line(2, "shoot", "1", "p2")], [shot(5, 4, 50), shot(5, 40, 5)])
    assert len({b["zone"] for b in extract_links(doc, fbcyl=False).baskets}) == 2


def test_feb_deleted_lines_are_ignored():
    doc = feb_doc([_line(1, "shoot", "1", "p2", deleted="1"), _line(2, "assist", "1", "p1")])
    links = extract_links(doc, fbcyl=False)
    assert links.baskets == [] and links.unlinked_assists == 1


def test_feb_a_game_without_play_by_play_gives_nothing():
    links = extract_links({"HEADER": {"TEAM": [{"id": "10"}, {"id": "20"}]}}, fbcyl=False)
    assert links.baskets == [] and links.unlinked_assists == 0


def test_feb_the_real_game_links_every_assist_that_follows_a_made_basket():
    doc = json.loads((ROOT / "src/JSON_samples/feb_game.json").read_text(encoding="utf-8"))
    doc = doc[0] if isinstance(doc, list) else doc
    lines = sorted(doc["PLAYBYPLAY"]["LINES"], key=lambda l: int(l["num"]))
    made = sum(1 for l in lines if l["action"] == "shoot" and "ANOTADO" in l["text"])
    assists = sum(1 for l in lines if l["action"] == "assist")
    links = extract_links(doc, fbcyl=False)
    assert len(links.baskets) == made
    assisted = sum(1 for b in links.baskets if b["passer"])
    assert assisted + links.unlinked_assists == assists
    assert assisted > 0
    assert sum(1 for b in links.baskets if b["zone"]) >= made - 2          # the shotchart misses about one basket in thirty


# -------------------------------------------------------------------------------------------------------------- FBCYL
def fb_doc(moves, shots=()):
    """Team intern 1 (extern 100) with players uuid u1 (actor 11), u2 (actor 12); team intern 2 (extern 200) with u9 (actor 19). ``shots``: (actor, eventUuid)."""
    def player(uuid, actor, name, mine):
        return {"uuid": uuid, "actorId": actor, "name": name, "data": {"shootingOfTwoSuccessfulPoint": [
            {"eventUuid": ev, "xnormalize": 8.0, "ynormalize": 46.0} for a, ev in shots if a == actor]}}
    return {"moves": moves, "stats": {"teams": [
        {"teamIdIntern": 1, "teamIdExtern": 100, "players": [player("u1", 11, "ANA", 1), player("u2", 12, "BEA", 1)]},
        {"teamIdIntern": 2, "teamIdExtern": 200, "players": [player("u9", 19, "EVA", 2)]},
    ]}}


def mv(move, team, actor, ev, sec=55, minute=9, period=1):
    return {"move": move, "idTeam": team, "actorId": actor, "eventUuid": ev, "min": minute, "sec": sec, "period": period}


def test_fbcyl_an_assist_right_after_a_basket_links_passer_scorer_and_zone_by_event_uuid():
    doc = fb_doc([mv("Canasta de 2", 1, 12, "e1"), mv("Asistencia", 1, 11, "e2")], [(12, "e1")])
    links = extract_links(doc, fbcyl=True)
    assert [(b["team_id"], b["scorer"], b["passer"]) for b in links.baskets] == [("100", "u2", "u1")]
    assert links.baskets[0]["zone"] is not None
    assert links.unlinked_assists == 0
    assert links.names["u1"] == "ANA"


@pytest.mark.parametrize("text, points", [("Canasta de 2", 2), ("Canasta de 3", 3), ("Mate", 2)])
def test_fbcyl_a_basket_knows_its_points(text, points):
    assert extract_links(fb_doc([mv(text, 1, 12, "e1")]), fbcyl=True).baskets[0]["points"] == points


def test_fbcyl_the_assist_can_come_a_move_later_when_something_sits_between():
    doc = fb_doc([mv("Canasta de 3", 1, 12, "e1"), mv("Rebote", 2, 19, "e0"), mv("Asistencia", 1, 11, "e2")])
    assert [b["passer"] for b in extract_links(doc, fbcyl=True).baskets] == ["u1"]


def test_fbcyl_free_throws_are_not_baskets_and_an_assist_after_one_is_unlinked():
    doc = fb_doc([mv("Canasta de 1", 1, 12, "e1"), mv("Asistencia", 1, 11, "e2")])
    links = extract_links(doc, fbcyl=True)
    assert links.baskets == [] and links.unlinked_assists == 1


@pytest.mark.parametrize("name, moves", [
    ("other team", [mv("Canasta de 2", 2, 19, "e1"), mv("Asistencia", 1, 11, "e2")]),
    ("other clock", [mv("Canasta de 2", 1, 12, "e1", sec=50), mv("Asistencia", 1, 11, "e2")]),
    ("other period", [mv("Canasta de 2", 1, 12, "e1", period=2), mv("Asistencia", 1, 11, "e2")]),
    ("self assist", [mv("Canasta de 2", 1, 11, "e1"), mv("Asistencia", 1, 11, "e2")]),
])
def test_fbcyl_an_assist_that_cannot_be_tied_to_a_basket_is_counted_apart(name, moves):
    links = extract_links(fb_doc(moves), fbcyl=True)
    assert links.unlinked_assists == 1, name
    assert all(b["passer"] is None for b in links.baskets), name


def test_fbcyl_one_basket_takes_one_assist_only():
    doc = fb_doc([mv("Canasta de 2", 1, 12, "e1"), mv("Asistencia", 1, 11, "e2"), mv("Asistencia", 1, 11, "e3")])
    links = extract_links(doc, fbcyl=True)
    assert [b["passer"] for b in links.baskets] == ["u1"] and links.unlinked_assists == 1


def test_fbcyl_a_basket_without_coordinates_still_counts_with_no_zone():
    doc = fb_doc([mv("Canasta de 2", 1, 12, "e1")])
    assert [(b["passer"], b["zone"]) for b in extract_links(doc, fbcyl=True).baskets] == [(None, None)]


def test_fbcyl_the_real_game_links_nearly_all_its_assists():
    doc = json.load(gzip.open(ROOT / "tests/fixtures/fbcyl_game_ok.json.gz", "rt", encoding="utf-8"))
    doc = doc[0] if isinstance(doc, list) else doc
    assists = sum(1 for m in doc["moves"] if m["move"].lower().startswith("asistencia"))
    links = extract_links(doc, fbcyl=True)
    assisted = sum(1 for b in links.baskets if b["passer"])
    assert assisted + links.unlinked_assists == assists and assisted >= assists - 2
    assert all(b["scorer"] != b["passer"] for b in links.baskets)


# ---- a malformed line of the real archive must not stop the publication of everything (web-data run of 06/11/2026: ``int(None)`` on a line with no team) ----
def test_feb_a_line_without_team_does_not_break_the_game_regression():
    """LF Endesa 2026-27 in the CI archive had a made shot (and an assist) with ``team: None``: the whole web-data publication failed on ``int(None)``."""
    lines = [_line(1, "shoot", None, "p2"), _line(2, "assist", None, "p1"), _line(3, "shoot", "1", "p2", time="05:00"), _line(4, "assist", "1", "p1", time="05:00")]
    links = extract_links(feb_doc(lines, [shot(5, 4, 50, time="05:00")]), fbcyl=False)
    assert [(b["scorer"], b["passer"]) for b in links.baskets] == [("p2", "p1")], "only the basket whose team is known is attributed"
    assert links.unlinked_assists == 1


@pytest.mark.parametrize("field, value", [("idPlayer", None), ("num", None), ("time", None), ("quarter", None), ("text", None), ("action", None)])
def test_feb_a_line_with_an_empty_field_never_raises(field, value):
    lines = [_line(1, "shoot", "1", "p2"), _line(2, "assist", "1", "p1")]
    lines[0][field] = value
    extract_links(feb_doc([{**l, "num": l["num"] or "9"} for l in lines]), fbcyl=False)


def test_feb_a_basket_or_an_assist_of_nobody_is_not_credited_to_a_ghost_player():
    links = extract_links(feb_doc([_line(1, "shoot", "1", None), _line(2, "assist", "1", "p1")]), fbcyl=False)
    assert links.baskets == [] and links.unlinked_assists == 1
    links = extract_links(feb_doc([_line(1, "shoot", "1", "p2"), _line(2, "assist", "1", None)]), fbcyl=False)
    assert [(b["scorer"], b["passer"]) for b in links.baskets] == [("p2", None)] and links.unlinked_assists == 1


def test_feb_a_shot_of_the_shotchart_with_an_empty_result_or_team_is_ignored():
    doc = feb_doc([_line(1, "shoot", "1", "p2")], [{**shot(5, 6, 50), "m": None}, {**shot(5, 6, 50), "team": None}, shot(5, 6, 50)])
    assert extract_links(doc, fbcyl=False).baskets[0]["zone"] == "restricted_area"


def test_fbcyl_a_move_without_actor_or_team_never_raises_nor_makes_a_ghost_player():
    doc = fb_doc([mv("Canasta de 2", 1, None, "e1"), mv("Asistencia", 1, None, "e2"), mv("Canasta de 2", None, 12, "e3"), mv("Asistencia", 1, 11, "e4")])
    links = extract_links(doc, fbcyl=True)
    assert all(b["scorer"] not in (None, "None") and b["passer"] not in ("None",) for b in links.baskets)
    assert links.unlinked_assists >= 1
