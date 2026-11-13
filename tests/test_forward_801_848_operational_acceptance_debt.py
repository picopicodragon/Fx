"""FWD-801..848: synthetic tests must never certify broker operations."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_fullstack_noorder_hub as hub
from research import forward_synthetic_safety_fault_campaign as drills
from research import forward_safety_acceptance_debt as debt
from research import forward_evidence_runbook as runbook
from research.offline_backtest import InputError

ASOF = "2026-11-13T05:00:00Z"


class OperationalAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = hub.inspect(asof_utc=ASOF)
        cls.s = drills.inspect()

    def test_ten_domains_remain_blocked_after_synthetic_pass(self):
        r = debt.inspect(self.h, self.s)
        self.assertEqual(r["domain_count"], 10)
        self.assertEqual(r["domain_count_independently_verified"], 0)
        self.assertFalse(r["owner_signoff_supplied_or_inferred"])
        self.assertFalse(r["programmatic_go_or_approval_logic_implemented"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(all(x["acceptance_status"]
                            == "BLOCKED_AWAITING_INDEPENDENT_EVIDENCE"
                            for x in r["review_dimensions"]))

    def test_broker_watchdog_and_alerts_are_unattested(self):
        r = debt.inspect(self.h, self.s)
        d = {x["domain"]: x for x in r["review_dimensions"]}
        for name in ("bidirectional_watchdog", "mobile_email_alerting",
                     "drawdown_approval_latches", "macro_blackout_recovery"):
            self.assertFalse(d[name][
                "broker_runtime_or_source_truth_independently_verified"])

    def test_forged_fullstack_go_rejected(self):
        with self.assertRaises(InputError):
            debt.inspect(dict(self.h, runtime_go_no_go="GO"), self.s)

    def test_forged_fullstack_demo_orders_rejected(self):
        with self.assertRaises(InputError):
            debt.inspect(dict(self.h, demo_orders_permitted=True), self.s)

    def test_forged_drill_demo_orders_rejected(self):
        with self.assertRaises(InputError):
            debt.inspect(self.h, dict(self.s, demo_orders_permitted=True))

    def test_forged_drill_result_sha_rejected(self):
        with self.assertRaises(InputError):
            debt.inspect(self.h, dict(self.s, synthetic_cases_sha256="0"*64))

    def test_changed_synthetic_case_rejected(self):
        d = copy.deepcopy(self.s)
        d["synthetic_scenarios"][1]["case"] = "TAMPERED"
        with self.assertRaises(InputError):
            debt.inspect(self.h, d)

    def test_duplicate_synthetic_case_rejected(self):
        d = copy.deepcopy(self.s)
        d["synthetic_scenarios"][1]["case"] = d["synthetic_scenarios"][0]["case"]
        with self.assertRaises(InputError):
            debt.inspect(self.h, d)

    def test_forged_synthetic_failed_count_rejected(self):
        with self.assertRaises(InputError):
            debt.inspect(self.h, dict(self.s, synthetic_failed_count=1))

    def test_invalid_hub_counter_type_rejected(self):
        with self.assertRaises(InputError):
            debt.inspect(dict(self.h, price_csv_count="114"), self.s)

    def test_broker_and_runbook_reads_are_no_order(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/"plan.json"
            p.write_text(json.dumps(runbook.empty_plan()), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                rc = runbook.main(["--plan-file", str(p), "--asof-utc", ASOF])
                result = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(result["operational_acceptance_debt"]["domain_count"], 10)
        self.assertEqual(result["synthetic_safety_fault_campaign"]["synthetic_failed_count"], 0)
        self.assertTrue(result["synthetic_test_green_does_not_clear_safety_hold"])
        self.assertFalse(result["real_orders_permitted"])

    def test_runbook_detects_forged_synthetic_go(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/"plan.json"
            p.write_text(json.dumps(runbook.empty_plan()))
            bad = dict(self.s, real_orders_permitted=True)
            with patch.object(runbook.safety_drills, "inspect", return_value=bad):
                with patch("sys.stdout", new_callable=io.StringIO) as out:
                    rc = runbook.main(["--plan-file", str(p), "--asof-utc", ASOF])
                    response = json.loads(out.getvalue())
        self.assertEqual(rc, 2)
        self.assertEqual(response["status"], "RUNBOOK_RESEARCH_FAIL_CLOSED_NO_GO")
        self.assertFalse(response["real_orders_permitted"])

    def test_matrix_cli_reads_only_and_no_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f1, f2 = root/"hub.json", root/"drills.json"
            f1.write_text(json.dumps(self.h))
            f2.write_text(json.dumps(self.s))
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                rc = debt.main(["--fullstack-report", str(f1),
                                "--synthetic-drill-report", str(f2)])
                r = json.loads(out.getvalue())
        self.assertEqual(rc, 0)
        self.assertEqual(r["network_calls_this_run"], 0)
        self.assertEqual(r["actual_orders_sent"], 0)
        self.assertFalse(r["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
