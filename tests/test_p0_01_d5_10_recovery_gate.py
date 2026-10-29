"""D5-10: fail-closed integration of D5-8 and D5-9 synthetic checks."""
import copy
import unittest

from scripts.p0_01_d5_10_recovery_gate import evaluate_synthetic_recovery_gate as check


def chain():
    return [
        dict(origin="SYNTHETIC_ONLY", schema_version=1,
             trading_day_start_ny_date="2026-07-01",
             daily_stop_latched=True, last_status="DAILY_STOP", sequence=10),
        dict(origin="SYNTHETIC_ONLY", schema_version=1,
             trading_day_start_ny_date="2026-07-02",
             daily_stop_latched=True, last_status="NEXT_DAY_REVIEW_PENDING", sequence=11),
    ]


class D510RecoveryGateTests(unittest.TestCase):
    def assert_denied(self, r):
        self.assertEqual(r["phase_1"], "BLOCKED")
        for field in ("broker_verified", "production_usable", "orders_generated",
                      "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(r[field], False)

    def assert_rejected(self, items, latest, day="2026-07-02", minimum=10):
        r = check(items, latest, day, minimum)
        self.assertEqual(r["status"], "INTEGRATION_REJECTED_FAIL_CLOSED")
        self.assertIs(r["daily_stop_latched"], True)
        self.assert_denied(r)

    def test_valid_stopped_history_remains_stopped(self):
        items = chain()
        r = check(items, items[-1], "2026-07-02", 10)
        self.assertEqual(r["status"], "INTEGRATED_STOP_LATCHED_SYNTHETIC_ONLY")
        self.assertIs(r["daily_stop_latched"], True)
        self.assert_denied(r)

    def test_valid_clean_snapshot_never_authorizes(self):
        item = chain()[0]
        item["daily_stop_latched"] = False
        item["last_status"] = "SYNTHETIC_MONITORING_ONLY"
        r = check([item], item, "2026-07-01", 10)
        self.assertEqual(r["status"], "INTEGRATED_CLEAN_NEVER_AUTHORIZED")
        self.assertIs(r["daily_stop_latched"], False)
        self.assert_denied(r)

    def test_missing_history_or_restore_rejected(self):
        items = chain()
        for bad in (None, [], "secret", {}):
            with self.subTest(bad=repr(bad)):
                self.assert_rejected(bad, items[-1])
        self.assert_rejected(items, None)

    def test_sequence_gap_rejected_even_if_latest_restores(self):
        items = chain()
        items[1]["sequence"] = 12
        self.assert_rejected(items, items[-1])

    def test_mismatched_latest_snapshot_rejected(self):
        items = chain()
        detached = copy.deepcopy(items[-1])
        detached["sequence"] = 12
        self.assert_rejected(items, detached)

    def test_stale_restore_rejected_even_if_chain_valid(self):
        items = chain()
        self.assert_rejected(items, items[-1], minimum=12)

    def test_stop_disappearance_rejected(self):
        items = chain()
        items[-1]["daily_stop_latched"] = False
        items[-1]["last_status"] = "SYNTHETIC_MONITORING_ONLY"
        self.assert_rejected(items, items[-1])

    def test_hard_stop_downgrade_rejected(self):
        items = chain()
        items[0]["last_status"] = "HARD_STOP_DD5"
        self.assert_rejected(items, items[-1])

    def test_corruption_or_wrong_day_rejected(self):
        items = chain()
        self.assert_rejected(items, items[-1], day="2026-07-01")
        items = chain()
        items[-1]["schema_version"] = 9
        self.assert_rejected(items, items[-1])

    def test_invalid_minimum_and_no_mutation(self):
        items = chain()
        before = copy.deepcopy(items)
        for minimum in (True, -1, "10", None):
            self.assert_rejected(items, items[-1], minimum=minimum)
        self.assertEqual(items, before)


if __name__ == "__main__":
    unittest.main()
