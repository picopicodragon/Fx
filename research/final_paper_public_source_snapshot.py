"""Fetch ONLY a pinned public-source list into a new local no-order archive.

Public HTML/ICS copies establish local bytes and a PC-claimed capture time.
They do NOT establish complete USD/EUR/JPY high-impact event coverage,
independent point-in-time forecasts, broker time, or actual execution costs.
No AI keys, broker trading, risk-state mutation, or paid inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCHEMA = "fx_final_paper_official_source_snapshot_v1"
SOURCES = {
    "us_bls_calendar_ics": "https://www.bls.gov/schedule/news_release/bls.ics",
    "us_fomc_calendar": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    "eur_ecb_calendar": "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html",
    "jpy_boj_calendar": "https://www.boj.or.jp/en/about/calendar/",
    "rakuten_mt4_rules": "https://www.rakuten-sec.co.jp/web/fx/mt4/rule.html",
    "rakuten_mt4_swap_spread": "https://www.rakuten-sec.co.jp/web/fx/mt4/commission.html",
}
MAX_SOURCE_BYTES = 2_500_000
MAX_TOTAL_BYTES = 10_000_000


class SnapshotError(Exception):
    """Fail closed without leaking external page content."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SnapshotError("REDIRECT_REJECTED")


def _download(url: str) -> tuple[bytes, str]:
    # Construct only from the immutable above public official source table.
    expected_host = urlparse(url).hostname
    if urlparse(url).scheme != "https":
        raise SnapshotError("NON_HTTPS_SOURCE")
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "FX-PAPER-offline-evidence/1.0",
                 "Accept": "text/html,text/calendar,*/*"},
        method="GET",
    )
    with opener.open(req, timeout=20) as response:
        actual = response.geturl()
        if (urlparse(actual).scheme != "https"
                or urlparse(actual).hostname != expected_host):
            raise SnapshotError("ORIGIN_CHANGED")
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if not 0 < len(raw) <= MAX_SOURCE_BYTES:
            raise SnapshotError("SOURCE_EMPTY_OR_TOO_LARGE")
        return raw, response.headers.get("Date", "")


def snapshot(out: Path, *, allow_network: bool = False,
             fetcher=None, now=None) -> dict:
    if not allow_network:
        raise SnapshotError("EXPLICIT_PUBLIC_NETWORK_OPT_IN_REQUIRED")
    if (out.exists() or out.is_symlink()
            or not out.parent.is_dir() or out.parent.is_symlink()):
        raise SnapshotError("ARCHIVE_OUTPUT_EXISTS_OR_UNSAFE")
    out.mkdir()
    fetch = fetcher or _download
    archived = []
    failures = []
    total = 0
    for name, url in SOURCES.items():
        try:
            data, server_date = fetch(url)
            if (type(data) is not bytes
                    or not 0 < len(data) <= MAX_SOURCE_BYTES
                    or type(server_date) is not str
                    or total + len(data) > MAX_TOTAL_BYTES):
                raise SnapshotError("INVALID_OR_OVERSIZE_ORIGIN")
            total += len(data)
            name_ext = ".ics" if name.endswith("_ics") else ".html"
            filename = name + name_ext
            captured = now or datetime.now(timezone.utc)
            if captured.tzinfo is None:
                raise SnapshotError("MISSING_UTC_CLOCK")
            with (out / filename).open("xb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            archived.append({
                "source_id": name,
                "url": url,
                "archive_file": filename,
                "sha256_local_only": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "captured_at_utc_pc_unattested": captured.astimezone(
                    timezone.utc).isoformat().replace("+00:00", "Z"),
                "source_http_date_header_unverified": server_date[:100],
                "publication_authenticity_independently_attested": False,
                "calendar_semantics_extracted_or_verified": False,
            })
        except (SnapshotError, OSError, urllib.error.URLError,
                ValueError, TypeError):
            # Continue other official sources; do not fabricate missing data.
            failures.append(name)
    record = {
        "schema": SCHEMA,
        "status": (
            "PUBLIC_OFFICIAL_BYTES_ARCHIVED_NOT_ATTESTED_NO_GO"
            if not failures else "PUBLIC_OFFICIAL_SOURCE_ARCHIVE_PARTIAL_NO_GO"
        ),
        "source_count": len(SOURCES),
        "archived_count": len(archived),
        "failed_source_ids": failures,
        "sources": archived,
        "source_publication_time_independently_attested": False,
        "all_important_usd_eur_jpy_events_covered": False,
        "consensus_point_in_time_verified": False,
        "broker_clock_independently_verified": False,
        "real_transaction_costs_verified": False,
        "new_paid_ai_calls_allowed": False,
        "new_virtual_positions_allowed": False,
        "demo_orders_allowed": False,
        "real_orders_allowed": False,
        "runtime_go_no_go": "NO_GO",
    }
    with (out / "manifest.json").open("x", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    return record


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bounded official public pages to local hashed research archive")
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--allow-network", action="store_true")
    args = p.parse_args(argv)
    try:
        result = snapshot(args.out_dir, allow_network=args.allow_network)
        print(json.dumps({k: result[k] for k in (
            "status", "source_count", "archived_count", "failed_source_ids",
            "all_important_usd_eur_jpy_events_covered",
            "new_virtual_positions_allowed", "runtime_go_no_go"
        )}, ensure_ascii=False))
        return 0 if not result["failed_source_ids"] else 2
    except (SnapshotError, ValueError, OSError, TypeError):
        print(json.dumps({
            "status": "PUBLIC_OFFICIAL_SOURCE_CAPTURE_FAIL_CLOSED_NO_GO",
            "new_virtual_positions_allowed": False,
            "new_paid_ai_calls_allowed": False,
            "demo_orders_allowed": False,
            "real_orders_allowed": False,
            "runtime_go_no_go": "NO_GO",
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
