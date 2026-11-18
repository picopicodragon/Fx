"""FINAL-PAPER-16: offline AI-call and journal reconciliation before renewal.

Not an API budget authorizer. Never infers actual JPY costs from call counts.
Requires no API key, broker connection or model inference. All ambiguous
paid-dispatch ledgers and cost evidence stay blocked for user review.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from research import final_demo_http401_recovery as paid_ledgers
from research import final_paper_runtime as runtime
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_ai_continuation_audit_v1"
CODE = frozenset({
    "PAPER_STATE_ROOT_MISSING", "PAID_LEDGER_PENDING_OR_UNRECONCILED",
    "PAPER_JOURNAL_AND_PAID_LEDGER_COUNT_MISMATCH",
    "PAID_LEDGER_MODEL_RESPONSE_INVALID", "PAID_LEDGER_FILENAME_INVALID",
    "PAID_LEDGER_FOLDER_INVALID", "UNSAFE_AUDIT_OUTPUT",
})
FILE_NAME = re.compile(r"^ai_(USDJPY|EURJPY|EURUSD)_[A-Za-z0-9_]+\.json$")


def audit(root: Path) -> dict:
    if (not root.is_dir() or root.is_symlink()
            or any(parent.is_symlink() for parent in root.parents)):
        raise InputError("PAPER_STATE_ROOT_MISSING")
    state, head = runtime._journal_load(root / "journal")
    ai_folder = root / "ai_research"
    if (not ai_folder.is_dir() or ai_folder.is_symlink()
            or any(parent.is_symlink() for parent in ai_folder.parents)):
        raise InputError("PAID_LEDGER_FOLDER_INVALID")
    # Reject any unknown possibly billed request; legitimate reviewed 401
    # is separate from a completed pair of paid model responses.
    try:
        preflight = paid_ledgers.check_directory(ai_folder)
    except InputError as exc:
        raise InputError("PAID_LEDGER_PENDING_OR_UNRECONCILED") from exc
    completed_ledgers = 0
    for file in ai_folder.glob("ai_*.json"):
        if FILE_NAME.fullmatch(file.name) is None:
            raise InputError("PAID_LEDGER_FILENAME_INVALID")
        status, _ = paid_ledgers._read_ledger(file)
        if status["stage"] == "COMPLETE":
            if (status["pending_role"] is not None
                    or status["analyst"] is None
                    or status["reviewer"] is None):
                raise InputError("PAID_LEDGER_MODEL_RESPONSE_INVALID")
            completed_ledgers += 1
    calls_from_complete_ledgers = completed_ledgers * 2
    calls_from_journal = state["paid_inference_calls"]
    if (type(calls_from_journal) is not int
            or calls_from_journal < 0
            or calls_from_journal > runtime.MAX_PAID_LIFETIME
            or calls_from_complete_ledgers != calls_from_journal):
        # In particular, a complete AI result with no corresponding durable
        # paper journal is an orphan. Never silently re-run that inference.
        raise InputError("PAPER_JOURNAL_AND_PAID_LEDGER_COUNT_MISMATCH")
    remaining = runtime.MAX_PAID_LIFETIME - calls_from_journal
    return {
        "schema": SCHEMA,
        "status": "PAPER_AI_COUNTER_RECONCILED_BILLING_UNVERIFIED_NO_GO",
        "journal_head_sha256_local_only": head,
        "journal_cycles": state["cycle_number"],
        "completed_two_model_ledgers": completed_ledgers,
        "paid_calls_recorded_in_journal": calls_from_journal,
        "paid_calls_in_completed_ledgers": calls_from_complete_ledgers,
        "previous_401_rejections_manually_reviewed":
            preflight["operator_reviewed_http401"],
        "existing_call_limit": runtime.MAX_PAID_LIFETIME,
        "remaining_calls_under_existing_limit": remaining,
        "estimated_or_actual_api_cost_jpy": None,
        "monthly_api_spend_independently_verified": False,
        "budget_renewal_authorized": False,
        "new_paid_inference_allowed_by_this_audit": False,
        "new_broker_orders_permitted": False,
        "virtual_only": True,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Read-only reconciliation of final paper AI ledger and journal")
    p.add_argument("--state-root", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = audit(args.state_root)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("UNSAFE_AUDIT_OUTPUT")
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2,
                      allow_nan=False)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, ValueError, TypeError, KeyError, OSError,
            OverflowError, UnicodeError) as exc:
        code = (exc.args[0] if isinstance(exc, InputError)
                and exc.args and type(exc.args[0]) is str else "")
        print(json.dumps({
            "schema": SCHEMA,
            "status": "PAPER_AI_RECONCILIATION_FAIL_CLOSED_NO_GO",
            "failure_reason_code": code if code in CODE
                 else "PAPER_AI_RECONCILIATION_VALIDATION_FAILED",
            "new_paid_inference_allowed_by_this_audit": False,
            "new_broker_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
