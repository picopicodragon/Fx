"""D5-4 hypothetical yen/equity boundary tests only."""
import unittest
from scripts.p0_01_d5_4_synthetic_risk import evaluate_synthetic_limits as check


def fixture():
    return dict(origin="SYNTHETIC_ONLY", equity_jpy="100000",
                peak_equity_jpy="100000", single_trade_risk_jpy="500",
                aggregate_risk_jpy="1000", daily_loss_jpy="1499")

class SyntheticRiskTests(unittest.TestCase):
    def denied(self,r):
        self.assertEqual(r["phase_1"],"BLOCKED")
        for k in ("broker_verified","production_usable","orders_generated",
                  "terminal_execution_approved","forward_trading_enabled"):
            self.assertIs(r[k],False)

    def test_boundary_equal_trade_and_aggregate(self):
        r=check(fixture())
        self.assertEqual(r["status"],"SYNTHETIC_WITHIN_LIMITS_NEVER_AUTHORIZED")
        self.denied(r)

    def test_single_trade_over_boundary(self):
        f=fixture();f["single_trade_risk_jpy"]="500.01"
        self.assertEqual(check(f)["status"],"RISK_LIMIT_EXCEEDED")

    def test_aggregate_over_boundary(self):
        f=fixture();f["aggregate_risk_jpy"]="1000.01"
        self.assertEqual(check(f)["status"],"RISK_LIMIT_EXCEEDED")

    def test_daily_exact_threshold_stops(self):
        f=fixture();f["daily_loss_jpy"]="1500"
        self.assertEqual(check(f)["status"],"DAILY_STOP")

    def test_daily_over_threshold_stops(self):
        f=fixture();f["daily_loss_jpy"]="1500.01"
        self.assertEqual(check(f)["status"],"DAILY_STOP")

    def test_drawdown_exact_five_percent_stops(self):
        f=fixture();f["equity_jpy"]="95000";f["peak_equity_jpy"]="100000"
        self.assertEqual(check(f)["status"],"HARD_STOP_DD5")

    def test_drawdown_over_five_percent_stops(self):
        f=fixture();f["equity_jpy"]="94999"
        self.assertEqual(check(f)["status"],"HARD_STOP_DD5")

    def test_drawdown_below_five_percent_no_hard_stop(self):
        f=fixture();f["equity_jpy"]="95001"
        self.assertNotEqual(check(f)["status"],"HARD_STOP_DD5")

    def test_limit_scales_down_with_equity(self):
        f=fixture();f["equity_jpy"]="80000";f["peak_equity_jpy"]="80000";f["daily_loss_jpy"]="1199"
        # Daily loss must be below 1.5% of 80,000 (1,200) to isolate trade/aggregate caps.
        self.assertEqual(check(f)["status"],"RISK_LIMIT_EXCEEDED")
        f["single_trade_risk_jpy"]="400";f["aggregate_risk_jpy"]="800"
        self.assertEqual(check(f)["status"],"SYNTHETIC_WITHIN_LIMITS_NEVER_AUTHORIZED")

    def test_priority_drawdown_over_daily_over_trade(self):
        f=fixture();f["equity_jpy"]="95000";f["daily_loss_jpy"]="1500"
        self.assertEqual(check(f)["status"],"HARD_STOP_DD5")
        f["equity_jpy"]="100000"
        self.assertEqual(check(f)["status"],"DAILY_STOP")

    def test_invalid_missing_and_unknown_fields(self):
        for value in (None,{},[],True,"bad"):
            r=check(value);self.assertEqual(r["status"],"REVIEW_REQUIRED");self.denied(r)
        for k in ("equity_jpy","peak_equity_jpy","single_trade_risk_jpy"):
            f=fixture();f[k]=None
            self.assertEqual(check(f)["status"],"REVIEW_REQUIRED")
        f=fixture();f["grant_orders"]=True
        self.assertEqual(check(f)["status"],"REVIEW_REQUIRED")

    def test_non_decimal_tokens_and_peak_below_equity(self):
        for s in ("NaN","1e5","-1","inf","100,000"):
            f=fixture();f["equity_jpy"]=s
            self.assertEqual(check(f)["status"],"REVIEW_REQUIRED")
        f=fixture();f["peak_equity_jpy"]="99999"
        self.assertEqual(check(f)["status"],"REVIEW_REQUIRED")

    def test_no_secret_echo_or_approval(self):
        f=fixture();f["equity_jpy"]="SECRET_ACCOUNT_VALUE"
        r=check(f)
        self.assertNotIn("SECRET_ACCOUNT_VALUE",repr(r))
        self.denied(r)


if __name__=="__main__":
    unittest.main()
