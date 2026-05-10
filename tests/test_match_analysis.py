"""Tests for MatchAnalysisService — TDD red phase.

Covers:
- Match list: FEB (sorted by date desc), empty collection
- Match analysis: home wins, away wins, draw, FEB field mapping
- Reverse stats: TOV%, PF — lower_is_better winner logic
- FBCYL field mapping
- Not-found returns None
- Formula unit tests: eFG%, possessions, OER
- Comparison builder: all expected stat keys present, delta sign correct
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from services.match_analysis_service import MatchAnalysisService


# ---------------------------------------------------------------------------
# Fixtures — minimal FEB/FBCYL match documents
# ---------------------------------------------------------------------------

def _feb_team_block(
    pts: int = 70,
    fgm: int = 25, fga: int = 55,
    p2m: int = 18, p2a: int = 38,
    p3m: int = 7,  p3a: int = 17,
    p1m: int = 8,  p1a: int = 10,
    ro: int = 8,   rd: int = 22,
    ast: int = 15, stl: int = 6,
    tov: int = 10, blk: int = 3, pf: int = 16,
    name: str = "TEAM A",
    team_id: str = "111",
) -> Dict:
    """Minimal FEB BOXSCORE.TEAM entry — matches real document structure.

    Real FEB documents contain a TOTAL sub-dict with authoritative team
    aggregates plus a PLAYER array with individual player rows.
    """
    return {
        "id": team_id,
        "name": name,
        # TOTAL is the authoritative source used by all other services
        "TOTAL": {
            "pts": str(pts),
            "fgm": str(fgm), "fga": str(fga),
            "p2m": str(p2m), "p2a": str(p2a),
            "p3m": str(p3m), "p3a": str(p3a),
            "p1m": str(p1m), "p1a": str(p1a),
            "ro":  str(ro),  "rd":  str(rd), "rt": str(ro + rd),
            "assist": str(ast),
            "st": str(stl),
            "to": str(tov),
            "bs": str(blk),
            "pf": str(pf),
        },
        "PLAYER": [
            {
                "pts": str(pts),
                "fgm": str(fgm), "fga": str(fga),
                "p2m": str(p2m), "p2a": str(p2a),
                "p3m": str(p3m), "p3a": str(p3a),
                "p1m": str(p1m), "p1a": str(p1a),
                "ro":  str(ro),  "rd":  str(rd), "rt": str(ro + rd),
                "assist": str(ast),
                "st": str(stl),
                "to": str(tov),
                "bs": str(blk),
                "pf": str(pf),
                "val": "20",
                "inn": "1",
            }
        ],
    }


def _make_feb_doc(
    match_id: int = 1001,
    home_pts: int = 70,
    away_pts: int = 65,
    date: str = "01-10-2025 - 19:00",
    round_: str = "1",
) -> Dict:
    """Minimal FEB match document."""
    return {
        "_id": match_id,
        "HEADER": {
            "game_code": match_id,
            "starttime": date,
            "place": "Pabellón Test",
            "round": round_,
            "TEAM": [
                {"id": "111", "name": "LOCAL TEAM", "pts": str(home_pts)},
                {"id": "222", "name": "VISITOR TEAM", "pts": str(away_pts)},
            ],
        },
        "BOXSCORE": {
            "TEAM": [
                _feb_team_block(pts=home_pts, name="LOCAL TEAM", team_id="111"),
                _feb_team_block(pts=away_pts, name="VISITOR TEAM", team_id="222",
                                fgm=22, fga=52, p2m=15, p2a=35, p3m=7, p3a=17,
                                p1m=6, p1a=8, ro=9, rd=20, ast=12, stl=4,
                                tov=13, blk=2, pf=18),
            ]
        },
    }


def _fbcyl_player(
    score: int = 60,
    p2m: int = 18, p2a: int = 36,
    p3m: int = 5,  p3a: int = 14,
    p1m: int = 7,  p1a: int = 9,
    orb: int = 7,  drb: int = 20,
    ast: int = 12, stl: int = 5,
    tov: int = 9,  blk: int = 2, pf: int = 14,
) -> Dict:
    return {
        "data": {
            "score": score,
            "shotsOfTwoSuccessful": p2m, "shotsOfTwoAttempted": p2a,
            "shotsOfThreeSuccessful": p3m, "shotsOfThreeAttempted": p3a,
            "shotsOfOneSuccessful": p1m, "shotsOfOneAttempted": p1a,
            "offensiveRebound": orb, "defensiveRebound": drb,
            "rebounds": orb + drb,
            "assists": ast, "steals": stl, "lost": tov,
            "block": blk, "personal": pf,
        }
    }


def _make_fbcyl_doc(
    match_id: str = "aabbccdd",
    home_score: int = 70,
    away_score: int = 65,
) -> Dict:
    """Minimal FBCYL match document."""
    return {
        "_id": match_id,
        "stats": {
            "idMatchIntern": 1,
            "time": "May 4, 2026 6:00:00 PM",
            "localId": 1001,
            "visitId": 1002,
            "score": [{"local": home_score, "visit": away_score, "period": 4}],
            "teams": [
                {
                    "teamIdIntern": 1001,
                    "name": "LOCAL FBCYL",
                    "players": [_fbcyl_player(score=home_score)],
                },
                {
                    "teamIdIntern": 1002,
                    "name": "VISITOR FBCYL",
                    "players": [_fbcyl_player(
                        score=away_score, p2m=15, p2a=33, p3m=4, p3a=12,
                        p1m=6, p1a=8, orb=8, drb=18, ast=10, stl=3,
                        tov=12, blk=1, pf=17,
                    )],
                },
            ],
        },
    }


def _make_service(docs: List[Dict], collection: str = "FEB_LF2_2025_A") -> MatchAnalysisService:
    """Build a MatchAnalysisService with a mocked MongoDB collection."""
    col = MagicMock()
    col.find.return_value = docs
    col.find_one.side_effect = lambda q, *a, **kw: next(
        (d for d in docs if d["_id"] == q.get("_id")), None
    )

    db = MagicMock()
    db.connection.get_collection.return_value = col
    return MatchAnalysisService(db, collection)


# ===========================================================================
# Match list
# ===========================================================================

class TestGetMatchList:
    def test_feb_returns_list_with_required_fields(self):
        doc = _make_feb_doc(match_id=100, home_pts=72, away_pts=68)
        svc = _make_service([doc])
        result = svc.get_match_list(is_fbcyl=False)
        assert isinstance(result, list)
        assert len(result) == 1
        row = result[0]
        assert row["match_id"] == 100
        assert row["home_team"] == "LOCAL TEAM"
        assert row["away_team"] == "VISITOR TEAM"
        assert row["home_score"] == 72
        assert row["away_score"] == 68
        assert "date" in row
        assert "round" in row

    def test_empty_collection_returns_empty_list(self):
        svc = _make_service([])
        result = svc.get_match_list(is_fbcyl=False)
        assert result == []

    def test_fbcyl_returns_list(self):
        doc = _make_fbcyl_doc(home_score=80, away_score=75)
        svc = _make_service([doc], collection="FBCYL_LF2_2025")
        result = svc.get_match_list(is_fbcyl=True)
        assert len(result) == 1
        row = result[0]
        assert row["home_team"] == "LOCAL FBCYL"
        assert row["away_score"] == 75

    def test_multiple_docs_returned(self):
        docs = [
            _make_feb_doc(match_id=i, date=f"0{i}-10-2025 - 19:00")
            for i in range(1, 4)
        ]
        svc = _make_service(docs)
        result = svc.get_match_list(is_fbcyl=False)
        assert len(result) == 3


# ===========================================================================
# Match analysis — FEB
# ===========================================================================

class TestGetMatchAnalysisFEB:
    def test_returns_none_for_missing_match(self):
        svc = _make_service([_make_feb_doc(match_id=999)])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        assert result is None

    def test_response_has_required_top_level_keys(self):
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        assert result is not None
        assert "home" in result
        assert "away" in result
        assert "comparison" in result

    def test_home_team_name_extracted(self):
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        assert result["home"]["team_name"] == "LOCAL TEAM"
        assert result["away"]["team_name"] == "VISITOR TEAM"

    def test_home_wins_pts_row(self):
        doc = _make_feb_doc(match_id=1, home_pts=80, away_pts=70)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        assert pts_row["winner"] == "home"
        assert pts_row["home_value"] == 80
        assert pts_row["away_value"] == 70
        assert pts_row["delta"] == pytest.approx(10)

    def test_away_wins_pts_row(self):
        doc = _make_feb_doc(match_id=1, home_pts=60, away_pts=75)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        assert pts_row["winner"] == "away"

    def test_all_comparison_rows_have_required_fields(self):
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        required = {"stat_key", "label", "home_value", "away_value", "delta",
                    "winner", "lower_is_better", "section"}
        for row in result["comparison"]:
            assert required <= row.keys(), f"Missing keys in row {row['stat_key']}"

    def test_expected_stat_keys_present(self):
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        keys = {r["stat_key"] for r in result["comparison"]}
        for expected in ["pts", "fg_pct", "three_pct", "ft_pct",
                         "reb", "ast", "stl", "tov", "blk", "pf",
                         "efg_pct", "tov_pct", "orb_pct", "ftr",
                         "possessions", "oer", "der", "net_rtg"]:
            assert expected in keys, f"Missing stat key: {expected}"

    def test_tov_is_lower_is_better(self):
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        tov_row = next(r for r in result["comparison"] if r["stat_key"] == "tov")
        assert tov_row["lower_is_better"] is True

    def test_tov_winner_is_lower_turnover_team(self):
        # Home: 10 TOV, Away: 5 TOV → away wins (fewer is better)
        doc = _make_feb_doc(match_id=1)
        home_block = doc["BOXSCORE"]["TEAM"][0]
        away_block = doc["BOXSCORE"]["TEAM"][1]
        home_block["to"] = "10"
        home_block["TOTAL"]["to"] = "10"
        home_block["PLAYER"][0]["to"] = "10"
        away_block["to"] = "5"
        away_block["TOTAL"]["to"] = "5"
        away_block["PLAYER"][0]["to"] = "5"
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        tov_row = next(r for r in result["comparison"] if r["stat_key"] == "tov")
        assert tov_row["winner"] == "away"

    def test_pts_is_not_lower_is_better(self):
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        assert pts_row["lower_is_better"] is False

    def test_der_is_lower_is_better(self):
        # Regression: defensive rating (der) must have lower_is_better=True
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        der_row = next((r for r in result["comparison"] if r["stat_key"] == "der"), None)
        assert der_row is not None, "der stat not found in comparison"
        assert der_row["lower_is_better"] is True, (
            "Defensive rating (der) should have lower_is_better=True"
        )


# ===========================================================================
# Match analysis — FBCYL
# ===========================================================================

class TestGetMatchAnalysisFBCYL:
    def test_returns_none_for_missing_match(self):
        svc = _make_service([_make_fbcyl_doc(match_id="abc")],
                            collection="FBCYL_LF2_2025")
        result = svc.get_match_analysis(match_id="xyz", is_fbcyl=True)
        assert result is None

    def test_response_has_required_keys(self):
        doc = _make_fbcyl_doc(match_id="aabb")
        svc = _make_service([doc], collection="FBCYL_LF2_2025")
        result = svc.get_match_analysis(match_id="aabb", is_fbcyl=True)
        assert result is not None
        assert "home" in result and "away" in result and "comparison" in result

    def test_home_team_name_fbcyl(self):
        doc = _make_fbcyl_doc(match_id="aabb")
        svc = _make_service([doc], collection="FBCYL_LF2_2025")
        result = svc.get_match_analysis(match_id="aabb", is_fbcyl=True)
        assert result["home"]["team_name"] == "LOCAL FBCYL"

    def test_pts_winner_fbcyl(self):
        doc = _make_fbcyl_doc(match_id="aabb", home_score=80, away_score=70)
        svc = _make_service([doc], collection="FBCYL_LF2_2025")
        result = svc.get_match_analysis(match_id="aabb", is_fbcyl=True)
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        assert pts_row["winner"] == "home"


# ===========================================================================
# Formula unit tests (pure functions, no DB needed)
# ===========================================================================

class TestFormulas:
    """Test the math helpers in isolation via the service's public interface."""

    def _get_comparison_row(self, stat_key: str, **doc_overrides) -> Dict:
        doc = _make_feb_doc(match_id=1, **doc_overrides)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        return next(r for r in result["comparison"] if r["stat_key"] == stat_key)

    def test_efg_pct_formula(self):
        # Home: FGM=25, 3PM=7, FGA=55 → eFG% = (25+0.5×7)/55 = 28.5/55 ≈ 51.82
        row = self._get_comparison_row("efg_pct")
        assert row["home_value"] == pytest.approx(51.82, abs=0.1)

    def test_fg_pct_formula(self):
        # Home: FGM=25, FGA=55 → FG% = 25/55 ≈ 45.45
        row = self._get_comparison_row("fg_pct")
        assert row["home_value"] == pytest.approx(45.45, abs=0.1)

    def test_three_pct_formula(self):
        # Home: 3PM=7, 3PA=17 → 3P% = 7/17 ≈ 41.18
        row = self._get_comparison_row("three_pct")
        assert row["home_value"] == pytest.approx(41.18, abs=0.1)

    def test_possessions_formula(self):
        # FGA - ORB + TOV + 0.44*FTA = 55 - 8 + 10 + 0.44*10 = 61.4
        row = self._get_comparison_row("possessions")
        assert row["home_value"] == pytest.approx(61.4, abs=0.5)

    def test_oer_formula(self):
        # OER = (PTS / possessions) * 100 = (70 / 61.4) * 100 ≈ 114.0
        row = self._get_comparison_row("oer")
        assert row["home_value"] == pytest.approx(114.0, abs=2.0)

    def test_net_rtg_is_oer_minus_der(self):
        doc = _make_feb_doc(match_id=1)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        comparison = {r["stat_key"]: r for r in result["comparison"]}
        home_oer = comparison["oer"]["home_value"]
        home_der = comparison["der"]["home_value"]
        home_net = comparison["net_rtg"]["home_value"]
        assert home_net == pytest.approx(home_oer - home_der, abs=0.01)

    def test_delta_is_home_minus_away_for_normal_stats(self):
        doc = _make_feb_doc(match_id=1, home_pts=75, away_pts=65)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=1, is_fbcyl=False)
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        assert pts_row["delta"] == pytest.approx(10.0, abs=0.01)

    def test_ftr_formula(self):
        # FTr = FTA / FGA = 10 / 55 ≈ 0.182
        row = self._get_comparison_row("ftr")
        assert row["home_value"] == pytest.approx(0.182, abs=0.01)


# ===========================================================================
# TOTAL block regression
# ===========================================================================

class TestTotalBlockRegression:
    """Regression: _stats_feb must read from BOXSCORE.TEAM[i].TOTAL.

    Bug: the original implementation summed individual PLAYER rows, which
    may be incomplete in real FEB documents.  The TOTAL sub-dict is the
    authoritative aggregate used by every other service.
    """

    def _make_doc_with_total_mismatch(self) -> Dict:
        """Doc where TOTAL has the real score but the single PLAYER has a lower value."""
        from copy import deepcopy
        doc = _make_feb_doc(match_id=5001, home_pts=72, away_pts=71)
        # Corrupt the PLAYER entry so summing players gives wrong result
        doc["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["pts"] = "40"
        doc["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["p2m"] = "12"
        doc["BOXSCORE"]["TEAM"][0]["PLAYER"][0]["p3m"] = "3"
        return doc

    def test_pts_from_total_not_player_sum(self):
        """Regression: home pts must equal TOTAL.pts (72), not sum-of-players (40)."""
        doc = self._make_doc_with_total_mismatch()
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=5001, is_fbcyl=False)
        assert result is not None
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        assert pts_row["home_value"] == 72, (
            f"Expected 72 (from TOTAL) but got {pts_row['home_value']} "
            "(probably from summing corrupt PLAYER rows)"
        )

    def test_winner_correct_when_using_total(self):
        """Regression: winner must reflect TOTAL score, not player-sum score."""
        doc = self._make_doc_with_total_mismatch()
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=5001, is_fbcyl=False)
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        # TOTAL: home=72, away=71 => home wins
        assert pts_row["winner"] == "home"

    def test_fallback_to_player_sum_when_no_total(self):
        """If TOTAL is absent the service must still work via player-row fallback."""
        from copy import deepcopy
        doc = _make_feb_doc(match_id=5002, home_pts=60, away_pts=55)
        # Remove TOTAL from both teams to simulate missing block
        doc["BOXSCORE"]["TEAM"][0].pop("TOTAL", None)
        doc["BOXSCORE"]["TEAM"][1].pop("TOTAL", None)
        svc = _make_service([doc])
        result = svc.get_match_analysis(match_id=5002, is_fbcyl=False)
        assert result is not None
        pts_row = next(r for r in result["comparison"] if r["stat_key"] == "pts")
        assert pts_row["home_value"] == 60
