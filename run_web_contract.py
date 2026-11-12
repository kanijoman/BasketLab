"""Entry point of the generated TypeScript types of ``web-data`` (#328) and of BasketLab Talent (#878): ``python run_web_contract.py [--check]``.

Writes ``frontend/src/webdata/contract.generated.ts`` from ``src/local_data/contract.py`` (the ONE description of the manifest of ``web-data``) and
``frontend/src/market/contract.generated.ts`` from ``src/market/contract.py`` (the one of ``talent-data``); ``--check`` only compares them (exit 1 when one is behind),
which is what a test and a pre-commit look do.
"""
import argparse
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TARGETS = (
    (os.path.join("frontend", "src", "webdata", "contract.generated.ts"), "src.local_data.contract", "src/local_data/contract.py"),
    (os.path.join("frontend", "src", "market", "contract.generated.ts"), "src.market.contract", "src/market/contract.py"),
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate the TypeScript types of the web-data and talent-data contracts")
    parser.add_argument("--check", action="store_true", help="do not write: exit 1 if a generated file is not the current contract")
    args = parser.parse_args(argv)

    behind = False
    for target, module, source in TARGETS:
        wanted = importlib.import_module(module).render_typescript()
        current = open(target, encoding="utf-8", newline="").read().replace("\r\n", "\n") if os.path.exists(target) else None
        if args.check:
            if current != wanted:
                print(f"{target} is behind {source}: run python run_web_contract.py", file=sys.stderr)
                behind = True
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(wanted)
        print("wrote", target)
    return 1 if behind else 0


if __name__ == "__main__":
    sys.exit(main())
