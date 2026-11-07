"""Static mock import-time restrictions, not runtime sandbox certification."""
from __future__ import annotations

import unittest

from scripts import audit_risk_3p_69_import_time_safety as mod


class ImportTimeSourceTests(unittest.TestCase):
    def test_six_current_pure_mock_sources_have_no_import_time_calls(self):
        self.assertEqual(mod.audit(), [])
        r = mod.snapshot()
        self.assertEqual(r["status"], "PASS_NARROW_IMPORT_TIME_AST_ONLY", r)
        self.assertEqual(r["mock_source_modules_reviewed"], 6)
        self.assertFalse(r["runtime_side_effect_freedom_proven"])
        self.assertFalse(r["transitive_dependencies_verified"])

    def test_module_body_process_network_and_io_calls_refused(self):
        for source in ("make_connection()", "open('secret.txt')",
                       "run_mt4()", "some_object.save()", "print('leak')"):
            with self.subTest(source=source):
                self.assertIn("P69_IMPORT_TIME_EXPRESSION",
                              mod.inspect_source(source))

    def test_import_time_arbitrary_initializer_rejected(self):
        for source in ("x = connect()",
                       "x: str = network()",
                       "items = [read_data() for x in range(3)]"):
            with self.subTest(source=source):
                self.assertIn("P69_IMPORT_TIME_INITIALIZER_EXECUTION",
                              mod.inspect_source(source))

    def test_function_decorators_and_dynamic_defaults_rejected(self):
        for source in ("@danger()\ndef f():\n    pass",
                       "def f(x=read_secret()):\n    return x"):
            with self.subTest(source=source):
                self.assertIn("P69_IMPORT_TIME_DECORATOR_OR_DEFAULT_CALL",
                              mod.inspect_source(source))

    def test_script_execution_conditional_and_loops_refused(self):
        for source in ("if __name__ == '__main__':\n    execute()",
                       "for i in range(3):\n    touch()",
                       "with file as f:\n    pass"):
            self.assertIn("P69_UNREVIEWED_IMPORT_TIME_STATEMENT",
                          mod.inspect_source(source))

    def test_existing_fixed_hash_regex_is_explicit_exception(self):
        self.assertEqual(mod.inspect_source(
            'import re\nHEX64 = re.compile(r"[0-9a-f]{64}\\Z")'), [])
        self.assertIn("P69_IMPORT_TIME_INITIALIZER_EXECUTION",
                      mod.inspect_source(
                          'HEX64 = re.compile(untrusted_expression())'))
        self.assertIn("P69_IMPORT_TIME_INITIALIZER_EXECUTION",
                      mod.inspect_source('OTHER = re.compile("x")'))

    def test_relative_private_override_is_rejected(self):
        r = mod.snapshot(overrides={
            "../private/passwords.py": "PRIVATE_CANARY_69"})
        self.assertEqual(r["status"], "FAIL_CLOSED")
        self.assertIn("P69_UNSAFE_OR_UNKNOWN_OVERRIDE", r["errors"])
        self.assertNotIn("PRIVATE_CANARY_69", str(r))

    def test_bad_syntax_and_binary_input_fail_closed(self):
        for source in (None, [], "def f(:", ""):
            with self.subTest(source=repr(source)):
                self.assertNotEqual(mod.inspect_source(source), [])

    def test_selected_module_override_detects_executable_code(self):
        path = mod.TARGETS[0]
        r = mod.snapshot(overrides={path:"import socket\nsocket.connect('remote')"})
        self.assertEqual(r["status"], "FAIL_CLOSED")
        self.assertIn("P69_SOURCE_1:P69_IMPORT_TIME_EXPRESSION", r["errors"])
        self.assertFalse(r["real_mt4_read_authorized"])


    def test_poison_override_key_not_hashed_or_compared(self):
        class PoisonKey:
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash(mod.TARGETS[0])
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_145")
        source = {PoisonKey(): "PRIVATE_CANARY_145"}
        PoisonKey.calls = 0
        result = mod.snapshot(overrides=source)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["errors"],
                         ["P69_UNSAFE_OR_UNKNOWN_OVERRIDE"])
        self.assertEqual(PoisonKey.calls, 0)
        self.assertNotIn("PRIVATE_CANARY_145", str(result))

    def test_str_subclass_key_not_hashed_or_compared(self):
        class PoisonStr(str):
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash(str(self))
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_145")
        source = {PoisonStr(mod.TARGETS[0]): "x=1"}
        PoisonStr.calls = 0
        self.assertEqual(mod.audit(overrides=source),
                         ["P69_UNSAFE_OR_UNKNOWN_OVERRIDE"])
        self.assertEqual(PoisonStr.calls, 0)

    def test_dict_subclass_override_not_visited(self):
        class PoisonDict(dict):
            calls = 0
            def items(self):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_145")
        value = PoisonDict({mod.TARGETS[0]: "x=1"})
        self.assertEqual(mod.audit(overrides=value),
                         ["P69_UNSAFE_OR_UNKNOWN_OVERRIDE"])
        self.assertEqual(PoisonDict.calls, 0)

    def test_unsafe_annotation_without_future_import_is_rejected(self):
        for src in ("def f(x: dangerous.payload):\n    pass",
                    "def f() -> attacker[0]:\n    pass",
                    "x: dangerous.attribute",
                    "x: dangerous.attribute = 1"):
            with self.subTest(source=src):
                self.assertIn("P69_UNPOSTPONED_ANNOTATION_EVALUATION",
                              mod.inspect_source(src))

    def test_postponed_annotations_do_not_execute_at_import_time(self):
        for src in (
                "from __future__ import annotations\n"
                "def f(x: dangerous.payload):\n    pass",
                "from __future__ import annotations\n"
                "x: dangerous.attribute"):
            with self.subTest(source=src):
                self.assertEqual(mod.inspect_source(src), [])

    def test_known_call_in_annotation_remains_rejected_even_if_postponed(self):
        src = ("from __future__ import annotations\n"
               "def f(x: injected()):\n    pass")
        self.assertIn("P69_IMPORT_TIME_DECORATOR_OR_DEFAULT_CALL",
                      mod.inspect_source(src))

    def test_oversized_import_time_source_fails_before_ast(self):
        src = "x = 1\n" + "#" * mod.MAX_STATIC_SOURCE_CHARS
        self.assertEqual(mod.inspect_source(src), ["P69_SOURCE_TOO_LARGE"])
        self.assertEqual(
            mod.audit(overrides={mod.TARGETS[0]: src}),
            ["P69_UNSAFE_OR_UNKNOWN_OVERRIDE"])

    def test_source_at_exact_resource_bound_does_not_fail_size_check(self):
        prefix = "x = 1\n"
        src = prefix + "#" * (mod.MAX_STATIC_SOURCE_CHARS - len(prefix))
        self.assertEqual(len(src), mod.MAX_STATIC_SOURCE_CHARS)
        self.assertEqual(mod.inspect_source(src), [])

    def test_unknown_override_with_poison_value_is_not_stringified(self):
        class BadValue:
            def __str__(self):
                raise RuntimeError("PRIVATE_CANARY_145")
        result = mod.snapshot(overrides={mod.TARGETS[0]: BadValue()})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["errors"],
                         ["P69_UNSAFE_OR_UNKNOWN_OVERRIDE"])

    def test_original_six_sources_still_pass_but_cannot_trade(self):
        result = mod.snapshot()
        self.assertEqual(result["status"], "PASS_NARROW_IMPORT_TIME_AST_ONLY")
        self.assertFalse(result["runtime_side_effect_freedom_proven"])
        self.assertFalse(result["transitive_dependencies_verified"])
        self.assertFalse(result["order_execution_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])


if __name__ == "__main__":
    unittest.main()
