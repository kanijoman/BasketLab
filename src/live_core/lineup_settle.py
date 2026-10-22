"""When the lineup on court can be trusted (issue #413).

FEB writes the substitutions of a stoppage some seconds after the dead ball, with the clock of the stoppage: a poll in between sees the
old five on court. The rules that speak about who is playing wait while a stoppage is going on: the last event is a stoppage (a timeout, a
foul, a free throw, a substitution, the end of a period) or the game clock has not moved since the previous poll (the ball is dead: the
clock of the header is real time, the lines of the play-by-play come late, so the delay between them says nothing). What waits is not lost:
the key of an alert is stored only when it is emitted, so it comes with the first polls in which the clock runs if it is still true (and, as the
first poll after a dead ball still has the old five, a lineup alert has to show in two polls in a row: ``AdviceEngine.evaluate``).
Standard library only.
"""

from __future__ import annotations

from typing import Any, Dict

# the rules whose alerts name a player or a lineup on court (their ids in ``RULE_IDS``)
# ``formation_lineup`` too (#481): a block of substitutions is several lines written one after the other (a formación player who comes in for a
# formación player arrives after the non-formación one who comes in for another), so the five are checked at the next play, when the block is complete
LINEUP_RULES = frozenset({"fatigue_high", "player_plus_minus", "lineup_net", "rest_starters", "formation_lineup"})
# events after which the substitutions of the stoppage may still be to be written
STOPPAGE_KINDS = frozenset({"timeout", "foul", "ft", "sub_in", "sub_out", "period_end"})


def lineup_unsettled(snapshot: Dict[str, Any]) -> bool:
    """True while lines of a stoppage may still be missing. A snapshot that does not say its last event (older engines, tests) is settled."""
    last = snapshot.get("last_event")
    return bool(last) and last["kind"] in STOPPAGE_KINDS
