"""P1-06: offline structural audit of Phase 1 status, not safety acceptance."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class PhaseOneAuditTests(unittest.TestCase):
    def test_phase_one_is_explicitly_blocked_and_not_approved(self):
        d = read_json("specs/acceptance_registry.json")
        phases = {x["id"]: x for x in d["phases"]}
        phase = phases["PHASE-1"]
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])
        self.assertIn("M-P1-FOUNDATION-DESIGN", phase["module_ids"])
        for n in range(2, 7):
            with self.subTest(phase=n):
                self.assertEqual(phases[f"PHASE-{n}"]["status"], "NOT_STARTED")

    def test_design_tasks_do_not_count_as_accepted_modules(self):
        d = read_json("specs/acceptance_registry.json")
        tasks = {t["id"]: t for t in d["tasks"]}
        self.assertEqual(set(tasks),
                         {f"P1-0{i}" for i in range(1, 7)}
                         | {f"E-GATE-{i:02}" for i in range(1, 7)}
                         | {f"H1-{letter}" for letter in "ABCDE"})
        self.assertEqual(tasks["P1-01"]["status"], "BLOCKED")
        self.assertEqual(tasks["P1-06"]["status"], "IN_PROGRESS")
        for i in range(2, 6):
            with self.subTest(task=i):
                task = tasks[f"P1-0{i}"]
                self.assertEqual(task["status"], "TESTED")
                self.assertTrue(task["evidence"])
                self.assertIn("only", task["scope_note"])
                self.assertIsNone(task["approval"])
        for i in range(1, 7):
            with self.subTest(way_e_task=i):
                task = tasks[f"E-GATE-{i:02}"]
                self.assertEqual(task["status"],
                                 "IN_PROGRESS" if i in (4, 6) else "TESTED")
                self.assertTrue(task["evidence"])
                self.assertIsNone(task["approval"])
        for letter in "ABCD":
            with self.subTest(h1_task=letter):
                task = tasks[f"H1-{letter}"]
                self.assertEqual(task["status"], "BLOCKED")
                self.assertTrue(task["evidence"])
                self.assertIsNone(task["approval"])
        self.assertEqual(tasks["H1-E"]["status"], "IN_PROGRESS")
        self.assertIsNone(tasks["H1-E"]["approval"])
        modules = d["modules"]
        self.assertEqual(len(modules), 1)
        self.assertTrue(modules[0]["safety_critical"])
        self.assertEqual(modules[0]["status"], "BLOCKED")
        self.assertIsNone(modules[0]["approval"])
        self.assertEqual(set(modules[0]["task_ids"]), set(tasks))

    def test_planned_fault_and_mock_cases_are_not_misreported_as_run(self):
        expected = {
            "specs/p1_04_fault_matrix.json": (26, "execution_status"),
            "specs/p1_05_mock_broker_scenarios.json": (27, "status"),
        }
        for path, (count, field) in expected.items():
            with self.subTest(path=path):
                cases = read_json(path)["test_cases"]
                self.assertEqual(len(cases), count)
                self.assertTrue(all(x[field] == "NOT_EXECUTED" for x in cases))
                self.assertTrue(all(not x["owner_safety_approved"] for x in cases))

    def test_register_adheres_to_existing_acceptance_gate(self):
        from scripts.check_acceptance import check_registry
        d = read_json("specs/acceptance_registry.json")
        self.assertEqual(check_registry(d), [])


if __name__ == "__main__":
    unittest.main()
