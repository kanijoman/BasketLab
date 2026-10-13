"""The FEB team roster (issue #271): who is a "formación" player, from baloncestoenvivo.feb.es/equipo/<id>.

The page has a table with Nombre, Puesto, Dorsal, Nacimiento, Nacionalidad, Formación (SI/NO), Altura and Peso; each
player links to ``Jugador.aspx?i=<team>&c=<player>`` and that code is the ``idPlayer`` of the play-by-play. The HTML
here is synthetic (same structure, invented players): the real roster has minors and does not belong in a public repo.
"""
from html import escape

import pytest

from src.live_prep.roster_fetcher import ROSTER_URL, fetch_rosters, fetch_team_roster, parse_roster

TEAM = "1008631"

# (class of the column, header text)
COLUMNS = [("nombre jugador", "Nombre"), ("puesto", "Puesto"), ("dorsal", "Dorsal"), ("fecha nacimiento", "Nacimiento"),
           ("nacionalidad", "Nacionalidad"), ("formacion", "Formación"), ("altura", "Altura"), ("peso", "Peso")]


def player(pid, name="ANA PRUEBA UNO", position="Base", dorsal="7", birth="01/02/2004", nationality="ESPAÑA",
           formacion="SI", height="175", weight="-"):
    return {"pid": pid, "nombre jugador": name, "puesto": position, "dorsal": dorsal, "fecha nacimiento": birth,
            "nacionalidad": nationality, "formacion": formacion, "altura": height, "peso": weight}


def page(players, columns=COLUMNS, team=TEAM, link=True, noise=True):
    head = "<th></th>" + "".join(f'<th class="{c}">{escape(t)}</th>' for c, t in columns)
    rows = []
    for p in players:
        href = f"https://baloncestoenvivo.feb.es/Jugador.aspx?i={team}&c={p['pid']}"
        photo = f"<td class=\"foto jugador\"><a href='{href}'><img src=\"x.png\"/></a></td>" if link else '<td class="foto jugador"></td>'
        cells = []
        for c, _ in columns:
            value = escape(str(p.get(c, "")))
            if c == "nombre jugador" and link:
                value = f"<a href='{href}'>{value}</a>"
            cells.append(f'<td class="{c}">{value}</td>')
        rows.append(f"<tr>{photo}{''.join(cells)}</tr>")
    other = "<table><tr><th>Competición</th></tr><tr><td>Liga</td></tr></table>" if noise else ""
    body = f'<table cellspacing="0"><tr>{head}</tr>{"".join(rows)}</table>'
    return f'<html><head><meta charset="utf-8"></head><body>{other}{body}</body></html>'


# --- parsing -----------------------------------------------------------------------------

def test_a_player_row_becomes_an_entry_keyed_by_the_play_by_play_id():
    roster = parse_roster(page([player("2892632", name="SOL PRUEBA DOS", position="A-Pivot", dorsal="4",
                                       birth="31/01/2000", nationality="ARGENTINA", formacion="NO", height="185")]), TEAM)
    assert roster == {"2892632": {
        "team_id": TEAM, "name": "SOL PRUEBA DOS", "formacion": False, "birth": "2000-01-31", "nationality": "ARGENTINA",
        "position": "A-Pivot", "dorsal": 4, "height": 185}}


@pytest.mark.parametrize("cell,expected", [("SI", True), ("SÍ", True), ("si ", True), ("NO", False), ("no", False),
                                           ("", None), ("-", None), ("?", None)])
def test_formacion_is_yes_no_or_unknown(cell, expected):
    assert parse_roster(page([player("1", formacion=cell)]), TEAM)["1"]["formacion"] is expected


def test_the_birth_date_may_carry_the_birthplace_and_missing_values_are_none():
    roster = parse_roster(page([
        player("1", birth="25/06/2003 Santiago de Compostela (A Coruña)"),
        player("2", birth="-", dorsal="-", height="-", position="-", nationality="")]), TEAM)
    assert roster["1"]["birth"] == "2003-06-25"
    assert (roster["2"]["birth"], roster["2"]["dorsal"], roster["2"]["height"], roster["2"]["position"]) == (None, None, None, None)
    assert roster["2"]["nationality"] is None


def test_accents_and_surrounding_spaces_are_kept_clean():
    roster = parse_roster(page([player("1", position="A-Pívot ", nationality="ESPAÑA ")]), TEAM)
    assert roster["1"]["position"] == "A-Pívot" and roster["1"]["nationality"] == "ESPAÑA"


def test_columns_are_found_by_what_they_are_not_by_their_position():
    shuffled = [COLUMNS[5], COLUMNS[0], ("extra", "Extra"), COLUMNS[3], COLUMNS[7], COLUMNS[1]]
    roster = parse_roster(page([player("9", formacion="SI", name="MARA PRUEBA")], columns=shuffled), TEAM)
    assert roster["9"]["formacion"] is True and roster["9"]["name"] == "MARA PRUEBA" and roster["9"]["birth"] == "2004-02-01"


def test_a_page_without_the_formacion_column_says_unknown_never_no():
    columns = [c for c in COLUMNS if c[0] != "formacion"]
    roster = parse_roster(page([player("1"), player("2")], columns=columns), TEAM)
    assert [e["formacion"] for e in roster.values()] == [None, None]


def test_the_player_id_is_read_from_the_link_whatever_the_order_of_its_query():
    html = page([player("7")]).replace("?i=1008631&c=7", "?c=7&i=1008631")
    assert list(parse_roster(html, TEAM)) == ["7"]


def test_a_row_without_a_player_link_cannot_be_matched_and_is_skipped():
    assert parse_roster(page([player("1")], link=False), TEAM) == {}


def test_the_page_may_have_other_tables_and_no_roster_at_all():
    assert parse_roster("<html><body><table><tr><th>Otra</th></tr></table></body></html>", TEAM) == {}
    assert parse_roster("", TEAM) == {} and parse_roster(b"", TEAM) == {}
    assert len(parse_roster(page([player("1"), player("2"), player("3")], noise=True), TEAM)) == 3


def test_bytes_are_decoded_as_utf_8_like_the_page():
    html = page([player("1", name="LÚA PRUEBA", nationality="ESPAÑA")]).encode("utf-8")
    roster = parse_roster(html, TEAM)
    assert roster["1"]["name"] == "LÚA PRUEBA" and roster["1"]["nationality"] == "ESPAÑA"


# --- fetching ----------------------------------------------------------------------------

class Response:
    def __init__(self, content, status=200):
        self.content, self.status_code = content, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def fake_get(pages):
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        item = pages[url]
        if isinstance(item, Exception):
            raise item
        return item

    get.calls = calls
    return get


def test_the_team_page_is_requested_with_a_user_agent_and_a_time_limit():
    get = fake_get({ROSTER_URL.format(team_id=TEAM): Response(page([player("1")]).encode("utf-8"))})
    assert list(fetch_team_roster(TEAM, get=get)) == ["1"]
    call = get.calls[0]
    assert call["url"] == "https://baloncestoenvivo.feb.es/equipo/1008631"
    assert "Mozilla" in call["headers"]["User-Agent"] and 0 < call["timeout"] <= 30


@pytest.mark.parametrize("answer", [ConnectionError("down"), Response(b"", 503), Response(b"<html>nothing</html>"), Response(b"")])
def test_a_page_that_cannot_be_read_gives_none_not_an_empty_roster(answer):
    assert fetch_team_roster(TEAM, get=fake_get({ROSTER_URL.format(team_id=TEAM): answer})) is None


def test_the_rosters_of_both_teams_are_merged_with_their_team_id():
    own, rival = TEAM, "1008898"
    get = fake_get({ROSTER_URL.format(team_id=own): Response(page([player("1")], team=own).encode("utf-8")),
                    ROSTER_URL.format(team_id=rival): Response(page([player("2", formacion="NO")], team=rival).encode("utf-8"))})
    merged = fetch_rosters([own, rival], get=get)
    assert {pid: e["team_id"] for pid, e in merged.items()} == {"1": own, "2": rival}
    assert [c["url"].rsplit("/", 1)[1] for c in get.calls] == [own, rival]


def test_if_one_team_fails_the_other_is_still_returned_and_if_both_fail_there_is_none():
    ok = Response(page([player("1")]).encode("utf-8"))
    get = fake_get({ROSTER_URL.format(team_id="A"): ok, ROSTER_URL.format(team_id="B"): ConnectionError("x")})
    assert list(fetch_rosters(["A", "B"], get=get)) == ["1"]
    down = fake_get({ROSTER_URL.format(team_id="A"): ConnectionError("x"), ROSTER_URL.format(team_id="B"): Response(b"", 500)})
    assert fetch_rosters(["A", "B"], get=down) is None
    assert fetch_rosters([], get=down) is None


def test_the_same_team_is_not_requested_twice():
    get = fake_get({ROSTER_URL.format(team_id=TEAM): Response(page([player("1")]).encode("utf-8"))})
    fetch_rosters([TEAM, TEAM], get=get)
    assert len(get.calls) == 1
