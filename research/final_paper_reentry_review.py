"""Read-only design gate for operator-authorized virtual re-entry.

No latch release, no risk change. Combines journal recovery evidence with the
single historical operator-attributed intentional stop, but never treats
classification as operator approval to clear a risk stop.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research import final_paper_comm_recovery_review as recovery
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_reentry_review_v1"
ATTESTATION_NAME="final_paper_interruption_operator_attestation_20261118.json"


def review(root:Path, *, attestation:Path|None=None)->dict:
    evidence=recovery.review(root)
    record_file=attestation or (
        Path(__file__).resolve().parents[1]/"specs"/ATTESTATION_NAME)
    if (not record_file.is_file() or record_file.is_symlink()
            or any(p.is_symlink() for p in record_file.parents)
            or not 0<record_file.stat().st_size<=16000):
        raise InputError("operator stop attestation absent or unsafe")
    try:
        record=json.loads(record_file.read_text("utf-8-sig"))
    except (ValueError,UnicodeError,OSError) as exc:
        raise InputError("invalid manual stop attestation") from exc
    gap=record.get("observation_gap",{})
    match=(
        record.get("schema")=="fx_final_paper_interruption_operator_attestation_v1"
        and record.get("event_id")=="PAPER_20261118_CYCLE_106_TO_107"
        and record.get("classification")=="OPERATOR_ATTESTED_INTENTIONAL_STOP"
        and record.get("operator_declared_stop_was_manual_and_regular") is True
        and record.get("applicable_to_other_future_stops") is False
        and type(gap) is dict
        and gap.get("previous_journal_cycle")==106
        and gap.get("next_journal_cycle")==107
        and gap.get("unobserved_seconds_pc_derived")==3420
    )
    if not match:
        raise InputError("manual stop attestation mismatch")
    conditions=(
        evidence["ready_for_manual_root_cause_review"] is True
        and evidence["communication_latched"] is True
        and evidence["virtual_open_positions"]==0
        and evidence["pending_signals"]==0
        and evidence["no_other_risk_latches"] is True
    )
    return {
        "schema":SCHEMA,
        "status":"PAPER_MANUAL_REENTRY_APPROVAL_REVIEW_ONLY_NO_GO",
        "historical_event_id":record["event_id"],
        "historical_stop_classification":record["classification"],
        "historical_manual_stop_attested":True,
        "journal_cycles":evidence["journal_cycles"],
        "journal_head_sha256_local_only":
            evidence["journal_head_sha256_local_only"],
        "recent_quote_continuity_and_risk_review_ok":conditions,
        "new_stop_after_historical_event_excluded_by_this_review":False,
        "explicit_release_approval_recorded":False,
        "release_plan_may_be_reviewed_by_operator":conditions,
        "communication_latch_cleared":False,
        "journal_modified_by_review":False,
        "new_virtual_entries_permitted":False,
        "new_paid_ai_calls_permitted":False,
        "broker_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Virtual-paper only release plan review")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=review(args.state_root)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("unsafe reentry output")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,KeyError,TypeError,ValueError,OSError,
            UnicodeError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"PAPER_REENTRY_REVIEW_FAIL_CLOSED_NO_GO",
            "communication_latch_cleared":False,
            "new_virtual_entries_permitted":False,
            "new_paid_ai_calls_permitted":False,
            "broker_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
