"""Pure-function helpers for WeeklyReportService.

Contains: colour utilities, matplotlib table renderer, field configs,
row builders for basic / advanced / comparative / last-match / player tables.
No database access, no PyQt6, no side-effects.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Colour constants — dark theme matching the web UI (tailwind.config.js)
# ---------------------------------------------------------------------------

# Q4 worst → Q1 best (higher-is-better); mirrors tailwind q1-q4 bg tokens
_Q_COLORS     = ['#500000', '#3d2000', '#5a3e00', '#14532d']  # worst→best bg
_Q_COLORS_REV = list(reversed(_Q_COLORS))                      # lower-is-better

# Cell background → high-contrast text colour
_BG_TEXT: Dict[str, str] = {
    '#14532d': '#4ade80',   # Q1 best  — bright green
    '#5a3e00': '#fde047',   # Q2       — bright yellow
    '#3d2000': '#fb923c',   # Q3       — orange
    '#500000': '#ef4444',   # Q4 worst — red
}
_CELL_BG   = '#0d1117'  # default cell background
_CELL_TEXT = '#e6edf3'  # default cell text
_HDR_BG    = '#1f2937'  # header background
_FIG_BG    = '#0d1117'  # figure / axes background

# CV badge thresholds and colours (matches CVBadge.tsx)
_CV_LO, _CV_HI = 15.0, 30.0


def _cv_badge_color(cv: float) -> str:
    if cv >= _CV_HI:  return '#ef4444'   # high   — red
    if cv >= _CV_LO:  return '#fbbf24'   # medium — amber
    return '#9ca3af'                      # low    — slate


# ---------------------------------------------------------------------------
# Quartile colour helpers
# ---------------------------------------------------------------------------


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
    text_colors: Optional[List[List[str]]] = None,
) -> bytes:
    """Return PNG bytes for a styled table rendered with matplotlib Agg backend.

    Args:
        col_headers: Column header labels.
        rows: Cell text values (rows × cols).
        cell_colors: Per-cell background hex colours (rows × cols).
        title: Figure title.
        dpi: Output resolution.
        text_colors: Optional per-cell text colour overrides (rows × cols).
            When *None*, text colour is derived from the cell background using
            :data:`_BG_TEXT` so quartile cells stay readable on dark theme.
    """
    n_rows = len(rows)
    n_cols = len(col_headers)
    has_cv = bool(text_colors)
    row_h  = 0.07 if has_cv else 0.055  # taller rows when σ badge wraps
    fig_width  = max(12, n_cols * 1.1)
    fig_height = max(2.5, n_rows * row_h * 10 + 1.4)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor(_FIG_BG)
    ax.set_facecolor(_FIG_BG)
    ax.axis('off')
    ax.set_title(title, fontsize=10, fontweight='bold', pad=8, color=_CELL_TEXT)

    if not rows:
        ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                color=_CELL_TEXT, transform=ax.transAxes)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor=_FIG_BG)
        plt.close(fig)
        return buf.getvalue()

    tbl = ax.table(
        cellText=rows,
        colLabels=col_headers,
        cellColours=cell_colors,
        colColours=[_HDR_BG] * n_cols,
        loc='center',
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7)
    tbl.auto_set_column_width(col=list(range(n_cols)))

    # Header row
    for col in range(n_cols):
        cell = tbl[0, col]
        cell.set_text_props(color=_CELL_TEXT, fontweight='bold')
        cell.set_height(0.06)

    # Data rows — auto-derive text colour from cell background for dark theme
    for row in range(1, n_rows + 1):
        for col in range(n_cols):
            c = tbl[row, col]
            c.set_height(row_h)
            ri = row - 1
            if text_colors and ri < len(text_colors) and col < len(text_colors[ri]):
                txt = text_colors[ri][col]
            else:
                bg  = cell_colors[ri][col] if cell_colors else _CELL_BG
                txt = _BG_TEXT.get(bg, _CELL_TEXT)
            c.get_text().set_color(txt)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor=_FIG_BG)
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
        rt, rc = [str(team.get('team_name', team.get('_id', '')))], [_CELL_BG]
        rt += [str(int(team.get(k, 0) or 0)) for k in ('total_games', 'games_home', 'games_away')]
        rc += [_CELL_BG, _CELL_BG, _CELL_BG]
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
        rc = [_CELL_BG, _CELL_BG]
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
        rc = [_CELL_BG]
        for key in ('total_games', 'games_home', 'games_away'):
            rt.append(f"{int(p1.get(key, 0) or 0)}+{int(p2.get(key, 0) or 0)}")
            rc.append(_CELL_BG)
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
        rc = [_CELL_BG, _CELL_BG]
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
        return '#1e2530'  # neutral dark
    if field in _HIGHER_IS_BETTER:
        return '#14532d' if val > opp else '#500000'  # Q1 green / Q4 red
    if field in _LOWER_IS_BETTER_LM:
        return '#14532d' if val < opp else '#500000'
    return '#14532d' if val > opp else '#500000'


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
        rc = [_CELL_BG, _CELL_BG]
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
        rt, rc = [str(p.get('player_name', '')), str(gp)], [_CELL_BG, _CELL_BG]
        for field, rev in PLAYER_FIELDS:
            v = _player_val(p, field, mode)
            rt.append(sf(v))
            rc.append(q_color(v, qs[field], rev))
        texts.append(rt)
        colors.append(rc)
    return headers, texts, colors


# ---------------------------------------------------------------------------
# Consistency table builder
# ---------------------------------------------------------------------------

# Key stats shown in the league-wide consistency PNG (CV % for each)
_CONSISTENCY_KEYS = [
    ("Pts CV%",   "points_per_game",   False),
    ("eFG% CV%",  "efg_percentage",    False),
    ("NR CV%",    "net_rating",        False),
    ("Poss CV%",  "possessions_per_game", False),
    ("TOV% CV%",  "turnover_rate",     True),   # higher CV = worse → reverse colouring
    ("3P% CV%",   "fg3_percentage",    False),
]

CONSISTENCY_HEADERS = ["Equipo"] + [k[0] for k in _CONSISTENCY_KEYS]


def build_consistency_rows(
    own_map: Dict[str, Dict],
) -> Tuple[List[List[str]], List[List[str]]]:
    """Return (row_texts, row_colors) for the league-wide consistency PNG.

    Args:
        own_map: The ``"own"`` sub-dict from ``TeamStatsService.get_consistency()``.
                 Format: ``{team_name: {stat_key: {"mean", "std", "cv", "n"}}}``.

    Returns:
        Tuple of (row_texts, row_colors) ready for :func:`render_table_png`.
    """
    if not own_map:
        return [], []

    # Collect CV values per column for quartile colouring
    col_values: Dict[str, List[float]] = {k[1]: [] for k in _CONSISTENCY_KEYS}
    for team_stats in own_map.values():
        for _, stat_key, _ in _CONSISTENCY_KEYS:
            cv = (team_stats.get(stat_key) or {}).get("cv")
            if cv is not None:
                col_values[stat_key].append(cv)

    quartiles = {sk: calc_quartiles(col_values[sk]) for _, sk, _ in _CONSISTENCY_KEYS}

    # Sort teams by net_rating CV ascending (most consistent first)
    sorted_teams = sorted(
        own_map.items(),
        key=lambda kv: (kv[1].get("net_rating") or {}).get("cv") or 9999,
    )

    texts:  List[List[str]] = []
    colors: List[List[str]] = []
    for team_name, team_stats in sorted_teams:
        row_t = [team_name]
        row_c = [_CELL_BG]
        for _, stat_key, reverse in _CONSISTENCY_KEYS:
            cv = (team_stats.get(stat_key) or {}).get("cv")
            row_t.append(sf(cv, 1) if cv is not None else '-')
            if cv is not None:
                # For consistency tables low CV = good → reverse colouring convention
                row_c.append(q_color(cv, quartiles[stat_key], reverse=not reverse))
            else:
                row_c.append(_CELL_BG)
        texts.append(row_t)
        colors.append(row_c)

    return texts, colors


# ---------------------------------------------------------------------------
# CV badge overlay — appends σXX% annotation to stat cells
# ---------------------------------------------------------------------------

def apply_cv_overlay(
    texts: List[List[str]],
    cv_data: Dict[str, Dict],
    fields: List[Tuple[str, bool]],
    n_meta: int = 4,
) -> Tuple[List[List[str]], List[List[str]]]:
    """Append a σXX% CV badge to numeric cells and return (new_texts, text_colors).

    Mirrors the ``CVBadge`` component in the web UI. Each cell that has a CV
    value gets its text replaced with ``"VALUE\\nσXX%"`` so the badge appears
    on a second line inside the cell, and the text colour is set to the badge
    colour (slate / amber / red depending on severity).

    Args:
        texts:   Row texts produced by any row-builder function.
        cv_data: ``{team_name: {field: {"cv", "mean", "std", "n"}}}`` from
                 ``TeamStatsService.get_consistency()['own']``.
        fields:  Ordered field list (e.g. ``BASIC_FIELDS`` or ``ADV_FIELDS``).
        n_meta:  Number of leading metadata columns to skip (name + count cols).

    Returns:
        Tuple ``(modified_texts, text_colors)`` where *text_colors* carries the
        per-cell display colour (CV badge colour, or ``_CELL_TEXT`` otherwise).
    """
    if not cv_data or not texts:
        return texts, []

    new_texts:   List[List[str]] = []
    text_colors: List[List[str]] = []

    for row in texts:
        team_name = row[0]
        team_cv   = cv_data.get(team_name, {})
        row_t     = list(row)
        row_c     = [_CELL_TEXT] * len(row)

        for i, (field, _) in enumerate(fields):
            col_idx  = n_meta + i
            cv_entry = team_cv.get(field)
            if cv_entry and cv_entry.get('n', 0) >= 3:
                cv          = float(cv_entry['cv'])
                badge_color = _cv_badge_color(cv)
                row_t[col_idx] = f"{row_t[col_idx]}\n\u03c3{cv:.0f}%"
                row_c[col_idx] = badge_color

        new_texts.append(row_t)
        text_colors.append(row_c)

    return new_texts, text_colors

