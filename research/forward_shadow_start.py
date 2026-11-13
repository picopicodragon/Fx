"""FWD-1401: begin an immutable NO-ORDER shadow-forward evidence campaign.

Start once with existing manually copied MT4 3-pair CSV sessions, then append
new explicitly chosen sessions with --mode step. --mode refresh integrates
newly observed real macro/AI journal evidence without falsely requiring a
second price observation, while rechecking all prior copied CSV originals. All old source bytes are
rechecked at every step. A missing real macro/consensus/reviewer event is a
deterministic RESEARCH HOLD, NEVER a fabricated AI signal or simulated fill.
This application performs no API calls, web fetch, scheduling, MT4 access,
live quote polling, network, automatic reconciliation, or orders.

The log contains locally hashed, write-once records. This is not digital
attestation of a market source or secure storage against hostile tampering.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from research import forward_demo_pilot as pilot
from research import forward_mt4_multisession_reliability as sessions_audit
from research import forward_macro_evidence_readiness as macro_readiness
from research import forward_macro_reviewed_outcomes as marks
from research import forward_evidence_runbook as runbook
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_noorder_shadow_forward_campaign_v1"
RECORD = "fx_fwd_noorder_shadow_forward_record_v1"
PAIR_SCOPE = ("USD/JPY", "EUR/JPY", "EUR/USD")
CSV_PATTERN = re.compile(r"^FxFwdV3_(USDJPY|EURJPY|EURUSD)_[0-9]{8}_[0-9]{6}\.csv$")
LOG_PATTERN = re.compile(r"^[0-9]{8}\.json$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_RECORDS = 120
MAX_FILE_BYTES = 1200
MAX_REPORT_BYTES = 180_000
MAX_AGE_HOURS = 24
HARD_VETOES = frozenset(marks.STRUCTURAL_VETO | {
    "SERVER_CLOCK_STALLED", "SERVER_AND_CLIENT_CLOCK_RATE_DIVERGED",
    "SERVER_TICK_TIME_REGRESSED", "REPLAYED_TIMESTAMP",
})
ACTUAL_MODEL_CALLS = 0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_file(path: Path, maximum: int) -> bytes:
    if (not isinstance(path, Path) or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
            or not path.is_file() or not 0 < path.stat().st_size <= maximum):
        raise InputError("missing/unsafe/oversized immutable source")
    content = path.read_bytes()
    if not 0 < len(content) <= maximum:
        raise InputError("evidence changed while inspecting")
    return content


def _safe_state_dir(folder: Path, *, new: bool) -> None:
    if not isinstance(folder, Path) or folder.is_symlink() or any(
            parent.is_symlink() for parent in folder.parents):
        raise InputError("unsafe shadow state directory")
    if new:
        if folder.exists() or not folder.parent.is_dir():
            raise InputError("shadow state folder must be new in an existing parent")
    elif not folder.is_dir():
        raise InputError("missing shadow campaign state folder")


def _checked_entries(directory: Path) -> list[Path]:
    names = list(directory.iterdir())
    if (len(names) > MAX_RECORDS or any(
            x.is_symlink() or not x.is_file()
            or LOG_PATTERN.fullmatch(x.name) is None for x in names)):
        raise InputError("shadow campaign directory has unexpected files")
    return sorted(names)


def _load(folder: Path) -> list[dict]:
    _safe_state_dir(folder, new=False)
    files = _checked_entries(folder)
    if not files or len(files) > MAX_RECORDS:
        raise InputError("empty or oversized shadow campaign")
    rows = []
    previous = None
    for index, file in enumerate(files, start=1):
        if file.name != f"{index:08d}.json":
            raise InputError("shadow campaign records not contiguous")
        raw = _safe_file(file, MAX_REPORT_BYTES)
        obj = json.loads(raw.decode("utf-8-sig"))
        if (type(obj) is not dict
                or set(obj) != {"schema", "sequence", "prev_record_sha256",
                               "record", "record_sha256"}
                or obj["schema"] != RECORD
                or type(obj["sequence"]) is not int
                or obj["sequence"] != index
                or obj["prev_record_sha256"] != previous
                or type(obj["record"]) is not dict
                or not isinstance(obj["record_sha256"], str)
                or SHA.fullmatch(obj["record_sha256"]) is None
                or obj["record_sha256"] != _sha(_canonical({
                    k: obj[k] for k in (
                        "schema", "sequence", "prev_record_sha256", "record")
                }))):
            raise InputError("modified local shadow campaign record")
        state = obj["record"]
        if (state.get("schema") != SCHEMA
                or state.get("runtime_go_no_go") != "NO_GO"
                or state.get("safety_hold_latched") is not True
                or state.get("demo_orders_permitted") is not False
                or state.get("real_orders_permitted") is not False
                or state.get("orders_sent_this_run") != 0
                or state.get("API_calls_this_run") != 0
                or type(state.get("sessions")) is not list):
            raise InputError("shadow record safety scope invalid")
        if rows:
            old = rows[-1]["record"]
            length = len(state["sessions"])
            if state.get("mode") == "step":
                if length <= len(old["sessions"]):
                    raise InputError("step did not add a new copied CSV session")
                if state["sessions"][:len(old["sessions"])] != old["sessions"]:
                    raise InputError("step changed previously recorded sessions")
            elif state.get("mode") == "refresh":
                if state["sessions"] != old["sessions"]:
                    raise InputError("macro refresh changed price evidence")
                prev_events = old["reviewed_macro_event_count_in_supplied_journal"]
                prev_reviews = old["independent_review_count_in_supplied_journal"]
                events = state["reviewed_macro_event_count_in_supplied_journal"]
                reviews = state["independent_review_count_in_supplied_journal"]
                if (type(events) is not int or type(reviews) is not int
                        or events < prev_events or reviews < prev_reviews
                        or (events == prev_events and reviews == prev_reviews)):
                    raise InputError("macro refresh lacks monotonic new evidence")
            else:
                raise InputError("illegal shadow campaign transition")
        elif state.get("mode") != "start":
            raise InputError("shadow campaign must begin with start")
        previous = obj["record_sha256"]
        rows.append(obj)
    return rows


def _session_manifest(directory: Path) -> dict:
    if (not isinstance(directory, Path) or directory.is_symlink()
            or any(parent.is_symlink() for parent in directory.parents)
            or not directory.is_dir()):
        raise InputError("unsafe copied MT4 CSV directory")
    paths = sorted(directory.iterdir())
    if (not paths or len(paths) > 200 or any(
            p.is_symlink() or not p.is_file()
            or CSV_PATTERN.fullmatch(p.name) is None for p in paths)):
        raise InputError("unexpected items in copied session folder")
    members = [
        {"filename": p.name, "sha256": _sha(_safe_file(p, MAX_FILE_BYTES))}
        for p in paths
    ]
    return {
        "source_manifest_sha256_local_only": _sha(_canonical({
            "members": members
        })),
        "file_count": len(members),
    }


def _entries_from_previous(previous: dict | None) -> list[tuple[str, Path]]:
    return [
        (row["label"], Path(row["directory"]))
        for row in previous["sessions"]
    ] if previous else []


def _choose_sessions(*, previous: dict | None, new: list[str],
                     plan_file: Path | None, mode: str
                     ) -> tuple[list[tuple[str, Path]], dict | None]:
    if plan_file is not None and new:
        raise InputError("use either full evidence plan or explicit new sessions")
    if mode == "refresh" and (plan_file is None or new or previous is None):
        raise InputError("refresh requires old campaign and full explicit plan")
    if plan_file is not None:
        decoded, _ = runbook.read_plan(plan_file)
        selected = decoded["sessions"]
    else:
        parsed = sessions_audit._parse_labeled_entries(new, "--session")
        selected = _entries_from_previous(previous) + list(parsed.items())
    if not selected or len(selected) > sessions_audit.MAX_SESSIONS:
        raise InputError("must provide 1-24 real copied sessions")
    if len({label for label, _ in selected}) != len(selected):
        raise InputError("repeated shadow session label")
    if previous is not None:
        old = _entries_from_previous(previous)
        if mode == "refresh":
            if selected != old:
                raise InputError("macro refresh must use exact old price sessions")
        elif len(selected) <= len(old) or selected[:len(old)] != old:
            raise InputError("shadow step must append a NEW session only")
    return selected, decoded if plan_file is not None else None


def inspect(*, mode: str, asof_utc: str, new_sessions: list[str],
            previous: dict | None = None,
            plan_file: Path | None = None) -> dict:
    if mode not in ("start", "step", "refresh") or (
            (mode == "start") == (previous is not None)):
        raise InputError("invalid shadow state transition")
    now = timestamp(asof_utc)
    selected, selected_plan = _choose_sessions(
        previous=previous, new=new_sessions, plan_file=plan_file, mode=mode)
    # The complete existing offline pilot runs macro, price, news, blackout,
    # safety fault and risk-acceptance debt audits on declared evidence.
    if selected_plan is None:
        values = [f"{label}={folder.absolute()}" for label, folder in selected]
        pilot_summary, runbook_report, _ = pilot.inspect(
            mode="audit", asof_utc=asof_utc, sessions=values)
        evidence_plan_sha = None
    else:
        pilot_summary, runbook_report, _ = pilot.inspect(
            mode="audit", asof_utc=asof_utc, plan_file=plan_file)
        evidence_plan_sha = runbook_report["plan_sha256_local_integrity_only"]
    if (pilot_summary.get("runtime_go_no_go") != "NO_GO"
            or pilot_summary.get("safety_hold_latched") is not True
            or pilot_summary.get("demo_orders_permitted") is not False
            or pilot_summary.get("real_orders_permitted") is not False
            or pilot_summary.get("orders_sent_this_run") != 0
            or runbook_report is None):
        raise InputError("underlying integrated pilot escaped research hold")
    audited = sessions_audit.inspect(selected, asof_utc=asof_utc,
                                    experts=selected_plan["experts"]
                                    if selected_plan else None,
                                    compiles=selected_plan["compiles"]
                                    if selected_plan else None)
    if (audited.get("runtime_go_no_go") != "NO_GO"
            or audited.get("safety_hold_latched") is not True
            or audited.get("demo_orders_permitted") is not False
            or audited.get("real_orders_permitted") is not False):
        raise InputError("shadow source audit escaped research hold")
    if (any(issue in HARD_VETOES
            for issue in audited["issues_and_safety_holds"])
            or audited["incomplete_cycle_count"] != 0):
        raise InputError("incomplete, repeated or structurally unsafe MT4 data")
    if len(selected) != audited["session_count"]:
        raise InputError("shadow session count mismatch")
    source = []
    last_seen = None
    fresh_added = False
    first_old_count = len(previous["sessions"]) if previous else 0
    for index, ((label, folder), entry) in enumerate(zip(selected, audited["sessions"])):
        if entry["label"] != label:
            raise InputError("session label mismatch")
        member = _session_manifest(folder)
        start = timestamp(entry["first_observation_utc"])
        end = timestamp(entry["last_observation_utc"])
        if last_seen is not None and start <= last_seen:
            raise InputError("old and new session timing overlaps/replays")
        last_seen = end
        if index >= first_old_count and now - end <= timedelta(hours=MAX_AGE_HOURS):
            fresh_added = True
        source.append({
            "label": label,
            "directory": str(folder.absolute()),
            **member,
            "first_observation_utc_unattested": entry["first_observation_utc"],
            "last_observation_utc_unattested": entry["last_observation_utc"],
            "complete_cycles": entry["complete_cycles"],
        })
    if previous is not None and source[:first_old_count] != previous["sessions"]:
        raise InputError("previous copied observation bytes changed")
    full = runbook_report["fullstack_report"]
    macro_events = full["price_ai_macro_observation_count"]
    reviews = full["price_ai_independent_review_count"]
    macro_holds = (
        full["external_macro_event_observations"] == 0
        or full["external_macro_missing_consensus_count"] != 0
        or macro_events == 0 or reviews == 0)
    if mode == "refresh":
        if selected_plan is None or selected_plan["observation_store"] is None:
            raise InputError("macro refresh requires a real observation journal")
        old_events = previous["reviewed_macro_event_count_in_supplied_journal"]
        old_reviews = previous["independent_review_count_in_supplied_journal"]
        if (macro_events < old_events or reviews < old_reviews
                or (macro_events == old_events and reviews == old_reviews)):
            raise InputError("macro refresh did not add any observed event/review")
    verdict = {
        pair: {
            "status": "SAFETY_HOLD_NO_VALIDATED_LIVE_AI_DECISION",
            "direction": "NO_SIGNAL",
            "source": "DETERMINISTIC_RESEARCH_GATE_NOT_AN_AI_PREDICTION",
            "position_opened": False,
            "broker_order_sent": False,
            "simulated_fill_generated": False,
        }
        for pair in PAIR_SCOPE
    }
    return {
        "schema": SCHEMA,
        "status": (
            "SHADOW_FORWARD_STARTED_DATA_ONLY_HOLD_NO_GO"
            if mode == "start" and fresh_added else
            "SHADOW_FORWARD_BASELINE_ONLY_HOLD_NO_GO"
            if mode == "start" else
            "SHADOW_FORWARD_MACRO_EVIDENCE_REFRESHED_HOLD_NO_GO"
            if mode == "refresh" else
            "SHADOW_FORWARD_NEW_SESSION_RECORDED_HOLD_NO_GO"
            if fresh_added else "SHADOW_FORWARD_HISTORICAL_STEP_HOLD_NO_GO"),
        "mode": mode,
        "asof_utc_local_clock_unattested": asof_utc,
        "sessions": source,
        "session_count": len(source),
        "new_session_count": len(source)-first_old_count,
        "complete_cycles_all_sessions": audited["complete_cycle_count"],
        "incomplete_cycles_all_sessions": audited["incomplete_cycle_count"],
        "new_observation_within_24h": fresh_added,
        "old_sessions_rechecked_sha256_each_step": previous is not None,
        "mt4_report_integrity_checked": True,
        "fullstack_report_sha256_local_only": _sha(_canonical(runbook_report)),
        "evidence_plan_sha256_local_only": evidence_plan_sha,
        "reviewed_macro_event_count_in_supplied_journal": macro_events,
        "independent_review_count_in_supplied_journal": reviews,
        "future_macro_calendar_and_consensus_incomplete": macro_holds,
        "no_spread_adjusted_marks_without_review": reviews == 0,
        "per_pair_shadow_decision_gate": verdict,
        "AI_hypotheses_generated_in_this_cycle": 0,
        "actual_AI_inference_performed": False,
        "forward_AI_inference_stage_ready_without_real_evidence": False,
        "unresolved_fullstack_holds": full["unresolved_holds"],
        "next_research_actions": full["next_research_actions"],
        "source_real_broker_provenance_attested": False,
        "independent_forecast_publication_clock_attested": False,
        "orders_sent_this_run": 0,
        "API_calls_this_run": 0,
        "network_calls_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def _append(folder: Path, record: dict, *, previous_hash: str | None,
            sequence: int) -> dict:
    item = {"schema": RECORD, "sequence": sequence,
            "prev_record_sha256": previous_hash, "record": record}
    item["record_sha256"] = _sha(_canonical(item))
    raw = json.dumps(item, ensure_ascii=False, indent=2,
                     allow_nan=False).encode("utf-8")
    if len(raw) > MAX_REPORT_BYTES:
        raise InputError("shadow record too large")
    with (folder / f"{sequence:08d}.json").open("xb") as target:
        target.write(raw)
    return item


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Begin/step/read immutable no-order shadow forward study")
    parser.add_argument("--mode", choices=("start", "step", "refresh", "status"), required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--session", action="append", default=[])
    parser.add_argument("--plan-file", type=Path)
    parser.add_argument("--asof-utc")
    args = parser.parse_args(argv)
    try:
        asof = args.asof_utc or _now()
        timestamp(asof)
        if args.mode == "status":
            if args.session or args.plan_file:
                raise InputError("status is read-only and accepts no new evidence")
            rows = _load(args.state_dir)
            last = rows[-1]
            report = last["record"]
            # Status never silently claims sources remain current, or replays
            # the last verified state without warning.
            answer = {
                "schema": SCHEMA, "status": "SHADOW_FORWARD_HISTORY_ONLY_HOLD_NO_GO",
                "latest_record_sha256_local_only": last["record_sha256"],
                "registered_record_count": len(rows),
                "last_report": report["status"],
                "last_asof_utc_unattested": report["asof_utc_local_clock_unattested"],
                "source_rechecked_in_this_status_call": False,
                "AI_calls_this_run": 0, "orders_sent_this_run": 0,
                "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
                "demo_orders_permitted": False, "real_orders_permitted": False,
            }
        else:
            if args.mode == "start":
                _safe_state_dir(args.state_dir, new=True)
                rows = []
            else:
                rows = _load(args.state_dir)
                if len(rows) >= MAX_RECORDS:
                    raise InputError("shadow campaign reached append cap")
            previous = rows[-1]["record"] if rows else None
            record = inspect(
                mode=args.mode, asof_utc=asof, new_sessions=args.session,
                previous=previous, plan_file=args.plan_file)
            # Neither evidence folder nor any of its parents may contain the
            # output state dir; no auto write inside saved MT4 material.
            # Normalize both sides through the same Windows/Unix resolver.
            # Path.absolute() may retain a different physical spelling from
            # Path.resolve(), silently allowing an output under raw CSVs.
            absolute_out = args.state_dir.resolve(strict=False)
            for entry in record["sessions"]:
                source_dir = Path(entry["directory"]).resolve(strict=True)
                if absolute_out == source_dir or source_dir in absolute_out.parents:
                    raise InputError("cannot create campaign inside source folder")
            if args.mode == "start":
                args.state_dir.mkdir()
            item = _append(
                args.state_dir, record,
                previous_hash=rows[-1]["record_sha256"] if rows else None,
                sequence=len(rows)+1)
            answer = {
                "schema": SCHEMA, "status": record["status"],
                "record_sha256_local_only": item["record_sha256"],
                "state_dir": str(args.state_dir),
                "session_count": record["session_count"],
                "complete_cycles": record["complete_cycles_all_sessions"],
                "new_session_count": record["new_session_count"],
                "new_observation_within_24h": record["new_observation_within_24h"],
                "registered_macro_events": record[
                    "reviewed_macro_event_count_in_supplied_journal"],
                "registered_review_count": record[
                    "independent_review_count_in_supplied_journal"],
                "AI_hypotheses_generated_this_cycle": 0,
                "orders_sent_this_run": 0, "API_calls_this_run": 0,
                "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
                "demo_orders_permitted": False, "real_orders_permitted": False,
            }
        print(json.dumps(answer, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, OSError, TypeError, ValueError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "SHADOW_FORWARD_FAIL_CLOSED_NO_GO",
            "reason": "MISSING_CHANGED_OR_INCONSISTENT_FORWARD_EVIDENCE",
            "orders_sent_this_run": 0,
            "API_calls_this_run": 0,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
