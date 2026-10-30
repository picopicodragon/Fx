"""D5-37: synthetic priority/dependency plan with immutable NO_GO safety."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_37_workplan_review import (
    _FALSE, _ORDER, review_d537_workplan,
)
from scripts.p0_01_d5_36_readiness_gate import (
    _BUNDLE_FIELDS, _APPROVALS,
)

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def plan(): return read("p0_01_d5_37_workplan_contract.json")
def track(): return read("p0_01_d5_37_synthetic_tracking.json")
def c36(): return read("p0_01_d5_36_acceptance_contract.json")
def reg36(): return read("p0_01_d5_36_readiness_register.json")
def auth36(): return read("p0_01_d5_36_synthetic_authorization.json")


def previous():
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
    return dict(zip(_BUNDLE_FIELDS, (read(x) for x in names)))


class D537WorkplanTests(TestCase):
    def check(self, expected, p=_DEFAULT, t=_DEFAULT, c=_DEFAULT,
              r=_DEFAULT, a=_DEFAULT, b=_DEFAULT):
        value = review_d537_workplan(
            plan() if p is _DEFAULT else p,
            track() if t is _DEFAULT else t,
            c36() if c is _DEFAULT else c,
            reg36() if r is _DEFAULT else r,
            auth36() if a is _DEFAULT else a,
            previous() if b is _DEFAULT else b,
        )
        self.assertEqual(value["status"], expected)
        self.assertEqual(value["phase_1"], "BLOCKED")
        self.assertEqual(value["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(value["verified_values"])
        self.assertEqual(value["effective_approved_actions"], [])
        self.assertIs(value["safety_hold_latched"], True)
        self.assertEqual(value["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(value["work_packages_planned"], 15)
        self.assertEqual(value["work_packages_executed"], 0)
        self.assertEqual(value["real_acceptance_criteria_completed"], 0)
        for name in ("current_positions", "current_pending_orders",
                     "current_ea_state"):
            self.assertEqual(value[name], "UNKNOWN")
        for name in _FALSE:
            self.assertIs(value[name], False, name)
        self.assertEqual(set(value), set(_FALSE) | {
            "status", "d536_status", "work_packages_planned",
            "work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return value

    def test_baseline_all_15_planned_zero_executed(self):
        v = self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")
        self.assertEqual(
            v["d536_status"],
            "D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED",
        )

    def test_privacy_protection_first_design_priority(self):
        self.assertEqual([x["criterion_id"] for x in plan()["work_packages"][:2]],
                         ["G2-06", "G2-07"])
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_real_mt4_evidence_collection_not_authorized_by_order(self):
        self.assertTrue(all(not x["implementation_allowed"]
                            for x in plan()["work_packages"]))
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_design_plan_is_topologically_ordered(self):
        entries = plan()["work_packages"]
        seen = set()
        for row in entries:
            self.assertTrue(set(row["depends_on"]).issubset(seen))
            seen.add(row["criterion_id"])
        self.assertEqual(len(seen), 15)
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_all_specification_ids_covered_exactly_once(self):
        self.assertEqual(
            [x["criterion_id"] for x in plan()["work_packages"]],
            list(_ORDER),
        )
        self.assertEqual(len(set(_ORDER)), 15)
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_all_future_evidence_is_label_not_real_data(self):
        entries = plan()["work_packages"]
        self.assertTrue(all(
            x["future_acceptance_evidence"].isupper()
            and x["preparation_state"] == "DESIGN_NOT_STARTED"
            and x["real_evidence_collected"] is False
            for x in entries
        ))
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_external_g7_g8_still_block(self):
        dependencies = set(sum((
            x["external_gate_dependencies"] for x in plan()["work_packages"]
        ), []))
        self.assertEqual(dependencies, {"G7", "G8"})
        self.assertFalse(track()["external_g7_verified"])
        self.assertFalse(track()["external_g8_verified"])
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_single_mt4_identity_remains_unknown(self):
        self.assertEqual(track()["account_identity_consistency"],
                         "NOT_RECONCILED")
        self.assertEqual(track()["current_positions"], "UNKNOWN")
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_changing_plan_source_spec_denied(self):
        p = plan()
        p["source_spec"] = "VERIFIED"
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_reordering_work_packages_denied(self):
        p = plan()
        p["work_packages"][0], p["work_packages"][1] = (
            p["work_packages"][1], p["work_packages"][0])
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_duplicate_work_package_denied(self):
        p = plan()
        p["work_packages"][1] = copy.deepcopy(p["work_packages"][0])
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_missing_work_package_denied(self):
        p = plan()
        p["work_packages"].pop()
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_extra_work_package_denied(self):
        p = plan()
        p["work_packages"].append(copy.deepcopy(p["work_packages"][0]))
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_change_dependency_denied(self):
        p = plan()
        next(x for x in p["work_packages"]
             if x["criterion_id"] == "G6-06")["depends_on"] = []
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_remove_external_dependency_denied(self):
        p = plan()
        next(x for x in p["work_packages"]
             if x["criterion_id"] == "G2-07")["external_gate_dependencies"] = []
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_change_private_evidence_to_public_denied(self):
        p = plan()
        next(x for x in p["work_packages"]
             if x["criterion_id"] == "G2-01")["privacy_class"] = (
                 "PUBLIC_METADATA_ONLY")
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_forged_acceptance_evidence_label_denied(self):
        p = plan()
        p["work_packages"][0]["future_acceptance_evidence"] = "REAL_APPROVED"
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_forged_real_broker_proof_denied(self):
        p = plan()
        p["work_packages"][6]["broker_verified"] = True
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_inferred_human_approval_denied(self):
        p = plan()
        p["human_approvals_recorded"] = True
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_plan_runtime_go_denied(self):
        p = plan()
        p["runtime_go_no_go"] = "GO"
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_plan_verified_values_denied(self):
        p = plan()
        p["verified_values"] = {}
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_plan_all_gates_must_remain_unresolved(self):
        p = plan()
        p["unresolved_gates"] = ["G2", "G6"]
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_plan_approval_not_optional(self):
        p = plan()
        p["work_packages"][0]["separate_human_approval_required"] = False
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_plan_boolean_as_rank_denied(self):
        p = plan()
        p["work_packages"][0]["planning_rank"] = True
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_plan_not_started_does_not_mean_complete(self):
        p = plan()
        p["work_packages"][0]["preparation_state"] = "COMPLETE"
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)

    def test_tracking_missing_row_denied(self):
        t = track()
        t["work_packages"].pop()
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_tracking_duplicate_row_denied(self):
        t = track()
        t["work_packages"][1] = copy.deepcopy(t["work_packages"][0])
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_tracking_reordered_row_denied(self):
        t = track()
        t["work_packages"].reverse()
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_tracking_extra_secret_field_denied(self):
        t = track()
        t["account_number"] = "SYNTHETIC_SECRET"
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_tracking_real_account_identity_denied(self):
        t = track()
        t["account_identity_consistency"] = "RECONCILED"
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_tracking_rejects_non_boolean_permission(self):
        t = track()
        t["actual_start_requested"] = 0
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_tracking_rejects_bogus_live_session(self):
        t = track()
        t["current_positions"] = "EMPTY"
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_tracking_cannot_simulate_completed_module(self):
        t = track()
        t["simulation_only"] = False
        self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=t)

    def test_predecessor_false_implementation_claim_denied(self):
        r = reg36()
        r["criteria"][0]["implementation_state"] = "IMPLEMENTED"
        self.check("D537_PREDECESSOR_NOT_COHERENT_NO_GO", r=r)

    def test_predecessor_g2_account_claim_denied(self):
        b = previous()
        b["old_evidence"]["positions_status"] = "ABSENT"
        self.check("D537_PREDECESSOR_NOT_COHERENT_NO_GO", b=b)

    def test_predecessor_stop_release_denied(self):
        b = previous()
        b["d535_case"]["stop_release_claim"] = True
        self.check("D537_PREDECESSOR_NOT_COHERENT_NO_GO", b=b)

    def test_predecessor_manual_approval_denied(self):
        a = auth36()
        a["approvals"]["mt4_read_only"] = True
        self.check("D537_PREDECESSOR_NOT_COHERENT_NO_GO", a=a)

    def test_forged_child_go_denied(self):
        with patch(
            "scripts.p0_01_d5_37_workplan_review.review_d536_readiness",
            return_value={"status":
                          "D536_DESIGN_CRITERIA_DOCUMENTED_REAL_ACCEPTANCE_BLOCKED",
                          "runtime_go_no_go": "GO"},
        ):
            self.check("D537_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_broker_verified_denied(self):
        from scripts.p0_01_d5_36_readiness_gate import (
            review_d536_readiness as original,
        )
        child = original(c36(), reg36(), auth36(), previous())
        child["broker_verified"] = True
        with patch(
            "scripts.p0_01_d5_37_workplan_review.review_d536_readiness",
            return_value=child,
        ):
            self.check("D537_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_accepted_criterion_denied(self):
        from scripts.p0_01_d5_36_readiness_gate import (
            review_d536_readiness as original,
        )
        child = original(c36(), reg36(), auth36(), previous())
        child["real_acceptance_criteria_completed"] = 1
        with patch(
            "scripts.p0_01_d5_37_workplan_review.review_d536_readiness",
            return_value=child,
        ):
            self.check("D537_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_invalid_status_denied(self):
        from scripts.p0_01_d5_36_readiness_gate import (
            review_d536_readiness as original,
        )
        child = original(c36(), reg36(), auth36(), previous())
        child["status"] = "GO"
        with patch(
            "scripts.p0_01_d5_37_workplan_review.review_d536_readiness",
            return_value=child,
        ):
            self.check("D537_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_invalid_plan_types_denied(self):
        for x in (None, {}, [], True, "GO"):
            with self.subTest(value=repr(x)):
                self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=x)

    def test_invalid_tracking_types_denied(self):
        for x in (None, {}, [], True, "GO"):
            with self.subTest(value=repr(x)):
                self.check("D537_TRACKING_SCHEMA_REJECTED_FAIL_CLOSED", t=x)

    def test_review_never_reads_os_files(self):
        args = (plan(), track(), c36(), reg36(), auth36(), previous())
        with patch("builtins.open", side_effect=AssertionError("No real IO")):
            result = review_d537_workplan(*args)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_review_does_not_mutate_inputs(self):
        args = (plan(), track(), c36(), reg36(), auth36(), previous())
        old = copy.deepcopy(args)
        review_d537_workplan(*args)
        self.assertEqual(args, old)

    def test_repeated_calls_never_authorize_anything(self):
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")
        t = track()
        t["mt4_operation_requested"] = True
        self.check("D537_UNAUTHORIZED_PROGRESS_OR_ACTION_NO_GO", t=t)
        self.check("D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_status_has_all_unresolved_gates_and_zero_real_work(self):
        s = read("p0_01_d5_37_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        self.assertEqual(s["real_acceptance_criteria_completed"], 0)
        self.assertEqual(s["real_work_packages_executed"], 0)
        for field in ("g2_real_world_resolved", "g6_real_world_resolved",
                      "broker_verified", "host_io_approved",
                      "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[field], False)


def _false_progress_test(index, field, value):
    def test(self):
        t = track()
        t["work_packages"][index][field] = value
        self.check("D537_UNAUTHORIZED_PROGRESS_OR_ACTION_NO_GO", t=t)
    return test


def _plan_permission_test(index, field):
    def test(self):
        p = plan()
        p["work_packages"][index][field] = True
        self.check("D537_WORKPLAN_REJECTED_FAIL_CLOSED", p=p)
    return test


def _fake_operation_test(field):
    def test(self):
        t = track()
        t[field] = True
        self.check("D537_UNAUTHORIZED_PROGRESS_OR_ACTION_NO_GO", t=t)
    return test


for _i, _ident in enumerate(_ORDER):
    for _field, _value in (
        ("implementation_state", "IMPLEMENTED"),
        ("evidence_state", "COLLECTED"),
        ("approval_state", "APPROVED"),
        ("acceptance_state", "ACCEPTED"),
    ):
        setattr(D537WorkplanTests,
                "test_no_progress_" + _ident.replace("-", "_") + "_" + _field,
                _false_progress_test(_i, _field, _value))
    for _flag in ("implementation_allowed", "real_evidence_collected",
                  "review_approved", "acceptance_allowed", "execution_allowed"):
        setattr(D537WorkplanTests,
                "test_plan_no_permission_" + _ident.replace("-", "_") + "_" + _flag,
                _plan_permission_test(_i, _flag))


for _action in (
    "external_g7_verified", "external_g8_verified",
    "actual_start_requested", "actual_evidence_collection_requested",
    "stop_release_requested", "mt4_operation_requested",
    "private_export_requested",
):
    setattr(D537WorkplanTests, "test_no_action_" + _action,
            _fake_operation_test(_action))


if __name__ == "__main__":
    main()
