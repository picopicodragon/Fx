"""FWD-801..848: independent evidence debt vs. synthetic fault-test results.

This matrix cannot be translated into GO. Its purpose is to tell reviewers
what was tested off-line, which local research inputs exist, and what remains
UNVERIFIED at actual MT4/broker runtime. No orders, APIs or external I/O.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research.offline_backtest import InputError

SCHEMA = "fx_fwd_operational_acceptance_debt_v1"
HUB_SCHEMA = "fx_fwd_fullstack_noorder_evidence_hub_v1"
SIM_SCHEMA = "fx_fwd_synthetic_safety_fault_campaign_v1"

DOMAINS = (
    ("global_release_calendar", "OFFICIAL_MULTI_REGION_POINT_IN_TIME_SCHEDULE_AND_INDEPENDENT_CLOCK"),
    ("pre_release_consensus", "SOURCE_ATTESTED_PRE_BLACKOUT_ESTIMATES_FOR_ALL_RELEVANT_EVENTS"),
    ("three_pair_market_quotes", "TIMESTAMPED_BID_ASK_AND_CONVERSION_FROM_REAL_DEMO_SERVER"),
    ("mt4_demo_identity", "ONE_BROKER_ACCOUNT_AND_TERMINAL_ACCOUNT_IDENTITY_INDEPENDENTLY_ATTESTED"),
    ("bidirectional_watchdog", "LIVE_HEARTBEATS_60S_LEVEL1_600S_LEVEL2_AND_FAIL_CLOSED_STOPS"),
    ("risk_limits_equity", "0_5_PERCENT_PER_TRADE_1_PERCENT_TOTAL_1_5_PERCENT_DAILY_NY17"),
    ("drawdown_approval_latches", "2_3_4_5_PERCENT_THRESHOLDS_4_5_REQUIRE_HUMAN_CLEARANCE"),
    ("macro_blackout_recovery", "REAL_15MIN_BEFORE_AFTER_RELEASE_STOP_AND_SAFE_REASSESSMENT"),
    ("mobile_email_alerting", "PUSH_AND_EMAIL_CRITICAL_ALERT_DELIVERY_CONFIRMED"),
    ("human_production_approval", "EXPLICIT_OWNER_REVIEW_AND_ENVIRONMENT_SPECIFIC_AUTHORIZATION"),
)


def _valid_hub(data: object) -> dict:
    if (type(data) is not dict
            or data.get("schema") != HUB_SCHEMA
            or data.get("status") != "FULLSTACK_FORWARD_RESEARCH_READINESS_HOLD_NO_GO"
            or data.get("runtime_go_no_go") != "NO_GO"
            or data.get("real_orders_permitted") is not False
            or data.get("demo_orders_permitted") is not False
            or data.get("safety_hold_latched") is not True):
        raise InputError("untrusted fullstack evidence report")
    keys = (
        "bls_snapshot_verified",
        "official_news_bundle_verified",
        "bls_html_ics_event_count_disagrees",
        "external_macro_event_observations",
        "archived_consensus_records",
        "mt4_copied_observation_session_count",
        "mt4_complete_observation_cycles",
        "research_blackout_pair_window_count",
        "research_blackout_copied_quote_overlap_windows",
        "price_csv_count",
    )
    for key in keys:
        if key not in data:
            raise InputError("fullstack audit missing field " + key)
    for key in ("bls_snapshot_verified", "official_news_bundle_verified"):
        if type(data[key]) is not bool:
            raise InputError("invalid local verification flag")
    for key in keys[3:]:
        if type(data[key]) is not int or data[key] < 0:
            raise InputError("invalid evidence volume")
    if (data.get("bls_html_ics_event_count_disagrees") is not None
            and type(data["bls_html_ics_event_count_disagrees"]) is not bool):
        raise InputError("invalid BLS disagreement tri-state")
    return data


def _valid_drills(data: object) -> dict:
    if (type(data) is not dict or data.get("schema") != SIM_SCHEMA
            or data.get("status") != "SYNTHETIC_SAFETY_FAULT_CAMPAIGN_HOLD_NO_GO"
            or data.get("runtime_go_no_go") != "NO_GO"
            or data.get("real_orders_permitted") is not False
            or data.get("demo_orders_permitted") is not False
            or data.get("safety_hold_latched") is not True
            or data.get("synthetic_green_is_operational_acceptance") is not False
            or data.get("real_source_events_or_broker_evidence_used") is not False
            or type(data.get("synthetic_scenario_count")) is not int
            or data["synthetic_scenario_count"] < 25
            or type(data.get("synthetic_passed_count")) is not int
            or data["synthetic_passed_count"] != data["synthetic_scenario_count"]
            or type(data.get("synthetic_failed_count")) is not int
            or data["synthetic_failed_count"] != 0):
        raise InputError("untrusted synthetic safety drill report")
    cases = data.get("synthetic_scenarios")
    digest = data.get("synthetic_cases_sha256")
    if (type(cases) is not list
            or len(cases) != data["synthetic_scenario_count"]
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or any(type(x) is not dict
                   or set(x) != {"case", "synthetic_contract_passed"}
                   or type(x["case"]) is not str
                   or not 1 <= len(x["case"]) <= 120
                   or x["synthetic_contract_passed"] is not True
                   for x in cases)):
        raise InputError("invalid synthetic scenario registry")
    names = [x["case"] for x in cases]
    if len(names) != len(set(names)):
        raise InputError("repeated scenario identity")
    payload = json.dumps(
        cases, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")
    if hashlib.sha256(payload).hexdigest() != digest:
        raise InputError("synthetic case register checksum mismatch")
    return data


def inspect(fullstack: dict, synthetic: dict) -> dict:
    hub = _valid_hub(fullstack)
    drill = _valid_drills(synthetic)
    observed = {
        "global_release_calendar":
            int(hub["bls_snapshot_verified"])
            + hub["external_macro_event_observations"],
        "pre_release_consensus": hub["archived_consensus_records"],
        "three_pair_market_quotes": hub["price_csv_count"],
        "mt4_demo_identity": hub["mt4_copied_observation_session_count"],
        "bidirectional_watchdog": 0,
        "risk_limits_equity": 0,
        "drawdown_approval_latches": 0,
        "macro_blackout_recovery": hub["research_blackout_copied_quote_overlap_windows"],
        "mobile_email_alerting": 0,
        "human_production_approval": 0,
    }
    checklist = []
    for domain, requirement in DOMAINS:
        checklist.append({
            "domain": domain,
            "required_independent_evidence": requirement,
            "local_research_evidence_item_count_unverified": observed[domain],
            "synthetic_contract_tests_covered_some_rules":
                domain in {"bidirectional_watchdog", "risk_limits_equity",
                           "drawdown_approval_latches", "macro_blackout_recovery"},
            "broker_runtime_or_source_truth_independently_verified": False,
            "acceptance_status": "BLOCKED_AWAITING_INDEPENDENT_EVIDENCE",
            "does_not_authorize_orders": True,
        })
    if len(checklist) != len(DOMAINS):
        raise InputError("acceptance debt domains incomplete")
    return {
        "schema": SCHEMA,
        "status": "OPERATIONAL_ACCEPTANCE_DEBT_RESEARCH_HOLD_NO_GO",
        "domain_count": len(checklist),
        "domain_count_independently_verified": 0,
        "source_evidence_only_not_broker_attested": True,
        "synthetic_safety_scenario_count": drill["synthetic_scenario_count"],
        "synthetic_safety_cases_sha256_unattested": drill["synthetic_cases_sha256"],
        "bls_html_ics_disagreement_unresolved_or_unknown":
            hub["bls_html_ics_event_count_disagrees"] is not False,
        "official_news_cannot_replace_forward_calendar": True,
        "review_dimensions": checklist,
        "programmatic_go_or_approval_logic_implemented": False,
        "owner_signoff_supplied_or_inferred": False,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read two explicit NO_GO research reports; no operational sign-off")
    parser.add_argument("--fullstack-report", type=Path, required=True)
    parser.add_argument("--synthetic-drill-report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        files = (args.fullstack_report, args.synthetic_drill_report)
        values = []
        for path in files:
            if (not path.is_file() or path.is_symlink()
                    or not 0 < path.stat().st_size <= 500000):
                raise InputError("unsafe or missing input report")
            values.append(json.loads(path.read_text(encoding="utf-8-sig")))
        result = inspect(*values)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, ValueError, TypeError, KeyError,
            UnicodeError, OSError, ArithmeticError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "OPERATIONAL_ACCEPTANCE_DEBT_FAIL_CLOSED_NO_GO",
            "network_calls_this_run": 0, "API_calls_this_run": 0,
            "actual_orders_sent": 0,
            "demo_orders_permitted": False, "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
