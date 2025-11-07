"""
Utility functions for UI components.
"""
import os
from PyQt6.QtGui import QIcon


def get_app_icon():
    """
    Get the application icon.

    Returns:
        QIcon: The application icon, or None if not found
    """
    # Try multiple possible paths for MfA.ico
    possible_paths = [
        # From src/ui/ directory
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'resources', 'MfA.ico'),
        # From project root
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'resources', 'MfA.ico'),
        # Absolute path construction
        os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'resources', 'MfA.ico'))
    ]

    for icon_path in possible_paths:
        if os.path.exists(icon_path):
            return QIcon(icon_path)

    # If no icon found, return empty QIcon
    return QIcon()


def set_app_icon(window):
    """
    Set the application icon for a window.

    Args:
        window: QMainWindow or QDialog to set icon for
    """
    icon = get_app_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)
