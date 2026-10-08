"""Substitution recommender: role-similar replacements, availability constraints,
quintet balance and lever-driven picks. No position data: roles come from z-profiles."""

import pytest

from src.live_core.config import RuleConfig
from src.live_core.profiles import METRICS  # noqa: F401
from src.live_core.recommender import Recommender

from live_helpers import GUARD, BIG, WING, TABLE, ON_COURT, OWN, RIVAL, player, snap, z  # noqa: E402,F401


def rec(**cfg):
    return Recommender(OWN, TABLE, RuleConfig(**cfg))


def swaps(r, s, out, **kw):
    return r.suggest_swaps(s, out, **kw)


def test_a_big_is_replaced_by_a_big_not_by_a_guard():
    out = swaps(rec(), snap(), "b1")
    assert out and out[0]["in_id"] in ("b2", "b3")
    assert all(o["in_id"] != "g2" for o in out)
    assert out[0]["role_distance"] < 2.5


def test_a_guard_is_replaced_by_a_guard():
    out = swaps(rec(), snap(), "g1")
    assert out[0]["in_id"] == "g2"


def test_recommendation_has_everything_the_ui_needs():
    [first, *_] = swaps(rec(), snap(), "b1")
    for key in ("type", "out_id", "out_name", "in_id", "in_name", "score", "role_distance",
                "balance_ok", "balance_delta", "message"):
        assert key in first
    assert first["type"] == "sub" and "Entra" in first["message"] and first["in_name"] in first["message"]


def test_fouled_out_or_foul_troubled_candidates_are_excluded():
    s = snap(overrides={"b2": {"pf": 5}, "b3": {"pf": 3}})  # b3 hits the period-2 warning (3)
    ids = [o["in_id"] for o in swaps(rec(), s, "b1")]
    assert "b2" not in ids and "b3" not in ids


def test_overloaded_bench_players_are_excluded():
    s = snap(elapsed=1500, overrides={"b2": {"minutes": 1900}})
    assert "b2" not in [o["in_id"] for o in swaps(rec(), s, "b1")]


def test_nothing_is_forced_when_no_similar_role_is_available():
    s = snap(overrides={"b2": {"pf": 5}, "b3": {"pf": 5}})
    assert swaps(rec(), s, "b1") == []


def test_only_bench_players_of_the_own_team_with_a_profile_are_candidates():
    s = snap()
    s["players"]["rival"] = {**player("b2", False), "team_id": RIVAL}
    s["players"]["ghost"] = {**player("b2", False)}  # no baseline in the package
    ids = [o["in_id"] for o in swaps(rec(), s, "b1")]
    assert "rival" not in ids and "ghost" not in ids


def test_unknown_or_bench_outgoing_player_gives_nothing():
    assert swaps(rec(), snap(), "nobody") == []
    assert swaps(rec(), snap(), "b2") == []  # b2 is on the bench: nobody to take out


def test_lever_picks_the_candidate_who_improves_it_most():
    out = swaps(rec(), snap(), "g1", lever="tov")
    assert out[0]["in_id"] == "g2"          # tov40 z -1.0 vs the outgoing +2.0
    assert out[0]["lever"] == "tov" and out[0]["lever_gain"] == pytest.approx(3.0)


def test_lever_gain_signs_per_factor():
    assert swaps(rec(), snap(), "b1", lever="orb")[0]["in_id"] == "b2"        # best offensive rebounder
    gain = swaps(rec(), snap(), "b1", lever="orb")[0]["lever_gain"]
    assert gain == pytest.approx(1.6 - 2.0)  # b1 is the better rebounder: gain negative but still the best option


def test_unbalanced_swaps_are_flagged_and_ranked_after_balanced_ones():
    table = dict(TABLE)
    table["stretch"] = {"name": "Pivot Abierto", "z": z(**{**BIG, "orb40": -0.5, "drb40": -0.5, "blk40": 0.0,
                                                          "fg3a40": 1.0, "fg2a40": 0.2}),
                        "avg_min": 900, "p90_min": 1500}
    s = snap()
    s["players"]["stretch"] = {"name": "Pivot Abierto", "team_id": OWN, "on_court": False, "pf": 0,
                               "minutes": 0, "stint": 0, "pts": 0, "pf_by_period": {}}
    out = Recommender(OWN, table, RuleConfig(rec_max_role_distance=4.5)).suggest_swaps(s, "b1")
    flags = {o["in_id"]: o["balance_ok"] for o in out}
    assert flags["b2"] is True and flags["stretch"] is False
    assert [o["in_id"] for o in out].index("b2") < [o["in_id"] for o in out].index("stretch")


def test_lever_suggestions_choose_who_to_take_out_and_bring_in():
    out = rec().suggest_for_lever(snap(), "tov")
    assert out and out[0]["out_id"] == "g1" and out[0]["in_id"] == "g2"
    assert len({o["in_id"] for o in out}) == len(out)
    assert len(out) <= RuleConfig().rec_max_results


def test_results_are_deterministic_and_limited():
    a, b = swaps(rec(), snap(), "b1", max_results=2), swaps(rec(), snap(), "b1", max_results=2)
    assert a == b and len(a) <= 2


def test_empty_bench_and_missing_roster_do_not_crash():
    s = snap()
    for pid in ("g2", "b2", "b3"):
        s["players"][pid]["on_court"] = True
    assert swaps(rec(), s, "b1") == []
    assert Recommender(OWN, {}, RuleConfig()).suggest_for_lever(snap(), "tov") == []


def test_a_swap_that_does_not_improve_the_lever_does_not_claim_to():
    """Foul-trouble swaps are ranked by the lever but must not say they improve it when they do not."""
    worse = swaps(rec(), snap(), "b1", lever="orb")[0]          # gain is negative (b1 is the better rebounder)
    assert worse["lever_gain"] < 0 and "mejorar" not in worse["message"]
    better = swaps(rec(), snap(), "g1", lever="tov")[0]
    assert better["lever_gain"] > 0 and "mejora" in better["message"].lower()


def test_lever_suggestions_ignore_marginal_gains():
    cfg = RuleConfig()
    assert cfg.rec_min_lever_gain > 0
    out = rec().suggest_for_lever(snap(), "tov")
    assert out and all(o["lever_gain"] >= cfg.rec_min_lever_gain for o in out)
    strict = Recommender(OWN, TABLE, RuleConfig(rec_min_lever_gain=99.0))
    assert strict.suggest_for_lever(snap(), "tov") == []


def test_names_in_messages_are_trimmed():
    s = snap()
    s["players"]["b1"]["name"] = "Pivot Uno  "
    [first, *_] = swaps(rec(), s, "b1")
    assert "  " not in first["message"] and first["out_name"] == "Pivot Uno"
