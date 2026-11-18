"""Official-host URLs do not prove complete calendar or consensus coverage."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_event_coverage_audit as audit
from research import final_paper_event_blackout as events
from research.offline_backtest import InputError

NOW=datetime(2026,11,18,5,0,tzinfo=timezone.utc)


def events_file(folder:Path,currencies:tuple[str,...])->Path:
    obj={
        "schema":events.SCHEMA,
        "scope":"OPERATOR_SAVED_RESEARCH_ONLY",
        "captured_at_utc_pc":"2026-11-18T04:30:00Z",
        "events":[{
            "id":"synthetic_"+currency,
            "currency":currency,
            "scheduled_at_utc":"2026-11-18T05:05:00Z",
            "source_url":{
                "USD":"https://www.bls.gov/schedule/",
                "EUR":"https://www.ecb.europa.eu/press/",
                "JPY":"https://www.boj.or.jp/en/mopo/"
            }[currency],
            "importance":"CRITICAL",
        } for currency in currencies],
    }
    file=folder/"events.json"
    file.write_text(json.dumps(obj),encoding="utf-8")
    return file


class PaperMacroCoverageTests(unittest.TestCase):
    def test_missing_calendar_halts_with_all_three_currency_gaps(self):
        result=audit.audit(None,now=NOW)
        self.assertEqual(result["currencies_without_any_event_evidence"],
                         ["USD","EUR","JPY"])
        self.assertFalse(result["entry_or_paid_ai_activation_authorized"])

    def test_us_only_calendar_still_requires_eur_jpy(self):
        with tempfile.TemporaryDirectory() as temp:
            file=events_file(Path(temp),("USD",))
            result=audit.audit(file,now=NOW)
            self.assertEqual(result["locally_archived_event_count"],1)
            self.assertEqual(result["currencies_without_any_event_evidence"],
                             ["EUR","JPY"])
            self.assertFalse(result["all_important_events_covered"])
            self.assertFalse(result["consensus_captured_before_release"])

    def test_three_covered_currencies_still_do_not_prove_completeness(self):
        with tempfile.TemporaryDirectory() as temp:
            file=events_file(Path(temp),("USD","EUR","JPY"))
            result=audit.audit(file,now=NOW)
            self.assertEqual(result["locally_archived_event_count"],3)
            self.assertEqual(result["currencies_without_any_event_evidence"],[])
            self.assertTrue(result["known_blackout_active_now"])
            self.assertEqual(len(result["calendar_sha256_local_only"]),64)
            self.assertFalse(result["calendar_source_independently_attested"])
            self.assertFalse(result["all_important_events_covered"])
            self.assertFalse(result["entry_or_paid_ai_activation_authorized"])

    def test_untrusted_host_rejected_even_if_currency_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            file=events_file(Path(temp),("USD",))
            obj=json.loads(file.read_text())
            obj["events"][0]["source_url"]="https://example.com/bogus"
            file.write_text(json.dumps(obj))
            with self.assertRaises(InputError):
                audit.audit(file,now=NOW)

    def test_no_order_spend_and_no_network_in_readonly_audit(self):
        source=(Path(__file__).resolve().parents[1]/
                "research/final_paper_event_coverage_audit.py").read_text()
        for token in ("OrderSend(", "OrderClose(", "urllib.request",
                      "OPENAI_API_KEY", "allow_external_api=True",
                      "ai.run(", "_journal_append("):
            self.assertNotIn(token,source)


if __name__=="__main__":
    unittest.main()
