"""
Statistics Formatter - Format statistics with quartile comparisons.

This module provides utilities for formatting statistical data with
league-wide quartile comparisons and strength/weakness indicators.
"""

from typing import Dict, Optional


class StatisticsFormatter:
    """Format statistics with quartile comparisons and assessments."""

    @staticmethod
    def format_stat_with_quartile(stat_name: str,
                                   value: float,
                                   quartiles: Dict[str, float],
                                   higher_is_better: Optional[bool] = True,
                                   is_percentage: bool = False,
                                   format_str: str = ".1f") -> str:
        """
        Format a statistic with quartile comparison and strength/weakness indicator.

        Args:
            stat_name: Name of the statistic
            value: Team's value for this stat
            quartiles: Dictionary with 'q1', 'q2' (median), 'q3', 'min', 'max' keys
            higher_is_better: True if higher values are better, False if lower is better, None if neutral
            is_percentage: Whether to display with % symbol
            format_str: Format string for the value (e.g., ".1f" for 1 decimal)

        Returns:
            Formatted string with value, quartile, and assessment
        """
        # Handle None or missing values
        if value is None:
            return f"- **{stat_name}**: N/A"

        # Convert to float to ensure it's numeric
        try:
            value = float(value)
        except (ValueError, TypeError):
            return f"- **{stat_name}**: N/A"

        # Format the value
        if is_percentage:
            value_str = f"{value:{format_str}}%"
        else:
            value_str = f"{value:{format_str}}"

        # If no quartile data, return just the value
        if not quartiles or not any(k in quartiles for k in ['q1', 'q2', 'q3']):
            return f"- **{stat_name}**: {value_str}"

        # Determine quartile position
        q1 = quartiles.get('q1', 0)
        q2 = quartiles.get('q2', 0)  # median
        q3 = quartiles.get('q3', 0)

        # Handle None values in quartiles
        if q1 is None or q2 is None or q3 is None:
            return f"- **{stat_name}**: {value_str}"

        # Classify into quartile
        if value <= q1:
            quartile_pos = "Q1 (cuartil inferior)"
            strength_level = 1
        elif value <= q2:
            quartile_pos = "Q2 (por debajo de la mediana)"
            strength_level = 2
        elif value <= q3:
            quartile_pos = "Q3 (por encima de la mediana)"
            strength_level = 3
        else:
            quartile_pos = "Q4 (cuartil superior)"
            strength_level = 4

        # Determine if this is a strength or weakness
        if higher_is_better is None:
            assessment = ""  # Neutral stat
        elif higher_is_better:
            if strength_level >= 3:
                assessment = " ✓ FORTALEZA"
            elif strength_level == 1:
                assessment = " ✗ DEBILIDAD"
            else:
                assessment = ""
        else:  # Lower is better
            if strength_level <= 2:
                assessment = " ✓ FORTALEZA"
            elif strength_level == 4:
                assessment = " ✗ DEBILIDAD"
            else:
                assessment = ""

        # Build the output
        try:
            median_str = f"{q2:{format_str}}%" if is_percentage else f"{q2:{format_str}}"
        except (ValueError, TypeError):
            median_str = "N/A"

        return f"- **{stat_name}**: {value_str} [{quartile_pos}, mediana liga: {median_str}]{assessment}"
