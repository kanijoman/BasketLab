"""Pure-function helpers for WeeklyReportService.

Contains: colour utilities, matplotlib table renderer, field configs,
row builders for basic / advanced / comparative / last-match / player tables.
No database access, no PyQt6, no side-effects.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Quartile colour helpers
# ---------------------------------------------------------------------------

_Q_COLORS     = ['#FFB3B3', '#FFD9A0', '#FFFFB3', '#B3FFB3']  # Q1→Q4 higher-is-better
_Q_COLORS_REV = list(reversed(_Q_COLORS))                      # Q1→Q4 lower-is-better


def q_color(value: float, quartiles: List[float], reverse: bool = False) -> str:
    """Return hex colour string for *value* relative to *quartiles* [Q1,Q2,Q3]."""
    palette = _Q_COLORS_REV if reverse else _Q_COLORS
    if value >= quartiles[2]:
        return palette[3]
    if value >= quartiles[1]:
        return palette[2]
    if value >= quartiles[0]:
        return palette[1]
    return palette[0]


def calc_quartiles(values: List[float]) -> List[float]:
    arr = [v for v in values if v is not None]
    if not arr:
        return [0.0, 0.0, 0.0]
    return [float(np.percentile(arr, q)) for q in [25, 50, 75]]


def sf(v: Any, decimals: int = 1) -> str:
    """Safe-format a number to string."""
    if v is None:
        return '-'
    try:
        return f'{float(v):.{decimals}f}'
    except (TypeError, ValueError):
        return str(v)


# ---------------------------------------------------------------------------
# Matplotlib table renderer
# ---------------------------------------------------------------------------

def render_table_png(
    col_headers: List[str],
    rows: List[List[str]],
    cell_colors: List[List[str]],
    title: str,
    dpi: int = 120,
) -> bytes:
    """Return PNG bytes for a styled table rendered with matplotlib Agg backend."""
    n_rows = len(rows)
    n_cols = len(col_headers)
    fig_width  = max(12, n_cols * 1.1)
    fig_height = max(2.5, n_rows * 0.38 + 1.4)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis('off')
    ax.set_title(title, fontsize=10, fontweight='bold', pad=8)

    if not rows:
        ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center', transform=ax.transAxes)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        return buf.getvalue()

    tbl = ax.table(
        cellText=rows,
        colLabels=col_headers,
        cellColours=cell_colors,
        colColours=['#2E4053'] * n_cols,
        loc='center',
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.auto_set_column_width(col=list(range(n_cols)))
    for col in range(n_cols):
        cell = tbl[0, col]
        cell.set_text_props(color='white', fontweight='bold')
        cell.set_height(0.06)
    for row in range(1, n_rows + 1):
        for col in range(n_cols):
            tbl[row, col].set_height(0.05)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    return buf.getvalue()


def fig_to_png(fig: Any, dpi: int = 150) -> bytes:
    """Save a matplotlib Figure to PNG bytes and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Field configurations
# ---------------------------------------------------------------------------

BASIC_HEADERS = [
    'Equipo', 'PJ', 'Local', 'Visitante',
    'P.Favor', 'P.Contra', 'Pts/P', 'PtsC/P',
    '%T2', '%T3', '%TL', 'Reb', 'RD', 'RO',
    'Ast', 'Rob', 'Pérd', 'Tap',
]

BASIC_FIELDS: List[Tuple[str, bool]] = [
    ('points_scored',           False),
    ('points_received',         True),
    ('points_per_game',         False),
    ('points_against_per_game', True),
    ('fg2_percentage',          False),
    ('fg3_percentage',          False),
    ('ft_percentage',           False),
    ('total_rebounds',          False),
    ('rebounds_def',            False),
    ('rebounds_off',            False),
    ('assists',                 False),
    ('steals',                  False),
    ('turnovers',               True),
    ('blocks',                  False),
]

ADV_HEADERS = [
    'Equipo', 'PJ',
    'Ritmo', 'OER', 'DER', 'Net',
    'eFG%', 'TS%', '3Pr', 'FTr', 'AST/FG',
    'AST%', 'TOV%', 'ROB%', 'TAP%', 'ORB%', 'RD%',
]

ADV_FIELDS: List[Tuple[str, bool]] = [
    ('possessions_per_game',    False),
    ('offensive_rating',        False),
    ('defensive_rating',        True),
    ('net_rating',              False),
    ('efg_percentage',          False),
    ('true_shooting',           False),
    ('three_point_rate',        False),
    ('free_throw_rate',         False),
    ('assist_fg_rate',          False),
    ('assist_rate',             False),
    ('turnover_rate',           True),
    ('steal_rate',              False),
    ('block_rate',              False),
    ('offensive_rebound_rate',  False),
    ('defensive_rebound_rate',  False),
]

PLAYER_HEADERS_AVG = [
    'Jugador', 'PJ', 'Min', 'Pts', '%TL', '%T2', '%T3',
    'RO', 'RD', 'Reb', 'Ast', 'Rob', 'BP', 'Tap', 'FP', 'FR', '+/-', 'Val',
]

PLAYER_HEADERS_TOT = [
    'Jugador', 'PJ', 'Min', 'Pts', 'TL', 'T2', 'T3',
    'RO', 'RD', 'Reb', 'Ast', 'Rob', 'BP', 'Tap', 'FP', 'FR', '+/-', 'Val',
]

PLAYER_FIELDS: List[Tuple[str, bool]] = [
    ('minutes_per_game',    False),
    ('points_per_game',     False),
    ('fg1_percentage',      False),
    ('fg2_percentage',      False),
    ('fg3_percentage',      False),
    ('total_ro',            False),
    ('total_rd',            False),
    ('rebounds_per_game',   False),
    ('assists_per_game',    False),
    ('steals_per_game',     False),
    ('turnovers_per_game',  True),
    ('blocks_per_game',     False),
    ('total_pf',            True),
    ('total_rf',            False),
    ('pllss_per_game',      False),
    ('valoracion_per_game', False),
]

LAST_MATCH_ADV_HEADERS = [
    'Equipo', 'PJ', 'Ritmo', 'OER', 'DER', 'Net',
    'eFG%', 'TS%', '3Pr', 'FTr', 'AST/FG',
    'AST%', 'TOV%', 'ROB%', 'TAP%', 'ORB%', 'RD%',
]

# ---------------------------------------------------------------------------
# Trend arrows
# ---------------------------------------------------------------------------

_TREND_LO, _TREND_HI = 5.0, 10.0


def trend_arrow(delta: float, lower_is_better: bool) -> str:
    abs_d = abs(delta)
    if abs_d < _TREND_LO:
        return '≈'
    good = (delta > 0) != lower_is_better
    if abs_d >= _TREND_HI:
        return '⇈' if good else '⇊'
    return '↑' if good else '↓'


# ---------------------------------------------------------------------------
# Basic / advanced row builders
# ---------------------------------------------------------------------------

def build_basic_rows(
    team_stats: List[Dict],
) -> Tuple[List[List[str]], List[List[str]]]:
    if not team_stats:
        return [], []
    qs = {f: calc_quartiles([float(t.get(f) or 0) for t in team_stats]) for f, _ in BASIC_FIELDS}
    texts, colors = [], []
    for team in team_stats:
        rt, rc = [str(team.get('team_name', team.get('_id', '')))], ['#FFFFFF']
        rt += [str(int(team.get(k, 0) or 0)) for k in ('total_games', 'games_home', 'games_away')]
        rc += ['#FFFFFF', '#FFFFFF', '#FFFFFF']
        for field, rev in BASIC_FIELDS:
            v = float(team.get(field) or 0)
            rt.append(sf(v))
            rc.append(q_color(v, qs[field], rev))
        texts.append(rt)
        colors.append(rc)
    return texts, colors


def build_advanced_rows(
    team_stats: List[Dict],
) -> Tuple[List[List[str]], List[List[str]]]:
    if not team_stats:
        return [], []
    qs = {f: calc_quartiles([float(t.get(f) or 0) for t in team_stats]) for f, _ in ADV_FIELDS}
    texts, colors = [], []
    for team in team_stats:
        rt = [str(team.get('team_name', team.get('_id', ''))), str(int(team.get('total_games', 0) or 0))]
        rc = ['#FFFFFF', '#FFFFFF']
        for field, rev in ADV_FIELDS:
            v = float(team.get(field) or 0)
            rt.append(sf(v))
            rc.append(q_color(v, qs[field], rev))
        texts.append(rt)
        colors.append(rc)
    return texts, colors


# ---------------------------------------------------------------------------
# Comparative row builders (period1 vs period2 with delta + arrow)
# ---------------------------------------------------------------------------

def build_comparative_basic_rows(
    comp_stats: List[Dict],
) -> Tuple[List[List[str]], List[List[str]]]:
    if not comp_stats:
        return [], []
    p1_list = [c['monthly'] for c in comp_stats]
    qs = {f: calc_quartiles([float(t.get(f) or 0) for t in p1_list]) for f, _ in BASIC_FIELDS}
    texts, colors = [], []
    for cs in comp_stats:
        p1, p2, deltas = cs['monthly'], cs['rest'], cs.get('deltas', {})
        rt = [str(p1.get('team_name', p1.get('_id', '')))]
        rc = ['#FFFFFF']
        for key in ('total_games', 'games_home', 'games_away'):
            rt.append(f"{int(p1.get(key, 0) or 0)}+{int(p2.get(key, 0) or 0)}")
            rc.append('#FFFFFF')
        for field, rev in BASIC_FIELDS:
            v = float(p1.get(field) or 0)
            arrow = trend_arrow(float(deltas.get(field, 0)), rev)
            rt.append(f'{sf(v)} {arrow}')
            rc.append(q_color(v, qs[field], rev))
        texts.append(rt)
        colors.append(rc)
    return texts, colors


def build_comparative_advanced_rows(
    comp_stats: List[Dict],
) -> Tuple[List[List[str]], List[List[str]]]:
    if not comp_stats:
        return [], []
    p1_list = [c['monthly'] for c in comp_stats]
    qs = {f: calc_quartiles([float(t.get(f) or 0) for t in p1_list]) for f, _ in ADV_FIELDS}
    texts, colors = [], []
    for cs in comp_stats:
        p1, deltas = cs['monthly'], cs.get('deltas', {})
        pg1, pg2 = int(p1.get('total_games', 0) or 0), int(cs['rest'].get('total_games', 0) or 0)
        rt = [str(p1.get('team_name', p1.get('_id', ''))), f'{pg1}+{pg2}']
        rc = ['#FFFFFF', '#FFFFFF']
        for field, rev in ADV_FIELDS:
            v = float(p1.get(field) or 0)
            arrow = trend_arrow(float(deltas.get(field, 0)), rev)
            rt.append(f'{sf(v)} {arrow}')
            rc.append(q_color(v, qs[field], rev))
        texts.append(rt)
        colors.append(rc)
    return texts, colors


# ---------------------------------------------------------------------------
# Last-match row builder
# ---------------------------------------------------------------------------

_HIGHER_IS_BETTER = {
    'points_per_game', 'fg2_percentage', 'fg3_percentage', 'ft_percentage',
    'efg_percentage', 'true_shooting', 'assists_per_game', 'steals_per_game',
    'blocks_per_game', 'offensive_rating', 'net_rating', 'rebounds_per_game',
    'offensive_rebound_rate', 'three_point_rate', 'free_throw_rate',
    'assist_fg_rate', 'assist_rate', 'steal_rate', 'block_rate',
    'possessions_per_game', 'total_rebounds', 'rebounds_def', 'rebounds_off',
    'assists', 'steals', 'blocks',
}

_LOWER_IS_BETTER_LM = {
    'defensive_rating', 'turnover_rate', 'turnovers_per_game',
    'points_against_per_game', 'points_received', 'turnovers',
}


def _lm_cell_color(val: float, opp: float, field: str) -> str:
    if abs(val - opp) < 0.01:
        return '#D3D3D3'
    if field in _HIGHER_IS_BETTER:
        return '#90EE90' if val > opp else '#FFB6C1'
    if field in _LOWER_IS_BETTER_LM:
        return '#90EE90' if val < opp else '#FFB6C1'
    return '#90EE90' if val > opp else '#FFB6C1'


def build_last_match_rows(
    sel_stats: Dict, opp_stats: Dict,
    sel_season: Dict, opp_season: Dict,
    sel_name: str, opp_name: str,
) -> Tuple[List[List[str]], List[List[str]]]:
    rows_t, rows_c = [], []
    for team_stats, opp_match, season, name in [
        (sel_stats, opp_stats, sel_season, sel_name),
        (opp_stats, sel_stats, opp_season, opp_name),
    ]:
        rt = [name, '1']
        rc = ['#FFFFFF', '#FFFFFF']
        for field, rev in ADV_FIELDS:
            val     = float(team_stats.get(field) or 0)
            opp_val = float(opp_match.get(field) or 0)
            sv      = float(season.get(field) or 0)
            arrow = trend_arrow(((val - sv) / abs(sv)) * 100, rev) if sv != 0 else ''
            col = _lm_cell_color(val, opp_val, field)
            rt.append(f'{sf(val)} {arrow}' if arrow else sf(val))
            rc.append(col)
        rows_t.append(rt)
        rows_c.append(rc)
    return rows_t, rows_c


# ---------------------------------------------------------------------------
# Player row builder
# ---------------------------------------------------------------------------

def _player_val(p: Dict, field: str, mode: str) -> float:
    gp  = max(int(p.get('games_played', 0)), 1)
    mpg = float(p.get('minutes_per_game', 0))

    if mode == 'total':
        total_map = {
            'minutes_per_game':   mpg * gp,
            'points_per_game':    float(p.get('total_pts', 0)),
            'fg1_percentage':     float(p.get('fg1_percentage', 0)),
            'fg2_percentage':     float(p.get('fg2_percentage', 0)),
            'fg3_percentage':     float(p.get('fg3_percentage', 0)),
            'total_ro':           float(p.get('total_ro', 0)),
            'total_rd':           float(p.get('total_rd', 0)),
            'rebounds_per_game':  float(p.get('total_rt', 0)),
            'assists_per_game':   float(p.get('total_assist', 0)),
            'steals_per_game':    float(p.get('total_st', 0)),
            'turnovers_per_game': float(p.get('total_to', 0)),
            'blocks_per_game':    float(p.get('total_bs', 0)),
            'total_pf':           float(p.get('total_pf', 0)),
            'total_rf':           float(p.get('total_rf', 0)),
            'pllss_per_game':     float(p.get('total_pllss', 0)),
            'valoracion_per_game': float(p.get('total_val', 0)),
        }
        return total_map.get(field, 0)

    if mode == 'projection':
        if field in ('fg1_percentage', 'fg2_percentage', 'fg3_percentage'):
            return float(p.get(field, 0))
        if field == 'minutes_per_game':
            return 30.0
        mult = (30.0 / mpg) if mpg > 0 else 0
        return _player_val(p, field, 'avg') * mult

    avg_map = {
        'minutes_per_game':   mpg,
        'points_per_game':    float(p.get('points_per_game', 0)),
        'fg1_percentage':     float(p.get('fg1_percentage', 0)),
        'fg2_percentage':     float(p.get('fg2_percentage', 0)),
        'fg3_percentage':     float(p.get('fg3_percentage', 0)),
        'total_ro':           float(p.get('total_ro', 0)) / gp,
        'total_rd':           float(p.get('total_rd', 0)) / gp,
        'rebounds_per_game':  float(p.get('rebounds_per_game', 0)),
        'assists_per_game':   float(p.get('assists_per_game', 0)),
        'steals_per_game':    float(p.get('steals_per_game', 0)),
        'turnovers_per_game': float(p.get('turnovers_per_game', 0)),
        'blocks_per_game':    float(p.get('blocks_per_game', 0)),
        'total_pf':           float(p.get('total_pf', 0)) / gp,
        'total_rf':           float(p.get('total_rf', 0)) / gp,
        'pllss_per_game':     float(p.get('pllss_per_game', 0)),
        'valoracion_per_game': float(p.get('valoracion_per_game', 0)),
    }
    return avg_map.get(field, 0)


def build_player_rows(
    players: List[Dict],
    mode: str,
) -> Tuple[List[str], List[List[str]], List[List[str]]]:
    """Return (headers, row_texts, row_colors) for a player stats table."""
    headers = PLAYER_HEADERS_TOT if mode == 'total' else PLAYER_HEADERS_AVG
    if not players:
        return headers, [], []
    qs = {f: calc_quartiles([_player_val(p, f, mode) for p in players]) for f, _ in PLAYER_FIELDS}
    texts, colors = [], []
    for p in players:
        gp = int(p.get('games_played', 0))
        rt, rc = [str(p.get('player_name', '')), str(gp)], ['#FFFFFF', '#FFFFFF']
        for field, rev in PLAYER_FIELDS:
            v = _player_val(p, field, mode)
            rt.append(sf(v))
            rc.append(q_color(v, qs[field], rev))
        texts.append(rt)
        colors.append(rc)
    return headers, texts, colors
