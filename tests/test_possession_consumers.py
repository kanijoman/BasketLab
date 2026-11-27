"""The consumers that still estimated possessions with 0.45 use the common estimate (0.44) and, when the game has them, its exact
possessions and validated rebounds / turnovers (#379): the weekly report's last match, the player sheet and the IN/OUT blocks."""
import pytest

from src.services.inout_service import enrich_stat_block as _enrich_stat_block


def _box(**kw):
    base = {"pts": 80, "p2m": 20, "p2a": 38, "p3m": 8, "p3a": 22, "p1m": 14, "p1a": 20, "ro": 10, "rd": 25, "assist": 15, "st": 7, "to": 12, "bs": 3}
    base.update({k: str(v) for k, v in kw.items()})
    return {k: str(v) if not isinstance(v, str) else v for k, v in base.items()}






def _game(derived=True):
    doc = {"HEADER": {"starttime": "05-10-2025 - 12:30", "TEAM": [{"id": "A", "name": "Local"}, {"id": "B", "name": "Visitante"}]},
           "BOXSCORE": {"TEAM": [{"id": "A", "TOTAL": {**_box(), "name": "Local"}}, {"id": "B", "TOTAL": {**_box(pts=70, ro=8, rd=20, to=14), "name": "Visitante"}}]}}
    if derived:
        doc["DERIVED"] = {"v": 5, "TEAM": [{"id": "A", "possessions": 75.0, "orb": 13, "drb": 26, "tov": 13},
                                           {"id": "B", "possessions": 72.0, "orb": 9, "drb": 22, "tov": 15}]}
    return doc












def test_the_player_sheet_blocks_use_the_common_free_throw_cost():
    block = _enrich_stat_block({"fga_2": 40, "fga_3": 20, "fta": 10, "tov": 8, "orb": 6, "points_for": 66, "minutes": 40,
                                "opp_fga_2": 35, "opp_fga_3": 20, "opp_fta": 10, "opp_tov": 9, "opp_orb": 5, "points_against": 60})

    assert block["possessions"] == pytest.approx(60 + 0.44 * 10 + 8 - 6, abs=0.05)             # 66.4, not 66.5
    assert block["offensive_rating"] == pytest.approx(66 / 66.4 * 100, abs=0.05)
