"""Structured data of the competition of each published collection (issue #438, epic #435).

The app listed and filtered matches parsing the name of the collection. The index now carries ``competition: {key, label, competition,
group, season, level, gender}`` per entry: names come from the scrape metadata (``COLLECTION_META``), ``level``/``gender``/``clubs``/``rule_config`` (and ``group_rules``: rules of the groups that name it, e.g. the knockout phases of a cup) from the
``competitions`` catalog of ``config/package_publish.json`` (matched by competition name, case and punctuation ignored). ``clubs`` are the
clubs whose packages are prepared in that competition (not published). "De interés" teams are NOT here: the user marks them in the app.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

GENDERS = ("M", "F")


def _norm(name: str) -> str:
    from src.scraper.schedule_client import normalize_name

    return normalize_name(name)


def _checked_rule_config(position: int, value: Any) -> Dict[str, Any]:
    """A ``rule_config`` written in the catalog: ``RuleConfig`` fields with known ``rules_off`` (the engine would silently ignore a typo)."""
    from dataclasses import fields

    from src.live_core.config import RuleConfig, unknown_rule_ids

    if not isinstance(value, dict):
        raise ValueError(f"competitions entry #{position}: rule_config must be an object")
    unknown = sorted(set(value) - {f.name for f in fields(RuleConfig)})
    if unknown:
        raise ValueError(f"competitions entry #{position}: rule_config has unknown fields: {', '.join(unknown)}")
    off = value.get("rules_off", [])
    if not isinstance(off, list) or unknown_rule_ids(off):
        raise ValueError(f"competitions entry #{position}: rule_config.rules_off must be a list of known rule ids")
    return dict(value)


def _checked_group_rules(position: int, value: Any) -> List[Dict[str, Any]]:
    """``group_rules``: ``[{"group": <text of the group label>, "rule_config": {...}}]``; a group that matches adds its rules to the competition's (#481)."""
    if not isinstance(value, list):
        raise ValueError(f"competitions entry #{position}: group_rules must be a list")
    out = []
    for n, rule in enumerate(value, start=1):
        if not isinstance(rule, dict) or not isinstance(rule.get("group"), str) or not rule["group"].strip() or "rule_config" not in rule:
            raise ValueError(f"competitions entry #{position}: group_rules #{n} needs a group (text of the group label) and a rule_config")
        try:
            out.append({"group": rule["group"], "rule_config": _checked_rule_config(position, rule["rule_config"])})
        except ValueError as exc:
            raise ValueError(f"competitions entry #{position}: group_rules #{n}: {exc}") from exc
    return out


def _rules_of(entry: Dict[str, Any], group: str) -> Dict[str, Any]:
    """The competition's ``rule_config`` plus, in order, the ones of every ``group_rules`` whose text is in the group label (case and accents ignored)."""
    rules = dict(entry.get("rule_config") or {})
    for rule in entry.get("group_rules") or []:
        if _norm(rule["group"]) in _norm(group):
            rules.update(rule["rule_config"])
    return rules


def normalize_catalog(entries: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Validated ``competitions`` entries of the config (``ValueError`` naming the position of a bad one)."""
    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(entries or [], start=1):
        name = raw.get("competition")
        level, gender, clubs = raw.get("level"), raw.get("gender"), raw.get("clubs", [])
        if not name or not isinstance(name, str):
            raise ValueError(f"competitions entry #{i} lacks: competition")
        if level is not None and (isinstance(level, bool) or not isinstance(level, int)):
            raise ValueError(f"competitions entry #{i}: level must be an integer")
        if gender is not None and gender not in GENDERS:
            raise ValueError(f"competitions entry #{i}: gender must be one of {GENDERS}")
        if not isinstance(clubs, list):
            raise ValueError(f"competitions entry #{i}: clubs must be a list of team ids")
        rule_config = _checked_rule_config(i, raw["rule_config"]) if "rule_config" in raw else {}
        out.append({"competition": name, "level": level, "gender": gender, "clubs": [str(c) for c in clubs], "rule_config": rule_config,
                    "group_rules": _checked_group_rules(i, raw.get("group_rules", []))})
    return out


def _meta(db: Any, collection: str) -> Dict[str, Any]:
    try:
        return db.repository.connection.get_collection("COLLECTION_META").find_one({"_id": collection}) or {}
    except Exception:  # noqa: BLE001 - labels are optional: a database that cannot answer never stops the publication
        return {}


def competition_infos(db: Any, collections: Iterable[str], catalog: List[Dict[str, Any]], default_clubs: List[str]) -> Dict[str, Dict[str, Any]]:
    """``{collection: info}``; a collection without metadata is labelled with its own name and a competition not in the catalog has no level/gender."""
    by_name = {_norm(c["competition"]): c for c in catalog}
    out: Dict[str, Dict[str, Any]] = {}
    for collection in collections:
        meta = _meta(db, collection)
        competition = meta.get("competition_label") or collection
        group = meta.get("group_label") or ""
        entry = by_name.get(_norm(competition), {})
        out[collection] = {
            "key": collection, "label": f"{competition} · {group}" if group else competition, "competition": competition, "group": group,
            "season": meta.get("season_label") or "", "level": entry.get("level"), "gender": entry.get("gender"),
            "clubs": list(entry.get("clubs") or default_clubs), "rule_config": {**({"gender": entry["gender"]} if entry.get("gender") else {}), **_rules_of(entry, group)},
        }
    return out


def public(info: Dict[str, Any]) -> Dict[str, Any]:
    """What goes in the index: everything but the clubs whose packages are prepared and the rules (those travel inside each package)."""
    return {k: v for k, v in info.items() if k not in ("clubs", "rule_config")}
