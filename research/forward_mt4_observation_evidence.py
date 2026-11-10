"""FWD-085..094: offline, fail-closed evidence bundle for copied MT4 DEMO observer captures.

Does not access MT4, emit trading decisions, authorize orders, poll prices,
schedule background collection, or claim logs independently authenticate MT4.
The user supplies a closed CSV session folder plus optional text evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research.forward_mt4_timer_capture_audit import (
    inspect as inspect_capture, PATTERN, MAX_FILES
)
from research.offline_backtest import InputError

SCHEMA = "fx_forward_demo_observation_evidence_bundle_v1"
MAX_LOG_BYTES = 2_000_000
MAX_LOG_LINES = 30000
MAX_COMPILE_BYTES = 100_000

START_MARK = "FXFWD_OBSERVER: started DEMO-only 30-cycle read-only observation; NO_GO."
STOP_MARK = "FXFWD_OBSERVER: 30-cycle safety cap reached; timer stopped."
DEINIT_MARK = "FXFWD_OBSERVER: stopped; NO_GO; reason="
CHANGE_STOP = "FXFWD_OBSERVER: account/chart/connection changed. STOP."
CSV_MARK = "FXFWD_OBSERVER: 3 research-only CSV files; NO_GO;"
FAILURE_MARKERS = (
    "FXFWD_OBSERVER: stale/missing quote for ",
    "FXFWD_OBSERVER: missing time. No export.",
    "FXFWD_OBSERVER: filename collision; no export for cycle.",
    "FXFWD_OBSERVER: cannot create CSV; partial cycle possible.",
    "FXFWD_OBSERVER: DEMO/connection/USDJPY chart gate failed.",
    "FXFWD_OBSERVER: cannot start 60-second timer.",
    CHANGE_STOP,
)


def _read_evidence(path: Path, *, max_bytes: int) -> tuple[bytes, str]:
    if (not isinstance(path, Path) or path.is_symlink()
            or not path.is_file() or
            not 0 < path.stat().st_size <= max_bytes):
        raise InputError("missing or unsafe evidence")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise InputError("binary evidence not accepted")
    try:
        return raw, raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("evidence is not UTF-8 text") from exc


def inspect(
    directory: Path, *, asof_utc: str,
    experts_log: Path | None = None,
    compile_log: Path | None = None,
) -> dict:
    report = inspect_capture(directory, asof_utc=asof_utc)
    paths = sorted(directory.iterdir(), key=lambda p: p.name)
    if len(paths) > MAX_FILES:
        raise InputError("more files than audit bound")
    manifest = []
    for p in paths:
        if p.is_symlink() or not p.is_file() or not PATTERN.fullmatch(p.name):
            raise InputError("unsafe or non-observation CSV")
        contents = p.read_bytes()
        manifest.append({
            "filename": p.name,
            "size_bytes": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
        })

    log_state = {
        "supplied": False,
        "sha256": None,
        "start_markers": 0,
        "cap_stop_markers": 0,
        "deinit_markers": 0,
        "csv_triplet_log_markers": 0,
        "failure_markers": 0,
        "account_or_connection_stop_markers": 0,
        "chronology_verified": False,
        "source_independently_authenticated": False,
    }
    stop_evidence = "NOT_ASSESSED"
    issues = set(report["blocking_reasons"])
    if experts_log is not None:
        raw, log = _read_evidence(experts_log, max_bytes=MAX_LOG_BYTES)
        lines = log.splitlines()
        if len(lines) > MAX_LOG_LINES:
            raise InputError("too many log lines")
        # Search exact observer markers rather than unrelated MT4/EA messages.
        log_state.update({
            "supplied": True,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "start_markers": sum(START_MARK in line for line in lines),
            "cap_stop_markers": sum(STOP_MARK in line for line in lines),
            "deinit_markers": sum(DEINIT_MARK in line for line in lines),
            "csv_triplet_log_markers": sum(CSV_MARK in line for line in lines),
            "failure_markers": sum(
                any(marker in line for marker in FAILURE_MARKERS)
                for line in lines),
            "account_or_connection_stop_markers": sum(
                CHANGE_STOP in line for line in lines),
        })
        if log_state["failure_markers"]:
            issues.add("OBSERVER_LOG_ERRORS_PRESENT")
        if log_state["cap_stop_markers"] and report["cycle_count"] < 30:
            issues.add("CAP_STOP_MARKER_BUT_FEWER_THAN_30_CAPTURE_CYCLES")
        if report["cycle_count"] >= 30 and not log_state["cap_stop_markers"]:
            issues.add("CAP_STOP_NOT_PRESENT_IN_SUPPLIED_LOG")
        if log_state["cap_stop_markers"] > 1:
            issues.add("MULTIPLE_CAP_STOP_MARKERS_IN_SUPPLIED_LOG")
        if log_state["start_markers"] > 1:
            issues.add("MULTIPLE_SESSION_STARTS_IN_SUPPLIED_LOG")
        if log_state["cap_stop_markers"] == 1 and report["cycle_count"] == 30:
            stop_evidence = "SELF_REPORTED_CAP_MARKER_AND_30_CSV_CYCLES"
        elif log_state["cap_stop_markers"]:
            stop_evidence = "STOP_LOG_AND_CSV_COUNT_CONFLICT"
        else:
            stop_evidence = "CAP_STOP_NOT_OBSERVED_IN_SUPPLIED_LOG"
    elif report["cycle_count"] >= 30:
        issues.add("STOP_LOG_EVIDENCE_NOT_PROVIDED")

    compiler_state = {
        "supplied": False,
        "sha256": None,
        "self_reported_zero_errors_zero_warnings": False,
        "independently_verified": False,
    }
    if compile_log is not None:
        raw, compile_text = _read_evidence(
            compile_log, max_bytes=MAX_COMPILE_BYTES)
        # Match a compiler summary, but never infer source provenance,
        # terminal identity, or the absence of undocumented warnings.
        zero = bool(re.search(
            r"\b0\s+errors\s*,\s*0\s+warnings\b",
            compile_text, re.IGNORECASE))
        compiler_state.update({
            "supplied": True, "sha256": hashlib.sha256(raw).hexdigest(),
            "self_reported_zero_errors_zero_warnings": zero,
        })
        if not zero:
            issues.add("COMPILE_ZERO_WARNING_EVIDENCE_NOT_PRESENT")

    if report["incomplete_cycle_count"]:
        issues.add("PARTIAL_THREE_PAIR_CYCLES")
    if "CAPTURE_INTERVAL_NOT_60S" in report["blocking_reasons"]:
        issues.add("TIMER_INTERVAL_OUT_OF_TOLERANCE")
    if report["cycle_count"] < 30:
        issues.add("THIRTY_CYCLE_STOP_NOT_YET_OBSERVED")
    if experts_log is None:
        issues.add("EXPERT_LOG_NOT_PROVIDED")
    if compile_log is None:
        issues.add("COMPILE_LOG_NOT_PROVIDED")

    return {
        "schema": SCHEMA,
        "status": "DEMO_OBSERVER_EVIDENCE_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "session_csv_folder": str(directory),
        "csv_manifest": manifest,
        "csv_manifest_count": len(manifest),
        "capture_audit": report,
        "observer_log": log_state,
        "compile_report": compiler_state,
        "stop_evidence_assessment": stop_evidence,
        "observed_issues_and_safety_holds": sorted(issues),
        "actual_mt4_terminal_accessed": False,
        "account_and_broker_independently_authenticated": False,
        "continuous_30_cycle_stoppage_independently_verified": False,
        "automatic_restart_approved": False,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline DEMO capture+log bundle, never GO")
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--experts-log", type=Path)
    p.add_argument("--compile-log", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or not args.out.parent.is_dir() or args.out.is_symlink():
            raise InputError("output exists or unsafe")
        if args.out.resolve() == args.directory.resolve():
            raise InputError("output inside evidence folder")
        result = inspect(
            args.directory, asof_utc=args.asof_utc,
            experts_log=args.experts_log, compile_log=args.compile_log)
        with args.out.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "files": result["csv_manifest_count"],
            "complete_cycles": result["capture_audit"]["complete_cycle_count"],
            "observed_issues_and_safety_holds":
                result["observed_issues_and_safety_holds"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "INVALID_DEMO_OBSERVATION_EVIDENCE",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
