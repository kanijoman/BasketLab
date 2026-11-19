"""Rates, role and percentiles of the Talent rows (B2, #878). One call is ONE competition and season: the population of the percentiles is the players of that competition only, never mixed.

Rates and role are the ones of the live engine (``live_core.profiles``: per-40, shrinkage towards the league by playing time, z-scored role dimensions) so that a player of Talent and a
player of a live package are described the same way. A percentile says how good a player is among those of his competition who played enough: for turnovers, lower is better."""
import pytest

from src.market.profile import MIN_GAMES, MIN_MINUTES_PER_GAME, MIN_TEAM_GAMES_SHARE, PERCENTILE_METRICS, add_profiles


def _row(person, minutes=24000, team="T", **over):
    base = {"person_id": person, "team_id": team, "league": "feb", "minutes": minutes, "games": 20, "pts": 200, "p1m": 40, "p1a": 50, "p2m": 60, "p2a": 120, "p3m": 20, "p3a": 60,
            "assist": 60, "ro": 20, "rd": 80, "rt": 100, "st": 20, "to": 40, "bs": 10, "pf": 50, "rf": 40, "val": 200, "pllss": 0}
    return {**base, **over}


def _league(n=12):
    """A small competition with a spread: player i scores and rebounds more the higher i is, and loses fewer balls."""
    return [_row(f"feb:{i}", pts=100 + 20 * i, p3m=10 + i, ro=10 + 2 * i, rd=40 + 6 * i, assist=30 + 5 * i, **{"to": 80 - 4 * i}) for i in range(n)]


def test_the_per_40_rates_are_the_raw_ones_of_the_stats_and_the_minutes():
    (row,) = add_profiles([_row("feb:1", minutes=12000, pts=100, p1m=10, p2m=30, p3m=20, p2a=60, p3a=40, p1a=20, ro=10, rd=30, assist=20, **{"to": 12})])
    assert row["per40"]["pts"] == pytest.approx((2 * 30 + 3 * 20 + 10) * 2400 / 12000)           # points made (2 x 2P + 3 x 3P + FT) scaled from 12,000 s to 40 minutes
    assert row["per40"]["orb"] == pytest.approx(10 * 2400 / 12000) and row["per40"]["tov"] == pytest.approx(12 * 2400 / 12000)
    assert row["per40"]["efg"] == pytest.approx((30 + 1.5 * 20) / 100) and row["per40"]["ts"] > 0


def test_a_player_without_minutes_has_nothing_known_not_zeros():
    (row,) = add_profiles([_row("feb:9", minutes=0, games=0)])
    assert row["per40"] is None and row["role"] is None and row["pct"] is None and row["eligible"] is False


def test_the_percentile_follows_the_value_and_the_best_of_the_league_is_near_100():
    rows = add_profiles(_league())
    by_points = sorted(rows, key=lambda r: r["per40"]["pts"])
    pcts = [r["pct"]["pts"] for r in by_points]
    assert pcts == sorted(pcts) and pcts[-1] > 90 and pcts[0] < 10


def test_for_turnovers_lower_is_better():
    rows = add_profiles(_league())
    fewest = min(rows, key=lambda r: r["per40"]["tov"])
    most = max(rows, key=lambda r: r["per40"]["tov"])
    assert fewest["pct"]["tov"] > most["pct"]["tov"] and fewest["pct"]["tov"] > 90


def test_ties_share_the_middle_rank_and_a_lone_player_is_in_the_middle():
    same = add_profiles([_row(f"feb:{i}") for i in range(4)])
    assert {r["pct"]["pts"] for r in same} == {50.0}
    (alone,) = add_profiles([_row("feb:1")])
    assert alone["pct"]["pts"] == 50.0


def test_players_with_few_minutes_are_ranked_but_do_not_make_the_population():
    league = _league()
    base = add_profiles(league)
    extra = add_profiles(league + [_row("feb:rookie", minutes=60, games=20, pts=900)])
    assert [r["pct"] for r in extra[:-1]] == [r["pct"] for r in base]                  # the population did not move
    assert extra[-1]["eligible"] is False and extra[-1]["pct"]["pts"] is not None and all(r["eligible"] for r in base)


def test_the_role_is_standardised_against_his_own_competition_and_the_percentiles_never_mix_competitions():
    strong, weak = _league(), [_row(f"feb:w{i}", p3m=2 + i, ro=5 + i, rd=20 + 2 * i, assist=10 + i) for i in range(12)]
    a, b = add_profiles(strong), add_profiles(weak)
    assert max(r["pct"]["pts"] for r in a) == max(r["pct"]["pts"] for r in b) > 90                # the best of each is the best of his own
    top_strong = max(a, key=lambda r: r["per40"]["pts"])
    top_weak = max(b, key=lambda r: r["per40"]["pts"])
    assert top_strong["per40"]["pts"] > top_weak["per40"]["pts"] and top_strong["pct"]["pts"] == top_weak["pct"]["pts"]


def test_a_player_with_little_time_is_pulled_towards_the_league_in_his_role():
    """Shrinkage: 15 minutes of an extreme rate say less than 400 of it, so the role z is closer to 0 than the raw one."""
    from src.live_core.profiles import league_distribution, raw_rates, z_scores

    league_rows = _league()
    few = _row("feb:few", minutes=900, ro=30, rd=60)
    rows = add_profiles(league_rows + [few])
    stats = lambda r: {"orb": r["ro"], "drb": r["rd"], "ast": r["assist"], "tov": r["to"], "stl": r["st"], "blk": r["bs"], "fg2a": r["p2a"], "fg3a": r["p3a"], "fg2m": r["p2m"], "fg3m": r["p3m"], "fta": r["p1a"], "ftm": r["p1m"]}
    league = league_distribution([raw_rates(stats(r), r["minutes"]) for r in league_rows])
    raw_z = z_scores(raw_rates(stats(few), few["minutes"]), league)
    assert abs(rows[-1]["role"]["orb40"]) < abs(raw_z["orb40"])
    assert set(rows[-1]["role"]) == {"orb40", "drb40", "ast40", "blk40", "fg3a40", "fg2a40", "usage40"}


def test_the_percentile_metrics_are_all_published_and_the_run_is_deterministic_and_does_not_change_the_input():
    league = _league()
    before = [dict(r) for r in league]
    first = add_profiles(league)
    assert league == before and first == add_profiles(list(league))
    assert set(first[0]["pct"]) == set(PERCENTILE_METRICS)
    assert add_profiles([]) == []


class TestPlayedEnough:
    """``eligible`` is «played enough» (#1010): at least 10 minutes per game he played, at least a third of the games of HIS team, and at least 3 games. It was 5 minutes in the whole season (94.6 % of the rows of
    the published senior FEB competitions passed): the search let through players with almost no minutes and their percentiles were noise. The same rule is the population of the percentiles."""

    @staticmethod
    def _eligible(player, mates=()):
        rows = add_profiles([player, *mates])
        return rows[0]["eligible"]

    def test_the_numbers_of_the_rule(self):
        assert (MIN_MINUTES_PER_GAME, MIN_GAMES) == (10, 3) and MIN_TEAM_GAMES_SHARE == pytest.approx(1 / 3)

    def test_ten_minutes_a_game_is_enough_and_a_second_less_is_not(self):
        assert self._eligible(_row("feb:1", games=10, minutes=10 * 600)) is True
        assert self._eligible(_row("feb:1", games=10, minutes=10 * 600 - 1)) is False

    def test_three_games_is_enough_and_two_is_not_however_many_minutes_he_played(self):
        mates = [_row("feb:m", team="A", games=3, minutes=3 * 1800)]
        assert self._eligible(_row("feb:1", team="A", games=3, minutes=3 * 1800), mates) is True
        assert self._eligible(_row("feb:1", team="A", games=2, minutes=2 * 2400), mates) is False

    def test_a_third_of_the_games_of_his_team_is_enough_and_less_is_not(self):
        team = [_row("feb:m", team="A", games=21, minutes=21 * 1800)]
        assert self._eligible(_row("feb:1", team="A", games=7, minutes=7 * 1500), team) is True            # 7 of 21
        assert self._eligible(_row("feb:1", team="A", games=6, minutes=6 * 1500), team) is False           # 6 of 21

    def test_the_games_of_the_team_are_those_of_ITS_most_played_player_not_of_another_team(self):
        other = [_row("feb:o", team="B", games=30, minutes=30 * 1800)]
        own = [_row("feb:m", team="A", games=9, minutes=9 * 1800)]
        assert self._eligible(_row("feb:1", team="A", games=3, minutes=3 * 1500), own + other) is True      # 3 of 9, whatever the others play

    def test_at_the_start_of_the_season_a_player_who_played_what_his_team_did_is_enough(self):
        team = [_row("feb:m", team="A", games=4, minutes=4 * 1800)]
        assert self._eligible(_row("feb:1", team="A", games=4, minutes=4 * 1500), team) is True

    def test_a_transfer_is_two_rows_each_against_the_games_of_its_own_team(self):
        rows = add_profiles([_row("feb:t", team="A", games=12, minutes=12 * 1500), _row("feb:t", team="B", games=3, minutes=3 * 1500),
                             _row("feb:a", team="A", games=36, minutes=36 * 1800), _row("feb:b", team="B", games=9, minutes=9 * 1800)])
        assert [r["eligible"] for r in rows[:2]] == [True, True]                                                # 12 of 36 and 3 of 9

    def test_those_who_did_not_play_enough_do_not_make_the_population_of_the_percentiles(self):
        league = _league()
        base = add_profiles(league)
        noise = add_profiles(league + [_row("feb:few", games=20, minutes=20 * 300, pts=900)])               # 5 min a game
        assert [r["pct"] for r in noise[:-1]] == [r["pct"] for r in base] and noise[-1]["eligible"] is False

    def test_the_answer_does_not_depend_on_the_order_of_the_rows(self):
        rows = [_row("feb:1", team="A", games=7, minutes=7 * 1500), _row("feb:m", team="A", games=21, minutes=21 * 1800), _row("feb:2", team="B", games=3, minutes=3 * 300)]
        first = {r["person_id"]: r["eligible"] for r in add_profiles(rows)}
        assert first == {r["person_id"]: r["eligible"] for r in add_profiles(list(reversed(rows)))}
