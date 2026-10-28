"""D4-5 completion contract: success in offline tests never authorizes MT4."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "specs/p0_01_d4_5_completion_gate.json"
OBS = ROOT / "specs/p0_01_mt4_readonly_observation_plan.json"

class CompletionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = json.loads(GATE.read_text(encoding="utf-8"))
        cls.obs = json.loads(OBS.read_text(encoding="utf-8"))

    def test_offline_completion_does_not_grant_authority(self):
        g = self.gate
        self.assertIs(g["offline_scope_completed"], True)
        self.assertEqual(g["assessment"], "OFFLINE_TEST_SCOPE_COMPLETED_NOT_BROKER_VERIFIED")
        self.assertEqual(g["phase_1"], "BLOCKED")
        for key in ("broker_verified", "terminal_execution_approved",
                    "read_only_ex4_execution_approved", "orders_generated",
                    "forward_trading_enabled", "human_safety_approval"):
            self.assertIs(g[key], False)

    def test_evidence_and_next_action_boundaries(self):
        self.assertEqual(self.gate["pr_evidence"], list(range(107, 113)))
        self.assertEqual(self.gate["eligible_next_action"], "OFFLINE_DESIGN_AND_TEST_ONLY")
        self.assertIs(self.gate["promotion_from_ci_or_merge_prohibited"], True)
        self.assertEqual(len(self.gate["blocked_gates"]), 5)

    def test_all_observed_values_still_pending(self):
        rows = self.obs["symbol_status"]
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertIs(row["production_usable"], False)
            self.assertEqual(len(row["verified_values"]), 5)
            self.assertTrue(all(v is None for v in row["verified_values"].values()))

if __name__ == "__main__":
    unittest.main()
