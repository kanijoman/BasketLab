"""The contract of the Talent publication (B2, #878): what the app reads of ``talent-data`` before it opens a sealed file, declared once like the one of ``web-data`` (#328).

Its manifest is not the one of ``web-data`` (one entry per competition and season, not per collection) and lives in its own branch, so it has its own schema and its own generated types."""
import pytest

from src.local_data.contract import ContractError
from src.market.contract import TALENT_SCHEMA, render_typescript, validate_talent_manifest

WRAP = {"scope": "talent", "iv": "aXY=", "key": "a2V5"}
ENTRY = {"file": "players/x.abc.json", "bytes": 10, "sha256": "ab" * 32, "key": "feb|lfendesa|2025", "league": "feb", "competition": "LF ENDESA", "season": "2025",
         "season_label": "2025/2026", "players": 31, "groups": ["Liga Regular · Único"], "wraps": [WRAP], "gender": "F", "level": 1}
MANIFEST = {"schema": TALENT_SCHEMA, "kind": "talent", "v": 2, "open_key": "b3Blbg==", "competitions": [ENTRY]}


def test_a_valid_manifest_passes_and_the_optional_fields_may_be_missing():
    validate_talent_manifest(MANIFEST)
    validate_talent_manifest({**MANIFEST, "competitions": [{k: v for k, v in ENTRY.items() if k not in ("gender", "level")}]})
    validate_talent_manifest({**MANIFEST, "competitions": []})


@pytest.mark.parametrize("change,where", [
    ({"schema": 99}, "schema"),
    ({"kind": "web-data"}, "kind"),
    ({"competitions": [{**ENTRY, "league": "acb"}]}, "league"),
    ({"competitions": [{**ENTRY, "players": "31"}]}, "players"),
    ({"competitions": [{**ENTRY, "wraps": [{"scope": "talent", "key": "a2V5"}]}]}, "iv"),
    ({"competitions": [{k: v for k, v in ENTRY.items() if k != "sha256"}]}, "sha256"),
])
def test_a_manifest_that_does_not_satisfy_the_contract_says_where(change, where):
    with pytest.raises(ContractError, match=where):
        validate_talent_manifest({**MANIFEST, **change})


def test_the_typescript_reuses_the_shared_types_instead_of_declaring_them_twice():
    ts = render_typescript()
    assert "import type { FileEntry, Wrap } from '@/webdata/contract.generated'" in ts
    assert "export interface TalentManifest" in ts and "export interface TalentCompetitionEntry" in ts
    assert "export interface Wrap" not in ts and f"export const TALENT_SCHEMA = {TALENT_SCHEMA}" in ts
    assert "kind: 'talent'" in ts


def test_the_generated_file_in_the_repository_is_the_current_contract():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "frontend" / "src" / "market" / "contract.generated.ts"
    assert path.read_text(encoding="utf-8").replace("\r\n", "\n") == render_typescript(), "run python run_web_contract.py"
