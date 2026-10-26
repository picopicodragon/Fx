"""Stage the reviewed MQL4 source for a MetaEditor compile-only check.

No MetaEditor/MT4 is launched. No MQL4 is compiled. No existing file is
overwritten. The destination must be outside Git and MT4 terminal folders.
"""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .audit_mt4_readonly_source import SOURCE, ROOT, audit_mql4_readonly
except ImportError:
    from audit_mt4_readonly_source import SOURCE, ROOT, audit_mql4_readonly

MQ4_NAME = "P0_01_ManualSymbolSnapshot_ReadOnly.mq4"
BLOCKED_COMPONENTS = {
    ".git", "mql4", "mql5", "metaquotes", "terminal",
}


def staging_location_allowed(path: Path) -> bool:
    try:
        p = path.resolve()
        if p == ROOT.resolve() or p.is_relative_to(ROOT.resolve()):
            return False
        # Fail closed if the path looks like a terminal installation/data
        # location; compilation must not produce EX4 in a runnable folder.
        if any(piece.casefold() in BLOCKED_COMPONENTS for piece in p.parts):
            return False
        return p.is_absolute()
    except (OSError, RuntimeError, ValueError):
        return False


def stage_compile_only(destination_dir: Path) -> str:
    if not staging_location_allowed(destination_dir):
        return "BLOCKED: DESTINATION_INSIDE_GIT_OR_MT4_LOCATION"
    target = destination_dir / MQ4_NAME
    if target.exists():
        return "BLOCKED: SOURCE_ALREADY_STAGED_NO_OVERWRITE"
    try:
        data = SOURCE.read_bytes()
        if audit_mql4_readonly(data.decode("utf-8")):
            return "BLOCKED: MQL4_STATIC_AUDIT_FAILED"
        destination_dir.mkdir(parents=True, exist_ok=True)
        if not staging_location_allowed(target):
            return "BLOCKED: DESTINATION_INSIDE_GIT_OR_MT4_LOCATION"
        # 'xb' is exclusive: even if a file appears concurrently, no clobber.
        with target.open("xb") as output:
            output.write(data)
    except FileExistsError:
        return "BLOCKED: SOURCE_ALREADY_STAGED_NO_OVERWRITE"
    except (UnicodeError, OSError):
        return "BLOCKED: STAGING_IO_ERROR"
    return "STAGED: MQ4 copied without launching MetaEditor or MT4"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Offline-only MQL4 compile staging")
    p.add_argument(
        "--output-dir", type=Path,
        default=Path.home() / "Documents" / "FxLocalReview" / "CompileOnly",
        help="Directory outside Git and all MetaTrader application/data folders",
    )
    args = p.parse_args(argv)
    status = stage_compile_only(args.output_dir)
    print(status)
    print("NO_COMPILE_ATTEMPTED / NO_TERMINAL_EXECUTION / PHASE_1_BLOCKED")
    return 0 if status.startswith("STAGED:") else 1


if __name__ == "__main__":
    raise SystemExit(main())
