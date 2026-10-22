"""The post-match report of a demo or a recording, with the gender of its competition (issues #477, #475).

The PDF button was only for live matches that ended and were kept on the device. A demo is a recording (``recorded_feed``): the report is built from its last document,
and the package's ``rule_config`` (its gender) goes in so the PDF says «Jugadoras» or «Jugadores».
"""
import gzip
import json
from pathlib import Path

from src.live_core.session import report_json

RECORDINGS = Path(__file__).parent / "recordings"
PACK = gzip.decompress((RECORDINGS / "2536133.rec.json.gz").read_bytes()).decode("utf-8")
OWN = "1008857"


def test_a_recording_pack_gives_the_report_of_its_final_document():
    report = json.loads(report_json(PACK, None, OWN))
    assert report["match"]["own"]["id"] == OWN and report["match"]["score"]["own"] + report["match"]["score"]["rival"] > 80
    assert report["players"] and report["periods" if "periods" in report else "match"]


def test_a_final_document_still_works_as_before(feb_game_doc):
    own = str(feb_game_doc["HEADER"]["TEAM"][0]["id"])
    assert json.loads(report_json(json.dumps(feb_game_doc), None, own))["match"]["own"]["id"] == own


def test_the_gender_of_the_package_goes_into_the_report():
    assert json.loads(report_json(PACK, None, OWN, json.dumps({"gender": "F"})))["gender"] == "F"
    assert json.loads(report_json(PACK, None, OWN, json.dumps({"gender": "M"})))["gender"] == "M"
    assert json.loads(report_json(PACK, None, OWN))["gender"] == ""


def test_a_recording_that_is_not_one_of_the_formats_is_an_error_not_a_crash():
    import pytest

    with pytest.raises(Exception):
        report_json(json.dumps({"hello": "world"}), None, OWN)
