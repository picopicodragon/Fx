"""D5-36: design readiness criteria, dependencies and human approval gate tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_36_readiness_gate import (
    _FALSE, _SPEC, _IDS, _APPROVALS, _BUNDLE_FIELDS,
    review_d536_readiness,
)

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def plan(): return read("p0_01_d5_36_acceptance_contract.json")
def readiness(): return read("p0_01_d5_36_readiness_register.json")
def actions(): return read("p0_01_d5_36_synthetic_authorization.json")


def predecessors():
    names = (
        "p0_01_d5_35_handoff_contract.json",
        "p0_01_d5_34_lineage_contract.json",
        "p0_01_d5_33_proof_boundary_contract.json",
        "p0_01_d5_32_crash_matrix_contract.json",
        "p0_01_d5_31_protocol_privacy_contract.json",
        "p0_01_d5_17_evidence_reconciliation_status.json",
        "p0_01_d5_25_gap_verification_matrix.json",
        "p0_01_d5_32_synthetic_fixture.json",
        "p0_01_d5_33_synthetic_fixture.json",
        "p0_01_d5_34_synthetic_fixture.json",
        "p0_01_d5_35_synthetic_fixture.json",
    )
    return dict(zip(_BUNDLE_FIELDS, (read(n) for n in names)))


class D536ReadinessTests(TestCase):
    def check(self, expected, p=_DEFAULT, r=_DEFAULT, a=_DEFAULT, b=_DEFAULT):
        value = review_d536_readiness(
            plan() if p is _DEFAULT else p,
            readiness() if r is _DEFAULT else r,
            actions() if a is _DEFAULT else a,
            predecessors() if b is _DEFAULT else b,
        )
        self.assertEqual(value["status"], expected)
        self.assertEqual(value["phase_1"], "BLOCKED")
        self.assertEqual(value["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(value["verified_values"])
        self.assertEqual(value["effective_approved_actions"], [])
        self.assertIs(value["safety_hold_latched"], True)
        self.assertEqual(value["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(value["real_acceptance_criteria_completed"], 0)
        self.assertEqual(value["g2_design_criteria_count"], 7)
        self.assertEqual(value["g6_design_criteria_count"], 8)
        for key in ("current_positions", "current_pending_orders", "current_ea_state"):
            self.assertEqual(value[key], "UNKNOWN")
        for key in _FALSE:
            self.assertIs(value[key], False, key)
        self.assertEqual(set(value), set(_FALSE) | {
            "status", "d535_status", "g2_design_criteria_count",
            "g6_design_criteria_count", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return value

    def test_default_g2_g6_all_blocked_and_design_only(self):
        v = self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")
        self.assertEqual(v["d535_status"],
                         "D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED")

    def test_exact_15_criteria_in_spec_and_contract(self):
        p = plan()
        self.assertEqual(len(p["criteria"]), 15)
        self.assertEqual([r["criterion_id"] for r in p["criteria"]], list(_IDS))
        self.assertEqual([r["gate"] for r in p["criteria"]].count("G2"), 7)
        self.assertEqual([r["gate"] for r in p["criteria"]].count("G6"), 8)
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_all_require_separate_user_approval(self):
        self.assertTrue(all(r["requires_separate_user_approval"] is True
                            for r in plan()["criteria"]))
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_internal_dependencies_are_earlier_in_design_order(self):
        seq = list(_IDS)
        for row in plan()["criteria"]:
            for dep in row["depends_on"]:
                self.assertLess(seq.index(dep), seq.index(row["criterion_id"]))
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_external_g7_g8_remain_unresolved(self):
        dependencies = {
            gate for row in plan()["criteria"]
            for gate in row["external_gate_dependencies"]
        }
        self.assertEqual(dependencies, {"G7", "G8"})
        self.assertEqual(readiness()["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_g2_private_broker_identity_is_not_public_metadata(self):
        self.assertEqual(plan()["criteria"][0]["privacy_class"], "PRIVATE_ONLY")
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_g2_publication_boundary_requires_private_store_first(self):
        row = next(x for x in plan()["criteria"]
                   if x["criterion_id"] == "G2-07")
        self.assertIn("G2-06", row["depends_on"])
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_g6_recovery_depends_on_anchor_journal_writer(self):
        row = next(x for x in plan()["criteria"]
                   if x["criterion_id"] == "G6-06")
        self.assertEqual(row["depends_on"], ["G6-02", "G6-04", "G6-05"])
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_g6_clock_and_approvals_block_later_recovery(self):
        rows = {x["criterion_id"]: x for x in plan()["criteria"]}
        self.assertIn("G7", rows["G6-07"]["external_gate_dependencies"])
        self.assertIn("G8", rows["G6-08"]["external_gate_dependencies"])
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_missing_requirement_entry_denied(self):
        p = plan()
        p["criteria"].pop()
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_duplicate_requirement_denied(self):
        p = plan()
        p["criteria"][1] = copy.deepcopy(p["criteria"][0])
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_reordered_criteria_denied(self):
        p = plan()
        p["criteria"][1], p["criteria"][2] = (
            p["criteria"][2], p["criteria"][1])
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_change_verification_boundary_denied(self):
        p = plan()
        p["criteria"][0]["verification_boundary"] = "REAL_MT4_RUN"
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_change_success_condition_denied(self):
        p = plan()
        p["criteria"][0]["success_condition"] = "AUTO_GO"
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_change_privacy_class_denied(self):
        p = plan()
        p["criteria"][0]["privacy_class"] = "PUBLIC_METADATA_ONLY"
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_change_dependency_denied(self):
        p = plan()
        p["criteria"][-1]["depends_on"] = []
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_fake_no_approval_needed_denied(self):
        p = plan()
        p["criteria"][0]["requires_separate_user_approval"] = False
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_extra_permission_on_criterion_denied(self):
        p = plan()
        p["criteria"][0]["live_trading"] = True
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_contract_real_g2_resolved_claim_denied(self):
        p = plan()
        p["real_g2_resolved"] = True
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_contract_real_g6_resolved_claim_denied(self):
        p = plan()
        p["real_g6_resolved"] = True
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_contract_mt4_approved_claim_denied(self):
        p = plan()
        p["mt4_and_host_approved"] = True
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_contract_go_denied(self):
        p = plan()
        p["runtime_go_no_go"] = "GO"
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_contract_verified_values_denied(self):
        p = plan()
        p["verified_values"] = {}
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_contract_schema_bool_denied(self):
        p = plan()
        p["schema_version"] = True
        self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_readiness_registration_reordered_denied(self):
        r = readiness()
        r["criteria"].reverse()
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_readiness_registration_duplicate_denied(self):
        r = readiness()
        r["criteria"][1]["criterion_id"] = "G2-01"
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_readiness_observation_date_not_permitted(self):
        r = readiness()
        r["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_readiness_all_gates_unchanged(self):
        r = readiness()
        r["unresolved_gates"] = ["G2", "G6"]
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_readiness_fake_account_identity_denied(self):
        r = readiness()
        r["account_identity_consistency"] = "RECONCILED"
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_readiness_fake_broker_verified_denied(self):
        r = readiness()
        r["broker_verified"] = True
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_readiness_missing_stop_latch_denied(self):
        r = readiness()
        r["safety_hold_latched"] = False
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_readiness_extra_account_number_field_denied(self):
        r = readiness()
        r["account_number"] = "SYNTHETIC_PLACEHOLDER"
        self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=r)

    def test_action_invalid_boolean_as_integer_denied(self):
        a = actions()
        a["approvals"]["host_io"] = 0
        self.check("D536_ACTION_SCHEMA_REJECTED_FAIL_CLOSED", a=a)

    def test_action_extra_unknown_permission_denied(self):
        a = actions()
        a["approvals"]["force_buy"] = True
        self.check("D536_ACTION_SCHEMA_REJECTED_FAIL_CLOSED", a=a)

    def test_action_simulation_only_false_denied(self):
        a = actions()
        a["simulation_only"] = False
        self.check("D536_ACTION_SCHEMA_REJECTED_FAIL_CLOSED", a=a)

    def test_action_top_level_extraneous_denied(self):
        a = actions()
        a["approval_signed"] = True
        self.check("D536_ACTION_SCHEMA_REJECTED_FAIL_CLOSED", a=a)

    def test_predecessor_missing_bundle_field_denied(self):
        b = predecessors()
        b.pop("d535_case")
        self.check("D536_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", b=b)

    def test_predecessor_extra_live_credentials_denied(self):
        b = predecessors()
        b["broker_credentials"] = "SYNTHETIC_PLACEHOLDER"
        self.check("D536_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", b=b)

    def test_predecessor_fake_accepted_g6_denied(self):
        b = predecessors()
        b["d535_case"]["transition"]["event"] = "ROTATION"
        self.check("D536_PREDECESSOR_NOT_COHERENT_NO_GO", b=b)

    def test_predecessor_fake_public_export_denied(self):
        b = predecessors()
        b["d535_case"]["publication_surfaces"][0][
            "private_payload_present"] = True
        self.check("D536_PREDECESSOR_NOT_COHERENT_NO_GO", b=b)

    def test_predecessor_fake_broker_verified_denied(self):
        b = predecessors()
        b["old_evidence"]["positions_status"] = "ABSENT"
        self.check("D536_PREDECESSOR_NOT_COHERENT_NO_GO", b=b)

    def test_forged_child_go_rejected(self):
        with patch(
            "scripts.p0_01_d5_36_readiness_gate.review_d535_handoff",
            return_value={"status":
                "D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED",
                "runtime_go_no_go": "GO"},
        ):
            self.check("D536_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_order_authorized_rejected(self):
        from scripts.p0_01_d5_35_handoff_review import (
            review_d535_handoff as original,
        )
        b = predecessors()
        child = original(*(b[k] for k in _BUNDLE_FIELDS))
        child["order_authorized"] = True
        with patch(
            "scripts.p0_01_d5_36_readiness_gate.review_d535_handoff",
            return_value=child,
        ):
            self.check("D536_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_coherent_status_is_not_approval(self):
        from scripts.p0_01_d5_35_handoff_review import (
            review_d535_handoff as original,
        )
        b = predecessors()
        child = original(*(b[k] for k in _BUNDLE_FIELDS))
        child["status"] = "GO"
        with patch(
            "scripts.p0_01_d5_36_readiness_gate.review_d535_handoff",
            return_value=child,
        ):
            self.check("D536_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_invalid_contract_inputs_denied(self):
        for value in (None, [], {}, True, "GO"):
            with self.subTest(value=repr(value)):
                self.check("D536_CONTRACT_REJECTED_FAIL_CLOSED", p=value)

    def test_invalid_readiness_inputs_denied(self):
        for value in (None, [], {}, True, "GO"):
            with self.subTest(value=repr(value)):
                self.check("D536_READINESS_REGISTER_REJECTED_FAIL_CLOSED", r=value)

    def test_invalid_action_inputs_denied(self):
        for value in (None, [], {}, True, "GO"):
            with self.subTest(value=repr(value)):
                self.check("D536_ACTION_SCHEMA_REJECTED_FAIL_CLOSED", a=value)

    def test_pure_review_never_accesses_host_files(self):
        args = (plan(), readiness(), actions(), predecessors())
        with patch("builtins.open", side_effect=AssertionError("I/O prohibited")):
            result = review_d536_readiness(*args)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_no_mutation_of_inputs(self):
        args = (plan(), readiness(), actions(), predecessors())
        original = copy.deepcopy(args)
        review_d536_readiness(*args)
        self.assertEqual(args, original)

    def test_repeated_calls_never_store_permission(self):
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")
        a = actions()
        a["approvals"]["mt4_launch"] = True
        self.check("D536_UNAUTHORIZED_ACTION_CLAIM_NO_GO", a=a)
        self.check("D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED")

    def test_status_all_gates_unresolved(self):
        s = read("p0_01_d5_36_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "terminal_execution_approved",
                  "host_io_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)


def _criterion_false_claim_test(index, field, value):
    def _test(self):
        reg = readiness()
        reg["criteria"][index][field] = value
        self.check("D536_FALSE_REAL_READINESS_CLAIM_NO_GO", r=reg)
    return _test


def _permission_claim_test(field):
    def _test(self):
        a = actions()
        a["approvals"][field] = True
        self.check("D536_UNAUTHORIZED_ACTION_CLAIM_NO_GO", a=a)
    return _test


for _index, _ident in enumerate(_IDS):
    for _field, _value in (
        ("implementation_state", "IMPLEMENTED"),
        ("real_evidence_state", "VERIFIED"),
        ("human_approval_state", "GRANTED"),
        ("acceptance_state", "ACCEPTED"),
    ):
        _name = ("test_no_promote_" + _ident.replace("-", "_")
                 + "_" + _field)
        setattr(D536ReadinessTests, _name,
                _criterion_false_claim_test(_index, _field, _value))

for _name in _APPROVALS:
    setattr(D536ReadinessTests, "test_no_action_" + _name,
            _permission_claim_test(_name))


if __name__ == "__main__":
    main()
