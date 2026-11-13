"""FWD-1361+: one-command NO-ORDER pilot for existing single Rakuten MT4 DEMO.

PREPARE checks the repository's fixed 30-cycle observer source and generates
a human-controlled installation/compile/operation checklist. AUDIT consumes
only manually COPIED session folders (or an explicit existing evidence plan)
and invokes the full offline runbook. This module NEVER touches the MT4 data
directory, copies an EA into MT4, starts a program, runs a job, connects to
the broker or permits even a DEMO order. A test passing is not operator
approval, MT4 compilation evidence or live runtime safety certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from research import forward_evidence_runbook as runbook
from research import forward_mt4_timer_observer_review as observer
from research import forward_mt4_multisession_reliability as multi
from research import forward_fullstack_noorder_hub as hub
from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_single_terminal_readonly_pilot_v1"
SOURCE = Path(__file__).parent / "mt4_readonly" / "FxForwardDemoTimerObserver.mq4"
MAX_SOURCE_BYTES = 60_000
MAX_REPORT_BYTES = 2_000_000
MANUAL_GATES = (
    "EXISTING_SINGLE_RAKUTEN_MT4_TERMINAL_ONLY",
    "DEMO_ACCOUNT_AND_SERVER_IDENTITY_OPERATOR_VERIFIED",
    "NO_OPEN_OR_PENDING_ORDERS_OPERATOR_VERIFIED",
    "AUTOTRADING_OFF_AND_DLL_EXTERNAL_IMPORTS_OFF_OPERATOR_VERIFIED",
    "EXISTING_EA_CONFLICTS_OPERATOR_VERIFIED",
    "OBSERVER_SOURCE_HASH_REVIEWED_AND_METAEDITOR_COMPILED_0_ERRORS",
    "READ_ONLY_EA_MANUALLY_ATTACHED_TO_ONE_USDJPY_CHART_ONLY",
    "OBSERVE_FIRST_TIMER_CYCLES_AND_MANUALLY_REMOVE_EA",
    "COPY_THREE_PAIR_CSV_AND_LOGS_OUTSIDE_MT4_FOR_OFFLINE_AUDIT",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_report() -> dict:
    if (SOURCE.is_symlink() or not SOURCE.is_file()
            or not 0 < SOURCE.stat().st_size <= MAX_SOURCE_BYTES):
        raise InputError("fixed 30-cycle MT4 observer source absent or unsafe")
    raw = SOURCE.read_bytes()
    static = observer.inspect(raw)
    if (static.get("status") != "DEMO_TIMER_OBSERVER_STATIC_RESEARCH_NO_GO"
            or static.get("static_preflight_passed") is not True
            or static.get("timer_seconds_declared") != 60
            or static.get("maximum_timer_cycles_declared") != 30
            or static.get("runtime_go_no_go") != "NO_GO"
            or static.get("safety_hold_latched") is not True
            or static.get("real_orders_permitted") is not False
            or static.get("demo_trading_allowed") is not False):
        raise InputError("observer source does not pass static no-order gate")
    return static


def _plan(*, plan_file: Path | None, session_values: list[str],
          mode: str) -> tuple[dict | None, str | None, list[Path]]:
    if plan_file is not None and session_values:
        raise InputError("choose --plan-file OR explicit --session entries")
    if mode == "prepare":
        if plan_file is not None or session_values:
            raise InputError("prepare only reviews fixed observer; no input sessions")
        return None, None, []
    if plan_file is not None:
        decoded, digest = runbook.read_plan(plan_file)
        if not decoded["sessions"]:
            raise InputError("audit plan contains no copied MT4 sessions")
        return decoded, digest, [plan_file, *decoded["evidence_paths"]]
    labels = multi._parse_labeled_entries(session_values, "--session")
    if not labels:
        raise InputError("audit requires at least one manually copied session")
    doc = runbook.empty_plan()
    doc["sessions"] = [{
        "label": label, "directory": str(folder.absolute()),
        "experts_log": None, "compile_log": None,
    } for label, folder in labels.items()]
    serialized = json.dumps(doc, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":")).encode("utf-8")
    # In-memory only. This path is NEVER opened or written.
    virtual_path = Path.cwd() / ".fx_fwd_nonexistent_pilot_plan.json"
    decoded = runbook.decode(doc, plan_file=virtual_path)
    return decoded, hashlib.sha256(serialized).hexdigest(), decoded["evidence_paths"]


def inspect(*, mode: str, asof_utc: str, plan_file: Path | None = None,
            sessions: list[str] | None = None) -> tuple[dict, dict | None, list[Path]]:
    if mode not in ("prepare", "audit"):
        raise InputError("unsupported no-order pilot mode")
    macro._utc(asof_utc)
    static = _source_report()
    plan, plan_sha, source_paths = _plan(
        plan_file=plan_file,
        session_values=[] if sessions is None else sessions,
        mode=mode)
    audited = None
    if mode == "audit":
        audited = runbook.inspect(plan, asof_utc=asof_utc,
                                  plan_sha256=plan_sha)
        if (audited.get("status") != "RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO"
                or audited.get("runtime_go_no_go") != "NO_GO"
                or audited.get("safety_hold_latched") is not True
                or audited.get("real_orders_permitted") is not False
                or audited.get("demo_orders_permitted") is not False
                or audited.get("orders_sent_this_run") != 0):
            raise InputError("integrated copied-session audit failed safety")
        full = audited["fullstack_report"]
        if (full.get("mt4_copied_observation_session_count", 0) < 1
                or full.get("runtime_go_no_go") != "NO_GO"
                or full.get("safety_hold_latched") is not True):
            raise InputError("no verifiable copied-session structure")
    else:
        full = None
    preview = (full["unresolved_holds"][:30] if full is not None else [])
    actions = (audited["priority_research_tasks_advisory_only"] if audited
               is not None else [])
    result = {
        "schema": SCHEMA,
        "status": (
            "MT4_READONLY_PILOT_PREPARATION_NEEDS_OPERATOR_ACTION_NO_GO"
            if mode == "prepare" else
            "MT4_COPIED_FORWARD_OBSERVATIONS_AUDITED_HOLD_NO_GO"),
        "asof_utc_local_or_supplied_clock_unattested": asof_utc,
        "pilot_mode": mode,
        "observer_source_repo_relative":
            "research/mt4_readonly/FxForwardDemoTimerObserver.mq4",
        "observer_source_sha256_local_integrity_only":
            static["source_sha256"],
        "observer_static_preflight_passed": True,
        "observer_timer_interval_seconds_declared": 60,
        "observer_maximum_timer_cycles_declared": 30,
        "observer_metaeditor_compile_verified": False,
        "observer_ea_executed_by_this_program": False,
        "mt4_data_folder_accessed_by_this_program": False,
        "operator_manual_gate_statuses": [
            {"gate": gate, "verified_by_this_program": False}
            for gate in MANUAL_GATES
        ],
        "copied_mt4_session_count":
            full["mt4_copied_observation_session_count"] if full else 0,
        "copied_quote_csv_count": full["price_csv_count"] if full else 0,
        "complete_observation_cycle_count":
            full["mt4_complete_observation_cycles"] if full else 0,
        "distinct_ny17_observation_bucket_count":
            full["mt4_observed_ny17_time_bucket_count"] if full else 0,
        "pending_holds_preview": preview,
        "pending_holds_omitted_count": (
            max(0, len(full["unresolved_holds"]) - len(preview))
            if full else 0),
        "prioritized_research_actions_advisory_only": actions,
        "runbook_report_sha256_local_only": (
            hashlib.sha256(json.dumps(
                audited, sort_keys=True, ensure_ascii=False,
                separators=(",", ":"), allow_nan=False
            ).encode("utf-8")).hexdigest() if audited else None),
        "runbook_executed_without_external_services": audited is not None,
        "operator_authorization_or_real_broker_safety_proven": False,
        "demo_forward_orders_authorized": False,
        "real_forward_orders_authorized": False,
        "research_observation_is_real_mt4_attestation": False,
        "no_go_cannot_be_cleared_by_report": True,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }
    return result, audited, source_paths


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Prepare or audit manual DEMO MT4 read-only forward pilot")
    p.add_argument("--mode", choices=("prepare", "audit"), required=True)
    p.add_argument("--asof-utc", default=None)
    p.add_argument("--plan-file", type=Path)
    p.add_argument("--session", action="append", default=[],
                   help="LABEL=COPIED_CSV_FOLDER; repeat per manual session")
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    try:
        asof = args.asof_utc or _now()
        result, audited, evidence = inspect(
            mode=args.mode, asof_utc=asof,
            plan_file=args.plan_file, sessions=args.session)
        if args.out is not None:
            hub._checked_new_output(
                args.out, [SOURCE, args.plan_file, *evidence])
            payload = {
                "schema": SCHEMA,
                "pilot_summary": result,
                "runbook_report_if_audited": audited,
            }
            raw = json.dumps(payload, ensure_ascii=False, indent=2,
                             allow_nan=False).encode("utf-8")
            if len(raw) > MAX_REPORT_BYTES:
                raise InputError("pilot report too large")
            with args.out.open("xb") as out:
                out.write(raw)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "MT4_READONLY_PILOT_FAIL_CLOSED_NO_GO",
            "reason_code": "MISSING_OR_INCONSISTENT_LOCAL_SAFETY_EVIDENCE",
            "network_calls_this_run": 0,
            "API_calls_this_run": 0,
            "orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
