"""D5-39 synthetic Git/PR/CI/publication-egress requirements regression."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_39_egress_gate import (
    _FALSE, _CHANNELS, _PARENT_KEYS, review_d539_egress,
)
from scripts.p0_01_d5_36_readiness_gate import _BUNDLE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def contract(): return read("p0_01_d5_39_egress_contract.json")
def manifest(): return read("p0_01_d5_39_synthetic_manifest.json")
def public_json(): return read("p0_01_d5_32_synthetic_fixture.json")["public_json"]


def parent():
    p = {
        "d538_design": read("p0_01_d5_38_private_vault_contract.json"),
        "d538_threat_matrix": read("p0_01_d5_38_threat_matrix.json"),
        "d537_workplan": read("p0_01_d5_37_workplan_contract.json"),
        "d537_tracking": read("p0_01_d5_37_synthetic_tracking.json"),
        "d536_contract": read("p0_01_d5_36_acceptance_contract.json"),
        "d536_readiness": read("p0_01_d5_36_readiness_register.json"),
        "d536_actions": read("p0_01_d5_36_synthetic_authorization.json"),
    }
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
    p["d536_predecessors"] = dict(zip(_BUNDLE_FIELDS, (read(n) for n in names)))
    return p


class D539EgressTests(TestCase):
    def check(self, expected, c=_MISSING, m=_MISSING, ref=_MISSING, b=_MISSING):
        v = review_d539_egress(
            contract() if c is _MISSING else c,
            manifest() if m is _MISSING else m,
            public_json() if ref is _MISSING else ref,
            parent() if b is _MISSING else b,
        )
        self.assertEqual(v["status"], expected)
        self.assertEqual(v["runtime_go_no_go"], "NO_GO")
        self.assertEqual(v["phase_1"], "BLOCKED")
        self.assertIsNone(v["verified_values"])
        self.assertIs(v["safety_hold_latched"], True)
        self.assertEqual(v["effective_approved_actions"], [])
        self.assertEqual(v["account_identity_consistency"], "NOT_RECONCILED")
        for k in ("current_positions", "current_pending_orders",
                  "current_ea_state"):
            self.assertEqual(v[k], "UNKNOWN")
        self.assertEqual(v["synthetic_egress_surfaces"], 8)
        self.assertEqual(v["real_egress_surfaces_scanned"], 0)
        self.assertEqual(v["real_evidence_items_collected"], 0)
        self.assertEqual(v["real_work_packages_executed"], 0)
        self.assertEqual(v["real_acceptance_criteria_completed"], 0)
        for k in _FALSE:
            self.assertIs(v[k], False, k)
        self.assertEqual(set(v), set(_FALSE) | {
            "status", "d538_status", "synthetic_egress_surfaces",
            "real_egress_surfaces_scanned", "real_evidence_items_collected",
            "real_work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return v

    def test_baseline_eight_channels_clean_but_no_real_export(self):
        r = self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")
        self.assertEqual(r["d538_status"],
                         "D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE")

    def test_all_eight_channels_in_exact_order(self):
        self.assertEqual([x["channel"] for x in manifest()["items"]],
                         list(_CHANNELS))
        self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")

    def test_canonical_public_metadata_is_fixed_and_unpublished(self):
        self.assertEqual(manifest()["public_json"], public_json())
        self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")

    def test_g2_06_is_a_dependency_not_real_completed_acceptance(self):
        self.assertEqual(contract()["depends_on"], ["G2-06"])
        self.assertEqual(contract()["external_gate_dependencies"], ["G8"])
        r = self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")
        self.assertIs(r["g2_06_vault_implemented"], False)

    def test_real_git_history_not_actually_scanned(self):
        r = self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")
        self.assertIs(r["g2_07_real_history_scanned"], False)

    def test_secret_scanner_absence_cannot_prove_no_secrets(self):
        r = self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")
        self.assertIs(r["g2_07_real_secret_leak_absence_proven"], False)

    def test_all_destinations_deny_real_egress(self):
        self.assertTrue(all(x["destination"] == "DENY_REAL_EGRESS"
                            for x in manifest()["items"]))
        self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")

    def test_invalid_contract_denied(self):
        for x in (None, [], {}, "GO", True):
            with self.subTest(x=repr(x)):
                self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=x)

    def test_invalid_manifest_denied(self):
        for x in (None, [], {}, "GO", True):
            with self.subTest(x=repr(x)):
                self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=x)

    def test_contract_target_change_denied(self):
        c = contract()
        c["target_criterion"] = "G2-06"
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_dependency_erasure_denied(self):
        c = contract()
        c["depends_on"] = []
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_g8_dependency_erasure_denied(self):
        c = contract()
        c["external_gate_dependencies"] = []
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_extra_public_field_denied(self):
        c = contract()
        c["allow_account_number"] = True
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_channel_reorder_denied(self):
        c = contract()
        c["channels"].reverse()
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_class_change_denied(self):
        c = contract()
        c["allowed_data_class"] = "ACCOUNT_TERMINAL_IDENTIFIERS"
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_real_operation_policy_denied(self):
        c = contract()
        c["review_mode"] = "REAL_EXPORT"
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_runtime_go_denied(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_verified_values_denied(self):
        c = contract()
        c["verified_values"] = {}
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_bool_schema_denied(self):
        c = contract()
        c["schema_version"] = True
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)

    def test_manifest_item_missing_denied(self):
        m = manifest()
        m["items"].pop()
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_item_duplicate_denied(self):
        m = manifest()
        m["items"][1] = copy.deepcopy(m["items"][0])
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_item_reorder_denied(self):
        m = manifest()
        m["items"].reverse()
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_extra_raw_log_denied(self):
        m = manifest()
        m["items"][0]["raw_mt4_log"] = "SYNTHETIC_SECRET_MARKER"
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_unknown_class_denied(self):
        m = manifest()
        m["items"][0]["data_class"] = "ACTUAL_ACCOUNT"
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_unknown_candidate_kind_denied(self):
        m = manifest()
        m["items"][0]["candidate_kind"] = "UNSCANNED_ZIP"
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_false_observation_claim_denied(self):
        m = manifest()
        m["items"][0]["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_extra_private_payload_denied(self):
        m = manifest()
        m["private_payload"] = "SYNTHETIC_SECRET_MARKER"
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_wrong_account_identity_denied(self):
        m = manifest()
        m["account_identity_consistency"] = "RECONCILED"
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_all_gates_unresolved(self):
        m = manifest()
        m["unresolved_gates"] = ["G2", "G6"]
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_manifest_invalid_boolean_as_integer_denied(self):
        m = manifest()
        m["items"][0]["private_data_attached"] = 0
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_public_json_duplicate_key_denied(self):
        m = manifest()
        m["public_json"] = m["public_json"].replace(
            '"schema_version":1', '"schema_version":1,"schema_version":1')
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_public_json_extra_field_denied(self):
        m = manifest()
        data = json.loads(m["public_json"])
        data["account_number"] = "SYNTHETIC_NOT_REAL"
        m["public_json"] = json.dumps(data, sort_keys=True, separators=(",", ":"))
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_public_json_noncanonical_spacing_denied(self):
        m = manifest()
        m["public_json"] = m["public_json"].replace(',"origin"', ', "origin"')
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_public_json_unicode_payload_denied(self):
        m = manifest()
        m["public_json"] += "日本語"
        self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)

    def test_public_json_scope_mismatch_denied(self):
        m = manifest()
        m["public_json"] = m["public_json"].replace(
            "D530-G2-01", "D530-G2-02")
        self.check("D539_PUBLIC_METADATA_SCOPE_MISMATCH_NO_GO", m=m)

    def test_expected_public_json_invalid_denied(self):
        self.check("D539_REFERENCE_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   ref="SYNTHETIC_UNSAFE")

    def test_expected_public_json_not_equivalent_denied(self):
        ref = public_json().replace("D530-G2-01", "D530-G2-02")
        self.check("D539_PUBLIC_METADATA_SCOPE_MISMATCH_NO_GO", ref=ref)

    def test_missing_predecessor_bundle_denied(self):
        self.check("D539_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", b={})

    def test_predecessor_extra_real_credentials_denied(self):
        p = parent()
        p["real_broker_credentials"] = "SYNTHETIC_NOT_REAL"
        self.check("D539_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", b=p)

    def test_predecessor_unapproved_vault_denied(self):
        p = parent()
        p["d538_design"]["permissions"]["real_host_write"] = True
        self.check("D539_PREDECESSOR_NOT_COHERENT_NO_GO", b=p)

    def test_predecessor_false_g6_anchor_denied(self):
        p = parent()
        p["d538_threat_matrix"]["external_anchor_verified"] = True
        self.check("D539_PREDECESSOR_NOT_COHERENT_NO_GO", b=p)

    def test_predecessor_false_readiness_denied(self):
        p = parent()
        p["d536_readiness"]["criteria"][0]["acceptance_state"] = "ACCEPTED"
        self.check("D539_PREDECESSOR_NOT_COHERENT_NO_GO", b=p)

    def test_forged_child_go_denied(self):
        with patch("scripts.p0_01_d5_39_egress_gate.review_d538_private_vault",
                   return_value={"status":
                       "D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE",
                       "runtime_go_no_go": "GO"}):
            self.check("D539_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_real_vault_denied(self):
        from scripts.p0_01_d5_38_private_vault_review import (
            review_d538_private_vault as original,
        )
        p = parent()
        child = original(*(p[k] for k in _PARENT_KEYS))
        child["g2_06_vault_implemented"] = True
        with patch("scripts.p0_01_d5_39_egress_gate.review_d538_private_vault",
                   return_value=child):
            self.check("D539_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_child_unexpected_coherent_status_denied(self):
        from scripts.p0_01_d5_38_private_vault_review import (
            review_d538_private_vault as original,
        )
        p = parent()
        child = original(*(p[k] for k in _PARENT_KEYS))
        child["status"] = "REAL_APPROVED"
        with patch("scripts.p0_01_d5_39_egress_gate.review_d538_private_vault",
                   return_value=child):
            self.check("D539_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_rejection_does_not_echo_untrusted_strings(self):
        m = manifest()
        m["secret"] = "SYNTHETIC_SECRET_MARKER"
        v = self.check("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED", m=m)
        self.assertNotIn("SYNTHETIC_SECRET_MARKER", repr(v))

    def test_no_real_file_operations_in_review_function(self):
        args = (contract(), manifest(), public_json(), parent())
        with patch("builtins.open", side_effect=AssertionError("NO IO")):
            out = review_d539_egress(*args)
        self.assertEqual(out["runtime_go_no_go"], "NO_GO")

    def test_pure_function_does_not_mutate_inputs(self):
        args = (contract(), manifest(), public_json(), parent())
        before = copy.deepcopy(args)
        review_d539_egress(*args)
        self.assertEqual(args, before)

    def test_repeated_calls_never_latch_approval(self):
        self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")
        m = manifest()
        m["items"][0]["actual_egress_requested"] = True
        self.check("D539_REAL_EGRESS_REQUEST_DENIED_NO_GO", m=m)
        self.check("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS")

    def test_status_tracks_zero_real_scans_and_acceptances(self):
        s = read("p0_01_d5_39_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        self.assertEqual(s["real_egress_surfaces_scanned"], 0)
        self.assertEqual(s["real_acceptance_criteria_completed"], 0)
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "host_io_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)


def _surface_test(index, mutation, expected):
    def test(self):
        m = manifest()
        if mutation == "git_destination":
            m["items"][index]["destination"] = "GIT_REPOSITORY"
        elif mutation == "ci_destination":
            m["items"][index]["destination"] = "CI_ARTIFACT_PUBLIC"
        elif mutation == "actual_egress":
            m["items"][index]["actual_egress_requested"] = True
        elif mutation == "private_data":
            m["items"][index]["private_data_attached"] = True
        elif mutation == "private_class":
            m["items"][index]["data_class"] = "SECRET_MATERIAL"
        elif mutation == "raw_content":
            m["items"][index]["candidate_kind"] = "RAW_TEXT"
        elif mutation == "scanner_claim":
            m["items"][index]["scanner_claim_verified"] = True
        elif mutation == "hook_claim":
            m["items"][index]["hook_claim_installed"] = True
        elif mutation == "published_claim":
            m["items"][index]["real_publication_verified"] = True
        self.check(expected, m=m)
    return test


def _policy_permission_test(name):
    def test(self):
        c = contract()
        c[name] = True
        self.check("D539_POLICY_REJECTED_FAIL_CLOSED", c=c)
    return test


def _host_operation_test(name):
    def test(self):
        m = manifest()
        m[name] = True
        self.check("D539_REAL_OPERATION_REQUEST_DENIED_NO_GO", m=m)
    return test


for _i, _channel in enumerate(_CHANNELS):
    for _mut, _expected in (
        ("git_destination", "D539_REAL_EGRESS_REQUEST_DENIED_NO_GO"),
        ("ci_destination", "D539_REAL_EGRESS_REQUEST_DENIED_NO_GO"),
        ("actual_egress", "D539_REAL_EGRESS_REQUEST_DENIED_NO_GO"),
        ("private_data", "D539_PRIVATE_CLASS_OR_ATTACHMENT_DENIED_NO_GO"),
        ("private_class", "D539_PRIVATE_CLASS_OR_ATTACHMENT_DENIED_NO_GO"),
        ("raw_content", "D539_NON_CANONICAL_CONTENT_TYPE_DENIED_NO_GO"),
        ("scanner_claim", "D539_FALSE_REAL_GUARD_CLAIM_NO_GO"),
        ("hook_claim", "D539_FALSE_REAL_GUARD_CLAIM_NO_GO"),
        ("published_claim", "D539_FALSE_REAL_GUARD_CLAIM_NO_GO"),
    ):
        setattr(D539EgressTests, f"test_surface_{_i:02d}_{_mut}",
                _surface_test(_i, _mut, _expected))

for _flag in (
    "real_guard_implemented", "real_git_hook_installed",
    "real_ci_scan_installed", "real_history_scanned",
    "real_public_export_approved", "real_private_export_approved",
    "actual_leakage_ruled_out",
):
    setattr(D539EgressTests, "test_no_policy_" + _flag,
            _policy_permission_test(_flag))

for _flag in (
    "real_host_io_requested", "real_mt4_access_requested",
    "real_private_evidence_collection_requested",
    "real_stop_release_requested", "real_trade_requested",
):
    setattr(D539EgressTests, "test_no_host_" + _flag,
            _host_operation_test(_flag))


if __name__ == "__main__":
    main()
