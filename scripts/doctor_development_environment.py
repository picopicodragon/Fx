"""P1-02: offline developer-environment preflight; no brokerage/API connections.

Checks repository prerequisites and actual temporary-file write/cleanup.
Does not certify trading safety or change the user's environment.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_PYTHON = (3, 12)
REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "MASTER_SPEC.md",
    ".github/workflows/ci.yml",
)
REQUIRED_DIRS = ("scripts", "tests", "specs")


def missing_repository_paths(root: Path) -> list[str]:
    """Report only public relative names, never private filesystem paths."""
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    missing.extend(name + "/" for name in REQUIRED_DIRS if not (root / name).is_dir())
    return missing


def probe_temp_directory(base: Path) -> bool:
    """Create, read, and remove a tiny synthetic file under an existing directory."""
    if not base.is_dir():
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="fx-p102-", dir=str(base)) as folder:
            probe = Path(folder) / "write_probe.txt"
            probe.write_bytes(b"fx-p1-02")
            return probe.read_bytes() == b"fx-p1-02"
    except OSError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline Python/CI development environment preflight (P1-02)."
    )
    parser.add_argument(
        "--temp-base",
        type=Path,
        help="Existing temp directory to test (default: Python's standard temp directory).",
    )
    args = parser.parse_args(argv)

    print("Fx P1-02 development environment (NOT a trading-safety test)")
    if sys.version_info[:2] == CI_PYTHON:
        print("PASS: Python matches CI reference version 3.12")
    else:
        print(
            f"WARN: Python {sys.version_info.major}.{sys.version_info.minor} "
            "differs from CI reference 3.12; compatibility is not yet certified"
        )

    missing = missing_repository_paths(ROOT)
    if missing:
        print("FAIL: Missing required repository paths: " + ", ".join(missing))
    else:
        print("PASS: Baseline repository paths present")

    try:
        base = args.temp_base if args.temp_base is not None else Path(tempfile.gettempdir())
        temp_ok = probe_temp_directory(base)
    except OSError:
        temp_ok = False

    if temp_ok:
        print("PASS: Temporary directory create/write/read/cleanup")
    else:
        print("FAIL: Temporary-file operations unavailable; inspect TEMP/TMP permissions")
        print("      Use --temp-base with an existing writable directory to diagnose.")
    print("INFO: No API calls, broker access, real order handling, or approval changes.")
    return 0 if not missing and temp_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
