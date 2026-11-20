"""The bio and the shot chart of an ACB game in the canonical document (#886, D2g of epic #872): what the pages of the players add to the game.

The REAL pages of ``tests/fixtures/acb`` again: Amine Noua's bio and his 68 shots (11 of them in Real Madrid - Unicaja). The shots are the ones of ONE player, so the chart of that game is incomplete, and the
rule is that an incomplete chart is not published (FEB's chart has EXACTLY the field goals of the play by play; a chart with some of them would make every zone look different). The complete case is built with a shot
for every field goal of the real play by play, in the coordinates the real shots have.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.external.acb_canonical import FIELD_GOALS, chart_shots, feb_coordinates, to_canonical
from src.external.acb_page import parse_game, parse_player, parse_shots
from src.live_core.zones import classify_fiba, feb_to_fiba

FIX = Path(__file__).resolve().parent / "fixtures" / "acb"
ENTRY = {"competition": "Liga Endesa", "season_value": "2026", "season_label": "2026/2027", "league": "acb", "gender": "M", "acb": {"competition_id": 1, "edition_id": 91}}
NOUA = 30001137
HOOP_Y, CX = 1.575, 7.5


def flight(name):
    return gzip.decompress((FIX / f"{name}.flight.gz").read_bytes()).decode("utf-8")


@pytest.fixture(scope="module")
def parsed():
    return parse_game(flight("105383.estadisticas"), flight("105383.jugadas"))


@pytest.fixture(scope="module")
def match():
    return next(m for m in json.loads((FIX / "team-matches.json").read_text(encoding="utf-8"))["matches"] if m["id"] == 105383)


@pytest.fixture(scope="module")
def noua_shots():
    return parse_shots(flight("player.zonas-de-tiro"))["shots"]


class TestTheCoordinates:
    def test_a_shot_of_acb_becomes_the_percentages_of_the_court_that_the_engine_turns_back_into_the_same_point(self, noua_shots):
        """ACB gives the metres from the basket (``x`` along the court, ``y`` across it, in millimetres); FEB the percentages of the whole court of the team that shoots. The engine's ``feb_to_fiba`` must give back
        the same point on the half court, for the team that shoots at the left basket and for the one that shoots at the right one."""
        for s in noua_shots:
            fiba = (CX + s["y"] / 1000, HOOP_Y + s["x"] / 1000)
            if fiba[1] > 14:                                                      # a shot from the other half of the court (a heave) folds over in FEB's chart
                continue
            for team in (0, 1):
                x_pct, y_pct = feb_coordinates(s["x"], s["y"], team)
                back = feb_to_fiba(x_pct, y_pct, team)
                assert back == pytest.approx(fiba, abs=0.02), (s, team)

    def test_the_zone_the_engine_gives_is_the_zone_of_acb_for_every_real_shot(self, noua_shots):
        expected = {"restricted_area": {"restricted_area"}, "paint": {"key_area"}, "corner_three_left": {"left_corner_three"}, "corner_three_right": {"right_corner_three"},
                    "wing_three_left": {"left_wing_three"}, "wing_three_right": {"right_wing_three"}, "top_three": {"center_three", "left_wing_three", "right_wing_three"},
                    "mid_range_left": {"short_mid_range", "medium_mid_range", "long_mid_range"}, "mid_range_right": {"short_mid_range", "medium_mid_range", "long_mid_range"}}
        for s in noua_shots:
            x, y = feb_to_fiba(*feb_coordinates(s["x"], s["y"], 0), 0)
            assert classify_fiba(x, y)["zone"] in expected[s["zone"]], s

    def test_the_left_and_the_right_of_acb_are_the_left_and_the_right_of_the_engine(self):
        left = feb_to_fiba(*feb_coordinates(246, -6836, 0), 0)
        right = feb_to_fiba(*feb_coordinates(246, 6836, 0), 0)
        assert classify_fiba(*left)["zone"] == "left_corner_three" and classify_fiba(*right)["zone"] == "right_corner_three"


class TestTheBio:
    def test_the_players_have_their_position_from_the_box_and_the_bio_from_their_page_when_it_is_there(self, parsed, match):
        bio = parse_player(flight("player.temporada"))
        doc = to_canonical(parsed, match, ENTRY, bios={NOUA: bio})
        noua = next(p for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if p["id"] == f"acb:{NOUA}")
        assert (noua["birth"], noua["height"], noua["nationality"], noua["position"]) == ("1997-02-07", "202", "Francia", "Ala-pívot")
        other = next(p for p in doc["BOXSCORE"]["TEAM"][0]["PLAYER"])
        assert other["birth"] is None and other["height"] is None and other["position"]                                       # the position comes with the box: every player has it

    def test_a_bio_without_a_birth_or_a_height_leaves_them_empty_and_never_guessed(self, parsed, match):
        bio = {**parse_player(flight("player.temporada")), "birth": None, "height_cm": None}
        doc = to_canonical(parsed, match, ENTRY, bios={NOUA: bio})
        noua = next(p for t in doc["BOXSCORE"]["TEAM"] for p in t["PLAYER"] if p["id"] == f"acb:{NOUA}")
        assert noua["birth"] is None and noua["height"] is None and noua["nationality"] == "Francia"


class TestTheChart:
    def test_the_shots_of_one_player_do_not_make_a_chart_of_the_game(self, parsed, match, noua_shots):
        doc = to_canonical(parsed, match, ENTRY, shots={NOUA: noua_shots})
        assert doc["SHOTCHART"]["SHOTS"] == []                                                                                # 11 of the 150 field goals: incomplete
        covered, total = chart_shots(parsed, {NOUA: noua_shots})[1:]
        assert (covered, total) == (11, sum(1 for p in parsed["plays"] if p["type"] in FIELD_GOALS))

    def test_with_a_shot_for_every_field_goal_the_chart_is_the_one_of_the_play_by_play(self, parsed, match, noua_shots):
        everyone = _everyone(parsed, noua_shots)
        doc = to_canonical(parsed, match, ENTRY, shots=everyone)
        shots = doc["SHOTCHART"]["SHOTS"]
        lines = [l for l in doc["PLAYBYPLAY"]["LINES"] if l["action"] == "shoot"]
        assert len(shots) == len(lines) and sum(1 for s in shots if s["m"] == "1") == sum(1 for l in lines if "ANOTADO" in l["text"])
        assert sorted((s["quarter"], s["t"], s["m"], s["team"]) for s in shots) == sorted((l["quarter"], l["time"], "1" if "ANOTADO" in l["text"] else "0", "0" if l["idTeam"] == "acb:4476" else "1") for l in lines)

    def test_a_shot_is_written_as_feb_writes_it_with_the_dorsal_and_the_team_slot(self, parsed, match, noua_shots):
        doc = to_canonical(parsed, match, ENTRY, shots=_everyone(parsed, noua_shots))
        shot = next(s for s in doc["SHOTCHART"]["SHOTS"] if s["team"] == "1" and s["player"] == "17")                     # Noua wears 17 and plays for Unicaja, the second team
        assert set(shot) == {"m", "t", "x", "y", "team", "player", "quarter"} and shot["m"] in ("0", "1") and len(shot["t"]) == 5 and shot["quarter"] in ("1", "2", "3", "4")
        assert 0 <= float(shot["x"]) <= 100 and 0 <= float(shot["y"]) <= 100
        teams = doc["SHOTCHART"]["TEAM"]
        assert [t["id"] for t in teams] == ["acb:4476", "acb:4477"] and any(p["id"] == f"acb:{NOUA}" and p["no"] == "17" for p in teams[1]["PLAYER"])

    def test_the_zone_pipeline_of_the_engine_reads_the_chart(self, parsed, match, noua_shots):
        from src.live_core.zones import classify_shot

        doc = to_canonical(parsed, match, ENTRY, shots=_everyone(parsed, noua_shots))
        zones = {classify_shot(s)["zone"] for s in doc["SHOTCHART"]["SHOTS"]}
        assert {"restricted_area", "left_corner_three", "right_corner_three", "key_area"} <= zones                # the zones of the real shots of Noua (the other players have copies of them)

    def test_a_game_where_the_shots_of_a_player_do_not_match_his_plays_gets_no_chart_for_him_and_so_none(self, parsed, match, noua_shots):
        everyone = _everyone(parsed, noua_shots)
        everyone[NOUA] = [dict(s, play_type=97 if s["play_type"] == 93 else s["play_type"]) for s in everyone[NOUA]]            # one of another type
        assert to_canonical(parsed, match, ENTRY, shots=everyone)["SHOTCHART"]["SHOTS"] == []

    def test_converting_with_the_pages_of_the_players_changes_nothing_of_what_it_gets_without_them(self, parsed, match, noua_shots):
        plain = to_canonical(parsed, match, ENTRY)
        rich = to_canonical(parsed, match, ENTRY, shots=_everyone(parsed, noua_shots), bios={NOUA: parse_player(flight("player.temporada"))})
        assert rich["PLAYBYPLAY"] == plain["PLAYBYPLAY"] and rich["HEADER"] == plain["HEADER"] and plain["SHOTCHART"] == {"quarters": None, "duration": None, "TEAM": [], "SHOTS": []}


def _everyone(parsed, noua_shots):
    """A shot for every field goal of every player of the game: the real ones of Noua and, for the rest, the coordinates of the real shots in turn (the same type of play)."""
    real = {t: [s for s in noua_shots if s["play_type"] == t] for t in FIELD_GOALS}
    out = {}
    counters = {}
    for play in sorted(parsed["plays"], key=lambda p: p["order"]):
        if play["type"] not in FIELD_GOALS or play["player_id"] == NOUA:
            continue
        pool = real[play["type"]] or noua_shots
        index = counters.get(play["type"], 0)
        counters[play["type"]] = index + 1
        base = pool[index % len(pool)]
        out.setdefault(play["player_id"], []).append(dict(base, id=len(out.get(play["player_id"], [])) + 1, match_id=parsed["match_id"], play_type=play["type"], made=play["type"] in (93, 94, 100)))
    out[NOUA] = noua_shots
    return out
