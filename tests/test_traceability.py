"""Regression tests for the Q109 traceability gate."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_traceability import audit


class TraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "specs").mkdir()
        self.registry = {
            "schema_version": 1,
            "groups": [{
                "group_id": "FX-RISK", "spec_ids": ["Q6", "Q7"],
                "prefixes": ["src/risk/"], "tests": [], "status": "planned"
            }]
        }
        self.write_registry()

    def tearDown(self):
        self.tmp.cleanup()

    def write_registry(self):
        (self.root / "specs" / "traceability.json").write_text(
            json.dumps(self.registry), encoding="utf-8"
        )

    def add_source(self):
        path = self.root / "src" / "risk" / "sizing.py"
        path.parent.mkdir(parents=True)
        path.write_text("def calc():\n    return 0\n", encoding="utf-8")

    def test_unimplemented_scope_is_allowed(self):
        self.assertEqual(audit(self.root), [])

    def test_critical_code_without_tests_is_rejected(self):
        self.add_source()
        self.assertTrue(audit(self.root))

    def test_critical_code_with_registered_test_passes(self):
        self.add_source()
        test = self.root / "tests" / "test_sizing.py"
        test.parent.mkdir()
        test.write_text("import unittest\n\nclass TestSizing(unittest.TestCase):\n"
                        "    def test_basic(self):\n        self.assertTrue(True)\n", encoding="utf-8")
        self.registry["groups"][0]["status"] = "active"
        self.registry["groups"][0]["tests"] = ["tests/test_sizing.py"]
        self.write_registry()
        self.assertEqual(audit(self.root), [])

    def test_specific_readonly_group_does_not_activate_trade_group(self):
        test = self.root / "tests" / "test_probe.py"
        test.parent.mkdir()
        test.write_text("import unittest\n", encoding="utf-8")
        source = self.root / "mt4" / "read_only" / "probe.mq4"
        source.parent.mkdir(parents=True)
        source.write_text("// synthetic only\n", encoding="utf-8")
        self.registry["groups"].append({
            "group_id": "FX-ORDER-SL", "spec_ids": ["Q26"],
            "prefixes": ["mt4/"], "tests": [], "status": "planned"
        })
        self.registry["groups"].append({
            "group_id": "FX-MT4-READONLY", "spec_ids": ["Q109"],
            "prefixes": ["mt4/read_only/"],
            "tests": ["tests/test_probe.py"], "status": "active"
        })
        self.write_registry()
        self.assertEqual(audit(self.root), [])

    def test_new_order_mql4_under_broad_mt4_still_blocked(self):
        test = self.root / "tests" / "test_probe.py"
        test.parent.mkdir()
        test.write_text("import unittest\n", encoding="utf-8")
        readonly = self.root / "mt4" / "read_only" / "probe.mq4"
        readonly.parent.mkdir(parents=True)
        readonly.write_text("// synthetic only\n", encoding="utf-8")
        order = self.root / "mt4" / "orders" / "send.mq4"
        order.parent.mkdir(parents=True)
        order.write_text("// synthetic only\n", encoding="utf-8")
        self.registry["groups"].append({
            "group_id": "FX-ORDER-SL", "spec_ids": ["Q26"],
            "prefixes": ["mt4/"], "tests": [], "status": "planned"
        })
        self.registry["groups"].append({
            "group_id": "FX-MT4-READONLY", "spec_ids": ["Q109"],
            "prefixes": ["mt4/read_only/"],
            "tests": ["tests/test_probe.py"], "status": "active"
        })
        self.write_registry()
        errors = audit(self.root)
        self.assertTrue(errors)
        self.assertIn("FX-ORDER-SL: critical code exists but group is not active",
                      "\n".join(errors))

    def test_readonly_subgroup_without_test_or_active_registration_fails(self):
        source = self.root / "mt4" / "read_only" / "probe.mq4"
        source.parent.mkdir(parents=True)
        source.write_text("// synthetic only\n", encoding="utf-8")
        self.registry["groups"].append({
            "group_id": "FX-ORDER-SL", "spec_ids": ["Q26"],
            "prefixes": ["mt4/"], "tests": [], "status": "planned"
        })
        self.registry["groups"].append({
            "group_id": "FX-MT4-READONLY", "spec_ids": ["Q109"],
            "prefixes": ["mt4/read_only/"],
            "tests": [], "status": "planned"
        })
        self.write_registry()
        errors = audit(self.root)
        self.assertIn("FX-MT4-READONLY: critical code exists but group is not active",
                      "\n".join(errors))
        self.assertIn("FX-MT4-READONLY: missing tests for critical code",
                      "\n".join(errors))

    def test_unregistered_critical_code_is_rejected(self):
        path = self.root / "mt4" / "executor.mq4"
        path.parent.mkdir()
        path.write_text("// not tested", encoding="utf-8")
        self.assertIn("Unregistered safety-critical source", "\n".join(audit(self.root)))


if __name__ == "__main__":
    unittest.main()
