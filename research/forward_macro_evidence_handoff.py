"""FWD-223..233: prepare a linked macro-event evidence snapshot for 2-AI.

This creates an UNPUBLISHED research snapshot. The operator can separately
ingest it into the existing append-only observation chain, then invoke the
existing opt-in two-model API workflow. No orders, API calls, journal
mutation, background monitoring or invented market consensus.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_ai_shadow as ai
from research import forward_observation as obs
from research import forward_macro_consensus_surprise as econ
from research import forward_macro_pre_release_capture as forecast
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_release_source_submission_v1"
FIELDS = frozenset(("schema", "value", "unit", "source_text",
                    "source_sha256", "source_url",
                    "source_published_at_utc"))
HASH_LEN = 64
MAX_RELEASE_BYTES = 6000
MAX_FORECAST_BYTES = 8000
SHA = "0123456789abcdef"


def _read(path: Path, maximum: int) -> dict:
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= maximum):
        raise InputError("missing/unsafe macro source input")
    obj = json.loads(path.read_text("utf-8-sig"))
    if type(obj) is not dict:
        raise InputError("invalid macro source JSON")
    return obj


def prepare(store: Path, event_sha: str, forecast_archive: dict,
            release: dict, *, asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    archive = forecast.verify_archive(
        forecast_archive, asof_utc=asof_utc)
    if (type(release) is not dict or set(release) != FIELDS
            or release["schema"] != SCHEMA
            or release["unit"] != archive["unit"]
            or type(event_sha) is not str
            or len(event_sha) != HASH_LEN
            or any(c not in SHA for c in event_sha)):
        raise InputError("release/forecast mismatch")
    source = ai._event(store, event_sha)  # calls observation chain audit
    body = source["payload"]
    feed = source["source_id"]
    event_title = archive["event_title_unverified"].lower()
    if ((feed == "bls_cpi"
         and not any(x in event_title
                     for x in ("consumer price index", "cpi")))
            or (feed == "bls_empsit"
                and not any(x in event_title
                            for x in ("employment situation", "employment")))
            or feed not in ("bls_cpi", "bls_empsit")
            or body["pair"] != archive["pair"]
            or body["source_status"] != "USER_SUPPLIED_UNVERIFIED"
            or body["consensus"].strip()
            or body["released_value"].strip()):
        raise InputError("unsupported or already-enriched BLS research event")
    scheduled = timestamp(archive["scheduled_at_utc_unverified"])
    published = timestamp(body["published_at_utc"])
    if not scheduled <= published <= scheduled + timedelta(hours=4):
        raise InputError("BLS release does not match scheduled window")
    if timestamp(source["observed_at_utc"]) > now:
        raise InputError("future original observation")
    # Source must be truly observed before creating derived research
    # context. No adding a claimed macro event before its publication.
    if not published <= timestamp(source["observed_at_utc"]) <= now:
        raise InputError("unobserved or future BLS event")
    if (type(release["source_text"]) is not str
            or not 1 <= len(release["source_text"]) <= 1500
            or "\x00" in release["source_text"]
            or type(release["source_sha256"]) is not str
            or not len(release["source_sha256"]) == 64
            or any(c not in SHA for c in release["source_sha256"])
            or hashlib.sha256(
                release["source_text"].encode("utf-8")).hexdigest()
               != release["source_sha256"]):
        raise InputError("release excerpt hash invalid")
    # The release excerpt URL must be the same BLS article as the
    # observation. It cannot be an unrelated quote provider's claim.
    if (release["source_url"] != body["source_url"]
            or urlsplit(release["source_url"]).hostname != "www.bls.gov"):
        raise InputError("release excerpt does not point to event article")
    # Submitted publication time is a claim, not a verification.
    published_measurement = timestamp(release["source_published_at_utc"])
    if not scheduled <= published_measurement <= now:
        raise InputError("invalid release measurement publication")
    econ_doc = {
        "schema": econ.SCHEMA,
        "event_id": "linked_bls",
        "pair": archive["pair"],
        "event_type": "CPI" if feed == "bls_cpi" else "EMPLOYMENT",
        "unit": archive["unit"],
        "scheduled_at_utc": archive["scheduled_at_utc_unverified"],
        "forecast": {
            "value": archive["forecast_value_self_reported"],
            "source_text": archive["source_text_excerpt"],
            "source_sha256": archive["source_text_sha256"],
            "source_url": archive["source_url_unverified"],
            "published_at_utc": archive[
                "source_published_at_utc_self_reported"],
            "captured_at_utc": archive[
                "recorded_at_utc_local_clock_unattested"],
        },
        "release": {
            "value": release["value"],
            "source_text": release["source_text"],
            "source_sha256": release["source_sha256"],
            "source_url": release["source_url"],
            "published_at_utc": release["source_published_at_utc"],
            "captured_at_utc": asof_utc,
        },
    }
    survey = econ.inspect(econ_doc, asof_utc=asof_utc)
    # We deliberately do not perform a live research override or create
    # fills. These hashes are included in the observation body so the
    # original release and forecast can later be found for manual audit.
    source_line = (
        "\n[RESEARCH_ONLY_UNATTESTED_SOURCE_HASHES] "
        "original_macro_event=" + event_sha +
        " forecast_capture=" + forecast_archive["record_sha256"] +
        " release_excerpt=" + release["source_sha256"])
    body_text = body["content"][:max(0, 7000 - len(source_line))]
    snapshot = {
        "schema": obs.SCHEMA,
        "kind": "MACRO_EVENT",
        "observed_at_utc": asof_utc,
        "source_id": "macro_joined",
        "payload": {
            "pair": archive["pair"],
            "title": body["title"],
            "source_url": body["source_url"],
            "published_at_utc": body["published_at_utc"],
            "content": body_text + source_line,
            "consensus": archive["forecast_value_self_reported"],
            "released_value": str(econ._number(release["value"])),
            "source_status": "USER_SUPPLIED_UNVERIFIED",
        },
    }
    obs.snapshot_validate(snapshot, received_at=asof_utc)
    return {
        "status": "LINKED_MACRO_RESEARCH_PREPARED_NO_GO",
        "snapshot": snapshot,
        "surprise_research_only": survey[
            "released_minus_forecast_same_unit"],
        "forecast_archive_sha256": forecast_archive["record_sha256"],
        "source_event_record_sha256": event_sha,
        "source_content_or_forecast_authenticated": False,
        "economic_surprise_direction_not_a_trade_signal": True,
        "journal_modified": False,
        "AI_api_called": False,
        "broker_orders_sent": 0,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline BLS release research snapshot")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--event-sha256", required=True)
    p.add_argument("--forecast-archive", type=Path, required=True)
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--snapshot-out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if (a.snapshot_out.exists() or a.snapshot_out.is_symlink()
                or not a.snapshot_out.parent.is_dir()
                or a.snapshot_out.resolve().is_relative_to(
                    a.store.resolve())):
            raise InputError("invalid linked macro snapshot destination")
        archive = _read(a.forecast_archive, MAX_FORECAST_BYTES)
        release = _read(a.release, MAX_RELEASE_BYTES)
        now = datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        result = prepare(
            a.store, a.event_sha256, archive, release, asof_utc=now)
        with a.snapshot_out.open("x", encoding="utf-8") as dest:
            json.dump(result["snapshot"], dest, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "source_event_record_sha256": result[
                "source_event_record_sha256"],
            "surprise_research_only": result["surprise_research_only"],
            "journal_modified": False,
            "AI_api_called": False,
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError,
            TypeError, KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "LINKED_BLS_MACRO_CONTEXT_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
