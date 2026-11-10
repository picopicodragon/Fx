"""Offline safety contract tests for FWD-011/012."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.forward_evidence_gate import gate, main
from research.offline_backtest import InputError, PAIRS


NOW = "2026-11-10T01:00:00Z"


def quality(*, fresh=True):
    return {
        "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        "late_capture_sequences": [], "out_of_order_source_sequences": [],
        "capture_clock_independently_verified": False,
        "source_authenticity_verified": False, "data_license_verified": False,
        "full_economic_calendar_coverage_verified": False,
        "record_count": 0,
        "current_asof_quote_freshness": {
            p: {"quote_fresh": fresh, "quote_age_seconds": 10 if fresh else None,
                "event_blackout_observed": False}
            for p in PAIRS},
    }


def calendar(at=NOW, event=None):
    return {
        "status": "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "real_orders_permitted": False,
        "source_authenticity_verified": False,
        "calendar_covers_all_fx_events": False,
        "asof_utc": at, "events": [event] if event else [],
    }


def paper(risk="500"):
    return {
        "status": "FORWARD_HYPOTHETICAL_PAPER_REPLAY_NO_GO",
        "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        "demo_order_execution_enabled": False, "asof_utc": NOW,
        "hypothetical_position": {"pair": PAIRS[0],
                                  "initial_risk_jpy": risk},
    }


class TestEvidenceGate(unittest.TestCase):
    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_missing_calendar_paper_always_no_go(self, _qa):
        result = gate(Path("unused"), asof_utc=NOW)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertIn("FUTURE_SCHEDULE_MISSING", result["global_blocking_reasons"])
        self.assertIn("PAPER_EVIDENCE_MISSING", result["global_blocking_reasons"])
        self.assertEqual(set(result["by_pair"]), set(PAIRS))

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_perfect_looking_evidence_still_no_go(self, _qa):
        result = gate(Path("unused"), asof_utc=NOW,
                      calendar=calendar(), paper=paper())
        self.assertTrue(result["research_risk"]["single_trade_limit_respected_in_paper"])
        self.assertFalse(result["research_risk"]["portfolio_risk_certified"])
        self.assertIn("PORTFOLIO_DAILY_DD_NOT_CERTIFIED",
                      result["global_blocking_reasons"])
        self.assertTrue(all(not v["demo_order_eligible"] for v in
                            result["by_pair"].values()))

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_risk_exceedance_is_detected(self, _qa):
        result = gate(Path("unused"), asof_utc=NOW,
                      calendar=calendar(), paper=paper("500.01"))
        self.assertFalse(result["research_risk"]["single_trade_limit_respected_in_paper"])
        self.assertIn("HYPOTHETICAL_TRADE_RISK_EXCEEDED",
                      result["global_blocking_reasons"])

    @patch("research.forward_evidence_gate.quality_report", return_value=quality(fresh=False))
    def test_missing_quotes_block_each_pair(self, _qa):
        result = gate(Path("unused"), asof_utc=NOW)
        self.assertTrue(all("MISSING_OR_STALE_QUOTE" in
                            r["blocking_reasons"] for r in result["by_pair"].values()))

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_scheduled_bls_blackout_applies_all_pairs(self, _qa):
        event = {"source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
                 "source_url": "https://www.bls.gov/schedule/news_release/bls.ics",
                 "title": "CPI",
                 "scheduled_at_utc": "2026-11-10T01:10:00Z"}
        result = gate(Path("unused"), asof_utc=NOW, calendar=calendar(event=event))
        self.assertIn("BLS_SCHEDULED_EVENT_BLACKOUT",
                      result["global_blocking_reasons"])
        self.assertTrue(all("BLS_SCHEDULED_EVENT_BLACKOUT" in
                            r["blocking_reasons"] for r in result["by_pair"].values()))

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_stale_calendar_is_not_safe(self, _qa):
        result = gate(Path("unused"), asof_utc=NOW,
                      calendar=calendar("2026-11-08T00:00:00Z"))
        self.assertIn("SCHEDULE_STALE_OR_FUTURE", result["global_blocking_reasons"])

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_untrusted_calendar_rejected(self, _qa):
        data = calendar()
        data["real_orders_permitted"] = True
        with self.assertRaises(InputError):
            gate(Path("unused"), asof_utc=NOW, calendar=data)

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_fake_future_event_rejected(self, _qa):
        data = calendar(event={"title": "x", "source_status": "FAKE",
                               "source_url": "https://evil.test/x",
                               "scheduled_at_utc": NOW})
        with self.assertRaises(InputError):
            gate(Path("unused"), asof_utc=NOW, calendar=data)

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_invalid_money_rejected(self, _qa):
        with self.assertRaises(InputError):
            gate(Path("unused"), asof_utc=NOW, paper=paper("NaN"))

    @patch("research.forward_evidence_gate.quality_report", return_value=quality())
    def test_mismatched_report_time_rejected(self, _qa):
        data = paper()
        data["asof_utc"] = "2026-11-09T01:00:00Z"
        with self.assertRaises(InputError):
            gate(Path("unused"), asof_utc=NOW, paper=data)

    def test_cli_fail_closed_without_store_and_no_output(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "out.json"
            self.assertEqual(main(["--store", str(Path(root) / "missing"),
                                   "--out", str(out), "--asof-utc", NOW]), 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
