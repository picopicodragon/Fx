"""Offline source-hash, point-in-time and monthly JPY envelope tests."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research import final_paper_point_in_time_evidence as pit
from research import final_paper_api_cost_envelope as envelope
from research.offline_backtest import InputError


def cost():
    return {
        "schema": envelope.SCHEMA,
        "first_model": "gpt-6.1-sol",
        "second_model": "gpt-6-astra",
        "usd_jpy_ceiling": "160",
        "monthly_billed_jpy_operator_reported": "1000.00",
        "first_input_usd_per_million": "12.00",
        "first_output_usd_per_million": "50",
        "second_input_usd_per_million": "12",
        "second_output_usd_per_million": "50",
        "first_input_tokens_cap": 6000,
        "first_output_tokens_cap": 3000,
        "second_input_tokens_cap": 6000,
        "second_output_tokens_cap": 3000,
        "provider_prices_independently_attested": False,
        "exchange_ceiling_independently_attested": False,
        "provider_billing_independently_attested": False,
    }


class OfflineEvidenceReadinessTests(unittest.TestCase):
    def test_cost_envelope_rounded_worst_case_and_no_paid_permission(self):
        item = envelope.estimate(cost())
        self.assertTrue(item["arithmetic_fits_3000_jpy"])
        self.assertFalse(item["new_paid_ai_calls_permitted"])
        self.assertFalse(item["actual_api_cost_guarantee"])
        blocked = cost()
        blocked["monthly_billed_jpy_operator_reported"] = "2950"
        item = envelope.estimate(blocked)
        self.assertFalse(item["arithmetic_fits_3000_jpy"])

    def test_cost_strict_limits_and_provenance_not_spoofed(self):
        for key, value in (
            ("first_input_tokens_cap", 1_000_001),
            ("second_output_tokens_cap", 0),
            ("usd_jpy_ceiling", "-1"),
            ("first_model", "gpt-6-astra"),
            ("provider_prices_independently_attested", True),
        ):
            with self.subTest(key=key):
                item = cost()
                item[key] = value
                with self.assertRaises(InputError):
                    envelope.estimate(item)

    def test_hash_archive_accepts_pre_release_bytes_but_never_authenticates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            a=root/"official.html"
            b=root/"consensus.txt"
            a.write_text("release published source snapshot",encoding="utf-8")
            b.write_text("forecast 2.4%",encoding="utf-8")
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            event={
                "id":"fixture-usd-event","currency":"USD",
                "release_at_utc":"2026-11-20T15:00:00Z",
                "official_source_url":"https://www.bls.gov/schedule/news_release/",
                "official_file":"official.html","official_sha256":sha(a),
                "official_captured_at_utc_pc":"2026-11-19T08:00:00Z",
                "consensus_source_url":"https://www.reuters.com/markets/",
                "consensus_file":"consensus.txt","consensus_sha256":sha(b),
                "consensus_captured_at_utc_pc":"2026-11-19T08:00:00Z",
            }
            manifest=root/"evidence.json"
            manifest.write_text(json.dumps({
                "schema":pit.SCHEMA,"events":[event]
            }),encoding="utf-8")
            reviewed=pit.audit(root,manifest)
            self.assertEqual(reviewed["locally_matched_event_count"],1)
            self.assertEqual(reviewed["source_currencies_missing"],["EUR","JPY"])
            self.assertFalse(reviewed["full_future_calendar_coverage_attested"])
            self.assertFalse(reviewed["live_virtual_entry_permitted"])
            b.write_text("changed!",encoding="utf-8")
            with self.assertRaises(InputError):
                pit.audit(root,manifest)

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(InputError):
                pit._sha(root,"../outside","a"*64)

    def test_no_order_or_live_dispatch_in_evidence_modules(self):
        base=Path(__file__).resolve().parents[1]
        for path in (
            "research/final_paper_api_cost_envelope.py",
            "research/final_paper_point_in_time_evidence.py",
        ):
            src=(base/path).read_text("utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                              "WebRequest(", "ai.run(", "OPENAI_API_KEY",
                              "urllib.request", "lock.unlink("):
                self.assertNotIn(forbidden, src)


if __name__=="__main__":
    unittest.main()
