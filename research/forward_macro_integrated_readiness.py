"""FWD-245..252: single-command offline macro forward readiness stage board.

Brings existing quote/AI outcome campaign, bounded BLS calendar windows and
a write-once forecast archive together. This tool never downloads a feed,
calls paid inference, emits orders, modifies research sources or self-approves.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.forward_macro_campaign_board import inspect as campaign
from research import forward_bls_macro_source_gate as source_gate
from research import forward_bls_snapshot_diff as bls_integrity
from research import forward_bls_dual_snapshot as bls_snapshot
from research import forward_global_macro_evidence as global_macro
from research import forward_multi_official_news_snapshot as official_news
from research.forward_macro_event_windows import inspect as windows
from research.forward_macro_pre_release_capture import (
    verify_archive as verify_forecast)
from research.forward_mt4_multisession_reliability import _parse_labeled_entries
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_macro_integrated_forward_research_v2"


def inspect(sessions, *, asof_utc: str, store: Path | None = None,
            calendar: dict | None = None, forecast_archive: dict | None = None,
            ai_ledgers: list[Path] | None = None,
            bls_snapshot_dir: Path | None = None,
            external_macro_observations: dict | None = None,
            official_news_bundle: Path | None = None) -> dict:
    timestamp(asof_utc)
    bls_sources = None
    if bls_snapshot_dir is not None:
        # Never use an unchecked local bundle as calendar evidence.
        bls_sources = source_gate.inspect(
            bls_snapshot_dir, asof_utc=asof_utc,
            forecast_archive=forecast_archive)
        bls_integrity.verify(bls_snapshot_dir)
        original = json.loads(bls_integrity._bytes(
            bls_snapshot_dir, bls_snapshot.CAL_NAME,
            bls_integrity.MAX_CALENDAR))
        if type(original) is not dict:
            raise InputError("saved source calendar root invalid")
        if calendar is not None and calendar != original:
            raise InputError("calendar report disagrees with saved BLS bundle")
        calendar = original
    if forecast_archive is not None and calendar is None:
        raise InputError("forecast archive needs matching calendar evidence")
    news = (official_news.verify(official_news_bundle)
            if official_news_bundle is not None else None)
    external = (
        global_macro.inspect_observations(
            external_macro_observations, asof_utc=asof_utc)
        if external_macro_observations is not None else None)
    price_and_ai = campaign(
        sessions, asof_utc=asof_utc, store=store, ai_ledgers=ai_ledgers)
    schedule = (windows(calendar, asof_utc=asof_utc)
                if calendar is not None else None)
    evidence = (verify_forecast(forecast_archive, asof_utc=asof_utc)
                if forecast_archive is not None else None)
    warnings = set(price_and_ai["unresolved_warnings_and_safety_holds"])
    tasks = list(price_and_ai["next_research_actions"])
    if news is not None:
        warnings.add("OFFICIAL_RSS_NEWS_NOT_A_FUTURE_MACRO_CALENDAR")
        warnings.add("OFFICIAL_RSS_NEWS_CONSENSUS_UNAVAILABLE")
        tasks.append("COLLECT_PRE_RELEASE_CONSENSUS_SEPARATELY_FROM_NEWS")
    if external is not None:
        warnings.update(external["unresolved_holds"])
        tasks.extend(external["next_research_actions"])
    if bls_sources is not None:
        warnings.update(bls_sources["unresolved_holds"])
        tasks.extend(bls_sources["next_research_actions"])
    if schedule is None:
        warnings.add("NO_BLS_CALENDAR_RESEARCH_SNAPSHOT")
        tasks.append("OBTAIN_FRESH_BLS_RELEASE_CALENDAR_EXPLICITLY")
    else:
        warnings.update(schedule["data_holds"])
        if schedule["calendar_stale"]:
            tasks.append("RECHECK_BLS_CALENDAR_STALE")
    matched_forecast = False
    if evidence is None:
        warnings.add("NO_PRE_RELEASE_FORECAST_CAPTURE_PROVIDED")
        tasks.append("ARCHIVE_POINT_IN_TIME_CONSENSUS_BEFORE_BLACKOUT")
    elif schedule is not None:
        matched_forecast = (
            evidence["calendar_report_sha256_self_reported"]
            == schedule["calendar_sha256_self_reported"]
            and any(
                x["scheduled_at_utc_unverified"]
                == evidence["scheduled_at_utc_unverified"]
                and x["title_unverified"]
                == evidence["event_title_unverified"]
                for x in schedule["windows"]))
        if not matched_forecast:
            warnings.add("CONSENSUS_ARCHIVE_CALENDAR_IDENTITY_CHANGED")
            tasks.append("RECONCILE_CALENDAR_REVISION_WITH_FORECAST_ARCHIVE")
    # There is no schedule that proves coverage of FOMC, Europe or
    # Japan, and past out-of-window RSS items never become fresh evidence.
    warnings.add("COMPLETE_GLOBAL_ECONOMIC_CALENDAR_NOT_ATTESTED")
    warnings.add("HYPOTHESIS_REVIEW_AND_PROFITABILITY_NOT_CERTIFIED")
    return {
        "schema": SCHEMA,
        "status": "INTEGRATED_MACRO_FORWARD_READINESS_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "price_csv_count": price_and_ai["price_csv_count"],
        "complete_cycle_count": price_and_ai["complete_cycle_count"],
        "macro_event_count": price_and_ai["observed_macro_event_count"],
        "research_review_count": price_and_ai["review_count"],
        "descriptive_post_review_marks":
            price_and_ai["descriptive_two_snapshot_mark_count"],
        "calendar_supplied": schedule is not None,
        "calendar_current_within_24h": (
            not schedule["calendar_stale"] if schedule else False),
        "scheduled_bls_event_count": (
            len(schedule["windows"]) if schedule else 0),
        "active_15_minute_research_window_count": (
            schedule["active_research_blackout_count"] if schedule else 0),
        "pre_release_forecast_archive_supplied": evidence is not None,
        "forecast_archive_matches_current_schedule": matched_forecast,
        "forecast_source_independently_authenticated": False,
        "official_news_bundle_verified": news is not None,
        "official_news_feed_count": news["feed_count"] if news else 0,
        "official_news_item_count": news["news_items_count"] if news else 0,
        "official_news_calendar_or_consensus_sufficient": False,
        "external_macro_evidence_supplied": external is not None,
        "external_macro_event_count": (
            external["external_event_observations_supplied"]
            if external is not None else 0),
        "external_macro_by_currency": (
            external["external_by_currency"] if external is not None
            else {"USD": 0, "EUR": 0, "JPY": 0}),
        "external_macro_missing_consensus_count": (
            external["external_missing_consensus_count"]
            if external is not None else 0),
        "external_macro_source_independently_attested": False,
        "bls_original_source_bundle_verified": bls_sources is not None,
        "bls_html_ics_schedule_disagreement": (
            bls_sources["html_ics_slot_count_disagreement"]
            if bls_sources is not None else None),
        "bls_html_only_missing_slot_instances": (
            bls_sources["missing_html_slot_instances"]
            if bls_sources is not None else None),
        "bls_snapshot_older_than_24h": (
            bls_sources["snapshot_older_than_24h"]
            if bls_sources is not None else None),
        "bls_saved_calendar_ics_sha256": (
            bls_sources["calendar_ics_sha256"]
            if bls_sources is not None else None),
        "independent_economic_calendar_coverage_certified": False,
        "pre_release_consensus_source_authenticity_certified": False,
        "unresolved_holds": sorted(warnings),
        "next_research_actions": list(dict.fromkeys(tasks)),
        "automatic_calendar_polling_enabled": False,
        "API_calls_this_run": 0,
        "actual_orders_submitted": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def _read(path: Path, cap: int):
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= cap):
        raise InputError("unsafe supporting research evidence file")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="One-shot read-only research readiness")
    p.add_argument("--session", action="append", required=True)
    p.add_argument("--store", type=Path)
    p.add_argument("--calendar-report", type=Path)
    p.add_argument("--bls-snapshot-dir", type=Path)
    p.add_argument("--external-macro-file", type=Path)
    p.add_argument("--official-news-bundle", type=Path)
    p.add_argument("--forecast-archive", type=Path)
    p.add_argument("--ai-ledger", action="append", type=Path, default=[])
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        sessions = list(_parse_labeled_entries(
            a.session, "--session").items())
        folders = [path.resolve() for _, path in sessions]
        if a.store:
            folders.append(a.store.resolve())
        if (a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()
                or any(folder in a.out.resolve().parents
                       for folder in folders)):
            raise InputError("invalid integrated report output")
        calendar = (_read(a.calendar_report, 160000)
                    if a.calendar_report else None)
        archive = (_read(a.forecast_archive, 8000)
                   if a.forecast_archive else None)
        external = (_read(a.external_macro_file,
                          global_macro.MAX_INPUT_BYTES)
                    if a.external_macro_file else None)
        report = inspect(
            sessions, asof_utc=a.asof_utc, store=a.store,
            calendar=calendar, forecast_archive=archive,
            ai_ledgers=a.ai_ledger,
            bls_snapshot_dir=a.bls_snapshot_dir,
            external_macro_observations=external,
            official_news_bundle=a.official_news_bundle)
        with a.out.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": report["status"],
            "price_csv_count": report["price_csv_count"],
            "macro_event_count": report["macro_event_count"],
            "scheduled_bls_event_count": report["scheduled_bls_event_count"],
            "forecast_archive_matches_current_schedule":
                report["forecast_archive_matches_current_schedule"],
            "bls_original_source_bundle_verified":
                report["bls_original_source_bundle_verified"],
            "external_macro_evidence_supplied":
                report["external_macro_evidence_supplied"],
            "external_macro_event_count":
                report["external_macro_event_count"],
            "official_news_bundle_verified":
                report["official_news_bundle_verified"],
            "official_news_item_count":
                report["official_news_item_count"],
            "external_macro_missing_consensus_count":
                report["external_macro_missing_consensus_count"],
            "bls_html_ics_schedule_disagreement":
                report["bls_html_ics_schedule_disagreement"],
            "bls_html_only_missing_slot_instances":
                report["bls_html_only_missing_slot_instances"],
            "next_research_actions": report["next_research_actions"],
            "API_calls_this_run": 0,
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            KeyError, UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "INTEGRATED_MACRO_FORWARD_EVIDENCE_INVALID",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
