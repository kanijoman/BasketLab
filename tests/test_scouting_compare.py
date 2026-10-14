"""Our team against the scouted one, stat by stat (issue #299, the matchup part that came from #143)."""

from src.live_prep.scouting_compare import compare_teams

OWN = {"points_per_game": 70.0, "turnovers_per_game": 12.0, "efg_percentage": 50.0, "possessions_per_game": 70.0, "net_rating": 2.0}
RIVAL = {"points_per_game": 66.0, "turnovers_per_game": 15.0, "efg_percentage": 50.2, "possessions_per_game": 74.0, "net_rating": 5.0}


def by_key(rows):
    return {r["key"]: r for r in rows}


def test_advantage_follows_the_direction_of_each_stat():
    rows = by_key(compare_teams(OWN, RIVAL))
    assert rows["points_per_game"]["advantage"] == "own"          # more points is better
    assert rows["turnovers_per_game"]["advantage"] == "own"       # fewer turnovers is better
    assert rows["net_rating"]["advantage"] == "rival"


def test_a_difference_under_the_threshold_is_even_and_neutral_stats_have_no_advantage():
    rows = by_key(compare_teams(OWN, RIVAL))
    assert rows["efg_percentage"]["advantage"] == "even"          # 0.4 % apart
    assert rows["possessions_per_game"]["advantage"] == "neutral" # tempo depends on style


def test_values_are_formatted_like_the_report_and_carry_both_sides():
    r = by_key(compare_teams(OWN, RIVAL))["efg_percentage"]
    assert (r["own"], r["rival"]) == (50.0, 50.2) and r["own_text"] == "50,0 %" and r["rival_text"] == "50,2 %"
    assert r["label"] == "eFG%" and r["group"] == "Four Factors"


def test_biggest_gaps_first_and_stats_missing_on_a_side_are_left_out():
    rows = compare_teams({**OWN, "assists_per_game": 10.0}, RIVAL)
    assert "assists_per_game" not in by_key(rows)
    gaps = [abs(r["diff_pct"]) for r in rows if r["advantage"] != "neutral"]
    assert gaps == sorted(gaps, reverse=True)


def test_without_one_of_the_teams_there_is_nothing_to_compare():
    assert compare_teams(None, RIVAL) == [] and compare_teams(OWN, None) == []
    assert compare_teams({}, RIVAL) == []


def test_it_works_for_any_pair_of_teams():
    swap = {"own": "rival", "rival": "own", "even": "even", "neutral": "neutral"}
    forward = {r["key"]: r["advantage"] for r in compare_teams(OWN, RIVAL)}
    backward = {r["key"]: r["advantage"] for r in compare_teams(RIVAL, OWN)}
    assert backward == {k: swap[v] for k, v in forward.items()}
