"""P1-02: offline developer-environment preflight; no brokerage/API connections.

Checks repository prerequisites and actual temporary-file write/cleanup.
Does not certify trading safety or change the user's environment.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
# Match the versions exercised by .github/workflows/ci.yml. This does not
# certify every patch release or a user's machine-specific dependencies.
CI_PYTHON_MATRIX = {
    "linux": (3, 12),
    "win32": (3, 13),
}
REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "MASTER_SPEC.md",
    ".github/workflows/ci.yml",
    "requirements-dev.txt",
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


def python_matrix_diagnostic(platform: str, version: tuple[int, int]) -> tuple[str, str]:
    """Report CI matrix membership, not proof of full runtime compatibility."""
    expected = CI_PYTHON_MATRIX.get(platform)
    actual = f"{version[0]}.{version[1]}"
    if expected is None:
        return ("WARN", f"Python {actual} on {platform}: no corresponding CI job")
    expected_text = f"{expected[0]}.{expected[1]}"
    if version == expected:
        return (
            "PASS",
            f"Python {actual} on {platform} matches CI test matrix "
            "(not full machine compatibility certification)"
        )
    return (
        "WARN",
        f"Python {actual} on {platform} differs from CI-tested "
        f"Python {expected_text} on this platform"
    )


REQUIRED_IANA_ZONES = ("America/New_York", "Asia/Tokyo")


def unavailable_iana_timezones(zone_loader=ZoneInfo) -> list[str]:
    """Check required IANA names without changing the Python environment."""
    missing = []
    for key in REQUIRED_IANA_ZONES:
        try:
            zone_loader(key)
        except (ZoneInfoNotFoundError, ModuleNotFoundError):
            missing.append(key)
    return missing


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
    python_level, python_message = python_matrix_diagnostic(
        sys.platform, sys.version_info[:2]
    )
    print(f"{python_level}: {python_message}")

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
    missing_zones = unavailable_iana_timezones()
    if missing_zones:
        print("FAIL: Required IANA time zones unavailable: " + ", ".join(missing_zones))
        print("      Windows: python -m pip install -r requirements-dev.txt")
        print("      zoneinfo needs system IANA data or the first-party tzdata wheel.")
    else:
        print("PASS: Required IANA time zones America/New_York and Asia/Tokyo")

    print("INFO: No API calls, broker access, real order handling, or approval changes.")
    return 0 if not missing and temp_ok and not missing_zones else 1


if __name__ == "__main__":
    raise SystemExit(main())
