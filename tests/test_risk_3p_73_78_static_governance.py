"""RISK-3P-73/78: regression proof for pure-mock AST and exact gate output.

These tests feed only code as text to static scanners; they do not run that
code or perform any external actions, and no mock PASS grants runtime GO.
"""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_69_import_time_safety as import_time
from scripts import audit_risk_3p_56_static_offline_boundary as static
from scripts import risk_3p_71_offline_integrity_gate as gate
from scripts import risk_3p_61_strict_offline_result_contract as exact


class LiteralOnlyImportTimeTests(unittest.TestCase):
    def test_current_six_mock_sources_still_pass_narrow_scan(self):
        self.assertEqual(import_time.audit(), [])
        self.assertEqual(import_time.snapshot()["status"],
                         "PASS_NARROW_IMPORT_TIME_AST_ONLY")

    def test_module_level_subscript_and_binary_operation_are_refused(self):
        for source in (
            "x = object_with_getitem['secret']",
            "x = object_with_getitem[0]",
            "x = dangerous_attribute.property",
            "x = 2 ** 10000000",
            "x = [i for i in user_input]",
            "x = f'{object_with_custom_format}'",
            "x = (lambda: 1)",
        ):
            with self.subTest(source=source):
                self.assertIn("P69_IMPORT_TIME_INITIALIZER_EXECUTION",
                              import_time.inspect_source(source))

    def test_legal_literal_containers_and_negative_numbers_still_pass(self):
        for source in (
            "KEYS = ('a', 'b', 'c')",
            "VALUES = {'flag': False, 'count': 0, 'optional': None}",
            "NUM = -10",
            "ARGS = ['x', 1, True]",
        ):
            with self.subTest(source=source):
                self.assertEqual(import_time.inspect_source(source), [])

    def test_function_default_subscript_and_binary_operator_refused(self):
        for source in (
            "def f(x=user_data[0]):\n    return x",
            "def f(x=system.property):\n    pass",
            "def f(x=1 / 0):\n    pass",
            "async def f(x=secret()[0]):\n    pass",
        ):
            with self.subTest(source=source):
                self.assertIn("P69_IMPORT_TIME_DECORATOR_OR_DEFAULT_CALL",
                              import_time.inspect_source(source))

    def test_pure_literal_function_defaults_remain_accepted(self):
        self.assertEqual(import_time.inspect_source(
            "def f(x='SIM_FAKE', y=None, *, enabled=False):\n    return x"), [])

    def test_annotation_calls_are_denied_at_module_and_function_level(self):
        for source, expected in (
            ("value: dangerous() = 1",
             "P69_IMPORT_TIME_INITIALIZER_EXECUTION"),
            ("def f(x: dangerous()):\n    pass",
             "P69_IMPORT_TIME_DECORATOR_OR_DEFAULT_CALL"),
            ("def f() -> dangerous():\n    pass",
             "P69_IMPORT_TIME_DECORATOR_OR_DEFAULT_CALL"),
        ):
            with self.subTest(source=source):
                self.assertIn(expected, import_time.inspect_source(source))

    def test_literal_regex_exception_is_fully_pinned(self):
        self.assertEqual(import_time.inspect_source(
            'import re\nHEX64 = re.compile(r"[0-9a-f]{64}\\Z")'), [])
        for source in (
            'HEX64 = re.compile(".*")',
            'HEX64 = re.compile("[0-9a-f]{64}")',
            'OTHER = re.compile(r"[0-9a-f]{64}\\Z")',
        ):
            with self.subTest(source=source):
                self.assertIn("P69_IMPORT_TIME_INITIALIZER_EXECUTION",
                              import_time.inspect_source(source))

    def test_composite_assignment_with_evaluated_target_refused(self):
        self.assertIn("P69_IMPORT_TIME_ASSIGNMENT_TARGET",
                      import_time.inspect_source("x[0] = 1"))
        self.assertIn("P69_IMPORT_TIME_ASSIGNMENT_TARGET",
                      import_time.inspect_source("x.y = 1"))

    def test_import_time_rejection_errors_do_not_echo_secrets(self):
        secret = "CONFIDENTIAL_FAKE_CANARY_73"
        result = import_time.inspect_source(
            "x = read_secret('" + secret + "')")
        self.assertTrue(result)
        self.assertNotIn(secret, str(result))


class ReflectionStaticBoundaryTests(unittest.TestCase):
    def test_reflection_attributes_refused_regardless_of_call(self):
        for name in static.REFLECTION_ESCAPE_ATTRIBUTES:
            with self.subTest(attribute=name):
                for expr in ("obj." + name,
                             "obj." + name + "()", "f." + name + "[0]"):
                    self.assertIn("P56_REFLECTION_ESCAPE_ATTRIBUTE",
                                  static._inspect_source(expr))

    def test_clean_public_literal_operations_remain_allowed(self):
        self.assertEqual(static._inspect_source(
            "def validate(x):\n    return x + 2"), [])

    def test_real_six_mock_sources_do_not_use_reflection_escape(self):
        self.assertEqual(static.audit(), [])

    def test_bad_source_with_secret_does_not_echo(self):
        secret = "CONFIDENTIAL_FAKE_CANARY_74"
        self.assertNotIn(secret, str(static._inspect_source(
            "obj.__globals__['" + secret + "']")))


class ExactSevenChildGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baselines = dict(zip(gate.NAMES, gate._outputs()))

    def reject(self, name, mutate, *, integration=False):
        target = copy.deepcopy(self.baselines[name])
        mutate(target)
        index = gate.NAMES.index(name)
        # All mutated snapshots are checked directly with the same strict
        # contract used by P71. The heavier full dependency gate is
        # exercised once per report class below.
        self.assertFalse(exact._strict_same(
            target, gate.EXPECTED_CHILD_REPORTS[index]))
        if not integration:
            return
        r = gate.evaluate(injected={name: target})
        self.assertEqual(r["status"], "FAIL_CLOSED", r)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(r["safety_hold_latched"])
        self.assertEqual(r["p05_passed"], 0)
        self.assertEqual(r["g1_real_verified"], 0)
        self.assertFalse(r["real_mt4_observation_authorized"])
        self.assertFalse(r["real_order_execution_authorized"])
        self.assertFalse(r["main_auto_merge_authorized"])

    def test_all_seven_child_outputs_match_literal_expected_records(self):
        self.assertEqual(len(gate.EXPECTED_CHILD_REPORTS), 7)
        for i, name in enumerate(gate.NAMES):
            with self.subTest(name=name):
                self.assertTrue(exact._strict_same(
                    self.baselines[name], gate.EXPECTED_CHILD_REPORTS[i]))
        self.assertEqual(gate.evaluate()["status"], "PASS_OFFLINE_INTEGRITY_ONLY")

    def test_unknown_authorization_field_rejected_on_each_child(self):
        for name in gate.NAMES:
            with self.subTest(name=name):
                self.reject(name, lambda d: d.update(
                    newly_invented_broker_approval=True), integration=True)

    def test_missing_errors_field_rejected_on_each_child(self):
        for name in gate.NAMES:
            with self.subTest(name=name):
                self.reject(name, lambda d: d.pop("errors"))

    def test_integer_counter_booleans_rejected_as_type_confusion(self):
        cases = (
            ("previous_governance", "offline_governance_subchecks"),
            ("traceability", "minimum_tracked_synthetic_sources"),
            ("g1_source_alignment", "required_real_g1_rows"),
            ("pinned_offline_inventory", "expected_offline_sources"),
            ("explicit_import_allowlist", "pure_synthetic_modules_scanned"),
            ("no_unreviewed_import_time_calls",
             "mock_source_modules_reviewed"),
            ("twenty_nine_mock_attacks", "mock_failures_exercised"),
        )
        for name, key in cases:
            with self.subTest(name=name):
                self.reject(name, lambda d, k=key: d.update({k: True}))

    def test_unreviewed_benign_looking_counter_change_rejected(self):
        self.reject("previous_governance",
                    lambda d: d.update(synthetic_corruption_cases_included=69))
        self.reject("twenty_nine_mock_attacks",
                    lambda d: d.update(pure_modules_reviewed=5))

    def test_secret_string_from_unknown_key_never_emitted(self):
        secret = "CONFIDENTIAL_FAKE_CANARY_75"
        injected = copy.deepcopy(
            self.baselines["pinned_offline_inventory"])
        injected["password"] = secret
        result = gate.evaluate(injected={"pinned_offline_inventory": injected})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn(secret, str(result))

    def test_no_live_or_demo_order_permission_from_mock_success(self):
        r = gate.evaluate()
        self.assertEqual(r["status"], "PASS_OFFLINE_INTEGRITY_ONLY")
        self.assertFalse(r["real_mt4_observation_authorized"])
        self.assertFalse(r["real_order_execution_authorized"])
        self.assertFalse(r["human_p05_signoff"])
        self.assertFalse(r["main_auto_merge_authorized"])


if __name__ == "__main__":
    unittest.main()
