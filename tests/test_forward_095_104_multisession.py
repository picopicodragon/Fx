"""FWD-095..104 multi-session observation audit regressions."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.forward_mt4_multisession_reliability import inspect, main
from research.forward_mt4_v2_quote import COLUMNS
from research.offline_backtest import InputError

ASOF = "2026-11-10T09:00:00Z"
PAIRS = {"USDJPY": "USD/JPY", "EURJPY": "EUR/JPY", "EURUSD": "EUR/USD"}


def make_session(root: Path, label: str, start_minute: int,
                 count: int, *, missing_pair: str | None = None) -> Path:
    folder = root / label
    folder.mkdir()
    beginning = datetime(2026, 11, 10, 6, 0, 0, tzinfo=timezone.utc)
    for offset in range(count):
        moment = beginning + timedelta(minutes=start_minute+offset)
        stamp = moment.strftime("%Y%m%d_%H%M%S")
        when = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        for symbol, pair in PAIRS.items():
            if symbol == missing_pair:
                continue
            values = (
                when, pair, "150.000", "150.005",
                "150.00000" if symbol == "EURUSD" else "1.00000",
                "2026-11-10T08:00:00", "2026-11-10T08:00:05", "5",
                "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED")
            (folder / f"FxFwdV3_{symbol}_{stamp}.csv").write_text(
                ",".join(COLUMNS)+"\n"+",".join(values)+"\n", encoding="utf-8")
    return folder


class MultiSessionDemoReliabilityTests(unittest.TestCase):
    def test_8_and_30_cycles_are_two_sessions_114_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a = make_session(root, "session001", 0, 8)
            b = make_session(root, "session002", 15, 30)
            result = inspect([("s1",a),("s2",b)], asof_utc=ASOF)
            self.assertEqual(result["session_count"], 2)
            self.assertEqual(result["csv_file_count"], 114)
            self.assertEqual(result["complete_cycle_count"], 38)
            self.assertEqual(result["incomplete_cycle_count"], 0)
            self.assertEqual(result["between_session_boundaries"][0]
                             ["between_sessions_seconds"], 480)
            self.assertNotIn("CSV_REPLAY_ACROSS_SESSIONS",
                             result["issues_and_safety_holds"])
            self.assertFalse(result["real_orders_permitted"])

    def test_session_order_is_data_driven_not_cli_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,2)
            b=make_session(root,"two",12,2)
            result=inspect([("later",b),("earlier",a)],asof_utc=ASOF)
            self.assertEqual(result["between_session_boundaries"][0]
                             ["earlier_label"],"earlier")

    def test_overlap_detected_not_mistaken_for_continuity(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,8)
            b=make_session(root,"two",6,8)
            result=inspect([("first",a),("second",b)],asof_utc=ASOF)
            self.assertIn("OVERLAPPING_SESSION_OBSERVATION_WINDOWS",
                          result["issues_and_safety_holds"])

    def test_cross_session_csv_replay_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            b=make_session(root,"two",0,1)
            report=inspect([("first",a),("replay",b)],asof_utc=ASOF)
            self.assertIn("CSV_REPLAY_ACROSS_SESSIONS",
                          report["issues_and_safety_holds"])
            self.assertFalse(report["real_orders_permitted"])

    def test_missing_pair_in_second_session_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,2)
            b=make_session(root,"two",10,2,missing_pair="EURUSD")
            report=inspect([("a",a),("b",b)],asof_utc=ASOF)
            self.assertEqual(report["incomplete_cycle_count"],2)
            self.assertIn("PARTIAL_THREE_PAIR_CYCLES",
                          report["issues_and_safety_holds"])

    def test_single_session_never_claims_multi_session_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,3)
            report=inspect([("only",a)],asof_utc=ASOF)
            self.assertIn("MULTISESSION_COMPARISON_NOT_YET_POSSIBLE",
                          report["issues_and_safety_holds"])

    def test_duplicate_label_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            b=make_session(root,"two",4,1)
            with self.assertRaises(InputError):
                inspect([("same",a),("same",b)],asof_utc=ASOF)

    def test_duplicate_folder_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            with self.assertRaises(InputError):
                inspect([("a",a),("b",a)],asof_utc=ASOF)

    def test_unrelated_expert_log_key_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            with self.assertRaises(InputError):
                inspect([("a",a)],asof_utc=ASOF,
                        experts={"different":root/"other.txt"})

    def test_excess_sessions_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            with self.assertRaises(InputError):
                inspect([(f"s{i}",a) for i in range(25)],asof_utc=ASOF)

    def test_future_observation_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",190,1)
            with self.assertRaises(InputError):
                inspect([("a",a)],asof_utc=ASOF.replace("09:00","07:00"))

    def test_filename_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            file=next(a.glob("*.csv"))
            file.write_text(file.read_text().replace(
                "2026-11-10T06:00:00Z","2026-11-10T06:00:01Z"))
            with self.assertRaises(InputError):
                inspect([("a",a)],asof_utc=ASOF)

    def test_cli_creates_new_report_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,2)
            b=make_session(root,"two",10,2)
            out=root/"result.json"
            args=["--session",f"first={a}","--session",f"next={b}",
                  "--asof-utc",ASOF,"--out",str(out)]
            self.assertEqual(main(args),0)
            self.assertEqual(main(args),2)
            self.assertTrue(out.is_file())

    def test_cli_refuses_output_inside_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            args=["--session",f"first={a}","--asof-utc",ASOF,
                  "--out",str(a/"bad.json")]
            self.assertEqual(main(args),2)
            self.assertFalse((a/"bad.json").exists())

    def test_cli_rejects_duplicate_label(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,1)
            out=root/"bad.json"
            self.assertEqual(main(["--session",f"x={a}",
                                   "--session",f"x={a}",
                                   "--asof-utc",ASOF,"--out",str(out)]),2)
            self.assertFalse(out.exists())

    def test_never_authorizes_trade_even_with_no_missing_pairs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            a=make_session(root,"one",0,2)
            b=make_session(root,"two",30,2)
            report=inspect([("a",a),("b",b)],asof_utc=ASOF)
            self.assertEqual(report["runtime_go_no_go"],"NO_GO")
            self.assertTrue(report["safety_hold_latched"])
            self.assertFalse(report["demo_orders_permitted"])
            self.assertFalse(report["real_orders_permitted"])
            self.assertFalse(report["stop_at_30_cycles_independently_verified"])


if __name__ == "__main__":
    unittest.main()
