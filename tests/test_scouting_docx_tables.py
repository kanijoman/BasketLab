"""The tables of a player's page of the individual scouting, as data (#717, 17b).

The DOCX is made in the browser too, so what the tables say (header, text of each cell, quartile fill) is decided in one place that is not python-docx: ``player_tables``.
The tests pin the rules the DOCX of the server always had: where the quartile colours go and for which columns they are reversed, the missing value as ``-``, minutes as MM:SS.
"""
from src.services.scouting_docx_tables import AVERAGES, ADVANCED, TOTALS_HEADERS, player_tables


def player(i: int, **extra) -> dict:
    base = {"player_id": str(i), "games_played": 10 + i, "minutes_per_game": 20.5 + i, "points_per_game": 8.0 + i, "fg1_percentage": 70.0 + i, "fg2_percentage": 50.0, "fg3_percentage": 30.0 + i,
            "offensive_rebounds_per_game": 1.0, "defensive_rebounds_per_game": 2.0, "rebounds_per_game": 3.0, "assists_per_game": 2.0 + i, "steals_per_game": 1.0,
            "turnovers_per_game": 1.0 + i, "blocks_per_game": 0.5, "fouls_per_game": 2.0 + i, "valoracion_per_game": 9.0 + i, "total_minutes": 205.5, "total_pts": 80, "total_p1m": 10, "total_p1a": 14,
            "total_p2m": 20, "total_p2a": 40, "total_p3m": 8, "total_p3a": 25, "total_ro": 10, "total_rd": 20, "total_rt": 30, "total_assist": 20, "total_st": 10, "total_to": 11, "total_bs": 5, "total_pf": 22,
            "total_val": 90, "true_shooting": 55.0 + i, "efg_percentage": 50.0, "net_rtg": 3.0 * i, "tov_pct_adv": 10.0 + i, "drating": 100.0 + i}
    return {**base, **extra}


def test_the_columns_of_each_table_are_those_of_the_documents_the_staff_already_reads():
    assert [c[0] for c in AVERAGES] == ["PJ", "MIN", "PTS", "TL%", "T2%", "T3%", "RO", "RD", "RT", "AST", "ROB", "BP", "TAP", "FP", "VAL"]
    assert [c[0] for c in ADVANCED] == ["TS%", "eFG%", "3PAr", "FTr", "ORB%", "DRB%", "AST%", "TO%", "ROB%", "TAP%", "USG%", "ORtg", "DRtg", "NetRtg"]
    assert TOTALS_HEADERS == [c[0] for c in AVERAGES]


def test_the_cells_are_formatted_and_the_percentages_and_minutes_have_their_own_format():
    players = [player(i) for i in range(5)]
    tables = player_tables(players[2], players)
    averages = {h: c["text"] for h, c in zip(tables["averages"]["headers"], tables["averages"]["cells"])}
    assert averages["MIN"] == "22:30" and averages["PTS"] == "10.0" and averages["TL%"] == "72.0%" and averages["PJ"] == "12.0"
    advanced = {h: c["text"] for h, c in zip(tables["advanced"]["headers"], tables["advanced"]["cells"])}
    assert advanced["TS%"] == "57.0%" and advanced["NetRtg"] == "6.0" and advanced["ORtg"] == "-"            # a figure the player does not have is a hyphen
    totals = tables["totals"]["cells"]
    assert totals[1] == "205:30" and totals[3] == "10⁠/⁠14" and totals[2] == "80"


def test_the_quartile_colour_goes_green_to_red_and_is_reversed_for_turnovers_fouls_and_the_defensive_rating():
    players = [player(i) for i in range(8)]
    best, worst = player_tables(players[7], players), player_tables(players[0], players)
    col = {h: i for i, h in enumerate(best["averages"]["headers"])}
    assert best["averages"]["cells"][col["PTS"]]["fill"] == "C6EFCE" and worst["averages"]["cells"][col["PTS"]]["fill"] == "FFC7CE"
    assert best["averages"]["cells"][col["BP"]]["fill"] == "FFC7CE" and worst["averages"]["cells"][col["BP"]]["fill"] == "C6EFCE"          # more turnovers is worse
    assert best["averages"]["cells"][col["FP"]]["fill"] == "FFC7CE"
    adv = {h: i for i, h in enumerate(best["advanced"]["headers"])}
    assert best["advanced"]["cells"][adv["DRtg"]]["fill"] == "FFC7CE" and worst["advanced"]["cells"][adv["DRtg"]]["fill"] == "C6EFCE"


def test_with_fewer_than_four_values_or_without_the_value_there_is_no_colour_regression():
    """Bug it prevents: shading a column from three players as if it were a league."""
    players = [player(i) for i in range(3)]
    assert all(c["fill"] is None for c in player_tables(players[0], players)["averages"]["cells"])
    many = [player(i) for i in range(6)]
    many[0]["points_per_game"] = None
    cell = player_tables(many[0], many)["averages"]["cells"][2]
    assert cell["text"] == "-" and cell["fill"] is None


def test_a_column_where_everyone_is_equal_is_colored_as_the_top_quartile():
    players = [player(i) for i in range(6)]
    table = player_tables(players[0], players)["averages"]
    assert table["cells"][table["headers"].index("T2%")]["fill"] == "C6EFCE"               # all 50.0: v >= q75
