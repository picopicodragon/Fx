"""D5-7 date rollover and daily stop fail-closed integration tests."""
import unittest
from scripts.p0_01_d5_7_daily_latch import evaluate_daily_latch as check

def fixture():
    return {
        "origin": "SYNTHETIC_ONLY", "utc_timestamp": "2026-07-01T20:59:59+00:00",
        "previous_day_label": "2026-06-30", "previous_daily_stop": True,
        "next_day_safety_checked": False,
        "risk_fixture": {"origin":"SYNTHETIC_ONLY","equity_jpy":"100000",
                         "peak_equity_jpy":"100000","single_trade_risk_jpy":"0",
                         "aggregate_risk_jpy":"0","daily_loss_jpy":"0"}}

class D57DailyLatchTests(unittest.TestCase):
    def denied(self,r):
        self.assertEqual(r["phase_1"],"BLOCKED")
        for k in ("broker_verified","production_usable","orders_generated",
                  "terminal_execution_approved","forward_trading_enabled"):
            self.assertIs(r[k],False)

    def test_before_boundary_still_latched(self):
        r=check(fixture())
        self.assertEqual(r["status"],"DAILY_STOP_LATCHED")
        self.assertIs(r["daily_stop_latched"],True)
        self.denied(r)

    def test_after_boundary_requires_review(self):
        f=fixture();f["utc_timestamp"]="2026-07-01T21:00:00+00:00"
        r=check(f)
        self.assertEqual(r["status"],"NEXT_DAY_REVIEW_PENDING")
        self.denied(r)

    def test_checked_next_day_still_never_resumes(self):
        f=fixture();f["utc_timestamp"]="2026-07-01T21:00:00+00:00"
        f["next_day_safety_checked"]=True
        r=check(f)
        self.assertEqual(r["status"],"OFFLINE_REVIEW_ONLY_NEVER_AUTO_RESUME")
        self.assertIs(r["daily_stop_latched"],True)
        self.denied(r)

    def test_daily_threshold_stops(self):
        f=fixture();f["previous_daily_stop"]=False
        f["risk_fixture"]["daily_loss_jpy"]="1500"
        self.assertEqual(check(f)["status"],"DAILY_STOP")

    def test_dd_priority_over_daily(self):
        f=fixture();f["risk_fixture"]["equity_jpy"]="95000"
        f["risk_fixture"]["daily_loss_jpy"]="1500"
        self.assertEqual(check(f)["status"],"HARD_STOP_DD5")

    def test_next_day_check_cannot_override_exceeded_risk(self):
        f=fixture();f["utc_timestamp"]="2026-07-01T21:00:00+00:00"
        f["next_day_safety_checked"]=True
        f["risk_fixture"]["single_trade_risk_jpy"]="501"
        self.assertEqual(check(f)["status"],"NEXT_DAY_REVIEW_REQUIRED")

    def test_bad_time_fail_closed(self):
        f=fixture();f["utc_timestamp"]="2026-07-01T21:00:00"
        r=check(f)
        self.assertEqual(r["status"],"REVIEW_REQUIRED")
        self.assertIs(r["daily_stop_latched"],True)
        self.denied(r)

    def test_bad_state_and_injection_fail_closed(self):
        f=fixture();f["next_day_safety_checked"]="yes"
        self.assertEqual(check(f)["status"],"REVIEW_REQUIRED")
        f=fixture();f["forward_trading_enabled"]=True
        self.assertEqual(check(f)["status"],"REVIEW_REQUIRED")

    def test_winter_rollover(self):
        f=fixture();f["previous_day_label"]="2026-01-14"
        f["utc_timestamp"]="2026-01-15T21:59:59+00:00"
        self.assertEqual(check(f)["status"],"DAILY_STOP_LATCHED")
        f["utc_timestamp"]="2026-01-15T22:00:00+00:00"
        self.assertEqual(check(f)["status"],"NEXT_DAY_REVIEW_PENDING")

    def test_not_stopped_still_not_authorized(self):
        f=fixture();f["previous_daily_stop"]=False
        r=check(f)
        self.assertEqual(r["status"],"SYNTHETIC_MONITORING_ONLY")
        self.denied(r)

if __name__=="__main__":
    unittest.main()
