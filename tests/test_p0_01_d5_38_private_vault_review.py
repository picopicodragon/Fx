"""D5-38: G2 private evidence vault requirements, not a real storage test."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_38_private_vault_review import (
    _FALSE, _THREATS, _ZONES, _PERMISSIONS,
    review_d538_private_vault,
)
from scripts.p0_01_d5_36_readiness_gate import _BUNDLE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as source:
        return json.load(source)


def design(): return read("p0_01_d5_38_private_vault_contract.json")
def matrix(): return read("p0_01_d5_38_threat_matrix.json")
def workplan(): return read("p0_01_d5_37_workplan_contract.json")
def tracking(): return read("p0_01_d5_37_synthetic_tracking.json")
def d36plan(): return read("p0_01_d5_36_acceptance_contract.json")
def d36readiness(): return read("p0_01_d5_36_readiness_register.json")
def d36actions(): return read("p0_01_d5_36_synthetic_authorization.json")


def predecessor():
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


class D538VaultTests(TestCase):
    def check(self, expected, plan=_DEFAULT, m=_DEFAULT, wp=_DEFAULT,
              tr=_DEFAULT, c36=_DEFAULT, r36=_DEFAULT,
              a36=_DEFAULT, b=_DEFAULT):
        result = review_d538_private_vault(
            design() if plan is _DEFAULT else plan,
            matrix() if m is _DEFAULT else m,
            workplan() if wp is _DEFAULT else wp,
            tracking() if tr is _DEFAULT else tr,
            d36plan() if c36 is _DEFAULT else c36,
            d36readiness() if r36 is _DEFAULT else r36,
            d36actions() if a36 is _DEFAULT else a36,
            predecessor() if b is _DEFAULT else b,
        )
        self.assertEqual(result["status"], expected)
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertEqual(result["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(result["g2_06_design_threats_documented"], 12)
        self.assertEqual(result["real_evidence_items_collected"], 0)
        self.assertEqual(result["real_work_packages_executed"], 0)
        self.assertEqual(result["real_acceptance_criteria_completed"], 0)
        for field in ("current_positions", "current_pending_orders",
                      "current_ea_state"):
            self.assertEqual(result[field], "UNKNOWN")
        for field in _FALSE:
            self.assertIs(result[field], False, field)
        self.assertEqual(set(result), set(_FALSE) | {
            "status", "d537_status", "g2_06_design_threats_documented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return result

    def test_baseline_is_design_only_never_actual_storage(self):
        result = self.check(
            "D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")
        self.assertEqual(result["d537_status"],
                         "D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED")

    def test_g2_06_source_and_g2_07_dependency_locked(self):
        p = design()
        self.assertEqual(p["target_criterion"], "G2-06")
        self.assertEqual(p["dependent_criterion"], "G2-07")
        self.assertEqual(p["independent_boundary"], "G6-02")
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_private_categories_never_represent_actual_capture(self):
        self.assertEqual(len(design()["privacy_classes"]), 6)
        self.assertIs(self.check(
            "D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE"
        )["g2_06_actual_private_store"], False)

    def test_four_zones_are_only_names_without_paths(self):
        self.assertEqual(len(matrix()["zones"]), 4)
        self.assertTrue(all(z["real_path"] is None for z in matrix()["zones"]))
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_twelve_threat_labels_in_fixed_order(self):
        self.assertEqual([t["threat_id"] for t in matrix()["threats"]],
                         list(_THREATS))
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_unset_retention_schedule_does_not_mean_approval(self):
        self.assertEqual(
            design()["controls"]["retention_schedule"],
            "UNDECIDED_REQUIRES_HUMAN_REVIEW")
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_delete_request_not_erasure_proof(self):
        self.assertEqual(
            design()["controls"]["deletion_semantics"],
            "DELETE_REQUEST_NOT_ERASURE_PROOF")
        self.assertFalse(matrix()["erasure_verified"])
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_g6_anchor_not_shared_trust_root(self):
        p = design()
        self.assertEqual(
            p["controls"]["g6_anchor"],
            "SEPARATE_TRUST_BOUNDARY_NOT_IMPLEMENTED")
        self.assertIs(self.check(
            "D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE"
        )["g6_real_anchor_trust_boundary_verified"], False)

    def test_future_git_ignore_not_sufficient_evidence(self):
        self.assertIn("GIT_HISTORY_REUSE", _THREATS)
        self.assertIn("CI_ARTIFACT_EXPORT", _THREATS)
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_symlink_escape_is_explicit_threat(self):
        self.assertIn("JUNCTION_SYMLINK_ESCAPE", _THREATS)
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_backups_and_crash_dumps_require_separate_protection(self):
        self.assertIn("BACKUP_OR_SNAPSHOT_LEAK", _THREATS)
        self.assertIn("CRASH_DUMP_LEAK", _THREATS)
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_no_real_keys_or_sensitive_values_in_fixture(self):
        combined = json.dumps({"plan": design(), "matrix": matrix()})
        for marker in ("-----BEGIN PRIVATE KEY-----", "C:\\Users\\",
                       "account_number", "broker_password"):
            self.assertNotIn(marker, combined)
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_plan_extra_actual_path_denied(self):
        p = design()
        p["real_path"] = "SYNTHETIC_PLACEHOLDER"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_privacy_class_removal_denied(self):
        p = design()
        p["privacy_classes"].pop()
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_classification_promoted_public_denied(self):
        p = design()
        p["privacy_classes"][0] = "PUBLIC"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_zone_change_denied(self):
        p = design()
        p["zones"][0] = "REAL_LOCAL_STORE"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_selection_of_crypto_algorithm_denied(self):
        p = design()
        p["controls"]["encryption_algorithm"] = "AES-256-GCM"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_unapproved_retention_days_denied(self):
        p = design()
        p["controls"]["retention_schedule"] = "30_DAYS"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_fake_erasure_certified_denied(self):
        p = design()
        p["controls"]["deletion_semantics"] = "CRYPTO_ERASURE_VERIFIED"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_actual_g6_anchor_flag_denied(self):
        p = design()
        p["controls"]["g6_anchor"] = "REAL_ANCHOR_AVAILABLE"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_extra_git_export_approval_denied(self):
        p = design()
        p["permissions"]["private_git_export"] = True
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_g2_06_id_cannot_be_g2_07(self):
        p = design()
        p["target_criterion"] = "G2-07"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_real_phase_go_denied(self):
        p = design()
        p["runtime_go_no_go"] = "GO"
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_plan_bool_schema_denied(self):
        p = design()
        p["schema_version"] = True
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)

    def test_matrix_unknown_threat_denied(self):
        m = matrix()
        m["threats"][0]["threat_id"] = "REAL_INCIDENT"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_missing_threat_denied(self):
        m = matrix()
        m["threats"].pop()
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_duplicate_threat_denied(self):
        m = matrix()
        m["threats"][1] = copy.deepcopy(m["threats"][0])
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_reordered_zone_denied(self):
        m = matrix()
        m["zones"].reverse()
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_unauthorized_real_path_denied(self):
        m = matrix()
        m["zones"][0]["real_path"] = "SYNTHETIC_PLACEHOLDER"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fake_current_position_denied(self):
        m = matrix()
        m["current_positions"] = "EMPTY"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fake_observed_time_denied(self):
        m = matrix()
        m["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_only_origin_synthetic_accepted(self):
        m = matrix()
        m["origin"] = "REAL"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_extra_private_data_denied(self):
        m = matrix()
        m["account_number"] = "SYNTHETIC_SECRET"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_fake_proven_retention_denied(self):
        m = matrix()
        m["retention_approved"] = True
        self.check("D538_FALSE_ERASURE_RETENTION_ANCHOR_CLAIM_NO_GO", m=m)

    def test_matrix_fake_proven_erasure_denied(self):
        m = matrix()
        m["erasure_verified"] = True
        self.check("D538_FALSE_ERASURE_RETENTION_ANCHOR_CLAIM_NO_GO", m=m)

    def test_matrix_fake_independent_anchor_denied(self):
        m = matrix()
        m["external_anchor_verified"] = True
        self.check("D538_FALSE_ERASURE_RETENTION_ANCHOR_CLAIM_NO_GO", m=m)

    def test_threat_classification_cannot_change(self):
        m = matrix()
        m["threats"][0]["classification"] = "SECRET_MATERIAL"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_extra_raw_log_field_denied(self):
        m = matrix()
        m["threats"][0]["raw_mt4_log"] = "SYNTHETIC_EXAMPLE"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_real_claim_bool_not_int(self):
        m = matrix()
        m["threats"][0]["control_implemented"] = 1
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_invalid_operation_literal_denied(self):
        m = matrix()
        m["threats"][0]["requested_action"] = "REAL_GO"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_threat_invalid_destination_literal_denied(self):
        m = matrix()
        m["threats"][0]["destination"] = "REAL_EMAIL"
        self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_predecessor_workplan_false_progress_denied(self):
        w = workplan()
        w["work_packages"][0]["implementation_allowed"] = True
        self.check("D538_PREDECESSOR_NOT_COHERENT_NO_GO", wp=w)

    def test_predecessor_readiness_fake_acceptance_denied(self):
        r = d36readiness()
        r["criteria"][0]["acceptance_state"] = "ACCEPTED"
        self.check("D538_PREDECESSOR_NOT_COHERENT_NO_GO", r36=r)

    def test_predecessor_mt4_access_claim_denied(self):
        t = tracking()
        t["mt4_operation_requested"] = True
        self.check("D538_PREDECESSOR_NOT_COHERENT_NO_GO", tr=t)

    def test_predecessor_old_account_reconciliation_denied(self):
        b = predecessor()
        b["old_evidence"]["positions_status"] = "ABSENT"
        self.check("D538_PREDECESSOR_NOT_COHERENT_NO_GO", b=b)

    def test_forged_child_go_denied(self):
        with patch(
            "scripts.p0_01_d5_38_private_vault_review.review_d537_workplan",
            return_value={"status":
                "D537_DESIGN_WORKPLAN_COHERENT_REAL_WORK_BLOCKED",
                "runtime_go_no_go": "GO"},
        ):
            self.check("D538_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_completed_work_denied(self):
        from scripts.p0_01_d5_37_workplan_review import (
            review_d537_workplan as original,
        )
        child = original(workplan(), tracking(), d36plan(),
                         d36readiness(), d36actions(), predecessor())
        child["work_packages_executed"] = 1
        with patch(
            "scripts.p0_01_d5_38_private_vault_review.review_d537_workplan",
            return_value=child,
        ):
            self.check("D538_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_pure_review_does_not_access_real_files(self):
        args = (design(), matrix(), workplan(), tracking(), d36plan(),
                d36readiness(), d36actions(), predecessor())
        with patch("builtins.open", side_effect=AssertionError("No host I/O")):
            r = review_d538_private_vault(*args)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_pure_review_does_not_mutate_inputs(self):
        args = (design(), matrix(), workplan(), tracking(), d36plan(),
                d36readiness(), d36actions(), predecessor())
        original = copy.deepcopy(args)
        review_d538_private_vault(*args)
        self.assertEqual(args, original)

    def test_no_secrets_echoed_on_rejection(self):
        m = matrix()
        m["secret"] = "SYNTHETIC_MARKER_NOT_REAL"
        out = self.check("D538_G2_06_THREAT_SCHEMA_REJECTED_FAIL_CLOSED", m=m)
        self.assertNotIn("SYNTHETIC_MARKER_NOT_REAL", repr(out))

    def test_no_auto_permissions_on_repeated_calls(self):
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")
        m = matrix()
        m["retention_approved"] = True
        self.check("D538_FALSE_ERASURE_RETENTION_ANCHOR_CLAIM_NO_GO", m=m)
        self.check("D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_current_status_has_zero_real_evidence(self):
        s = read("p0_01_d5_38_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        self.assertEqual(s["real_evidence_items_collected"], 0)
        self.assertEqual(s["real_acceptance_criteria_completed"], 0)
        for key in ("g2_real_world_resolved", "g6_real_world_resolved",
                    "broker_verified", "terminal_execution_approved",
                    "host_io_approved", "forward_trading_enabled"):
            self.assertIs(s[key], False)


def _threat_test(index, field, value, status):
    def test(self):
        m = matrix()
        m["threats"][index][field] = value
        self.check(status, m=m)
    return test


def _zone_test(index, field, value):
    def test(self):
        m = matrix()
        m["zones"][index][field] = value
        self.check("D538_UNAUTHORIZED_STORAGE_ZONE_CLAIM_NO_GO", m=m)
    return test


def _permission_test(name):
    def test(self):
        p = design()
        p["permissions"][name] = True
        self.check("D538_G2_06_DESIGN_CONTRACT_REJECTED_FAIL_CLOSED", plan=p)
    return test


for _i, _name in enumerate(_THREATS):
    for _field, _value, _status in (
        ("destination", "PUBLIC_METADATA",
         "D538_G2_G6_PRIVACY_EGRESS_DENIED_NO_GO"),
        ("destination", "GIT_REPOSITORY",
         "D538_G2_G6_PRIVACY_EGRESS_DENIED_NO_GO"),
        ("destination", "G6_ANCHOR",
         "D538_G2_G6_PRIVACY_EGRESS_DENIED_NO_GO"),
        ("requested_action", "ALLOW_PRIVATE_EXPORT",
         "D538_UNAUTHORIZED_DATA_OPERATION_NO_GO"),
        ("requested_action", "ALLOW_DELETE",
         "D538_UNAUTHORIZED_DATA_OPERATION_NO_GO"),
        ("control_implemented", True,
         "D538_FALSE_PROTECTION_IMPLEMENTED_CLAIM_NO_GO"),
        ("real_evidence_observed", True,
         "D538_FALSE_PROTECTION_IMPLEMENTED_CLAIM_NO_GO"),
        ("mitigation_state", "IMPLEMENTED",
         "D538_FALSE_PROTECTION_IMPLEMENTED_CLAIM_NO_GO"),
    ):
        setattr(D538VaultTests,
                f"test_threat_{_i:02d}_" + _field + "_" + str(_value).lower(),
                _threat_test(_i, _field, _value, _status))

for _i, _name in enumerate(_ZONES):
    for _field, _value in (
        ("implementation_state", "IMPLEMENTED"),
        ("real_read_allowed", True),
        ("real_write_allowed", True),
        ("git_export_allowed", True),
    ):
        setattr(D538VaultTests,
                f"test_zone_{_i:02d}_{_field}",
                _zone_test(_i, _field, _value))

for _permission in _PERMISSIONS:
    setattr(D538VaultTests, "test_no_" + _permission,
            _permission_test(_permission))


if __name__ == "__main__":
    main()
