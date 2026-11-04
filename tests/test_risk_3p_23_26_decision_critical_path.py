"""RISK-3P-23..26 review DAG and human approval boundary tests."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_23_26_decision_critical_path as mod


class CriticalPathOwnerReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = mod._data(mod.ROOT, None)

    def mutation(self, path, edit, expected):
        sources = copy.deepcopy(self.documents)
        edit(sources[path])
        issues = mod.audit(injected=sources)
        self.assertIn(expected, issues, issues)

    def test_baseline_dependency_plan_and_fixed_blocker_report(self):
        self.assertEqual(mod.audit(), [])
        report = mod.snapshot()
        self.assertEqual(report["readiness"],
                         "BLOCKED_OWNER_ORIGINALS_AND_G1_REAL_EVIDENCE")
        self.assertEqual(report["owner_decisions_pending"], 43)
        self.assertEqual(report["g1_real_fields_verified"], 0)
        self.assertEqual(report["fx_saf_originals_reviewed"], 0)
        self.assertEqual(tuple(report["proposed_next_human_review_entries"]),
                         mod.HUMAN_FIRST)
        self.assertFalse(report["order_allowed"])
        self.assertFalse(report["stop_release_allowed"])
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")
        self.assertEqual(report["phase_1"], "BLOCKED")

    def test_four_cohorts_cover_all_forms_and_in_dependency_priority(self):
        x = self.documents[mod.PLAN]["cohorts"]
        self.assertEqual(len(x), 4)
        self.assertEqual([y["sequence"] for y in x], [1, 2, 3, 4])
        self.assertEqual(sorted(form for group in x for form in group["forms"]),
                         list(mod.EXPECTED_FORMS))
        self.mutation(mod.PLAN, lambda p: p["cohorts"][2]["forms"].pop(),
                      "FOUR_COHORT_SCOPE_DRIFT")
        self.mutation(mod.PLAN, lambda p: p["cohorts"][1].update(
            requires_human_spec_decision=False),
            "COHORT_FALSELY_REVIEWED_OR_OUT_OF_ORDER:"
            "D2_PROTECTION_RECONCILIATION_AND_GROSS")

    def test_all_twelve_stages_proposed_and_none_executable(self):
        stages = self.documents[mod.PLAN]["proposed_dependency_nodes"]
        self.assertEqual(len(stages), 12)
        self.assertEqual(
            mod.topological_nodes(stages),
            tuple(node[0] for node in mod.NODES),
        )
        self.assertTrue(all(not step["execution_permitted"] for step in stages))
        self.mutation(mod.PLAN, lambda p: p["proposed_dependency_nodes"][5]
                      .update(execution_permitted=True),
                      "DEPENDENCY_OR_AUTHORITY_DRIFT:P06_G1_PRIMARY_OBSERVATION")

    def test_no_approval_safety_rollback_or_main_gate_weakening(self):
        for flag, expected in (
            ("real_mt4_observation_authorized",
             "FALSE_OPERATIONAL_AUTHORITY:real_mt4_observation_authorized"),
            ("production_authorized",
             "FALSE_OPERATIONAL_AUTHORITY:production_authorized"),
            ("orders_authorized",
             "FALSE_OPERATIONAL_AUTHORITY:orders_authorized"),
            ("stop_release_authorized",
             "FALSE_OPERATIONAL_AUTHORITY:stop_release_authorized"),
            ("automated_owner_approval_authorized",
             "FALSE_OPERATIONAL_AUTHORITY:automated_owner_approval_authorized"),
            ("safety_gate_overrides_authorized",
             "FALSE_OPERATIONAL_AUTHORITY:safety_gate_overrides_authorized"),
        ):
            with self.subTest(flag=flag):
                self.mutation(mod.PLAN, lambda d, k=flag: d.update({k: True}),
                              expected)
        self.mutation(mod.PLAN, lambda p: p.update(
            potential_subsequent_branch_release_prohibited=False),
            "FALSE_OPERATIONAL_AUTHORITY:potential_subsequent_branch_release_prohibited")

    def test_no_go_still_required_if_draft_preparation_marked_complete(self):
        self.mutation(mod.PLAN, lambda p: p.update(runtime_go_no_go="GO"),
                      "STOP_OR_APPROVAL_STATUS_PROMOTED")
        self.mutation(mod.PLAN, lambda p: p.update(phase_1="ACCEPTED"),
                      "STOP_OR_APPROVAL_STATUS_PROMOTED")
        self.mutation(mod.PLAN, lambda p: p.update(safety_hold_latched=False),
                      "STOP_OR_APPROVAL_STATUS_PROMOTED")
        self.mutation(mod.PLAN, lambda p: p.update(
            verified_values={"EUR/USD": "fake"}),
            "STOP_OR_APPROVAL_STATUS_PROMOTED")

    def test_hard_caps_and_old_g1_history_cannot_change(self):
        self.mutation(mod.PLAN, lambda p: p["safety_caps"].update(
            combined_risk="0.02"), "HARD_CAPS_DRIFT")
        self.mutation(mod.PLAN, lambda p: p.update(g1_fields_proved=15),
                      "FORM_OR_G1_COUNTS_PROMOTED")
        self.mutation(mod.PLAN, lambda p: p.update(
            existing_g1_scope_status="NEW_3x5_VERIFIED"),
            "FORM_OR_G1_COUNTS_PROMOTED")

    def test_cycle_detected_even_if_all_node_names_are_plausible(self):
        self.mutation(mod.PLAN, lambda p: p["proposed_dependency_nodes"][0]
                      ["requires"].append("P12_MODULE_PHASE_ACCEPTANCE"),
                      "INVALID_OR_CYCLIC_DEPENDENCIES")
        self.mutation(mod.PLAN, lambda p: p["proposed_dependency_nodes"][3]
                      ["requires"].append("P99_NOT_PRESENT"),
                      "INVALID_OR_CYCLIC_DEPENDENCIES")

    def test_missing_edges_are_denied_no_false_acceleration(self):
        self.mutation(mod.PLAN, lambda p: p["proposed_dependency_nodes"][6]
                      .update(requires=[]),
                      "DEPENDENCY_OR_AUTHORITY_DRIFT:P07_G1_INDEPENDENT_VERIFICATION")
        self.mutation(mod.PLAN, lambda p: p["proposed_dependency_nodes"].pop(),
                      "STAGE_SET_DRIFT")
        self.mutation(mod.PLAN, lambda p: p["proposed_dependency_nodes"][1]
                      .update(status="APPROVED"),
                      "DEPENDENCY_OR_AUTHORITY_DRIFT:P02_OWNER_VERIFY_SOURCE_ORIGINALS")

    def test_no_stage_can_be_marked_real_environment_permission(self):
        for i in range(12):
            with self.subTest(i=i):
                ident = self.documents[mod.PLAN]["proposed_dependency_nodes"][i]["id"]
                self.mutation(mod.PLAN, lambda p, j=i:
                              p["proposed_dependency_nodes"][j].update(
                                  execution_permitted=True),
                              "DEPENDENCY_OR_AUTHORITY_DRIFT:" + ident)

    def test_original_source_safety_and_acceptance_must_remain_blocked(self):
        self.mutation(mod.SOURCE, lambda p: p["items"][0].update(
            source_review="VERIFIED"),
            "ORIGINAL_SAFETY_SOURCES_NOT_UNRESOLVED")
        self.mutation(mod.GATES, lambda p: p["gaps"][5].update(
            real_world_verified=True),
            "FORMAL_GATES_NOT_ALL_BLOCKED")
        self.mutation(mod.ACCEPT, lambda p: p["phases"][0].update(
            status="ACCEPTED", approval={"fake": "yes"}),
            "Q110_MODULE_OR_PHASE_FALSELY_ACCEPTED")

    def test_form_and_g1_pending_provenance_not_lost(self):
        self.mutation(mod.DOCKET, lambda p: p["decisions"][0].update(
            owner_decision="APPROVED"),
            "UPSTREAM_OWNER_DECISIONS_NOT_PENDING")
        self.mutation(mod.G1, lambda p: p["rows"][0].update(
            real_world_verified=True),
            "UPSTREAM_G1_NOT_PENDING")

    def test_schema_and_declared_sources_checked(self):
        self.mutation(mod.PLAN, lambda p: p.update(schema_version=2),
                      "PLAN_ID_OR_SOURCE_INVALID")
        self.mutation(mod.PLAN, lambda p: p.update(source_docket="missing.json"),
                      "PLAN_ID_OR_SOURCE_INVALID")
        self.mutation(mod.PLAN, lambda p: p.update(
            pr_merge_is_not_form_approval=False),
            "FALSE_POLICY_RELAXATION:pr_merge_is_not_form_approval")

    def test_graph_rejects_duplicate_dangling_and_ill_typed_links(self):
        base = copy.deepcopy(self.documents[mod.PLAN]["proposed_dependency_nodes"])
        cases = [
            (lambda a: a.append(copy.deepcopy(a[1]))),
            (lambda a: a[1].update(requires=["P01_DOCUMENTARY_REVIEW_PACKET"] * 2)),
            (lambda a: a[1].update(requires=[True])),
            (lambda a: a[1].update(requires=["MISSING"])),
            (lambda a: a[1].update(requires="P01_DOCUMENTARY_REVIEW_PACKET")),
        ]
        for i, mutate in enumerate(cases):
            with self.subTest(index=i):
                x = copy.deepcopy(base)
                mutate(x)
                with self.assertRaises(ValueError):
                    mod.topological_nodes(x)

    def test_invalid_packet_fails_closed(self):
        d = copy.deepcopy(self.documents)
        d[mod.PLAN] = []
        self.assertEqual(mod.audit(injected=d), ["INVALID_CRITICAL_PATH_PLAN"])


if __name__ == "__main__":
    unittest.main()
