"""RISK-3P-265..282: batch regression for three offline fail-closed gates.

Only public repository fixtures, simulated exceptions and values. No MT4,
broker, market feed, order path, private source archive or approval action.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts import risk_3p_52_offline_provenance_gate as p52
from scripts import audit_risk_3p_56_static_offline_boundary as p56
from scripts import audit_risk_3p_59_p05_dependency_dag as p59


CANARY = "SIMULATED_SECRET_265_NEVER_ECHO"


class PoisonKey:
    def __hash__(self):
        return 562659

    def __eq__(self, other):
        raise AssertionError(CANARY)


class PoisonString(str):
    def __hash__(self):
        return 562660

    def __eq__(self, other):
        raise AssertionError(CANARY)


class PoisonValue:
    def __eq__(self, other):
        raise AssertionError(CANARY)


class PoisonList(list):
    def __eq__(self, other):
        raise AssertionError(CANARY)


class PoisonDict(dict):
    def get(self, *args, **kwargs):
        raise AssertionError(CANARY)


def assert_safe(test, result):
    test.assertEqual(result["status"], "FAIL_CLOSED", result)
    test.assertEqual(result["runtime_go_no_go"], "NO_GO")
    test.assertIs(result["safety_hold_latched"], True)
    test.assertNotIn(CANARY, str(result))


class P52BatchedBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = dict(zip(p52.CASE_NAMES, p52._results(p52.ROOT)))

    def child(self, key="simulated_chain"):
        return copy.deepcopy(self.baseline[key])

    def test_265_clean_synthetic_four_report_chain(self):
        result = p52.evaluate()
        self.assertEqual(result["status"], "PASS_OFFLINE_PROVENANCE_QA_ONLY", result)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_265_root_bad_key_refused_before_equality(self):
        result = p52.evaluate(injected={PoisonKey(): CANARY})
        assert_safe(self, result)
        self.assertIn("P52_INJECTED_UNKNOWN_OR_SENSITIVE_CASE", result["errors"])

    def test_266_root_str_subclass_refused(self):
        result = p52.evaluate(injected={PoisonString("simulated_chain"): self.child()})
        assert_safe(self, result)

    def test_266_root_dict_subclass_refused(self):
        result = p52.evaluate(injected=PoisonDict({"simulated_chain": self.child()}))
        assert_safe(self, result)

    def test_267_child_bad_key_refused_before_equality(self):
        row = self.child()
        row[PoisonKey()] = CANARY
        result = p52.evaluate(injected={"simulated_chain": row})
        assert_safe(self, result)

    def test_267_child_bad_string_key_refused(self):
        row = self.child()
        row[PoisonString("hidden")] = CANARY
        assert_safe(self, p52.evaluate(injected={"simulated_chain": row}))

    def test_268_child_status_poison_value_refused(self):
        row = self.child()
        row["status"] = PoisonValue()
        result = p52.evaluate(injected={"simulated_chain": row})
        assert_safe(self, result)
        self.assertIn("P52_COMPOSITE_RESULT_UNTRUSTED:1", result["errors"])

    def test_268_child_errors_list_subclass_refused(self):
        row = self.child()
        row["errors"] = PoisonList()
        assert_safe(self, p52.evaluate(injected={"simulated_chain": row}))

    def test_269_wrong_counter_or_extra_permission_refused(self):
        row = self.child()
        row["p05_passed"] = False
        assert_safe(self, p52.evaluate(injected={"simulated_chain": row}))
        row = self.child()
        row["real_order_execution_authorized"] = True
        result = p52.evaluate(injected={"simulated_chain": row})
        assert_safe(self, result)
        self.assertIn("P52_REAL_WORLD_AUTHORITY_FABRICATED:1", result["errors"])

    def test_270_unexpected_child_exception_fixed_no_go(self):
        for exc in (RuntimeError, AssertionError, ZeroDivisionError):
            with self.subTest(exc=exc.__name__):
                with patch.object(p52, "_results", side_effect=exc(CANARY)):
                    result = p52.evaluate()
                assert_safe(self, result)
                self.assertIn("P52_OFFLINE_CHILD_EVALUATION_FAILURE", result["errors"])
                self.assertIs(result["real_mt4_read_authorized"], False)


class P56BatchedBoundaryTests(unittest.TestCase):
    def test_271_original_six_static_sources_remain_mock_pass(self):
        result = p56.snapshot()
        self.assertEqual(result["status"], "PASS_NARROW_STATIC_REVIEW_ONLY", result)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_272_ast_parse_runtime_exception_fixed(self):
        with patch.object(p56.ast, "parse", side_effect=RuntimeError(CANARY)):
            self.assertEqual(p56._inspect_source("x=1"),
                             ["P56_INVALID_PYTHON_SYNTAX"])

    def test_273_ast_walk_assertion_fixed(self):
        with patch.object(p56.ast, "walk", side_effect=AssertionError(CANARY)):
            self.assertEqual(p56._inspect_source("x=1"),
                             ["P56_INVALID_PYTHON_SYNTAX"])

    def test_274_unexpected_read_error_fixed_no_go(self):
        with patch.object(p56.Path, "read_text", side_effect=RuntimeError(CANARY)):
            result = p56.snapshot()
        assert_safe(self, result)
        self.assertIn("P56_TARGET_1:P56_TARGET_MISSING_OR_UNREADABLE",
                      result["errors"])
        self.assertIs(result["real_mt4_access_authorized"], False)

    def test_275_unexpected_scanner_exception_fixed(self):
        with patch.object(p56, "_inspect_source", side_effect=RuntimeError(CANARY)):
            result = p56.snapshot()
        assert_safe(self, result)
        self.assertIn("P56_TARGET_1:P56_TARGET_MISSING_OR_UNREADABLE",
                      result["errors"])

    def test_276_poisoned_override_key_no_reflection(self):
        result = p56.snapshot(overrides={PoisonKey(): CANARY})
        assert_safe(self, result)
        self.assertEqual(result["errors"], ["P56_UNKNOWN_OR_PRIVATE_PATH_OVERRIDE"])


class P59BatchedBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: p59._read(p59.ROOT, name)
                    for name in (p59.GRAPH, p59.P05)}

    def altered(self, edit):
        docs = copy.deepcopy(self.docs)
        edit(docs)
        return p59.snapshot(injected=docs)

    def test_277_p05_eight_blocked_gates_still_no_go(self):
        result = p59.snapshot()
        self.assertEqual(result["status"], "PASS_BLOCKED_DEPENDENCY_DAG_ONLY", result)
        self.assertEqual(result["p05_real_accepted"], 0)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_277_hostile_root_key_before_lookup(self):
        result = self.altered(lambda d: d.update({PoisonKey(): CANARY}))
        assert_safe(self, result)
        self.assertIn("P59_MALFORMED_OR_MISSING_SOURCE", result["errors"])

    def test_278_hostile_graph_row_key_before_set(self):
        result = self.altered(lambda d: d[p59.GRAPH]["checks"][0].update(
            {PoisonKey(): CANARY}))
        assert_safe(self, result)
        self.assertIn("P59_ROW_SCHEMA:1", result["errors"])

    def test_279_hostile_state_key_before_eq(self):
        result = self.altered(lambda d: d[p59.GRAPH]["state"].update(
            {PoisonKey(): CANARY}))
        assert_safe(self, result)
        self.assertIn("P59_REAL_BROKER_OR_OWNER_APPROVAL_FORGED", result["errors"])

    def test_279_status_str_subclass_rejected(self):
        result = self.altered(lambda d: d[p59.GRAPH]["checks"][0].update(
            status=PoisonString("BLOCKED_NOT_INDEPENDENTLY_VERIFIED")))
        assert_safe(self, result)
        self.assertIn("P59_GATE_ORDER_OR_AUTHORIZATION_PROMOTED:1", result["errors"])

    def test_280_bool_as_zero_p05_counter_rejected(self):
        result = self.altered(lambda d: d[p59.GRAPH]["state"].update(
            p05_passed=False))
        assert_safe(self, result)
        self.assertIn("P59_REAL_BROKER_OR_OWNER_APPROVAL_FORGED", result["errors"])

    def test_280_bool_as_schema_version_rejected(self):
        result = self.altered(lambda d: d[p59.GRAPH].update(schema_version=True))
        assert_safe(self, result)
        self.assertIn("P59_DEPENDENCY_PLAN_SCOPE_DRIFT", result["errors"])

    def test_281_hostile_edge_list_subclass_rejected(self):
        result = self.altered(lambda d: d[p59.GRAPH]["checks"][1].update(
            depends_on=PoisonList(["P05-01"])))
        assert_safe(self, result)
        self.assertIn("P59_GATE_ORDER_OR_AUTHORIZATION_PROMOTED:2", result["errors"])

    def test_282_unexpected_source_error_fixed(self):
        with patch.object(p59, "_read", side_effect=RuntimeError(CANARY)):
            result = p59.snapshot()
        assert_safe(self, result)
        self.assertIn("P59_INVALID_OR_MISSING_OFFLINE_SPEC", result["errors"])

    def test_282_failure_does_not_mutate_baseline(self):
        before = copy.deepcopy(self.docs)
        assert_safe(self, self.altered(lambda d: d[p59.GRAPH]["state"].update(
            owner_p05_signoff=True)))
        self.assertEqual(self.docs, before)


if __name__ == "__main__":
    unittest.main()
