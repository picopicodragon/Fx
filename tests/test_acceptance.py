"""Test structural acceptance gate; does not validate user approval identity."""
import unittest

from scripts.check_acceptance import check_registry


def example():
    return {
        "schema_version": 1,
        "tasks": [{"id": "T1", "spec_ids": ["Q6"], "module_id": "M1",
                   "status": "ACCEPTED", "evidence": ["ci/test-123"]}],
        "modules": [{"id": "M1", "safety_critical": True, "task_ids": ["T1"],
                     "status": "TESTED", "evidence": ["integration/123"], "approval": None}],
        "phases": [{"id": "PHASE-1", "module_ids": ["M1"], "status": "IN_PROGRESS",
                    "evidence": [], "approval": None}],
    }


def approve():
    return {"actor": "maintainer", "approved_at": "2026-10-15T12:00:00+09:00",
            "decision_ref": "DECISIONS.md#example"}


class AcceptanceTests(unittest.TestCase):
    def test_default_in_progress_is_valid(self):
        self.assertEqual(check_registry(example()), [])

    def test_safety_module_cannot_accept_without_human_approval(self):
        d = example()
        d["modules"][0]["status"] = "ACCEPTED"
        self.assertIn("human approval required", "\n".join(check_registry(d)))

    def test_phase_cannot_accept_unapproved_module(self):
        d = example()
        d["phases"][0].update(status="ACCEPTED", evidence=["phase/check"], approval=approve())
        self.assertIn("before every module", "\n".join(check_registry(d)))

    def test_phase_cannot_accept_without_human_approval(self):
        d = example()
        d["modules"][0].update(status="ACCEPTED", approval=approve())
        d["phases"][0].update(status="ACCEPTED", evidence=["phase/check"])
        self.assertIn("human approval required", "\n".join(check_registry(d)))

    def test_acceptance_chain_with_evidence_and_approvals(self):
        d = example()
        d["modules"][0].update(status="ACCEPTED", approval=approve())
        d["phases"][0].update(status="ACCEPTED", evidence=["phase/check"],
                              approval=approve())
        self.assertEqual(check_registry(d), [])

    def test_tasks_not_accepted_block_module(self):
        d = example()
        d["tasks"][0]["status"] = "IN_PROGRESS"
        d["modules"][0].update(status="ACCEPTED", approval=approve())
        self.assertIn("before every task", "\n".join(check_registry(d)))


if __name__ == "__main__":
    unittest.main()
