"""Statistics the report covers (keys match the team-stats / league-quartiles rows)."""
from typing import Dict, NamedTuple, Optional, Tuple


class StatDef(NamedTuple):
    key: str
    label: str
    group: str
    higher_is_better: Optional[bool]  # None = neutral (depends on style)
    pct: bool
    theme: str


GROUPS = ("Básicas", "Tiro", "Four Factors", "Juego colectivo", "Eficiencia")

CATALOG: Tuple[StatDef, ...] = (
    StatDef("points_per_game", "Puntos por partido", "Básicas", True, False, "scoring"),
    StatDef("points_against_per_game", "Puntos recibidos por partido", "Básicas", False, False, "defense"),
    StatDef("rebounds_per_game", "Rebotes por partido", "Básicas", True, False, "def_rebound"),
    StatDef("offensive_rebounds_per_game", "Rebotes ofensivos por partido", "Básicas", True, False, "off_rebound"),
    StatDef("defensive_rebounds_per_game", "Rebotes defensivos por partido", "Básicas", True, False, "def_rebound"),
    StatDef("assists_per_game", "Asistencias por partido", "Básicas", True, False, "playmaking"),
    StatDef("steals_per_game", "Robos por partido", "Básicas", True, False, "pressure"),
    StatDef("turnovers_per_game", "Pérdidas por partido", "Básicas", False, False, "turnovers"),
    StatDef("blocks_per_game", "Tapones por partido", "Básicas", True, False, "rim"),
    StatDef("possessions_per_game", "Posesiones por partido", "Básicas", None, False, "tempo"),
    StatDef("fg2_percentage", "% tiros de 2", "Tiro", True, True, "shoot2"),
    StatDef("fg3_percentage", "% triples", "Tiro", True, True, "shoot3"),
    StatDef("ft_percentage", "% tiros libres", "Tiro", True, True, "free_throws"),
    StatDef("three_point_rate", "Tasa de triples (3PA/FGA)", "Tiro", None, True, "shot_mix"),
    StatDef("efg_percentage", "eFG%", "Four Factors", True, True, "shooting_eff"),
    StatDef("true_shooting", "TS%", "Four Factors", True, True, "shooting_eff"),
    StatDef("turnover_rate", "TOV%", "Four Factors", False, True, "turnovers"),
    StatDef("offensive_rebound_rate", "ORB%", "Four Factors", True, True, "off_rebound"),
    StatDef("free_throw_rate", "FTr", "Four Factors", True, True, "free_throw_rate"),
    StatDef("assist_rate", "Ratio de asistencias", "Juego colectivo", True, True, "playmaking"),
    StatDef("assist_fg_rate", "% canastas asistidas", "Juego colectivo", True, True, "playmaking"),
    StatDef("steal_rate", "Ratio de robos", "Juego colectivo", True, True, "pressure"),
    StatDef("block_rate", "Ratio de tapones", "Juego colectivo", True, True, "rim"),
    StatDef("defensive_rebound_rate", "DRB%", "Juego colectivo", True, True, "def_rebound"),
    StatDef("offensive_rating", "Rating ofensivo (ORtg)", "Eficiencia", True, False, "off_rating"),
    StatDef("defensive_rating", "Rating defensivo (DRtg)", "Eficiencia", False, False, "def_rating"),
    StatDef("net_rating", "Net Rating", "Eficiencia", True, False, "net_rating"),
)

BY_KEY: Dict[str, StatDef] = {s.key: s for s in CATALOG}


def format_value(stat: StatDef, value: float) -> str:
    return f"{value:.1f}%" if stat.pct else f"{value:.1f}"
