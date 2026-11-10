"""FWD-014-016 deterministic multi-cycle research tests; never place orders."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_multicycle import SCHEMA, combine, from_manifest, main
from research.offline_backtest import InputError, PAIRS


def report(cid, time, count, pnl, risk="500", position=True):
    qa = {
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
        "status": "FORWARD_QUALITY_RESEARCH_ONLY_NO_GO",
        "asof_utc": time, "record_count": count,
        "source_authenticity_verified": False,
        "capture_clock_independently_verified": False,
        "full_economic_calendar_coverage_verified": False,
        "late_capture_sequences": [],
        "out_of_order_source_sequences": [],
        "current_asof_quote_freshness": {
            pair: {"quote_fresh": True} for pair in PAIRS},
    }
    paper = {
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False, "demo_order_execution_enabled": False,
        "mt4_connected": False,
        "status": "FORWARD_HYPOTHETICAL_PAPER_REPLAY_NO_GO",
        "asof_utc": time, "hypothetical_pnl_jpy": str(pnl),
        "hypothetical_position": {
            "pair": "USD/JPY", "direction": "LONG",
            "hypothesis_record_sha256": "a" * 64,
            "initial_risk_jpy": str(risk), "position_closed": False,
        } if position else None,
    }
    return {"cycle_id": cid, "quality": qa, "paper": paper,
            "quality_sha256": "1" * 64, "paper_sha256": "2" * 64}


class MultiCycleTests(unittest.TestCase):
    def setUp(self):
        self.a = report("cycle1", "2026-11-10T22:00:00Z", 8, "0")
        self.b = report("cycle2", "2026-11-10T22:01:00Z", 9, "150")
        self.c = report("cycle3", "2026-11-10T22:02:00Z", 10, "-100")

    def test_independent_full_replays_are_not_summed(self):
        out = combine([self.a, self.b, self.c])
        self.assertEqual(out["research_only_latest_hypothetical_pnl_jpy"], "-100")
        self.assertEqual(out["research_only_latest_hypothetical_equity_jpy"], "99900")
        self.assertEqual(out["pnl_aggregation"], "LATEST_INDEPENDENT_FULL_REPLAY_NOT_SUM")
        self.assertEqual(out["cycle_count"], 3)
        self.assertEqual(out["runtime_go_no_go"], "NO_GO")
        self.assertFalse(out["real_orders_permitted"])
        self.assertFalse(out["demo_order_execution_enabled"])

    def test_gap_is_hold_not_reconstructed_data(self):
        later = report("cycle2", "2026-11-10T22:30:00Z", 9, "5")
        out = combine([self.a, later])
        self.assertIn("CYCLE_GAP_EXCEEDED", out["blocking_reasons"])

    def test_rollback_refused(self):
        self.b["quality"]["record_count"] = 7
        with self.assertRaises(InputError):
            combine([self.a, self.b])

    def test_same_time_refused(self):
        self.b["quality"]["asof_utc"] = self.a["quality"]["asof_utc"]
        self.b["paper"]["asof_utc"] = self.a["quality"]["asof_utc"]
        with self.assertRaises(InputError):
            combine([self.a, self.b])

    def test_mixed_hypothesis_refused(self):
        self.b["paper"]["hypothetical_position"]["hypothesis_record_sha256"] = "b" * 64
        with self.assertRaises(InputError):
            combine([self.a, self.b])

    def test_fake_trade_authorization_refused(self):
        self.a["quality"]["real_orders_permitted"] = True
        with self.assertRaises(InputError):
            combine([self.a])

    def test_missing_quotes_hold(self):
        self.a["quality"]["current_asof_quote_freshness"]["EUR/USD"]["quote_fresh"] = False
        self.assertIn("UNFRESH_OR_MISSING_PAIR",
                      combine([self.a])["blocking_reasons"])

    def test_different_asof_refused(self):
        self.a["paper"]["asof_utc"] = "2026-11-10T22:10:00Z"
        with self.assertRaises(InputError):
            combine([self.a])

    def test_excess_risk_hold(self):
        self.a["paper"]["hypothetical_position"]["initial_risk_jpy"] = "501"
        self.assertIn("PAPER_SINGLE_TRADE_RISK_EXCEEDED",
                      combine([self.a])["blocking_reasons"])

    def test_untrusted_schema_rejected(self):
        self.a["quality"]["status"] = "LIVE_APPROVED"
        with self.assertRaises(InputError):
            combine([self.a])

    def test_identical_count_hold(self):
        self.b["quality"]["record_count"] = self.a["quality"]["record_count"]
        self.assertIn("NO_NEW_OBSERVATIONS",
                      combine([self.a, self.b])["blocking_reasons"])

    def test_nonfinite_pnl_rejected(self):
        for invalid in ("NaN", "Infinity", " 1", "", "1 "):
            with self.subTest(invalid=invalid):
                row = copy.deepcopy(self.a)
                row["paper"]["hypothetical_pnl_jpy"] = invalid
                with self.assertRaises(InputError):
                    combine([row])

    def test_paper_zero_without_position(self):
        row = report("empty", "2026-11-10T22:00:00Z", 0, "0", position=False)
        self.assertIn("NO_PAPER_POSITION", combine([row])["blocking_reasons"])
        row["paper"]["hypothetical_pnl_jpy"] = "1"
        with self.assertRaises(InputError):
            combine([row])

    def test_duplicate_cycle_refused(self):
        self.b["cycle_id"] = self.a["cycle_id"]
        with self.assertRaises(InputError):
            combine([self.a, self.b])

    def test_manifest_loads_exact_paths_and_hashes(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            row = self.a
            for kind in ("quality", "paper"):
                raw = json.dumps(row[kind]).encode()
                (d / ("cycle1_" + kind + ".json")).write_bytes(raw)
            manifest = {"schema": SCHEMA, "cycles": ["cycle1"]}
            loaded = from_manifest(manifest, d)
            self.assertEqual(loaded[0]["quality_sha256"],
                             hashlib.sha256((d / "cycle1_quality.json").read_bytes()).hexdigest())
            self.assertEqual(combine(loaded)["cycle_count"], 1)
            (d / "manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(main([
                "--manifest", str(d / "manifest.json"),
                "--reports-dir", str(d),
                "--out", str(d / "out.json"),
            ]), 0)
            self.assertEqual(main([
                "--manifest", str(d / "manifest.json"),
                "--reports-dir", str(d),
                "--out", str(d / "out.json"),
            ]), 2)

    def test_manifest_path_traversal_refused(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(InputError):
                from_manifest({"schema": SCHEMA, "cycles": ["../secret"]},
                              Path(root))

    def test_empty_manifest_refused(self):
        with self.assertRaises(InputError):
            combine([])


if __name__ == "__main__":
    unittest.main()
