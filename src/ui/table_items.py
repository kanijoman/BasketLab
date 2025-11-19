"""Custom table widget items for statistics display."""

from PyQt6.QtWidgets import QTableWidgetItem
from .numeric_utils import safe_float


class NumericTableWidgetItem(QTableWidgetItem):
    """Custom QTableWidgetItem for proper numeric sorting in descending order."""

    def __init__(self, value, text, is_numeric=True):
        """
        Initialize numeric table widget item.

        Args:
            value: Numeric value for sorting
            text: Display text
            is_numeric: Whether the item contains numeric data
        """
        super().__init__(text)
        self.is_numeric = is_numeric
        self._numeric_value = self._convert_to_numeric(value) if is_numeric else None

    def _convert_to_numeric(self, value):
        """Convert value to float."""
        if value is None:
            return 0.0
        try:
            return float(str(value).strip().replace(',', '.'))
        except (ValueError, TypeError, AttributeError):
            return 0.0

    def __lt__(self, other):
        """Implement less than comparison for sorting (inverted for descending order)."""
        if not isinstance(other, NumericTableWidgetItem):
            return super().__lt__(other)

        if self.is_numeric and other.is_numeric:
            # Inverted comparison for descending order by default
            return self._numeric_value > other._numeric_value

        return self.text() < other.text()


def process_numeric_value(value, key):
    """
    Convert value to numeric and format for display.

    Args:
        value: Value to process
        key: Key name (unused but kept for compatibility)

    Returns:
        Tuple of (numeric_value, formatted_string)
    """
    try:
        num_value = float(str(value).strip().replace(',', '.'))
        # Display integers without decimal places
        if num_value.is_integer():
            return num_value, str(int(num_value))
        return num_value, f"{num_value:.1f}"
    except (ValueError, TypeError):
        return 0.0, "0"
