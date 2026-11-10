"""FWD-028..032: fail-closed Windows research intake and fault scenario tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_restart_receipts import (
    make_receipt, verify_receipt, main as receipt_main)
from research.forward_source_intake import evaluate as intake
from research.forward_shadow_campaign import audit as campaign
from research.offline_backtest import InputError


def mt4():
    return {
        "status": "MT4_READONLY_EXPORT_RESEARCH_NO_GO",
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False, "mt4_connected": False,
        "asof_utc": "2026-11-10T01:00:00Z",
        "missing_pairs": [], "file_evidence": [
            {"pair": p, "observed_at_utc": "2026-11-10T00:59:55Z",
             "source_sha256": "a" * 64,
             "source_status": "USER_SUPPLIED_UNVERIFIED"}
            for p in ("USD/JPY", "EUR/JPY", "EUR/USD")
        ],
    }


def cal(key="US_BLS"):
    domains = {"US_BLS": "www.bls.gov", "US_FED": "www.federalreserve.gov",
               "EU_ECB": "www.ecb.europa.eu", "JP_BOJ": "www.boj.or.jp"}
    return {
        "schema": "fx_forward_schedule_snapshot_v1", "source_key": key,
        "retrieved_at_utc": "2026-11-10T00:59:00Z",
        "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
        "runtime_go_no_go": "NO_GO",
        "real_orders_permitted": False,
        "source_authenticity_verified": False,
        "events": [{
            "title": "synthetic event",
            "source_url": "https://" + domains[key] + "/test",
            "scheduled_at_utc": "2026-11-11T01:00:00Z",
            "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
        }],
    }


def watch():
    return {
        "status": "FORWARD_SHADOW_WATCH_HOLD_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True, "real_orders_permitted": False,
        "watchdog_latched": False,
    }


def ledger(stage="COMPLETE", pending=None):
    return {
        "schema": "fx_forward_ai_shadow_v1",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True, "real_orders_permitted": False,
        "event_record_sha256": "1" * 64, "stage": stage,
        "pending_request": pending,
        "analyst": {"action": "HOLD"} if stage != "ANALYST_PENDING" else None,
        "reviewer": {"verdict": "PENDING"} if stage == "COMPLETE" else None,
    }


class RestartReceiptTests(unittest.TestCase):
    def test_first_and_second_receipt(self):
        a = make_receipt("a", "2026-11-10T01:00:00Z", "f" * 64)
        b = make_receipt("b", "2026-11-10T01:01:00Z", "e" * 64, a)
        verify_receipt(a)
        verify_receipt(b)
        self.assertEqual(b["sequence"], 2)
        self.assertEqual(b["previous_receipt_sha256"], a["receipt_sha256"])
        self.assertFalse(b["automated_restart_permitted"])
        self.assertFalse(b["real_orders_permitted"])

    def test_corruption_rejected(self):
        a = make_receipt("a", "2026-11-10T01:00:00Z", "f" * 64)
        a["cycle_id"] = "forged"
        with self.assertRaises(InputError):
            verify_receipt(a)

    def test_regression_and_duplicate_rejected(self):
        a = make_receipt("a", "2026-11-10T01:00:00Z", "f" * 64)
        for cid, time in (("a", "2026-11-10T01:01:00Z"),
                          ("b", "2026-11-10T01:00:00Z")):
            with self.assertRaises(InputError):
                make_receipt(cid, time, "e" * 64, a)

    def test_cli_rejects_go_report(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            (d / "report.json").write_text(json.dumps({
                "runtime_go_no_go": "GO",
                "safety_hold_latched": False,
                "real_orders_permitted": True}))
            out = d / "out.json"
            self.assertEqual(receipt_main([
                "--cycle-id", "a", "--asof-utc", "2026-11-10T01:00:00Z",
                "--report", str(d / "report.json"), "--out", str(out)]), 2)
            self.assertFalse(out.exists())


class SourceIntakeTests(unittest.TestCase):
    def test_three_pairs_four_central_bank_sources_never_certified(self):
        r = intake(mt4(), [cal(key) for key in
                   ("US_BLS", "US_FED", "EU_ECB", "JP_BOJ")])
        self.assertEqual(r["calendar_source_count"], 4)
        self.assertFalse(r["url_origin_cryptographically_verified"])
        self.assertFalse(r["real_orders_permitted"])

    def test_missing_source_holds(self):
        r = intake(mt4(), [])
        self.assertIn("CALENDAR_AUTHORITIES_INCOMPLETE", r["blocking_reasons"])

    def test_fake_domain_rejected(self):
        fake = cal()
        fake["events"][0]["source_url"] = "https://www.bls.gov.evil.test/event"
        with self.assertRaises(InputError):
            intake(mt4(), [fake])

    def test_url_credentials_rejected(self):
        fake = cal()
        fake["events"][0]["source_url"] = "https://admin@www.bls.gov/event"
        with self.assertRaises(InputError):
            intake(mt4(), [fake])

    def test_duplicate_tick_rejected(self):
        sample = mt4()
        sample["file_evidence"].append(copy.deepcopy(sample["file_evidence"][0]))
        with self.assertRaises(InputError):
            intake(sample, [])

    def test_fake_trade_rights_rejected(self):
        item = mt4()
        item["real_orders_permitted"] = True
        with self.assertRaises(InputError):
            intake(item, [])


class FaultCampaignTests(unittest.TestCase):
    def setUp(self):
        self.receipt = make_receipt("a", "2026-11-10T01:00:00Z", "f" * 64)
        self.intake = intake(mt4(), [])

    def test_completed_ledger_is_still_no_go(self):
        result = campaign([ledger()], watch(), self.intake, self.receipt)
        self.assertEqual(result["ai_completed"], 1)
        self.assertFalse(result["operational_long_duration_test_completed"])
        self.assertFalse(result["real_orders_permitted"])

    def test_pending_request_requires_reconciliation(self):
        result = campaign([ledger("REVIEW_PENDING", "reviewer")],
                          watch(), self.intake, self.receipt)
        self.assertIn("AMBIGUOUS_AI_REQUEST_REQUIRES_RECONCILIATION",
                      result["blocking_reasons"])

    def test_watchdog_latch_cannot_be_ignored(self):
        item = watch()
        item["watchdog_latched"] = True
        out = campaign([], item, self.intake, self.receipt)
        self.assertIn("WATCHDOG_STOP_LATCHED", out["blocking_reasons"])

    def test_duplicate_ai_event_rejected(self):
        with self.assertRaises(InputError):
            campaign([ledger(), ledger()], watch(), self.intake, self.receipt)

    def test_tampered_receipt_rejected(self):
        bad = copy.deepcopy(self.receipt)
        bad["report_sha256"] = "a" * 64
        with self.assertRaises(InputError):
            campaign([], watch(), self.intake, bad)


if __name__ == "__main__":
    unittest.main()
