"""Synthetic offline DEMO broker contract capture validation (no orders)."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_demo_broker_contract_audit as auditor
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 18, 0, 50, tzinfo=timezone.utc)


def make_snapshot(root: Path, *, orders: str = "0",
                  age: int = 15, quote_age: int = 1) -> Path:
    path=root/"FxDemoBrokerSafety_20261118_005000.csv"
    epoch=int(NOW.timestamp())-age
    for_now=int(NOW.timestamp())-20
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.writer(stream)
        writer.writerow(auditor.FIELDS)
        for sym,price,tickvalue in (("USDJPY",157.5,950.0),
                                     ("EURJPY",175.2,1000.0),
                                     ("EURUSD",1.1,1400.0)):
            writer.writerow([
                "DEMO","1234567","JPY","100000.00","100000.00",
                orders,str(epoch),str(for_now),sym,
                f"{price:.5f}",f"{price+0.005:.5f}",
                str(for_now-quote_age),str(tickvalue),"1.0",
                "0.01","0.01","100.0","20","10",
                "0.001","3","1"
            ])
    return path


class BrokerTermsAuditTests(unittest.TestCase):
    def test_valid_three_pair_contract_is_hard_no_go_and_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=make_snapshot(root)
            with patch("urllib.request.urlopen") as net:
                report=auditor.audit(source,now=NOW)
                net.assert_not_called()
            self.assertEqual(report["contract_count"],3)
            self.assertEqual(report["risk_budget_per_trade_jpy_0_5pct"],500)
            self.assertEqual(report["risk_budget_open_positions_jpy_1pct"],1000)
            self.assertEqual(report["risk_budget_daily_loss_jpy_1_5pct"],1500)
            self.assertEqual(report["drawdown_5pct_jpy_reference_only"],5000)
            self.assertEqual(report["status"],
                             "DEMO_BROKER_TERMS_OBSERVED_RESEARCH_HOLD_NO_GO")
            self.assertFalse(report["demo_orders_permitted"])
            self.assertFalse(report["real_orders_permitted"])
            self.assertNotIn("1234567",json.dumps(report))
            out=root/"audit.json"
            with patch.object(auditor,"audit",return_value=report):
                self.assertEqual(auditor.main([
                    "--snapshot",str(source),"--out",str(out)]),0)
            self.assertEqual(json.loads(out.read_text())["contract_count"],3)

    def test_stale_and_future_clock_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=make_snapshot(Path(tmp),age=601)
            with self.assertRaises(InputError):
                auditor.audit(source,now=NOW)
            source=make_snapshot(Path(tmp),age=-61)
            with self.assertRaises(InputError):
                auditor.audit(source,now=NOW)

    def test_preexisting_broker_order_blocks_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=make_snapshot(Path(tmp),orders="1")
            with self.assertRaises(InputError):
                auditor.audit(source,now=NOW)

    def test_quote_age_blocks_trade_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=make_snapshot(Path(tmp),quote_age=31)
            with self.assertRaises(InputError):
                auditor.audit(source,now=NOW)

    def test_pair_order_and_csv_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=make_snapshot(Path(tmp))
            lines=source.read_text().splitlines()
            source.write_text("\n".join(lines[:-1])+"\n")
            with self.assertRaises(InputError):
                auditor.audit(source,now=NOW)
            source=make_snapshot(Path(tmp))
            lines=source.read_text().splitlines()
            source.write_text("\n".join(lines[:1]+list(reversed(lines[1:])))+"\n")
            with self.assertRaises(InputError):
                auditor.audit(source,now=NOW)

    def test_report_does_not_independently_attest_broker_or_allow_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=auditor.audit(make_snapshot(Path(tmp)),now=NOW)
            self.assertFalse(result["broker_clock_independently_attested"])
            self.assertFalse(result["broker_identity_independently_attested"])
            self.assertFalse(result["risk_stop_order_lifecycle_verified"])
            self.assertFalse(result["tickvalue_conversion_verified"])
            self.assertFalse(result["terminal_trade_execution_verified"])

    def test_source_has_no_order_or_network_calls(self):
        files=("research/final_demo_broker_contract_audit.py",
               "mt4/read_only/FxFinalDemoBrokerSafetyProbe.mq4")
        base=Path(__file__).resolve().parents[1]
        for filename in files:
            source=(base/filename).read_text("utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                              "OrderDelete(", "WebRequest(", "#import ",
                              "EnableDemoOrders=true"):
                self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
