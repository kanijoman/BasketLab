"""Characterization of the possession core on both sample games (FEB and FBCYL).

Written before splitting ``src/pbp/possession_core.py`` (#360): the refactor must not change a single
row or quality count, so the goldens below were captured from the code as it was before the split.
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

GOLDENS = {
    "fbcyl": {
        "digest": "8de7208b0a8fc31dc86e441b94458701268b5cfa89ebf546dc81423a694b3b10",
        "endings": {
            "otro": 48,
            "tiro_2": 24,
            "tiro_fallado": 74,
            "tiros_libres": 28,
            "triple": 9,
            "violacion": 2
        },
        "origins": {
            "rebote_defensivo": 72,
            "saque_fondo": 108,
            "saque_inicial_periodo": 3,
            "violacion": 2
        },
        "points": {
            "33865": 35,
            "33866": 92
        },
        "quality": {
            "33865": {
                "RebD": 0,
                "RebO": 0,
                "T1A": 9,
                "T1M": 6,
                "T2A": 30,
                "T2M": 10,
                "T3A": 31,
                "T3M": 3,
                "TOV": 0
            },
            "33866": {
                "RebD": 0,
                "RebO": 0,
                "T1A": 37,
                "T1M": 21,
                "T2A": 55,
                "T2M": 25,
                "T3A": 19,
                "T3M": 7,
                "TOV": 2
            }
        },
        "rows": 185
    },
    "feb": {
        "digest": "5fea2ca5895da588553c4033891b52221d68842e5d2cd5b2aab0ef733bff0477",
        "endings": {
            "otro": 14,
            "recuperacion": 18,
            "tiro_2": 24,
            "tiro_fallado": 58,
            "tiros_libres": 17,
            "triple": 19,
            "violacion": 6
        },
        "origins": {
            "rebote_defensivo": 58,
            "recuperacion": 18,
            "saque_fondo": 69,
            "saque_inicial_periodo": 5,
            "violacion": 6
        },
        "points": {
            "981204": 56,
            "982047": 74
        },
        "quality": {
            "981204": {
                "RebD": 22,
                "RebO": 5,
                "T1A": 17,
                "T1M": 7,
                "T2A": 29,
                "T2M": 11,
                "T3A": 32,
                "T3M": 9,
                "TOV": 11
            },
            "982047": {
                "RebD": 31,
                "RebO": 13,
                "T1A": 16,
                "T1M": 11,
                "T2A": 33,
                "T2M": 15,
                "T3A": 27,
                "T3M": 11,
                "TOV": 13
            }
        },
        "rows": 156
    }
}


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
        "extract_possession_rows", "count_quality_pbp_metrics", "order_possession_moves",
        "previous_missed_shot_index", "is_controversial_possession", "is_tab_evaluated_possession",
        "QUALITY_METRICS",
    ):
        assert hasattr(possession_core, name), name
