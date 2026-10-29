"""Entry point of the generated TypeScript types of ``web-data`` (#328): ``python run_web_contract.py [--check]``.

Writes ``frontend/src/webdata/contract.generated.ts`` from ``src/local_data/contract.py`` (the ONE description of the manifest); ``--check`` only compares it
(exit 1 when it is behind), which is what a test and a pre-commit look do.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TARGET = os.path.join("frontend", "src", "webdata", "contract.generated.ts")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate the TypeScript types of the web-data contract")
    parser.add_argument("--check", action="store_true", help="do not write: exit 1 if the generated file is not the current contract")
    args = parser.parse_args(argv)

    from src.local_data.contract import render_typescript

    wanted = render_typescript()
    current = open(TARGET, encoding="utf-8", newline="").read().replace("\r\n", "\n") if os.path.exists(TARGET) else None
    if args.check:
        if current != wanted:
            print(f"{TARGET} is behind src/local_data/contract.py: run python run_web_contract.py", file=sys.stderr)
            return 1
        return 0
    with open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(wanted)
    print("wrote", TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main())
