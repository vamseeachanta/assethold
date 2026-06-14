"""Command-line entrypoint for ``python -m assethold``."""

import sys

from assethold.engine import engine


def main() -> None:
    inputfile = sys.argv[1] if len(sys.argv) > 1 else None
    engine(inputfile)


if __name__ == "__main__":
    main()
