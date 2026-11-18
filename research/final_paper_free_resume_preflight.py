"""Read-only preflight for resuming FREE paper price observation.

This does not clear communication/risk latches, renew paid AI, restart an
operator or prove that Windows Python processes are absent. All previous
journal and paid AI ledgers must reconcile. Suitable solely for operator-
supervised free observation after an unexpected shutdown.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_stream_diagnostic as stream
from research import final_paper_ai_continuation_audit as paid
from research import final_paper_status as paper_status
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_free_observation_restart_preflight_v1"
OK_DIAGNOSES = frozenset({
    "FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON",
    "LATEST_MT4_QUOTE_ALREADY_PROCESSED",
})
REASONS = frozenset({
    "RUNNING_LOCK_MUST_NOT_BE_REMOVED",
    "MT4_FRESH_QUOTE_REQUIRED",
    "EXISTING_PAPER_POSITIONS_REQUIRE_REVIEW",
    "PAID_AI_LEDGER_UNRECONCILED",
    "PAPER_STATUS_UNSAFE",
    "DIAGNOSTIC_OUTPUT_UNSAFE",
})


def preflight(root: Path, mt4: Path, *, now: datetime|None=None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise InputError("PAPER_STATUS_UNSAFE")
    lock = root/".single_operator.lock"
    if lock.exists() or lock.is_symlink():
        raise InputError("RUNNING_LOCK_MUST_NOT_BE_REMOVED")
    try:
        diagnostic = stream.diagnose(root,mt4,now=now)
    except (InputError, ValueError, TypeError, OSError) as exc:
        raise InputError("MT4_FRESH_QUOTE_REQUIRED") from exc
    if (diagnostic["diagnosis"] not in OK_DIAGNOSES
            or diagnostic["latest_raw_quote_age_seconds_pc_derived"] is None
            or not 0 <= diagnostic[
                "latest_raw_quote_age_seconds_pc_derived"] <= 120):
        raise InputError("MT4_FRESH_QUOTE_REQUIRED")
    try:
        summary = paper_status.summarize(root,now=now)
    except (InputError, ValueError, TypeError, OSError) as exc:
        raise InputError("PAPER_STATUS_UNSAFE") from exc
    if summary["virtual_open_position_count"] != 0:
        raise InputError("EXISTING_PAPER_POSITIONS_REQUIRE_REVIEW")
    try:
        reconciliation = paid.audit(root)
    except (InputError, ValueError, TypeError, OSError) as exc:
        raise InputError("PAID_AI_LEDGER_UNRECONCILED") from exc
    if (reconciliation["paid_calls_recorded_in_journal"]
            != reconciliation["paid_calls_in_completed_ledgers"]):
        raise InputError("PAID_AI_LEDGER_UNRECONCILED")
    last = diagnostic["last_processed_quote_epoch_pc_unattested"]
    latest = diagnostic["latest_raw_quote_epoch_pc_unattested"]
    gap = latest - last if last else None
    return {
        "schema": SCHEMA,
        "status": "FREE_OBSERVATION_ONLY_RESTART_CANDIDATE_NO_GO",
        "diagnosis": diagnostic["diagnosis"],
        "journal_cycles": reconciliation["journal_cycles"],
        "journal_head_sha256_local_only":
            reconciliation["journal_head_sha256_local_only"],
        "paid_ai_calls_used": reconciliation["paid_calls_recorded_in_journal"],
        "paid_ai_calls_left_under_old_limit":
            reconciliation["remaining_calls_under_existing_limit"],
        "unverified_quote_gap_seconds": gap,
        "communication_gap_will_latch_on_next_quote":
            bool(gap is not None and gap > 600),
        "all_virtual_positions_absent": True,
        "operator_must_verify_no_python_supervisor_process": True,
        "actual_process_absence_verified_by_python": False,
        "start_paid_ai_allowed": False,
        "new_virtual_entries_allowed_by_preflight": False,
        "existing_risk_latches_cleared": False,
        "ledger_or_runtime_lock_modified": False,
        "auto_restart_performed": False,
        "broker_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="Offline-only read-only free observation restart audit")
    parser.add_argument("--state-root",type=Path,required=True)
    parser.add_argument("--mt4-files",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        result=preflight(args.state_root,args.mt4_files)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("DIAGNOSTIC_OUTPUT_UNSAFE")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,KeyError,ValueError,OSError,TypeError,
            UnicodeError,OverflowError) as exc:
        code=(exc.args[0] if isinstance(exc,InputError)
              and exc.args and type(exc.args[0]) is str else "")
        print(json.dumps({
            "schema": SCHEMA,
            "status": "FREE_OBSERVATION_RESTART_PREFLIGHT_FAIL_CLOSED_NO_GO",
            "failure_reason_code":
                code if code in REASONS else "PREFLIGHT_VALIDATION_FAILED",
            "start_paid_ai_allowed": False,
            "new_virtual_entries_allowed_by_preflight": False,
            "auto_restart_performed": False,
            "broker_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
