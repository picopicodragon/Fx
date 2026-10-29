"""D5-11: cross-stage fail-closed synthetic regression, no external side effects."""
import copy
import unittest

from scripts.p0_01_d5_4_synthetic_risk import evaluate_synthetic_limits as risk
from scripts.p0_01_d5_6_ny17_boundary import label_synthetic_ny17 as day
from scripts.p0_01_d5_7_daily_latch import evaluate_daily_latch as daily
from scripts.p0_01_d5_8_stop_restore import restore_synthetic_stop_state as restore
from scripts.p0_01_d5_9_snapshot_chain import audit_synthetic_snapshot_chain as chain_audit
from scripts.p0_01_d5_10_recovery_gate import evaluate_synthetic_recovery_gate as gate


def money():
    return dict(origin="SYNTHETIC_ONLY", equity_jpy="100000",
                peak_equity_jpy="100000", single_trade_risk_jpy="0",
                aggregate_risk_jpy="0", daily_loss_jpy="0")


def latch():
    return dict(origin="SYNTHETIC_ONLY", utc_timestamp="2026-07-01T21:00:00+00:00",
                previous_day_label="2026-06-30", previous_daily_stop=True,
                next_day_safety_checked=False, risk_fixture=money())


def records():
    return [
        dict(origin="SYNTHETIC_ONLY", schema_version=1,
             trading_day_start_ny_date="2026-06-30",
             daily_stop_latched=True, last_status="DAILY_STOP", sequence=20),
        dict(origin="SYNTHETIC_ONLY", schema_version=1,
             trading_day_start_ny_date="2026-07-01",
             daily_stop_latched=True, last_status="NEXT_DAY_REVIEW_PENDING", sequence=21),
    ]


class D511CrossFailureRegression(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["phase_1"], "BLOCKED")
        for field in ("broker_verified", "production_usable", "orders_generated",
                      "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(result[field], False)

    def rejected_gate(self, items):
        result = gate(items, items[-1], "2026-07-01", 20)
        self.assertEqual(result["status"], "INTEGRATION_REJECTED_FAIL_CLOSED")
        self.assertIs(result["daily_stop_latched"], True)
        self.denied(result)

    def test_corrupt_time_and_daily_cap(self):
        f = latch()
        f["utc_timestamp"] = "2026-07-01T21:00:00"
        f["risk_fixture"]["daily_loss_jpy"] = "1500"
        r = daily(f)
        self.assertEqual(r["status"], "REVIEW_REQUIRED")
        self.assertIs(r["daily_stop_latched"], True)
        self.denied(r)

    def test_invalid_risk_and_rollover(self):
        f = latch()
        f["next_day_safety_checked"] = True
        f["risk_fixture"]["equity_jpy"] = "0"
        r = daily(f)
        self.assertEqual(r["status"], "REVIEW_REQUIRED")
        self.assertIs(r["daily_stop_latched"], True)
        self.denied(r)

    def test_dd5_and_daily_cap_priority_after_rollover(self):
        f = latch()
        f["risk_fixture"]["equity_jpy"] = "95000"
        f["risk_fixture"]["daily_loss_jpy"] = "1500"
        r = daily(f)
        self.assertEqual(r["status"], "HARD_STOP_DD5")
        self.assertIs(r["daily_stop_latched"], True)
        self.denied(r)

    def test_checked_next_day_does_not_unlatch(self):
        f = latch()
        f["next_day_safety_checked"] = True
        r = daily(f)
        self.assertEqual(r["status"], "OFFLINE_REVIEW_ONLY_NEVER_AUTO_RESUME")
        self.assertIs(r["daily_stop_latched"], True)
        self.denied(r)

    def test_restoration_corruption_and_sequence_gap(self):
        items = records()
        items[-1]["sequence"] = 23
        items[-1]["schema_version"] = 2
        self.rejected_gate(items)

    def test_snapshot_rollback_and_stop_loss(self):
        items = records()
        items[-1]["sequence"] = 19
        items[-1]["daily_stop_latched"] = False
        items[-1]["last_status"] = "SYNTHETIC_MONITORING_ONLY"
        self.rejected_gate(items)

    def test_hard_stop_downgrade_and_corrupt_day(self):
        items = records()
        items[0]["last_status"] = "HARD_STOP_DD5"
        items[-1]["trading_day_start_ny_date"] = "2026-13-01"
        self.rejected_gate(items)

    def test_valid_chain_but_stale_restore(self):
        items = records()
        r = gate(items, items[-1], "2026-07-01", 22)
        self.assertEqual(r["status"], "INTEGRATION_REJECTED_FAIL_CLOSED")
        self.assertIs(r["daily_stop_latched"], True)
        self.denied(r)

    def test_multiple_independent_invalid_inputs(self):
        self.denied(risk(dict(money(), daily_loss_jpy="-1")))
        self.denied(day("2026-07-01T21:00:00"))
        self.denied(restore(None, "2026-07-01", True))
        self.denied(chain_audit([], "2026-02-30"))

    def test_no_inputs_mutated_by_cross_checks(self):
        f = latch()
        items = records()
        original_f, original_items = copy.deepcopy(f), copy.deepcopy(items)
        self.denied(daily(f))
        self.denied(gate(items, items[-1], "2026-07-01", 20))
        self.assertEqual(f, original_f)
        self.assertEqual(items, original_items)


if __name__ == "__main__":
    unittest.main()
