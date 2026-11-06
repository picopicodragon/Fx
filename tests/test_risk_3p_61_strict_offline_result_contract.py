"""P60 subresults: unknown safety fields, forged scopes and bool/int drift."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_61_strict_offline_result_contract as strict
from scripts import risk_3p_60_offline_ingress_quality_gate as gate


class StrictSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.baselines = dict(zip(gate.NAMES, gate._outputs()))

    def check_rejected(self, name, edit):
        payload = copy.deepcopy(self.baselines)
        edit(payload[name])
        result = strict.snapshot(payload)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertFalse(result["real_mt4_read_authorized"])
        self.assertTrue(result["safety_hold_latched"])
        combined = gate.evaluate(injected={name: payload[name]})
        self.assertEqual(combined["status"], "FAIL_CLOSED", combined)
        self.assertEqual(combined["p05_passed"], 0)
        self.assertFalse(combined["real_order_or_ea_action_authorized"])

    def test_seven_real_mock_snapshots_match_literal_contract(self):
        self.assertEqual(gate.NAMES, strict.EXPECTED_NAMES)
        r = strict.snapshot(self.baselines)
        self.assertEqual(r["status"], "PASS_EXACT_OFFLINE_RESULTS_ONLY", r)
        self.assertEqual(r["offline_report_contracts"], 7)
        self.assertEqual(gate.evaluate()["status"],
                         "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY")

    def test_unknown_broker_permission_cannot_pass_in_any_child(self):
        for name in strict.EXPECTED_NAMES:
            with self.subTest(name=name):
                self.check_rejected(name, lambda v: v.update(
                    real_mt4_order_execution_authorized=True))

    def test_missing_field_cannot_silently_validate(self):
        for name in strict.EXPECTED_NAMES:
            with self.subTest(name=name):
                self.check_rejected(name, lambda v: v.pop("errors"))

    def test_true_not_equivalent_to_int_one_for_passed_counters(self):
        for name, value in (
            ("fictional_ingress", "p05_passed"),
            ("previous_provenance_gate", "g1_real_verified"),
            ("unsigned_dependency_dag", "p05_real_accepted")):
            with self.subTest(name=name):
                self.check_rejected(name, lambda d, k=value: d.update({k: False}))

    def test_synthetic_success_counter_drift_also_fails_closed(self):
        self.check_rejected(
            "fictional_ingress", lambda d: d.update(fake_event_count=4))
        self.check_rejected(
            "static_boundary",
            lambda d: d.update(pure_synthetic_modules_scanned=5))
        self.check_rejected(
            "safe_diagnostics",
            lambda d: d.update(synthetic_checks_consistent=3))

    def test_claims_that_runtime_safe_or_p05_approved_are_denied(self):
        self.check_rejected(
            "static_boundary", lambda d: d.update(full_runtime_isolation_proven=True))
        self.check_rejected(
            "unsigned_future_handoff",
            lambda d: d.update(actual_evidence_received=True))
        self.check_rejected(
            "fake_clocks", lambda d: d.update(real_data_freshness_verified=True))

    def test_unknown_class_and_wrong_root_type_rejected_without_echo(self):
        self.assertEqual(strict.check("NOT_A_REAL_CASE", {"secret": "CANARY_61"}),
                         ["P61_UNKNOWN_REPORT_CLASS"])
        self.assertEqual(strict.snapshot([{"password": "CANARY_61"}])["status"],
                         "FAIL_CLOSED")
        self.assertNotIn("CANARY_61", str(strict.snapshot(
            {"private": "CANARY_61"})))

    def test_baseline_fixture_not_mutated_by_failed_inputs(self):
        baseline = copy.deepcopy(self.baselines)
        for name in strict.EXPECTED_NAMES:
            copy_d = copy.deepcopy(baseline)
            copy_d[name]["real_approval"] = True
            self.assertEqual(strict.snapshot(copy_d)["status"], "FAIL_CLOSED")
        self.assertEqual(self.baselines, baseline)

    def test_error_codes_do_not_reflect_user_supplied_string(self):
        self.check_rejected(
            "safe_diagnostics",
            lambda d: d.update(private_log_path="CANARY_61_SENSITIVE"))
        d = copy.deepcopy(self.baselines)
        d["safe_diagnostics"]["private_log_path"] = "CANARY_61_SENSITIVE"
        self.assertNotIn("CANARY_61_SENSITIVE", str(strict.snapshot(d)))


if __name__ == "__main__":
    unittest.main()
