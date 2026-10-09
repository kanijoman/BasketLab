"""Entry point of the scheduled Atlas refresh (issue #177): ``python run_atlas_refresh.py [--require-env]``."""
import os
import sys

# Ensure 'src/' is on the path so internal absolute imports resolve (legacy ``utils`` imports).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if __name__ == "__main__":
    from src.services.atlas_refresh import main

    sys.exit(main())
