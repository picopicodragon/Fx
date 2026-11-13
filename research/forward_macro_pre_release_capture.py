"""FWD-213..222: write-once, clock-stamped pre-release consensus evidence.

Accepts ONLY explicit locally supplied consensus excerpts and an existing
official-calendar observation report. The system capture time is taken from
UTC *now* during CLI execution: no CLI backdating. Local hashing verifies
integrity, NOT source truth or publisher/clock authenticity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_macro_event_windows as windows
from research.forward_macro_consensus_surprise import _number
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_pre_release_consensus_capture_v1"
FORM = "fx_fwd_pre_release_consensus_submission_v1"
FIELDS = frozenset(("schema", "event_title", "scheduled_at_utc",
                    "pair", "value", "unit", "source_text",
                    "source_sha256", "source_url",
                    "source_published_at_utc"))
ALLOWED_UNITS = frozenset(("percent", "percentage_points", "index",
                           "persons", "thousands", "millions",
                           "basis_points", "other"))
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_FORM_BYTES = 6000
MAX_CALENDAR_BYTES = 160000


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def _url(value: object) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 1000
            or any(x.isspace() for x in value)):
        raise InputError("unsafe forecast citation URL")
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname
                or not parts.netloc.isascii() or parts.port
                or parts.username or parts.password
                or parts.fragment or len(parts.hostname) > 200
                or parts.path.startswith("//")):
            raise InputError("unsafe forecast source")
    except ValueError as exc:
        raise InputError("invalid forecast source") from exc
    return value


def validate_submission(form: object, calendar: dict, *,
                        captured_at_utc: str) -> dict:
    captured = timestamp(captured_at_utc)
    if (type(form) is not dict or set(form) != FIELDS
            or form["schema"] != FORM
            or type(form["pair"]) is not str or form["pair"] not in PAIRS
            or type(form["unit"]) is not str
            or form["unit"] not in ALLOWED_UNITS
            or type(form["event_title"]) is not str
            or not 1 <= len(form["event_title"]) <= 250
            or not form["event_title"].strip()):
        raise InputError("invalid consensus submission")
    _number(form["value"])
    t = timestamp(form["scheduled_at_utc"])
    source_at = timestamp(form["source_published_at_utc"])
    if not source_at <= captured < t:
        raise InputError("forecast not captured before release")
    txt = form["source_text"]
    if (type(txt) is not str or not 1 <= len(txt) <= 2000
            or "\x00" in txt):
        raise InputError("invalid consensus excerpt")
    fingerprint = form["source_sha256"]
    if (type(fingerprint) is not str or not SHA.fullmatch(fingerprint)
            or hashlib.sha256(txt.encode("utf-8")).hexdigest() != fingerprint):
        raise InputError("forecast text checksum mismatch")
    _url(form["source_url"])
    # Prevent writing an apparently valid forecast against a report that is
    # stale, incomplete, forged in status or does not list this exact event.
    plan = windows.inspect(calendar, asof_utc=captured_at_utc)
    if plan["calendar_stale"]:
        raise InputError("BLS schedule is stale for consensus capture")
    matches = [e for e in plan["windows"] if
               e["title_unverified"] == form["event_title"] and
               e["scheduled_at_utc_unverified"] == form["scheduled_at_utc"]]
    if len(matches) != 1:
        raise InputError("forecast references unknown/ambiguous BLS event")
    if matches[0]["research_state"] != "BEFORE_RESEARCH_BLACKOUT":
        raise InputError("forecast too close to or after event")
    return {
        "schema": SCHEMA,
        "status": "PRE_RELEASE_CONSENSUS_CAPTURED_RESEARCH_NO_GO",
        "recorded_at_utc_local_clock_unattested": captured_at_utc,
        "event_title_unverified": form["event_title"],
        "scheduled_at_utc_unverified": form["scheduled_at_utc"],
        "pair": form["pair"],
        "forecast_value_self_reported": str(_number(form["value"])),
        "unit": form["unit"],
        "source_url_unverified": form["source_url"],
        "source_text_excerpt": txt,
        "source_text_sha256": fingerprint,
        "source_published_at_utc_self_reported": form[
            "source_published_at_utc"],
        "calendar_report_sha256_self_reported":
            calendar["calendar_sha256"],
        "source_truth_authenticated": False,
        "published_at_independently_attested": False,
        "forecast_poll_or_web_search_performed": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def verify_archive(report: object, *, asof_utc: str) -> dict:
    timestamp(asof_utc)
    if (type(report) is not dict
            or set(report) != {"record", "record_sha256"}
            or type(report["record"]) is not dict
            or type(report["record_sha256"]) is not str
            or not SHA.fullmatch(report["record_sha256"])
            or sha(report["record"]) != report["record_sha256"]):
        raise InputError("corrupt forecast archive")
    data = report["record"]
    if (data.get("schema") != SCHEMA or
            data.get("status") != "PRE_RELEASE_CONSENSUS_CAPTURED_RESEARCH_NO_GO"
            or data.get("runtime_go_no_go") != "NO_GO"
            or data.get("real_orders_permitted") is not False
            or data.get("demo_orders_permitted") is not False
            or data.get("safety_hold_latched") is not True
            or data.get("source_truth_authenticated") is not False
            or data.get("published_at_independently_attested") is not False
            or data.get("forecast_poll_or_web_search_performed") is not False):
        raise InputError("untrusted forecast archive scope")
    source = data["source_text_excerpt"]
    if (type(source) is not str or
            hashlib.sha256(source.encode("utf-8")).hexdigest()
            != data["source_text_sha256"]):
        raise InputError("forecast excerpt modified")
    captured = timestamp(data["recorded_at_utc_local_clock_unattested"])
    published = timestamp(data["source_published_at_utc_self_reported"])
    scheduled = timestamp(data["scheduled_at_utc_unverified"])
    # Archive replay must enforce the same strict 15-minute blackout
    # boundary as validate_submission. Re-hashing a modified record cannot
    # turn a late forecast into admissible point-in-time evidence.
    if (not published <= captured < scheduled - timedelta(minutes=15)
            or captured > timestamp(asof_utc)):
        raise InputError("invalid archive timing or forecast blackout")
    if data["pair"] not in PAIRS or data["unit"] not in ALLOWED_UNITS:
        raise InputError("invalid archive pair/unit")
    _number(data["forecast_value_self_reported"])
    _url(data["source_url_unverified"])
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Write-once pre-release forecast")
    parser.add_argument("--calendar-report", required=True, type=Path)
    parser.add_argument("--forecast", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    a = parser.parse_args(argv)
    try:
        if (a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()
                or any(not p.is_file() or p.is_symlink()
                       or not 0 < p.stat().st_size <= cap
                       for p, cap in (
                           (a.forecast, MAX_FORM_BYTES),
                           (a.calendar_report, MAX_CALENDAR_BYTES)))):
            raise InputError("unsafe write-once forecast source")
        calendar = json.loads(a.calendar_report.read_text("utf-8-sig"))
        form = json.loads(a.forecast.read_text("utf-8-sig"))
        captured = datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        record = validate_submission(
            form, calendar, captured_at_utc=captured)
        payload = {"record": record, "record_sha256": sha(record)}
        # Do not rewrite an earlier snapshot even if a newer forecast differs.
        with a.out.open("x", encoding="utf-8") as dest:
            json.dump(payload, dest, ensure_ascii=False, indent=2)
            dest.flush()
        print(json.dumps({
            "status": record["status"],
            "record_sha256": payload["record_sha256"],
            "recorded_at_utc": captured,
            "source_truth_authenticated": False,
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError,
            TypeError, KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "PRE_RELEASE_CONSENSUS_NOT_ESTABLISHED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
