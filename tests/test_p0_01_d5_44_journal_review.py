"""D5-44 Journal/tombstone synthetic structure and adversarial regression."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_44_journal_review import (
    _FALSE, _CONTROLS, _ENTRIES, _THREATS, _POLICIES,
    _CONTRACT_FALSE, _FIXTURE_FALSE, _PARENT_KEYS,
    review_d544_journal,
)
from scripts.p0_01_d5_43_key_lifecycle_review import review_d543_key_lifecycle
from scripts.p0_01_d5_36_readiness_gate import _BUNDLE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def contract(): return read("p0_01_d5_44_journal_contract.json")
def fixture(): return read("p0_01_d5_44_synthetic_journal.json")


def predecessor():
    p = {
        "d543_contract": read("p0_01_d5_43_key_lifecycle_contract.json"),
        "d543_matrix": read("p0_01_d5_43_synthetic_key_lifecycle.json"),
    }
    p42 = {
        "d542_contract": read("p0_01_d5_42_selection_rules.json"),
        "d542_scenario": read("p0_01_d5_42_synthetic_selection_review.json"),
    }
    p41 = {
        "d541_contract": read("p0_01_d5_41_anchor_selection_contract.json"),
        "d541_matrix": read("p0_01_d5_41_candidate_evidence_matrix.json"),
    }
    p40 = {
        "d540_contract": read("p0_01_d5_40_trust_boundary_contract.json"),
        "d540_matrix": read("p0_01_d5_40_candidate_threat_matrix.json"),
    }
    p39 = {
        "d539_contract": read("p0_01_d5_39_egress_contract.json"),
        "d539_manifest": read("p0_01_d5_39_synthetic_manifest.json"),
        "d539_public_json": read("p0_01_d5_32_synthetic_fixture.json")["public_json"],
    }
    p38 = {
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
    p38["d536_predecessors"] = dict(zip(_BUNDLE_FIELDS, (read(n) for n in names)))
    p39["d539_predecessors"] = p38
    p40["d540_predecessor_bundle"] = p39
    p41["d541_predecessor"] = p40
    p42["d542_predecessor"] = p41
    p["d543_predecessor"] = p42
    return p


class D544JournalTests(TestCase):
    def check(self, expected, c=_MISSING, f=_MISSING, p=_MISSING):
        out = review_d544_journal(
            contract() if c is _MISSING else c,
            fixture() if f is _MISSING else f,
            predecessor() if p is _MISSING else p,
        )
        self.assertEqual(out["status"], expected)
        self.assertEqual(out["runtime_go_no_go"], "NO_GO")
        self.assertEqual(out["phase_1"], "BLOCKED")
        self.assertIsNone(out["verified_values"])
        self.assertIs(out["safety_hold_latched"], True)
        self.assertEqual(out["effective_approved_actions"], [])
        self.assertEqual(out["account_identity_consistency"], "NOT_RECONCILED")
        for k in ("current_positions", "current_pending_orders", "current_ea_state"):
            self.assertEqual(out[k], "UNKNOWN")
        for k, n in (
            ("journal_control_requirements", 12),
            ("synthetic_journal_entries", 12),
            ("synthetic_threats", 14),
            ("real_journal_entries_written", 0),
            ("real_tombstones_verified", 0),
            ("real_independent_tips_verified", 0),
            ("real_trust_anchors_implemented", 0),
            ("real_evidence_items_collected", 0),
            ("real_work_packages_executed", 0),
            ("real_acceptance_criteria_completed", 0),
        ):
            self.assertEqual(out[k], n, k)
        for k in _FALSE:
            self.assertIs(out[k], False, k)
        self.assertEqual(set(out), set(_FALSE) | {
            "status", "d543_status", "journal_control_requirements",
            "synthetic_journal_entries", "synthetic_threats",
            "real_journal_entries_written", "real_tombstones_verified",
            "real_independent_tips_verified", "real_trust_anchors_implemented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return out

    def test_baseline_design_only_journal(self):
        v = self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")
        self.assertEqual(v["d543_status"],
                         "D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_fixed_twelve_event_order(self):
        self.assertEqual([r["entry_id"] for r in fixture()["journal_entries"]],
                         list(_ENTRIES))
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_two_distinct_revocation_tombstones(self):
        self.assertIn("KEY_REVOKE_TOMBSTONE", _ENTRIES)
        self.assertIn("ISSUER_REVOKE_TOMBSTONE", _ENTRIES)
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_fixed_fourteen_attacks(self):
        self.assertEqual([r["threat_id"] for r in fixture()["threats"]],
                         [x[0] for x in _THREATS])
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_fixed_twelve_controls(self):
        self.assertEqual([r["control_id"] for r in fixture()["controls"]],
                         [x[0] for x in _CONTROLS])
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_tags_are_not_cryptographic_hashes(self):
        self.assertEqual(contract()["chain_policy"],
                         "SYNTHETIC_TAG_LINKS_ARE_NOT_CRYPTOGRAPHIC_PROOF")
        self.assertIsNone(fixture()["independent_tip"])
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_genesis_is_unpinned(self):
        self.assertIsNone(fixture()["trusted_genesis"])
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_no_real_record_content(self):
        self.assertTrue(all(r["private_payload"] is None
                            and r["actual_signature"] is None
                            and r["real_timestamp"] is None
                            for r in fixture()["journal_entries"]))
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_g6_04_depends_on_g6_01_not_automatically_g6_03(self):
        self.assertEqual(contract()["predecessor_criterion"], "G6-01")
        self.assertIn("G6-03", contract()["cross_boundary_requirements"])
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_g6_05_06_are_future_requirements_not_implemented(self):
        self.assertIn("G6-05", contract()["cross_boundary_requirements"])
        self.assertIn("G6-06", contract()["cross_boundary_requirements"])
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_tombstones_not_real_persistence(self):
        self.assertFalse(any(r["real_persisted"]
                             for r in fixture()["journal_entries"]))
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_attack_while_mitigation_marked_still_denied(self):
        f = fixture()
        f["threats"][0]["simulated_outcome"] = "SIMULATED_ATTACK"
        f["threats"][1]["simulated_outcome"] = "SIMULATED_MITIGATED"
        self.check("D544_SYNTHETIC_JOURNAL_ATTACK_DENIED_NO_GO", f=f)

    def test_all_simulated_mitigated_never_authorizes(self):
        f = fixture()
        for row in f["threats"]:
            row["simulated_outcome"] = "SIMULATED_MITIGATED"
        self.check("D544_SIMULATED_MITIGATION_NOT_REAL_PROOF", f=f)

    def test_contract_cannot_approve_trading(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_skip_privacy(self):
        c = contract()
        c["cross_boundary_requirements"].remove("G2-07")
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_skip_writer_fence(self):
        c = contract()
        c["writer_policy"] = "NO_FENCE_NEEDED"
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_claim_real_hashes(self):
        c = contract()
        c["chain_policy"] = "REAL_SHA_256_VERIFIED"
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_erase_tombstone(self):
        c = contract()
        c["revocation_policy"] = "TOMBSTONE_DELETION_ALLOWED"
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_promote_release_on_restart(self):
        c = contract()
        c["restart_policy"] = "AUTO_RELEASE"
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_authorize_real_os_io(self):
        c = contract()
        c["real_os_io_approved"] = True
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_cannot_add_secret(self):
        c = contract()
        c["real_signing_key"] = "SYNTHETIC_MARKER"
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_bool_version_denied(self):
        c = contract()
        c["schema_version"] = True
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_fixture_record_deleted_denied(self):
        f = fixture()
        f["journal_entries"].pop(4)
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_prefix_deleted_denied(self):
        f = fixture()
        f["journal_entries"] = f["journal_entries"][1:]
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_duplicate_entry_denied(self):
        f = fixture()
        f["journal_entries"][1] = copy.deepcopy(f["journal_entries"][0])
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_reordered_entry_denied(self):
        f = fixture()
        f["journal_entries"][5], f["journal_entries"][6] = (
            f["journal_entries"][6], f["journal_entries"][5]
        )
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_gap_in_sequence_denied(self):
        f = fixture()
        f["journal_entries"][5]["sequence"] = 17
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_previous_link_rebind_denied(self):
        f = fixture()
        f["journal_entries"][6]["previous_tag"] = "TAG_DESIGN_01"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_false_genesis_denied(self):
        f = fixture()
        f["journal_entries"][0]["previous_tag"] = "OTHER_GENESIS"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_tombstone_removed_denied(self):
        f = fixture()
        f["journal_entries"][6]["entry_id"] = "JOURNAL_COMMIT"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_record_payload_denied(self):
        f = fixture()
        f["journal_entries"][0]["private_payload"] = "FAKE_SECRET"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_fake_signature_denied(self):
        f = fixture()
        f["journal_entries"][0]["actual_signature"] = "SYNTHETIC"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_fake_time_denied(self):
        f = fixture()
        f["journal_entries"][0]["real_timestamp"] = "2026-10-30"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_real_tip_denied(self):
        f = fixture()
        f["independent_tip"] = "FAKE"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_real_path_denied(self):
        f = fixture()
        f["real_private_journal_path"] = "SYNTHETIC"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_pretend_account_reconciled_denied(self):
        f = fixture()
        f["account_identity_consistency"] = "RECONCILED"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_claim_current_positions_denied(self):
        f = fixture()
        f["current_positions"] = "EMPTY"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_gate_resolution_denied(self):
        f = fixture()
        f["unresolved_gates"].pop()
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_extra_unknown_key_denied(self):
        f = fixture()
        f["raw_log"] = "FAKE_MARKER"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_bool_sequence_denied(self):
        f = fixture()
        f["journal_entries"][0]["sequence"] = True
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_tampered_issuer_denied(self):
        f = fixture()
        f["journal_entries"][7]["issuer_alias"] = "SYNTHETIC_ISSUER_BETA"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_tampered_epoch_denied(self):
        f = fixture()
        f["journal_entries"][7]["epoch_label"] = "SYNTHETIC_EPOCH_0"
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_false_control_status_denied(self):
        f = fixture()
        f["controls"][0]["real_control_verified"] = True
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_fake_witness_verified_denied(self):
        f = fixture()
        f["journal_entries"][0]["real_witness_verified"] = True
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_fixture_false_stop_release_denied(self):
        f = fixture()
        f["real_stop_release_requested"] = True
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)

    def test_predecessor_missing_denied(self):
        self.check("D544_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", p={})

    def test_predecessor_forged_key_provision_denied(self):
        p = predecessor()
        p["d543_contract"]["real_key_generated"] = True
        self.check("D544_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_forged_tombstone_denied(self):
        p = predecessor()
        p["d543_matrix"]["issuer_chain"]["revocation_tombstone"] = "PERSISTED"
        self.check("D544_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_predecessor_forged_anchor_denied(self):
        p = predecessor()
        p["d543_predecessor"]["d542_predecessor"]["d541_predecessor"][
            "d540_matrix"]["external_anchor_verified"] = True
        self.check("D544_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_forged_parent_go_denied(self):
        with patch(
            "scripts.p0_01_d5_44_journal_review.review_d543_key_lifecycle",
            return_value={"status":"D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS",
                          "runtime_go_no_go":"GO"},
        ):
            self.check("D544_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_parent_real_keys_denied(self):
        p = predecessor()
        v = review_d543_key_lifecycle(*(p[k] for k in _PARENT_KEYS))
        v["real_keys_generated"] = 1
        with patch(
            "scripts.p0_01_d5_44_journal_review.review_d543_key_lifecycle",
            return_value=v,
        ):
            self.check("D544_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_forged_parent_status_denied(self):
        p = predecessor()
        v = review_d543_key_lifecycle(*(p[k] for k in _PARENT_KEYS))
        v["status"] = "REAL_APPROVED"
        with patch(
            "scripts.p0_01_d5_44_journal_review.review_d543_key_lifecycle",
            return_value=v,
        ):
            self.check("D544_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_pure_review_does_not_open_host_files(self):
        args = (contract(), fixture(), predecessor())
        with patch("builtins.open", side_effect=AssertionError("NO IO")):
            v = review_d544_journal(*args)
        self.assertEqual(v["runtime_go_no_go"], "NO_GO")

    def test_pure_review_does_not_change_inputs(self):
        args = (contract(), fixture(), predecessor())
        original = copy.deepcopy(args)
        review_d544_journal(*args)
        self.assertEqual(args, original)

    def test_no_secret_echo_on_reject(self):
        f = fixture()
        f["secret"] = "SYNTHETIC_SENTINEL"
        v = self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)
        self.assertNotIn("SYNTHETIC_SENTINEL", repr(v))

    def test_repeated_checks_never_authorize(self):
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")
        f = fixture()
        f["threats"][0]["simulated_outcome"] = "SIMULATED_ATTACK"
        self.check("D544_SYNTHETIC_JOURNAL_ATTACK_DENIED_NO_GO", f=f)
        self.check("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED")

    def test_status_zero_real_storage_and_anchor(self):
        s = read("p0_01_d5_44_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        for k in ("real_journal_entries_written", "real_tombstones_verified",
                  "real_independent_tips_verified",
                  "real_acceptance_criteria_completed"):
            self.assertEqual(s[k], 0)
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "host_io_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)


def _threat_test(i, value, expected):
    def test(self):
        f = fixture()
        f["threats"][i]["simulated_outcome"] = value
        self.check(expected, f=f)
    return test


def _entry_test(i, field, value):
    def test(self):
        f = fixture()
        f["journal_entries"][i][field] = value
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)
    return test


def _contract_test(field):
    def test(self):
        c = contract()
        c[field] = True
        self.check("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED", c=c)
    return test


def _fixture_test(field):
    def test(self):
        f = fixture()
        f[field] = True
        self.check("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED", f=f)
    return test


for _i in range(len(_THREATS)):
    for _label, _status in (
        ("SIMULATED_ATTACK", "D544_SYNTHETIC_JOURNAL_ATTACK_DENIED_NO_GO"),
        ("SIMULATED_MITIGATED", "D544_SIMULATED_MITIGATION_NOT_REAL_PROOF"),
    ):
        setattr(D544JournalTests, f"test_threat_{_i:02d}_{_label}",
                _threat_test(_i, _label, _status))

for _i in range(len(_ENTRIES)):
    for _field, _value in (
        ("real_persisted", True),
        ("real_witness_verified", True),
        ("sequence", 0),
        ("entry_tag", "FORGED"),
        ("previous_tag", "FORGED"),
    ):
        setattr(D544JournalTests, f"test_entry_{_i:02d}_{_field}",
                _entry_test(_i, _field, _value))

for _field in _CONTRACT_FALSE:
    setattr(D544JournalTests, f"test_no_contract_{_field}",
            _contract_test(_field))

for _field in _FIXTURE_FALSE:
    setattr(D544JournalTests, f"test_no_fixture_{_field}",
            _fixture_test(_field))


if __name__ == "__main__":
    main()
