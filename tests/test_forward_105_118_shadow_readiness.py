"""FWD-105..118 quote-quality and shadow-veto offline regressions."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from research.forward_shadow_quote_quality import (
    inspect as inspect_quality, main as quality_main
)
from research.forward_shadow_candidate_veto import (
    inspect as inspect_veto, main as veto_main
)
from research.offline_backtest import InputError
from research.forward_mt4_v2_quote import COLUMNS

ASOF = "2026-11-10T07:00:00Z"
PAIRS = {"USDJPY": "USD/JPY", "EURJPY": "EUR/JPY",
         "EURUSD": "EUR/USD"}


def session(root: Path, name: str, start_minute=0, count=2,
            *, wide=False) -> Path:
    folder = root / name
    folder.mkdir()
    start = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
    for minute in range(start_minute, start_minute+count):
        moment = start+timedelta(minutes=minute)
        stamp = moment.strftime("%Y%m%d_%H%M%S")
        obs = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        for symbol, pair in PAIRS.items():
            bid = ("150.000" if symbol != "EURUSD" else "1.12000")
            ask = ("150.060" if wide else "150.005") if symbol != "EURUSD" else (
                "1.12100" if wide else "1.12005")
            conversion = "150.00000" if symbol == "EURUSD" else "1.00000"
            fields = [obs,pair,bid,ask,conversion,
                      "2026-11-10T08:00:00","2026-11-10T08:00:05",
                      "5","DEMO","MANUAL_MT4_DEMO_V2_UNVERIFIED"]
            (folder/f"FxFwdV3_{symbol}_{stamp}.csv").write_text(
                ",".join(COLUMNS)+"\n"+",".join(fields)+"\n",encoding="utf-8")
    return folder


def candidate(**kwargs):
    c = {
        "pair": "USD/JPY", "side": "LONG",
        "equity_jpy": "100000", "units": "1000",
        "stop_distance_pips": "20",
        "current_total_risk_jpy": "0",
        "daily_loss_jpy": "0", "drawdown_percent": "0",
        "scenario_label": "synthetic-no-orders",
    }
    c.update(kwargs)
    return c


class FwdShadowReadinessTests(unittest.TestCase):
    def test_pair_quality_counts_and_pip_spreads(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            r=inspect_quality([("s",folder)],asof_utc=ASOF)
            self.assertEqual(r["files"],6)
            self.assertEqual(r["cycle_count"],2)
            self.assertEqual(r["pair_statistics"]["USD/JPY"]["quotes"],2)
            self.assertEqual(r["pair_statistics"]["USD/JPY"]["spread_max_pips"],"0.5")
            self.assertEqual(r["pair_statistics"]["EUR/USD"]["spread_max_pips"],"0.5")
            self.assertFalse(r["real_orders_permitted"])

    def test_wide_spread_is_flagged(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session",wide=True)
            r=inspect_quality([("s",folder)],asof_utc=ASOF)
            self.assertIn("SPREAD_ABOVE_RESEARCH_REVIEW_THRESHOLD",
                          r["data_quality_alerts_and_safety_holds"])

    def test_quality_over_two_sessions(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            a=session(root,"first",0,2)
            b=session(root,"second",8,3)
            r=inspect_quality([("a",a),("b",b)],asof_utc=ASOF)
            self.assertEqual(r["files"],15)
            self.assertEqual(r["pair_statistics"]["EUR/JPY"]["quotes"],5)
            self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_candidate_small_scenario_always_veto(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            r=inspect_veto([("s",folder)],asof_utc=ASOF,candidate=candidate())
            self.assertEqual(r["scenario_stop_loss_risk_jpy"],"200.00")
            self.assertEqual(r["simulated_fills_created"],0)
            self.assertEqual(r["actual_positions_created"],0)
            self.assertIn("NO_VERIFIED_MACRO_HYPOTHESIS",
                          r["scenario_violations_and_holds"])
            self.assertFalse(r["demo_orders_permitted"])

    def test_per_trade_limit_veto(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            r=inspect_veto([("s",folder)],asof_utc=ASOF,
                           candidate=candidate(units="3000"))
            self.assertIn("PER_CANDIDATE_RISK_ABOVE_0_5_PERCENT",
                          r["scenario_violations_and_holds"])

    def test_total_limit_veto(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            r=inspect_veto([("s",folder)],asof_utc=ASOF,
                           candidate=candidate(current_total_risk_jpy="900"))
            self.assertIn("AGGREGATE_RISK_ABOVE_1_PERCENT",
                          r["scenario_violations_and_holds"])

    def test_daily_halt_and_drawdown_veto(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            r=inspect_veto([("s",folder)],asof_utc=ASOF,
                           candidate=candidate(daily_loss_jpy="1500",
                                               drawdown_percent="5"))
            holds=r["scenario_violations_and_holds"]
            self.assertIn("DAILY_LOSS_1_5_PERCENT_HALT",holds)
            self.assertIn("DD_4_PERCENT_NEW_ENTRIES_HALTED",holds)
            self.assertIn("DD_5_PERCENT_HUMAN_APPROVAL_REQUIRED",holds)

    def test_eurusd_uses_conservative_usdjpy_ask(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            r=inspect_veto([("s",folder)],asof_utc=ASOF,
                           candidate=candidate(pair="EUR/USD",
                                               stop_distance_pips="20"))
            self.assertEqual(r["notional_risk_conversion_research_only"],
                             "150.005")
            self.assertEqual(r["scenario_stop_loss_risk_jpy"],
                             "300.0100000")

    def test_invalid_extra_field_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            with self.assertRaises(InputError):
                inspect_veto([("s",folder)],asof_utc=ASOF,
                             candidate=candidate(order_send=True))

    def test_invalid_pair_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            with self.assertRaises(InputError):
                inspect_veto([("s",folder)],asof_utc=ASOF,
                             candidate=candidate(pair="GBP/USD"))

    def test_invalid_decimal_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            folder=session(Path(t),"session")
            with self.assertRaises(InputError):
                inspect_veto([("s",folder)],asof_utc=ASOF,
                             candidate=candidate(units="nan"))

    def test_quality_cli_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            folder=session(root,"session")
            out=root/"quality.json"
            args=["--session",f"s={folder}","--asof-utc",ASOF,
                  "--out",str(out)]
            self.assertEqual(quality_main(args),0)
            self.assertEqual(quality_main(args),2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])

    def test_candidate_cli_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            folder=session(root,"session")
            input_path=root/"candidate.json"
            input_path.write_text(json.dumps(candidate()))
            out=root/"veto.json"
            args=["--session",f"s={folder}","--candidate",str(input_path),
                  "--asof-utc",ASOF,"--out",str(out)]
            self.assertEqual(veto_main(args),0)
            self.assertEqual(veto_main(args),2)
            self.assertEqual(json.loads(out.read_text())["runtime_go_no_go"],
                             "NO_GO")

    def test_candidate_cli_rejects_output_in_evidence_directory(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            folder=session(root,"session")
            input_path=root/"candidate.json"
            input_path.write_text(json.dumps(candidate()))
            out=folder/"bad.json"
            args=["--session",f"s={folder}","--candidate",str(input_path),
                  "--asof-utc",ASOF,"--out",str(out)]
            self.assertEqual(veto_main(args),2)
            self.assertFalse(out.exists())


if __name__=="__main__":
    unittest.main()
