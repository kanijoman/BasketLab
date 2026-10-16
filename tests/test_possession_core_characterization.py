"""Characterization of the possession core on both sample games (FEB and FBCYL).

Written before splitting ``src/pbp/possession_core.py`` (#360). The rows are now built with the possession tracker
(#350), a deliberate change: the points per team still equal the official score (56-74, 35-92) and the phantom
'otro' rows drop from 14 to 5 (FEB) and from 48 to 10 (FBCYL, whose clock was being read backwards); the goldens
were regenerated then.
If a deliberate behaviour change breaks them, regenerate with
``python -c "from tests.test_possession_core_characterization import print_goldens; print_goldens()"``.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

import pytest

from src.pbp import possession_core
from src.pbp.possession_core import count_quality_pbp_metrics, extract_possession_rows

GOLDENS = {'fbcyl': {'digest': '4fffc1f372842ee7e7944e37cd14983f2b180aa9cf3811169950d42545ae22c3',
           'endings': {'otro': 10,
                       'tiro_2': 26,
                       'tiro_fallado': 57,
                       'tiros_libres': 21,
                       'triple': 10,
                       'violacion': 2},
           'origins': {'rebote_defensivo': 59, 'saque_fondo': 61, 'saque_inicial_periodo': 4, 'violacion': 2},
           'points': {'33865': 35, '33866': 92},
           'quality': {'33865': {'RebD': 0,
                                 'RebO': 0,
                                 'T1A': 9,
                                 'T1M': 6,
                                 'T2A': 30,
                                 'T2M': 10,
                                 'T3A': 31,
                                 'T3M': 3,
                                 'TOV': 0},
                       '33866': {'RebD': 0,
                                 'RebO': 0,
                                 'T1A': 37,
                                 'T1M': 21,
                                 'T2A': 55,
                                 'T2M': 25,
                                 'T3A': 19,
                                 'T3M': 7,
                                 'TOV': 2}},
           'rows': 126},
 'feb': {'digest': 'b67b2c1ba6dd20444ac63f56c2e5fdeb31667730ac1d9c6679b7613441db1aef',
         'endings': {'otro': 5,
                     'recuperacion': 18,
                     'tiro_2': 25,
                     'tiro_fallado': 54,
                     'tiros_libres': 14,
                     'triple': 20,
                     'violacion': 6},
         'origins': {'rebote_defensivo': 57,
                     'recuperacion': 18,
                     'saque_fondo': 57,
                     'saque_inicial_periodo': 4,
                     'violacion': 6},
         'points': {'981204': 56, '982047': 74},
         'quality': {'981204': {'RebD': 22,
                                'RebO': 5,
                                'T1A': 17,
                                'T1M': 7,
                                'T2A': 29,
                                'T2M': 11,
                                'T3A': 32,
                                'T3M': 9,
                                'TOV': 11},
                     '982047': {'RebD': 31,
                                'RebO': 13,
                                'T1A': 16,
                                'T1M': 11,
                                'T2A': 33,
                                'T2M': 15,
                                'T3A': 27,
                                'T3M': 11,
                                'TOV': 13}},
         'rows': 142}}


def _team_info(doc, is_fbcyl):
    if is_fbcyl:
        teams = doc["stats"]["teams"]
        return {str(t["teamIdIntern"]): {"name": t["name"], "home_away": "Local" if i == 0 else "Visitante"}
                for i, t in enumerate(teams)}
    return {str(t["id"]): {"name": t["name"], "home_away": "Local" if i == 0 else "Visitante"}
            for i, t in enumerate(doc["HEADER"]["TEAM"][:2])}


def snapshot(doc, is_fbcyl):
    info = _team_info(doc, is_fbcyl)
    rows = extract_possession_rows(doc, is_fbcyl, "GOLDEN", info)
    canonical = json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str)
    points = Counter()
    for row in rows:
        points[row["Equipo_ID"]] += int(row["Puntos_obtenidos"] or 0)
    return {
        "rows": len(rows),
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "points": dict(sorted(points.items())),
        "origins": dict(sorted(Counter(r["Origen_posesion"] for r in rows).items())),
        "endings": dict(sorted(Counter(r["Tipo_finalizacion"] for r in rows).items())),
        "quality": count_quality_pbp_metrics(doc, is_fbcyl, list(info)),
    }


def print_goldens():  # pragma: no cover - maintenance helper
    from pathlib import Path

    from src.live_core.vectors import unwrap_extended_json

    samples = Path(__file__).parent.parent / "src" / "JSON_samples"
    with open(samples / "feb_game.json", encoding="utf-8") as f:
        feb = unwrap_extended_json(json.load(f))
    with open(samples / "fbcyl_game.json", encoding="utf-8") as f:
        fbcyl = json.load(f)
    print(json.dumps({"feb": snapshot(feb, False), "fbcyl": snapshot(fbcyl, True)}, indent=4, sort_keys=True))


@pytest.mark.parametrize("name,is_fbcyl", [("feb", False), ("fbcyl", True)])
def test_extraction_and_quality_counts_do_not_change(name, is_fbcyl, feb_game_doc, fbcyl_game_doc):
    doc = fbcyl_game_doc if is_fbcyl else feb_game_doc
    assert snapshot(doc, is_fbcyl) == GOLDENS[name]


def test_public_names_stay_importable_from_possession_core():
    """Consumers import these from ``src.pbp.possession_core`` (the split keeps it as the facade)."""
    for name in (
        "extract_possession_rows", "count_quality_pbp_metrics", "is_controversial_possession", "is_tab_evaluated_possession",
        "QUALITY_METRICS",
    ):
        assert hasattr(possession_core, name), name
