"""The publication of the equivalence graph (#891, E1c of epic #872): ``equivalences.json`` in ``talent-data``.

The document carries what a browser needs to answer ONE estimate per player (``equivalence_model.estimate``): per sex the levels of the competitions, their covariance, the noise, the reliability of one season
and of two, the edges that exist and a validation block with the `usable` flag. The tests build it from the REAL sample of rows (``talent_rows_movers.json.gz``) and check that the estimate rebuilt from the
document equals the one of the model (that is what the port to the browser will be compared with), that it is deterministic, and that the contract and the manifest carry it.
"""
import gzip
import json
from pathlib import Path

import pytest

from src.market.contract import validate_talent_manifest
from src.market.equivalence import AXES, observations
from src.market.equivalence_model import estimate, fit_observations
from src.market.equivalence_publish import build_document, estimate_from_document

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "talent_rows_movers.json.gz"
DATA = json.loads(gzip.decompress(FIXTURE.read_bytes()).decode("utf-8"))
ROWS, COMPETITIONS = DATA["rows"], DATA["competitions"]
OBS = observations(ROWS, COMPETITIONS)
MODEL = fit_observations(OBS)
DOC = build_document(ROWS, COMPETITIONS)


class TestTheDocument:
    def test_it_says_the_axes_and_per_sex_everything_the_estimate_needs(self):
        assert DOC["axes"] == list(AXES)
        for sex, part in DOC["sexes"].items():
            n = len(part["nodes"])
            assert len(part["component"]) == n and len(part["rho"]) == len(AXES) and len(part["sigma"]) == len(AXES)
            assert len(part["theta"]) == len(AXES) and all(len(row) == n for row in part["theta"])
            assert all(len(m) == n and all(len(r) == n for r in m) for m in part["cov"])

    def test_the_reliability_of_two_seasons_is_there_when_the_model_has_it(self):
        for sex, part in DOC["sexes"].items():
            assert (part.get("two") is not None) == (sex in MODEL.history)

    def test_the_edges_are_only_the_ones_with_enough_persons(self):
        from src.market.equivalence_model import MIN_PERSONS
        assert DOC["edges"] and all(e["persons"] >= MIN_PERSONS for e in DOC["edges"])

    def test_it_carries_its_validation_and_whether_the_range_can_be_shown(self):
        v = DOC["validation"]
        assert isinstance(DOC["usable"], bool) and {"n", "mae_model", "mae_identity", "coverage"} <= set(v)
        assert DOC["usable"] == (v["publish"] is True)

    def test_it_is_deterministic_to_the_byte(self):
        again = build_document(list(reversed(ROWS)), COMPETITIONS)
        assert json.dumps(again, sort_keys=True) == json.dumps(DOC, sort_keys=True)

    def test_no_rows_means_no_document_not_an_empty_one(self):
        assert build_document([], COMPETITIONS) is None


class TestTheEstimateOfTheDocument:
    def _cases(self):
        """Every person with observations in a node of the graph, against every other node of his sex."""
        by_person = {}
        for o in OBS:
            by_person.setdefault(o.person, []).append(o)
        nodes = {n for part in DOC["sexes"].values() for n in part["nodes"]}
        for person, history in list(by_person.items())[:150]:
            for to in sorted(nodes):
                yield history, to

    def test_the_estimate_rebuilt_from_the_document_equals_the_one_of_the_model_regression(self):
        compared = 0
        for history, to in self._cases():
            want, got = estimate(MODEL, history, to), estimate_from_document(DOC, history, to)
            assert (want is None) == (got is None)
            if want is None:
                continue
            compared += 1
            assert got[0]["seasons"] == want[0]["seasons"]
            for a, b in zip(want, got):
                for key in ("mean", "lo", "hi"):
                    assert b[key] == pytest.approx(a[key], abs=2e-3)
        assert compared > 100

    def test_without_history_or_connection_there_is_no_estimate(self):
        assert estimate_from_document(DOC, [], "F|feb|LF CHALLENGE") is None
        assert estimate_from_document(DOC, OBS[:1], "F|feb|NO SUCH LEVEL") is None


class TestTheContract:
    def _manifest(self, **extra):
        return {"schema": 1, "kind": "talent", "v": 1, "competitions": [], **extra}

    def test_the_manifest_may_carry_the_equivalences_entry_and_checks_its_shape(self):
        entry = {"file": "players/equivalences.abc.json", "bytes": 10, "sha256": "ab", "wraps": [], "usable": True, "sexes": ["F", "M"]}
        validate_talent_manifest(self._manifest(equivalences=entry))
        validate_talent_manifest(self._manifest())
        with pytest.raises(Exception):
            validate_talent_manifest(self._manifest(equivalences={**entry, "usable": "yes"}))

    def test_the_generated_typescript_knows_the_entry(self):
        from src.market.contract import render_typescript
        assert "TalentEquivalencesEntry" in render_typescript()


class TestThePublication:
    """``publish._equivalences``: the file is sealed like the rest, the manifest says whether it is usable, a second run keeps the bytes and without a graph there is no entry."""

    def _rows_by_key(self):
        out = {}
        for row in ROWS:
            out.setdefault(row["comp"], []).append(row)
        return out

    def _publish(self, out, rows_by_key=None):
        from src.live_prep.package_sealing import ScopedSealer
        from src.market.publish import _equivalences
        entries = [{**v, "key": k} for k, v in COMPETITIONS.items()]
        return _equivalences(out, ScopedSealer("k" * 32, open_access=True), None, self._rows_by_key() if rows_by_key is None else rows_by_key, entries)

    def test_the_entry_is_sealed_says_if_it_is_usable_and_opens_to_the_document(self, tmp_path):
        from src.live_prep.package_scopes import open_sealed
        entry = self._publish(tmp_path)
        assert entry["usable"] == DOC["usable"] and entry["sexes"] == sorted(DOC["sexes"]) and {w["scope"] for w in entry["wraps"]} >= {"abierto", "talent"}
        envelope = json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))
        from src.live_prep.package_scopes import scope_key
        assert json.loads(open_sealed(envelope, entry["wraps"], {"talent": scope_key("k" * 32, "talent")}))["usable"] == DOC["usable"]

    def test_a_second_run_gives_the_same_file_name(self, tmp_path):
        assert self._publish(tmp_path)["file"] == self._publish(tmp_path / "again")["file"]

    def test_without_a_graph_there_is_no_entry(self, tmp_path):
        assert self._publish(tmp_path, {}) is None
