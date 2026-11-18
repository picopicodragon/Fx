"""Offline BLS ICS -> known-USD-event research snapshot only.

Never downloads public data, invents event times, grants independent calendar
coverage or enables MT4/new virtual orders. High-impact releases recognized
by explicit conservative labels. Unrecognized titles are not an assurance
that there are no important releases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

from research import forward_bls_calendar as bls
from research import final_paper_event_blackout as guard
from research.offline_backtest import InputError

IMPORTANT_PREFIXES=(
    ("employment situation", "CRITICAL"),
    ("consumer price index", "CRITICAL"),
    ("producer price index", "HIGH"),
    ("employment cost index", "HIGH"),
    ("productivity and costs", "HIGH"),
    ("import and export price", "HIGH"),
    ("real earnings", "HIGH"),
)


def convert(file:Path, *, asof_utc:str, days_forward:int=14)->dict:
    if (not file.is_file() or file.is_symlink()
            or any(p.is_symlink() for p in file.parents)
            or not 0<file.stat().st_size<=bls.MAX_ICS_BYTES):
        raise InputError("unsafe offline BLS calendar input")
    raw=file.read_bytes()
    events=bls.parse_calendar(raw,asof_utc=asof_utc,
                              days_forward=days_forward)
    try:
        captured=datetime.fromisoformat(
            asof_utc.replace("Z","+00:00"))
    except (ValueError,AttributeError) as exc:
        raise InputError("bad calendar capture time") from exc
    if captured.tzinfo is None or captured.utcoffset().total_seconds()!=0:
        raise InputError("UTC BLS capture timestamp required")
    seen=set()
    chosen=[]
    for source in events["events"]:
        title=source["title"].strip().lower()
        importance=next((importance for prefix,importance in IMPORTANT_PREFIXES
                         if title.startswith(prefix)),None)
        if importance is None:
            continue
        stamp=source["scheduled_at_utc"]
        identity=hashlib.sha256((title+"|"+stamp).encode()).hexdigest()[:24]
        if identity in seen:
            raise InputError("duplicate matched BLS release")
        seen.add(identity)
        chosen.append({
            "id":"BLS_"+identity,
            "currency":"USD",
            "scheduled_at_utc":stamp,
            "source_url":bls.URL,
            "importance":importance,
        })
    if len(chosen)>100:
        raise InputError("too many selected BLS events")
    candidate={
        "schema":guard.SCHEMA,
        "captured_at_utc_pc":asof_utc,
        "scope":"OPERATOR_SAVED_RESEARCH_ONLY",
        "events":chosen,
    }
    # Deliberately no false authenticity or three-currency coverage flag.
    return {
        "known_event_calendar":candidate,
        "source_bls_ics_sha256_local_only":hashlib.sha256(raw).hexdigest(),
        "bls_raw_schedule_event_count":events["event_count"],
        "selected_important_us_event_count":len(chosen),
        "eur_jpy_events_included":False,
        "calendar_coverage_independently_attested":False,
        "pre_release_consensus_attested":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(
        description="No-network BLS ICS to local USD known blackout candidate")
    p.add_argument("--ics-file",type=Path,required=True)
    p.add_argument("--asof-utc",required=True)
    p.add_argument("--days-forward",type=int,default=14)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=convert(args.ics_file,asof_utc=args.asof_utc,
                       days_forward=args.days_forward)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("unsafe BLS candidate output")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(result["known_event_calendar"],f,ensure_ascii=False,
                      indent=2,allow_nan=False)
        print(json.dumps({k:v for k,v in result.items()
                          if k!="known_event_calendar"},ensure_ascii=False))
        return 0
    except (InputError,OSError,ValueError,TypeError,UnicodeError,
            OverflowError):
        print(json.dumps({
            "status":"BLS_OFFLINE_KNOWN_EVENT_ARCHIVE_FAIL_CLOSED_NO_GO",
            "eur_jpy_events_included":False,
            "calendar_coverage_independently_attested":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
