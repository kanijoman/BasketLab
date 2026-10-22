"""``rule_config`` per competition in the packages (issue #439, epic #435).

``PreparationPackage.rule_config`` existed and the engine reads it (``AdviceEngine.from_package``), but the builder never filled it. The
catalog of ``config/package_publish.json`` can now give each competition its own overrides (a rule off, a threshold, the formation rule), which
travel in every package of that competition. The spike on 2ª/3ª FEB (#436) found the FIBA rules of the clock and the timeouts unchanged, so
nothing else is parametrised; the formation rule stays on everywhere unless a competition says otherwise.
"""
import json
from unittest.mock import MagicMock

import pytest

from src.live_core.advice import AdviceEngine
from src.live_prep.competition_info import competition_infos, normalize_catalog, public
from src.live_prep.package_builder import SeasonAccumulator, build_package
from src.live_prep.publisher import load_config, publish_all, publish_round_bundles
from src.live_prep.round_packages import build_round_packages
from tests.test_package_publisher import OWN, PASSWORD, R1, _match, _round, _round_service, _schedule

A, B = "982047", "981204"
RULES = {"rules_off": ["formation_lineup"], "formation_min_on_court": 1}


class TestBuilder:
    def test_the_package_carries_the_rule_config_it_is_given(self, feb_game_doc):
        package = build_package([feb_game_doc], "C", "2026", A, B, rule_config=RULES)
        assert package.rule_config == RULES

    def test_without_rule_config_the_package_is_what_it_was(self, feb_game_doc):
        assert build_package([feb_game_doc], "C", "2026", A, B).rule_config == {}

    def test_the_engine_of_the_package_applies_it(self, feb_game_doc):
        package = build_package([feb_game_doc], "C", "2026", A, B, rule_config=RULES)
        from src.live_core.config import RuleConfig

        assert AdviceEngine.from_package(package) is not None
        config = RuleConfig.from_dict(package.rule_config)
        assert config.rules_off == ("formation_lineup",) and config.formation_min_on_court == 1

    def test_a_round_bundle_carries_the_rule_config_in_every_package(self, feb_game_doc):
        match = {"code": "1", "start": "2026-10-21T20:00", "round": 1, "home": {"id": A, "name": "A"}, "away": {"id": B, "name": "B"}}
        built = build_round_packages([feb_game_doc], "C", "2026", [match], rule_config=RULES)
        assert len(built) == 2 and all(b["package"].rule_config == RULES for b in built)

    def test_the_rule_config_is_not_shared_between_packages(self, feb_game_doc):
        acc = SeasonAccumulator(track=[A, B])
        acc.add_game(feb_game_doc)
        first = acc.to_package("C", "2026", A, B, None, None, rule_config=RULES)
        first.rule_config["rules_off"].append("x")
        assert acc.to_package("C", "2026", A, B, None, None, rule_config=RULES).rule_config == RULES


class TestCatalog:
    def test_an_entry_may_carry_a_rule_config(self):
        entry = normalize_catalog([{"competition": "LIGA U", "rule_config": RULES}])[0]
        assert entry["rule_config"] == RULES

    @pytest.mark.parametrize("bad", [{"rules_off": ["no_such_rule"]}, {"no_such_field": 1}, ["rules_off"], {"rules_off": "formation_lineup"}])
    def test_a_typo_or_a_wrong_shape_is_rejected_when_the_config_is_read(self, bad):
        with pytest.raises(ValueError, match="rule_config"):
            normalize_catalog([{"competition": "X", "rule_config": bad}])

    def test_a_competition_gives_its_collections_the_rule_config(self):
        from tests.test_publisher_competitions import META, SEGUNDA, _db

        catalog = normalize_catalog([{"competition": "SEGUNDA FEB", "rule_config": RULES}])
        info = competition_infos(_db(META), [SEGUNDA], catalog, ["1"])[SEGUNDA]
        assert info["rule_config"] == RULES and "rule_config" not in public(info)

    def test_without_it_the_info_has_an_empty_one(self):
        from tests.test_publisher_competitions import META, SEGUNDA, _db

        assert competition_infos(_db(META), [SEGUNDA], normalize_catalog([]), ["1"])[SEGUNDA]["rule_config"] == {}

    def test_the_repository_config_keeps_the_formation_rule_everywhere(self):
        """The decision of the plan: the rule applies in every competition unless it says otherwise (and none does yet)."""
        for entry in load_config()["competitions"]:
            assert "formation_lineup" not in (entry.get("rule_config") or {}).get("rules_off", []), entry["competition"]

    def test_liga_u_is_a_male_league_without_level(self):
        liga_u = next(c for c in load_config()["competitions"] if c["competition"] == "LIGA U")
        assert (liga_u["gender"], liga_u["level"]) == ("M", None)


class TestPublisher:
    INFO = {"key": "COL", "label": "X", "competition": "X", "group": "", "season": "s", "level": None, "gender": "M", "clubs": [OWN],
            "rule_config": RULES}

    def test_the_packages_of_a_competition_are_built_with_its_rule_config(self, tmp_path):
        seen = []

        def build(db, collection, team_id, rival_id, season=None, competition_meta=None, progress=None, rule_config=None):
            seen.append(rule_config)
            package = MagicMock()
            package.dumps.return_value = json.dumps({"x": 1})
            return package

        publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=_schedule([_match("10", R1, "2026-10-10T17:00")]), build=build,
                    competitions={"COL": self.INFO})
        assert seen == [RULES]

    def test_a_competition_without_rule_config_is_built_exactly_as_before(self, tmp_path):
        """The builder is not even given the argument: a builder that predates it still works."""
        def build(db, collection, team_id, rival_id, season=None, competition_meta=None, progress=None):
            package = MagicMock()
            package.dumps.return_value = json.dumps({"x": 1})
            return package

        info = {**self.INFO, "rule_config": {}}
        assert publish_all(object(), tmp_path, PASSWORD, ["COL"], OWN, service=_schedule([_match("10", R1, "2026-10-10T17:00")]), build=build,
                           competitions={"COL": info})

    def test_the_bundles_of_a_competition_are_built_with_its_rule_config(self, tmp_path):
        seen = []

        def build(db, collection, matches, club_team_id=None, roster_source=None, season=None, rule_config=None):
            seen.append(rule_config)
            return []

        publish_round_bundles(object(), tmp_path, PASSWORD, ["COL"], OWN, service=_round_service({"COL": _round(4, (OWN, R1))}), build=build,
                              competitions={"COL": self.INFO})
        assert seen == [RULES]


class TestRulesByPhase:
    """The formation rule depends on the PHASE of a competition (issue #481): Copa de España applies 2ª FEB's criterion (at least 2 players of
    formación on court) in the group stage and 1ª FEB's (no limit) in the knockout phases; Primera FEB has no limit either."""

    CATALOG = [{"competition": "COPA ESPAÑA", "rule_config": {"formation_min_on_court": 0},
                "group_rules": [{"group": "FASE DE GRUPOS", "rule_config": {"formation_min_on_court": 2}}]}]

    def info(self, group):
        from tests.test_publisher_competitions import _db

        meta = {"_id": "C", "competition_label": "COPA ESPAÑA", "season_label": "2026/2027", "group_label": group}
        return competition_infos(_db(meta), ["C"], normalize_catalog(self.CATALOG), ["1"])["C"]

    def test_a_group_that_matches_takes_its_own_rules_over_the_competition_ones(self):
        assert self.info('FASE DE GRUPOS "A"')["rule_config"] == {"formation_min_on_court": 2}

    def test_the_other_groups_keep_the_rules_of_the_competition(self):
        assert self.info("Play-offs 1/16 Final")["rule_config"] == {"formation_min_on_court": 0}
        assert self.info("Play-offs 1/8 Final")["rule_config"] == {"formation_min_on_court": 0}     # a round that is not drawn yet

    def test_the_group_is_matched_ignoring_case_and_accents(self):
        assert self.info("fase de grupos B")["rule_config"] == {"formation_min_on_court": 2}

    def test_the_rules_of_a_group_add_to_the_ones_of_the_competition(self):
        catalog = normalize_catalog([{"competition": "X", "rule_config": {"rules_off": ["fatigue_high"]},
                                      "group_rules": [{"group": "A", "rule_config": {"formation_min_on_court": 0}}]}])
        from tests.test_publisher_competitions import _db

        meta = {"_id": "C", "competition_label": "X", "group_label": "A"}
        assert competition_infos(_db(meta), ["C"], catalog, ["1"])["C"]["rule_config"] == {"rules_off": ["fatigue_high"], "formation_min_on_court": 0}

    @pytest.mark.parametrize("bad", [{"group": "", "rule_config": {}}, {"rule_config": {}}, {"group": "A", "rule_config": {"no_such_field": 1}},
                                     {"group": "A"}, "A"])
    def test_a_wrong_group_rule_is_rejected_when_the_config_is_read(self, bad):
        with pytest.raises(ValueError, match="group_rules"):
            normalize_catalog([{"competition": "X", "group_rules": [bad]}])

    def test_the_repository_applies_the_phase_criteria_of_the_copa_and_of_primera_feb(self):
        catalog = {c["competition"]: c for c in load_config()["competitions"]}
        copa = catalog["COPA ESPAÑA"]
        assert copa["rule_config"].get("formation_min_on_court") == 0
        assert [(g["group"], g["rule_config"]["formation_min_on_court"]) for g in copa["group_rules"]] == [("FASE DE GRUPOS", 2)]
        assert catalog["PRIMERA FEB"]["rule_config"]["formation_min_on_court"] == 0
        assert "formation_min_on_court" not in catalog["SEGUNDA FEB"].get("rule_config", {})      # 2ª FEB: the default, 2
