"""Regression tests for IN/OUT OOM prevention.

Before the fix, _games_with_playbyplay_feb/fbcyl() called
list(collection.find(...)) with NO field projection, loading entire game
documents (including all stats, lineups, etc.) into memory at once.
For a full season this caused OOM errors.

After the fix:
- Both methods apply a field projection (only PBP + minimal team/player
  fields are fetched).
- get_games_with_playbyplay() returns the pymongo cursor directly (lazy)
  instead of materialising it with list().
- A new count_games_with_playbyplay() method uses count_documents() to
  get the total without loading documents.
"""

import pytest
from unittest.mock import MagicMock, call, patch
from pymongo.cursor import Cursor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(collection_name="lf2_2025"):
    """Create a BasketballRepository with a mocked connection/collection."""
    from src.database.repository import BasketballRepository

    mock_cursor = MagicMock(spec=Cursor)
    mock_collection = MagicMock()
    mock_collection.find.return_value = mock_cursor
    mock_collection.aggregate.return_value = mock_cursor
    mock_collection.count_documents.return_value = 30

    mock_connection = MagicMock()
    mock_connection.is_connected.return_value = True
    mock_connection.get_collection.return_value = mock_collection
    mock_connection.ensure_indexes.return_value = None

    repo = BasketballRepository(mock_connection)
    return repo, mock_collection, mock_cursor


# ---------------------------------------------------------------------------
# Field projection — FEB
# ---------------------------------------------------------------------------

class TestFEBProjection:
    """_games_with_playbyplay_feb must pass a projection to collection.find()."""

    def test_projection_applied_on_find_regression(self):
        """find() must be called with a projection dict, not without one."""
        repo, mock_col, _ = _make_repo("lf2_2025")
        repo.get_games_with_playbyplay("lf2_2025")

        assert mock_col.find.called or mock_col.aggregate.called, (
            "Expected find() or aggregate() to be called"
        )
        if mock_col.find.called:
            _, kwargs = mock_col.find.call_args
            args_list = mock_col.find.call_args[0]
            # projection is either a positional arg (2nd) or keyword arg
            projection = (
                kwargs.get("projection")
                or (args_list[1] if len(args_list) > 1 else None)
            )
            assert projection is not None, (
                "find() must be called with a projection to avoid loading "
                "entire game documents (OOM prevention)"
            )

    def test_projection_includes_playbyplay_lines(self):
        """FEB projection must include PLAYBYPLAY.LINES (required for analysis)."""
        repo, mock_col, _ = _make_repo("lf2_2025")
        repo.get_games_with_playbyplay("lf2_2025")

        if mock_col.find.called:
            args_list = mock_col.find.call_args[0]
            kwargs = mock_col.find.call_args[1]
            projection = kwargs.get("projection") or (
                args_list[1] if len(args_list) > 1 else {}
            )
            assert any("PLAYBYPLAY" in str(k) for k in projection), (
                "FEB projection must include PLAYBYPLAY.LINES"
            )

    def test_projection_excludes_large_unnecessary_fields(self):
        """FEB projection must NOT include fields that are not needed for PBP analysis."""
        repo, mock_col, _ = _make_repo("lf2_2025")
        repo.get_games_with_playbyplay("lf2_2025")

        if mock_col.find.called:
            args_list = mock_col.find.call_args[0]
            kwargs = mock_col.find.call_args[1]
            projection = kwargs.get("projection") or (
                args_list[1] if len(args_list) > 1 else {}
            )
            # BOXSCORE.TEAM.TOTAL is large and not needed for PBP
            assert "BOXSCORE.TEAM.TOTAL" not in projection, (
                "Projection must not include BOXSCORE.TEAM.TOTAL (bloats document)"
            )


# ---------------------------------------------------------------------------
# Field projection — FBCYL
# ---------------------------------------------------------------------------

class TestFBCYLProjection:
    """_games_with_playbyplay_fbcyl must pass a projection to collection.find()."""

    def test_projection_applied_on_find_regression(self):
        """find() must be called with a projection dict for FBCYL collections."""
        repo, mock_col, _ = _make_repo("FBCYL_LF2_2025")
        repo.get_games_with_playbyplay("FBCYL_LF2_2025")

        assert mock_col.find.called or mock_col.aggregate.called
        if mock_col.find.called:
            args_list = mock_col.find.call_args[0]
            kwargs = mock_col.find.call_args[1]
            projection = kwargs.get("projection") or (
                args_list[1] if len(args_list) > 1 else None
            )
            assert projection is not None, (
                "FBCYL find() must be called with a projection (OOM prevention)"
            )

    def test_projection_includes_moves(self):
        """FBCYL projection must include 'moves' (required for PBP analysis)."""
        repo, mock_col, _ = _make_repo("FBCYL_LF2_2025")
        repo.get_games_with_playbyplay("FBCYL_LF2_2025")

        if mock_col.find.called:
            args_list = mock_col.find.call_args[0]
            kwargs = mock_col.find.call_args[1]
            projection = kwargs.get("projection") or (
                args_list[1] if len(args_list) > 1 else {}
            )
            assert "moves" in projection, (
                "FBCYL projection must include 'moves'"
            )


# ---------------------------------------------------------------------------
# Cursor is not materialised into a list
# ---------------------------------------------------------------------------

class TestCursorNotMaterialised:
    """get_games_with_playbyplay must return the cursor, not list(cursor)."""

    def test_feb_returns_cursor_not_list_regression(self):
        """get_games_with_playbyplay for FEB must not call list() on the cursor.

        Before the fix, list(collection.find(...)) loaded all documents into
        RAM.  After the fix the raw cursor is returned and callers iterate it.
        """
        repo, mock_col, mock_cursor = _make_repo("lf2_2025")

        result = repo.get_games_with_playbyplay("lf2_2025")

        # The returned object must be iterable but NOT a plain Python list
        assert not isinstance(result, list), (
            "get_games_with_playbyplay must return a cursor, not a materialised "
            "list. Returning list() causes OOM for large collections."
        )

    def test_fbcyl_returns_cursor_not_list_regression(self):
        """get_games_with_playbyplay for FBCYL must not call list() on the cursor."""
        repo, mock_col, mock_cursor = _make_repo("FBCYL_LF2_2025")

        result = repo.get_games_with_playbyplay("FBCYL_LF2_2025")

        assert not isinstance(result, list), (
            "FBCYL: get_games_with_playbyplay must return a cursor, not a list."
        )


# ---------------------------------------------------------------------------
# count_games_with_playbyplay
# ---------------------------------------------------------------------------

class TestCountGamesWithPlaybyplay:
    """count_games_with_playbyplay must use count_documents() without loading docs."""

    def test_method_exists(self):
        """count_games_with_playbyplay method must exist on the repository."""
        from src.database.repository import BasketballRepository
        assert hasattr(BasketballRepository, "count_games_with_playbyplay"), (
            "Missing count_games_with_playbyplay method"
        )

    def test_uses_count_documents_not_find_regression(self):
        """count_games_with_playbyplay must use count_documents(), not find()."""
        repo, mock_col, _ = _make_repo("lf2_2025")
        mock_col.count_documents.return_value = 25

        count = repo.count_games_with_playbyplay("lf2_2025")

        assert mock_col.count_documents.called, (
            "count_documents() must be called (not find()) so that no documents "
            "are loaded into memory"
        )
        assert not mock_col.find.called, (
            "find() must NOT be called inside count_games_with_playbyplay"
        )
        assert count == 25

    def test_returns_zero_when_not_connected(self):
        """Returns 0 when the DB is not connected (no crash)."""
        from src.database.repository import BasketballRepository

        mock_connection = MagicMock()
        mock_connection.is_connected.return_value = False
        repo = BasketballRepository(mock_connection)

        count = repo.count_games_with_playbyplay("lf2_2025")

        assert count == 0

    def test_feb_and_fbcyl_both_supported(self):
        """Works for both FEB and FBCYL collections."""
        repo_feb, col_feb, _ = _make_repo("lf2_2025")
        col_feb.count_documents.return_value = 20
        assert repo_feb.count_games_with_playbyplay("lf2_2025") == 20

        repo_fbcyl, col_fbcyl, _ = _make_repo("FBCYL_LF2_2025")
        col_fbcyl.count_documents.return_value = 18
        assert repo_fbcyl.count_games_with_playbyplay("FBCYL_LF2_2025") == 18
