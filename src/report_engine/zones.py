"""Shot-zone findings: hot / cold zones vs the league average for that zone (issue #141)."""
from typing import Any, Dict, List, Optional

TEXT = {
    ("own", "hot"): "Zona caliente: rinde por encima de la liga en esta zona; conviene buscarla en ataque.",
    ("own", "cold"): "Zona fría: rinde por debajo de la liga; revisar la selección de tiro o trabajar el tiro desde aquí.",
    ("rival", "hot"): "Zona peligrosa: anota por encima de la liga; defenderla con prioridad.",
    ("rival", "cold"): "Zona poco eficiente: dejarle tirar desde aquí, pero sin permitir ventajas en las zonas calientes.",
}
KIND_BY_RATING = {"above": "hot", "below": "cold"}


def zone_findings(zones: Optional[List[Dict[str, Any]]], mode: str) -> List[Dict[str, Any]]:
    out = []
    for z in zones or []:
        kind = KIND_BY_RATING.get(z.get("rating"))
        if not kind:
            continue
        out.append({
            "zone": z["zone"], "label": z.get("zone_label") or z["zone"], "points": z.get("points"),
            "fga": z.get("fga", 0), "fg_pct": z.get("fg_pct"), "league_pct": z.get("league_pct"),
            "delta_pp": z.get("delta_pp"), "low_sample": bool(z.get("low_sample")),
            "kind": kind, "text": TEXT[(mode, kind)],
        })
    return sorted(out, key=lambda x: -abs(x["delta_pp"] or 0.0))
