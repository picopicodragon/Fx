"""P05 prerequisites cannot be reordered or self-approved via offline tests."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_59_p05_dependency_dag as mod


class P05DependencyGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._read(mod.ROOT, name)
                    for name in (mod.GRAPH, mod.P05)}

    def reject(self, path, mutation, code):
        inputs = copy.deepcopy(self.docs)
        mutation(inputs[path])
        result = mod.snapshot(injected=inputs)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(code, result["errors"])
        self.assertEqual(result["p05_real_accepted"], 0)
        self.assertFalse(result["real_mt4_observation_authorized"])
        self.assertFalse(result["order_execution_authorized"])
        self.assertFalse(result["human_p05_signoff"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_baseline_is_eight_blocked_checks_and_no_go(self):
        self.assertEqual(mod.audit(), [])
        snapshot = mod.snapshot()
        self.assertEqual(snapshot["status"], "PASS_BLOCKED_DEPENDENCY_DAG_ONLY")
        self.assertEqual(snapshot["p05_prerequisites"], 8)
        self.assertEqual(snapshot["p05_real_accepted"], 0)
        self.assertTrue(snapshot["owner_storage_accepted_for_offline_planning"])

    def test_cycle_cannot_make_approval_automatic(self):
        self.reject(mod.GRAPH,
                    lambda x: x["checks"][0].update(
                        depends_on=["P05-08"]),
                    "P59_CYCLE_OR_SELF_DEPENDENCY")
        self.reject(mod.GRAPH,
                    lambda x: x["checks"][1].update(
                        depends_on=["P05-02"]),
                    "P59_CYCLE_OR_SELF_DEPENDENCY")

    def test_unknown_or_duplicate_dependency_not_allowed(self):
        self.reject(mod.GRAPH,
                    lambda x: x["checks"][0].update(
                        depends_on=["G10"]),
                    "P59_UNKNOWN_OR_DUPLICATE_DEPENDENCY:1")
        self.reject(mod.GRAPH,
                    lambda x: x["checks"][2].update(
                        depends_on=["P05-01", "P05-01"]),
                    "P59_UNKNOWN_OR_DUPLICATE_DEPENDENCY:3")

    def test_dependency_order_and_criteria_cannot_be_modified(self):
        self.reject(mod.GRAPH,
                    lambda x: x["checks"][7].update(depends_on=[]),
                    "P59_GATE_ORDER_OR_AUTHORIZATION_PROMOTED:8")
        self.reject(mod.GRAPH,
                    lambda x: x["checks"][6].update(
                        criterion="SAFE_TO_TRADE"),
                    "P59_GATE_ORDER_OR_AUTHORIZATION_PROMOTED:7")

    def test_each_gate_requires_independent_evidence_and_signature(self):
        for i in range(8):
            with self.subTest(i=i):
                self.reject(mod.GRAPH,
                            lambda x, n=i: x["checks"][n].update(
                                independent_evidence_verified=True),
                            "P59_GATE_ORDER_OR_AUTHORIZATION_PROMOTED:"
                            + str(i + 1))
                self.reject(mod.GRAPH,
                            lambda x, n=i: x["checks"][n].update(
                                owner_signed=True),
                            "P59_GATE_ORDER_OR_AUTHORIZATION_PROMOTED:"
                            + str(i + 1))

    def test_owner_storage_acceptance_is_offline_only(self):
        self.reject(mod.GRAPH,
                    lambda x: x["state"].update(real_acl_verified=True),
                    "P59_REAL_BROKER_OR_OWNER_APPROVAL_FORGED")
        self.reject(mod.GRAPH,
                    lambda x: x["state"].update(p05_passed=6),
                    "P59_REAL_BROKER_OR_OWNER_APPROVAL_FORGED")

    def test_all_safety_flags_immutable(self):
        for key, value in mod.STATE.items():
            with self.subTest(key=key):
                updated = not value if type(value) is bool else (
                    1 if type(value) is int else "GO")
                self.reject(mod.GRAPH,
                            lambda x, k=key, v=updated:
                            x["state"].update({k: v}),
                            "P59_REAL_BROKER_OR_OWNER_APPROVAL_FORGED")

    def test_original_p05_cannot_be_promoted(self):
        self.reject(mod.P05,
                    lambda x: x.update(
                        p05_human_safety_signoff=True),
                    "P59_SOURCE_P05_STILL_UNACCEPTED_REQUIRED")
        self.reject(mod.P05,
                    lambda x: x["p05_checks"][3].update(
                        p05_accepted=True),
                    "P59_SOURCE_HUMAN_SIGNOFF_FALSE:4")

    def test_missing_or_unhashable_gate_ids_fail_closed(self):
        self.reject(mod.GRAPH,
                    lambda x: x["checks"][0].update(
                        check_id=["UNHASHABLE"]),
                    "P59_UNKNOWN_OR_DUPLICATE_DEPENDENCY:1")
        self.reject(mod.GRAPH,
                    lambda x: x["checks"].pop(),
                    "P59_EXACTLY_EIGHT_GATES")

    def test_secret_injection_never_appears_in_errors(self):
        self.reject(mod.GRAPH,
                    lambda x: x.update(private_mt4_password="CANARY_59"),
                    "P59_DEPENDENCY_PLAN_SCOPE_DRIFT")
        data = copy.deepcopy(self.docs)
        data[mod.GRAPH] = {"password": "CANARY_59"}
        result = mod.snapshot(injected=data)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn("CANARY_59", str(result))


if __name__ == "__main__":
    unittest.main()
