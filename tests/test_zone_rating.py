"""Zone shooting rated against the league's average for that zone (issue #139)."""
import pytest

from src.shotcharts.zone_rating import ZoneRatingConfig, rate_zone, rate_zones


def _r(fgm, fga, lfgm, lfga, **kw):
    return rate_zone(fgm, fga, lfgm, lfga, ZoneRatingConfig(**kw) if kw else None)


class TestRateZone:
    def test_clearly_above_league_average(self):
        r = _r(60, 100, 400, 1000)
        assert r["rating"] == "above"
        assert r["league_pct"] == pytest.approx(40.0)
        assert r["delta_pp"] == pytest.approx(20.0)

    def test_clearly_below_league_average(self):
        assert _r(20, 100, 400, 1000)["rating"] == "below"

    def test_close_to_average_is_average(self):
        assert _r(41, 100, 400, 1000)["rating"] == "average"

    def test_small_gap_is_average_even_with_many_shots(self):
        # +1 pp with 2000 shots is statistically significant but below the 2 pp floor
        assert _r(820, 2000, 400, 1000, )["rating"] == "average"

    def test_large_gap_with_few_shots_is_average_when_noise_dominates(self):
        # 6/10 = 60 % vs 50 %: +10 pp but z = 0.63 < 1
        assert _r(6, 10, 500, 1000)["rating"] == "average"

    def test_no_shots(self):
        r = _r(0, 0, 400, 1000)
        assert r["rating"] == "none" and r["delta_pp"] is None

    def test_league_without_data_is_unknown(self):
        assert _r(5, 10, 0, 0)["rating"] == "unknown"

    def test_low_sample_flag(self):
        assert _r(3, 9, 400, 1000)["low_sample"] is True
        assert _r(4, 10, 400, 1000)["low_sample"] is False

    def test_thresholds_are_configurable(self):
        assert _r(43, 100, 400, 1000)["rating"] == "average"
        assert _r(43, 100, 400, 1000, z_threshold=0.5, min_delta_pp=1.0)["rating"] == "above"

    def test_degenerate_league_pct_does_not_divide_by_zero(self):
        assert _r(1, 10, 0, 1000)["rating"] in {"above", "average"}
        assert _r(9, 10, 1000, 1000)["rating"] in {"below", "average"}


class TestRateZones:
    ZONES = [
        {"zone": "paint", "fga": 100, "fgm": 60, "fg_pct": 60.0},
        {"zone": "top_three", "fga": 0, "fgm": 0, "fg_pct": 0.0},
    ]
    LEAGUE = [
        {"zone": "paint", "fga": 1000, "fgm": 400, "fg_pct": 40.0},
        {"zone": "top_three", "fga": 500, "fgm": 150, "fg_pct": 30.0},
    ]

    def test_adds_rating_fields_per_zone_keeping_originals(self):
        out = rate_zones(self.ZONES, self.LEAGUE)
        assert out[0]["zone"] == "paint" and out[0]["fg_pct"] == 60.0
        assert out[0]["rating"] == "above" and out[0]["league_pct"] == pytest.approx(40.0)
        assert out[1]["rating"] == "none"

    def test_zone_missing_in_league_is_unknown(self):
        out = rate_zones(self.ZONES, [])
        assert out[0]["rating"] == "unknown"

    def test_inputs_are_not_mutated(self):
        rate_zones(self.ZONES, self.LEAGUE)
        assert "rating" not in self.ZONES[0]
