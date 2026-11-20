"""FINAL-PAPER: read-only unexpected supervisor stop and residual lock triage.

A lock file with no Python PID is a SUSPECTED orphan, not authorization to
remove the lock. The process count is checked separately by Windows.
No auto restarts, paid inference, risk latch clear, journal edits, or orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_stream_diagnostic as stream
from research import final_paper_ai_continuation_audit as ai_audit
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_supervisor_incident_triage_v1"
MAX_LOCK_BYTES = 4096


def investigate(root: Path, mt4: Path, *,
                now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("SUPERVISOR_INCIDENT_CLOCK_UNSAFE")
    # Detect a concurrent journal writer or corrupted/truncated journal.
    state, before_head = runtime._journal_load(root / "journal")
    evidence = stream.diagnose(root, mt4, now=current)
    reconciled = ai_audit.audit(root)
    _, after_head = runtime._journal_load(root / "journal")
    if (before_head != after_head
            or evidence["journal_cycles"] != state["cycle_number"]
            or reconciled["journal_cycles"] != state["cycle_number"]
            or reconciled["journal_head_sha256_local_only"] != before_head):
        raise InputError("SUPERVISOR_INCIDENT_NON_ATOMIC_JOURNAL")
    lock = root / ".single_operator.lock"
    if lock.is_symlink():
        raise InputError("SUPERVISOR_INCIDENT_LOCK_SYMLINK")
    lock_present = lock.exists()
    lock_digest = None
    lock_bytes = None
    lock_modified_utc = None
    if lock_present:
        if (not lock.is_file() or
                not 0 < lock.stat().st_size <= MAX_LOCK_BYTES):
            raise InputError("SUPERVISOR_INCIDENT_UNSAFE_LOCK")
        raw = lock.read_bytes()
        lock_bytes = len(raw)
        lock_digest = hashlib.sha256(raw).hexdigest()
        lock_modified_utc = datetime.fromtimestamp(
            lock.stat().st_mtime, tz=timezone.utc).isoformat()
    last = evidence["last_processed_quote_epoch_pc_unattested"]
    raw_latest = evidence["latest_raw_quote_epoch_pc_unattested"]
    interval = (raw_latest - last if
                type(raw_latest) is int and type(last) is int and last > 0
                else None)
    if interval is not None and interval < 0:
        raise InputError("SUPERVISOR_INCIDENT_SOURCE_BEHIND_JOURNAL")
    long_gap = interval is not None and interval > 600
    last_utc = (datetime.fromtimestamp(last, timezone.utc).isoformat()
                if type(last) is int and last > 0 else None)
    raw_utc = (datetime.fromtimestamp(raw_latest, timezone.utc).isoformat()
               if type(raw_latest) is int and raw_latest > 0 else None)
    stop_latched = state["communication_latched"] is True
    return {
        "schema": SCHEMA,
        "status": "UNEXPECTED_PAPER_SUPERVISOR_STOP_FORENSICS_ONLY_NO_GO",
        "journal_cycles": state["cycle_number"],
        "journal_head_sha256_local_only": before_head,
        "last_consumed_quote_utc_pc_unattested": last_utc,
        "latest_mt4_quote_utc_pc_unattested": raw_utc,
        "unconsumed_quote_gap_seconds_pc_derived": interval,
        "new_interruption_longer_than_600_seconds": long_gap,
        "quote_stream_diagnosis": evidence["diagnosis"],
        "latest_raw_quote_age_seconds_pc_derived":
            evidence["latest_raw_quote_age_seconds_pc_derived"],
        "runtime_lock_exists": lock_present,
        "runtime_lock_bytes": lock_bytes,
        "runtime_lock_sha256_local_only": lock_digest,
        "runtime_lock_last_write_utc_pc_unattested": lock_modified_utc,
        "old_20261118_comm_release_approval_covers_this_gap": False,
        "journal_communication_latched": stop_latched,
        "other_risk_latches": {
            name: state[name] for name in (
                "daily_loss_latched", "dd4_latched", "dd5_latched")
        },
        "virtual_open_position_count": len(state["positions"]),
        "pending_signal_count": len(state["pending_signals"]),
        "paid_calls_journal": reconciled["paid_calls_recorded_in_journal"],
        "paid_calls_completed_ledgers":
            reconciled["paid_calls_in_completed_ledgers"],
        "python_supervisor_process_count": "CHECK_ON_WINDOWS_NOT_ATTESTED",
        "lock_is_proven_orphan": False,
        "root_cause_of_python_exit_proven": False,
        "recovery_requires_operator_investigation": True,
        "lock_file_removed_or_renamed": False,
        "supervisor_restarted": False,
        "communication_latch_released": False,
        "new_virtual_positions_permitted": False,
        "new_paid_ai_calls_permitted": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Forensic read-only analysis of stopped virtual supervisor")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--mt4-files", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = investigate(args.state_root, args.mt4_files)
        out = args.out
        if (out.exists() or out.is_symlink()
                or not out.parent.is_dir() or out.parent.is_symlink()):
            raise InputError("SUPERVISOR_INCIDENT_REPORT_ALREADY_EXISTS")
        with out.open("x", encoding="utf-8") as stream_out:
            json.dump(report, stream_out, ensure_ascii=False, indent=2,
                      allow_nan=False)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, KeyError,
            OverflowError, TypeError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "SUPERVISOR_INCIDENT_REVIEW_FAIL_CLOSED_NO_GO",
            "lock_file_removed_or_renamed": False,
            "supervisor_restarted": False,
            "new_virtual_positions_permitted": False,
            "new_paid_ai_calls_permitted": False,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
