"""Pure offline Decimal/zoneinfo arithmetic for P0-01 hypothetical illustrations.

No brokerage, order path, production risk calculator, or approvals.
"""
import json
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
REPORT = "specs/p0_01_risk_snapshot_timing_numeric_examples.json"
D = Decimal


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class RiskSnapshotTimingNumericExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = read(REPORT)
        cls.examples = cls.record["numerical_examples"]

    def test_only_dd_monitor_release_has_approved_seconds_limit(self):
        checks = self.record["checks"]
        self.assertEqual(len(checks), 10)
        self.assertEqual({r["id"] for r in checks},
                         {f"TD-{i:02d}" for i in range(1, 11)})
        limited = [r for r in checks if r["allowed_max_age_seconds"] is not None]
        self.assertEqual(len(limited), 1)
        self.assertEqual(limited[0]["id"], "TD-09")
        self.assertEqual(limited[0]["allowed_max_age_seconds"], 15)
        self.assertIn("DD2/3", limited[0]["event"])
        for r in checks:
            self.assertTrue(r["required"])
            self.assertTrue(r["reason"])

    def test_source_references_and_distinct_account_data_evidence(self):
        for path in self.record["references"]:
            self.assertTrue((ROOT / path).is_file(), path)
        domains = {r["domain"] for r in self.record["checks"]}
        self.assertIn("FX_PRICES_AND_JPY_CONVERSION", domains)
        self.assertIn("CURRENT_EQUITY", domains)
        self.assertIn("NY17_DAY_OPEN_EQUITY", domains)
        self.assertIn("PENDING_AND_INFLIGHT", domains)
        self.assertIn("STOP_STATE_AND_CLOCK", domains)
        self.assertEqual(self.record["status"],
                         "HYPOTHETICAL_ILLUSTRATIONS_AND_DATA_CHECKLIST_ONLY")

    def test_preorder_illustrations_decimal_not_rounded_or_authorized(self):
        cases = self.examples["preorder"]
        self.assertEqual(len(cases), 5)
        verdicts = {
            "EX-RISK-01": "WITHIN_NUMERIC_LIMITS_ONLY",
            "EX-RISK-02": "COMBINED_EXCEEDED",
            "EX-RISK-03": "SINGLE_EXCEEDED",
            "EX-RISK-04": "AT_BOUNDARY_ONLY",
            "EX-RISK-05": "WITHIN_NUMERIC_LIMITS_ONLY",
        }
        self.assertEqual({c["id"] for c in cases}, set(verdicts))
        for c in cases:
            with self.subTest(c["id"]):
                equity = D(c["equity"])
                single = equity * D("0.005")
                combined = equity * D("0.01")
                exposure = sum((D(c[k]) for k in (
                    "existing_estimated_loss", "pending_estimated_loss",
                    "candidate_estimated_loss")), D("0"))
                self.assertEqual(single, D(c["single_limit"]))
                self.assertEqual(combined, D(c["combined_limit"]))
                self.assertEqual(exposure, D(c["combined_exposure"]))
                if D(c["candidate_estimated_loss"]) > single:
                    actual = "SINGLE_EXCEEDED"
                elif exposure > combined:
                    actual = "COMBINED_EXCEEDED"
                elif D(c["candidate_estimated_loss"]) == single or exposure == combined:
                    actual = "AT_BOUNDARY_ONLY"
                else:
                    actual = "WITHIN_NUMERIC_LIMITS_ONLY"
                self.assertEqual(actual, c["numeric_verdict"])
                self.assertEqual(actual, verdicts[c["id"]])

    def test_daily_cashflow_sign_and_fixed_equity_limit(self):
        cases = self.examples["daily"]
        self.assertEqual({c["id"] for c in cases},
                         {f"EX-DAY-{i:02d}" for i in range(1, 6)})
        expected = {
            "EX-DAY-01": "BELOW_FIXED_LIMIT",
            "EX-DAY-02": "LIMIT_EXCEEDED",
            "EX-DAY-03": "LIMIT_REACHED",
            "EX-DAY-04": "BELOW_FIXED_LIMIT",
            "EX-DAY-05": "BELOW_FIXED_LIMIT",
        }
        for c in cases:
            with self.subTest(c["id"]):
                start = D(c["day_open_equity"])
                net_flows = D(c["net_external_cash_inflow"])
                current = D(c["current_equity"])
                loss = start + net_flows - current
                limit = start * D("0.015")
                self.assertEqual(loss, D(c["illustrative_loss"]))
                self.assertEqual(limit, D(c["fixed_daily_limit"]))
                actual = (
                    "LIMIT_EXCEEDED" if loss > limit else
                    "LIMIT_REACHED" if loss == limit else
                    "BELOW_FIXED_LIMIT"
                )
                self.assertEqual(actual, c["numeric_verdict"])
                self.assertEqual(actual, expected[c["id"]])

    def test_day_limit_does_not_change_with_deposits(self):
        limits = {c["fixed_daily_limit"] for c in self.examples["daily"]}
        self.assertEqual(limits, {"1500"})
        cash = [D(c["net_external_cash_inflow"]) for c in self.examples["daily"]]
        self.assertIn(D("20000"), cash)
        self.assertIn(D("-10000"), cash)
        self.assertEqual(self.examples["daily"][2]["numeric_verdict"],
                         "LIMIT_REACHED")

    def test_unitized_drawdown_deposit_does_not_change_unit_price(self):
        d = self.examples["unitized_drawdown"]
        self.assertEqual(D(d["initial_equity"]) / D(d["initial_units"]),
                         D(d["initial_unit_value"]))
        hwm = D(d["initial_hwm"])
        before_price = D(d["predeposit_equity"]) / D(d["predeposit_units"])
        self.assertEqual(before_price, D(d["predeposit_unit_value"]))
        issued = D(d["external_deposit"]) / before_price
        self.assertEqual(issued, D(d["units_issued"]))
        units_after = D(d["predeposit_units"]) + issued
        equity_after = D(d["predeposit_equity"]) + D(d["external_deposit"])
        self.assertEqual(units_after, D(d["postdeposit_units"]))
        self.assertEqual(equity_after, D(d["postdeposit_equity"]))
        self.assertEqual(equity_after / units_after, before_price)
        dd_before = (D(1) - before_price / hwm) * 100
        dd_after = (D(1) - (equity_after / units_after) / hwm) * 100
        self.assertEqual(dd_before, D(d["predeposit_dd_pct"]))
        self.assertEqual(dd_after, D(d["postdeposit_dd_pct"]))
        recovery = D(d["illustrative_recovery_equity"]) / units_after
        self.assertEqual(recovery, D(d["illustrative_recovery_unit_value"]))
        self.assertEqual((D(1) - recovery / hwm) * 100,
                         D(d["illustrative_recovery_dd_pct"]))
        self.assertEqual(d["dd4_stop_latch_after_recovery"],
                         "REMAINS_UNTIL_EXPLICIT_HUMAN_CLEARANCE")

    def test_dd_release_candidate_is_strictly_below_threshold(self):
        examples = {c["id"]: c for c in self.examples["monitor_thresholds"]}
        self.assertEqual(set(examples),
                         {f"EX-MON-{i:02d}" for i in range(1, 5)})
        for key, threshold, attr in (
            ("EX-MON-01", D("1.5"), "dd2_below_1_5"),
            ("EX-MON-02", D("1.5"), "dd2_below_1_5"),
            ("EX-MON-03", D("2.5"), "dd3_below_2_5"),
            ("EX-MON-04", D("2.5"), "dd3_below_2_5"),
        ):
            self.assertEqual(D(examples[key]["dd_pct"]) < threshold,
                             examples[key][attr])
        self.assertFalse(examples["EX-MON-01"]["dd2_below_1_5"])
        self.assertFalse(examples["EX-MON-03"]["dd3_below_2_5"])

    def test_ny17_dst_converts_to_expected_jst(self):
        examples = self.examples["new_york_day_boundaries"]
        self.assertEqual(len(examples), 2)
        tz_ny = ZoneInfo("America/New_York")
        tz_jst = ZoneInfo("Asia/Tokyo")
        for case in examples:
            with self.subTest(case["id"]):
                dt_ny = datetime.fromisoformat(case["ny_local"]).replace(tzinfo=tz_ny)
                self.assertEqual(dt_ny.astimezone(tz_jst).isoformat(),
                                 case["jst"])
                self.assertEqual(dt_ny.hour, 17)
        self.assertEqual(examples[0]["id"], "EX-TIME-EDT")
        self.assertEqual(examples[1]["id"], "EX-TIME-EST")

    def test_neither_examples_nor_existing_drafts_authorize_orders(self):
        self.assertIs(self.record["review_examples_are_authorizations"], False)
        auth = self.record["safety_status"]
        for key in ("implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety", "forward_trading_enabled",
                    "live_orders_allowed"):
            self.assertIs(auth[key], False)
        self.assertEqual(auth["phase_1"], "BLOCKED")
        for ref in ("specs/p0_01_risk_data_consistency_draft.json",
                    "specs/p0_01_stop_reason_clearance_matrix_draft.json",
                    "specs/p0_01_closeout_retry_evidence_matrix_draft.json"):
            earlier = read(ref)
            self.assertEqual(earlier["safety_status" if "safety_status" in earlier
                                     else "safety_authorization"]["forward_trading_enabled"],
                             False)

    def test_approval_registries_preserve_blocked_status(self):
        registry = read("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        for rec in registry["items"]:
            self.assertIs(rec["implementation_approved"], False)
            self.assertIsNone(rec["owner_approval"])
        for rec in read("specs/source_review_priority.json")["items"]:
            self.assertEqual(rec["source_review"], "PENDING_ORIGINAL")
            self.assertIs(rec["human_safety_approval"], False)
        phase = next(p for p in read("specs/acceptance_registry.json")["phases"]
                     if p["id"] == "PHASE-1")
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
