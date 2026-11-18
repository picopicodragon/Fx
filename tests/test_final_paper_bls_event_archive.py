"""BLS local ICS imports only recognized USD releases and never grants GO."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_bls_event_archive as importer
from research import final_paper_event_blackout as blackout
from research.offline_backtest import InputError

ASOF="2026-11-18T12:00:00Z"
NOW=datetime(2026,11,18,12,0,tzinfo=timezone.utc)


def raw(*,recognized=True):
    title="Consumer Price Index for October 2026" if recognized else (
        "Unknown Placeholder Non-FX Event")
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "DTSTART;TZID=America/New_York:20261118T083000\r\n"
        f"SUMMARY:{title}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n").encode()


class OfflineBlsPaperArchiveTests(unittest.TestCase):
    def test_converts_recognized_release_into_real_known_event_guard_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"bls.ics"
            file.write_bytes(raw())
            obj=importer.convert(file,asof_utc=ASOF)
            self.assertEqual(obj["selected_important_us_event_count"],1)
            self.assertFalse(obj["eur_jpy_events_included"])
            self.assertFalse(obj["calendar_coverage_independently_attested"])
            self.assertFalse(obj["real_orders_permitted"])
            target=Path(tmp)/"events.json"
            target.write_text(json.dumps(obj["known_event_calendar"]))
            status=blackout.check(
                target,int(datetime(2026,11,18,13,25,
                                    tzinfo=timezone.utc).timestamp()),
                now=NOW)
            self.assertTrue(status["active_known_blackout"])
            self.assertFalse(status["independent_calendar_coverage_attested"])

    def test_unrecognized_event_not_fabricated_as_critical(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"bls.ics"
            file.write_bytes(raw(recognized=False))
            result=importer.convert(file,asof_utc=ASOF)
            self.assertEqual(result["selected_important_us_event_count"],0)
            self.assertEqual(result["known_event_calendar"]["events"],[])
            self.assertFalse(result["calendar_coverage_independently_attested"])

    def test_missing_ics_and_bad_timezone_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            with self.assertRaises(InputError):
                importer.convert(folder/"absent.ics",asof_utc=ASOF)
            file=folder/"bls.ics"
            file.write_bytes(raw().replace(
                b"America/New_York",b"Mars/Base"))
            with self.assertRaises(InputError):
                importer.convert(file,asof_utc=ASOF)

    def test_import_never_does_network_provider_or_trading(self):
        source=(Path(__file__).resolve().parents[1]/
                "research/final_paper_bls_event_archive.py").read_text()
        for forbidden in ("OrderSend(", "OrderClose(", "urllib.request",
                          "OPENAI_API_KEY", "allow_external_api=True",
                          "ai.run(", "WebRequest("):
            self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
