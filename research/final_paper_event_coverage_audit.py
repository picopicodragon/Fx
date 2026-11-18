"""No-network audit of locally archived official macro schedule candidates.

Validates supplied known-event structure and visible currency coverage,
without treating event snapshots as an independently authenticated or complete
USD/EUR/JPY macro calendar. A zero-event list is NOT proof of no risk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_event_blackout as guard
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_macro_archive_coverage_audit_v1"
CURRENCIES=("USD","EUR","JPY")


def audit(calendar:Path|None, *, now:datetime|None=None)->dict:
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("timezone-aware current time required")
    if calendar is None:
        return {
            "schema":SCHEMA,
            "status":"MACRO_CURRENCY_COVERAGE_EVIDENCE_MISSING_NO_GO",
            "calendar_supplied":False,
            "locally_archived_event_count":0,
            "event_currencies_in_snapshot":[],
            "currencies_without_any_event_evidence":list(CURRENCIES),
            "calendar_sha256_local_only":None,
            "known_blackout_active_now":False,
            "calendar_source_independently_attested":False,
            "all_important_events_covered":False,
            "consensus_captured_before_release":False,
            "entry_or_paid_ai_activation_authorized":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }
    if (not calendar.is_file() or calendar.is_symlink()
            or any(p.is_symlink() for p in calendar.parents)
            or not 0<calendar.stat().st_size<=32000):
        raise InputError("unsafe calendar archive")
    result=guard.check(calendar,int(current.timestamp()),now=current)
    # guard.check parsed and validated official-host URLs, expiration and UTC.
    # Parse exactly the same local file again; its immutable hash is evidence
    # of local bytes, NOT evidence that BLS/ECB/BOJ actually published them.
    raw=calendar.read_bytes()
    candidate=json.loads(raw.decode("utf-8-sig"))
    currencies=set(event["currency"] for event in candidate["events"])
    return {
        "schema":SCHEMA,
        "status":"MACRO_LOCAL_ARCHIVE_VALIDATED_NOT_ATTESTED_NO_GO",
        "calendar_supplied":True,
        "locally_archived_event_count":result["official_source_event_count"],
        "event_currencies_in_snapshot":sorted(currencies),
        "currencies_without_any_event_evidence":
            sorted(set(CURRENCIES)-currencies),
        "calendar_sha256_local_only":hashlib.sha256(raw).hexdigest(),
        "known_blackout_active_now":result["active_known_blackout"],
        "calendar_source_independently_attested":False,
        "all_important_events_covered":False,
        "consensus_captured_before_release":False,
        "entry_or_paid_ai_activation_authorized":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(
        description="No-cost USD/EUR/JPY schedule archive gap audit")
    p.add_argument("--event-blackout-file",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=audit(args.event_blackout_file)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("unsafe new macro audit output")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,UnicodeError,OSError,ValueError,TypeError,KeyError,
            OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"MACRO_ARCHIVE_AUDIT_FAIL_CLOSED_NO_GO",
            "all_important_events_covered":False,
            "consensus_captured_before_release":False,
            "entry_or_paid_ai_activation_authorized":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
