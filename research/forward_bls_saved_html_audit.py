"""FWD-345..360: offline actual saved BLS HTML vs saved ICS comparison.

Reads verified same-capture bundle only, never the manually transcribed
reference. An HTML table parse is provisional, not publisher authentication.
No network, files written, AI, MT4, brokers, orders or safety-gate change.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from research import forward_bls_calendar_crosscheck as previous
from research import forward_bls_dual_snapshot as snapshot
from research import forward_bls_snapshot_diff as integrity
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_bls_saved_html_ics_audit_v1"
ET = ZoneInfo("America/New_York")
DATE_FORMAT = re.compile(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), (November) (0?[1-9]|[12][0-9]|30), 2026\Z")
TIME_FORMAT = re.compile(r"(0?[1-9]|1[0-2]):([0-5][0-9]) (AM|PM)\Z")
HOLIDAYS = frozenset(("Veterans Day", "Thanksgiving Day"))
MAX_TITLES_PER_SLOT = 12
MAX_DISPUTED_SLOTS = 12


def _tidy(text: str) -> str:
    return " ".join(text.split())


class _TableRows(HTMLParser):
    """Extract table rows at *every* nesting depth, not just layout tables.

    The public BLS page can use a two-column layout table which contains
    another Date/Time/Release table. Do not treat outer layout-cell text as
    the schedule itself. Only a unique exact 3-column header is eligible.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.stack: list[dict] = []
        self.depth = 0
        self.invalid_structure = False

    def handle_starttag(self, tag: str, attrs):
        if tag == "table":
            if len(self.stack) >= 20:
                self.invalid_structure = True
                return
            self.stack.append({"rows": [], "row": None, "cell": None})
            self.depth = len(self.stack)
            return
        if not self.stack:
            return
        table = self.stack[-1]
        if tag == "tr":
            if table["row"] is not None:
                self.invalid_structure = True
            table["row"] = []
        elif tag in ("td", "th"):
            if table["row"] is not None:
                if table["cell"] is not None:
                    self.invalid_structure = True
                table["cell"] = []

    def handle_data(self, data: str):
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"].append(data)

    def handle_endtag(self, tag: str):
        if tag == "table":
            if not self.stack:
                self.invalid_structure = True
                return
            item = self.stack.pop()
            if item["row"] is not None or item["cell"] is not None:
                self.invalid_structure = True
            self.tables.append(item["rows"])
            self.depth = len(self.stack)
            return
        if not self.stack:
            return
        item = self.stack[-1]
        if tag in ("td", "th") and item["cell"] is not None:
            if item["row"] is None:
                self.invalid_structure = True
            else:
                item["row"].append(_tidy("".join(item["cell"])))
            item["cell"] = None
        elif tag == "tr" and item["row"] is not None:
            if item["cell"] is not None:
                self.invalid_structure = True
            item["rows"].append(item["row"])
            item["row"] = None



def _release_rows(raw_html: bytes) -> list[tuple[str, str]]:
    snapshot._validate_html(raw_html)
    try:
        data = raw_html.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("invalid HTML character encoding") from exc
    parser = _TableRows()
    parser.feed(data)
    parser.close()
    if parser.depth != 0 or parser.invalid_structure:
        raise InputError("incomplete or malformed HTML table")
    candidates = []
    for table in parser.tables:
        header_index = next((
            i for i, row in enumerate(table)
            if len(row) == 3
            and tuple(v.casefold() for v in row) == (
                "date", "time", "release")
        ), None)
        if header_index is not None:
            candidates.append(table[header_index + 1:])
    if len(candidates) != 1:
        raise InputError("BLS dated release table absent or ambiguous")
    rows = candidates[0]
    if not 5 <= len(rows) <= 100:
        raise InputError("unexpected BLS release row count")
    extracted = []
    for row in rows:
        if len(row) != 3:
            raise InputError("unexpected BLS release cell count")
        date, clock, title = row
        match = DATE_FORMAT.fullmatch(date)
        if not match:
            raise InputError("unexpected BLS release date format")
        local_day = datetime.strptime(date, "%A, %B %d, %Y")
        if local_day.strftime("%A") != match.group(1):
            raise InputError("invalid BLS release weekday")
        if not clock:
            if title not in HOLIDAYS:
                raise InputError("unexpected untimed BLS release")
            continue
        if not TIME_FORMAT.fullmatch(clock):
            raise InputError("unexpected BLS release time format")
        if not 1 <= len(title) <= 250 or not title.strip():
            raise InputError("invalid BLS release title")
        local_time = datetime.strptime(clock, "%I:%M %p").time()
        when = datetime.combine(local_day.date(), local_time)
        # Reuse existing fail-closed NY DST handling.
        aware = when.replace(tzinfo=ET)
        roundtrip = aware.astimezone(previous.timezone.utc).astimezone(ET)
        if roundtrip.replace(tzinfo=None) != when:
            raise InputError("nonexistent release wall time")
        if when.replace(tzinfo=ET, fold=1).utcoffset() != aware.utcoffset():
            raise InputError("ambiguous release wall time")
        utc = aware.astimezone(previous.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        extracted.append((utc, title))
    if not 5 <= len(extracted) <= 100:
        raise InputError("unexpected BLS released-item count")
    return extracted


def inspect(saved_bundle: Path) -> dict:
    manifest = integrity.verify(saved_bundle)
    with (saved_bundle / snapshot.CAL_NAME).open("r", encoding="utf-8") as source:
        calendar = json.load(source)
    lower, end, ics_slots = previous._validate_calendar(calendar)
    if (lower.astimezone(ET).strftime("%Y-%m") != "2026-11"
            or end.astimezone(ET).strftime("%Y-%m") != "2026-11"):
        raise InputError("HTML month does not cover calendar horizon")
    raw = integrity._bytes(saved_bundle, snapshot.HTML_NAME,
                           snapshot.HTML_MAX_BYTES)
    rows = _release_rows(raw)
    html_events = [(t, name) for t, name in rows
                   if lower <= previous._utc(t) <= end]
    html_slots: Counter[str] = Counter(t for t, _ in html_events)
    missing = html_slots - ics_slots
    unexpected = ics_slots - html_slots
    evidence = []
    disputed = sorted(set(missing) | set(unexpected))
    for slot in disputed[:MAX_DISPUTED_SLOTS]:
        ics_names = sorted(e["title"] for e in calendar["events"]
                           if e["scheduled_at_utc"] == slot)
        html_names = sorted(name for t, name in html_events if t == slot)
        evidence.append({
            "scheduled_at_utc": slot,
            "ics_title_count": len(ics_names),
            "html_title_count": len(html_names),
            "ics_titles_unverified": ics_names[:MAX_TITLES_PER_SLOT],
            "html_titles_unverified": html_names[:MAX_TITLES_PER_SLOT],
            "ics_title_omission_count": max(0, len(ics_names)-MAX_TITLES_PER_SLOT),
            "html_title_omission_count": max(0, len(html_names)-MAX_TITLES_PER_SLOT),
            "release_family_candidate_review":
                previous._family_correspondence_for_review(
                    ics_names, html_names),
            "missing_event_identity_verified": False,
            "auto_backfill_allowed": False,
        })
    return {
        "schema": SCHEMA,
        "status": "BLS_SAVED_HTML_ICS_AUDIT_HOLD_NO_GO",
        "comparison": (
            "SAVED_HTML_ICS_SLOT_COUNTS_MATCH_UNVERIFIED"
            if not missing and not unexpected
            else "SAVED_HTML_ICS_SLOT_COUNTS_DISAGREE"),
        "same_local_bundle_integrity_consistent": True,
        "html_table_parse_is_provisional": True,
        "html_source_sha256": manifest["html_sha256"],
        "ics_source_sha256": manifest["ics_sha256"],
        "local_ics_capture_clock_unattested":
            manifest["ics_observed_at_utc_local_clock_unattested"],
        "local_html_capture_clock_unattested":
            manifest["html_observed_at_utc_local_clock_unattested"],
        "calendar_asof_utc": calendar["asof_utc"],
        "ics_event_count": sum(ics_slots.values()),
        "html_event_count_within_window": sum(html_slots.values()),
        "html_month_selected_release_item_count": len(rows),
        "matched_slot_instance_count": sum((ics_slots & html_slots).values()),
        "missing_html_slot_instance_count": sum(missing.values()),
        "unexpected_ics_slot_instance_count": sum(unexpected.values()),
        "disputed_slot_title_evidence": evidence,
        "disputed_slots_omitted_count": max(0, len(disputed)-MAX_DISPUTED_SLOTS),
        "missing_events_automatically_added": False,
        "titles_or_event_identity_authenticated": False,
        "publication_timing_independently_verified": False,
        "source_authenticity_independently_verified": False,
        "sources_independent_publishers": False,
        "complete_fx_macro_calendar_coverage": False,
        "consensus_evidence_captured": False,
        "files_written_this_run": 0,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offline verify and compare saved real BLS HTML/ICS")
    p.add_argument("--snapshot-dir", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        result = inspect(args.snapshot_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "BLS_SAVED_HTML_ICS_AUDIT_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_BUNDLE_OR_UNSUPPORTED_HTML_STRUCTURE",
            "files_written_this_run": 0,
            "network_calls_this_run": 0,
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
