"""FWD-043/044: operator-selected MT4 CSV handoff into immutable local evidence.

A single explicit local CSV is read; this module never finds terminals,
modifies MT4 directories, imports the journal, schedules jobs, or trades.
A self-reported DEMO field is not broker authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from research.forward_mt4_quote_import import parse_quote_csv, MAX_BYTES
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_manual_handoff_v1"
BASENAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


def capture(source: Path, target: Path, *, capture_id: str,
            asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    if (type(capture_id) is not str or not BASENAME.fullmatch(capture_id) or
            not isinstance(source, Path) or not isinstance(target, Path) or
            source.is_symlink() or target.exists() or
            not target.parent.is_dir() or not source.is_file() or
            not 0 < source.stat().st_size <= MAX_BYTES):
        raise InputError("unsafe handoff source or target")
    raw = source.read_bytes()
    if len(raw) > MAX_BYTES:
        raise InputError("source changed while reading")
    try:
        snapshot = parse_quote_csv(raw.decode("utf-8-sig"), now=now)
    except UnicodeError as exc:
        raise InputError("invalid CSV encoding") from exc
    # No raw filename/path, terminal account number, credentials or
    # application data root is embedded into portable report.
    evidence = {
        "schema": SCHEMA,
        "status": "MANUAL_MT4_CSV_HANDOFF_NO_GO",
        "capture_id": capture_id,
        "asof_utc": asof_utc,
        "observed_at_utc": snapshot["observed_at_utc"],
        "pair": snapshot["payload"]["pair"],
        "csv_sha256": hashlib.sha256(raw).hexdigest(),
        "csv_file": "quote.csv",
        "source_status": "USER_SUPPLIED_UNVERIFIED",
        "source_file_preserved": True,
        "journal_import_performed": False,
        "mt4_account_independently_authenticated": False,
        "clock_independently_attested": False,
        "mt4_terminal_started_or_modified": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }
    # Exclusive directory prevents collisions and preserves the original.
    # On an unexpected partial write the directory remains for investigation,
    # never attempt to overwrite or silently resume it.
    target.mkdir()
    with (target / "quote.csv").open("xb") as out:
        out.write(raw)
    with (target / "receipt.json").open("x", encoding="utf-8") as out:
        json.dump(evidence, out, ensure_ascii=False, indent=2)
    return evidence


def verify_capture(folder: Path) -> dict:
    if (not folder.is_dir() or folder.is_symlink()
            or (folder / "quote.csv").is_symlink()
            or (folder / "receipt.json").is_symlink()
            or not (folder / "quote.csv").is_file()
            or not (folder / "receipt.json").is_file()
            or (folder / "quote.csv").stat().st_size > MAX_BYTES
            or (folder / "receipt.json").stat().st_size > 10000):
        raise InputError("incomplete or unsafe captured file")
    report = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    if (type(report) is not dict or
            report.get("schema") != SCHEMA or
            report.get("status") != "MANUAL_MT4_CSV_HANDOFF_NO_GO" or
            report.get("runtime_go_no_go") != "NO_GO" or
            report.get("safety_hold_latched") is not True or
            report.get("real_orders_permitted") is not False or
            report.get("demo_order_execution_enabled") is not False or
            report.get("journal_import_performed") is not False or
            report.get("mt4_terminal_started_or_modified") is not False):
        raise InputError("untrusted captured receipt")
    now = timestamp(report["asof_utc"])
    raw = (folder / "quote.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest() != report["csv_sha256"]:
        raise InputError("local CSV modified")
    snapshot = parse_quote_csv(raw.decode("utf-8-sig"), now=now)
    if (snapshot["observed_at_utc"] != report["observed_at_utc"] or
            snapshot["payload"]["pair"] != report["pair"] or
            report.get("csv_file") != "quote.csv"):
        raise InputError("capture metadata mismatch")
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Manual offline MT4 CSV copy; no trading")
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--capture-id", required=True)
    p.add_argument("--asof-utc")
    args = p.parse_args(argv)
    try:
        stamp = args.asof_utc or datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        result = capture(args.source, args.out_dir,
                         capture_id=args.capture_id, asof_utc=stamp)
        verify_capture(args.out_dir)
        print(json.dumps({
            "status": result["status"],
            "pair": result["pair"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            UnicodeError, KeyError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MANUAL_MT4_HANDOFF_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
