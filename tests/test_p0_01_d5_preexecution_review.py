"""P0-01 D5: audit-only review constraints. No terminal/network access."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class D5ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d5 = json.loads((ROOT / "specs/p0_01_d5_preexecution_review.json").read_text(encoding="utf-8"))
        cls.d45 = json.loads((ROOT / "specs/p0_01_d4_5_completion_gate.json").read_text(encoding="utf-8"))
        cls.obs = json.loads((ROOT / "specs/p0_01_mt4_readonly_observation_plan.json").read_text(encoding="utf-8"))

    def test_all_gates_still_blocked_and_no_go(self):
        p = self.d5
        self.assertEqual([g["id"] for g in p["gates"]], ["G1", "G2", "G3", "G4", "G5"])
        self.assertTrue(all(g["status"] in {"BLOCKED_EXTERNAL_POLICY", "NOT_AUTHORIZED", "UNVERIFIED", "REVIEW_REQUIRED"} for g in p["gates"]))
        self.assertEqual(p["runtime_go_no_go"], "NO_GO")
        self.assertEqual(p["phase_1"], "BLOCKED")
        self.assertTrue(p["ci_or_merge_never_authorizes_runtime"])

    def test_permission_flags_and_existing_observation_nulls(self):
        for k in ("broker_verified", "orders_generated", "terminal_execution_approved",
                  "read_only_ex4_execution_approved", "forward_trading_enabled",
                  "human_safety_approval"):
            self.assertIs(self.d5[k], False)
        self.assertTrue(self.d5["verified_values_must_remain_null"])
        for row in self.obs["symbol_status"]:
            self.assertIs(row["production_usable"], False)
            self.assertTrue(all(v is None for v in row["verified_values"].values()))

    def test_offline_completion_not_runtime_approval(self):
        self.assertTrue(self.d45["offline_scope_completed"])
        self.assertEqual(self.d45["phase_1"], "BLOCKED")
        self.assertTrue(self.d5["offline_next_actions_only"])
        self.assertEqual(self.d5["review_kind"], "DOCUMENT_ONLY_NO_RUNTIME")
        self.assertEqual(self.d5["status"], "OFFLINE_REVIEW_COMPLETE_RUNTIME_BLOCKED")

if __name__ == "__main__":
    unittest.main()
