"""The IN/OUT and the lineup calculators count every play-by-play action as they did before the refactor of #200 (block 6 of #452).

Characterization, not specification: ``tests/fixtures/inout_lineup_golden.json.gz`` holds what the code did with each case of ``tests/pbp_stat_corpus.py``
(55 k cases: FEB texts × types × log params × teams × the previous shot × the last missed shot, every FBCYL move, and the IN/OUT of each player and
the lineups of a real FBCYL match). A refactor must leave it
untouched; a change of a counting rule on purpose regenerates it (``python tests/pbp_stat_corpus.py``) and says so in the commit.
"""
import json

from tests import pbp_stat_corpus as corpus


def test_every_action_is_counted_as_before():
    golden, now = corpus.read_golden(), corpus.corpus()
    assert now.keys() == golden.keys()
    different = [k for k in golden if now[k] != golden[k]]
    shown = "\n".join(f"{k}\n  before: {json.dumps(golden[k])}\n  now:    {json.dumps(now[k])}" for k in different[:5])
    assert not different, f"{len(different)} of {len(golden)} cases changed; first ones:\n{shown}"


def test_the_corpus_covers_both_formats_and_every_counting_function():
    kinds = {json.loads(k)[0] for k in corpus.read_golden()}
    assert kinds == {"io.points", "io.feb", "io.fbcyl", "io.list", "lineup.feb", "lineup.fbcyl", "lineup.feb.seq", "lineup.fbcyl.seq", "io.game", "lineup.game"}
