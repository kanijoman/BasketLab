"""Pytest configuration for BasketLab tests."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import mongomock
import pytest

# Add src/ to Python path so imports work correctly
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

SAMPLES_DIR = Path(__file__).parent.parent / "src" / "JSON_samples"


# ---------------------------------------------------------------------------
# Cache isolation — clear module-level TTLCaches before every test to prevent
# cross-test contamination.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_module_caches():
    """Clear all module-level TTLCaches before each test to prevent
    cross-test cache contamination.

    The same module may be registered under different aliases in sys.modules
    depending on which sys.path entry resolves first — clear all known variants.
    """
    _cache_attr = "_player_stats_cache"
    for _mod_path in ("services.player_stats_service", "src.services.player_stats_service"):
        _mod = sys.modules.get(_mod_path)
        if _mod is not None and hasattr(_mod, _cache_attr):
            getattr(_mod, _cache_attr).clear()
    yield


# ---------------------------------------------------------------------------
# Raw JSON fixtures (loaded once per session for speed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def feb_game_doc():
    """Single FEB game document as a Python dict (from JSON sample)."""
    with open(SAMPLES_DIR / "feb_game.json", encoding="utf-8") as f:
        doc = json.load(f)
    # Convert $numberInt / $oid wrappers that MongoDB stores as extended JSON
    _unwrap_extended_json(doc)
    return doc


@pytest.fixture(scope="session")
def fbcyl_game_doc():
    """Single FBCYL game document as a Python dict (from JSON sample)."""
    with open(SAMPLES_DIR / "fbcyl_game.json", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# mongomock database fixtures (fresh per test function)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_feb_db(feb_game_doc):
    """In-memory MongoDB client with one FEB game inserted."""
    client = mongomock.MongoClient()
    db = client["basketlab_test"]
    db["FEB_LF2_2025_A"].insert_one(dict(feb_game_doc))
    return db


@pytest.fixture
def mock_fbcyl_db(fbcyl_game_doc):
    """In-memory MongoDB client with one FBCYL game inserted."""
    client = mongomock.MongoClient()
    db = client["basketlab_test"]
    db["FBCYL_SE_2025_A"].insert_one(dict(fbcyl_game_doc))
    return db


# ---------------------------------------------------------------------------
# Mock connection helper (wraps mongomock db as a MongoDBHandler-compatible object)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_feb_connection(mock_feb_db):
    """Mock MongoDBHandler connected to the FEB in-memory database."""
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.db = mock_feb_db
    conn.get_collection.side_effect = lambda name: mock_feb_db[name]
    return conn


@pytest.fixture
def mock_fbcyl_connection(mock_fbcyl_db):
    """Mock MongoDBHandler connected to the FBCYL in-memory database."""
    conn = MagicMock()
    conn.is_connected.return_value = True
    conn.db = mock_fbcyl_db
    conn.get_collection.side_effect = lambda name: mock_fbcyl_db[name]
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unwrap_extended_json(obj):
    """Recursively replace MongoDB Extended JSON wrappers with plain Python values.

    Handles ``{"$numberInt": "123"}`` → ``123``,
    ``{"$numberDouble": "1.5"}`` → ``1.5``,
    ``{"$oid": "abc"}`` → ``"abc"``.
    """
    if isinstance(obj, dict):
        if "$numberInt" in obj:
            return int(obj["$numberInt"])
        if "$numberDouble" in obj:
            return float(obj["$numberDouble"])
        if "$oid" in obj:
            return obj["$oid"]
        for key in list(obj):
            obj[key] = _unwrap_extended_json(obj[key])
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = _unwrap_extended_json(item)
    return obj
