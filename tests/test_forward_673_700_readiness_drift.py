"""FWD-673..700: prior evidence snapshots are descriptive, not GO approval."""
from __future__ import annotations

import copy
import unittest

from research import forward_fullstack_noorder_hub as hub
from research import forward_readiness_drift as delta
from research.offline_backtest import InputError

EARLY = "2026-11-13T04:00:00Z"
LATER = "2026-11-13T05:00:00Z"


def prior(source):
    return {
        "schema": delta.PREVIOUS_SCHEMA,
        "status": "RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "real_orders_permitted": False,
        "demo_orders_permitted": False,
        "safety_hold_latched": True,
        "fullstack_report": source,
    }


class ReadinessDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.older = hub.inspect(asof_utc=EARLY)
        cls.current = hub.inspect(asof_utc=LATER)

    def test_identical_evidence_reports_do_not_authorize_orders(self):
        r = delta.compare(prior(self.older), self.current)
        self.assertEqual(r["newly_reported_holds"], [])
        self.assertEqual(r[
            "previously_reported_holds_not_in_current_unverified"], [])
        self.assertFalse(r["human_or_runtime_reauthorization_permitted"])
        self.assertTrue(r["holding_reason_disappearance_is_not_safety_clearance"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertFalse(r["demo_orders_permitted"])

    def test_disappearing_hold_is_not_called_safety_clearance(self):
        changed = copy.deepcopy(self.current)
        hold = changed["unresolved_holds"].pop()
        r = delta.compare(prior(self.older), changed)
        self.assertIn(hold,
                      r["previously_reported_holds_not_in_current_unverified"])
        self.assertTrue(r["changed_source_inputs_not_independently_authenticated"])
        self.assertFalse(r["real_orders_permitted"])

    def test_new_hold_and_counter_change_are_visible_but_descriptive(self):
        changed = copy.deepcopy(self.current)
        changed["unresolved_holds"].append("NEW_TEST_HOLD")
        changed["price_csv_count"] = 114
        r = delta.compare(prior(self.older), changed)
        self.assertIn("NEW_TEST_HOLD", r["newly_reported_holds"])
        self.assertEqual(
            r["numeric_metric_changes_unattested"]["price_csv_count"]
            ["descriptive_change"], 114)
        self.assertFalse(
            r["numeric_metric_changes_unattested"]["price_csv_count"]
            ["improvement_in_safety_claimed"])

    def test_reversed_local_clock_rejected(self):
        with self.assertRaises(InputError):
            delta.compare(prior(self.current), self.older)

    def test_same_timestamp_allowed_but_marked(self):
        r = delta.compare(prior(self.older), self.older)
        self.assertTrue(r["same_local_clock_second"])
        self.assertFalse(r["human_or_runtime_reauthorization_permitted"])

    def test_previous_runbook_go_forgery_rejected(self):
        forged = prior(self.older)
        forged["runtime_go_no_go"] = "GO"
        with self.assertRaises(InputError):
            delta.compare(forged, self.current)

    def test_previous_runbook_order_permission_forgery_rejected(self):
        forged = prior(self.older)
        forged["demo_orders_permitted"] = True
        with self.assertRaises(InputError):
            delta.compare(forged, self.current)

    def test_previous_embedded_hub_go_forgery_rejected(self):
        forged = prior(copy.deepcopy(self.older))
        forged["fullstack_report"]["real_orders_permitted"] = True
        with self.assertRaises(InputError):
            delta.compare(forged, self.current)

    def test_current_embedded_hub_go_forgery_rejected(self):
        forged = copy.deepcopy(self.current)
        forged["runtime_go_no_go"] = "GO"
        with self.assertRaises(InputError):
            delta.compare(prior(self.older), forged)

    def test_nonrunbook_previous_report_rejected(self):
        with self.assertRaises(InputError):
            delta.compare(self.older, self.current)

    def test_no_bogus_negative_metric_accepted(self):
        forged = copy.deepcopy(self.current)
        forged["price_csv_count"] = -1
        with self.assertRaises(InputError):
            delta.compare(prior(self.older), forged)

    def test_no_nonnumeric_metric_accepted(self):
        forged = copy.deepcopy(self.current)
        forged["price_csv_count"] = "114"
        with self.assertRaises(InputError):
            delta.compare(prior(self.older), forged)

    def test_non_string_hold_is_refused(self):
        forged = copy.deepcopy(self.current)
        forged["unresolved_holds"].append({"name": "GO"})
        with self.assertRaises(InputError):
            delta.compare(prior(self.older), forged)

    def test_duplicate_hold_is_refused(self):
        forged = copy.deepcopy(self.current)
        forged["unresolved_holds"].append(forged["unresolved_holds"][0])
        with self.assertRaises(InputError):
            delta.compare(prior(self.older), forged)

    def test_non_z_timestamp_refused(self):
        forged = copy.deepcopy(self.current)
        forged["asof_utc_local_or_supplied_unattested"] = "2026-11-13 05:00"
        with self.assertRaises(InputError):
            delta.compare(prior(self.older), forged)

    def test_missing_counter_is_not_treated_as_zero(self):
        forged = copy.deepcopy(self.current)
        del forged["price_ai_macro_observation_count"]
        with self.assertRaises(InputError):
            delta.compare(prior(self.older), forged)


if __name__ == "__main__":
    unittest.main()
