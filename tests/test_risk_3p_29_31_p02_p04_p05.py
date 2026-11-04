"""P02/P04 procedural owner approval and P05 fail-closed evidence tests."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_29_31_p02_p04_p05 as mod


class OwnerProcedureAndP05Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {k: mod._read(mod.ROOT, k) for k in (
            mod.PLAN, mod.PATH, mod.PROTOCOL, mod.UPSTREAM, mod.SCOPE,
            mod.GATES, mod.SAFETY, mod.DOCKET,
        )}

    def refuse(self, file, mutate, expected):
        d = copy.deepcopy(self.docs)
        mutate(d[file])
        errors = mod.audit(injected=d)
        self.assertIn(expected, errors, errors)

    def test_baseline_two_method_approvals_and_zero_observation(self):
        self.assertEqual(mod.audit(), [])
        p = self.docs[mod.PLAN]
        self.assertEqual([x["id"] for x in p["decisions"]], ["P02", "P04"])
        self.assertEqual([x["owner_approved"] for x in p["decisions"]],
                         [True, True])
        self.assertEqual(p["p05_total_checks"], 8)
        self.assertEqual(p["p05_passed_checks"], 0)
        self.assertTrue(all(x["safe_to_proceed"] is False
                            for x in p["p05_checks"]))
        self.assertEqual(mod.snapshot()["audit_status"], "PASS_DOCUMENT_ONLY")
        self.assertEqual(mod.snapshot()["runtime_go_no_go"], "NO_GO")

    def test_connection_display_is_user_report_not_server_or_account_verification(self):
        p = self.docs[mod.PLAN]
        row = p["p05_checks"][0]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_MT4_COMMUNICATING_DISPLAY_ACCOUNT_UNVERIFIED")
        self.assertEqual(row["owner_reported_connection_display"],
                         mod.P05_01_OWNER_REPORT)
        self.assertFalse(row["safe_to_proceed"])
        self.assertFalse(row["p05_accepted"])
        self.assertIsNone(row["observation_at_utc"])
        summary = mod.snapshot()
        self.assertTrue(summary["p05_01_owner_reported_communicating_display"])
        self.assertFalse(summary["p05_01_account_and_server_verified"])
        self.assertFalse(summary["p05_03_broker_orders_confirmed_absent"])
        self.assertEqual(summary["p05_checks_passed"], 0)
        self.assertEqual(summary["runtime_go_no_go"], "NO_GO")

    def test_communication_indicator_cannot_fabricate_server_sync_or_session_permission(self):
        for key in ("account_type_confirmed", "account_identity_confirmed",
                    "server_connection_independently_verified",
                    "order_state_synchronized_with_server_verified",
                    "terminal_session_authorized_by_report"):
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN,
                    lambda p, k=key: p["p05_checks"][0]["owner_reported_connection_display"]
                    .update({k: True}),
                    "P05_01_CONNECTION_UI_REPORT_OVERCLAIMED")
        self.refuse(
            mod.PLAN,
            lambda p: p["p05_checks"][0]["owner_reported_connection_display"]
            .update(display_report="BROKER_VERIFIED_ZERO_ORDERS"),
            "P05_01_CONNECTION_UI_REPORT_OVERCLAIMED")
        self.refuse(
            mod.PLAN,
            lambda p: p["p05_checks"][0].update(p05_accepted=True),
            "P05_PREMATURE_OR_UNVERIFIED:P05-01")
        self.refuse(
            mod.PLAN,
            lambda p: p["p05_checks"][2]["owner_reported_ui_observation"]
            .update(connection_status="BROKER_VERIFIED_SYNCHRONIZED"),
            "P05_03_UI_REPORT_FALSIFIED_OR_OVERCLAIMED")

    def test_balance_only_trade_tab_report_does_not_verify_server_orders(self):
        p = self.docs[mod.PLAN]
        row = p["p05_checks"][2]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_TRADE_TAB_BALANCE_ONLY_NO_ORDER_ROWS_VISIBLE")
        self.assertEqual(row["owner_reported_ui_observation"],
                         mod.P05_03_OWNER_REPORT)
        self.assertFalse(row["p05_accepted"])
        self.assertFalse(row["safe_to_proceed"])
        self.assertIsNone(row["observation_at_utc"])
        self.assertEqual(p["p05_passed_checks"], 0)
        state = mod.snapshot()
        self.assertTrue(state["p05_03_user_reported_no_order_rows_visible"])
        self.assertFalse(state["p05_03_broker_orders_confirmed_absent"])
        self.assertFalse(state["p04_real_mt4_session_allowed"])

    def test_trade_tab_row_report_cannot_be_treated_as_broker_reconciliation(self):
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][2]
                    ["owner_reported_ui_observation"].update(
                        server_order_state_reconciled=True),
                    "P05_03_UI_REPORT_FALSIFIED_OR_OVERCLAIMED")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][2]
                    ["owner_reported_ui_observation"].update(
                        account_identity_confirmed=True),
                    "P05_03_UI_REPORT_FALSIFIED_OR_OVERCLAIMED")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][2]
                    ["owner_reported_ui_observation"].update(
                        connection_status="CONNECTED"),
                    "P05_03_UI_REPORT_FALSIFIED_OR_OVERCLAIMED")
        self.refuse(mod.PLAN, lambda p: p.update(
                        p05_current_observation_summary="SERVER_ORDERS_ZERO"),
                    "P05_UI_OBSERVATION_MISTAKEN_FOR_ACCOUNT_RECONCILIATION")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][2].update(
                        p05_accepted=True),
                    "P05_PREMATURE_OR_UNVERIFIED:P05-03")

    def test_owner_provenance_must_be_current_explicit_turn(self):
        self.refuse(mod.PLAN, lambda p: p.update(
            source="AI_INFERRED_COMPLIANCE"),
            "OWNER_APPROVAL_IDENTITY_OR_SOURCE_DRIFT")
        self.refuse(mod.PLAN, lambda p: p.update(date_jst="2020-01-01"),
                    "OWNER_APPROVAL_IDENTITY_OR_SOURCE_DRIFT")

    def test_p02_is_a_method_not_fifteen_originals_verified(self):
        self.refuse(mod.PLAN, lambda p: p["decisions"][0].update(
            fx_saf_original_verified_count=15),
            "P02_FALSE_ORIGINAL_SOURCE_VERIFICATION")
        self.refuse(mod.PLAN, lambda p: p["decisions"][0].update(
            original_source_access_performed=True),
            "P02_FALSE_ORIGINAL_SOURCE_VERIFICATION")
        self.refuse(mod.PLAN, lambda p: p["decisions"][0].update(
            form_implementation_approvals_recorded=43),
            "P02_FALSE_ORIGINAL_SOURCE_VERIFICATION")

    def test_p04_method_does_not_authorize_current_terminal_session(self):
        self.refuse(mod.PLAN, lambda p: p["decisions"][1].update(
            real_mt4_login_authorized_now=True),
            "P04_FALSE_TERMINAL_SESSION_PERMISSION")
        self.refuse(mod.PLAN, lambda p: p["decisions"][1].update(
            script_or_ea_execution_authorized=True),
            "P04_FALSE_TERMINAL_SESSION_PERMISSION")
        self.refuse(mod.PLAN, lambda p: p["decisions"][1].update(
            order_or_position_changes_authorized=True),
            "P04_FALSE_TERMINAL_SESSION_PERMISSION")

    def test_cannot_forge_method_owner_approval(self):
        self.refuse(mod.PLAN, lambda p: p["decisions"][0].update(
            owner_approved=False),
            "OWNER_P02_P04_METHOD_DECISION_INVALID")
        self.refuse(mod.PLAN, lambda p: p["decisions"][1].update(
            method_status="OBSERVER_EXECUTED"),
            "OWNER_P02_P04_METHOD_DECISION_INVALID")

    def test_eight_p05_items_must_be_present_and_exactly_unknown(self):
        self.refuse(mod.PLAN, lambda p: p["p05_checks"].pop(),
                    "P05_MANDATORY_CHECK_SET_CHANGED")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][0].update(
            check_id="P05-08"), "P05_MANDATORY_CHECK_SET_CHANGED")
        for i, item in enumerate(self.docs[mod.PLAN]["p05_checks"]):
            with self.subTest(id=item["check_id"]):
                self.refuse(mod.PLAN, lambda p, n=i: p["p05_checks"][n].update(
                    current_status="CONFIRMED"),
                    "P05_PREMATURE_OR_UNVERIFIED:" + item["check_id"])
                self.refuse(mod.PLAN, lambda p, n=i: p["p05_checks"][n].update(
                    safe_to_proceed=True),
                    "P05_PREMATURE_OR_UNVERIFIED:" + item["check_id"])

    def test_p05_evidence_utc_and_reviewer_are_not_invented(self):
        for k, v in (("evidence_reference", "fake-provenance"),
                     ("observation_at_utc", "2026-11-04T05:00:00Z"),
                     ("reviewer_reference", "fake-owner")):
            with self.subTest(key=k):
                self.refuse(mod.PLAN, lambda p, name=k, val=v:
                            p["p05_checks"][3].update({name: val}),
                            "P05_PREMATURE_OR_UNVERIFIED:P05-04")

    def test_no_skip_to_p05_p06_or_p07(self):
        self.refuse(mod.PLAN, lambda p: p.update(p05_passed_checks=8),
                    "P05_UNJUSTIFIED_PRECHECK_PASS")
        self.refuse(mod.PLAN, lambda p: p.update(
            p05_gate_status="PASSED"),
            "P05_UNJUSTIFIED_PRECHECK_PASS")
        for name in mod.UNAUTHORIZED:
            with self.subTest(name=name):
                self.refuse(mod.PLAN,
                            lambda p, key=name: p.update({key: True}),
                            "FALSE_REAL_OPERATION_AUTHORITY:" + name)

    def test_historical_macd_sample_and_orders_must_remain_unreconciled(self):
        self.refuse(mod.PLAN,
                    lambda p: p["historical_existing_account_hazards"].clear(),
                    "EVIDENCE_COUNT_OR_PRIOR_ACCOUNT_HAZARD_DRIFT")
        self.refuse(mod.PLAN,
                    lambda p: p.update(g1_actual_broker_fields_verified=15),
                    "EVIDENCE_COUNT_OR_PRIOR_ACCOUNT_HAZARD_DRIFT")

    def test_cross_source_approvals_cannot_be_promoted_to_executed(self):
        self.refuse(mod.PATH, lambda p: p["proposed_dependency_nodes"][1]
                    .update(status="ALL_ORIGINALS_VERIFIED"),
                    "CRITICAL_PATH_P02_P04_METHOD_APPROVAL_DRIFT")
        self.refuse(mod.PATH, lambda p: p["proposed_dependency_nodes"][3]
                    .update(status="REAL_MT4_SESSION_APPROVED"),
                    "CRITICAL_PATH_P02_P04_METHOD_APPROVAL_DRIFT")
        self.refuse(mod.PROTOCOL, lambda p: p.update(
            owner_approved_real_read=True),
            "READONLY_PROTOCOL_METHOD_MISTAKEN_FOR_OBSERVATION")
        self.refuse(mod.UPSTREAM, lambda p: p.update(
            p05_environment_precheck_status="PASSED"),
            "UPSTREAM_EVIDENCE_STATUS_PROMOTED")

    def test_form_and_fx_saf_remain_pending(self):
        self.refuse(mod.SAFETY, lambda p: p["items"][0].update(
            source_review="VERIFIED_ORIGINAL"),
            "UNREVIEWED_SOURCE_FALSELY_ACCEPTED")
        self.refuse(mod.DOCKET, lambda p: p["decisions"][0].update(
            owner_decision="APPROVED"),
            "FORM43_FALSELY_ACCEPTED")
        self.refuse(mod.GATES, lambda p: p.update(
            real_mt4_access_approved=True),
            "FORMAL_GATES_OR_MT4_ACCESS_PROMOTED")

    def test_safety_hold_beyond_scope_approval(self):
        for key, value in (("phase_1", "ACCEPTED"),
                           ("runtime_go_no_go", "GO"),
                           ("safety_hold_latched", False),
                           ("verified_values", {"fake": 1})):
            with self.subTest(key=key):
                self.refuse(mod.PLAN,
                            lambda p, k=key, v=value: p.update({k: v}),
                            "SAFETY_HOLD_OR_NO_GO_PROMOTED")

    def test_invalid_plan_fails_closed_without_carryover(self):
        d = copy.deepcopy(self.docs)
        d[mod.PLAN] = []
        self.assertEqual(mod.audit(injected=d),
                         ["INVALID_PROCEDURAL_APPROVAL_PLAN"])


if __name__ == "__main__":
    unittest.main()
