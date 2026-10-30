"""The list and the analysis of every match of a competition, for the web (#677).

The same service the endpoints call (``MatchAnalysisService``): a match analysis is a head-to-head of two box scores, a few KB, and the 271 matches of the biggest league take
under two seconds and 0.11 MB compressed. Computed once at publication, the page reads the list and each analysis from one file and the figures cannot differ from the API's.
"""
from __future__ import annotations

import json
from typing import Any, Dict

from src.local_data.export import FORMAT
from src.utils.collection_utils import is_fbcyl


def export_matches(handler: Any, name: str) -> Dict[str, Any]:
    """``matches``: for every match of ``name`` (in the order of the collection) its list entry plus its ``analysis``."""
    from src.services.match_analysis_service import MatchAnalysisService

    fbcyl = is_fbcyl(name)
    service = MatchAnalysisService(handler, name)
    matches = []
    for summary in service.get_match_list(fbcyl):
        analysis = service.get_match_analysis(summary["match_id"], fbcyl)
        matches.append(json.loads(json.dumps({**summary, "analysis": analysis}, default=str)))
    return {"format": FORMAT, "collection": name, "league": "fbcyl" if fbcyl else "feb", "games": len(matches), "matches": matches}
