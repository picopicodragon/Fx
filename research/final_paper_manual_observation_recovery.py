"""One-time operator-reviewed lock ARCHIVE for FREE paper observation only.

CAUTION: This is NOT communication-latch release. Never run from an unattended
scheduler, never when a Python paper supervisor is present. Windows wrapper
must explicitly attest process absence, then operator opts in. No live virtual
entry, no paid API, no MT4 order, no automatic process launch.

The original lock bytes and hash are preserved under a distinct archive name,
not deleted. Only the documented November 20 incident journal head is eligible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_supervisor_incident as incident
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_free_observation_operator_recovery_v1"
APPROVAL = "ACKNOWLEDGE_20261120_GAP_RESUME_UNPAID_OBSERVATION_ONLY"
EXPECTED_CYCLES = 550
EXPECTED_LAST_QUOTE = 1795004931
LOCK_BYTES = b"running; review journal on unexpected stop\r\n"
# Windows text-mode lock creation converts LF to CRLF. The 2026-11-20
# observed 44-byte lock has this exact SHA256; never accept arbitrary text.
LOCK_SHA256_OBSERVED = "7298c233cd837ff6c403e25dbf3a8632031ad57a4e35dad0a0c66aad2ccee4f1"
RECEIPT_NAME = "manual_observation_lock_recovery_20261120.json"
ARCHIVE_NAME = "manual_observation_lock_20261120.archived"


def recover(root: Path, mt4: Path, *, operator_approval: str,
            windows_absence_checked: bool,
            now: datetime | None = None) -> dict:
    if (operator_approval != APPROVAL
            or windows_absence_checked is not True):
        raise InputError("OBSERVER_RESTART_OPERATOR_CONFIRMATION_REQUIRED")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset().total_seconds() != 0:
        raise InputError("OBSERVER_RESTART_UTC_CLOCK_REQUIRED")
    if (not root.is_dir() or root.is_symlink()
            or any(x.is_symlink() for x in root.parents)
            or not mt4.is_dir() or mt4.is_symlink()
            or not str(mt4.resolve()).lower().endswith(
                str(Path("MQL4") / "Files").lower())):
        raise InputError("OBSERVER_RESTART_SOURCE_PATH_UNSAFE")
    lock = root / ".single_operator.lock"
    receipt = root / RECEIPT_NAME
    archive = root / ARCHIVE_NAME
    old_permit = root / "manual_comm_release_20261118.json"
    if (receipt.exists() or receipt.is_symlink()
            or archive.exists() or archive.is_symlink()
            or old_permit.exists() or old_permit.is_symlink()):
        raise InputError("OBSERVER_RESTART_PREVIOUS_PERMIT_OR_ARCHIVE_PRESENT")
    if (not lock.is_file() or lock.is_symlink()
            or lock.read_bytes() != LOCK_BYTES
            or hashlib.sha256(lock.read_bytes()).hexdigest()
                != LOCK_SHA256_OBSERVED):
        raise InputError("OBSERVER_RESTART_LOCK_CONTENT_UNEXPECTED")
    record = incident.investigate(root, mt4, now=current)
    if (record["journal_cycles"] != EXPECTED_CYCLES
            or record["last_consumed_quote_utc_pc_unattested"] !=
                datetime.fromtimestamp(
                    EXPECTED_LAST_QUOTE, tz=timezone.utc).isoformat()
            or record["journal_communication_latched"] is not True
            or record["runtime_lock_exists"] is not True
            or record["quote_stream_diagnosis"] !=
                "FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON"
            or record["new_interruption_longer_than_600_seconds"] is not True
            or type(record["latest_raw_quote_age_seconds_pc_derived"]) is not int
            or not 0 <= record["latest_raw_quote_age_seconds_pc_derived"] <= 120
            or record["virtual_open_position_count"] != 0
            or record["pending_signal_count"] != 0
            or any(value is not False
                   for value in record["other_risk_latches"].values())
            or record["paid_calls_journal"] != 6
            or record["paid_calls_completed_ledgers"] != 6
            or record["runtime_lock_sha256_local_only"] !=
                LOCK_SHA256_OBSERVED):
        raise InputError("OBSERVER_RESTART_SAFETY_EVIDENCE_INCOMPLETE")
    # No new process can be proven absent *inside* Python. The local
    # PowerShell wrapper must re-check all Win32 Python process args just
    # before calling. This is NOT a general automatic crash recovery.
    state, head = runtime._journal_load(root / "journal")
    if (state["cycle_number"] != EXPECTED_CYCLES
            or state["last_quote_epoch"] != EXPECTED_LAST_QUOTE
            or head != record["journal_head_sha256_local_only"]):
        raise InputError("OBSERVER_RESTART_CONCURRENT_JOURNAL_CHANGE")
    evidence = {
        "schema": SCHEMA,
        "incident_id": "PAPER_20261120_PROCESS_ABSENT_JOURNAL_550",
        "operator_approval": APPROVAL,
        "authorized_scope": "FREE_READ_ONLY_QUOTE_MONITORING_ONLY",
        "operator_checked_win32_paper_supervisor_count_zero": True,
        "original_journal_cycles": EXPECTED_CYCLES,
        "original_journal_head_sha256": head,
        "original_lock_sha256": LOCK_SHA256_OBSERVED,
        "original_lock_archive_name": ARCHIVE_NAME,
        "created_utc_pc_unattested": current.isoformat(),
        "new_38h_communication_gap_release_authorized": False,
        "communication_latched_unchanged": True,
        "dd_risk_latches_unchanged": True,
        "new_virtual_entries_authorized": False,
        "new_paid_ai_calls_authorized": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
    }
    with receipt.open("x", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    # Preserve the original lock byte-for-byte. An interrupted archival step
    # must be investigated; the process is NEVER automatically restarted.
    os.rename(lock, archive)
    if archive.read_bytes() != LOCK_BYTES:
        raise InputError("OBSERVER_RESTART_ARCHIVED_LOCK_UNSAFE")
    return {
        "schema": SCHEMA,
        "status": "MANUAL_LOCK_ARCHIVED_OBSERVATION_RESTART_CANDIDATE_NO_GO",
        "receipt": str(receipt),
        "original_lock_archived_at": str(archive),
        "supervisor_restarted": False,
        "communication_latch_released": False,
        "new_virtual_entries_permitted": False,
        "new_paid_ai_calls_permitted": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Explicit manual stale lock archive for FREE quote observation")
    p.add_argument("--state-root", required=True, type=Path)
    p.add_argument("--mt4-files", required=True, type=Path)
    p.add_argument("--operator-approval", default="")
    p.add_argument("--windows-absence-checked", action="store_true")
    args = p.parse_args(argv)
    try:
        result = recover(
            args.state_root, args.mt4_files,
            operator_approval=args.operator_approval,
            windows_absence_checked=args.windows_absence_checked)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, KeyError,
            OverflowError, TypeError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "MANUAL_OBSERVATION_LOCK_RECOVERY_FAIL_CLOSED_NO_GO",
            "supervisor_restarted": False,
            "communication_latch_released": False,
            "new_virtual_entries_permitted": False,
            "new_paid_ai_calls_permitted": False,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
