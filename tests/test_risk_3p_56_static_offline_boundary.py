"""Static guard catches obvious risky syntax but cannot prove runtime safety."""
from __future__ import annotations

import unittest

from scripts import audit_risk_3p_56_static_offline_boundary as mod


class StaticOfflineGuardTests(unittest.TestCase):
    def test_real_selected_sources_have_no_disallowed_static_patterns(self):
        self.assertEqual(mod.audit(), [])
        result = mod.snapshot()
        self.assertEqual(result["status"], "PASS_NARROW_STATIC_REVIEW_ONLY")
        self.assertEqual(result["pure_synthetic_modules_scanned"], 6)
        self.assertFalse(result["full_runtime_isolation_proven"])
        self.assertFalse(result["transitive_imports_or_reflection_proven_safe"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_network_process_and_broker_imports_refused(self):
        for source in (
            "import socket", "import subprocess", "import os",
            "from requests import get", "import MetaTrader5",
            "from win32com.client import Dispatch", "import importlib",
            "from urllib.request import urlopen",
        ):
            with self.subTest(source=source):
                codes = mod._inspect_source(source)
                expected = ("P56_DISALLOWED_IMPORT" if source.startswith("import ")
                            else "P56_DISALLOWED_IMPORT_FROM")
                self.assertIn(expected, codes)

    def test_unapproved_repository_module_import_is_rejected(self):
        for source in (
            "from scripts import broker_adapter",
            "from scripts import risk_3p_49_synthetic_evidence_chain, broker_api",
            "import scripts.broker_adapter",
            "import scripts",
            "import scripts.risk_3p_49_synthetic_evidence_chain.extra",
            "from scripts.broker_adapter import connect",
        ):
            with self.subTest(source=source):
                self.assertIn("P56_UNAPPROVED_LOCAL_MODULE_IMPORT",
                              mod._inspect_source(source))

    def test_explicit_mock_imports_remain_allowed(self):
        for module in mod.ALLOWED_SCRIPT_MODULES:
            with self.subTest(module=module):
                self.assertEqual(mod._inspect_source(
                    "from scripts import " + module), [])
                self.assertEqual(mod._inspect_source(
                    "import scripts." + module), [])

    def test_disallowed_import_from_and_star_refused(self):
        for source in ("from subprocess import run",
                       "from socket import socket",
                       "from scripts.foo import *",
                       "from . import secret"):
            with self.subTest(source=source):
                result = mod._inspect_source(source)
                self.assertIn("P56_DISALLOWED_IMPORT_FROM", result)

    def test_filesystem_network_execution_and_dynamic_calls_refused(self):
        for source in ("open('private.log')", "Path('x').read_text()",
                       "path.write_bytes(b'x')", "os.system('cmd')",
                       "socket.connect(addr)", "exec('x = 1')",
                       "eval('1')", "__import__('socket')",
                       "getattr(o, 'x')", "subprocess.run(['cmd'])",
                       "OrderSend(1)", "terminal.OrderClose(2)"):
            with self.subTest(source=source):
                result = mod._inspect_source(source)
                self.assertTrue(any(code in result for code in (
                    "P56_UNSAFE_DIRECT_CALL", "P56_UNSAFE_ATTRIBUTE_CALL",
                    "P56_PRIVILEGED_SYMBOL_REFERENCE")), result)

    def test_allowed_pure_math_parsing_and_helpers_are_not_blocked(self):
        for source in ("import hashlib\nx = hashlib.sha256(b'x')",
                       "from decimal import Decimal\ny = Decimal('0.01')",
                       "from scripts import risk_3p_55_synthetic_ingress_contract",
                       "def f(x):\n    return x + 1"):
            with self.subTest(source=source):
                self.assertEqual(mod._inspect_source(source), [])

    def test_syntax_errors_or_binary_input_fail_closed(self):
        for source in ("", "def x(:", None, b'raw'):
            with self.subTest(value=repr(source)):
                result = mod._inspect_source(source)
                self.assertTrue(result)
                self.assertTrue(all(e.startswith("P56_") for e in result))

    def test_overrides_detect_unsafe_change_in_any_guarded_source(self):
        for name in mod.TARGETS:
            with self.subTest(name=name):
                result = mod.audit(overrides={
                    name: "import socket\nsocket.connect('actual')"})
                self.assertIn("P56_DISALLOWED_IMPORT",
                              result[0].split(":", 1)[1])
                self.assertEqual(mod.snapshot(overrides={
                    name: "import socket"}).get("runtime_go_no_go"), "NO_GO")

    def test_unknown_or_private_path_injection_never_processed(self):
        result = mod.snapshot(overrides={
            "../private/mt4.log": "PRIVATE_CANARY_56"})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P56_UNKNOWN_OR_PRIVATE_PATH_OVERRIDE", result["errors"])
        self.assertNotIn("PRIVATE_CANARY_56", str(result))

    def test_commented_unsafe_strings_do_not_misrepresent_ast_guard(self):
        self.assertEqual(mod._inspect_source(
            "# Open(...) is a comment, not a call\nx = 1"), [])


if __name__ == "__main__":
    unittest.main()
