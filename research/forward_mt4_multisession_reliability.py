"""FWD-095..104: multi-session MT4 DEMO observation research reliability audit.

Offline only. No access to MT4, network, broker, order execution or unattended
scheduling. User-provided CSV and log files are NOT authenticated evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from research.forward_mt4_observation_evidence import inspect as inspect_evidence
from research.forward_mt4_timer_capture_audit import EXPECTED_INTERVAL, INTERVAL_TOLERANCE
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_mt4_multisession_reliability_v1"
MAX_SESSIONS = 24
MAX_TOTAL_CSV = 720
SESSION_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")

# Each observation cycle comprises exactly three pair CSVs, and the first
# validated capture time is the session-local start of *observed evidence*.
def inspect(sessions: list[tuple[str, Path]], *, asof_utc: str,
            experts: dict[str, Path] | None = None,
            compiles: dict[str, Path] | None = None) -> dict:
    cutoff = timestamp(asof_utc)
    if (type(sessions) is not list or not 1 <= len(sessions) <= MAX_SESSIONS
            or any(type(x) is not tuple or len(x) != 2
                   for x in sessions)):
        raise InputError("invalid session count/shape")
    experts = {} if experts is None else experts
    compiles = {} if compiles is None else compiles
    if not isinstance(experts, dict) or not isinstance(compiles, dict):
        raise InputError("invalid log mapping")
    labels = [label for label, _ in sessions]
    if (len(labels) != len(set(labels))
            or any(not isinstance(label, str) or
                   not SESSION_LABEL.fullmatch(label) for label in labels)
            or any(label not in labels for label in [*experts, *compiles])):
        raise InputError("duplicate/unsafe labels")
    resolved_dirs = []
    for _, path in sessions:
        if not isinstance(path, Path) or path.is_symlink() or not path.is_dir():
            raise InputError("invalid session folder")
        resolved_dirs.append(path.resolve(strict=True))
    if len(resolved_dirs) != len(set(resolved_dirs)):
        raise InputError("same source folder used twice")
    report_sessions = []
    occurrences: dict[str, str] = {}
    chronological: list[tuple[datetime, datetime, str]] = []
    total_files = 0
    total_cycles = 0
    full_cycles = 0
    incomplete_cycles = 0
    all_issues: set[str] = set()
    for label, directory in sessions:
        evidence = inspect_evidence(
            directory, asof_utc=asof_utc,
            experts_log=experts.get(label), compile_log=compiles.get(label))
        manifest = evidence["csv_manifest"]
        cycles = evidence["capture_audit"]["cycles"]
        total_files += len(manifest)
        if total_files > MAX_TOTAL_CSV:
            raise InputError("too many CSV snapshots")
        total_cycles += len(cycles)
        full_cycles += evidence["capture_audit"]["complete_cycle_count"]
        incomplete_cycles += evidence["capture_audit"]["incomplete_cycle_count"]
        session_issues = set(evidence["observed_issues_and_safety_holds"])
        for record in manifest:
            fingerprint = record["sha256"]
            if fingerprint in occurrences:
                session_issues.add("CSV_REPLAY_ACROSS_SESSIONS")
                all_issues.add("CSV_REPLAY_ACROSS_SESSIONS")
            else:
                occurrences[fingerprint] = label
        times = [timestamp(cycle["capture_utc"]) for cycle in cycles]
        if not times:
            raise InputError("session without cycles")
        if len(times) > 30:
            session_issues.add("SESSION_EXCEEDS_30_CAPTURE_CYCLES")
        if len(times) >= 2:
            intervals = evidence["capture_audit"]["cycle_intervals_seconds"]
            if any(abs(delta - EXPECTED_INTERVAL) > INTERVAL_TOLERANCE
                   for delta in intervals):
                session_issues.add("TIMER_INTERVAL_OUT_OF_TOLERANCE")
        duration = int((times[-1] - times[0]).total_seconds())
        if duration < 0:
            raise InputError("invalid timestamps")
        chronological.append((times[0], times[-1], label))
        all_issues.update(session_issues)
        report_sessions.append({
            "label": label, "file_count": len(manifest),
            "first_observation_utc": cycles[0]["capture_utc"],
            "last_observation_utc": cycles[-1]["capture_utc"],
            "observation_span_seconds": duration,
            "cycles": len(cycles),
            "complete_cycles": evidence["capture_audit"]["complete_cycle_count"],
            "incomplete_cycles": evidence["capture_audit"]["incomplete_cycle_count"],
            "interval_seconds": evidence["capture_audit"]["cycle_intervals_seconds"],
            "stop_evidence_assessment": evidence["stop_evidence_assessment"],
            "expert_log_supplied": evidence["observer_log"]["supplied"],
            "compile_log_supplied": evidence["compile_report"]["supplied"],
            "session_issues_and_holds": sorted(session_issues),
            "csv_sha256_manifest": manifest,
        })
    ordered = sorted(chronological)
    boundaries = []
    for previous, current in zip(ordered, ordered[1:]):
        # Equal endpoint is a duplicate capture time, and overlapping
        # windows cannot be attested as independent sequential sessions.
        gap = int((current[0] - previous[1]).total_seconds())
        overlap = gap <= 0
        if overlap:
            all_issues.add("OVERLAPPING_SESSION_OBSERVATION_WINDOWS")
        boundaries.append({
            "earlier_label": previous[2], "later_label": current[2],
            "between_sessions_seconds": gap,
            "overlap_or_boundary_collision": overlap,
            "is_expected_collection_gap": None,
        })
    if len(sessions) < 2:
        all_issues.add("MULTISESSION_COMPARISON_NOT_YET_POSSIBLE")
    all_issues.add("SOURCES_AND_BROKER_CLOCK_NOT_INDEPENDENTLY_ATTESTED")
    all_issues.add("DEMO_IDENTITY_NOT_INDEPENDENTLY_ATTESTED")
    all_issues.add("TRADING_AUTHORIZATION_PROHIBITED")

    return {
        "schema": SCHEMA,
        "status": "MT4_MULTISESSION_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "session_count": len(sessions),
        "csv_file_count": total_files,
        "observed_cycle_count": total_cycles,
        "complete_cycle_count": full_cycles,
        "incomplete_cycle_count": incomplete_cycles,
        "sessions": report_sessions,
        "between_session_boundaries": boundaries,
        "issues_and_safety_holds": sorted(all_issues),
        "broker_server_timezone_attested": False,
        "continuous_long_duration_mt4_operation_verified": False,
        "stop_at_30_cycles_independently_verified": False,
        "operating_system_or_mt4_accessed": False,
        "auto_trading_enabled": False,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _parse_labeled_entries(values: list[str], option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise InputError("use LABEL=PATH for " + option)
        label, path = item.split("=", 1)
        if (not SESSION_LABEL.fullmatch(label) or not path
                or label in result):
            raise InputError("invalid or repeated label for " + option)
        result[label] = Path(path)
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Audit copied DEMO MT4 sessions; never authorize trading")
    p.add_argument("--session", action="append", required=True,
                   help="LABEL=CSV_FOLDER, repeat per observed session")
    p.add_argument("--experts", action="append", default=[],
                   help="LABEL=EXPERTS_UTF8_TXT, optional")
    p.add_argument("--compile", action="append", default=[],
                   help="LABEL=COMPILER_UTF8_TXT, optional")
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        sessions = list(_parse_labeled_entries(
            args.session, "--session").items())
        experts = _parse_labeled_entries(args.experts, "--experts")
        compiles = _parse_labeled_entries(args.compile, "--compile")
        if args.out.is_symlink() or args.out.exists() or not args.out.parent.is_dir():
            raise InputError("unsafe output or overwrite")
        # Reject output inside any evidence folder, preserving raw evidence.
        if any(path.resolve() in args.out.resolve().parents
               for _, path in sessions):
            raise InputError("report path inside evidence source folder")
        result = inspect(
            sessions, asof_utc=args.asof_utc,
            experts=experts, compiles=compiles)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "session_count": result["session_count"],
            "files": result["csv_file_count"],
            "complete_cycles": result["complete_cycle_count"],
            "incomplete_cycles": result["incomplete_cycle_count"],
            "issues_and_safety_holds": result["issues_and_safety_holds"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "INVALID_MULTISESSION_MT4_EVIDENCE",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
