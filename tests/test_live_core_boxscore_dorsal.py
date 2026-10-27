"""The jersey number of a player in the box score tab (issue #597): «#5 A. PRIMERA».

Two sources, in this order: the ``no`` of the document's box score (the FBCYL adapter writes it; the FEB feed of a live match does NOT have it, its roster entries are
``{id, name}``) and the ``dorsal`` of the package's roster (FEB's current roster, ``tables.roster``). A number is text: «04» and «0» are numbers.
"""
import copy
import gzip
import json
from pathlib import Path

import pytest

from src.live_core.boxscore import build
from src.live_core.config import RuleConfig
from src.live_core.engine import LiveEngine
from tests.builders import OWN, Match, engine

ROOT = Path(__file__).parent.parent
CFG = RuleConfig()


@pytest.fixture(scope="module")
def feb_doc():
    return json.loads((ROOT / "src" / "JSON_samples" / "feb_game.json").read_text(encoding="utf-8"))


class TestFromTheDocument:
    def test_a_feb_player_has_the_number_of_the_box_score_as_text(self, feb_doc):
        snap = LiveEngine().update(feb_doc)
        boxed = {p["id"]: p["no"] for team in feb_doc["BOXSCORE"]["TEAM"] for p in team["PLAYER"] if p.get("no") is not None}
        assert boxed and all(snap["players"][pid]["no"] == no for pid, no in boxed.items() if pid in snap["players"])
        assert snap["players"]["2361369"]["no"] == "04"                            # the zero of «04» is not lost

    def test_a_player_the_box_score_does_not_number_has_none(self, feb_doc):
        doc = copy.deepcopy(feb_doc)
        for team in doc["BOXSCORE"]["TEAM"]:
            for p in team["PLAYER"]:
                p.pop("no", None)
        assert all(p["no"] is None for p in LiveEngine().update(doc)["players"].values())

    def test_a_player_who_only_shows_up_in_the_play_by_play_has_none(self, feb_doc):
        doc = copy.deepcopy(feb_doc)
        doc["BOXSCORE"]["TEAM"][0]["PLAYER"] = [p for p in doc["BOXSCORE"]["TEAM"][0]["PLAYER"] if p["id"] != "2817524"]
        assert LiveEngine().update(doc)["players"]["2817524"]["no"] is None

    def test_a_fbcyl_player_has_his_dorsal_through_the_adapter(self):
        from src.live_prep.fbcyl_adapter import to_feb_document
        raw = json.loads(gzip.open(ROOT / "tests" / "fixtures" / "fbcyl_game_ok.json.gz").read())
        played = [p for p in LiveEngine().update(to_feb_document(raw))["players"].values() if p["minutes"] > 0]
        assert len(played) >= 10 and all(p["no"] for p in played)


class TestFromTheRoster:
    def entry(self, snap, roster, pid="p1"):
        return build(snap, {}, CFG, roster)[pid]

    def snapshot(self):
        return Match().lineup(OWN, ["p1"], at=0).score(OWN, 2, at=30, player="p1").snapshot()

    def test_the_dorsal_of_the_roster_is_the_number_when_the_document_has_none(self):
        assert self.entry(self.snapshot(), {"p1": {"dorsal": 7}})["no"] == "7"

    def test_the_number_of_the_document_wins_over_the_roster(self):
        snap = self.snapshot()
        snap["players"]["p1"]["no"] = "04"
        assert self.entry(snap, {"p1": {"dorsal": 7}})["no"] == "04"

    @pytest.mark.parametrize("dorsal", [0, "0", "00"])
    def test_zero_is_a_number(self, dorsal):
        assert self.entry(self.snapshot(), {"p1": {"dorsal": dorsal}})["no"] == str(dorsal)

    @pytest.mark.parametrize("roster", [{}, {"p1": {}}, {"p1": {"dorsal": None}}, {"p1": {"dorsal": ""}}, None])
    def test_without_a_dorsal_there_is_no_number(self, roster):
        assert self.entry(self.snapshot(), roster)["no"] is None

    def test_the_engine_hands_the_roster_over(self):
        box = engine(roster={"p1": {"dorsal": 9}}).analyze(self.snapshot())["boxscore"]
        assert box["p1"]["no"] == "9"
