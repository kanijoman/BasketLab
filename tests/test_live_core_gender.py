"""The text of the alerts follows the gender of the competition (issue #475, feedback of 0.3.2).

The alerts said «jugadora» in men's competitions too (2ª FEB, 3ª FEB, Copa...). The package carries the gender of its competition
(``rule_config.gender``: ``F`` or ``M``; the catalog of the publisher has it) and the words are chosen from it: «jugadora» only when it is ``F``;
in doubt (nothing said) the neutral, masculine.
"""
import json
from pathlib import Path

import pytest

from src.live_core.advice import AdviceEngine
from src.live_core.config import RuleConfig
from src.live_core.lexicon import jugador, jugadores, pronoun, object_pronoun
from src.live_core.package import PreparationPackage
from src.live_core.rules_lineup import departure_note
from src.live_core.session import LiveSession
from tests.test_live_core_advice import OWN, RIVAL
from tests.test_live_core_players import RIVAL_TABLE, by_id, evaluate, player

RECORDINGS = Path(__file__).parent / "recordings"


class TestLexicon:
    def test_feminine_only_when_the_competition_says_so(self):
        assert jugador(RuleConfig(gender="F")) == "jugadora" and jugadores(RuleConfig(gender="F")) == "jugadoras"
        assert jugador(RuleConfig(gender="M")) == "jugador" and jugadores(RuleConfig(gender="M")) == "jugadores"

    def test_in_doubt_it_is_the_neutral_masculine(self):
        for config in (RuleConfig(), RuleConfig(gender=""), RuleConfig(gender="X"), RuleConfig(gender=None)):
            assert jugador(config) == "jugador"

    def test_the_pronouns_agree(self):
        assert (pronoun(RuleConfig(gender="F")), object_pronoun(RuleConfig(gender="F"))) == ("ella", "la")
        assert (pronoun(RuleConfig()), object_pronoun(RuleConfig())) == ("él", "lo")

    def test_a_package_without_gender_loads_with_the_neutral(self):
        assert RuleConfig.from_dict({"rules_off": []}).gender == "" and RuleConfig.from_dict({"gender": "F"}).gender == "F"


class TestAlerts:
    def engine(self, gender):
        return AdviceEngine(own_team_id=OWN, rival_team_id=RIVAL, rival_baselines=RIVAL_TABLE, config=RuleConfig(gender=gender))

    def key_player_out(self, gender):
        eng = self.engine(gender)
        evaluate({"r1": player("Rita", RIVAL), "r2": player("Rosa", RIVAL)}, elapsed=300, eng=eng)
        return by_id(evaluate({"r1": player("Rita", RIVAL, on_court=False), "r2": player("Rosa", RIVAL)}, elapsed=330, eng=eng), "rival_star_out")[0]

    def test_the_key_player_of_the_rival_is_a_jugadora_only_in_women_competitions(self):
        assert "su jugadora clave" in self.key_player_out("F").message
        assert "su jugador clave" in self.key_player_out("M").message and "su jugador clave" in self.key_player_out("").message

    def test_the_return_with_fouls_agrees_with_the_gender(self):
        for gender, who, obj in (("F", "jugadora", "atacarla"), ("M", "jugador", "atacarlo"), ("", "jugador", "atacarlo")):
            eng = self.engine(gender)
            evaluate({"r1": player("Rita", RIVAL, on_court=False, pf=4), "r2": player("Rosa", RIVAL)}, elapsed=300, eng=eng)
            [alert] = by_id(evaluate({"r1": player("Rita", RIVAL, pf=4), "r2": player("Rosa", RIVAL)}, elapsed=330, eng=eng), "rival_star_back")
            assert f"su {who} clave" in alert.message and obj in alert.message

    def test_the_formation_note_says_without_her_or_him(self):
        snap = {"players": {"a": {"name": "Ana", "team_id": OWN, "on_court": True}}}
        roster = {"a": {"team_id": OWN, "formacion": True}, "b": {"team_id": OWN, "formacion": True}}
        for gender, text in (("F", "sin ella"), ("M", "sin él"), ("", "sin él")):
            note = departure_note({**snap, "players": {**snap["players"], "b": {"name": "Bea", "team_id": OWN, "on_court": True}}}, OWN, roster, RuleConfig(gender=gender, formation_min_on_court=2), "a")
            assert note and text in note


class TestPackages:
    def test_the_publisher_gives_each_competition_its_gender(self):
        from db_helpers import new_mock_db
        from unittest.mock import MagicMock

        from src.live_prep.competition_info import competition_infos, normalize_catalog

        metas = new_mock_db()["COLLECTION_META"]
        metas.insert_one({"_id": "S", "competition_label": "SEGUNDA FEB", "group_label": "A"})
        metas.insert_one({"_id": "L", "competition_label": "LF CHALLENGE", "group_label": "U"})
        metas.insert_one({"_id": "X", "competition_label": "LIGA NUEVA", "group_label": "U"})
        db = MagicMock()
        db.repository.connection.get_collection.return_value = metas
        catalog = normalize_catalog([{"competition": "SEGUNDA FEB", "gender": "M"}, {"competition": "LF CHALLENGE", "gender": "F"}, {"competition": "LIGA NUEVA"}])
        info = competition_infos(db, ["S", "L", "X"], catalog, ["1"])
        assert info["S"]["rule_config"]["gender"] == "M" and info["L"]["rule_config"]["gender"] == "F" and "gender" not in info["X"]["rule_config"]

    def test_the_repository_catalog_has_the_gender_of_every_competition_but_the_unknown(self):
        from src.live_prep.publisher import load_config

        genders = {c["competition"]: c["gender"] for c in load_config()["competitions"]}
        assert genders["SEGUNDA FEB"] == "M" and genders["LF CHALLENGE"] == "F" and genders["LIGA U"] == "M" and genders["COPA ESPAÑA"] == "M"

    def test_the_old_women_demo_keeps_the_feminine(self):
        package = PreparationPackage.loads((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
        assert package.rule_config.get("gender") == "F"

    def test_the_fbcyl_demo_of_a_women_league_keeps_the_feminine(self):
        package = PreparationPackage.loads((RECORDINGS / "264803.package.json").read_text(encoding="utf-8"))
        assert package.rule_config.get("gender") == "F"

    def test_a_men_demo_has_no_feminine_word_in_any_alert(self):
        """Cultural - Melilla (2ª FEB, men): the whole replay says nothing in the feminine."""
        code = "2536133"
        session = LiveSession((RECORDINGS / f"{code}.package.json").read_text(encoding="utf-8"))
        session.load_recording((RECORDINGS / f"{code}.rec.json.gz").read_bytes())
        text = ""
        for t in range(0, 7200, 10):
            out = session.play(t)["output"]
            if out:
                text += json.dumps(out["alerts"], ensure_ascii=False).lower()
        assert text and not any(word in text for word in ("jugadora", "atacarla", "sin ella"))


class TestReport:
    def test_the_post_match_report_says_the_gender(self, feb_game_doc):
        from src.live_core.postmatch import build_report

        own = str(feb_game_doc["HEADER"]["TEAM"][0]["id"])
        assert build_report(feb_game_doc, own, config=RuleConfig(gender="F"))["gender"] == "F"
        assert build_report(feb_game_doc, own)["gender"] == ""
