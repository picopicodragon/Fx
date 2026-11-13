"""FWD-673..700: descriptive comparison of two offline NO_GO evidence reports.

A changed local report is NOT an independently verified improvement. In
particular disappearance of a hold cannot authorize trading or imply that
its original defect was corrected. Refuse untrusted GO and reversed clocks.
"""
from __future__ import annotations

from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_research_readiness_delta_v1"
PREVIOUS_SCHEMA = "fx_fwd_evidence_runbook_readiness_v1"
HUB_SCHEMA = "fx_fwd_fullstack_noorder_evidence_hub_v1"
MAX_HOLDS = 1024
MAX_TASKS = 256
METRICS = (
    "official_news_item_count",
    "external_macro_event_observations",
    "external_macro_missing_consensus_count",
    "archived_consensus_records",
    "archived_consensus_matching_bls_events",
    "archived_consensus_unmatched",
    "bls_events_without_archived_consensus",
    "mt4_copied_observation_session_count",
    "mt4_observed_ny17_time_bucket_count",
    "mt4_complete_observation_cycles",
    "research_blackout_pair_window_count",
    "research_blackout_copied_quote_overlap_windows",
    "price_csv_count",
    "price_ai_macro_observation_count",
    "price_ai_independent_review_count",
)


def _safe(data: object, *, previous: bool) -> dict:
    if type(data) is not dict:
        raise InputError("invalid research report root")
    if previous:
        if (data.get("schema") != PREVIOUS_SCHEMA
                or data.get("status")
                != "RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO"):
            raise InputError("previous report must be exact runbook output")
        for name, expected in (("runtime_go_no_go", "NO_GO"),
                               ("real_orders_permitted", False),
                               ("demo_orders_permitted", False),
                               ("safety_hold_latched", True)):
            if ((type(expected) is bool and data.get(name) is not expected)
                    or (type(expected) is str and data.get(name) != expected)):
                raise InputError("previous runbook safety flags untrusted")
        data = data.get("fullstack_report")
    if (type(data) is not dict
            or data.get("schema") != HUB_SCHEMA
            or data.get("status")
            != "FULLSTACK_FORWARD_RESEARCH_READINESS_HOLD_NO_GO"):
        raise InputError("invalid fullstack report status")
    for key, expected in (("runtime_go_no_go", "NO_GO"),
                          ("safety_hold_latched", True),
                          ("demo_orders_permitted", False),
                          ("real_orders_permitted", False)):
        if ((type(expected) is bool and data.get(key) is not expected)
                or (type(expected) is str and data.get(key) != expected)):
            raise InputError("reported trading safety not NO_GO")
    holds = data.get("unresolved_holds")
    tasks = data.get("next_research_actions")
    if (type(holds) is not list or len(holds) > MAX_HOLDS
            or any(type(h) is not str or not 1 <= len(h) <= 200
                   for h in holds)
            or len(holds) != len(set(holds))
            or type(tasks) is not list or len(tasks) > MAX_TASKS
            or any(type(a) is not str or not 1 <= len(a) <= 200
                   for a in tasks)):
        raise InputError("unsafe research hold/task format")
    for key in METRICS:
        v = data.get(key)
        if type(v) is not int or v < 0 or v > 10_000_000:
            raise InputError("invalid comparison metrics")
    macro._utc(data["asof_utc_local_or_supplied_unattested"])
    return data


def compare(previous_report: object, current_report: object) -> dict:
    earlier = _safe(previous_report, previous=True)
    newer = _safe(current_report, previous=False)
    earlier_at = macro._utc(earlier["asof_utc_local_or_supplied_unattested"])
    current_at = macro._utc(newer["asof_utc_local_or_supplied_unattested"])
    if earlier_at > current_at:
        raise InputError("previous local observation after current report")
    oldholds = set(earlier["unresolved_holds"])
    newholds = set(newer["unresolved_holds"])
    diffs = {
        name: {
            "previous": earlier[name],
            "current": newer[name],
            "descriptive_change": newer[name] - earlier[name],
            "improvement_in_safety_claimed": False,
        }
        for name in METRICS if earlier[name] != newer[name]
    }
    return {
        "schema": SCHEMA,
        "status": "RESEARCH_REPORT_DESCRIPTIVE_DELTA_HOLD_NO_GO",
        "previous_asof_utc_self_reported":
            earlier["asof_utc_local_or_supplied_unattested"],
        "current_asof_utc_self_reported":
            newer["asof_utc_local_or_supplied_unattested"],
        "same_local_clock_second": earlier_at == current_at,
        "previous_hold_count": len(oldholds),
        "current_hold_count": len(newholds),
        "newly_reported_holds": sorted(newholds - oldholds),
        "previously_reported_holds_not_in_current_unverified":
            sorted(oldholds - newholds),
        "numeric_metric_changes_unattested": diffs,
        "changed_source_inputs_not_independently_authenticated": True,
        "holding_reason_disappearance_is_not_safety_clearance": True,
        "human_or_runtime_reauthorization_permitted": False,
        "API_calls_this_run": 0,
        "network_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }
