"""D5-5: zero/nonnegative risk values and malformed input fail-closed checks."""
import unittest
from scripts.p0_01_d5_4_synthetic_risk import evaluate_synthetic_limits as check

def base():
    return {"origin":"SYNTHETIC_ONLY", "equity_jpy":"100000",
            "peak_equity_jpy":"100000", "single_trade_risk_jpy":"0",
            "aggregate_risk_jpy":"0", "daily_loss_jpy":"0"}

class D55ZeroRiskTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["phase_1"],"BLOCKED")
        for key in ("broker_verified","production_usable","orders_generated",
                    "terminal_execution_approved","forward_trading_enabled"):
            self.assertIs(result[key],False)

    def test_all_zero_losses_are_valid_but_never_authorized(self):
        r=check(base())
        self.assertEqual(r["status"],"SYNTHETIC_WITHIN_LIMITS_NEVER_AUTHORIZED")
        self.denied(r)

    def test_each_zero_loss_field_is_accepted(self):
        for key in ("single_trade_risk_jpy","aggregate_risk_jpy","daily_loss_jpy"):
            x=base();x["single_trade_risk_jpy"]="500";x["aggregate_risk_jpy"]="1000";x["daily_loss_jpy"]="1499"
            x[key]="0"
            with self.subTest(key=key):
                self.assertEqual(check(x)["status"],"SYNTHETIC_WITHIN_LIMITS_NEVER_AUTHORIZED")

    def test_equity_and_peak_zero_are_rejected(self):
        for key in ("equity_jpy","peak_equity_jpy"):
            x=base();x[key]="0"
            with self.subTest(key=key):
                self.assertEqual(check(x)["status"],"REVIEW_REQUIRED")

    def test_missing_and_negative_losses_rejected(self):
        for key in ("single_trade_risk_jpy","aggregate_risk_jpy","daily_loss_jpy"):
            for bad in (None,"","-0.1","-0","-1"):
                x=base();x[key]=bad
                with self.subTest(key=key,bad=bad):
                    r=check(x)
                    self.assertEqual(r["status"],"REVIEW_REQUIRED")
                    self.denied(r)

    def test_bad_zero_representations_not_silently_coerced(self):
        for bad in (0,False,0.0,"+0"," 0 ","NaN","Infinity","1e-3"):
            x=base();x["daily_loss_jpy"]=bad
            with self.subTest(bad=repr(bad)):
                self.assertEqual(check(x)["status"],"REVIEW_REQUIRED")

    def test_zero_loss_does_not_override_risk_violation(self):
        x=base();x["single_trade_risk_jpy"]="500.01"
        self.assertEqual(check(x)["status"],"RISK_LIMIT_EXCEEDED")

    def test_daily_threshold_with_zero_trade_risk_still_stops(self):
        x=base();x["daily_loss_jpy"]="1500"
        self.assertEqual(check(x)["status"],"DAILY_STOP")

    def test_dd_threshold_with_zero_losses_still_stops(self):
        x=base();x["equity_jpy"]="95000"
        self.assertEqual(check(x)["status"],"HARD_STOP_DD5")

    def test_secret_or_extra_approval_key_denied(self):
        x=base();x["forward_trading_enabled"]=True
        r=check(x)
        self.assertEqual(r["status"],"REVIEW_REQUIRED")
        self.denied(r)

    def test_zero_does_not_change_other_stage_authority(self):
        from scripts.p0_01_offline_approval_gate import deny_all, invariant_holds
        r=deny_all("SYNTHETIC",base())
        self.assertTrue(invariant_holds(r))
        self.assertEqual(r["status"],"REVIEW_REQUIRED")

if __name__=="__main__":
    unittest.main()
