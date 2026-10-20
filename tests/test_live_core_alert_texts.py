"""Texts of the alerts: the message is the situation, the proposals are the actions (issue #421).

Reviewing the alerts with the staff: almost every rule with a proposal said the action twice, as the last sentence of the message and as
the proposal (shown under the message in the app, between brackets in the PDF): "Triples fríos: 1/7 seguidos. Atacar el aro." and
"Atacar el aro, menos triples". The message says what is happening, with its numbers and a short reading; what to do goes in the proposal.
A rule that has no proposal keeps its action in the message.
"""
import re
from collections import namedtuple
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from src.live_core.package import PreparationPackage
from src.live_core.session import LiveSession
from tests.test_live_core_rule_registry import SCENARIOS, _engine

RECORDINGS = Path(__file__).parent / "recordings"
Item = namedtuple("Item", "id message proposals")


def plain(text):
    """The words of a text that are not a name (written in capitals), a number or a symbol, lowercased: what is being said."""
    words = [w for w in re.split(r"[\s,;:.()]+", text) if w and not w.isupper() and not re.search(r"\d|%", w) and len(w) > 1 or w in ("a", "y")]
    return " ".join(w.lower() for w in words if not (len(w) <= 2 and w.endswith(".")))


def sentences(message):
    return [plain(x) for x in re.split(r"[.;:]\s", message) if len(plain(x)) >= 16]


def echoes(message, proposal_text):
    """The proposal says what a sentence of the message already says (one contains the other or they are nearly the same)."""
    p = plain(proposal_text)
    return p in plain(message) or any(s in p or SequenceMatcher(None, s, p).ratio() >= 0.7 for s in sentences(message))


def from_scenarios():
    items = []
    for build, _emits, kw in SCENARIOS.values():
        snapshots = build()
        engine = _engine(**kw)
        for s in (snapshots if isinstance(snapshots, list) else [snapshots]):
            for _ in range(2):
                items += [Item(a.id, a.message, [dict(p) for p in a.proposal]) for a in engine.evaluate(s)]
    return items


def replay(recording, rival=None):
    """The alerts of a recorded match; the package of Zamora-Leon is the one at hand, so for Leon-Unibasket its rival is changed."""
    package = PreparationPackage.loads((RECORDINGS / "2524470.package.json").read_text(encoding="utf-8"))
    if rival:
        package.rival = rival
    session = LiveSession(package.dumps())
    session.load_recording((RECORDINGS / recording).read_bytes())
    items = []
    for t in range(0, 8000, 20):
        out = session.play(t)["output"]
        items += [Item(a["id"], a["message"], a["proposal"]) for a in (out["alerts"] if out else [])]
    return items


def from_the_real_matches():
    return replay("2524470.rec.json.gz") + replay("2524475.rec.json.gz", {"id": "1008895", "name": "BOSONIT UNIBASKET"})


@pytest.fixture(scope="module")
def alerts():
    items = from_scenarios() + from_the_real_matches()
    assert len({i.id for i in items}) >= 30, "the check must see most of the rules"
    return items


def test_no_proposal_repeats_a_sentence_of_its_message(alerts):
    offenders = sorted({(i.id, p["message"]) for i in alerts for p in i.proposals
                        if p.get("type") in ("tactic", "timeout") and p.get("message") and echoes(i.message, p["message"])})
    assert offenders == []


# the sentences that were the action of a rule that has it as a proposal (each is checked on top of the general rule above, because the
# proposal does not always use the same words: "ventana para correr" and "Correr: transición y ritmo alto")
ACTION_SENTENCES = {
    "fg_drought": "atacar el aro", "own_drought": "valorar tiempo muerto", "rival_drought": "ventana para correr", "long_run": "valorar tiempo muerto",
    "rival_run": "valorar tiempo muerto", "cold_3p_streak": "atacar el aro", "cold_3p_volume": "atacar el aro", "cold_fg_streak": "buscar juego interior",
    "rival_3p_streak": "cerrar la línea", "rival_hot_streak": "cambiar la defensa", "own_hot_player": "buscarle", "own_orb_player": "mantenerle en pista",
    "own_cold_player": "cambiar su rol", "rival_hot_run": "2x1", "rival_star_out": "momento de apretar", "own_zone_hot": "insistir por",
    "own_zone_cold": "cambiar la selección", "rival_concedes_zone": "atacar por ahí", "rival_player_zone": "negarle esa zona",
    "rival_foul_pair": "atacarles", "rival_foul_trouble": "atacarle", "rival_no_timeouts": "presionar hasta el final",
    "rival_scores_after_timeout": "preparar la defensa", "static_offense": "mover el balón", "advantage_management": "gastar reloj",
    "comeback_plan": "posesiones extra", "period_edge_deficit": "cuidar los últimos", "period_summary": "ajustes:",
    "disqualification_risk": "sin riesgo", "key_fouls_close": "defensa sin riesgo", "ft_cold": "el balón a los buenos", "paint_battle": "cerrar la zona",
}


@pytest.mark.parametrize("rule_id, phrase", sorted(ACTION_SENTENCES.items()))
def test_the_message_of_a_rule_with_proposals_does_not_carry_the_action(alerts, rule_id, phrase):
    messages = [i.message for i in alerts if i.id == rule_id and i.proposals]
    assert messages, f"{rule_id} must fire with a proposal in the scenarios or in the real match"
    assert not [m for m in messages if phrase in m.lower()]
