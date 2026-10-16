"""Characterization of AdvancedStatsCalculator.calculate_all_advanced_stats for several player profiles.

Written before moving the rating formulas out of ``src/stats/advanced_stats_calculator.py`` (#360): every
statistic of every profile must stay identical. Regenerate the goldens, if a behaviour change is deliberate,
with ``python -c "from tests.test_advanced_stats_characterization import print_goldens; print_goldens()"``.
"""
from __future__ import annotations

import pytest

from src.stats.advanced_stats_calculator import AdvancedStatsCalculator

GOLDENS = {'bench_low_minutes': {'ast_pct': 6.02409638554217,
                       'blk_pct': 0.0,
                       'drating': 113.41654646677901,
                       'drb_pct': 10.416666666666666,
                       'efg': 28.571428571428573,
                       'ftr': 28.571428571428573,
                       'mpg': 6.0,
                       'net_rtg': -28.28763131325516,
                       'orating': 85.12891515352385,
                       'orb_pct': 5.376344086021505,
                       'pie': 0.042643923240938165,
                       'ppg': 1.5,
                       'stl_pct': 0.0,
                       'three_pr': 28.571428571428573,
                       'tov_pct': 11.261261261261263,
                       'ts': 38.07106598984772,
                       'usage': 18.435475834578973,
                       'val_pg': 1.0},
 'big_man': {'ast_pct': 8.080808080808081,
             'blk_pct': 12.0,
             'drating': 92.30403953186256,
             'drb_pct': 45.0,
             'efg': 62.5,
             'ftr': 44.642857142857146,
             'mpg': 25.0,
             'net_rtg': 26.014310775232715,
             'orating': 118.31835030709527,
             'orb_pct': 25.806451612903224,
             'pie': 16.545842217484008,
             'ppg': 17.0,
             'stl_pct': 0.96,
             'three_pr': 1.7857142857142858,
             'tov_pct': 15.723270440251572,
             'ts': 63.43283582089552,
             'usage': 31.689088191330345,
             'val_pg': 19.0},
 'empty_player': {'ast_pct': 0.0,
                  'blk_pct': 0.0,
                  'drating': 100.0,
                  'drb_pct': 0.0,
                  'efg': 0.0,
                  'ftr': 0.0,
                  'mpg': 0,
                  'net_rtg': 0.0,
                  'orating': 100.0,
                  'orb_pct': 0.0,
                  'pie': 0.0,
                  'ppg': 0,
                  'stl_pct': 0.0,
                  'three_pr': 0.0,
                  'tov_pct': 0.0,
                  'ts': 0.0,
                  'usage': 0.0,
                  'val_pg': 0},
 'empty_team': {'ast_pct': 0.0,
                'blk_pct': 0.0,
                'drating': 100.0,
                'drb_pct': 0.0,
                'efg': 50.0,
                'ftr': 21.428571428571427,
                'mpg': 28.0,
                'net_rtg': 0.0,
                'orating': 100.0,
                'orb_pct': 0.0,
                'pie': 0.0,
                'ppg': 14.0,
                'stl_pct': 1.4285714285714286,
                'three_pr': 42.857142857142854,
                'tov_pct': 11.547344110854505,
                'ts': 45.69190600522194,
                'usage': 0.0,
                'val_pg': 12.0},
 'guard': {'ast_pct': 19.10828025477707,
           'blk_pct': 1.7857142857142858,
           'drating': 105.4936921418689,
           'drb_pct': 17.857142857142858,
           'efg': 50.0,
           'ftr': 21.428571428571427,
           'mpg': 28.0,
           'net_rtg': 2.44141296268063,
           'orating': 107.93510510454954,
           'orb_pct': 9.216589861751151,
           'pie': 8.742004264392325,
           'ppg': 14.0,
           'stl_pct': 1.4285714285714286,
           'three_pr': 42.857142857142854,
           'tov_pct': 11.547344110854505,
           'ts': 45.69190600522194,
           'usage': 30.82069898213396,
           'val_pg': 12.0},
 'no_games': {'ast_pct': 19.10828025477707,
              'blk_pct': 1.7857142857142858,
              'drating': 105.4936921418689,
              'drb_pct': 17.857142857142858,
              'efg': 50.0,
              'ftr': 21.428571428571427,
              'mpg': 0,
              'net_rtg': 2.44141296268063,
              'orating': 107.93510510454954,
              'orb_pct': 9.216589861751151,
              'pie': 8.742004264392325,
              'ppg': 0,
              'stl_pct': 1.4285714285714286,
              'three_pr': 42.857142857142854,
              'tov_pct': 11.547344110854505,
              'ts': 45.69190600522194,
              'usage': 30.82069898213396,
              'val_pg': 0},
 'no_minutes': {'ast_pct': 0.0,
                'blk_pct': 0.0,
                'drating': 100.0,
                'drb_pct': 0.0,
                'efg': 0.0,
                'ftr': 0.0,
                'mpg': 0.0,
                'net_rtg': 0.0,
                'orating': 100.0,
                'orb_pct': 0.0,
                'pie': 0.0,
                'ppg': 0.0,
                'stl_pct': 0.0,
                'three_pr': 0.0,
                'tov_pct': 0.0,
                'ts': 0.0,
                'usage': 0.0,
                'val_pg': 0.0},
 'three_point_specialist': {'ast_pct': 24.0,
                            'blk_pct': 2.5,
                            'drating': 105.08607452782195,
                            'drb_pct': 9.375,
                            'efg': 51.829268292682926,
                            'ftr': 7.317073170731708,
                            'mpg': 20.0,
                            'net_rtg': -5.475383017968667,
                            'orating': 99.61069150985328,
                            'orb_pct': 1.935483870967742,
                            'pie': 4.776119402985075,
                            'ppg': 9.0,
                            'stl_pct': 2.0,
                            'three_pr': 85.36585365853658,
                            'tov_pct': 19.1131498470948,
                            'ts': 53.16635160680529,
                            'usage': 26.06875934230194,
                            'val_pg': 12.0}}

TEAM = {
    "total_games": 10, "points_scored": 750, "fg2_made": 240, "fg2_attempted": 430, "fg3_made": 70,
    "fg3_attempted": 200, "ft_made": 90, "ft_attempted": 120, "rebounds_off": 80, "rebounds_def": 250,
    "total_rebounds": 330, "assists": 160, "steals": 75, "blocks": 40, "turnovers": 120, "personal_fouls": 200,
}
OPP = {
    "total_games": 10, "points_scored": 720, "fg2_made": 220, "fg2_attempted": 400, "fg3_made": 60,
    "fg3_attempted": 180, "ft_made": 80, "ft_attempted": 100, "rebounds_off": 70, "rebounds_def": 230,
    "total_rebounds": 300, "assists": 140, "steals": 65, "blocks": 35, "turnovers": 130, "personal_fouls": 210,
}


def _player(games=10, mp=280, pts=140, p2m=40, p2a=80, p3m=20, p3a=60, p1m=20, p1a=30,
            ro=20, rd=40, ast=30, st=10, bs=5, pf=20, to=20, val=120):
    return {
        "games_played": games, "total_minutes": mp, "total_pts": pts, "total_val": val,
        "total_p2m": p2m, "total_p2a": p2a, "total_p3m": p3m, "total_p3a": p3a, "total_p1m": p1m, "total_p1a": p1a,
        "total_ro": ro, "total_rd": rd, "total_assist": ast, "total_st": st, "total_bs": bs,
        "total_pf": pf, "total_to": to,
    }


PROFILES = {
    "guard": _player(),
    "big_man": _player(mp=250, pts=170, p2m=70, p2a=110, p3m=0, p3a=2, p1m=30, p1a=50, ro=50, rd=90, ast=10, st=6,
                       bs=30, pf=35, to=25, val=190),
    "three_point_specialist": _player(mp=200, pts=90, p2m=5, p2a=12, p3m=25, p3a=70, p1m=5, p1a=6, ro=3, rd=15),
    "bench_low_minutes": _player(games=4, mp=24, pts=6, p2m=2, p2a=5, p3m=0, p3a=2, p1m=2, p1a=2, ro=1, rd=2,
                                 ast=1, st=0, bs=0, pf=3, to=1, val=4),
    "no_minutes": _player(games=3, mp=0, pts=0, p2m=0, p2a=0, p3m=0, p3a=0, p1m=0, p1a=0, ro=0, rd=0, ast=0,
                          st=0, bs=0, pf=0, to=0, val=0),
    "no_games": _player(games=0),
    "empty_player": {},
}


def _results():
    out = {}
    for name, player in PROFILES.items():
        out[name] = AdvancedStatsCalculator.calculate_all_advanced_stats(player, TEAM, OPP)
    out["empty_team"] = AdvancedStatsCalculator.calculate_all_advanced_stats(PROFILES["guard"], {}, {})
    return out


def print_goldens():  # pragma: no cover - maintenance helper
    import pprint

    pprint.pprint(_results(), width=110, sort_dicts=True)


@pytest.mark.parametrize("name", list(PROFILES) + ["empty_team"])
def test_all_advanced_stats_do_not_change(name):
    actual = _results()[name]
    assert set(actual) == set(GOLDENS[name])
    for key, expected in GOLDENS[name].items():
        assert actual[key] == pytest.approx(expected, rel=1e-12, abs=1e-12), (name, key)
