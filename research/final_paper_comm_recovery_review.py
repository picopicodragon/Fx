"""FINAL-PAPER: read-only, evidence-only communication recovery review.

Checks latest 10 consecutive journaled DEMO observations after a LEVEL2 gap.
Never changes a latch, market data, API budget, broker orders or journal.
A successful review is NOT authority for new virtual entries or a release.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_status as status
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_communication_recovery_review_v1"
MIN_CONSECUTIVE = 10
MAX_STEP_SECONDS = 90
MIN_STEP_SECONDS = 30
MAX_LATEST_AGE_SECONDS = 120
SAFE_REASONS = frozenset({
    "RECOVERY_INPUT_UNSAFE", "RECOVERY_STATE_UNSAFE",
    "RECOVERY_JOURNAL_INVALID", "RECOVERY_OUTPUT_EXISTS",
})


def review(root: Path, *, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("RECOVERY_INPUT_UNSAFE")
    if (not root.is_dir() or root.is_symlink()
            or any(p.is_symlink() for p in root.parents)
            or (root/".single_operator.lock").is_symlink()):
        raise InputError("RECOVERY_INPUT_UNSAFE")
    state, journal_head = runtime._journal_load(root/"journal")
    snapshot = status.summarize(root,now=current)
    # The observer might still be adding journal records; fail closed rather
    # than mixing snapshots from two points in time.
    if (snapshot["completed_cycles"] != state["cycle_number"]
            or snapshot["journal_head_sha256_local_only"] != journal_head):
        raise InputError("RECOVERY_JOURNAL_INVALID")
    if (state.get("virtual_only") is not True
            or state.get("broker_orders_permitted") is not False
            or state.get("jev_required") is not False):
        raise InputError("RECOVERY_STATE_UNSAFE")
    if (type(state.get("paid_inference_calls")) is not int
            or state["paid_inference_calls"]>runtime.MAX_PAID_LIFETIME):
        raise InputError("RECOVERY_STATE_UNSAFE")
    count = state["cycle_number"]
    chain = []
    # runtime._journal_load has already hash-verified the entire chain.
    for i in range(max(1,count-MIN_CONSECUTIVE),count+1):
        file = root/"journal"/f"{i:08d}.json"
        payload = json.loads(file.read_text("utf-8-sig"))
        entry = payload["state"]
        if (type(entry.get("last_quote_epoch")) is not int
                or entry.get("cycle_number") != i
                or entry.get("communication_latched") is not True
                or entry.get("virtual_only") is not True
                or entry.get("broker_orders_permitted") is not False):
            break
        chain.append(entry["last_quote_epoch"])
    valid_intervals = (
        len(chain)>=MIN_CONSECUTIVE
        and all(MIN_STEP_SECONDS<=b-a<=MAX_STEP_SECONDS
                for a,b in zip(chain,chain[1:]))
    )
    safety_block = any(state.get(k) is True for k in (
        "dd4_latched","dd5_latched","daily_loss_latched"))
    position_count = len(state.get("positions",[]))
    pending_count = len(state.get("pending_signals",[]))
    age = snapshot["last_recorded_quote_age_seconds_pc_derived"]
    recent = (type(age) is int and 0<=age<=MAX_LATEST_AGE_SECONDS)
    evidence_sufficient = (
        valid_intervals and recent and not safety_block
        and position_count==0 and pending_count==0
        and state.get("communication_latched") is True
    )
    return {
        "schema": SCHEMA,
        "status": "COMM_RECOVERY_EVIDENCE_REVIEW_ONLY_NO_GO",
        "journal_cycles": count,
        "journal_head_sha256_local_only": journal_head,
        "communication_latched": state["communication_latched"],
        "consecutive_observations_minimum": MIN_CONSECUTIVE,
        "consecutive_quote_sequence_evidence_ok": valid_intervals,
        "quote_latest_age_seconds_pc_unattested": age,
        "quote_fresh_enough_pc_unattested": recent,
        "no_other_risk_latches": not safety_block,
        "virtual_open_positions": position_count,
        "pending_signals": pending_count,
        "paid_ai_calls_lifetime": state["paid_inference_calls"],
        "paid_ai_calls_remaining_under_current_limit":
            runtime.MAX_PAID_LIFETIME-state["paid_inference_calls"],
        "ready_for_manual_root_cause_review": evidence_sufficient,
        "root_cause_explained": False,
        "independent_broker_clock_attested": False,
        "independent_calendar_coverage_attested": False,
        "operator_approval_to_clear_communication_latch_recorded": False,
        "communication_latch_cleared": False,
        "new_virtual_entries_permitted": False,
        "new_paid_ai_calls_permitted": False,
        "broker_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="Read-only evidence review, NOT a risk latch clear")
    parser.add_argument("--state-root",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        output=review(args.state_root)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("RECOVERY_OUTPUT_EXISTS")
        with args.out.open("x",encoding="utf-8") as handle:
            json.dump(output,handle,ensure_ascii=False,
                      allow_nan=False,indent=2)
        print(json.dumps(output,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,ValueError,TypeError,KeyError,
            UnicodeError,OverflowError) as exc:
        reason=(exc.args[0] if isinstance(exc,InputError)
                and exc.args and type(exc.args[0]) is str else "")
        print(json.dumps({
            "schema": SCHEMA,
            "status": "COMM_RECOVERY_REVIEW_FAIL_CLOSED_NO_GO",
            "failure_reason_code": (
                reason if reason in SAFE_REASONS else "RECOVERY_VALIDATION_FAILED"),
            "communication_latch_cleared": False,
            "new_virtual_entries_permitted": False,
            "new_paid_ai_calls_permitted": False,
            "broker_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
