"""Incremental live state, validated against the OFFICIAL final box score of the real
sample game: if the PBP-derived numbers equal the box score, the parser is right."""

import json

import pytest

from src.live_core.engine import LiveEngine

DOC = "feb_game_doc"


def _final(feb_game_doc):
    engine = LiveEngine()
    return engine, engine.update(feb_game_doc)


def _box(doc):
    return {t["id"]: t for t in doc["BOXSCORE"]["TEAM"]}


def test_final_score_matches_header(feb_game_doc):
    _, snap = _final(feb_game_doc)
    for team in feb_game_doc["HEADER"]["TEAM"]:
        assert snap["score"][team["id"]] == int(team["pts"])


def test_player_fouls_match_box_score(feb_game_doc):
    _, snap = _final(feb_game_doc)
    for team in feb_game_doc["BOXSCORE"]["TEAM"]:
        for p in team["PLAYER"]:
            expected = int(p.get("pf") or 0)
            got = snap["players"].get(p["id"], {}).get("pf", 0)
            assert got == expected, f"{p['name']}: PBP {got} vs box {expected}"


def test_team_totals_match_box_score(feb_game_doc):
    _, snap = _final(feb_game_doc)
    for tid, team in _box(feb_game_doc).items():
        tot, s = team["TOTAL"], snap["teams"][tid]["stats"]
        pairs = {
            "fg2m": "p2m", "fg2a": "p2a", "fg3m": "p3m", "fg3a": "p3a", "ftm": "p1m", "fta": "p1a",
            "orb": "ro", "drb": "rd", "tov": "to", "stl": "st", "ast": "assist", "pts": "pts",
        }
        for ours, theirs in pairs.items():
            assert s[ours] == int(tot[theirs]), f"{tid} {ours}: {s[ours]} vs {theirs} {tot[theirs]}"


def test_minutes_match_box_score_within_tolerance(feb_game_doc):
    _, snap = _final(feb_game_doc)
    for team in feb_game_doc["BOXSCORE"]["TEAM"]:
        for p in team["PLAYER"]:
            expected = int(p.get("min") or 0)
            got = snap["players"].get(p["id"], {}).get("minutes", 0)
            assert abs(got - expected) <= 30, f"{p['name']}: {got}s vs box {expected}s"


def test_five_players_on_court_per_team_at_end_of_first_quarter(feb_game_doc):
    from src.live_core.replay import truncate_doc

    engine = LiveEngine()
    snap = engine.update(truncate_doc(feb_game_doc, period=2, remaining=590))
    for team in feb_game_doc["HEADER"]["TEAM"]:
        on = [p for p in snap["players"].values() if p["team_id"] == team["id"] and p["on_court"]]
        assert len(on) == 5, f"{team['name']} has {len(on)} on court"


def test_incremental_updates_equal_one_shot(feb_game_doc):
    from src.live_core.replay import truncate_doc

    one_shot = LiveEngine().update(feb_game_doc)
    engine = LiveEngine()
    snap = None
    for period, remaining in [(1, 300), (2, 0), (2, 420), (3, 300), (4, 599), (4, 0)]:
        snap = engine.update(truncate_doc(feb_game_doc, period=period, remaining=remaining))
    snap = engine.update(feb_game_doc)
    assert json.dumps(snap, sort_keys=True) == json.dumps(one_shot, sort_keys=True)


def test_refeeding_the_same_document_is_idempotent(feb_game_doc):
    engine = LiveEngine()
    first = engine.update(feb_game_doc)
    second = engine.update(feb_game_doc)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_line_order_does_not_matter(feb_game_doc):
    import copy

    doc = copy.deepcopy(feb_game_doc)
    doc["PLAYBYPLAY"]["LINES"].reverse()
    assert json.dumps(LiveEngine().update(doc), sort_keys=True) == json.dumps(
        LiveEngine().update(feb_game_doc), sort_keys=True)


def test_deleted_line_triggers_consistent_rebuild(feb_game_doc):
    import copy

    engine = LiveEngine()
    engine.update(feb_game_doc)
    doc = copy.deepcopy(feb_game_doc)
    target = next(l for l in doc["PLAYBYPLAY"]["LINES"]
                  if l["action"] == "shoot" and "ANOTADO" in l["text"] and l["num"] == "18")
    target["deleted"] = "1"
    snap = engine.update(doc)
    fresh = LiveEngine().update(doc)
    assert json.dumps(snap, sort_keys=True) == json.dumps(fresh, sort_keys=True)
    assert snap["score"]["982047"] == 74 - 2


def test_snapshot_is_json_serialisable(feb_game_doc):
    _, snap = _final(feb_game_doc)
    json.dumps(snap)


def test_clock_follows_the_header_when_it_is_a_clock(feb_game_doc):
    """The header is fresher than the last event (there may be no event for a while)."""
    from src.live_core.clock import elapsed_seconds
    from src.live_core.replay import truncate_doc

    snap = LiveEngine().update(truncate_doc(feb_game_doc, period=3, remaining=300))
    assert (snap["period"], snap["remaining"]) == (3, 300)
    assert snap["elapsed"] == elapsed_seconds(3, 300)


def test_clock_falls_back_to_the_last_event_when_header_is_final(feb_game_doc):
    snap = LiveEngine().update(feb_game_doc)  # header time is "FINAL"
    assert snap["period"] == 4 and snap["remaining"] == 0


def test_stint_keeps_growing_between_events(feb_game_doc):
    from src.live_core.replay import truncate_doc

    early = LiveEngine().update(truncate_doc(feb_game_doc, period=3, remaining=307))
    later = LiveEngine().update(truncate_doc(feb_game_doc, period=3, remaining=300))
    for pid, p in early["players"].items():
        if p["on_court"] and later["players"][pid]["on_court"]:
            assert later["players"][pid]["stint"] >= p["stint"] + 7 - 0


def test_team_level_turnovers_are_counted_separately(feb_game_doc):
    """FEB logs "Equipo: PERDIDA" with no player; the box score's player-based TO excludes it."""
    _, snap = _final(feb_game_doc)
    assert snap["teams"]["982047"]["stats"]["tov_team"] == 1
    assert snap["teams"]["981204"]["stats"]["tov_team"] == 0


def test_current_stint_grows_for_players_on_court(feb_game_doc):
    from src.live_core.replay import truncate_doc

    snap = LiveEngine().update(truncate_doc(feb_game_doc, period=1, remaining=60))
    on_court = [p for p in snap["players"].values() if p["on_court"]]
    assert on_court and all(p["stint"] > 0 for p in on_court)
    assert all(p["minutes"] >= p["stint"] for p in on_court)
