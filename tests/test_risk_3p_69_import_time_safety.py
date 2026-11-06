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


if __name__ == "__main__":
    unittest.main()
