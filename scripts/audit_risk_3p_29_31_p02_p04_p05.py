"""RISK-3P-29..31: P02/P04 procedural approvals and P05 safety preflight.

An owner-approved *method* is not performed reconciliation or a terminal
session grant. The only successful result is a blocked documentary register.
This module reads local JSON; no MT4, broker, filesystem writes, or credentials.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.review_mt4_manual_symbol_3p_v3 import PAIRS, FIVE

ROOT = Path(__file__).resolve().parents[1]
PLAN = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
PATH = "specs/risk_3p_23_26_owner_decision_critical_path_20261104.json"
PROTOCOL = "specs/risk_3p_18_19_g1_readonly_provenance_protocol_20261104.json"
UPSTREAM = "specs/risk_3p_16_17_owner_g1_readiness_preflight_20261104.json"
SCOPE = "specs/risk_3p_28_g1_scope_owner_decision_20261104.json"
GATES = "specs/p0_01_d5_25_gap_verification_matrix.json"
SAFETY = "specs/source_review_priority.json"
DOCKET = "specs/risk_3p_22_form43_owner_review_docket_20261104.json"
P05_IDS = tuple(f"P05-{i:02d}" for i in range(1, 9))
P05_STATES = (
    "OWNER_REPORTED_DEMO_ACCOUNT_COMMUNICATING_IDENTITY_UNVERIFIED",
    "OWNER_REPORTED_MACD_SAMPLE_VISIBLE_RUNTIME_UNVERIFIED",
    "OWNER_REPORTED_TRADE_TAB_BALANCE_ONLY_NO_ORDER_ROWS_VISIBLE",
    "OWNER_REPORTS_THIS_MT4_ONLY_NO_PARALLEL_LOGIN_INDEPENDENTLY_UNVERIFIED",
    "NOT_DEMONSTRATED_ON_CURRENT_ENVIRONMENT",
    "OWNER_ACCEPTED_LOCAL_FOLDER_AND_PARENTS_FOR_OFFLINE_PLANNING_ONLY",
    "ACTUAL_MT4_SYMBOL_AND_TIME_NOT_OBSERVED",
    "NO_SEPARATE_P05_PASS_OR_OPERATOR_ATTESTATION",
)
P05_06_UNFAMILIAR_PRINCIPALS_OWNER_REPORT = {
    "source": "USER_EXPLICIT_NO_UNFAMILIAR_GROUPS_OR_ACCOUNTS_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-06",
    "observation": "NO_UNFAMILIAR_ACCOUNTS_OR_GROUPS_DISPLAYED",
    "classification": "OWNER_REPORTED_UI_OBSERVATION_ONLY",
    "all_effective_ntfs_acl_principals_independently_verified": False,
    "inheritance_or_nested_group_memberships_independently_verified": False,
    "raw_account_names_or_windows_path_collected": False,
    "share_or_acl_setting_modified": False,
    "p05_accepted": False
}

P05_06_OWNER_STORAGE_SECURITY_ACCEPTANCE = {
    "source": "USER_EXPLICIT_ACCEPT_FOLDER_AND_PARENT_SECURITY_AS_SATISFACTORY_CURRENT_CHAT",
    "decision_on_jst_date": "2026-11-06",
    "decision": "OWNER_ACCEPTS_FOLDER_AND_PARENT_SECURITY_FOR_CONTINUED_OFFLINE_WORK",
    "accepted_for": "OFFLINE_DESIGN_AND_SYNTHETIC_TEST_PLANNING_ONLY",
    "applies_to_reported_private_folder_and_ancestors": True,
    "not_an_independent_windows_security_audit": True,
    "effective_ntfs_acl_independently_verified": False,
    "cloud_backup_absence_independently_verified": False,
    "real_mt4_session_or_data_collection_authorized": False,
    "p05_independent_preflight_accepted": False,
    "private_broker_data_upload_authorized": False,
    "trade_or_order_execution_authorized": False,
    "safety_hold_release_authorized": False
}

P05_06_EVERYONE_VISIBILITY_OWNER_REPORT = {
    "source": "USER_EXPLICIT_EVERYONE_NOT_VISIBLE_REPLY_TO_P05_06_SECURITY_TAB_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "display_observation": "EVERYONE_NOT_LISTED",
    "classification": "OWNER_REPORTED_WINDOWS_SECURITY_TAB_UI_ONLY",
    "unfamiliar_principals_present": "UNKNOWN_NOT_ANSWERED",
    "individual_or_group_names_collected": False,
    "windows_security_tab_independently_inspected": False,
    "effective_acl_or_inherited_permissions_verified": False,
    "other_builtin_group_or_unknown_account_absence_verified": False,
    "principal_access_and_write_permissions_verified": False,
    "network_or_remote_access_absence_verified": False,
    "evidence_storage_security_approved": False,
    "acl_or_folder_modified_by_assistant": False,
    "confidential_data_collection_authorized": False,
    "p05_accepted": False
}

P05_06_NETWORK_SHARING_OWNER_REPORT = {
    "source": "USER_EXPLICIT_NOT_SHARED_REPLY_TO_P05_06_WINDOWS_SHARE_TAB_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "reported_state": "NOT_SHARED",
    "classification": "OWNER_REPORTED_WINDOWS_NETWORK_SHARING_STATUS_ONLY",
    "windows_share_tab_display_independently_verified": False,
    "effective_ntfs_acl_and_inheritance_verified": False,
    "advanced_network_share_and_admin_share_absence_verified": False,
    "remote_access_or_other_app_access_absence_verified": False,
    "cloud_sync_or_backup_absence_independently_verified": False,
    "private_data_access_and_retention_policy_approved": False,
    "folder_sharing_modified_by_assistant": False,
    "sensitive_evidence_collection_authorized": False,
    "any_file_or_mt4_log_collected": False,
    "p05_accepted": False
}

P05_06_CLOUD_SYNC_OWNER_REPORT = {
    "source": "USER_EXPLICIT_CLOUD_SYNC_OFF_REPLY_TO_P05_06_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "reported_state": "NOT_SYNCED",
    "classification": "OWNER_REPORT_NO_SYNC_INDEPENDENT_VERIFICATION_PENDING",
    "service_or_folder_settings_independently_inspected": False,
    "windows_cloud_sync_or_backup_absence_independently_verified": False,
    "cloud_sync_setting_changed_by_assistant": False,
    "evidence_collected_or_uploaded": False,
    "sensitive_evidence_collection_authorized": False,
    "p05_accepted": False
}

P05_06_FOLDER_CREATION_OWNER_REPORT = {
    "source": "USER_EXPLICIT_FOLDER_CREATED_REPLY_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "observation": "PRIVATE_EVIDENCE_FOLDER_CREATED_BY_OWNER",
    "classification": "OWNER_ATTESTED_CREATION_NO_LOCAL_VERIFICATION",
    "location_relation_from_owner_path": "SIBLING_OF_FX_REPOSITORY_BY_REPORTED_PATH_ONLY",
    "private_absolute_path_stored_in_git": False,
    "private_path_repeated_in_documentation": False,
    "independently_verified_on_windows": False,
    "git_exclusion_independently_verified": False,
    "cloud_sync_or_backup_absence_verified": False,
    "windows_acl_and_sharing_verified": False,
    "encryption_and_retention_policy_verified": False,
    "sensitive_material_collection_authorized": False,
    "private_data_collected_or_uploaded": False,
    "folder_created_or_modified_by_assistant": False,
    "p05_accepted": False
}

P05_06_PRIVATE_STORAGE_OWNER_REPORT = {
    "source": "USER_EXPLICIT_NO_REPLY_TO_P05_06_PRIVATE_FOLDER_QUESTION",
    "reported_on_jst_date": "2026-11-04",
    "response": "NO_PRIVATE_EVIDENCE_FOLDER_PREPARED",
    "classification": "OWNER_REPORT_ONLY_NO_FILESYSTEM_INSPECTION",
    "folder_path_disclosed": False,
    "local_folder_independently_verified": False,
    "out_of_repo_private_folder_ready": False,
    "confidential_evidence_collection_authorized": False,
    "any_log_or_screenshot_collected": False,
    "filesystem_modified_by_assistant": False,
    "p05_accepted": False
}

P05_01_DEMO_TYPE_REPORT = {
    "source": "USER_EXPLICIT_DEMO_ACCOUNT_REPLY_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "classification": "OWNER_ATTESTED_DEMO_ACCOUNT_TYPE_ONLY",
    "account_type_owner_reported": "DEMO",
    "creation_date_owner_reported": "2026-10-26",
    "independent_broker_account_type_verified": False,
    "same_as_historically_known_demo_login_verified": False,
    "server_account_or_session_independently_verified": False,
    "account_identifiers_disclosed": False,
    "p05_accepted": False,
    "not_a_broker_statement": True,
}
P05_02_FACE_ICON_OWNER_REPORT = {
    "source": "USER_EXPLICIT_REPLY_TO_P05_02_MACD_SAMPLE_FACE_ICON_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "view": "EXISTING_MT4_CHART_MACD_SAMPLE_NEARBY",
    "display_observation": "SAD_FACE_ICON",
    "classification": "OWNER_REPORTED_CHART_UI_ONLY",
    "expert_advisor_attached_independently_verified": False,
    "ea_execution_state_independently_verified": False,
    "autotrading_permission_for_this_ea_independently_verified": False,
    "all_ea_scripts_inactive_verified": False,
    "server_order_or_position_absence_verified": False,
    "account_or_broker_sync_independently_verified": False,
    "chart_or_terminal_modified_by_assistant": False,
    "p05_accepted": False,
    "not_a_broker_or_execution_proof": True
}

P05_02_AUTOTRADING_OFF_OWNER_REPORT = {
    "source": "USER_EXPLICIT_OFF_REPLY_TO_P05_AUTOTRADING_UI_QUESTION",
    "reported_on_jst_date": "2026-11-04",
    "display_observation": "AUTOTRADING_BUTTON_OFF",
    "classification": "OWNER_REPORTED_UI_INDICATOR_ONLY",
    "broker_execution_state_independently_verified": False,
    "ea_or_script_activity_absent_verified": False,
    "server_positions_or_pending_orders_absent_verified": False,
    "button_or_ea_changed_by_assistant": False,
    "account_identity_verified_by_report": False,
    "p05_accepted": False,
    "not_an_execution_or_broker_proof": True
} 

P05_02_EA_VISIBLE_REPORT = {
    "source": "USER_REPORTED_MACD_SAMPLE_VISIBLE_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "display_observation": "MACD_SAMPLE_VISIBLE",
    "attachment_location_currently_verified": False,
    "active_or_trading_verified": False,
    "ea_changed_or_stopped": False,
    "order_risk_absence_verified": False,
    "not_a_runtime_execution_proof": True,
}
P05_04_SINGLE_SESSION_OWNER_REPORT = {
    "source": "USER_EXPLICIT_CURRENT_MT4_ONLY_REPLY_IN_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "reported_usage": "CURRENT_MT4_ONLY",
    "other_pc_or_mt4_same_demo_login_owner_reported": False,
    "other_pc_or_mt4_same_demo_login_independently_verified_absent": False,
    "login_session_count_broker_verified": False,
    "different_demo_account_absence_independently_verified": False,
    "demo_contract_compliance_independently_verified": False,
    "additional_login_or_account_created_by_assistant": False,
    "not_a_broker_statement": True,
}
P05_03_OWNER_REPORT = {
    "source": "USER_REPORT_IN_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "view": "MT4_TERMINAL_TRADE_TAB",
    "observation": "BALANCE_ONLY_NO_POSITION_OR_PENDING_ORDER_ROWS_VISIBLE",
    "account_identity_confirmed": False,
    "server_order_state_reconciled": False,
    "connection_status": "OWNER_REPORTED_MT4_COMMUNICATING_DISPLAY_ONLY",
    "current_positions_or_pending_orders_independently_verified_absent": False,
    "not_a_broker_statement": True,
}
P05_01_ACCOUNT_CREATION_DATE_CORRECTION = {
    "source": "USER_CORRECTED_ACCOUNT_CREATION_DATE_IN_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "corrected_creation_date": "2026-10-26",
    "superseded_incorrect_date": "2026-11-26",
    "date_is_owner_report_not_broker_proof": True,
    "account_type_confirmed": False,
    "same_as_previously_used_demo_account_confirmed": False,
    "account_identity_independently_verified": False,
    "server_account_reconciled": False,
    "not_a_broker_statement": True,
}
P05_01_OWNER_REPORT = {
    "source": "USER_REPORT_IN_CURRENT_CHAT",
    "reported_on_jst_date": "2026-11-04",
    "display_report": "MT4_COMMUNICATING",
    "classification": "UI_REPORTED_COMMUNICATION_ONLY",
    "account_type_confirmed": False,
    "account_identity_confirmed": False,
    "server_connection_independently_verified": False,
    "order_state_synchronized_with_server_verified": False,
    "terminal_session_authorized_by_report": False,
    "not_a_broker_statement": True,
}
EXPECTED_METHODS = (
    ("P02", "ORIGINAL_SOURCE_RECONCILIATION_METHOD_ONLY",
     "APPROVED_NOT_EXECUTED"),
    ("P04", "NONDESTRUCTIVE_MT4_OBSERVATION_PROTOCOL_DESIGN_ONLY",
     "APPROVED_P05_PRECHECK_REQUIRED"),
)
P02_STATUS = "OWNER_APPROVED_METHOD_ONLY_ORIGINALS_NOT_REVIEWED"
P04_STATUS = "OWNER_APPROVED_PROTOCOL_ONLY_P05_PRECHECK_PENDING"
UNAUTHORIZED = (
    "p05_real_world_environment_evaluated",
    "p05_human_safety_signoff",
    "p06_observation_authorized",
    "p07_independent_broker_evidence_verified",
    "read_only_mt4_login_authorized_now",
    "terminal_script_execution_authorized",
    "private_account_info_collected",
    "additional_demo_account_authorized",
    "parallel_session_authorized",
    "existing_ea_change_authorized",
    "position_or_pending_order_change_authorized",
    "trading_authorized",
    "g1_accepted",
    "stop_release_authorized",
    "auto_merge_authorized",
)
HAZARDS = (
    "MACD_SAMPLE_REPORTED_ON_CHART_AND_NAVIGATOR",
    "OPEN_POSITIONS_OR_PENDING_ORDERS_REPORTED_YES",
    "AUTOTRADING_DISPLAY_OFF_LIKE_NOT_AN_EXECUTION_PROOF",
)


def _read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, *, injected: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        docs = {
            k: (injected[k] if injected is not None and k in injected
                else _read(root, k))
            for k in (PLAN, PATH, PROTOCOL, UPSTREAM, SCOPE, GATES, SAFETY, DOCKET)
        }
        plan = docs[PLAN]
        if type(plan) is not dict:
            return ["INVALID_PROCEDURAL_APPROVAL_PLAN"]
        if (type(plan.get("schema_version")) is not int
                or plan.get("schema_version") != 1
                or plan.get("id") !=
                "RISK-3P-29-31-P02-P04-APPROVAL-AND-P05-PREFLIGHT-20261104"
                or plan.get("source") !=
                "DIRECT_USER_CHAT_APPROVAL_P02_AND_P04_DATE_ONLY_NO_PRIVATE_QUOTE"
                or plan.get("date_jst") != "2026-11-04"
                or plan.get("scope") !=
                "OWNER_APPROVED_OFFLINE_REVIEW_METHODS_WITH_P05_REAL_ENVIRONMENT_HOLD"
                or plan.get("previous_owner_g1_scope_ref") != SCOPE
                or plan.get("prior_protocol_ref") != PROTOCOL
                or plan.get("prior_critical_path_ref") != PATH):
            errors.append("OWNER_APPROVAL_IDENTITY_OR_SOURCE_DRIFT")
        decisions = plan.get("decisions")
        if (type(decisions) is not list or len(decisions) != 2
                or [(r.get("id"), r.get("approved_component"), r.get("method_status"))
                    for r in decisions if type(r) is dict] != list(EXPECTED_METHODS)
                or any(r.get("owner_approved") is not True
                       or type(r.get("authorized_scope")) is not str
                       or not r["authorized_scope"] for r in decisions)):
            errors.append("OWNER_P02_P04_METHOD_DECISION_INVALID")
        else:
            p02, p04 = decisions
            if (p02.get("no_auto_original_certification") is not True
                    or p02.get("fx_saf_original_verified_count") != 0
                    or p02.get("form_implementation_approvals_recorded") != 0
                    or p02.get("original_source_access_performed") is not False):
                errors.append("P02_FALSE_ORIGINAL_SOURCE_VERIFICATION")
            if (p04.get("no_blanket_terminal_access") is not True
                    or p04.get("real_mt4_login_authorized_now") is not False
                    or p04.get("script_or_ea_execution_authorized") is not False
                    or p04.get("order_or_position_changes_authorized") is not False):
                errors.append("P04_FALSE_TERMINAL_SESSION_PERMISSION")
        if (plan.get("g1_scope_owner_approved") is not True
                or plan.get("g1_actual_broker_fields_verified") != 0
                or plan.get("fx_saf_originals_verified") != 0
                or plan.get("form_implementation_choices_approved") != 0
                or plan.get("historical_existing_account_hazards") != list(HAZARDS)):
            errors.append("EVIDENCE_COUNT_OR_PRIOR_ACCOUNT_HAZARD_DRIFT")
        if (plan.get("p05_gate_status") !=
                "BLOCKED_AWAITING_INDEPENDENT_ENVIRONMENT_SAFETY_CHECK"
                or plan.get("p05_total_checks") != 8
                or plan.get("p05_passed_checks") != 0):
            errors.append("P05_UNJUSTIFIED_PRECHECK_PASS")
        if plan.get("p05_current_observation_summary") != "OWNER_DEMO_SINGLE_MT4_MACD_VISIBLE_SAD_FACE_AUTOTRADING_OFF_COMMUNICATING_TRADE_TAB_BALANCE_ONLY_ALL_UI_REPORTS_NOT_SERVER_VERIFIED":
            errors.append("P05_UI_OBSERVATION_MISTAKEN_FOR_ACCOUNT_RECONCILIATION")
        checks = plan.get("p05_checks")
        if (type(checks) is not list or len(checks) != len(P05_IDS)
                or [x.get("check_id") for x in checks if type(x) is dict]
                != list(P05_IDS)):
            errors.append("P05_MANDATORY_CHECK_SET_CHANGED")
        else:
            for i, row in enumerate(checks):
                if i == 5 and row.get("owner_reported_unfamiliar_principals") != P05_06_UNFAMILIAR_PRINCIPALS_OWNER_REPORT:
                    errors.append("P05_06_NO_UNKNOWN_PRINCIPALS_FALSELY_CERTIFIED")
                if i != 5 and "owner_reported_unfamiliar_principals" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_PRINCIPALS:" + P05_IDS[i])
                if i == 5 and row.get("owner_accepted_storage_security_scope") != P05_06_OWNER_STORAGE_SECURITY_ACCEPTANCE:
                    errors.append("P05_06_OWNER_ACCEPTANCE_WRONGLY_EXTENDED_TO_MT4_OR_ACL_PROOF")
                if i != 5 and "owner_accepted_storage_security_scope" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_OWNER_APPROVES_STORAGE:" + P05_IDS[i])
                if i == 5 and row.get("owner_reported_ntfs_everyone_visibility") != P05_06_EVERYONE_VISIBILITY_OWNER_REPORT:
                    errors.append("P05_06_EVERYONE_ABSENT_FALSELY_TREATED_AS_FULL_ACL_PROOF")
                if i != 5 and "owner_reported_ntfs_everyone_visibility" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_EVERYONE_VISIBILITY:" + P05_IDS[i])
                if i == 5 and row.get("owner_reported_network_sharing") != P05_06_NETWORK_SHARING_OWNER_REPORT:
                    errors.append("P05_06_NOT_SHARED_FALSELY_TREATED_AS_ACCESS_CONTROL_PROOF")
                if i != 5 and "owner_reported_network_sharing" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_NETWORK_SHARING:" + P05_IDS[i])
                if i == 5 and row.get("owner_reported_cloud_sync") != P05_06_CLOUD_SYNC_OWNER_REPORT:
                    errors.append("P05_06_CLOUD_SYNC_REPORT_FALSELY_VERIFIED_OR_PROMOTED")
                if i != 5 and "owner_reported_cloud_sync" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_CLOUD_SYNC:" + P05_IDS[i])
                if i == 5 and row.get("owner_reported_folder_creation") != P05_06_FOLDER_CREATION_OWNER_REPORT:
                    errors.append("P05_06_FOLDER_CREATED_REPORT_FALSE_SECURITY_CERTIFICATION")
                if i != 5 and "owner_reported_folder_creation" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_FOLDER_CREATION:" + P05_IDS[i])
                if i == 5 and row.get("owner_reported_private_storage") != P05_06_PRIVATE_STORAGE_OWNER_REPORT:
                    errors.append("P05_06_OWNER_NO_FOLDER_FALSIFIED_OR_OVERCLAIMED")
                if i != 5 and "owner_reported_private_storage" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_PRIVATE_STORAGE:" + P05_IDS[i])
                if i == 3 and row.get("owner_reported_session_observation") != P05_04_SINGLE_SESSION_OWNER_REPORT:
                    errors.append("P05_04_OWNER_SINGLE_SESSION_REPORT_OVERCLAIMED")
                if i != 3 and "owner_reported_session_observation" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_SINGLE_SESSION_REPORTED:" + P05_IDS[i])
                if i == 0 and row.get("owner_reported_account_type") != P05_01_DEMO_TYPE_REPORT:
                    errors.append("P05_01_DEMO_OWNER_ATTESTATION_OVERCLAIMED")
                if i != 0 and "owner_reported_account_type" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_ATTESTED_DEMO:" + P05_IDS[i])
                if i == 1 and row.get("owner_reported_ea_visibility") != P05_02_EA_VISIBLE_REPORT:
                    errors.append("P05_02_EA_VISIBILITY_FALSELY_INTERPRETED_AS_RUNNING")
                if i == 1 and row.get("owner_reported_chart_ea_face_icon") != P05_02_FACE_ICON_OWNER_REPORT:
                    errors.append("P05_02_FACE_ICON_FALSELY_TREATED_AS_EA_OR_ORDER_PROOF")
                if i != 1 and "owner_reported_chart_ea_face_icon" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_EA_FACE_ICON:" + P05_IDS[i])
                if i == 1 and row.get("owner_reported_autotrading_display") != P05_02_AUTOTRADING_OFF_OWNER_REPORT:
                    errors.append("P05_02_AUTOTRADING_OFF_FALSELY_TREATED_AS_EXECUTION_PROOF")
                if i != 1 and "owner_reported_autotrading_display" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_AUTOTRADING:" + P05_IDS[i])
                if i != 1 and "owner_reported_ea_visibility" in row:
                    errors.append("P05_OTHER_CHECK_FALSELY_REPORTS_EA:" + P05_IDS[i])
                if i == 0 and row.get("owner_reported_account_creation") != P05_01_ACCOUNT_CREATION_DATE_CORRECTION:
                    errors.append("P05_01_CREATION_DATE_OR_ACCOUNT_IDENTITY_OVERCLAIMED")
                if i != 0 and "owner_reported_account_creation" in row:
                    errors.append("P05_UNEXPECTED_ACCOUNT_CREATION_REPORT:" + P05_IDS[i])
                if i == 0 and row.get("owner_reported_connection_display") != P05_01_OWNER_REPORT:
                    errors.append("P05_01_CONNECTION_UI_REPORT_OVERCLAIMED")
                if i != 0 and "owner_reported_connection_display" in row:
                    errors.append("P05_OTHER_CHECK_FALSLY_CONNECTION_REPORTED:" + P05_IDS[i])
                if i == 2 and row.get("owner_reported_ui_observation") != P05_03_OWNER_REPORT:
                    errors.append("P05_03_UI_REPORT_FALSIFIED_OR_OVERCLAIMED")
                if i != 2 and "owner_reported_ui_observation" in row:
                    errors.append("P05_OTHER_CHECK_FALSLY_REPORTED:" + P05_IDS[i])
                if (row.get("current_status") != P05_STATES[i]
                        or type(row.get("title")) is not str or not row["title"]
                        or type(row.get("known_historical_condition")) is not str
                        or not row["known_historical_condition"]
                        or type(row.get("required_for_future")) is not str
                        or not row["required_for_future"]
                        or any(row.get(name, "MISSING") is not None for name in (
                            "evidence_reference", "observation_at_utc",
                            "reviewer_reference"))
                        or row.get("safe_to_proceed") is not False
                        or row.get("p05_accepted") is not False):
                    errors.append("P05_PREMATURE_OR_UNVERIFIED:" + P05_IDS[i])
        for key in UNAUTHORIZED:
            if plan.get(key) is not False:
                errors.append("FALSE_REAL_OPERATION_AUTHORITY:" + key)
        if (plan.get("phase_1") != "BLOCKED"
                or plan.get("runtime_go_no_go") != "NO_GO"
                or plan.get("safety_hold_latched") is not True
                or plan.get("verified_values", "MISSING") is not None):
            errors.append("SAFETY_HOLD_OR_NO_GO_PROMOTED")
        g1 = docs[SCOPE]
        if (g1.get("authorized_scope") != list(PAIRS)
                or g1.get("five_required_fields") != list(FIVE)
                or g1.get("real_verified_field_count") != 0
                or g1.get("decision_status") != "OWNER_APPROVED_SCOPE_ONLY"):
            errors.append("G1_OWNER_SCOPE_SOURCE_PROMOTED")
        path = docs[PATH]
        nodes = {x["id"]: x for x in path["proposed_dependency_nodes"]}
        if (nodes["P02_OWNER_VERIFY_SOURCE_ORIGINALS"].get("status") != P02_STATUS
                or nodes["P04_OWNER_READONLY_PROTOCOL_DECISION"].get("status")
                != P04_STATUS
                or nodes["P05_SAFE_ENVIRONMENT_PRECHECK"].get("status")
                != "PENDING_ENVIRONMENT_PRECHECK"
                or any(nodes[name].get("execution_permitted") is not False
                       for name in nodes)
                or path.get("p02_reconciliation_method_owner_approved") is not True
                or path.get("p04_readonly_protocol_method_owner_approved") is not True
                or path.get("p02_p04_owner_method_decision_ref") != PLAN
                or path.get("p02_actual_originals_reviewed") is not False
                or path.get("p04_real_terminal_session_authorized") is not False
                or path.get("p05_environment_safety_verified") is not False):
            errors.append("CRITICAL_PATH_P02_P04_METHOD_APPROVAL_DRIFT")
        protocol = docs[PROTOCOL]
        if (protocol.get("p04_readonly_protocol_method_owner_approved") is not True
                or protocol.get("p02_p04_owner_method_decision_ref") != PLAN
                or protocol.get("p05_environment_precheck_status") !=
                "BLOCKED_SAFETY_CONDITIONS_UNKNOWN"
                or protocol.get("owner_approved_real_read") is not False
                or protocol.get("evidence_collected") is not False
                or any(x.get("status") != "NOT_AUTHORIZED"
                       for x in protocol["environment_readonly_steps"])):
            errors.append("READONLY_PROTOCOL_METHOD_MISTAKEN_FOR_OBSERVATION")
        prev = docs[UPSTREAM]
        if (prev.get("p02_reconciliation_method_owner_approved") is not True
                or prev.get("p04_readonly_protocol_method_owner_approved") is not True
                or prev.get("p02_p04_method_decision_ref") != PLAN
                or prev.get("p05_environment_precheck_status") != "BLOCKED_NOT_PERFORMED"
                or prev.get("current_readiness")
                != "BLOCKED_MISSING_ORIGINALS_AND_REAL_EVIDENCE"
                or prev.get("g1_real_world_verified") is not False):
            errors.append("UPSTREAM_EVIDENCE_STATUS_PROMOTED")
        gates = docs[GATES]
        if (gates.get("g1_evidence_verified") is not False
                or gates.get("real_mt4_access_approved") is not False
                or gates.get("real_order_execution_approved") is not False
                or gates.get("runtime_go_no_go") != "NO_GO"
                or any(x.get("release_blocker") is not True
                       or x.get("real_world_verified") is not False
                       or x.get("implementation_status") != "UNRESOLVED"
                       for x in gates["gaps"])):
            errors.append("FORMAL_GATES_OR_MT4_ACCESS_PROMOTED")
        safety = docs[SAFETY]
        if (len(safety["items"]) != 15
                or any(x.get("source_review") != "PENDING_ORIGINAL"
                       or x.get("human_safety_approval") is not False
                       for x in safety["items"])):
            errors.append("UNREVIEWED_SOURCE_FALSELY_ACCEPTED")
        docket = docs[DOCKET]
        if (len(docket["decisions"]) != 43
                or any(x.get("owner_decision") != "NOT_RECORDED"
                       or x.get("implementation_approved") is not False
                       for x in docket["decisions"])):
            errors.append("FORM43_FALSELY_ACCEPTED")
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError):
        errors.append("MALFORMED_OR_MISSING_METHOD_OR_EVIDENCE_REGISTER")
    return errors


def snapshot(root: Path = ROOT) -> dict:
    errors = audit(root)
    return {
        "audit_status": "PASS_DOCUMENT_ONLY" if not errors else "FAIL_CLOSED",
        "p02_method_owner_approved": not errors,
        "p02_actual_fx_saf_originals_verified": 0,
        "p04_method_owner_approved": not errors,
        "p04_real_mt4_session_allowed": False,
        "p05_checks_passed": 0,
        "p05_total_checks": 8,
        "p05_06_prior_absence_report_retained": not errors,
        "p05_06_owner_reported_no_unfamiliar_principals": not errors,
        "p05_06_owner_accepts_folder_and_parents_for_offline_work": not errors,
        "p05_06_storage_permission_is_not_broker_permission": True,
        "p05_06_owner_reported_everyone_not_visible": not errors,
        "p05_06_unfamiliar_principals_state": "UNVERIFIED",
        "p05_06_effective_ntfs_permissions_verified": False,
        "p05_06_owner_reported_not_network_shared": not errors,
        "p05_06_network_sharing_independently_verified": False,
        "p05_06_ntfs_acl_independently_verified": False,
        "p05_06_owner_reported_no_cloud_sync": not errors,
        "p05_06_owner_reported_folder_created": not errors,
        "p05_06_path_is_outside_repo_per_owner_report_only": not errors,
        "p05_06_windows_permissions_verified": False,
        "p05_06_cloud_sync_absence_verified": False,
        "p05_06_local_storage_ready": False,
        "p05_06_confidential_collection_authorized": False,
        "p05_04_owner_reported_single_mt4_only": not errors,
        "p05_04_single_session_independently_verified": False,
        "p05_01_owner_reported_demo_account": not errors,
        "p05_02_macd_sample_visible_runtime_unverified": not errors,
        "p05_02_sad_face_icon_owner_reported_not_execution_proof": not errors,
        "p05_02_autotrading_off_owner_reported_not_broker_verified": not errors,
        "p05_02_ea_or_orders_absent_verified": False,
        "p05_01_independent_account_identity_verified": False,
        "p05_01_owner_reported_communicating_display": not errors,
        "p05_01_owner_reported_creation_date": "2026-10-26" if not errors else None,
        "p05_01_account_same_as_prior_demo_verified": False,
        "p05_01_account_and_server_verified": False,
        "p05_03_user_reported_no_order_rows_visible": not errors,
        "p05_03_broker_orders_confirmed_absent": False,
        "p05_readiness": "BLOCKED",
        "g1_verified": "0/15",
        "form_decisions_approved": "0/43",
        "runtime_go_no_go": "NO_GO",
        "phase_1": "BLOCKED",
        "safety_hold_latched": True,
        "errors": errors,
    }


def main() -> None:
    state = snapshot()
    print(json.dumps(state, ensure_ascii=False, indent=2))
    if state["audit_status"] != "PASS_DOCUMENT_ONLY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
