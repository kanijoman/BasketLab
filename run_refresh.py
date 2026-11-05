"""Entry point of the scheduled refresh of the archive (issues #177, #724): ``python run_refresh.py [--require-env]``."""
import os
import sys

# Ensure 'src/' is on the path so internal absolute imports resolve (legacy ``utils`` imports).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if __name__ == "__main__":
    from src.services.competition_refresh import main

    sys.exit(main())
