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






    def test_p05_06_everyone_not_visible_but_other_principals_unknown(self):
        row = self.docs[mod.PLAN]["p05_checks"][5]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_EVERYONE_NOT_VISIBLE_SECURITY_UNVERIFIED")
        self.assertEqual(row["owner_reported_ntfs_everyone_visibility"],
                         mod.P05_06_EVERYONE_VISIBILITY_OWNER_REPORT)
        self.assertEqual(row["owner_reported_ntfs_everyone_visibility"]
                         ["display_observation"], "EVERYONE_NOT_LISTED")
        self.assertEqual(row["owner_reported_ntfs_everyone_visibility"]
                         ["unfamiliar_principals_present"], "UNKNOWN_NOT_ANSWERED")
        self.assertFalse(row["p05_accepted"])
        self.assertFalse(row["safe_to_proceed"])
        state = mod.snapshot()
        self.assertTrue(state["p05_06_owner_reported_everyone_not_visible"])
        self.assertEqual(state["p05_06_unfamiliar_principals_state"], "UNVERIFIED")
        self.assertFalse(state["p05_06_effective_ntfs_permissions_verified"])
        self.assertFalse(state["p05_06_local_storage_ready"])
        self.assertFalse(state["p05_06_confidential_collection_authorized"])
        self.assertEqual(state["p05_checks_passed"], 0)
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")

    def test_p05_06_everyone_absence_cannot_certify_acl_or_execution(self):
        keys = (
            "individual_or_group_names_collected",
            "windows_security_tab_independently_inspected",
            "effective_acl_or_inherited_permissions_verified",
            "other_builtin_group_or_unknown_account_absence_verified",
            "principal_access_and_write_permissions_verified",
            "network_or_remote_access_absence_verified",
            "evidence_storage_security_approved",
            "acl_or_folder_modified_by_assistant",
            "confidential_data_collection_authorized",
            "p05_accepted",
        )
        for key in keys:
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN, lambda p, k=key: p["p05_checks"][5]
                    ["owner_reported_ntfs_everyone_visibility"].update({k: True}),
                    "P05_06_EVERYONE_ABSENT_FALSELY_TREATED_AS_FULL_ACL_PROOF")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][5]
            ["owner_reported_ntfs_everyone_visibility"].update(
                unfamiliar_principals_present="NONE_VERIFIED"),
            "P05_06_EVERYONE_ABSENT_FALSELY_TREATED_AS_FULL_ACL_PROOF")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][5].update(p05_accepted=True),
            "P05_PREMATURE_OR_UNVERIFIED:P05-06")
        self.refuse(
            mod.PLAN, lambda p: p.update(p06_observation_authorized=True),
            "FALSE_REAL_OPERATION_AUTHORITY:p06_observation_authorized")

    def test_p05_06_not_shared_owner_report_keeps_all_gates_blocked(self):
        row = self.docs[mod.PLAN]["p05_checks"][5]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_EVERYONE_NOT_VISIBLE_SECURITY_UNVERIFIED")
        self.assertEqual(row["owner_reported_network_sharing"],
                         mod.P05_06_NETWORK_SHARING_OWNER_REPORT)
        self.assertFalse(row["safe_to_proceed"])
        self.assertFalse(row["p05_accepted"])
        self.assertIsNone(row["evidence_reference"])
        state = mod.snapshot()
        self.assertTrue(state["p05_06_owner_reported_not_network_shared"])
        self.assertFalse(state["p05_06_network_sharing_independently_verified"])
        self.assertFalse(state["p05_06_ntfs_acl_independently_verified"])
        self.assertFalse(state["p05_06_local_storage_ready"])
        self.assertFalse(state["p05_06_confidential_collection_authorized"])
        self.assertEqual(state["p05_checks_passed"], 0)
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")

    def test_p05_06_not_shared_ui_cannot_certify_acl_or_authorize_mt4(self):
        fields = (
            "windows_share_tab_display_independently_verified",
            "effective_ntfs_acl_and_inheritance_verified",
            "advanced_network_share_and_admin_share_absence_verified",
            "remote_access_or_other_app_access_absence_verified",
            "cloud_sync_or_backup_absence_independently_verified",
            "private_data_access_and_retention_policy_approved",
            "folder_sharing_modified_by_assistant",
            "sensitive_evidence_collection_authorized",
            "any_file_or_mt4_log_collected",
            "p05_accepted",
        )
        for key in fields:
            with self.subTest(key=key):
                self.refuse(mod.PLAN, lambda p, k=key: p["p05_checks"][5]
                            ["owner_reported_network_sharing"].update({k: True}),
                            "P05_06_NOT_SHARED_FALSELY_TREATED_AS_ACCESS_CONTROL_PROOF")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][5]
                    ["owner_reported_network_sharing"].update(reported_state="VERIFIED"),
                    "P05_06_NOT_SHARED_FALSELY_TREATED_AS_ACCESS_CONTROL_PROOF")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][5].update(p05_accepted=True),
                    "P05_PREMATURE_OR_UNVERIFIED:P05-06")
        self.refuse(mod.PLAN, lambda p: p.update(p06_observation_authorized=True),
                    "FALSE_REAL_OPERATION_AUTHORITY:p06_observation_authorized")

    def test_p05_06_no_cloud_sync_is_owner_report_only(self):
        row = self.docs[mod.PLAN]["p05_checks"][5]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_EVERYONE_NOT_VISIBLE_SECURITY_UNVERIFIED")
        self.assertEqual(row["owner_reported_cloud_sync"],
                         mod.P05_06_CLOUD_SYNC_OWNER_REPORT)
        self.assertEqual(row["owner_reported_cloud_sync"]["reported_state"],
                         "NOT_SYNCED")
        self.assertFalse(row["safe_to_proceed"])
        self.assertFalse(row["p05_accepted"])
        snap = mod.snapshot()
        self.assertTrue(snap["p05_06_owner_reported_no_cloud_sync"])
        self.assertFalse(snap["p05_06_cloud_sync_absence_verified"])
        self.assertFalse(snap["p05_06_windows_permissions_verified"])
        self.assertFalse(snap["p05_06_confidential_collection_authorized"])
        self.assertEqual(snap["p05_checks_passed"], 0)
        self.assertEqual(snap["runtime_go_no_go"], "NO_GO")

    def test_p05_06_no_sync_report_cannot_approve_storage_or_collection(self):
        fields = ("service_or_folder_settings_independently_inspected",
                  "windows_cloud_sync_or_backup_absence_independently_verified",
                  "cloud_sync_setting_changed_by_assistant",
                  "evidence_collected_or_uploaded",
                  "sensitive_evidence_collection_authorized",
                  "p05_accepted")
        for key in fields:
            with self.subTest(key=key):
                self.refuse(mod.PLAN, lambda p, k=key: p["p05_checks"][5]
                            ["owner_reported_cloud_sync"].update({k: True}),
                            "P05_06_CLOUD_SYNC_REPORT_FALSELY_VERIFIED_OR_PROMOTED")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][5]
                    ["owner_reported_cloud_sync"].update(
                        reported_state="VERIFIED_DISABLED"),
                    "P05_06_CLOUD_SYNC_REPORT_FALSELY_VERIFIED_OR_PROMOTED")
        self.refuse(mod.PLAN, lambda p: p["p05_checks"][5].update(
                    current_status="ACCEPTED"),
                    "P05_PREMATURE_OR_UNVERIFIED:P05-06")
        self.refuse(mod.PLAN, lambda p: p.update(p06_observation_authorized=True),
                    "FALSE_REAL_OPERATION_AUTHORITY:p06_observation_authorized")

    def test_p05_06_creation_supersedes_previous_no_folder_observation(self):
        p = self.docs[mod.PLAN]
        row = p["p05_checks"][5]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_EVERYONE_NOT_VISIBLE_SECURITY_UNVERIFIED")
        self.assertEqual(row["owner_reported_folder_creation"],
                         mod.P05_06_FOLDER_CREATION_OWNER_REPORT)
        self.assertEqual(
            row["owner_reported_private_storage"],
            mod.P05_06_PRIVATE_STORAGE_OWNER_REPORT)
        self.assertFalse(row["p05_accepted"])
        self.assertFalse(row["safe_to_proceed"])
        self.assertIsNone(row["evidence_reference"])
        snap = mod.snapshot()
        self.assertTrue(snap["p05_06_prior_absence_report_retained"])
        self.assertTrue(snap["p05_06_owner_reported_folder_created"])
        self.assertFalse(snap["p05_06_local_storage_ready"])
        self.assertFalse(snap["p05_06_cloud_sync_absence_verified"])
        self.assertFalse(snap["p05_06_windows_permissions_verified"])
        self.assertFalse(snap["p05_06_confidential_collection_authorized"])
        self.assertEqual(snap["p05_checks_passed"], 0)
        self.assertEqual(snap["runtime_go_no_go"], "NO_GO")

    def test_p05_06_owner_created_folder_never_becomes_verified_or_access_authority(self):
        keys = (
            "private_absolute_path_stored_in_git",
            "private_path_repeated_in_documentation",
            "independently_verified_on_windows",
            "git_exclusion_independently_verified",
            "cloud_sync_or_backup_absence_verified",
            "windows_acl_and_sharing_verified",
            "encryption_and_retention_policy_verified",
            "sensitive_material_collection_authorized",
            "private_data_collected_or_uploaded",
            "folder_created_or_modified_by_assistant",
            "p05_accepted",
        )
        for key in keys:
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN,
                    lambda p, k=key: p["p05_checks"][5]
                    ["owner_reported_folder_creation"].update({k: True}),
                    "P05_06_FOLDER_CREATED_REPORT_FALSE_SECURITY_CERTIFICATION")
        self.refuse(
            mod.PLAN,
            lambda p: p["p05_checks"][5]["owner_reported_folder_creation"]
            .update(observation="INDEPENDENTLY_VERIFIED"),
            "P05_06_FOLDER_CREATED_REPORT_FALSE_SECURITY_CERTIFICATION")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][5]
            ["owner_reported_folder_creation"].update(
                private_full_path="UNSAFE_PRIVATE_PATH_IN_GIT"),
            "P05_06_FOLDER_CREATED_REPORT_FALSE_SECURITY_CERTIFICATION")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][5].update(p05_accepted=True),
            "P05_PREMATURE_OR_UNVERIFIED:P05-06")

    def test_p05_06_owner_reports_no_private_storage_folder(self):
        p = self.docs[mod.PLAN]
        row = p["p05_checks"][5]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_EVERYONE_NOT_VISIBLE_SECURITY_UNVERIFIED")
        self.assertEqual(row["owner_reported_private_storage"],
                         mod.P05_06_PRIVATE_STORAGE_OWNER_REPORT)
        self.assertFalse(row["p05_accepted"])
        self.assertFalse(row["safe_to_proceed"])
        self.assertIsNone(row["evidence_reference"])
        snap = mod.snapshot()
        self.assertTrue(snap["p05_06_prior_absence_report_retained"])
        self.assertTrue(snap["p05_06_owner_reported_folder_created"])
        self.assertFalse(snap["p05_06_local_storage_ready"])
        self.assertFalse(snap["p05_06_confidential_collection_authorized"])
        self.assertEqual(snap["p05_checks_passed"], 0)
        self.assertEqual(snap["runtime_go_no_go"], "NO_GO")

    def test_p05_06_no_folder_must_not_grant_storage_or_mt4_access(self):
        fields = (
            "folder_path_disclosed",
            "local_folder_independently_verified",
            "out_of_repo_private_folder_ready",
            "confidential_evidence_collection_authorized",
            "any_log_or_screenshot_collected",
            "filesystem_modified_by_assistant",
            "p05_accepted",
        )
        for name in fields:
            with self.subTest(name=name):
                self.refuse(
                    mod.PLAN,
                    lambda p, k=name: p["p05_checks"][5]
                    ["owner_reported_private_storage"].update({k: True}),
                    "P05_06_OWNER_NO_FOLDER_FALSIFIED_OR_OVERCLAIMED")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][5]
            ["owner_reported_private_storage"].update(
                response="FOLDER_CREATED"),
            "P05_06_OWNER_NO_FOLDER_FALSIFIED_OR_OVERCLAIMED")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][5].update(
                current_status="STORAGE_VERIFIED"),
            "P05_PREMATURE_OR_UNVERIFIED:P05-06")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][5].update(p05_accepted=True),
            "P05_PREMATURE_OR_UNVERIFIED:P05-06")
        self.refuse(
            mod.PLAN, lambda p: p.update(p05_passed_checks=1),
            "P05_UNJUSTIFIED_PRECHECK_PASS")
        self.refuse(
            mod.PLAN, lambda p: p.update(p06_observation_authorized=True),
            "FALSE_REAL_OPERATION_AUTHORITY:p06_observation_authorized")

    def test_owner_reports_this_mt4_only_without_independent_session_proof(self):
        p = self.docs[mod.PLAN]
        row = p["p05_checks"][3]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTS_THIS_MT4_ONLY_NO_PARALLEL_LOGIN_INDEPENDENTLY_UNVERIFIED")
        self.assertEqual(row["owner_reported_session_observation"],
                         mod.P05_04_SINGLE_SESSION_OWNER_REPORT)
        self.assertIsNone(row["observation_at_utc"])
        self.assertFalse(row["p05_accepted"])
        self.assertFalse(row["safe_to_proceed"])
        self.assertEqual(p["p05_passed_checks"], 0)
        snap = mod.snapshot()
        self.assertTrue(snap["p05_04_owner_reported_single_mt4_only"])
        self.assertFalse(snap["p05_04_single_session_independently_verified"])
        self.assertEqual(snap["runtime_go_no_go"], "NO_GO")

    def test_solo_mt4_report_must_not_auto_verify_demo_terms_or_release_gate(self):
        for key in (
            "other_pc_or_mt4_same_demo_login_independently_verified_absent",
            "login_session_count_broker_verified",
            "different_demo_account_absence_independently_verified",
            "demo_contract_compliance_independently_verified",
            "additional_login_or_account_created_by_assistant",
        ):
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN,
                    lambda p, k=key: p["p05_checks"][3]
                    ["owner_reported_session_observation"].update({k: True}),
                    "P05_04_OWNER_SINGLE_SESSION_REPORT_OVERCLAIMED")
        self.refuse(
            mod.PLAN,
            lambda p: p["p05_checks"][3]["owner_reported_session_observation"]
            .update(reported_usage="TWO_MT4_LOGINS"),
            "P05_04_OWNER_SINGLE_SESSION_REPORT_OVERCLAIMED")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][3].update(p05_accepted=True),
            "P05_PREMATURE_OR_UNVERIFIED:P05-04")
        self.refuse(
            mod.PLAN, lambda p: p.update(p05_passed_checks=1),
            "P05_UNJUSTIFIED_PRECHECK_PASS")

    def test_user_reported_demo_account_is_not_independent_account_identity_proof(self):
        row = self.docs[mod.PLAN]["p05_checks"][0]
        self.assertEqual(row["owner_reported_account_type"], mod.P05_01_DEMO_TYPE_REPORT)
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_DEMO_ACCOUNT_COMMUNICATING_IDENTITY_UNVERIFIED")
        self.assertFalse(row["p05_accepted"])
        self.assertFalse(row["safe_to_proceed"])
        snap = mod.snapshot()
        self.assertTrue(snap["p05_01_owner_reported_demo_account"])
        self.assertFalse(snap["p05_01_independent_account_identity_verified"])
        self.assertEqual(snap["p05_checks_passed"], 0)

    def test_demo_report_cannot_prove_login_or_server_consistency(self):
        for key in (
            "independent_broker_account_type_verified",
            "same_as_historically_known_demo_login_verified",
            "server_account_or_session_independently_verified",
            "account_identifiers_disclosed",
            "p05_accepted",
        ):
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN,
                    lambda p, k=key: p["p05_checks"][0]
                    ["owner_reported_account_type"].update({k: True}),
                    "P05_01_DEMO_OWNER_ATTESTATION_OVERCLAIMED")

    def test_macd_sample_visible_does_not_prove_ea_execution_or_safety(self):
        row = self.docs[mod.PLAN]["p05_checks"][1]
        self.assertEqual(row["owner_reported_ea_visibility"],
                         mod.P05_02_EA_VISIBLE_REPORT)
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_MACD_SAMPLE_VISIBLE_RUNTIME_UNVERIFIED")
        self.assertFalse(row["safe_to_proceed"])
        self.assertFalse(row["p05_accepted"])
        self.assertTrue(mod.snapshot()["p05_02_macd_sample_visible_runtime_unverified"])
        for key in ("attachment_location_currently_verified",
                    "active_or_trading_verified", "ea_changed_or_stopped",
                    "order_risk_absence_verified"):
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN, lambda p, k=key: p["p05_checks"][1]
                    ["owner_reported_ea_visibility"].update({k: True}),
                    "P05_02_EA_VISIBILITY_FALSELY_INTERPRETED_AS_RUNNING")



    def test_sad_face_icon_is_only_owner_ui_report(self):
        p = self.docs[mod.PLAN]
        row = p["p05_checks"][1]
        self.assertEqual(row["owner_reported_chart_ea_face_icon"],
                         mod.P05_02_FACE_ICON_OWNER_REPORT)
        self.assertEqual(
            row["owner_reported_chart_ea_face_icon"]["display_observation"],
            "SAD_FACE_ICON")
        self.assertEqual(row["owner_reported_autotrading_display"]
                         ["display_observation"], "AUTOTRADING_BUTTON_OFF")
        self.assertFalse(row["safe_to_proceed"])
        self.assertFalse(row["p05_accepted"])
        snap = mod.snapshot()
        self.assertTrue(snap["p05_02_sad_face_icon_owner_reported_not_execution_proof"])
        self.assertFalse(snap["p05_02_ea_or_orders_absent_verified"])
        self.assertEqual(snap["p05_checks_passed"], 0)
        self.assertEqual(snap["runtime_go_no_go"], "NO_GO")

    def test_sad_face_icon_cannot_be_ea_stop_broker_or_order_proof(self):
        keys = (
            "expert_advisor_attached_independently_verified",
            "ea_execution_state_independently_verified",
            "autotrading_permission_for_this_ea_independently_verified",
            "all_ea_scripts_inactive_verified",
            "server_order_or_position_absence_verified",
            "account_or_broker_sync_independently_verified",
            "chart_or_terminal_modified_by_assistant",
            "p05_accepted",
        )
        for key in keys:
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN,
                    lambda p, k=key: p["p05_checks"][1]
                    ["owner_reported_chart_ea_face_icon"].update({k: True}),
                    "P05_02_FACE_ICON_FALSELY_TREATED_AS_EA_OR_ORDER_PROOF")
        self.refuse(mod.PLAN,
                    lambda p: p["p05_checks"][1]
                    ["owner_reported_chart_ea_face_icon"].update(
                        display_observation="SMILING_FACE_ICON"),
                    "P05_02_FACE_ICON_FALSELY_TREATED_AS_EA_OR_ORDER_PROOF")
        self.refuse(mod.PLAN,
                    lambda p: p["p05_checks"][1].update(
                        current_status="EA_DISABLED_VERIFIED"),
                    "P05_PREMATURE_OR_UNVERIFIED:P05-02")
        self.refuse(mod.PLAN,
                    lambda p: p.update(p05_passed_checks=1),
                    "P05_UNJUSTIFIED_PRECHECK_PASS")

    def test_autotrading_off_ui_report_does_not_verify_ea_or_order_state(self):
        row = self.docs[mod.PLAN]["p05_checks"][1]
        self.assertEqual(row["owner_reported_autotrading_display"],
                         mod.P05_02_AUTOTRADING_OFF_OWNER_REPORT)
        self.assertEqual(
            row["owner_reported_autotrading_display"]["display_observation"],
            "AUTOTRADING_BUTTON_OFF")
        self.assertFalse(row["p05_accepted"])
        self.assertFalse(row["safe_to_proceed"])
        snap = mod.snapshot()
        self.assertTrue(snap["p05_02_autotrading_off_owner_reported_not_broker_verified"])
        self.assertFalse(snap["p05_02_ea_or_orders_absent_verified"])
        self.assertEqual(snap["p05_checks_passed"], 0)
        self.assertEqual(snap["runtime_go_no_go"], "NO_GO")

    def test_autotrading_off_report_cannot_promote_broker_proof_or_approval(self):
        keys = (
            "broker_execution_state_independently_verified",
            "ea_or_script_activity_absent_verified",
            "server_positions_or_pending_orders_absent_verified",
            "button_or_ea_changed_by_assistant",
            "account_identity_verified_by_report",
            "p05_accepted",
        )
        for key in keys:
            with self.subTest(key=key):
                self.refuse(
                    mod.PLAN,
                    lambda p, k=key: p["p05_checks"][1]
                    ["owner_reported_autotrading_display"].update({k: True}),
                    "P05_02_AUTOTRADING_OFF_FALSELY_TREATED_AS_EXECUTION_PROOF")
        self.refuse(
            mod.PLAN,
            lambda p: p["p05_checks"][1]
            ["owner_reported_autotrading_display"].update(
                display_observation="AUTOTRADING_BUTTON_ON"),
            "P05_02_AUTOTRADING_OFF_FALSELY_TREATED_AS_EXECUTION_PROOF")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][1].update(p05_accepted=True),
            "P05_PREMATURE_OR_UNVERIFIED:P05-02")
        self.refuse(
            mod.PLAN, lambda p: p.update(
                p05_current_observation_summary="BROKER_VERIFIED_SAFE"),
            "P05_UI_OBSERVATION_MISTAKEN_FOR_ACCOUNT_RECONCILIATION")

    def test_corrected_account_creation_date_is_user_report_not_identity_evidence(self):
        check = self.docs[mod.PLAN]["p05_checks"][0]
        self.assertEqual(check["owner_reported_account_creation"],
                         mod.P05_01_ACCOUNT_CREATION_DATE_CORRECTION)
        self.assertEqual(check["owner_reported_account_creation"]
                         ["corrected_creation_date"], "2026-10-26")
        self.assertEqual(check["owner_reported_account_creation"]
                         ["superseded_incorrect_date"], "2026-11-26")
        self.assertFalse(check["safe_to_proceed"])
        self.assertFalse(check["p05_accepted"])
        self.assertEqual(mod.snapshot()["p05_01_owner_reported_creation_date"],
                         "2026-10-26")
        self.assertFalse(mod.snapshot()["p05_01_account_same_as_prior_demo_verified"])
        self.assertEqual(mod.snapshot()["p05_checks_passed"], 0)

    def test_date_correction_cannot_falsely_verify_account_or_demo_identity(self):
        for name in (
            "account_type_confirmed",
            "same_as_previously_used_demo_account_confirmed",
            "account_identity_independently_verified",
            "server_account_reconciled",
        ):
            with self.subTest(field=name):
                self.refuse(
                    mod.PLAN, lambda p, k=name: p["p05_checks"][0]
                    ["owner_reported_account_creation"].update({k: True}),
                    "P05_01_CREATION_DATE_OR_ACCOUNT_IDENTITY_OVERCLAIMED")
        self.refuse(
            mod.PLAN, lambda p: p["p05_checks"][0]
            ["owner_reported_account_creation"].update(
                corrected_creation_date="2026-11-26"),
            "P05_01_CREATION_DATE_OR_ACCOUNT_IDENTITY_OVERCLAIMED")

    def test_connection_display_is_user_report_not_server_or_account_verification(self):
        p = self.docs[mod.PLAN]
        row = p["p05_checks"][0]
        self.assertEqual(row["current_status"],
                         "OWNER_REPORTED_DEMO_ACCOUNT_COMMUNICATING_IDENTITY_UNVERIFIED")
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
