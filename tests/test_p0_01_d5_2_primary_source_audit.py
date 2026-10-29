"""D5-2: external policy uncertainty cannot authorize runtime."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class D52SourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((ROOT/"specs/p0_01_d5_2_primary_source_audit.json").read_text(encoding="utf-8"))
        cls.d51 = json.loads((ROOT/"specs/p0_01_d5_1_preflight_gate.json").read_text(encoding="utf-8"))

    def test_concurrency_and_existing_state_safety_unproven(self):
        d = {e["id"]:e for e in self.audit["claims"]}
        self.assertEqual(set(d),set(("E1","E2","E3","E4","E5","E6")))
        for key in ("E1","E2","E3"):
            self.assertEqual(d[key]["status"],"NOT_ESTABLISHED")
        self.assertEqual(self.audit["g1"],"BLOCKED_EXTERNAL_POLICY")
        self.assertEqual(self.audit["pf1"],"BLOCKED")

    def test_documentation_never_grants_execution(self):
        self.assertEqual(self.audit["runtime_go_no_go"],"NO_GO")
        self.assertEqual(self.audit["phase_1"],"BLOCKED")
        self.assertIs(self.audit["creation_or_installation_approved"],False)
        for key in ("broker_verified","terminal_execution_approved",
                    "read_only_ex4_execution_approved","forward_trading_enabled",
                    "orders_generated"):
            self.assertIs(self.audit[key],False)

    def test_prior_gate_still_no_go_and_environment_a_unchanged(self):
        self.assertIs(self.audit["existing_environment_a_unchanged"],True)
        self.assertEqual(self.d51["runtime_go_no_go"],"NO_GO")
        self.assertIs(self.d51["candidate_b_installed"],False)
        self.assertIs(self.d51["concurrent_demo_policy_confirmed"],False)

    def test_documented_terminal_isolation_is_not_broker_policy(self):
        entries = {x["id"]:x for x in self.audit["claims"]}
        for code in ("E4","E5","E6"):
            self.assertEqual(entries[code]["status"],"DOCUMENTED_DESIGN_ONLY")
        self.assertEqual(self.audit["next_action"],"OFFLINE_MOCKS_OR_PUBLIC_DOCUMENT_REVIEW_ONLY")

if __name__ == "__main__":
    unittest.main()
