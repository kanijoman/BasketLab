"""Entry point of the live package publication (issue #175): ``python run_package_publish.py [--out DIR]``."""
import os
import sys

# Ensure 'src/' is on the path so internal absolute imports resolve (legacy ``utils`` imports).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

if __name__ == "__main__":
    from src.live_prep.publisher import main

    sys.exit(main())
