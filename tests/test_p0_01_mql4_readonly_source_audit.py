"""Synthetic static checks only: MQL4 source is never compiled or executed."""
import unittest

from scripts.audit_mt4_readonly_source import (
    EXPECTED_FIELDS, EXPECTED_SYMBOLS, SOURCE, audit_mql4_readonly,
)


class ReadOnlyMql4SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_source_passes_default_deny_static_audit(self):
        self.assertEqual(audit_mql4_readonly(self.source), [])

    def test_onstart_only_and_explicit_consent_starts_false(self):
        self.assertIn("#property script_show_inputs", self.source)
        self.assertIn("input bool   InpExplicitReadApproval = false;", self.source)
        self.assertIn("if(!InpExplicitReadApproval)", self.source)
        self.assertEqual(self.source.count("void OnStart()"), 1)
        self.assertLess(self.source.index("if(!InpExplicitReadApproval)"),
                        self.source.index("if(!IsConnected())"))

    def test_only_five_readonly_marketinfo_fields_per_symbol(self):
        self.assertEqual(len(EXPECTED_FIELDS), 5)
        self.assertEqual(self.source.count("MarketInfo(symbol_name, property_id)"), 1)
        for field, mode in EXPECTED_FIELDS.items():
            self.assertIn(f'"{field}", {mode}', self.source)
        self.assertIn("MathIsValidNumber(observed)", self.source)
        self.assertIn("observed <= 0.0", self.source)
        self.assertIn("GetLastError()", self.source)

    def test_only_four_explicit_symbol_inputs_and_no_symbolselect_mutation(self):
        self.assertEqual(len(EXPECTED_SYMBOLS), 4)
        self.assertIn("SYMBOL_SELECT", self.source)
        for sym in EXPECTED_SYMBOLS:
            self.assertIn(f'Inp{sym} = "{sym}"', self.source)
            self.assertIn(f'InspectPair("{sym}", Inp{sym})', self.source)
        self.assertNotIn("SymbolSelect(", self.source)
        self.assertIn("UNVERIFIED_SYMBOL_NOT_SELECTED", self.source)

    def test_trade_side_effect_injection_is_rejected(self):
        edited = self.source.replace(
            "void OnStart()",
            "void Unapproved() { OrderSend(); }\nvoid OnStart()",
        )
        self.assertIn("SIDE_EFFECT_FUNCTION", audit_mql4_readonly(edited))
        self.assertIn("UNEXPECTED_FUNCTION_CALLS", audit_mql4_readonly(edited))

    def test_file_output_or_web_request_injection_is_rejected(self):
        for addition in ("FileOpen(1);", "WebRequest(1);",
                         "SendNotification(1);", "SymbolSelect(1);"):
            with self.subTest(addition=addition):
                altered = self.source.replace(
                    "void OnStart()", f"void OnStart() {{ {addition} }}\nvoid OnStart()"
                )
                self.assertNotEqual(audit_mql4_readonly(altered), [])

    def test_default_on_or_missing_consent_gate_is_rejected(self):
        on = self.source.replace("InpExplicitReadApproval = false",
                                 "InpExplicitReadApproval = true")
        self.assertIn("DEFAULT_DENY_MISSING", audit_mql4_readonly(on))
        no_check = self.source.replace("if(!InpExplicitReadApproval)",
                                       "if(false)")
        self.assertIn("EXECUTION_GUARD_OR_READ_PATH",
                      audit_mql4_readonly(no_check))

    def test_extra_mql4_include_import_or_event_handler_is_rejected(self):
        for added in ("#include <Trade.mqh>\n", "#import \"kernel32.dll\"\n",
                      "void OnTick() {}\n", "void OnTimer() {}\n"):
            with self.subTest(added=added):
                self.assertNotEqual(audit_mql4_readonly(added + self.source), [])

    def test_comments_and_strings_do_not_count_as_executable_side_effects(self):
        marked = self.source + '\n// OrderSend(1);\n'
        self.assertEqual(audit_mql4_readonly(marked), [])
        marked = self.source + '\n/* FileOpen(1); */\n'
        self.assertEqual(audit_mql4_readonly(marked), [])

    def test_output_remains_local_nonauthorizing_and_no_file_writes(self):
        self.assertIn("OBSERVED_NOT_VERIFIED", self.source)
        self.assertIn("INCOMPLETE_DO_NOT_USE", self.source)
        self.assertIn("FORM_01_PENDING", self.source)
        self.assertIn("FORM_03_PENDING", self.source)
        self.assertIn("PHASE_1_BLOCKED", self.source)
        self.assertIn("Print(", self.source)
        for forbidden in ("AccountNumber(", "AccountName(", "AccountBalance(",
                          "FileWrite(", "WebRequest(", "OrderSend("):
            self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
