"""FWD-06B: static safety boundary for optional MT4 source file.

The CI runner does not have MetaEditor, so this does NOT prove MQL4
compilation, broker compatibility or demo account identity.
"""
import re
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / (
    "research/mt4_readonly/FxForwardReadOnlyQuote.mq4")


class Mt4ReadonlySourceTests(unittest.TestCase):
    def test_source_requires_demo_and_connected_only(self):
        code = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("void OnStart()", code)
        self.assertRegex(code, r"if\s*\(\s*!IsDemo\(\)\s*\)")
        self.assertRegex(code, r"if\s*\(\s*!IsConnected\(\)\s*\)")
        self.assertIn("MANUAL_MT4_DEMO_EXPORT_UNVERIFIED", code)
        self.assertIn("FxForwardReadOnlyQuote.csv", code)
        self.assertIn('FILE_CSV | FILE_WRITE | FILE_ANSI', code)

    def test_no_trade_operations_or_broker_identity_files(self):
        code = SCRIPT.read_text(encoding="utf-8")
        forbidden = (
            "OrderSend", "OrderClose", "OrderModify", "OrderDelete",
            "OrderCloseBy", "OrderSelect", "AccountNumber",
            "AccountPassword", "WebRequest", "ShellExecute",
            "FileOpenHistory", "FILE_COMMON", "WinExec",
        )
        # This test is intentionally literal; source-only static safety check.
        for name in forbidden:
            with self.subTest(name=name):
                self.assertNotRegex(code,
                                    r"\b" + re.escape(name) + r"\s*\(")
        self.assertNotIn("FILE_COMMON", code)
        self.assertNotIn("AccountNumber()", code)


if __name__ == "__main__":
    unittest.main()
