"""FWD-553..600: one command for ALL existing offline forward readiness.

Composes actual validated BLS raw calendar, official news snapshots,
multi-currency user evidence, point-in-time consensus archives, copied MT4
observer sessions and the older multi-session price/AI campaign. Every
source remains explicitly optional: missing evidence is a HOLD, never
replaced by a fixture. Zero network, broker, MT4, inference or orders.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import forward_global_macro_evidence as global_macro
from research import forward_consensus_archive_batch as consensus
from research import forward_mt4_long_run_review as mt4
from research import forward_macro_campaign_board as campaign
from research import forward_multi_official_news_snapshot as official_news
from research import forward_mt4_multisession_reliability as mt4_reliability
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_fullstack_noorder_evidence_hub_v1"
MAX_LEDGER_FILES = 24


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def inspect(*, asof_utc: str,
            bls_snapshot_dir: Path | None = None,
            official_news_bundle: Path | None = None,
            external_macro_observations: dict | None = None,
            forecast_archives: list[Path] | None = None,
            sessions: list[tuple[str, Path]] | None = None,
            experts: dict[str, Path] | None = None,
            compiles: dict[str, Path] | None = None,
            observation_store: Path | None = None,
            ai_ledgers: list[Path] | None = None) -> dict:
    asof = global_macro._utc(asof_utc)
    forecasts = [] if forecast_archives is None else forecast_archives
    sessions = [] if sessions is None else sessions
    if type(forecasts) is not list or type(sessions) is not list:
        raise InputError("expected finite explicit evidence lists")
    ledgers = [] if ai_ledgers is None else ai_ledgers
    if (type(ledgers) is not list
            or len(ledgers) > MAX_LEDGER_FILES
            or any(not isinstance(p, Path) for p in ledgers)):
        raise InputError("invalid AI research ledger paths")
    if (not sessions and (observation_store is not None or ledgers)):
        raise InputError("price/AI research requires copied MT4 source sessions")
    macro = global_macro.inspect(
        asof_utc=asof_utc,
        bls_snapshot_dir=bls_snapshot_dir,
        official_news_bundle=official_news_bundle,
        external_observations=external_macro_observations)
    forecasts_report = consensus.inspect(
        forecasts, asof_utc=asof_utc,
        bls_snapshot_dir=bls_snapshot_dir)
    mt4_report = mt4.inspect(
        sessions, asof_utc=asof_utc,
        experts=experts, compiles=compiles)
    warnings = set(macro["unresolved_holds"])
    warnings.update(forecasts_report["unresolved_holds"])
    warnings.update(mt4_report["unresolved_holds"])
    tasks = (list(macro["next_research_actions"])
             + list(forecasts_report["next_research_actions"])
             + list(mt4_report["next_research_actions"]))
    # The news manifest clock is self-reported. Nevertheless refuse
    # impossible future captures and mark old research observations stale.
    news_stale = None
    if official_news_bundle is not None:
        raw = official_news._bytes(
            official_news_bundle / "manifest.json",
            limit=official_news.MAX_MANIFEST)
        manifest = json.loads(raw)
        captured = global_macro._utc(
            manifest["captured_at_utc_local_clock_unattested"])
        if captured > asof:
            raise InputError("future local-clock news snapshot")
        news_stale = asof - captured > timedelta(hours=24)
        if news_stale:
            warnings.add("OFFICIAL_NEWS_SNAPSHOT_OLDER_THAN_24H")
            tasks.append("EXPLICITLY_REFRESH_OFFICIAL_NEWS_IF_NEEDED")
    price = None
    if sessions:
        price = campaign.inspect(
            sessions, asof_utc=asof_utc,
            store=observation_store, ai_ledgers=ledgers)
        if (price.get("status") != "MACRO_RESEARCH_CAMPAIGN_HOLD_NO_GO"
                and price.get("runtime_go_no_go") != "NO_GO"):
            raise InputError("price/AI campaign escaped NO_GO scope")
        if (price.get("real_orders_permitted") is not False
                or price.get("safety_hold_latched") is not True):
            raise InputError("price/AI campaign safety flags incorrect")
        warnings.update(price["unresolved_warnings_and_safety_holds"])
        tasks.extend(price["next_research_actions"])
    else:
        warnings.add("PRICE_AI_CAMPAIGN_HAS_NO_VERIFIABLE_COPIED_SESSIONS")
        tasks.append("COLLECT_COPIED_MT4_CSV_FOR_PRICE_AI_RESEARCH")
    warnings.update({
        "COMPLETE_USD_EUR_JPY_FUTURE_CALENDAR_NOT_AUTHENTICATED",
        "MT4_BROKER_CLOCK_AND_DEMO_ORDER_DISABLED_NOT_INDEPENDENTLY_TESTED",
        "NO_AUTOMATED_RELEASE_BLACKOUT_OR_RECOVERY_AUTHORIZATION",
        "HUMAN_ACCEPTANCE_AND_REAL_TRADING_AUTHORIZATION_NOT_GRANTED",
    })
    return {
        "schema": SCHEMA,
        "status": "FULLSTACK_FORWARD_RESEARCH_READINESS_HOLD_NO_GO",
        "asof_utc_local_or_supplied_unattested": asof_utc,
        "bls_snapshot_verified": macro[
            "bls_snapshot_supplied_and_integrity_checked"],
        "bls_html_ics_event_count_disagrees":
            macro["bls_html_ics_disagreement"],
        "bls_html_missing_ics_slot_instances":
            macro["bls_html_only_missing_slot_instances"],
        "official_news_bundle_verified": macro[
            "official_news_bundle_verified"],
        "official_news_item_count": macro["official_news_items_observed"],
        "official_news_snapshot_older_than_24h": news_stale,
        "official_news_not_future_calendar": True,
        "external_macro_event_observations": macro[
            "external_event_observations_supplied"],
        "external_macro_by_currency": macro["external_by_currency"],
        "external_macro_missing_consensus_count":
            macro["external_missing_consensus_count"],
        "archived_consensus_records": forecasts_report["archive_count"],
        "archived_consensus_matching_bls_events":
            forecasts_report["matched_unique_bls_event_count"],
        "archived_consensus_unmatched": forecasts_report[
            "unmatched_archive_count"],
        "bls_events_without_archived_consensus":
            forecasts_report["bls_events_without_archive_count"],
        "mt4_copied_observation_session_count": mt4_report[
            "verified_format_copied_session_count"],
        "mt4_observed_ny17_time_bucket_count": mt4_report[
            "distinct_ny17_bucket_count"],
        "mt4_complete_observation_cycles": mt4_report[
            "complete_observation_cycle_count"],
        "price_ai_campaign_inspected": price is not None,
        "price_csv_count": price["price_csv_count"] if price else 0,
        "price_ai_macro_observation_count": (
            price["observed_macro_event_count"] if price else 0),
        "price_ai_independent_review_count": (
            price["review_count"] if price else 0),
        "number_of_holds": len(warnings),
        "unresolved_holds": sorted(warnings),
        "next_research_actions": list(dict.fromkeys(tasks)),
        "publisher_clock_and_consensus_independently_authenticated": False,
        "broker_and_mt4_order_safety_independently_verified": False,
        "coverage_completeness_proven": False,
        "live_trading_authorization_established": False,
        "automatic_download_or_retry": False,
        "API_calls_this_run": 0,
        "network_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def _checked_new_output(path: Path, evidence_paths: list[Path]) -> None:
    if (path.exists() or path.is_symlink() or not path.parent.is_dir()
            or path.parent.is_symlink()):
        raise InputError("report output must be absent in safe directory")
    out = path.resolve()
    for source in evidence_paths:
        if source is None:
            continue
        resolved = source.resolve()
        if out == resolved or resolved in out.parents:
            raise InputError("output inside immutable source evidence")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="One offline, no-order, no-provider full forward audit")
    p.add_argument("--bls-snapshot-dir", type=Path)
    p.add_argument("--official-news-bundle", type=Path)
    p.add_argument("--external-macro-file", type=Path)
    p.add_argument("--forecast-archive", action="append", type=Path,
                   default=[])
    p.add_argument("--session", action="append", default=[])
    p.add_argument("--experts", action="append", default=[])
    p.add_argument("--compile", action="append", default=[])
    p.add_argument("--observation-store", type=Path)
    p.add_argument("--ai-ledger", action="append", type=Path, default=[])
    p.add_argument("--asof-utc", default=None)
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    try:
        asof = a.asof_utc or _now()
        sessions = list(mt4_reliability._parse_labeled_entries(
            a.session, "--session").items())
        experts = mt4_reliability._parse_labeled_entries(
            a.experts, "--experts")
        compiles = mt4_reliability._parse_labeled_entries(
            a.compile, "--compile")
        evidence = [a.bls_snapshot_dir, a.official_news_bundle,
                    a.external_macro_file, a.observation_store]
        evidence.extend([p for _, p in sessions])
        evidence.extend(a.forecast_archive)
        evidence.extend(a.ai_ledger)
        evidence.extend(experts.values())
        evidence.extend(compiles.values())
        if a.out is not None:
            _checked_new_output(a.out, evidence)
        external = (
            global_macro._load(a.external_macro_file)
            if a.external_macro_file is not None else None)
        report = inspect(
            asof_utc=asof,
            bls_snapshot_dir=a.bls_snapshot_dir,
            official_news_bundle=a.official_news_bundle,
            external_macro_observations=external,
            forecast_archives=a.forecast_archive,
            sessions=sessions, experts=experts, compiles=compiles,
            observation_store=a.observation_store,
            ai_ledgers=a.ai_ledger)
        if a.out is not None:
            with a.out.open("x", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False,
                          allow_nan=False)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, OSError, ValueError, KeyError, TypeError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "FULLSTACK_FORWARD_RESEARCH_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_OR_CONFLICTING_RESEARCH_EVIDENCE",
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
