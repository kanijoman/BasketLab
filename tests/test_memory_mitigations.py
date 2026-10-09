"""Memory mitigations for the 512 MB Render limit (issue #163)."""
import json
import time
from pathlib import Path

import pytest
from db_helpers import new_mock_db

ROOT = Path(__file__).resolve().parents[1]


# --- 1. a single uvicorn worker by default ------------------------------------------------

class TestWorkers:
    def test_defaults_to_one_worker_on_linux_production_regression(self):
        """run_api.py used to start 4 workers on Linux (≈170 MB each at idle > 512 MB)."""
        from src.api.runtime import uvicorn_workers

        assert uvicorn_workers({}, "linux", dev_mode=False) == 1

    def test_web_concurrency_overrides(self):
        from src.api.runtime import uvicorn_workers

        assert uvicorn_workers({"WEB_CONCURRENCY": "2"}, "linux", dev_mode=False) == 2

    @pytest.mark.parametrize("raw", ["", "0", "-3", "abc", "1.5"])
    def test_invalid_values_fall_back_to_one(self, raw):
        from src.api.runtime import uvicorn_workers

        assert uvicorn_workers({"WEB_CONCURRENCY": raw}, "linux", dev_mode=False) == 1

    def test_capped_to_protect_memory(self):
        from src.api.runtime import MAX_WORKERS, uvicorn_workers

        assert uvicorn_workers({"WEB_CONCURRENCY": "50"}, "linux", dev_mode=False) == MAX_WORKERS

    def test_windows_is_always_single(self):
        from src.api.runtime import uvicorn_workers

        assert uvicorn_workers({"WEB_CONCURRENCY": "3"}, "win32", dev_mode=False) == 1

    def test_dev_mode_uses_reload_without_workers(self):
        from src.api.runtime import uvicorn_workers

        assert uvicorn_workers({}, "linux", dev_mode=True) is None

    def test_run_api_uses_the_helper_instead_of_a_hardcoded_four(self):
        src = (ROOT / "run_api.py").read_text(encoding="utf-8")
        assert "uvicorn_workers" in src and "else 4" not in src


# --- 2. the match list must not load whole documents ---------------------------------------

def _feb_doc(i):
    return {
        "_id": f"g{i}",
        "HEADER": {"starttime": "01-10-2026 - 18:00", "round": "1", "place": "Pab",
                   "TEAM": [{"name": "A", "pts": "80"}, {"name": "B", "pts": "70"}]},
        "BOXSCORE": {"TEAM": [{"name": "A", "PLAYER": [{"x": "y" * 1000}] * 50}]},
        "PLAYBYPLAY": {"LINES": [{"text": "z" * 100}] * 500},
        "SHOTCHART": {"SHOTS": [{"x": 1}] * 300},
    }


class TestMatchList:
    def _service(self, docs, fbcyl=False):
        from unittest.mock import MagicMock

        from src.services.match_analysis_service import MatchAnalysisService

        coll = new_mock_db()["FBCYL_X" if fbcyl else "FEB_X"]
        coll.insert_many(docs)
        db = MagicMock()
        db.connection.get_collection.return_value = coll
        return MatchAnalysisService(db, "col"), coll

    def test_feb_list_reads_only_the_header_fields_it_needs_regression(self):
        svc, coll = self._service([_feb_doc(1)])
        seen = []
        real_find = coll.find

        def spy(filter=None, projection=None, *a, **k):
            seen.append(projection)
            return real_find(filter, projection, *a, **k)

        coll.find = spy
        out = svc.get_match_list(is_fbcyl=False)
        assert seen and seen[0], "get_match_list must pass a projection"
        for heavy in ("BOXSCORE", "PLAYBYPLAY", "SHOTCHART"):
            assert heavy not in seen[0]
        assert out == [{"match_id": "g1", "date": "01-10-2026 - 18:00", "round": "1", "venue": "Pab",
                        "home_team": "A", "away_team": "B", "home_score": 80, "away_score": 70}]

    def test_fbcyl_list_projection_and_summary(self):
        doc = {"_id": "u1", "stats": {"time": "2026-10-01", "teams": [{"name": "A", "players": [{"d": "x" * 5000}]},
                                                                       {"name": "B"}],
                                      "score": [{"local": 3, "visit": 2}, {"local": 60, "visit": 50}]},
               "moves": [{"m": "x"}] * 400}
        svc, coll = self._service([doc], fbcyl=True)
        out = svc.get_match_list(is_fbcyl=True)
        assert out[0]["home_score"] == 60 and out[0]["away_team"] == "B"

    def test_projection_does_not_change_the_summary_of_real_documents(self):
        from src.live_core.vectors import unwrap_extended_json

        game = unwrap_extended_json(json.loads((ROOT / "src/JSON_samples/feb_game.json").read_text(encoding="utf-8")))
        svc, _ = self._service([{**game, "_id": "real"}])
        full = svc._summary_feb({**game, "_id": "real"})
        assert svc.get_match_list(is_fbcyl=False) == [full]


# --- 3. league zone stats without materialising every shot ---------------------------------

class TestLeagueZonesStreaming:
    def _coll(self, n_games=3):
        coll = new_mock_db()["FEB_Z"]
        shot = {"team": "0", "x": 3, "y": 50, "m": 1, "player": "4"}
        for g in range(n_games):
            coll.insert_one({"HEADER": {"TEAM": [{"id": "1"}, {"id": "2"}]}, "SHOTCHART": {"SHOTS": [shot] * 10}})
        return coll

    def test_iter_shots_feb_is_a_lazy_iterator_with_the_same_shots(self):
        from src.shotcharts.feb_zones import extract_shots_feb, iter_shots_feb

        coll = self._coll()
        it = iter_shots_feb(coll, None, None)
        assert not isinstance(it, list)
        assert list(it) == extract_shots_feb(coll, None, None)

    def test_league_zone_stats_streams_the_shots_to_the_analyzer_regression(self):
        from src.shotcharts.league_zones import league_zone_stats

        received = {}

        class Spy:
            def analyze_zone_performance(self, shots):
                received["is_list"] = isinstance(shots, list)
                n = sum(1 for _ in shots)
                return {"zone_stats": {"z": {"total": n}}}

        stats = league_zone_stats(Spy(), self._coll())
        assert received["is_list"] is False
        assert stats == {"z": {"total": 30}}

    def test_zone_analyzer_accepts_any_iterable(self):
        from src.shotcharts.zone_analysis import ZoneAnalyzer

        az = ZoneAnalyzer()
        shots = ({"x": 7.5, "y": 1.2, "made": i % 2 == 0} for i in range(10))
        result = az.analyze_zone_performance(shots)
        assert result["total_shots"] == 10
        assert sum(z["total"] for z in result["zone_stats"].values()) == 10


# --- 4. weekly-report jobs expire ----------------------------------------------------------

class TestReportJobsExpire:
    def test_stale_jobs_are_purged_and_fresh_ones_kept(self):
        from src.api.routers import reports

        reports.REPORT_JOBS.clear()
        now = time.time()
        reports.REPORT_JOBS["old"] = {"status": "done", "zip_bytes": b"x" * 10, "created_at": now - reports.JOB_TTL_S - 1}
        reports.REPORT_JOBS["new"] = {"status": "done", "zip_bytes": b"y", "created_at": now}
        reports.REPORT_JOBS["running"] = {"status": "running", "zip_bytes": None, "created_at": now - 10}
        reports.purge_expired_jobs(now)
        assert set(reports.REPORT_JOBS) == {"new", "running"}
        reports.REPORT_JOBS.clear()

    def test_starting_a_report_stamps_the_job_and_purges_old_ones(self):
        from unittest.mock import MagicMock

        from fastapi.testclient import TestClient

        from src.api.app import app
        from src.api.deps import get_db
        from src.api.routers import reports

        reports.REPORT_JOBS.clear()
        reports.REPORT_JOBS["old"] = {"status": "done", "zip_bytes": b"x", "created_at": time.time() - reports.JOB_TTL_S - 5}
        app.dependency_overrides[get_db] = lambda: MagicMock()
        try:
            from unittest.mock import patch

            with patch.object(reports, "_run_weekly_report"):
                r = TestClient(app).post("/api/v1/reports/col/weekly-report", json={"team_a": "1", "team_b": "2"})
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 200
        jid = r.json()["job_id"]
        assert "old" not in reports.REPORT_JOBS and "created_at" in reports.REPORT_JOBS[jid]
        reports.REPORT_JOBS.clear()


# --- 5. optional per-request memory log ----------------------------------------------------

class TestMemoryLog:
    def test_rss_is_a_positive_number(self):
        from src.api.memory import rss_mb

        assert rss_mb() > 10

    def test_middleware_logs_requests_that_grow_memory(self, monkeypatch, caplog):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api import memory

        values = iter([100.0, 160.0])
        monkeypatch.setattr(memory, "rss_mb", lambda: next(values))
        monkeypatch.setenv("LOG_MEMORY", "1")
        app = FastAPI()

        @app.get("/heavy")
        def heavy():
            return {"ok": True}

        memory.install(app)
        with caplog.at_level("WARNING", logger="basketlab.memory"):
            assert TestClient(app).get("/heavy").status_code == 200
        assert any("/heavy" in r.message and "+60" in r.message for r in caplog.records)

    def test_disabled_by_default(self, monkeypatch, caplog):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api import memory

        monkeypatch.delenv("LOG_MEMORY", raising=False)
        app = FastAPI()

        @app.get("/x")
        def x():
            return {}

        memory.install(app)
        with caplog.at_level("WARNING", logger="basketlab.memory"):
            TestClient(app).get("/x")
        assert not caplog.records


# --- 6. deployment config ------------------------------------------------------------------

class TestRenderConfig:
    def test_api_service_limits_memory_hungry_defaults(self):
        text = (ROOT / "render.yaml").read_text(encoding="utf-8")
        assert "MALLOC_ARENA_MAX" in text
        assert "WEB_CONCURRENCY" in text
        assert "--no-cache-dir" in text
