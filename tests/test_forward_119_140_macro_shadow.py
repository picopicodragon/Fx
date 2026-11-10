"""FWD-119..140 deterministic synthetic quality, macro and replay tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.forward_mt4_v2_quote import COLUMNS
from research.offline_backtest import InputError
from research.forward_shadow_time_regimes import (
    inspect as inspect_times, main as time_main
)
from research.forward_shadow_macro_contract import (
    inspect as inspect_macro, main as macro_main
)
from research.forward_shadow_causal_replay import (
    inspect as inspect_replay, main as replay_main
)

ASOF = "2026-11-10T09:00:00Z"
PAIRS = {"USDJPY": "USD/JPY", "EURJPY": "EUR/JPY", "EURUSD": "EUR/USD"}


def fixture(root: Path, name: str, start: int = 0, count: int = 4,
            *, down_at: int | None = None) -> Path:
    directory = root / name
    directory.mkdir()
    base = datetime(2026, 11, 10, 6, 0, 0, tzinfo=timezone.utc)
    for idx in range(count):
        dt = base + timedelta(minutes=start+idx)
        stamp = dt.strftime("%Y%m%d_%H%M%S")
        obs = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        server = (dt+timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        tick = (dt+timedelta(hours=2,seconds=-1)).strftime("%Y-%m-%dT%H:%M:%S")
        bid_usd = "149.000" if idx == down_at else f"{150 + (idx*0.01):.3f}"
        for symbol, pair in PAIRS.items():
            if symbol=="USDJPY":
                bid, ask = bid_usd, f"{float(bid_usd)+0.005:.3f}"
            elif symbol=="EURJPY":
                bid, ask = "170.000", "170.010"
            else:
                bid, ask = "1.12000", "1.12005"
            conversion = (
                f"{float(bid_usd):.5f}" if symbol=="EURUSD" else "1.00000")
            fields = [
                obs, pair, bid, ask, conversion,
                tick, server, "1", "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED"
            ]
            (directory/f"FxFwdV3_{symbol}_{stamp}.csv").write_text(
                ",".join(COLUMNS) + "\n" + ",".join(fields) + "\n",
                encoding="utf-8")
    return directory


def macro(**kw):
    item = {
        "hypothesis_id": "h1",
        "pair": "USD/JPY",
        "direction": "LONG",
        "source_records": [{
            "source_label": "synthetic-doc-1",
            "published_at_utc": "2026-11-10T05:50:00Z",
            "accessed_at_utc": "2026-11-10T05:55:00Z",
            "content_sha256": "a"*64,
        }],
        "constructed_at_utc": "2026-11-10T05:56:00Z",
        "reviewed_at_utc": "2026-11-10T05:57:00Z",
        "decision_at_utc": "2026-11-10T06:00:30Z",
        "builder_id": "dummy-builder",
        "reviewer_id": "dummy-verifier",
        "review_status": "APPROVED",
        "macro_thesis": "Synthetic input only, not a real macro thesis.",
        "counter_thesis": "Synthetic counterargument not validated.",
        "expected_catalyst": "None, synthetic scenario.",
        "invalidation_conditions": "Synthetic reversal.",
    }
    item.update(kw)
    return item


def scenario(**kw):
    item = {
        "scenario_label": "synthetic-no-orders",
        "hypothesis_id": "h1",
        "session_label": "s1",
        "evaluation_end_at_utc": "2026-11-10T06:03:00Z",
        "equity_jpy": "100000", "units": "1000",
        "stop_distance_pips": "20",
        "slippage_pips_each_side": "0.2",
        "existing_open_risk_jpy": "0",
        "daily_loss_jpy": "0",
        "drawdown_percent": "0",
    }
    item.update(kw)
    return item


class TimeRegimeTests(unittest.TestCase):
    def test_one_hour_coverage_explicitly_insufficient(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_times([("s1",d)],asof_utc=ASOF)
            self.assertEqual(r["csv_file_count"],12)
            self.assertEqual(r["per_pair_utc_hour"]["USD/JPY"]["06"]["samples"],4)
            self.assertIn("INSUFFICIENT_TIME_OF_DAY_COVERAGE",
                          r["coverage_and_safety_holds"])
            self.assertFalse(r["broker_time_attested"])

    def test_two_sessions_grouped_by_supplied_pc_utc_hour(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            a=fixture(root,"a",0,2)
            b=fixture(root,"b",62,2)
            r=inspect_times([("s1",a),("s2",b)],asof_utc=ASOF)
            self.assertEqual(set(r["per_pair_utc_hour"]["EUR/USD"]),
                             {"06","07"})
            self.assertEqual(r["per_pair_utc_hour"]["EUR/JPY"]["06"]
                             ["spread_max_pips"],"1.0")
            self.assertFalse(r["real_orders_permitted"])

    def test_time_regime_cli_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=fixture(root,"s1")
            out=root/"time.json"
            args=["--session",f"s1={d}","--asof-utc",ASOF,"--out",str(out)]
            self.assertEqual(time_main(args),0)
            self.assertEqual(time_main(args),2)


class MacroContractTests(unittest.TestCase):
    def test_self_reported_approval_is_not_verified(self):
        result=inspect_macro(macro(),asof_utc=ASOF)
        self.assertTrue(result["source_publication_chronology_consistent"])
        self.assertTrue(result["hypothetical_replay_allowed_by_document_only"])
        self.assertFalse(result["actual_llm_verification_performed"])
        self.assertFalse(result["trading_authorized"])

    def test_source_published_after_construct_rejected(self):
        bad=macro(source_records=[{
            "source_label":"synthetic", "content_sha256":"a"*64,
            "published_at_utc":"2026-11-10T06:01:00Z",
            "accessed_at_utc":"2026-11-10T06:01:30Z",
        }])
        with self.assertRaises(InputError):
            inspect_macro(bad,asof_utc=ASOF)

    def test_review_before_build_rejected(self):
        with self.assertRaises(InputError):
            inspect_macro(macro(reviewed_at_utc="2026-11-10T05:50:00Z"),
                          asof_utc=ASOF)

    def test_decision_before_review_rejected(self):
        with self.assertRaises(InputError):
            inspect_macro(macro(decision_at_utc="2026-11-10T05:55:00Z"),
                          asof_utc=ASOF)

    def test_same_builder_and_reviewer_rejected(self):
        with self.assertRaises(InputError):
            inspect_macro(macro(reviewer_id="dummy-builder"),asof_utc=ASOF)

    def test_pending_or_rejected_cannot_replay(self):
        for status in ("PENDING","REVISION","REJECTED"):
            with self.subTest(status=status):
                r=inspect_macro(macro(review_status=status),asof_utc=ASOF)
                self.assertFalse(r["hypothetical_replay_allowed_by_document_only"])

    def test_hold_direction_not_replayable(self):
        result=inspect_macro(macro(direction="HOLD"),asof_utc=ASOF)
        self.assertFalse(result["hypothetical_replay_allowed_by_document_only"])

    def test_bad_source_fingerprint_rejected(self):
        source=macro()["source_records"][0].copy()
        source["content_sha256"]="bad"
        with self.assertRaises(InputError):
            inspect_macro(macro(source_records=[source]),asof_utc=ASOF)

    def test_macro_cli_preserves_no_go(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            file=root/"hypothesis.json";file.write_text(json.dumps(macro()))
            out=root/"contract.json"
            args=["--hypothesis",str(file),"--asof-utc",ASOF,
                  "--out",str(out)]
            self.assertEqual(macro_main(args),0)
            self.assertEqual(macro_main(args),2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])


class CausalReplayTests(unittest.TestCase):
    def test_next_observation_not_same_or_prior(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_replay([("s1",d)],hypothesis=macro(),
                             scenario=scenario(),asof_utc=ASOF)
            self.assertEqual(r["scenario_vetoes"],[])
            ledger=r["hypothetical_mark_ledger"]
            self.assertEqual(ledger["entry_observed_at_utc"],
                             "2026-11-10T06:01:00Z")
            self.assertEqual(ledger["exit_observed_at_utc"],
                             "2026-11-10T06:03:00Z")
            self.assertFalse(ledger["broker_execution_or_fill_attested"])
            self.assertEqual(r["actual_broker_trades"],0)
            self.assertEqual(r["demo_order_calls"],0)
            self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_adverse_slippage_used_both_sides(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_replay([("s1",d)],hypothesis=macro(),
                             scenario=scenario(),asof_utc=ASOF)
            ledger=r["hypothetical_mark_ledger"]
            self.assertEqual(ledger["entry_side_with_adverse_slippage"],
                             "150.017")
            self.assertEqual(ledger["exit_side_with_adverse_slippage"],
                             "150.028")

    def test_stop_is_snapshot_only_not_intraminute(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1",down_at=2)
            r=inspect_replay([("s1",d)],hypothesis=macro(),
                             scenario=scenario(),asof_utc=ASOF)
            self.assertEqual(r["hypothetical_mark_ledger"]
                             ["exit_reason_observations_only"],
                             "STOP_LEVEL_CROSSED_AT_OBSERVED_SNAPSHOT")
            self.assertEqual(r["hypothetical_mark_ledger"]
                             ["exit_observed_at_utc"],
                             "2026-11-10T06:02:00Z")

    def test_snapshot_gap_loss_is_not_hidden_by_risk_budget(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1",down_at=2)
            r=inspect_replay([("s1",d)],hypothesis=macro(),
                             scenario=scenario(),asof_utc=ASOF)
            self.assertTrue(r["hypothetical_mark_ledger"]
                            ["loss_exceeded_reserved_risk"])
            self.assertIn("SYNTHETIC_MARK_LOSS_EXCEEDS_RESERVED_RISK",
                          r["unresolved_safety_holds"])
            self.assertFalse(r["real_orders_permitted"])

    def test_pending_macro_vetoes_even_if_prices_good(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_replay([("s1",d)],
                             hypothesis=macro(review_status="PENDING"),
                             scenario=scenario(),asof_utc=ASOF)
            self.assertIsNone(r["hypothetical_mark_ledger"])
            self.assertIn("MACRO_SELF_REPORTED_APPROVAL_NOT_PRESENT",
                          r["scenario_vetoes"])

    def test_risk_over_half_percent_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_replay([("s1",d)],hypothesis=macro(),
                             scenario=scenario(units="4000"),asof_utc=ASOF)
            self.assertIn("RESERVED_SINGLE_RISK_GT_0_5_PERCENT",
                          r["scenario_vetoes"])
            self.assertIsNone(r["hypothetical_mark_ledger"])

    def test_total_risk_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_replay([("s1",d)],hypothesis=macro(),
                             scenario=scenario(existing_open_risk_jpy="900"),
                             asof_utc=ASOF)
            self.assertIn("RESERVED_TOTAL_RISK_GT_1_PERCENT",
                          r["scenario_vetoes"])

    def test_daily_loss_and_dd_hard_stop(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_replay([("s1",d)],hypothesis=macro(),
                             scenario=scenario(
                                 daily_loss_jpy="1490",
                                 drawdown_percent="5"),asof_utc=ASOF)
            for flag in ("DAILY_LOSS_BUDGET_EXHAUSTED",
                         "DD4_NEW_ENTRY_STOP",
                         "DD5_HUMAN_APPROVAL_REQUIRED"):
                self.assertIn(flag,r["scenario_vetoes"])

    def test_next_observation_window_expired(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            late=macro(decision_at_utc="2026-11-10T06:03:01Z")
            r=inspect_replay([("s1",d)],hypothesis=late,
                             scenario=scenario(
                                 evaluation_end_at_utc="2026-11-10T06:10:00Z"),
                             asof_utc=ASOF)
            self.assertIn("NO_NEXT_OBSERVATION_WITHIN_ENTRY_WINDOW",
                          r["scenario_vetoes"])

    def test_horizon_cannot_end_before_decision(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            with self.assertRaises(InputError):
                inspect_replay([("s1",d)],hypothesis=macro(),
                               scenario=scenario(
                                   evaluation_end_at_utc="2026-11-10T06:00:00Z"),
                               asof_utc=ASOF)

    def test_unknown_session_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            with self.assertRaises(InputError):
                inspect_replay([("s1",d)],hypothesis=macro(),
                               scenario=scenario(session_label="bogus"),
                               asof_utc=ASOF)

    def test_eurusd_conversion_is_research_only(self):
        with tempfile.TemporaryDirectory() as t:
            d=fixture(Path(t),"s1")
            r=inspect_replay([("s1",d)],
                             hypothesis=macro(pair="EUR/USD"),
                             scenario=scenario(),asof_utc=ASOF)
            self.assertIsNotNone(r["hypothetical_mark_ledger"])
            self.assertFalse(r["strategy_profitability_validated"])

    def test_replay_cli_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            folder=fixture(root,"s1")
            macro_path=root/"hyp.json";macro_path.write_text(json.dumps(macro()))
            case=root/"scenario.json";case.write_text(json.dumps(scenario()))
            out=root/"replay.json"
            args=["--session",f"s1={folder}",
                  "--hypothesis",str(macro_path),
                  "--scenario",str(case),
                  "--asof-utc",ASOF,"--out",str(out)]
            self.assertEqual(replay_main(args),0)
            self.assertEqual(replay_main(args),2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])


if __name__=="__main__":
    unittest.main()
