"""The publication of the formation index (#893, E3b): ``formation.json`` in ``talent-data`` and how the estimate of a player of the formation is rebuilt from it and from the equivalences.

Built from SYNTHETIC rows with a known world (two senior competitions of a sex with a known difference of level, careers that stay and move, and players of the formation of two groups who reach the senior game
the next season): the document must carry what the browser needs, be deterministic, say whether it can be shown (``usable``) and give, with the equivalences, the SAME estimate as the model.
"""
import json
import random
from statistics import NormalDist

import pytest

from src.market.contract import validate_talent_manifest
from src.market.equivalence import AXES, observations
from src.market.equivalence_publish import build_document as build_equivalences
from src.market.formation import formation_observations, project, fit as fit_formation, pairs
from src.market.formation_publish import build_document, estimate_from_documents

PHI = NormalDist().cdf
A, B = "F|feb|LF A", "F|feb|LF B"
LEVEL = {A: 0.0, B: -0.6}
COMPETITIONS = {
    **{f"s|{n}|{y}": {"competition": n.split("|")[2], "league": "feb", "gender": "F", "category": "senior", "season": str(y), "level": 1 if n == A else 2} for n in (A, B) for y in range(2019, 2025)},
    **{f"f|{g}|{y}": {"competition": f"CE {g}", "league": "feb", "gender": "F", "category": "formacion", "age_group": g, "season": str(y)} for g in ("U16", "U18") for y in range(2019, 2025)},
}


def pct(z):
    return {a: 100 * PHI(v) for a, v in zip(AXES, z)}


def world(seed=3, careers=700, youth=500):
    rng = random.Random(seed)
    rows = []

    def senior(person, node, season, z):
        rows.append({"comp": f"s|{node}|{season}", "person_id": person, "linked_to": None, "minutes": 900, "eligible": True, "pct": pct([v - LEVEL[node] * 0 for v in z])})

    for k in range(careers):
        node, season = rng.choice((A, B)), rng.randint(2019, 2022)
        z = [rng.gauss(0, 1) for _ in AXES]
        for s in range(season, season + 3):
            senior(f"c{k}", node, s, [v + LEVEL[node] for v in z])
            z = [0.7 * v + rng.gauss(0, 0.7) for v in z]
            if rng.random() < 0.3:
                node = B if node == A else A
    for k in range(youth):
        season, group = rng.randint(2019, 2023), rng.choice(("U16", "U18"))
        z = [rng.gauss(0, 1) for _ in AXES]
        rows.append({"comp": f"f|{group}|{season}", "person_id": f"y{k}", "linked_to": None, "minutes": 600, "eligible": True, "pct": pct(z)})
        node = rng.choice((A, B))
        senior(f"y{k}", node, season + 1, [0.6 * v + rng.gauss(0, 0.6) + LEVEL[node] for v in z])
    return rows


ROWS = world()
DOC = build_document(ROWS, COMPETITIONS)
EQ = build_equivalences(ROWS, COMPETITIONS)


class TestTheDocument:
    def test_it_carries_per_sex_the_coefficients_the_noise_and_the_groups_it_can_speak_of(self):
        part = DOC["sexes"]["F"]
        assert DOC["axes"] == list(AXES) and len(part["coef"]) == len(AXES) and all(len(c) == 3 for c in part["coef"]) and len(part["sigma"]) == len(AXES)
        assert set(DOC["groups"]) == {"U16", "U18"}

    def test_it_says_how_it_validated_and_whether_the_range_can_be_shown(self):
        v = DOC["validation"]
        assert {"n", "mae_model", "mae_mean", "coverage", "publish"} <= set(v) and DOC["usable"] == v["publish"]
        assert v["mae_model"] < v["mae_mean"]                                          # the world has a relation: it must be found

    def test_it_is_deterministic_whatever_the_order_of_the_rows(self):
        again = build_document(list(reversed(ROWS)), COMPETITIONS)
        assert json.dumps(again, sort_keys=True) == json.dumps(DOC, sort_keys=True)

    def test_without_formation_or_without_a_graph_there_is_no_document(self):
        assert build_document([r for r in ROWS if r["comp"].startswith("s|")], COMPETITIONS) is None
        assert build_document([r for r in ROWS if r["comp"].startswith("f|")], COMPETITIONS) is None
        assert build_document([], COMPETITIONS) is None


class TestTheEstimate:
    def history(self, person="y1"):
        return [o for o in formation_observations(ROWS, COMPETITIONS) if o.person == person]

    def test_it_equals_the_projection_of_the_model_plus_the_level_of_the_competition_from_the_graph(self):
        history = self.history()
        assert history
        got = estimate_from_documents(DOC, EQ, history, A)
        sen = observations(ROWS, COMPETITIONS)
        from src.market.equivalence_model import fit_observations
        graph = fit_observations(sen)
        fitted = graph.fits["F"]
        theta = [float(fitted.theta[i][fitted.nodes.index(A)]) for i in range(len(AXES))]
        model = fit_formation(pairs(formation_observations(ROWS, COMPETITIONS), sen, lambda n: tuple(float(fitted.theta[i][fitted.nodes.index(n)]) for i in range(len(AXES))) if n in fitted.nodes else None))
        want = project(model, "F", history[-1].z, history[-1].group, theta)
        for g, w in zip(got, want):
            for key in ("mean", "lo", "hi"):
                assert g[key] == pytest.approx(w[key], abs=3e-3)

    def test_a_better_competition_to_play_in_means_a_higher_expected_z_by_the_difference_of_level(self):
        history = self.history()
        high, low = estimate_from_documents(DOC, EQ, history, A), estimate_from_documents(DOC, EQ, history, B)
        assert sum(h["mean"] - l_["mean"] for h, l_ in zip(high, low)) / len(AXES) == pytest.approx(0.6, abs=0.25)

    def test_no_formation_a_group_it_does_not_know_or_a_competition_outside_the_graph_gives_nothing(self):
        assert estimate_from_documents(DOC, EQ, [], A) is None
        assert estimate_from_documents(DOC, EQ, self.history(), "F|feb|NO SUCH LEVEL") is None
        assert estimate_from_documents(DOC, EQ, [type(self.history()[0])("x", 2022, "U12", "F", 600, (0.0,) * len(AXES))], A) is None


class TestTheContract:
    def test_the_manifest_may_carry_the_formation_entry_and_checks_its_shape(self):
        entry = {"file": "players/formation.abc.json", "bytes": 10, "sha256": "ab", "wraps": [], "usable": True, "sexes": ["F"]}
        manifest = {"schema": 1, "kind": "talent", "v": 1, "competitions": []}
        validate_talent_manifest({**manifest, "formation": entry})
        with pytest.raises(Exception):
            validate_talent_manifest({**manifest, "formation": {**entry, "usable": "yes"}})

    def test_the_generated_typescript_knows_the_entry(self):
        from src.market.contract import render_typescript
        assert "TalentFormationEntry" in render_typescript()


class TestThePublication:
    def publish(self, out, rows):
        from src.live_prep.package_sealing import ScopedSealer
        from src.market.publish import _formation
        rows_by_key = {}
        for r in rows:
            rows_by_key.setdefault(r["comp"], []).append(r)
        return _formation(out, ScopedSealer("k" * 32, open_access=True), None, rows_by_key, [{**v, "key": k} for k, v in COMPETITIONS.items()])

    def test_the_entry_is_sealed_and_says_if_it_is_usable(self, tmp_path):
        entry = self.publish(tmp_path, ROWS)
        assert entry["usable"] == DOC["usable"] and entry["sexes"] == ["F"] and (tmp_path / entry["file"]).exists()

    def test_without_formation_there_is_no_entry(self, tmp_path):
        assert self.publish(tmp_path, [r for r in ROWS if r["comp"].startswith("s|")]) is None
