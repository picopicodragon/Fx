"""FWD-721..800: deterministic synthetic risk, outages, blackout and fault injection."""
from __future__ import annotations

import copy
import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_synthetic_safety_fault_campaign as drill
from research import forward_shadow_watch as watch
from research import forward_risk_timeline as risk
from research import forward_macro_event_windows as windows
from research.offline_backtest import InputError


def run_cli(args=None):
    with patch("sys.stdout", new_callable=io.StringIO) as out:
        rc=drill.main([] if args is None else args)
    return rc,json.loads(out.getvalue())


class FaultCampaignTests(unittest.TestCase):
    def test_default_full_scenario_campaign_passes_and_is_no_go(self):
        result=drill.inspect()
        self.assertEqual(result["status"],
                         "SYNTHETIC_SAFETY_FAULT_CAMPAIGN_HOLD_NO_GO")
        self.assertGreaterEqual(result["synthetic_scenario_count"],30)
        self.assertEqual(result["synthetic_scenario_count"],
                         result["synthetic_passed_count"])
        self.assertEqual(result["synthetic_failed_count"],0)
        self.assertEqual(len(result["synthetic_cases_sha256"]),64)
        self.assertFalse(result["synthetic_green_is_operational_acceptance"])
        self.assertFalse(result["real_source_events_or_broker_evidence_used"])
        self.assertFalse(result["live_mt4_connection_ever_attempted"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["demo_orders_permitted"])
        self.assertTrue(result["safety_hold_latched"])
        self.assertEqual(result["runtime_go_no_go"],"NO_GO")

    def test_scenario_names_are_unique(self):
        cases=drill.inspect()["synthetic_scenarios"]
        self.assertEqual(len(cases),len(set(x["case"] for x in cases)))
        self.assertTrue(all(x["synthetic_contract_passed"] is True
                            for x in cases))

    def test_scenario_hash_deterministic(self):
        self.assertEqual(drill.inspect()["synthetic_cases_sha256"],
                         drill.inspect()["synthetic_cases_sha256"])

    def test_outage_thresholds_59_60_599_600_in_catalog(self):
        names={x["case"] for x in drill.inspect()["synthetic_scenarios"]}
        for name in ("outage_threshold_59_none",
                     "outage_threshold_60_level1",
                     "outage_threshold_599_level1",
                     "outage_threshold_600_level2"):
            self.assertIn(name,names)

    def test_dd_recovery_human_approval_guard_in_catalog(self):
        names={x["case"] for x in drill.inspect()["synthetic_scenarios"]}
        self.assertIn("dd5_recovery_does_not_clear_dd5",names)
        self.assertIn("dd5_recovery_does_not_clear_level3",names)
        self.assertIn("dd5_never_claims_human_approval",names)

    def test_calendar_blackout_exact_edges_in_catalog(self):
        names={x["case"] for x in drill.inspect()["synthetic_scenarios"]}
        self.assertIn("blackout_exact_minus15",names)
        self.assertIn("blackout_one_second_before_plus15",names)
        self.assertIn("after_plus15_requires_reassessment",names)

    def test_ny17_dst_case_both_seasons(self):
        names={x["case"] for x in drill.inspect()["synthetic_scenarios"]}
        self.assertIn("ny17_summer_boundary",names)
        self.assertIn("ny17_winter_boundary",names)

    def test_single_trade_risk_is_contract_only_not_broker(self):
        names={x["case"] for x in drill.inspect()["synthetic_scenarios"]}
        self.assertIn("single_trade_0_5_percent_arithmetic_only",names)
        self.assertIn(
            "SYNTHETIC_RESULTS_NOT_PROOF_OF_BROKER_RISK_CONTROLS",
            drill.inspect()["unresolved_operational_holds"])

    def test_watchdog_nan_age_fails_closed(self):
        obs,quote=drill._observed(drill.BASE)
        obs["latest_cycle_age_seconds"]=float("nan")
        with self.assertRaises(InputError):
            watch.evaluate(obs,quote,asof_utc=drill._utc(drill.BASE))

    def test_watchdog_infinity_age_fails_closed(self):
        obs,quote=drill._observed(drill.BASE)
        quote["by_pair"]["EUR/JPY"]["latest_quote_age_seconds"]=float("inf")
        with self.assertRaises(InputError):
            watch.evaluate(obs,quote,asof_utc=drill._utc(drill.BASE))

    def test_watchdog_negative_quote_age_fails_closed(self):
        obs,quote=drill._observed(drill.BASE)
        quote["by_pair"]["EUR/USD"]["latest_quote_age_seconds"]=-1
        with self.assertRaises(InputError):
            watch.evaluate(obs,quote,asof_utc=drill._utc(drill.BASE))

    def test_watchdog_previous_latch_int_is_not_bool(self):
        obs,quote=drill._observed(drill.BASE)
        previous=watch.evaluate(obs,quote,asof_utc=drill._utc(drill.BASE))
        previous["watchdog_latched"]=1
        with self.assertRaises(InputError):
            watch.evaluate(obs,quote,
                           asof_utc=drill._utc(
                               drill.BASE+drill.timedelta(seconds=1)),
                           prior=previous)

    def test_watchdog_false_previous_latch_does_not_enable_orders(self):
        obs,quote=drill._observed(drill.BASE)
        previous=watch.evaluate(obs,quote,asof_utc=drill._utc(drill.BASE))
        later=watch.evaluate(obs,quote,
                             asof_utc=drill._utc(
                                drill.BASE+drill.timedelta(seconds=1)),
                             prior=previous)
        self.assertFalse(later["resume_automatically_permitted"])
        self.assertFalse(later["demo_orders_permitted"])

    def test_risk_evaluator_fake_go_triggers_failure(self):
        original=risk.evaluate
        def unsafe(samples):
            data=original(samples)
            data["real_orders_permitted"]=True
            return data
        with patch.object(drill.risk,"evaluate",side_effect=unsafe):
            with self.assertRaises(InputError):
                drill.inspect()

    def test_watchdog_fake_autoresume_triggers_failure(self):
        original=watch.evaluate
        def unsafe(*args,**kwargs):
            data=original(*args,**kwargs)
            data["resume_automatically_permitted"]=True
            return data
        with patch.object(drill.watch,"evaluate",side_effect=unsafe):
            with self.assertRaises(InputError):
                drill.inspect()

    def test_watchdog_fake_demo_orders_triggers_failure(self):
        original=watch.evaluate
        def unsafe(*args,**kwargs):
            data=original(*args,**kwargs)
            data["demo_orders_permitted"]=True
            return data
        with patch.object(drill.watch,"evaluate",side_effect=unsafe):
            with self.assertRaises(InputError):
                drill.inspect()

    def test_blackout_fake_runtime_go_triggers_failure(self):
        original=windows.inspect
        def unsafe(*args,**kwargs):
            data=original(*args,**kwargs)
            data["runtime_go_no_go"]="GO"
            return data
        with patch.object(drill.windows,"inspect",side_effect=unsafe):
            with self.assertRaises(InputError):
                drill.inspect()

    def test_blackout_fake_order_permission_triggers_failure(self):
        original=windows.inspect
        def unsafe(*args,**kwargs):
            data=copy.deepcopy(original(*args,**kwargs))
            data["windows"][0]["new_orders_permitted"]=True
            return data
        with patch.object(drill.windows,"inspect",side_effect=unsafe):
            with self.assertRaises(InputError):
                drill.inspect()

    def test_cli_without_out_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("os.getcwd",return_value=str(root)):
                code,out=run_cli([])
            self.assertEqual(code,0)
            self.assertEqual(out["network_calls_this_run"],0)
            self.assertEqual(out["API_calls_this_run"],0)
            self.assertEqual(out["actual_orders_sent"],0)
            self.assertEqual(list(root.iterdir()),[])

    def test_cli_write_once_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"synthetic.json"
            rc,data=run_cli(["--out",str(path)])
            self.assertEqual(rc,0)
            self.assertTrue(path.exists())
            self.assertFalse(data["real_orders_permitted"])
            original=path.read_bytes()
            rc2,second=run_cli(["--out",str(path)])
            self.assertEqual(rc2,2)
            self.assertEqual(original,path.read_bytes())
            self.assertEqual(second["runtime_go_no_go"],"NO_GO")

    def test_cli_fail_closed_when_child_throws(self):
        with patch.object(drill.risk,"evaluate",
                          side_effect=InputError("synthetic regression")):
            rc,data=run_cli()
        self.assertEqual(rc,2)
        self.assertEqual(data["status"],
                         "SYNTHETIC_SAFETY_FAULT_CAMPAIGN_FAIL_CLOSED_NO_GO")
        self.assertFalse(data["demo_orders_permitted"])

    def test_no_unattended_background_network_or_broker_connection(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("network not permitted")):
            rc,data=run_cli()
        self.assertEqual(rc,0)
        self.assertFalse(data["live_mt4_connection_ever_attempted"])


if __name__ == "__main__":
    unittest.main()
