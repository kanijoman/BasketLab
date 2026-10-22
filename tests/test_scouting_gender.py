"""The words of the scouting report agree with the gender of the competition (issue #495, as #475 did for the alerts of the engine).

The gender comes from the catalog of the publisher (``F`` / ``M``); in doubt (a competition not in the catalog) the neutral masculine, as the lexicon of the engine.
"""
import pytest

from src.live_prep.scouting_report import ALERTS, build_scouting_report
from src.services.scouting_pdf import render_scouting_pdf
from src.services.scouting_rival_service import ScoutingRivalService
from tests.test_scouting_report import collected
from tests.test_scouting_rival_service import COLLECTION, A, FakeReport, FakeStats, docs, db  # noqa: F401 - fixtures


def alert_data(*ids):
    return collected(alerts=[{"id": i, "category": "x", "count": 6, "games": 4, "per_game": 1.5, "avg_minute": 20.0, "severity": "warning", "message": "m"} for i in ids])


def labels(report):
    return " | ".join(a["label"] for a in report["alerts"])


FEMININE_IDS = ["fatigue_high", "foul_trouble", "own_cold_player", "own_hot_player", "player_plus_minus", "rest_starters", "formation_lineup"]


def test_the_labels_of_a_female_competition_stay_in_the_feminine():
    text = labels(build_scouting_report(alert_data(*FEMININE_IDS), gender="F"))
    assert "Fatiga de sus jugadoras" in text and "Descanso de las titulares" in text and "jugadoras de formación" in text


def test_the_labels_of_a_male_competition_use_the_masculine_regression():
    """Found with the Copa (22/10/2026): a male competition said «Fatiga de sus jugadoras»."""
    text = labels(build_scouting_report(alert_data(*FEMININE_IDS), gender="M"))
    assert "jugadora" not in text.lower() and "titulares" in text and "las titulares" not in text
    assert "Fatiga de sus jugadores" in text and "Descanso de los titulares" in text


def test_without_a_gender_it_is_the_masculine():
    assert "jugadora" not in labels(build_scouting_report(alert_data(*FEMININE_IDS))).lower()


def test_every_label_formats_in_both_genders():
    from types import SimpleNamespace
    from src.live_prep.scouting_report import alert_label
    for key in ALERTS:
        for g in ("F", "M", ""):
            assert "{" not in alert_label(key, SimpleNamespace(gender=g))


def test_the_text_about_the_top_scorer_agrees_with_the_gender():
    male = " ".join(k["text"] for k in build_scouting_report(collected(), gender="M")["keys"])
    female = " ".join(k["text"] for k in build_scouting_report(collected(), gender="F")["keys"])
    assert "Limitarlo" in male and "Limitarla" not in male
    assert "Limitarla" in female


def test_the_report_says_its_gender_and_the_pdf_titles_follow_it():
    male = render_scouting_pdf(build_scouting_report(collected(), gender="M"), compress=False)
    female = render_scouting_pdf(build_scouting_report(collected(), gender="F"), compress=False)
    assert b"Jugadores clave" in male and b"Jugadoras clave" not in male and b"[Jugadores]" in male
    assert b"Jugadoras clave" in female
    assert build_scouting_report(collected(), gender="M")["gender"] == "M"


@pytest.mark.parametrize("gender", ["F", "M"])
def test_the_service_takes_the_gender_of_the_competition(db, docs, gender):  # noqa: F811
    service = ScoutingRivalService(db, stats=FakeStats(), report_service=FakeReport(), games=lambda handler, collection: iter(docs), gender_of=lambda collection: gender)
    assert service.build(COLLECTION, A)["gender"] == gender


def test_a_failing_gender_lookup_does_not_stop_the_report(db, docs):  # noqa: F811
    def broken(collection):
        raise RuntimeError("no catalog")
    service = ScoutingRivalService(db, stats=FakeStats(), report_service=FakeReport(), games=lambda handler, collection: iter(docs), gender_of=broken)
    assert service.build(COLLECTION, A)["gender"] == ""
