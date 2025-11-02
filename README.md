# MetricsForAll

Basketball analytics application for advanced statistical analysis using data from the Spanish Basketball Federation (FEB) and regional federations.

## Overview

MetricsForAll is an application for advanced statistical analysis of basketball using information provided by the FEB (Spanish Basketball Federation) and various regional federations in Spain. The basic functionality includes:

- **Data scraper** from configured sources where competitions are hosted (currently only FEB)
- **Structured information recovery** and storage in a cloud database (MongoDB, JSON-oriented)
- **Statistical analysis tools** for basic and advanced metrics

Currently in the first proof-of-concept phase with the LF2 (Liga Femenina 2) competition from FEB. More competitions from FEB and other regional federations will be added in the future.

## Features

### Data Collection
- Scraper for FEB competition data
- Structured data storage in MongoDB
- Automatic updates to keep information current

### User Interface (PyQt6)
- Competition, season, and group selection window
- "Update and View Statistics" button:
  - Updates competition information in the database
  - Displays a new statistics window with two tabs: basic and advanced statistics

### Statistics Window
- Color-coded information based on quartiles:
  - Q1: Green
  - Q2: Yellow
  - Q3: Orange
  - Q4: Red
- Sortable by any column (ascending/descending)
- Data export functionality: CSV, PNG, or PDF formats

## FIBA Court Visualization

This project includes a **FIBA Basketball Court Generator** module for creating half-court visualizations with official FIBA dimensions.

### Quick Start

```python
from src.shotcharts import plot_court_with_theme
import matplotlib.pyplot as plt

# Generate a FIBA half-court with white background
fig = plot_court_with_theme(theme='light', title='FIBA Half Court')
plt.show()
```

### Features
- Official FIBA court dimensions (all in meters)
- Complete court elements (key, three-point line, restricted area, etc.)
- Predefined color themes (light, wood, dark, classic, modern)
- Customizable colors and sizes
- Export to multiple formats (PNG, PDF, SVG)
- Data overlay support for shot charts and heatmaps
- White background by default for clean visualizations

### Documentation

For detailed documentation on the FIBA court generator, see:
- [`src/shotcharts/README.md`](src/shotcharts/README.md) - Complete API reference and usage guide
- [`src/shotcharts/example_usage.py`](src/shotcharts/example_usage.py) - Simple usage examples

### Example

```python
from src.shotcharts import FIBACourt
import matplotlib.pyplot as plt

# Create court and add shot data
court = FIBACourt()
fig = court.plot_court(title='Shot Chart')
ax = fig.axes[0]

# Add shots
ax.scatter([7.5, 8.2], [3.5, 5.2], c='green', s=100, label='Made')
ax.scatter([6.8], [7.1], c='red', s=100, marker='x', label='Missed')
ax.legend()

plt.show()
```

## Future Development

Adding new federations is a complex change that will be addressed in later phases because the information structure differs from FEB, requiring data transformation to use the same analysis methods.

## Installation

```bash
# Install required packages
pip install numpy matplotlib pymongo PyQt6
```

## Usage

Run the main application:
```bash
python src/main.py
```

Generate FIBA court visualizations:
```bash
python -m src.shotcharts.fiba_court
# or
python -m src.shotcharts.example_usage
```
