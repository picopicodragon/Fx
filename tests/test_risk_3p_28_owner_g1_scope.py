"""G1 scope approval is not broker evidence or permission to trade.

Tests target the current explicit approval + preserved original G1 snapshot.
"""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_28_owner_g1_scope as mod


class OwnerG1ScopeDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.formal = mod.load(mod.ROOT, mod.FORMAL)
        cls.history = mod.load(mod.ROOT, mod.HISTORY_FILE)
        cls.decision = mod.load(mod.ROOT, mod.DECISION)

    def bad(self, which, edit, expected):
        records = {
            "formal": copy.deepcopy(self.formal),
            "history": copy.deepcopy(self.history),
            "decision": copy.deepcopy(self.decision),
        }
        edit(records[which])
        problems = mod.audit(formal=records["formal"],
                             history=records["history"],
                             decision=records["decision"])
        self.assertIn(expected, problems, problems)

    def test_current_owner_scope_is_three_pairs_five_fields_and_no_go(self):
        self.assertEqual(mod.audit(), [])
        self.assertEqual(self.decision["decision_status"], "OWNER_APPROVED_SCOPE_ONLY")
        self.assertEqual(self.decision["authorized_scope"],
                         ["USD/JPY", "EUR/JPY", "EUR/USD"])
        self.assertEqual(self.decision["required_count"], 15)
        self.assertEqual(self.formal["g1_scope_approved"], True)
        self.assertEqual(self.formal["g1_evidence_verified"], False)
        g = self.formal["gaps"][0]
        self.assertEqual(g["approved_major_attribute_count"], 15)
        self.assertEqual(g["verified_major_attribute_count"], 0)
        self.assertEqual(g["implementation_status"], "UNRESOLVED")
        self.assertIs(g["release_blocker"], True)
        self.assertIs(g["real_world_verified"], False)
        self.assertEqual(self.formal["phase_1"], "BLOCKED")
        self.assertEqual(self.formal["runtime_go_no_go"], "NO_GO")
        self.assertIs(self.formal["real_mt4_access_approved"], False)
        self.assertIs(self.formal["real_order_execution_approved"], False)

    def test_original_g1_scope_and_evidence_requirement_are_preserved(self):
        self.assertEqual(self.history["original_verification_status"], "UNRESOLVED")
        self.assertEqual(self.history["historical_major_field_count"], 20)
        self.assertEqual(self.history["g1_before_scope_approval"]["id"], "G1")
        self.assertEqual(self.history["g1_before_scope_approval"]["real_world_verified"], False)
        self.assertTrue(self.history["has_no_release_authority"])

    def test_owner_decision_is_scope_only_and_not_permission(self):
        for key in (
            "source_original_fx_saf_verified",
            "form01_10_implementation_approved",
            "live_mt4_read_approved", "ea_or_script_execution_approved",
            "order_execution_approved", "stop_release_approved",
            "production_authorized", "independent_broker_account_verified",
        ):
            with self.subTest(key=key):
                self.bad("decision", lambda d, k=key: d.update({k: True}),
                         "UNAUTHORIZED_SCOPE_EFFECT:" + key)

    def test_owner_scope_only_requires_direct_user_turn_provenance(self):
        self.bad("decision", lambda d: d.update(
            owner_decision_origin="AI_INFERRED_APPROVAL"),
            "SCOPE_OWNER_DECISION_INVALID")
        self.bad("decision", lambda d: d.update(
            decision_status="ALL_G1_ACCEPTED"),
            "SCOPE_OWNER_DECISION_INVALID")

    def test_no_old_pair_can_be_promoted_to_the_new_scope(self):
        self.bad("decision", lambda d: d["authorized_scope"].append("GBP/USD"),
                 "SCOPE_TARGET_OR_HISTORY_CHANGED")
        self.bad("formal", lambda d: d["gaps"][0]
                 ["approved_target_pairs"].append("AUD/USD"),
                 "FORMAL_G1_NEW_SCOPE_MISMATCH")
        self.bad("decision", lambda d: d["five_required_fields"].pop(),
                 "SCOPE_TARGET_OR_HISTORY_CHANGED")
        self.bad("formal", lambda d: d["gaps"][0].update(
            approved_major_attribute_count=20),
            "FORMAL_G1_NEW_SCOPE_MISMATCH")

    def test_forged_verified_values_and_g1_release_are_rejected(self):
        self.bad("formal", lambda d: d["gaps"][0].update(
            verified_major_attribute_count=1),
            "FORMAL_G1_NEW_SCOPE_MISMATCH")
        self.bad("formal", lambda d: d["gaps"][0].update(
            real_world_verified=True),
            "G1_FALSELY_ACCEPTED")
        self.bad("formal", lambda d: d["gaps"][0].update(
            implementation_status="ACCEPTED"),
            "G1_FALSELY_ACCEPTED")
        self.bad("formal", lambda d: d.update(g1_evidence_verified=True),
                 "FORMAL_SCOPE_APPROVAL_RECORD_MISMATCH")
        self.bad("decision", lambda d: d.update(real_verified_field_count=15),
                 "SCOPE_DECISION_MISREPRESENTS_REAL_EVIDENCE")
        self.bad("decision", lambda d: d["status_after_change"].update(
            safety_hold_latched=False),
            "OWNER_SCOPE_DECISION_FALSELY_RELEASED_STOP")

    def test_no_fake_mt4_read_permission_or_trade_start(self):
        self.bad("formal", lambda d: d.update(real_mt4_access_approved=True),
                 "STOP_OR_BROKER_PERMISSION_FALSELY_PROMOTED")
        self.bad("formal", lambda d: d.update(forward_trading_enabled=True),
                 "STOP_OR_BROKER_PERMISSION_FALSELY_PROMOTED")
        self.bad("formal", lambda d: d.update(runtime_go_no_go="GO"),
                 "STOP_OR_BROKER_PERMISSION_FALSELY_PROMOTED")
        self.bad("formal", lambda d: d.update(phase_1="ACCEPTED"),
                 "STOP_OR_BROKER_PERMISSION_FALSELY_PROMOTED")
        self.bad("formal", lambda d: d.update(verified_values={"foo": "bar"}),
                 "STOP_OR_BROKER_PERMISSION_FALSELY_PROMOTED")

    def test_legacy_archive_must_be_identical_in_scope_and_provenance(self):
        self.bad("history", lambda d: d.update(historical_major_field_count=15),
                 "LEGACY_SCOPE_ARCHIVE_CHANGED")
        self.bad("history", lambda d: d["g1_before_scope_approval"].update(
            implementation_status="ACCEPTED"),
            "LEGACY_G1_ORIGINAL_SCOPE_CORRUPTED")
        self.bad("history", lambda d: d["g1_before_scope_approval"].update(
            external_or_real_evidence_required=[]),
            "LEGACY_G1_ORIGINAL_SCOPE_CORRUPTED")
        self.bad("history", lambda d: d["g1_before_scope_approval"].update(
            subject="NEW_G1_APPROVED"),
            "LEGACY_G1_ORIGINAL_SCOPE_CORRUPTED")

    def test_supplementary_contract_evidence_never_dropped(self):
        self.bad("formal", lambda d: d["gaps"][0].update(
            external_or_real_evidence_required=[]),
            "G1_BROKER_EVIDENCE_REQUIREMENTS_MISSING")
        self.bad("decision", lambda d: d.update(additional_attributes_remain_required=False),
                 "SCOPE_DECISION_MISREPRESENTS_REAL_EVIDENCE")

    def test_all_other_gates_remain_closed(self):
        self.bad("formal", lambda d: d["gaps"][8].update(
            implementation_status="ACCEPTED"),
            "G1_TO_G9_GATE_FALSELY_RESOLVED")

    def test_malformed_packet_is_not_valid_approval(self):
        self.assertEqual(mod.audit(formal=[]), ["INVALID_G1_SCOPE_RECORD"])
        self.assertEqual(mod.audit(history="invalid"), ["INVALID_G1_SCOPE_RECORD"])
        self.assertEqual(mod.audit(decision=[]), ["INVALID_G1_SCOPE_RECORD"])


if __name__ == "__main__":
    unittest.main()
