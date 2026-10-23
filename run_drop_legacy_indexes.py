"""Entry point to drop the legacy index of the FEB collections (issue #137): ``python run_drop_legacy_indexes.py [--collection NAME] [--apply]``."""
import os
import sys

# Ensure 'src/' is on the path so internal absolute imports resolve (legacy ``utils`` imports).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if __name__ == "__main__":
    from src.services.legacy_indexes import main

    sys.exit(main())
