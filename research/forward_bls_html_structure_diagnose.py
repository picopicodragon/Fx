"""FWD-365: non-disclosing read-only structure diagnostic for BLS HTML.

Only numeric structural metadata is emitted. No user/private values, HTML
source text, calendar body, release titles or date/time events. Zero network.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research import forward_bls_saved_html_audit as audit
from research import forward_bls_dual_snapshot as snapshot
from research import forward_bls_snapshot_diff as integrity
from research.offline_backtest import InputError

SCHEMA = "fx_bls_saved_html_structure_diagnostic_v1"
MAX_TABLES_SHOWN = 12


def diagnose(folder: Path) -> dict:
    manifest = integrity.verify(folder)
    raw = integrity._bytes(
        folder, snapshot.HTML_NAME, snapshot.HTML_MAX_BYTES)
    doc = audit._TableRows()
    doc.feed(raw.decode("utf-8-sig"))
    doc.close()
    # Safe structural-only: do not output or log source paragraphs/events.
    known_header = ("date", "time", "release")
    eligible = 0
    for table in doc.tables:
        eligible += sum(
            len(row) == 3 and tuple(v.casefold() for v in row) == known_header
            for row in table)
    return {
        "schema": SCHEMA,
        "status": "BLS_SAVED_HTML_STRUCTURE_OBSERVATION_HOLD_NO_GO",
        "source_integrity_checked": True,
        "html_sha256_verified_against_snapshot": True,
        "html_sha256": manifest["html_sha256"],
        "table_count_all_nesting_depths": len(doc.tables),
        "table_parser_open_depth_at_end": doc.depth,
        "table_parser_invalid_structure": doc.invalid_structure,
        "date_time_release_header_count": eligible,
        "sampled_table_profiles": [
            {
                "row_count": len(table),
                "first_row_column_count": len(table[0]) if table else 0,
                "three_column_row_count": sum(len(row) == 3 for row in table),
            }
            for table in doc.tables[:MAX_TABLES_SHOWN]
        ],
        "omitted_table_count": max(0, len(doc.tables)-MAX_TABLES_SHOWN),
        "source_titles_dates_or_raw_body_included": False,
        "timezone_or_event_identity_verified": False,
        "network_calls_this_run": 0,
        "files_written_this_run": 0,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="BLS saved HTML nested structure, metadata-only NO_GO")
    p.add_argument("--snapshot-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(diagnose(args.snapshot_dir), ensure_ascii=False))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "BLS_SAVED_HTML_STRUCTURE_FAIL_CLOSED_NO_GO",
            "reason_code": "BUNDLE_INVALID_OR_UNAVAILABLE",
            "network_calls_this_run": 0,
            "files_written_this_run": 0,
            "API_calls_this_run": 0,
            "actual_orders_sent": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
