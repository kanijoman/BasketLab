"""
MongoDB connection configuration.
This file contains the connection string and is excluded from version control.
"""

import os
import sys
from pathlib import Path

def get_mongodb_connection_string() -> str:
    """
    Get MongoDB connection string.

    Priority:
    1. Environment variable MONGODB_CONNECTION_STRING
    2. Local config file (for development)
    3. Packaged file (for PyInstaller distribution)
    4. Fallback default

    Returns:
        MongoDB connection string
    """
    # Try environment variable first
    env_connection = os.getenv('MONGODB_CONNECTION_STRING')
    if env_connection:
        return env_connection

    # Try local config file for development
    config_file = Path(__file__).parent / 'db_credentials.txt'
    if config_file.exists():
        with open(config_file, 'r') as f:
            connection_string = f.read().strip()
            if connection_string:
                return connection_string

    # Try packaged file for PyInstaller distribution
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        packaged_file = bundle_dir / 'database' / 'db_credentials.txt'
        if packaged_file.exists():
            with open(packaged_file, 'r') as f:
                connection_string = f.read().strip()
                if connection_string:
                    return connection_string

    # Default fallback (should not be reached in production)
    return "mongodb://localhost:27017/"
