"""``get_player_in_out_stats`` of the repository returns what it did before its refactor (#200, second PR).

Characterization, not specification: ``tests/fixtures/inout_repository_golden.json`` holds what the code did with each scenario of
``tests/inout_repo_corpus.py`` (43 scenarios: a real FBCYL match with every player, two games, a team without players, a phantom player, a player
without minutes, the surnames fallback; a FEB game with every minutes format, the rival without players, a player not found; no connection).
It pins, among others, the bug of #818 (the FBCYL «IN» side comes out at zero): the arreglo changes those scenarios and regenerates the file in its
commit (``PYTHONPATH=".;src" python tests/inout_repo_corpus.py``). A refactor must leave it as it is.
"""
import json

from tests import inout_repo_corpus as corpus


def test_every_scenario_returns_what_it_did_before():
    golden, now = corpus.read_golden(), json.loads(json.dumps(corpus.corpus(), ensure_ascii=False, default=str))
    assert now.keys() == golden.keys()
    different = [k for k in golden if now[k] != golden[k]]
    shown = "\n".join(f"{k}\n  before: {json.dumps(golden[k])[:400]}\n  now:    {json.dumps(now[k])[:400]}" for k in different[:3])
    assert not different, f"{len(different)} of {len(golden)} scenarios changed; first ones:\n{shown}"


def test_the_scenarios_cover_the_skips_and_the_early_returns():
    golden = corpus.read_golden()
    assert golden["not connected"]["result"] == {}
    assert golden["feb player not found"]["result"] == {}
    assert golden["fbcyl team without players"]["result"]["games_analyzed"] == 0
    assert golden["fbcyl phantom"]["result"]["in"]["games"] == 0           # inscribed, never played: not a game of the player
    assert golden["feb two games"]["result"]["games_analyzed"] == 2
