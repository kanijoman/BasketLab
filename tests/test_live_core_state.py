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


def test_event_log_feeds_runs_and_streaks(feb_game_doc):
    """[elapsed, team_id, kind, value]: scoring, turnovers (player + team) and offensive rebounds."""
    _, snap = _final(feb_game_doc)
    log = snap["log"]
    assert log == sorted(log, key=lambda e: e[0]), "log must be chronological"
    for tid, team in snap["teams"].items():
        s = team["stats"]
        assert sum(v for t, team_id, k, v in [(e[0], e[1], e[2], e[3]) for e in log] if team_id == tid and k == "pts") == s["pts"]
        assert sum(1 for e in log if e[1] == tid and e[2] == "tov") == s["tov"] + s["tov_team"]
        assert sum(1 for e in log if e[1] == tid and e[2] == "orb") == s["orb"]


# --- rest between periods ----------------------------------------------------------

def _doc(quarter, clock):
    """P1 (team T1) is a starter that never leaves the court; one early event reveals him."""
    line = {"num": "1", "quarter": "1", "time": "09:00", "idTeam": "T1", "idPlayer": "P1",
            "action": "shoot", "text": "(A) UNO: TIRO DE 2 FALLADO", "deleted": None}
    return {
        "HEADER": {"TEAM": [{"id": "T1", "name": "A", "pts": "0"}, {"id": "T2", "name": "B", "pts": "0"}],
                   "quarter": str(quarter), "time": clock, "status": "2"},
        "BOXSCORE": {"TEAM": [{"id": "T1", "PLAYER": [{"id": "P1", "name": "UNO"}]},
                              {"id": "T2", "PLAYER": []}]},
        "PLAYBYPLAY": {"LINES": [line]},
    }


def _p1(quarter, clock):
    return LiveEngine().update(_doc(quarter, clock))["players"]["P1"]


def test_minutes_are_never_discounted_for_rest():
    assert _p1(3, "09:30")["minutes"] == 1230


def test_quarter_break_gives_partial_recovery_to_the_current_stint():
    # Q2 starts at 600 s of play; the 2-minute break credits 60 s.
    assert _p1(1, "05:00")["stint"] == 300
    assert _p1(2, "08:00")["stint"] == 720 - 60


def test_halftime_resets_the_stint_completely():
    assert _p1(3, "09:30")["stint"] == 30
    # Q4: 600 s of the second half minus the Q3->Q4 break credit.
    assert _p1(4, "09:00")["stint"] == 660 - 60


def test_a_player_who_re_enters_after_the_break_starts_a_fresh_stint():
    doc = _doc(2, "08:00")
    doc["PLAYBYPLAY"]["LINES"] += [
        {"num": "2", "quarter": "2", "time": "09:50", "idTeam": "T1", "idPlayer": "P1", "action": "subst",
         "text": "(A) UNO: Sustitución (Sale de pista)", "deleted": None},
        {"num": "3", "quarter": "2", "time": "09:00", "idTeam": "T1", "idPlayer": "P1", "action": "subst",
         "text": "(A) UNO: Sustitución (Entra a pista)", "deleted": None},
    ]
    p = LiveEngine().update(doc)["players"]["P1"]
    assert p["on_court"] and p["stint"] == 60  # in at 09:00 -> 60 s until 08:00, no credit


def test_closed_stints_are_recorded_with_the_rest_adjusted_length():
    """Baselines compare like with like: same stint measure as the live fatigue rule."""
    doc = _doc(2, "08:00")
    doc["PLAYBYPLAY"]["LINES"].append(
        {"num": "2", "quarter": "2", "time": "09:50", "idTeam": "T1", "idPlayer": "P1", "action": "subst",
         "text": "(A) UNO: Sustitución (Sale de pista)", "deleted": None})
    p = LiveEngine().update(doc)["players"]["P1"]
    assert p["stints_done"] == 1
    assert p["stint_sum"] == 610 - 60  # 610 s on court, minus the Q1->Q2 break credit


def test_open_stint_is_not_counted_as_done():
    p = _p1(1, "05:00")
    assert p["stints_done"] == 0 and p["stint_sum"] == 0 and p["stint"] == 300
