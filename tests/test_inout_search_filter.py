"""Tests for player search/filter functionality in InOutAnalysisWindow.

All tests mock Qt widgets so no QApplication is needed (Qt UI is deprecated).
"""

from unittest.mock import MagicMock, call, patch


class TestFilterPlayersCombo:
    """Unit tests for _filter_players_combo using mocked QComboBox."""

    PLAYERS = [
        ("García López, Pedro", "p1"),
        ("Martínez Ruiz, Juan", "p2"),
        ("García Sánchez, Luis", "p3"),
        ("López Torres, Carlos", "p4"),
    ]

    def _make_window(self):
        """Build a minimal stub with _filter_players_combo and team_players."""
        from src.ui.inout_analysis_window import InOutAnalysisWindow
        with patch.object(InOutAnalysisWindow, "__init__", lambda self, *a, **kw: None):
            win = InOutAnalysisWindow.__new__(InOutAnalysisWindow)
        win.team_combo = MagicMock()
        win.team_combo.currentText.return_value = "Equipo A"
        win.team_players = {"Equipo A": list(self.PLAYERS)}
        return win

    def _make_combo(self):
        """Return a MagicMock that tracks addItem calls."""
        combo = MagicMock()
        combo.addItem = MagicMock()
        return combo

    def _added_names(self, combo):
        return [c.args[0] for c in combo.addItem.call_args_list]

    def _added_ids(self, combo):
        return [c.args[1] for c in combo.addItem.call_args_list]

    def test_search_filters_combo_by_name(self):
        """Only players whose name contains the search text are added."""
        win = self._make_window()
        combo = self._make_combo()
        win._filter_players_combo("García", combo)
        names = self._added_names(combo)
        assert len(names) == 2
        assert all("García" in n for n in names)

    def test_search_case_insensitive(self):
        """Search is case-insensitive."""
        win = self._make_window()
        combo = self._make_combo()
        win._filter_players_combo("garcía", combo)
        assert len(self._added_names(combo)) == 2

    def test_search_empty_restores_all_players(self):
        """Empty search text adds all players for the current team."""
        win = self._make_window()
        combo = self._make_combo()
        win._filter_players_combo("", combo)
        assert len(self._added_names(combo)) == 4

    def test_player_id_preserved_after_filter(self):
        """After filtering, the correct player_id is passed to addItem."""
        win = self._make_window()
        combo = self._make_combo()
        win._filter_players_combo("Martínez", combo)
        names = self._added_names(combo)
        ids = self._added_ids(combo)
        assert names == ["Martínez Ruiz, Juan"]
        assert ids == ["p2"]

    def test_search_no_match_yields_no_items(self):
        """A search with no matches results in no addItem calls."""
        win = self._make_window()
        combo = self._make_combo()
        win._filter_players_combo("XxXNoExiste", combo)
        combo.addItem.assert_not_called()

    def test_signals_blocked_during_update(self):
        """blockSignals(True) is called before clear and False after."""
        win = self._make_window()
        combo = self._make_combo()
        win._filter_players_combo("García", combo)
        calls = combo.blockSignals.call_args_list
        assert calls[0] == call(True)
        assert calls[-1] == call(False)
