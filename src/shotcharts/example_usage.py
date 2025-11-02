"""
Simple example script showing how to use the FIBA court generator.

This script demonstrates basic usage of the shotcharts module.

Run from the project root directory:
    python -m src.shotcharts.example_usage
"""

from src.shotcharts import FIBACourt, plot_court, plot_court_with_theme
import matplotlib.pyplot as plt


def example_basic():
    """Example 1: Create a basic court."""
    print("Example 1: Basic court")
    fig = plot_court(save_path='output_basic.png')
    plt.show()


def example_with_theme():
    """Example 2: Create a court with a predefined theme."""
    print("\nExample 2: Court with theme")
    fig = plot_court_with_theme(
        theme='dark',
        title='FIBA Half Court - Dark Theme',
        save_path='output_dark.png'
    )
    plt.show()


def example_custom_colors():
    """Example 3: Create a court with custom colors."""
    print("\nExample 3: Custom colors")
    fig = plot_court(
        court_color='#E8F4F8',
        line_color='#2C5F8D',
        title='FIBA Half Court - Custom Colors',
        save_path='output_custom.png'
    )
    plt.show()


def example_with_data():
    """Example 4: Create a court and overlay data."""
    print("\nExample 4: Court with data overlay")
    
    # Create court
    court = FIBACourt()
    fig = court.plot_court(
        title='Shot Chart Example',
        figsize=(12, 12)
    )
    
    # Get axis
    ax = fig.axes[0]
    
    # Example shot data (x, y coordinates in meters)
    shots = [
        (7.5, 3.5, True),   # (x, y, made)
        (8.2, 5.2, True),
        (6.8, 7.1, False),
        (9.1, 4.8, True),
        (5.5, 6.3, False),
    ]
    
    # Plot shots
    for x, y, made in shots:
        color = 'green' if made else 'red'
        marker = 'o' if made else 'x'
        ax.scatter(x, y, c=color, s=100, marker=marker, 
                  alpha=0.7, edgecolors='darkgreen' if made else 'darkred',
                  linewidth=2, zorder=10)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='green', label='Made shots'),
        Patch(facecolor='red', label='Missed shots')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.savefig('output_shot_chart.png', dpi=150, bbox_inches='tight')
    plt.show()


if __name__ == "__main__":
    print("FIBA Court Generator - Examples")
    print("=" * 50)
    
    # Uncomment the example you want to run:
    
    example_basic()
    # example_with_theme()
    # example_custom_colors()
    # example_with_data()
    
    print("\n" + "=" * 50)
    print("Done! Check the generated images.")
