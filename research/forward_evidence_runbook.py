"""FWD-617..672: one reusable, bounded offline FX evidence runbook.

A user-selected plan is a set of explicit local paths, not a discovery
mechanism. Resolve paths relative to the plan; never glob, recurse, fetch,
modify sources, call MT4/brokers/AI, or authorize demo/live trading.
An empty template can be created once with --init-plan; no background work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research import forward_fullstack_noorder_hub as hub
from research import forward_readiness_drift as drift
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_evidence_runbook_v1"
RESULT = "fx_fwd_evidence_runbook_readiness_v1"
MAX_PLAN_BYTES = 32_000
MAX_REPORT_BYTES = 500_000
MAX_SOURCE_PATH_CHARS = 1024
FIELDS = frozenset((
    "schema", "bls_snapshot_dir", "official_news_bundle",
    "external_macro_file", "forecast_archives", "sessions",
    "observation_store", "ai_ledgers"))
SESSION_FIELDS = frozenset((
    "label", "directory", "experts_log", "compile_log"))
LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def empty_plan() -> dict:
    return {
        "schema": SCHEMA,
        "bls_snapshot_dir": None,
        "official_news_bundle": None,
        "external_macro_file": None,
        "forecast_archives": [],
        "sessions": [],
        "observation_store": None,
        "ai_ledgers": [],
    }


def _bytes(path: Path, limit: int) -> bytes:
    if (not isinstance(path, Path) or path.is_symlink()
            or not path.is_file() or not 0 < path.stat().st_size <= limit):
        raise InputError("absent/unsafe/oversized read-only evidence file")
    data = path.read_bytes()
    if not 0 < len(data) <= limit:
        raise InputError("evidence file changed size while reading")
    return data


def _path(base: Path, value: object, *, kind: str) -> Path | None:
    if value is None:
        return None
    if (type(value) is not str or not 1 <= len(value) <= MAX_SOURCE_PATH_CHARS
            or any(x in value for x in ("\x00", "\n", "\r"))
            or value != value.strip()
            or "*" in value or "?" in value):
        raise InputError("unsafe or ambiguous explicit evidence path")
    p = Path(value)
    if not p.is_absolute():
        p = base / p
    # Ensure the named evidence item exists now and has the intended kind.
    # No symlink following for the named evidence item or its parents.
    if p.is_symlink():
        raise InputError("symlink evidence path not accepted")
    p = p.absolute()
    for ancestor in p.parents:
        if ancestor.is_symlink():
            raise InputError("symlink ancestor in evidence path")
    if kind == "dir" and not p.is_dir():
        raise InputError("evidence folder not found")
    if kind == "file" and not p.is_file():
        raise InputError("evidence file not found")
    return p


def _unique_paths(paths: list[Path | None]) -> None:
    found = set()
    for p in paths:
        if p is None:
            continue
        resolved = p.resolve(strict=True)
        if resolved in found:
            raise InputError("duplicated evidence path in runbook")
        found.add(resolved)


def decode(plan: object, *, plan_file: Path) -> dict:
    if type(plan) is not dict or set(plan) != FIELDS or plan["schema"] != SCHEMA:
        raise InputError("unexpected runbook schema or keys")
    if (type(plan["forecast_archives"]) is not list
            or len(plan["forecast_archives"]) > 64
            or type(plan["ai_ledgers"]) is not list
            or len(plan["ai_ledgers"]) > 24
            or type(plan["sessions"]) is not list
            or len(plan["sessions"]) > 24):
        raise InputError("runbook evidence count exceeded")
    base = plan_file.absolute().parent
    bls = _path(base, plan["bls_snapshot_dir"], kind="dir")
    news = _path(base, plan["official_news_bundle"], kind="dir")
    external = _path(base, plan["external_macro_file"], kind="file")
    store = _path(base, plan["observation_store"], kind="file")
    forecasts = [_path(base, x, kind="file")
                 for x in plan["forecast_archives"]]
    ledgers = [_path(base, x, kind="file") for x in plan["ai_ledgers"]]
    if None in forecasts or None in ledgers:
        raise InputError("null entry in evidence file collection")
    sessions = []
    experts = {}
    compiles = {}
    labels = set()
    for item in plan["sessions"]:
        if (type(item) is not dict or set(item) != SESSION_FIELDS
                or type(item["label"]) is not str
                or not LABEL.fullmatch(item["label"])
                or item["label"] in labels):
            raise InputError("invalid or duplicate MT4 session")
        name = item["label"]
        labels.add(name)
        folder = _path(base, item["directory"], kind="dir")
        if folder is None:
            raise InputError("MT4 session folder missing")
        sessions.append((name, folder))
        expert = _path(base, item["experts_log"], kind="file")
        compile_log = _path(base, item["compile_log"], kind="file")
        if expert is not None:
            experts[name] = expert
        if compile_log is not None:
            compiles[name] = compile_log
    allpaths = [bls, news, external, store, *forecasts, *ledgers]
    allpaths.extend(x for _, x in sessions)
    allpaths.extend(experts.values())
    allpaths.extend(compiles.values())
    _unique_paths(allpaths)
    # Prevent reports and plans masquerading as evidence items.
    if plan_file.absolute().resolve() in {
            p.resolve(strict=True) for p in allpaths if p is not None}:
        raise InputError("runbook plan is also an evidence source")
    return {
        "bls_snapshot_dir": bls,
        "official_news_bundle": news,
        "external_macro_file": external,
        "forecast_archives": forecasts,
        "sessions": sessions,
        "experts": experts,
        "compiles": compiles,
        "observation_store": store,
        "ai_ledgers": ledgers,
        "evidence_paths": allpaths,
    }


def read_plan(path: Path) -> tuple[dict, str]:
    raw = _bytes(path, MAX_PLAN_BYTES)
    data = json.loads(raw.decode("utf-8-sig"))
    decoded = decode(data, plan_file=path)
    return decoded, hashlib.sha256(raw).hexdigest()


def _category(action: str) -> str:
    if any(word in action for word in (
            "CONSENSUS", "FORECAST", "PRE_RELEASE")):
        return "PRIORITY_1_PRE_RELEASE_CONSENSUS_EVIDENCE"
    if any(word in action for word in (
            "CALENDAR", "BLS", "MACRO", "SCHEDULE", "EVENT_SOURCE")):
        return "PRIORITY_2_GLOBAL_EVENT_SOURCE_COVERAGE"
    if any(word in action for word in (
            "MT4", "BROKER", "ACCOUNT", "OBSERVER",
            "CAP_STOP", "30_CYCLE", "OBSERVATION_TIME")):
        return "PRIORITY_3_MT4_NOORDER_SAFETY_EVIDENCE"
    if any(word in action for word in (
            "PRICE", "CSV", "AI", "HYPOTHESIS", "REVIEW", "QUOTE")):
        return "PRIORITY_4_PRICE_AI_RESEARCH"
    return "PRIORITY_5_OTHER_RESEARCH_TASKS"


def prioritize(actions: object) -> list[dict]:
    if (type(actions) is not list or len(actions) > 256
            or any(type(a) is not str or len(a) > 150 or not a
                   for a in actions)):
        raise InputError("invalid research tasks")
    labels = list(dict.fromkeys(actions))
    return [
        {"category": category,
         "action_count": len(group),
         "actions": group}
        for category, group in sorted((
            (category, [a for a in labels if _category(a) == category])
            for category in sorted({_category(a) for a in labels})))
        if group
    ]


def inspect(plan: dict, *, asof_utc: str, plan_sha256: str,
            previous_report: dict | None = None) -> dict:
    ext = (hub.global_macro._load(plan["external_macro_file"])
           if plan["external_macro_file"] else None)
    report = hub.inspect(
        asof_utc=asof_utc,
        bls_snapshot_dir=plan["bls_snapshot_dir"],
        official_news_bundle=plan["official_news_bundle"],
        external_macro_observations=ext,
        forecast_archives=plan["forecast_archives"],
        sessions=plan["sessions"],
        experts=plan["experts"],
        compiles=plan["compiles"],
        observation_store=plan["observation_store"],
        ai_ledgers=plan["ai_ledgers"])
    if (report["runtime_go_no_go"] != "NO_GO"
            or report["real_orders_permitted"] is not False
            or report["demo_orders_permitted"] is not False
            or report["safety_hold_latched"] is not True):
        raise InputError("integrated report violated safety conditions")
    delta = (drift.compare(previous_report, report)
             if previous_report is not None else None)
    return {
        "schema": RESULT,
        "status": "RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO",
        "plan_sha256_local_integrity_only": plan_sha256,
        "plan_source_authenticity_unattested": True,
        "asof_utc_local_or_supplied_unattested": asof_utc,
        "input_evidence_counts": {
            "bls_bundle": int(plan["bls_snapshot_dir"] is not None),
            "official_news_bundle": int(plan["official_news_bundle"] is not None),
            "external_macro_file": int(plan["external_macro_file"] is not None),
            "forecast_archives": len(plan["forecast_archives"]),
            "mt4_sessions": len(plan["sessions"]),
            "ai_ledgers": len(plan["ai_ledgers"]),
        },
        "priority_research_tasks_advisory_only":
            prioritize(report["next_research_actions"]),
        "compared_prior_report_self_attested_only": delta is not None,
        "previous_report_change_summary": delta,
        "fullstack_report": report,
        "no_go_cannot_be_cleared_by_runbook": True,
        "automatic_network_or_api_calls": False,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Single read-only batch evidence plan with optional delta")
    p.add_argument("--plan-file", type=Path)
    p.add_argument("--init-plan", type=Path)
    p.add_argument("--init-bls-snapshot-dir", type=Path)
    p.add_argument("--init-official-news-bundle", type=Path)
    p.add_argument("--previous-report", type=Path)
    p.add_argument("--asof-utc")
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    try:
        if a.init_plan is not None:
            if (a.plan_file or a.previous_report or a.asof_utc or a.out
                    or a.init_plan.exists() or a.init_plan.is_symlink()
                    or a.init_plan.parent.is_symlink()
                    or not a.init_plan.parent.is_dir()):
                raise InputError("unsafe plan initialization")
            contents = empty_plan()
            source_directories = []
            if a.init_bls_snapshot_dir is not None:
                pth = a.init_bls_snapshot_dir.absolute()
                contents["bls_snapshot_dir"] = str(
                    _path(a.init_plan.parent.absolute(), str(pth), kind="dir"))
                source_directories.append(Path(contents["bls_snapshot_dir"]))
            if a.init_official_news_bundle is not None:
                pth = a.init_official_news_bundle.absolute()
                contents["official_news_bundle"] = str(
                    _path(a.init_plan.parent.absolute(), str(pth), kind="dir"))
                source_directories.append(Path(contents["official_news_bundle"]))
            hub._checked_new_output(a.init_plan, source_directories)
            with a.init_plan.open("x", encoding="utf-8") as f:
                json.dump(contents, f, ensure_ascii=False, indent=2)
            print(json.dumps({
                "schema": SCHEMA, "status": "EMPTY_RESEARCH_PLAN_CREATED_NO_GO",
                "filename": str(a.init_plan),
                "evidence_sources_populated": False,
                "automatic_network_or_api_calls": False,
                "real_orders_permitted": False, "demo_orders_permitted": False,
                "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
            }))
            return 0
        if a.plan_file is None or (a.init_bls_snapshot_dir is not None
                                   or a.init_official_news_bundle is not None):
            raise InputError("explicit plan-file required; init options only for init-plan")
        sources, plan_sha = read_plan(a.plan_file)
        asof = a.asof_utc or hub._now()
        previous = (json.loads(
            _bytes(a.previous_report, MAX_REPORT_BYTES).decode("utf-8-sig"))
            if a.previous_report is not None else None)
        if a.out is not None:
            hub._checked_new_output(
                a.out, [a.plan_file, a.previous_report,
                        *sources["evidence_paths"]])
        result = inspect(sources, asof_utc=asof, plan_sha256=plan_sha,
                         previous_report=previous)
        if a.out is not None:
            with a.out.open("x", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2,
                          allow_nan=False)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": RESULT,
            "status": "RUNBOOK_RESEARCH_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_PLAN_OR_INCONSISTENT_EVIDENCE",
            "network_calls_this_run": 0, "API_calls_this_run": 0,
            "orders_sent_this_run": 0,
            "demo_orders_permitted": False, "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
