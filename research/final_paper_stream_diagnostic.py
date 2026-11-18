"""Read-only MT4 observer versus virtual-paper supervisor gap diagnosis.

Distinguishes stale DEMO CSV production from unconsumed fresh quotes.
Does not open accounts, send broker orders, call AI, mutate journals,
remove runtime locks or authorize recovery. Timestamps are PC-derived,
and neither broker time nor OS clock is independently attested.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_engine as paper
from research import final_paper_status as status
from research import final_paper_runtime as runtime
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_stream_gap_diagnostic_v1"
NAME = re.compile(r"^FxPaperQuote_[0-9]{8}_[0-9]{6}\.csv$")
SAFE_REASONS = frozenset({
    "DIAGNOSTIC_PATH_UNSAFE", "DIAGNOSTIC_SOURCE_INVALID",
    "DIAGNOSTIC_QUOTE_MISMATCH", "DIAGNOSTIC_CLOCK_INVALID",
    "DIAGNOSTIC_REPORT_ALREADY_EXISTS",
})


def _quote_metadata(file: Path) -> tuple[int, int]:
    """Read strictly bounded metadata but never return bid/ask or account data."""
    if (not file.is_file() or file.is_symlink() or
            not NAME.fullmatch(file.name)
            or not 0 < file.stat().st_size <= 4500):
        raise InputError("DIAGNOSTIC_SOURCE_INVALID")
    raw = file.read_bytes()
    if b"\x00" in raw:
        raise InputError("DIAGNOSTIC_SOURCE_INVALID")
    try:
        rows = csv.DictReader(raw.decode("utf-8-sig").splitlines(),
                              strict=True)
        if tuple(rows.fieldnames or ()) != paper.QUOTE_FIELDS:
            raise InputError("DIAGNOSTIC_SOURCE_INVALID")
        data = list(rows)
        if len(data) != 3 or tuple(r["pair"] for r in data) != paper.SYMS:
            raise InputError("DIAGNOSTIC_SOURCE_INVALID")
        if any(None in r or set(r) != set(paper.QUOTE_FIELDS) for r in data):
            raise InputError("DIAGNOSTIC_SOURCE_INVALID")
        captures = {int(r["capture_epoch_utc_pc"]) for r in data}
        if len(captures) != 1 or next(iter(captures)) <= 0:
            raise InputError("DIAGNOSTIC_QUOTE_MISMATCH")
        return captures.pop(), int(file.stat().st_mtime)
    except (UnicodeError, csv.Error, ValueError, OverflowError) as exc:
        raise InputError("DIAGNOSTIC_SOURCE_INVALID") from exc


def diagnose(root: Path, mt4: Path, *, now: datetime|None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("DIAGNOSTIC_CLOCK_INVALID")
    if (not root.is_dir() or root.is_symlink() or
            not mt4.is_dir() or mt4.is_symlink()
            or any(p.is_symlink() for p in (*root.parents,*mt4.parents))
            or not str(mt4.resolve()).lower().endswith(
                str(Path("MQL4") / "Files").lower())):
        raise InputError("DIAGNOSTIC_PATH_UNSAFE")
    summary = status.summarize(root, now=current)
    state, _ = runtime._journal_load(root/"journal")
    last = state["last_quote_epoch"]
    files = sorted(
        (file for file in mt4.glob("FxPaperQuote_*.csv")
         if NAME.fullmatch(file.name)),
        key=lambda f:f.name, reverse=True)
    result = {
        "schema": SCHEMA,
        "status": "PAPER_STREAM_DIAGNOSTIC_RESEARCH_NO_GO",
        "diagnosis": None,
        "journal_cycles": state["cycle_number"],
        "last_processed_quote_epoch_pc_unattested": last,
        "last_processed_quote_age_seconds_pc_derived":
            summary["last_recorded_quote_age_seconds_pc_derived"],
        "journal_quote_warning_level":
            summary["price_stream_warning_level_pc_derived"],
        "latest_raw_quote_epoch_pc_unattested": None,
        "latest_raw_quote_age_seconds_pc_derived": None,
        "latest_raw_quote_file_age_seconds_pc_derived": None,
        "raw_quote_ahead_of_journal": False,
        "runtime_lock_present_not_process_proof":
            (root/".single_operator.lock").exists(),
        "mt4_observer_running": "NOT_ATTESTED",
        "paper_supervisor_running": "NOT_ATTESTED",
        "quote_clock_independently_verified": False,
        "api_calls_this_run": 0,
        "broker_orders_this_run": 0,
        "new_paid_calls_authorized": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }
    if (root/".single_operator.lock").is_symlink():
        raise InputError("DIAGNOSTIC_PATH_UNSAFE")
    if not files:
        result["diagnosis"] = "MT4_OBSERVER_HAS_NO_QUOTE_CSV"
        return result
    latest = files[0]
    captured, modified = _quote_metadata(latest)
    now_epoch = int(current.timestamp())
    age = now_epoch - captured
    file_age = now_epoch - modified
    if age < -10 or file_age < -10:
        raise InputError("DIAGNOSTIC_CLOCK_INVALID")
    result["latest_raw_quote_epoch_pc_unattested"] = captured
    result["latest_raw_quote_age_seconds_pc_derived"] = age
    result["latest_raw_quote_file_age_seconds_pc_derived"] = file_age
    result["raw_quote_ahead_of_journal"] = captured > last
    if last and captured < last:
        result["diagnosis"] = "QUOTE_ARCHIVE_BEHIND_JOURNAL_REVIEW"
    elif age >= 600:
        result["diagnosis"] = "MT4_OBSERVER_QUOTE_STREAM_STALE"
    elif captured > last and age <= 120:
        result["diagnosis"] = "FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON"
    elif captured > last:
        result["diagnosis"] = "UNPROCESSED_MT4_QUOTES_ALREADY_STALE"
    elif age >= 120:
        result["diagnosis"] = "MT4_OBSERVER_QUOTE_STREAM_DELAYED"
    else:
        result["diagnosis"] = "LATEST_MT4_QUOTE_ALREADY_PROCESSED"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only DEMO quote producer/virtual consumer gap diagnosis")
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--mt4-files", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = diagnose(args.state_root, args.mt4_files)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("DIAGNOSTIC_REPORT_ALREADY_EXISTS")
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2,
                      allow_nan=False)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, KeyError, TypeError,
            UnicodeError, OverflowError) as exc:
        reason = (exc.args[0] if isinstance(exc, InputError)
                  and exc.args and type(exc.args[0]) is str else "")
        print(json.dumps({
            "schema": SCHEMA,
            "status": "PAPER_STREAM_DIAGNOSTIC_FAIL_CLOSED_NO_GO",
            "failure_reason_code":
                reason if reason in SAFE_REASONS else "DIAGNOSTIC_INVALID_INPUT",
            "api_calls_this_run": 0,
            "broker_orders_this_run": 0,
            "new_paid_calls_authorized": False,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
