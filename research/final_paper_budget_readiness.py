"""Offline monthly JPY cost readiness, no paid dispatch or budget renewal.

Operator-supplied evidence is a claim about billing, NOT independent provider
attestation. The old lifetime 6-call cap remains active regardless of result.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from research import final_paper_ai_continuation_audit as ai
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_manual_billing_reconciliation_v1"
EVIDENCE_SCHEMA="fx_final_paper_operator_billing_statement_v1"
JPY_CAP=Decimal("3000.00")
MONTH=re.compile(r"^20[0-9]{2}-(0[1-9]|1[0-2])$")
VALUE=re.compile(r"^(0|[1-9][0-9]{0,7})(\.[0-9]{1,2})?$")


def _jpy(value:object)->Decimal:
    if type(value) is not str or VALUE.fullmatch(value) is None:
        raise InputError("invalid JPY billing amount")
    try:
        amount=Decimal(value)
    except InvalidOperation as exc:
        raise InputError("invalid JPY billing amount") from exc
    if not amount.is_finite() or amount<0:
        raise InputError("invalid JPY billing amount")
    return amount


def review(root:Path, statement:Path|None=None, *,
           now:datetime|None=None)->dict:
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("UTC billing review clock required")
    reconciliation=ai.audit(root)
    billed=None
    reserve=None
    arithmetic=False
    human_claim=False
    period=current.strftime("%Y-%m")
    if statement is not None:
        if (not statement.is_file() or statement.is_symlink()
                or any(p.is_symlink() for p in statement.parents)
                or not 0<statement.stat().st_size<=8192):
            raise InputError("unsafe manual billing statement file")
        try:
            record=json.loads(statement.read_text("utf-8-sig"))
        except (OSError,UnicodeError,ValueError) as exc:
            raise InputError("manual billing statement malformed") from exc
        if (type(record) is not dict or set(record)!={
              "schema","month_utc","captured_at_utc",
              "source","currency","billed_jpy",
              "future_two_call_reserve_jpy",
              "completed_paid_calls_observed","operator_checked_provider_page"}
              or record["schema"]!=EVIDENCE_SCHEMA
              or record["currency"]!="JPY"
              or record["source"]!="OPENAI_PROVIDER_BILLING_OPERATOR_TRANSCRIPTION"
              or type(record["operator_checked_provider_page"]) is not bool
              or type(record["completed_paid_calls_observed"]) is not int
              or record["completed_paid_calls_observed"]<0
              or type(record["month_utc"]) is not str
              or MONTH.fullmatch(record["month_utc"]) is None
              or record["month_utc"]!=period):
            raise InputError("invalid billing statement schema/month")
        try:
            captured=datetime.fromisoformat(
                record["captured_at_utc"].replace("Z","+00:00"))
        except (AttributeError,ValueError) as exc:
            raise InputError("invalid billing statement capture time") from exc
        if (captured.tzinfo is None or
                captured.utcoffset().total_seconds()!=0 or
                not 0<=(current-captured).total_seconds()<=86400):
            raise InputError("billing snapshot stale or future")
        if record["completed_paid_calls_observed"]!=reconciliation[
                "paid_calls_recorded_in_journal"]:
            raise InputError("provider and paper AI call counts do not match")
        billed=_jpy(record["billed_jpy"])
        reserve=_jpy(record["future_two_call_reserve_jpy"])
        arithmetic=billed+reserve<=JPY_CAP and reserve>0
        human_claim=record["operator_checked_provider_page"]
    return {
        "schema":SCHEMA,
        "status":"MONTHLY_JPY_BILLING_REVIEW_ONLY_NO_GO",
        "billing_month_utc":period,
        "operator_billing_statement_supplied":statement is not None,
        "operator_claimed_provider_page_checked":human_claim,
        "paid_calls_in_paper_journal":
            reconciliation["paid_calls_recorded_in_journal"],
        "paid_call_ledgers_reconciled":True,
        "monthly_budget_limit_jpy":format(JPY_CAP,".2f"),
        "billed_jpy_operator_reported":
            format(billed,".2f") if billed is not None else None,
        "two_call_reserve_jpy_operator_reported":
            format(reserve,".2f") if reserve is not None else None,
        "arithmetic_room_for_reserved_two_calls":arithmetic,
        "provider_billing_independently_verified":False,
        "operator_approved_paid_renewal":False,
        "old_lifetime_paid_call_cap":6,
        "old_lifetime_paid_call_cap_exhausted":
            reconciliation["remaining_calls_under_existing_limit"]==0,
        "future_paid_inference_authorized":False,
        "new_virtual_entries_authorized":False,
        "broker_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(
        description="Read-only 3000 JPY/month billing evidence audit")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--operator-statement",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=review(args.state_root,args.operator_statement)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("unsafe billing report output")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,KeyError,TypeError,ValueError,
            UnicodeError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"MONTHLY_JPY_BILLING_FAIL_CLOSED_NO_GO",
            "future_paid_inference_authorized":False,
            "new_virtual_entries_authorized":False,
            "broker_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
