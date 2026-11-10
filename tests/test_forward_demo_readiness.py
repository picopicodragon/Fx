"""FWD-022: all declarations remain insufficient for execution permission."""
import tempfile
import unittest
from pathlib import Path

from research.forward_demo_readiness import assess, main
from research.offline_backtest import InputError


def evidence(status):
    return {"status": status, "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True, "real_orders_permitted": False}


def reports():
    a = evidence("FORWARD_OBSERVABILITY_HOLD_NO_GO")
    a["blocking_reasons"] = []
    b = evidence("QUOTE_CONTINUITY_RESEARCH_NO_GO")
    b["all_pairs_have_fresh_quotes"] = True
    c = evidence("MT4_READONLY_SOURCE_STATIC_AUDIT_NO_GO")
    c["static_token_checks_passed"] = True
    return a, b, c


def declaration():
    return {"schema": "fx_forward_operator_declaration_v1",
            "account_type_reported": "DEMO",
            "mt4_compilation_verified": True,
            "sole_terminal_session_reported": True,
            "data_license_reviewed": True}


class DemoReadinessTests(unittest.TestCase):
    def test_missing_declaration_stays_no_go(self):
        result = assess(*reports())
        self.assertIn("OPERATOR_DECLARATION_ABSENT", result["blocking_reasons"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["demo_order_execution_enabled"])

    def test_all_manual_green_still_no_go(self):
        result = assess(*reports(), operator_evidence=declaration())
        self.assertIn("FORMAL_DEMO_ORDER_APPROVAL_NOT_GRANTED",
                      result["blocking_reasons"])
        self.assertIn("BROKER_DEMO_ACCOUNT_NOT_INDEPENDENTLY_AUTHENTICATED",
                      result["blocking_reasons"])
        self.assertFalse(result["real_orders_permitted"])

    def test_untrusted_approval_forgery_refused(self):
        vals = list(reports())
        vals[0]["real_orders_permitted"] = True
        with self.assertRaises(InputError):
            assess(*vals)

    def test_bad_boolean_decl_refused(self):
        d = declaration()
        d["data_license_reviewed"] = "yes"
        with self.assertRaises(InputError):
            assess(*reports(), operator_evidence=d)

    def test_real_account_decl_refused(self):
        d = declaration()
        d["account_type_reported"] = "LIVE"
        with self.assertRaises(InputError):
            assess(*reports(), operator_evidence=d)

    def test_cli_missing_report_no_output(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            out = base / "out.json"
            self.assertEqual(main(["--observability", str(base / "missing"),
                                   "--quote", str(base / "quote"),
                                   "--mt4-static", str(base / "audit"),
                                   "--out", str(out)]), 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
