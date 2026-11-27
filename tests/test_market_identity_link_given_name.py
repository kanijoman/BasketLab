"""The birth link needs the given name too (#1126): two sisters share the surnames and, if one is not in the FEB rosters, the birth of the other."""
import pytest

from src.market.identity_link import link_players

BIRTH = "2008-05-05"


def _link(fiba_name, feb_name, **player):
    row = {"person_id": "feb:1", "name": feb_name, "birth": BIRTH}
    found = link_players([row], [{"id": "fiba:1", "name": fiba_name, "birth": BIRTH, **player}])
    return found[0] if found else None


def test_a_twin_with_another_given_name_goes_to_review_with_the_reason_regression():
    """FIBA «Ana Garcia Lopez» was linked to FEB «MARIA GARCIA LOPEZ» by the same birth and the two surnames."""
    link = _link("Ana Garcia Lopez", "MARIA GARCIA LOPEZ")

    assert link["status"] == "review" and link["feb"] is None
    assert link["candidates"][0]["feb"] == "feb:1" and link["candidates"][0]["reason"] == "given_name"


@pytest.mark.parametrize("fiba_name, feb_name", [
    ("Maria Garcia Lopez", "MARIA GARCIA LOPEZ"),          # the same name
    ("M. Garcia Lopez", "MARIA GARCIA LOPEZ"),             # initial
    ("Ana Maria Garcia Lopez", "MARIA GARCIA LOPEZ"),      # a compound given name: one of its words
])
def test_the_same_given_name_or_its_initial_keeps_the_link(fiba_name, feb_name):
    assert _link(fiba_name, feb_name)["status"] == "linked"


def test_the_papers_name_of_the_player_can_supply_the_given_name():
    """ACB shows «Edy Tavares» and the page of the player says «Walter Tavares», the name FEB writes (#886)."""
    link = _link("Edy Tavares", "WALTER TAVARES", full_name="Walter Tavares")

    assert link["status"] == "linked"
