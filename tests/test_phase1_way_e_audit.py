"""Way E snapshot tests; all inputs are repository design registries only."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_phase1_way_e as gate


ROOT = Path(__file__).resolve().parents[1]


class WayEGateAuditTests(unittest.TestCase):
    def setUp(self):
        self.source = {key: gate._read(ROOT, path)
                       for key, path in gate.SOURCES.items()}
        self.register = gate._read(ROOT, gate.REGISTER)

    def audit_with(self, mutate):
        source = copy.deepcopy(self.source)
        mutate(source)
        paths = {path: key for key, path in gate.SOURCES.items()}
        with patch.object(gate, "_read", side_effect=lambda root, path: source[paths[path]]):
            return gate.audit(ROOT, gate.derive_register(ROOT))

    def test_current_snapshot_matches_all_sources_and_stays_blocked(self):
        self.assertEqual(gate.audit(ROOT, self.register), [])
        self.assertEqual([x["id"] for x in self.register["gates"]],
                         ["G2", "G6", "G8", "G7", "G3", "G1", "G5", "G9", "G4"])
        self.assertEqual(self.register["acceptance"]["phase"], "BLOCKED")

    def test_unreviewed_snapshot_edit_is_rejected(self):
        altered = copy.deepcopy(self.register)
        altered["gates"][0]["real_world_verified"] = True
        self.assertIn("SNAPSHOT_MISMATCH", gate.audit(ROOT, altered))

    def test_source_gate_promotion_cannot_be_copied_into_snapshot(self):
        errors = self.audit_with(lambda d: d["gap"]["gaps"][0].update(
            implementation_status="RESOLVED", release_blocker=False,
            real_world_verified=True))
        self.assertIn("GATE_STATE_PROMOTED", errors)

    def test_work_package_and_readiness_promotion_are_rejected(self):
        self.assertIn("WORK_PACKAGE_PROMOTED", self.audit_with(
            lambda d: d["work"]["work_packages"][0].update(
                implementation_allowed=True)))
        self.assertIn("WORK_PACKAGE_PROMOTED", self.audit_with(
            lambda d: d["work"]["work_packages"][0].update(
                separate_human_approval_required=False)))
        self.assertIn("READINESS_PROMOTED", self.audit_with(
            lambda d: d["readiness"]["criteria"][0].update(
                real_evidence_state="COLLECTED")))

    def test_source_and_acceptance_promotion_are_rejected(self):
        self.assertIn("SAFETY_SOURCE_PROMOTED", self.audit_with(
            lambda d: d["recon"]["items"][0].update(
                source_kind="ORIGINAL", implementation_approved=True)))
        self.assertIn("ACCEPTANCE_PROMOTED", self.audit_with(
            lambda d: d["acceptance"]["phases"][0].update(status="ACCEPTED")))

    def test_planned_scenarios_cannot_be_described_as_executed(self):
        self.assertIn("PLANNED_CASES_MISSTATED", self.audit_with(
            lambda d: d["fault"]["test_cases"][0].update(
                execution_status="PASS")))
        self.assertIn("PLANNED_CASES_MISSTATED", self.audit_with(
            lambda d: d["broker"]["test_cases"][0].update(status="PASS")))

    def test_unknown_dependency_and_runtime_go_are_rejected(self):
        self.assertIn("UNKNOWN_DEPENDENCY", self.audit_with(
            lambda d: d["plan"]["gates"][0].update(depends_on=["G10"])))
        self.assertIn("RUNTIME_GATE_PROMOTED", self.audit_with(
            lambda d: d["gap"].update(runtime_go_no_go="GO")))

    def test_cycle_or_work_package_relabel_cannot_hide_in_updated_snapshot(self):
        self.assertIn("DEPENDENCY_ORDER_INVALID", self.audit_with(
            lambda d: d["plan"]["gates"][0].update(depends_on=["G6"])))
        self.assertIn("WORK_PACKAGE_SET_INVALID", self.audit_with(
            lambda d: d["work"]["work_packages"][0].update(
                criterion_id="G2-07")))

    def test_historical_preexecution_labels_are_not_current_gate_subjects(self):
        historical = gate._read(ROOT, "specs/p0_01_d5_preexecution_review.json")
        self.assertNotEqual(historical["gates"][0]["unblock_requires"],
                            self.register["gates"][5]["subject"])
        self.assertEqual(self.register["gates"][5]["source_definition"],
                         "specs/p0_01_d5_25_gap_verification_matrix.json")

    def test_offline_synthetic_sources_have_explicit_spec_and_test_mapping(self):
        trace = json.loads((ROOT / "specs/traceability.json").read_text(encoding="utf-8"))
        mapping = {row["source"]: row for row in trace["offline_synthetic_mappings"]}
        self.assertEqual(set(mapping), {
            "scripts/phase1_synthetic_persistence.py",
            "scripts/check_phase1_way_e.py",
            "scripts/phase1_way_e_synthetic_review.py",
            "scripts/phase1_h3_synthetic_anchor.py",
            "scripts/phase1_three_pair_synthetic_risk.py",
            "scripts/review_mt4_manual_symbol_3p_v3.py",
        })
        for source, row in mapping.items():
            with self.subTest(source=source):
                self.assertTrue((ROOT / source).is_file())
                self.assertTrue(row["spec_ids"])
                self.assertTrue(row["tests"])
                self.assertIs(row["production_authorized"], False)
                self.assertTrue(all((ROOT / path).is_file() for path in row["tests"]))

    def test_way_e_tasks_are_tracked_without_module_or_phase_acceptance(self):
        acceptance = gate._read(ROOT, "specs/acceptance_registry.json")
        tasks = {row["id"]: row for row in acceptance["tasks"]}
        module = next(row for row in acceptance["modules"]
                      if row["id"] == "M-P1-FOUNDATION-DESIGN")
        phase = next(row for row in acceptance["phases"]
                     if row["id"] == "PHASE-1")
        for i in range(1, 7):
            ident = f"E-GATE-{i:02}"
            self.assertIn(ident, tasks)
            self.assertIn(ident, module["task_ids"])
            self.assertIn(tasks[ident]["status"], {"TESTED", "IN_PROGRESS"})
            self.assertIsNone(tasks[ident]["approval"])
        self.assertEqual(module["status"], "BLOCKED")
        self.assertIsNone(module["approval"])
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
