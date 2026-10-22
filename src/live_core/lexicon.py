"""The words of the alerts that agree with the gender of the competition (issue #475, feedback of 0.3.2).

The package says it (``rule_config.gender``: ``F`` or ``M``, from the catalog of the publisher). The feminine is used only when it is ``F``; in doubt (nothing
said, an older package) the neutral, which is the masculine. Standard library only (it runs on the tablet with the engine).
"""

from __future__ import annotations

from typing import Any


def feminine(config: Any) -> bool:
    return getattr(config, "gender", "") == "F"


def jugador(config: Any) -> str:
    return "jugadora" if feminine(config) else "jugador"


def jugadores(config: Any) -> str:
    return "jugadoras" if feminine(config) else "jugadores"


def pronoun(config: Any) -> str:
    """«ella» / «él»."""
    return "ella" if feminine(config) else "él"


def object_pronoun(config: Any) -> str:
    """«la» / «lo» (atacarla / atacarlo)."""
    return "la" if feminine(config) else "lo"


def other(config: Any) -> str:
    """«otra» / «otro» (el cambio debe ser por otra/otro de formación)."""
    return "otra" if feminine(config) else "otro"
