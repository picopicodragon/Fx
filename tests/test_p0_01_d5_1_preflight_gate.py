"""D5-1 offline preflight contract regression tests."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class D51PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "specs/p0_01_d5_1_preflight_gate.json").read_text(encoding="utf-8"))
        cls.d5 = json.loads((ROOT / "specs/p0_01_d5_preexecution_review.json").read_text(encoding="utf-8"))
        cls.obs = json.loads((ROOT / "specs/p0_01_mt4_readonly_observation_plan.json").read_text(encoding="utf-8"))

    def test_preflight_never_authorizes_runtime(self):
        d = self.data
        self.assertEqual(d["phase_1"], "BLOCKED")
        self.assertEqual(d["runtime_go_no_go"], "NO_GO")
        self.assertEqual(d["review_type"], "OFFLINE_DESIGN_ONLY")
        self.assertIs(d["merge_is_not_approval"], True)
        for k in ("broker_verified","production_usable","read_only_ex4_execution_approved",
                  "terminal_execution_approved","orders_generated",
                  "forward_trading_enabled","human_safety_approval"):
            self.assertIs(d[k], False)

    def test_all_eight_items_unapproved(self):
        d = self.data
        self.assertEqual([x["id"] for x in d["items"]], [f"PF{i}" for i in range(1,9)])
        self.assertTrue(all(x["runtime_authorized"] is False for x in d["items"]))
        self.assertIs(d["concurrent_demo_policy_confirmed"], False)
        self.assertIs(d["candidate_b_installed"], False)
        self.assertIs(d["existing_terminal_a_must_be_unchanged"], True)

    def test_no_existing_broker_values_promoted(self):
        self.assertEqual(self.d5["runtime_go_no_go"], "NO_GO")
        self.assertEqual(self.d5["phase_1"], "BLOCKED")
        self.assertEqual(len(self.obs["symbol_status"]), 4)
        for row in self.obs["symbol_status"]:
            self.assertIs(row["production_usable"], False)
            self.assertEqual(len(row["verified_values"]),5)
            self.assertTrue(all(value is None for value in row["verified_values"].values()))

    def test_only_offline_followups_permitted(self):
        d = self.data
        self.assertEqual(set(d["approved_next_actions"]),{"OFFLINE_DOCUMENT_REVIEW","SYNTHETIC_TESTS"})
        self.assertIn("PLACE_MODIFY_CANCEL_OR_CLOSE_ORDER",d["forbidden_operations"])
        self.assertIn("DEPLOY_OR_RUN_EX4",d["forbidden_operations"])
        self.assertIn("CREATE_DEMO_ACCOUNT",d["forbidden_operations"])

if __name__ == "__main__":
    unittest.main()
