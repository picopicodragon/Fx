"""FWD-062: canonical three-pair entry point for v2 research readiness.

The older module name ending in four_pair remains solely to preserve
existing Python imports. Its logic is corrected to three pairs and NEVER GO.
"""
from __future__ import annotations

from research.forward_mt4_v2_four_pair import (
    SCHEMA, review, main as legacy_main)


def main(argv=None) -> int:
    return legacy_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
