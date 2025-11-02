# FIBA Basketball Court Generator

Python module to generate half-court basketball visualizations with official FIBA dimensions.

## Features

- Official FIBA court dimensions (all in meters)
- Complete court elements:
  - Half-court border
  - Key/paint area
  - Three-point line
  - Free throw circle
  - Restricted area
  - Backboard and hoop
  - Half-court circle
- Predefined color themes (light, wood, dark, classic, modern)
- White background by default for clean visualizations
- Customizable colors and sizes
- Export to PNG, PDF, SVG, etc.

## Official FIBA Dimensions

Based on official FIBA basketball rules:
- Court width: 15.0 meters
- Half-court length: 14.0 meters (28/2)
- Key (paint): 5.8m × 4.9m
- Three-point line radius: 6.75 meters
- Free throw circle radius: 1.8 meters
- Restricted area radius: 1.25 meters
- Hoop diameter: 0.45 meters
- Backboard width: 1.8 meters

References:
- [FIBA Official Basketball Rules (2020)](https://www.fiba.basketball/documents/official-basketball-rules/2020.pdf)
- [FIBA Basketball Equipment](https://www.fiba.basketball/documents/BasketballEquipment.pdf)

## Usage

### Basic Usage

```python
from src.shotcharts import plot_court
import matplotlib.pyplot as plt

# Generate a basic court (white background by default)
fig = plot_court()
plt.show()

# Save to file
fig = plot_court(save_path='my_court.png')
```

### Using the FIBACourt Class

```python
from src.shotcharts import FIBACourt
import matplotlib.pyplot as plt

# Create court instance
court = FIBACourt()

# Generate plot
fig = court.plot_court(
    court_color='#FFFFFF',  # White background (default)
    line_color='#000000',    # Black lines (default)
    title='FIBA Half Court',
    save_path='fiba_court.png',
    figsize=(12, 12),
    dpi=150
)

plt.show()
```

### Using Predefined Themes

```python
from src.shotcharts import plot_court_with_theme
import matplotlib.pyplot as plt

# Available themes: 'light' (white), 'wood', 'dark', 'classic', 'modern'
fig = plot_court_with_theme(
    theme='light',  # White background
    title='FIBA Court - Light Theme',
    figsize=(12, 12)
)

plt.show()
```

### Custom Colors

```python
from src.fiba_court import plot_court

fig = plot_court(
    court_color='#1E90FF',  # Dodger blue
    line_color='#FFD700',    # Gold
    title='Custom Colors Court'
)
```

### Overlay Data (e.g., Shot Chart)

```python
from src.shotcharts import FIBACourt
import matplotlib.pyplot as plt

# Create court
court = FIBACourt()
fig = court.plot_court(title='Shot Chart')
ax = fig.axes[0]

# Add shot data
shot_x = [7.5, 8.2, 6.8]
shot_y = [3.5, 5.2, 7.1]
made = [True, True, False]

# Plot shots
for x, y, m in zip(shot_x, shot_y, made):
    color = 'green' if m else 'red'
    marker = 'o' if m else 'x'
    ax.scatter(x, y, c=color, s=100, marker=marker, zorder=10)

plt.show()
```

## API Reference

### FIBACourt Class

Main class for generating FIBA half-court visualizations.

**Methods:**

- `plot_court(court_color, line_color, figsize, title, save_path, dpi)`: Generate and plot the court

**Attributes:**

All dimensions are stored as instance attributes in meters (e.g., `width`, `height`, `three_point_radius`, etc.)

### Functions

**`plot_court(...)`**

Convenience function to quickly generate a court.

Parameters:
- `court_color` (str): Background color
- `line_color` (str): Line color
- `figsize` (tuple): Figure size (width, height)
- `title` (str, optional): Plot title
- `save_path` (str, optional): Path to save image
- `dpi` (int): DPI for saved image

Returns: `matplotlib.figure.Figure`

**`plot_court_with_theme(theme, ...)`**

Generate court with a predefined theme.

Parameters:
- `theme` (str): Theme name ('light', 'dark', 'classic', 'modern')
- Additional parameters same as `plot_court()`

Returns: `matplotlib.figure.Figure`

### Predefined Themes

**`COURT_THEMES`** dictionary contains:

- **light**: White court with black lines (default)
- **wood**: Light wood court with black lines
- **dark**: Dark gray court with white lines
- **classic**: Classic wood with saddle brown lines
- **modern**: Light gray with royal blue lines

## Dependencies

- `numpy`: Mathematical operations
- `matplotlib`: Plotting and visualization

## Export Formats

Supports all matplotlib-compatible formats:

```python
# PNG (recommended for web)
plot_court(save_path='court.png', dpi=150)

# PDF (recommended for print)
plot_court(save_path='court.pdf', dpi=300)

# SVG (vector, editable)
plot_court(save_path='court.svg')

# JPG
plot_court(save_path='court.jpg', dpi=150)
```

## Implementation Details

### Three-Point Line

The three-point line is drawn as three separate components to avoid visual artifacts:
1. Left vertical line from baseline to arc start
2. Arc connecting both vertical lines
3. Right vertical line from arc end to baseline

The arc connection points are calculated mathematically to ensure perfect alignment without gaps.

### Restricted Area

Similar to the three-point line, the restricted area is drawn as:
1. Left vertical line from backboard to arc start
2. Semi-circular arc
3. Right vertical line from arc end to backboard

This ensures no horizontal lines cross through the area.

### Code Quality

The module has been refactored with the following improvements:

- **Type hints**: Complete type annotations for all functions and methods
- **Input validation**: All parameters are validated with clear error messages
- **DRY principle**: Eliminated code duplication with helper methods
- **Properties**: Computed values use `@property` decorators for clarity
- **Constants**: Magic numbers replaced with named class constants
- **Error handling**: Comprehensive validation with informative exceptions
- **Separation of concerns**: Drawing logic split into focused methods

## Examples

Run the module directly to see a basic example:

```bash
python -m src.shotcharts.fiba_court
```

Or explore the example usage script:

```bash
python -m src.shotcharts.example_usage
```

This will generate a half-court image with the light theme and display it.

## License

This code generates basketball courts with official FIBA dimensions for data visualization purposes.
