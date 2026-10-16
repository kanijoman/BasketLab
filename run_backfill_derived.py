"""Entry point of the DERIVED backfill (issue #372): ``python run_backfill_derived.py [--collection NAME]``."""
import os
import sys

# Ensure 'src/' is on the path so internal absolute imports resolve (legacy ``utils`` imports).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if __name__ == "__main__":
    from src.services.derived_backfill import main

    sys.exit(main())
