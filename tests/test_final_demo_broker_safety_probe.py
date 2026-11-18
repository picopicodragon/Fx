"""Static safety contract for manual DEMO broker read-only script.

Only actual Rakuten MetaEditor compilation and demo terminal runtime can
validate MQL4 functionality; this prevents accidental trading APIs.
"""
from __future__ import annotations

import unittest
from pathlib import Path


class DemoBrokerSafetyProbeTests(unittest.TestCase):
    def test_readonly_probe_never_has_order_network_or_dll_calls(self):
        source=(Path(__file__).resolve().parents[1] /
                "mt4" / "read_only" /
                "FxFinalDemoBrokerSafetyProbe.mq4").read_text("utf-8")
        for item in (
            "#property strict", "void OnStart()",
            "IsDemo()", "IsConnected()",
            'Symbol() != "USDJPY"', "Period() != PERIOD_H1",
            'AccountCurrency() != "JPY"',
            'AccountNumber() <= 0', "OrdersTotal()",
            'FxDemoBrokerSafety_', "TimeGMT()", "TimeCurrent()",
            "MODE_TICKVALUE", "MODE_TICKSIZE", "MODE_LOTSTEP",
            "MODE_MINLOT", "MODE_MAXLOT", "MODE_STOPLEVEL",
            "MODE_FREEZELEVEL", "MODE_TRADEALLOWED",
            "tick_time_server_epoch_unattested",
            "broker_time_epoch_unattested",
            "pc_utc_epoch_unattested",
            "account_number", "equity_jpy_broker_reported",
            "FileFlush(f)", "NO_EXPORT"):
            self.assertIn(item, source)
        for forbidden in (
            "OrderSend(", "OrderClose(", "OrderModify(", "OrderDelete(",
            "WebRequest(", "#import ", "FILE_COMMON", "EventSetTimer(",
            "GlobalVariableSet(", "EnableDemoOrders = true",
            "IsExpertEnabled(", "SendNotification("):
            self.assertNotIn(forbidden, source)

    def test_local_runner_is_offline_and_produces_redacted_report(self):
        script=(Path(__file__).resolve().parents[1] /
                "scripts"/"final_demo_broker_safety_once.ps1").read_text("utf-8")
        for token in ("FxDemoBrokerSafety_", "final_demo_broker_contract_audit",
                      "--snapshot $copy --out $report",
                      "redacted_broker_terms_audit.json", "MQL4\\Files"):
            self.assertIn(token,script)
        for forbidden in ("-AllowPaidAi", "OrderSend(", "OrderModify(",
                          "OPENAI_API_KEY", "Invoke-WebRequest",
                          "EnableDemoOrders=true"):
            self.assertNotIn(forbidden,script)

    def test_probe_does_not_confuse_broker_values_with_independent_attestation(self):
        source=(Path(__file__).resolve().parents[1] /
                "mt4" / "read_only" /
                "FxFinalDemoBrokerSafetyProbe.mq4").read_text("utf-8")
        self.assertIn("NOT independent attestation", source)
        self.assertIn("account sensitive", source)
        self.assertIn("orders NOT authorized or placed", source)
        self.assertLess(source.index("for(int i=0; i<3; i++)"),
                        source.index("int f=FileOpen("))


if __name__=="__main__":
    unittest.main()
