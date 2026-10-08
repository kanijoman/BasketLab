"""Shared types for rules and the advice engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import RuleConfig

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Advice:
    key: str                       # identity for dedupe: the same key is not emitted twice
    id: str                        # rule id
    severity: str                  # "critical" | "warning" | "info"
    category: str                  # "faltas" | "rotacion" | "gestion" ...
    message: str                   # Spanish, for the staff
    evidence: Dict[str, Any] = field(default_factory=dict)
    proposal: List[Dict[str, Any]] = field(default_factory=list)
    rearm_s: Optional[int] = None  # None: once; N: may be emitted again after N game-seconds


@dataclass(frozen=True)
class RuleContext:
    own_team_id: str
    rival_team_id: Optional[str]
    config: RuleConfig
    baselines: Dict[str, Dict[str, Any]]   # player id -> season baselines (from the package)
    model: Optional[Any] = None            # FourFactorsModel (None without a rival)
    rival_baselines: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # rival player id -> baselines
    impact_league: Dict[str, float] = field(default_factory=dict)             # league per-40 means
    zone_ref: Dict[str, Any] = field(default_factory=dict)                    # {"rival": {zone: cell}, "league": {...}}
