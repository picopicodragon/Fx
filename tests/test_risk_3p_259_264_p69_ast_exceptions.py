"""RISK-3P-259..264: P69 public-source AST scanner exception containment.

Static-only checks; does not import user Python or connect to a broker.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts import audit_risk_3p_69_import_time_safety as p69

CANARY = "P69_FAKE_PRIVATE_CANARY_NO_ECHO"
EXCEPTIONS = (RuntimeError, AssertionError, ZeroDivisionError,
              LookupError, NotImplementedError, UnicodeError)


class P69UnexpectedExceptions(unittest.TestCase):
    def assert_closed(self, result, code):
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(code, result["errors"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(result["real_mt4_read_authorized"], False)
        self.assertIs(result["order_execution_authorized"], False)
        self.assertIs(result["runtime_side_effect_freedom_proven"], False)
        self.assertNotIn(CANARY, str(result))

    def test_259_existing_six_modules_still_mock_pass(self):
        result = p69.snapshot()
        self.assertEqual(result["status"], "PASS_NARROW_IMPORT_TIME_AST_ONLY")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_260_unexpected_ast_parse_exception_is_fixed_error(self):
        for exc in EXCEPTIONS:
            with self.subTest(exception=exc.__name__):
                with patch.object(p69.ast, "parse", side_effect=exc(CANARY)):
                    self.assertEqual(p69.inspect_source("x=1"),
                                     ["P69_BAD_PYTHON_SYNTAX"])

    def test_261_ast_walk_exception_is_fixed_error(self):
        src = "def mock(x: int):\n    pass"
        with patch.object(p69.ast, "walk", side_effect=RuntimeError(CANARY)):
            self.assertEqual(p69.inspect_source(src), ["P69_BAD_PYTHON_SYNTAX"])

    def test_262_public_source_read_exception_is_fixed_error(self):
        with patch.object(p69.Path, "read_text", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p69.snapshot(), "P69_SOURCE_1:P69_SOURCE_UNAVAILABLE")

    def test_262_scanner_unexpected_exception_is_fixed_error(self):
        with patch.object(p69, "inspect_source", side_effect=RuntimeError(CANARY)):
            self.assert_closed(p69.snapshot(), "P69_SOURCE_1:P69_SOURCE_UNAVAILABLE")

    def test_263_no_private_source_reflected_after_exception(self):
        with patch.object(p69, "_inspect_source_impl",
                          side_effect=RuntimeError(CANARY)):
            self.assertEqual(p69.inspect_source("x=1"),
                             ["P69_BAD_PYTHON_SYNTAX"])

    def test_264_clean_mock_scan_after_injected_exception(self):
        with patch.object(p69.ast, "parse", side_effect=RuntimeError(CANARY)):
            self.assertEqual(p69.inspect_source("x=1"),
                             ["P69_BAD_PYTHON_SYNTAX"])
        self.assertEqual(p69.inspect_source("x=1"), [])
        self.assertEqual(p69.snapshot()["status"],
                         "PASS_NARROW_IMPORT_TIME_AST_ONLY")


if __name__ == "__main__":
    unittest.main()
