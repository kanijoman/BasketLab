"""Trend calculator for comparative statistics analysis."""

from typing import Dict, Tuple, List
from .stats_config import TREND_THRESHOLDS, TREND_COLORS, LOWER_IS_BETTER_FIELDS


class TrendCalculator:
    """
    Calculates statistical trends and provides visual indicators.

    This class handles:
    - Delta calculation between two periods
    - Trend symbol determination based on thresholds
    - Color assignment for visual indicators
    """

    def __init__(self):
        """Initialize the trend calculator with configuration."""
        self.thresholds = TREND_THRESHOLDS
        self.colors = TREND_COLORS
        self.lower_is_better = LOWER_IS_BETTER_FIELDS

    def calculate_deltas(self, monthly: Dict, rest: Dict, fields: List[str]) -> Dict[str, float]:
        """
        Calculate percentage deltas for all numeric fields.

        Args:
            monthly: Statistics for the monthly period
            rest: Statistics for the rest of the season
            fields: List of field names to calculate deltas for

        Returns:
            Dictionary mapping field names to percentage deltas
        """
        deltas = {}

        for field in fields:
            if field not in monthly or field not in rest:
                continue

            monthly_val = monthly.get(field)
            rest_val = rest.get(field)

            # Skip if either value is None
            if monthly_val is None or rest_val is None:
                continue

            # Convert to float to ensure numeric operations
            try:
                monthly_val = float(monthly_val)
                rest_val = float(rest_val)
            except (ValueError, TypeError):
                continue

            # Calculate percentage change
            if rest_val != 0:
                delta = ((monthly_val - rest_val) / rest_val) * 100
            else:
                delta = 0 if monthly_val == 0 else 100

            deltas[field] = delta

        return deltas

    def get_trend_indicator(self, delta: float, field: str, is_opponent: bool = False) -> Tuple[str, str]:
        """
        Get trend indicator symbol and color based on delta percentage.

        Args:
            delta: Percentage change (positive = increase, negative = decrease)
            field: Field name to determine if higher is better
            is_opponent: Whether this is for opponent stats (inverts logic)

        Returns:
            Tuple of (symbol, color) where color is HTML color code
        """
        # Determine if this field benefits from increase or decrease
        increase_is_good = field not in self.lower_is_better

        # For opponent stats, invert the logic
        if is_opponent:
            increase_is_good = not increase_is_good

        # Check thresholds
        abs_delta = abs(delta)

        if abs_delta < self.thresholds['minimal']:
            return ("≈", self.colors['minimal'])

        # Determine if change is positive or negative for this field
        is_positive_change = (delta > 0 and increase_is_good) or (delta < 0 and not increase_is_good)

        # Significant change (>10%)
        if abs_delta >= self.thresholds['significant']:
            if is_positive_change:
                return ("⇈", self.colors['significant_good'])
            else:
                return ("⇊", self.colors['significant_bad'])

        # Moderate change (5-10%)
        if is_positive_change:
            return ("↑", self.colors['moderate_good'])
        else:
            return ("↓", self.colors['moderate_bad'])

    def get_no_data_indicator(self) -> Tuple[str, str]:
        """
        Get indicator for missing data.

        Returns:
            Tuple of (symbol, color) for no data case
        """
        return ("—", self.colors['no_data'])

    def get_legend_items(self) -> List[Tuple[str, str, str]]:
        """
        Get legend items for display in UI.

        Returns:
            List of tuples (symbol, description, color)
        """
        return [
            ("⇈", "Mejora significativa (>10%)", self.colors['significant_good']),
            ("↑", "Mejora moderada (5-10%)", self.colors['moderate_good']),
            ("≈", "Sin cambios (<5%)", self.colors['minimal']),
            ("↓", "Empeoramiento moderado (5-10%)", self.colors['moderate_bad']),
            ("⇊", "Empeoramiento significativo (>10%)", self.colors['significant_bad']),
            ("—", "Sin datos para comparar", self.colors['no_data'])
        ]
