"""Manager for comparative mode functionality in statistics windows."""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Callable, Any, List
from PyQt6.QtWidgets import QMessageBox

from .stats_filter_constants import (
    RESULT_WON, RESULT_LOST, VENUE_HOME, VENUE_AWAY,
    CACHE_GENERAL, CACHE_MONTHLY, CACHE_REST, CACHE_HOME, CACHE_AWAY, CACHE_WON, CACHE_LOST
)


class ComparativeModeManager:
    """Manages comparative analysis modes with caching and period selection."""

    def __init__(self, reload_callback: Callable, collection_name: str):
        """
        Initialize the comparative mode manager.

        Args:
            reload_callback: Function to reload data with filters (date_filter, venue_filter, result_filter)
            collection_name: Name of the MongoDB collection
        """
        self.reload_callback = reload_callback
        self.collection_name = collection_name
        self._data_cache: Dict[str, Any] = {}
        self._initialize_cache()

    def _initialize_cache(self):
        """Initialize the data cache with default keys."""
        self._data_cache = {
            CACHE_GENERAL: None,
            CACHE_MONTHLY: None,
            CACHE_REST: None,
            CACHE_HOME: None,
            CACHE_AWAY: None,
            CACHE_WON: None,
            CACHE_LOST: None
        }

    def invalidate_cache(self):
        """Clear all cached data to force reload on next period change."""
        self._initialize_cache()

    def load_comparative_period(self, period_type: str, days: int, parent_widget=None) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        """
        Load data for comparative temporal analysis (e.g., last N days vs rest).

        Args:
            period_type: Type of period (e.g., "comparative_30")
            days: Number of days for recent period
            parent_widget: Parent widget for error dialogs

        Returns:
            Tuple of (recent_data, rest_data, comparison_label) or (None, None, None) if failed
        """
        now = datetime.now()
        period_start = now - timedelta(days=days)

        # Use dynamic cache key based on days
        cache_key_recent = f"recent_{days}"
        cache_key_rest = f"rest_{days}"

        # Check cache first
        if cache_key_recent not in self._data_cache or cache_key_rest not in self._data_cache or \
           self._data_cache.get(cache_key_recent) is None or self._data_cache.get(cache_key_rest) is None:
            # Get recent period data
            recent_filter = {"$gte": period_start}
            recent_data = self.reload_callback(
                self.collection_name, date_filter=recent_filter, venue_filter=None, result_filter=None
            )

            # Get rest of season data (before recent period)
            rest_filter = {"$lt": period_start}
            rest_data = self.reload_callback(
                self.collection_name, date_filter=rest_filter, venue_filter=None, result_filter=None
            )

            # Cache the loaded data
            self._data_cache[cache_key_recent] = recent_data
            self._data_cache[cache_key_rest] = rest_data
        else:
            # Use cached data
            recent_data = self._data_cache[cache_key_recent]
            rest_data = self._data_cache[cache_key_rest]

        # Check if data is valid
        if not self._validate_comparative_data(recent_data, rest_data, parent_widget):
            return None, None, None

        # Create comparison label
        period_label = f"últimos {days} días" if days != 30 else "último mes"
        comparison_label = f"{period_label} vs resto temporada"

        return recent_data, rest_data, comparison_label

    def load_venue_comparison(self, parent_widget=None) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        """
        Load data for venue comparison (home vs away).

        Args:
            parent_widget: Parent widget for error dialogs

        Returns:
            Tuple of (home_data, away_data, comparison_label) or (None, None, None) if failed
        """
        # Check cache first
        if self._data_cache[CACHE_HOME] is None or self._data_cache[CACHE_AWAY] is None:
            # Get home data
            home_data = self.reload_callback(
                self.collection_name, date_filter=None, venue_filter=VENUE_HOME, result_filter=None
            )

            # Get away data
            away_data = self.reload_callback(
                self.collection_name, date_filter=None, venue_filter=VENUE_AWAY, result_filter=None
            )

            # Cache the loaded data
            self._data_cache[CACHE_HOME] = home_data
            self._data_cache[CACHE_AWAY] = away_data
        else:
            # Use cached data
            home_data = self._data_cache[CACHE_HOME]
            away_data = self._data_cache[CACHE_AWAY]

        # Check if data is valid
        if not self._validate_comparative_data(home_data, away_data, parent_widget):
            return None, None, None

        comparison_label = "local vs visitante"
        return home_data, away_data, comparison_label

    def load_result_comparison(self, parent_widget=None) -> Tuple[Optional[Any], Optional[Any], Optional[str]]:
        """
        Load data for result comparison (won vs lost games).

        Args:
            parent_widget: Parent widget for error dialogs

        Returns:
            Tuple of (won_data, lost_data, comparison_label) or (None, None, None) if failed
        """
        # Check cache first
        if self._data_cache[CACHE_WON] is None or self._data_cache[CACHE_LOST] is None:
            # Get won games data
            won_data = self.reload_callback(
                self.collection_name, date_filter=None, venue_filter=None, result_filter=RESULT_WON
            )

            # Get lost games data
            lost_data = self.reload_callback(
                self.collection_name, date_filter=None, venue_filter=None, result_filter=RESULT_LOST
            )

            # Cache the loaded data
            self._data_cache[CACHE_WON] = won_data
            self._data_cache[CACHE_LOST] = lost_data
        else:
            # Use cached data
            won_data = self._data_cache[CACHE_WON]
            lost_data = self._data_cache[CACHE_LOST]

        # Check if data is valid
        if not self._validate_comparative_data(won_data, lost_data, parent_widget):
            return None, None, None

        comparison_label = "ganados vs perdidos"
        return won_data, lost_data, comparison_label

    def load_general_data(self, parent_widget=None) -> Optional[Any]:
        """
        Load general (all season) data.

        Args:
            parent_widget: Parent widget for error dialogs

        Returns:
            General data or None if failed
        """
        # Check cache first
        if self._data_cache[CACHE_GENERAL] is None:
            general_data = self.reload_callback(
                self.collection_name, date_filter=None, venue_filter=None, result_filter=None
            )
            # Cache the loaded data
            self._data_cache[CACHE_GENERAL] = general_data
        else:
            # Use cached data
            general_data = self._data_cache[CACHE_GENERAL]

        if not general_data or (isinstance(general_data, (tuple, list)) and len(general_data) == 0):
            if parent_widget:
                QMessageBox.information(parent_widget, "Sin datos", "No hay datos para el período seleccionado")
            return None

        return general_data

    def _validate_comparative_data(self, data1: Any, data2: Any, parent_widget=None) -> bool:
        """
        Validate that comparative data is available.

        Args:
            data1: First dataset
            data2: Second dataset
            parent_widget: Parent widget for error dialogs

        Returns:
            True if both datasets are valid, False otherwise
        """
        # Handle both single values and tuples (for team stats windows that return (team_stats, opponent_stats))
        def is_empty(data):
            if data is None:
                return True
            if isinstance(data, (list, tuple)):
                if len(data) == 0:
                    return True
                # If it's a tuple of (team_stats, opponent_stats), check the first element
                if len(data) == 2 and isinstance(data[0], list):
                    return len(data[0]) == 0
            return False

        if is_empty(data1) or is_empty(data2):
            if parent_widget:
                QMessageBox.information(parent_widget, "Sin datos", "No hay suficientes datos para comparar")
            return False

        return True

    @staticmethod
    def extract_days_from_period_type(period_type: str) -> int:
        """
        Extract number of days from period type string.

        Args:
            period_type: Period type (e.g., "comparative_30")

        Returns:
            Number of days (defaults to 30 if not parseable)
        """
        days = 30  # default
        if "_" in period_type:
            try:
                days = int(period_type.split("_")[1])
            except (ValueError, IndexError):
                days = 30
        return days
