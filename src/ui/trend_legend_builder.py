"""Builder for trend legends in comparative mode."""

from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QHBoxLayout
from typing import Tuple, List


class TrendLegendBuilder:
    """Builds trend legend widgets for comparative statistics."""

    @staticmethod
    def create_legend(trend_calculator) -> Tuple[QWidget, QLabel]:
        """
        Create a trend indicator legend widget for comparative mode.

        Args:
            trend_calculator: TrendCalculator instance to get legend items

        Returns:
            Tuple of (legend_frame, title_label) where title_label can be updated later
        """
        legend_frame = QFrame()
        legend_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        legend_frame.setMaximumHeight(40)

        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(10, 5, 10, 5)
        legend_layout.setSpacing(15)

        # Add legend title
        title_label = QLabel("Tendencia:")
        title_label.setStyleSheet("font-weight: bold;")
        legend_layout.addWidget(title_label)

        # Get trend indicators from calculator
        trends = trend_calculator.get_legend_items()

        for symbol, description, color in trends:
            # Create container for each legend item
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(5)

            # Create symbol label
            symbol_label = QLabel(symbol)
            symbol_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {color};")
            symbol_label.setFixedWidth(25)
            item_layout.addWidget(symbol_label)

            # Create description label
            text_label = QLabel(description)
            text_label.setStyleSheet("font-size: 9pt;")
            item_layout.addWidget(text_label)

            legend_layout.addWidget(item_widget)

        # Add stretch to push items to the left
        legend_layout.addStretch()

        return legend_frame, title_label

    @staticmethod
    def update_legend_title(title_label: QLabel, comparison_text: str):
        """
        Update the trend legend title with the current comparison type.

        Args:
            title_label: The QLabel to update
            comparison_text: Description of the comparison (e.g., "local vs visitante")
        """
        title_label.setText(f"Tendencia ({comparison_text}):")

    @staticmethod
    def update_legend_titles(title_labels: List[QLabel], comparison_text: str):
        """
        Update multiple trend legend titles with the current comparison type.

        Args:
            title_labels: List of QLabel widgets to update
            comparison_text: Description of the comparison
        """
        for title_label in title_labels:
            TrendLegendBuilder.update_legend_title(title_label, comparison_text)
