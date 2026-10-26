"""The box score of the live engine against the official FEB PDF, player by player (issue #593).

``tests/fixtures/feb_pdf_player_ground_truth.json`` has what the PDF says of every player of 4 recorded matches (2 of LF Challenge/LF2 2026-27 and 2 of 2ª/3ª FEB):
fouls committed and drawn (the ``Rec`` of the column ``FP/FT``), the valuation (``VAL``), the blocks received (``TAP Rec``) and the plus/minus. Extracted with
``pdftotext -raw`` (docs/DATA_FORMATS.md) and matched to the player ids of the recording by order, checked with the points of each player. The engine reads the fouls
a player draws from the licence the foul line carries, and its valuation leaves out the blocks received (the decision of the user, issue #593): it differs from
the PDF by exactly those blocks.
"""
import json
from pathlib import Path

import pytest

from src.live_core.engine import LiveEngine
from src.live_core.recorded_feed import RecordedFeed

ROOT = Path(__file__).parent
GROUND_TRUTH = json.loads((ROOT / "fixtures" / "feb_pdf_player_ground_truth.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def final_snapshots():
    out = {}
    for code in GROUND_TRUTH:
        feed, engine, snap = RecordedFeed.load(ROOT / "recordings" / f"{code}.rec.json.gz"), LiveEngine(), None
        for frame in feed.frames:
            snap = engine.update(feed.document_at(frame["t"]))
        out[code] = snap
    return out


@pytest.mark.parametrize("code", sorted(GROUND_TRUTH))
def test_the_fouls_each_player_draws_are_the_ones_of_the_pdf(code, final_snapshots):
    players = final_snapshots[code]["players"]
    wrong = {pid: (v["fd"], players[pid]["fd"]) for pid, v in GROUND_TRUTH[code].items() if players[pid]["fd"] != v["fd"]}
    assert not wrong, f"fouls drawn (PDF, engine) that differ: {wrong}"


@pytest.mark.parametrize("code", sorted(GROUND_TRUTH))
def test_the_fouls_each_player_commits_are_the_ones_of_the_pdf(code, final_snapshots):
    players = final_snapshots[code]["players"]
    wrong = {pid: (v["pf"], players[pid]["pf"]) for pid, v in GROUND_TRUTH[code].items() if players[pid]["pf"] != v["pf"]}
    assert not wrong, f"fouls committed (PDF, engine) that differ: {wrong}"


@pytest.mark.parametrize("code", sorted(GROUND_TRUTH))
def test_the_valuation_is_the_one_of_the_pdf_leaving_out_the_blocks_received(code, final_snapshots):
    """The PDF is built from the official box score and the engine from the play-by-play, which differ by one action in a few players (assists and rebounds, docs/evaluaciones/
    2026-10-16_pdf-ground-truth.md): exact in at least 95 % of the players and never off by more than one."""
    from src.live_core.boxscore import build
    from src.live_core.config import RuleConfig

    box = build(final_snapshots[code], {}, RuleConfig())
    gap = {pid: box[pid]["val"] - (v["val"] + v["blk_rec"]) for pid, v in GROUND_TRUTH[code].items()}
    assert max(abs(g) for g in gap.values()) <= 1, f"engine - (PDF + blocks received): {gap}"
    assert sum(1 for g in gap.values() if g) <= 0.05 * len(gap) + 1, f"too many players differ: {gap}"


def test_the_plus_minus_is_the_one_of_the_pdf_up_to_the_order_of_the_lines_of_one_second(final_snapshots):
    """The engine credits a basket to who is on court in the ORDER OF THE LINES; FEB's box score does not always agree when a substitution and free throws share the clock
    (tried: putting substitutions or free throws first is worse: 77 of 90 players exact in this order, 29 to 49 with any other). Guard: 3 of 4 exact, never off by more than 4."""
    gaps = [final_snapshots[code]["players"][pid]["pm"] - v["pm"] for code, g in GROUND_TRUTH.items() for pid, v in g.items()]
    assert max(abs(g) for g in gaps) <= 4
    assert sum(1 for g in gaps if g == 0) >= 0.75 * len(gaps)
