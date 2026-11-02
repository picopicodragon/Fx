"""D5-44 G6-04 append-only Journal and revocation tombstone design review.

Pure in-memory synthetic labels, not cryptographic hashes, durable storage,
independent attestation, actual deletion-prevention, or host/MT4 I/O.
"""
from __future__ import annotations

from scripts.p0_01_d5_43_key_lifecycle_review import (
    _FALSE as _D543_FALSE, review_d543_key_lifecycle,
)

_CONTROLS = (
    ("APPEND_ONLY_HISTORY", "FUTURE_STORAGE_REJECTS_OVERWRITE_AND_DELETE"),
    ("TOTAL_SEQUENCE", "FUTURE_VERIFY_STRICT_SEQUENCE_NO_GAPS_OR_DUPLICATES"),
    ("PREDECESSOR_BINDING", "FUTURE_VERIFY_AUTHENTICATED_PREVIOUS_LINK"),
    ("GENESIS_IDENTITY", "FUTURE_PIN_TRUSTED_GENESIS_OUT_OF_BAND"),
    ("INDEPENDENT_TIP_COMPARISON", "FUTURE_PROVE_REMOTE_WITNESS_TIP_AND_FRESHNESS"),
    ("TOMBSTONE_NON_ERASURE", "FUTURE_PROVE_KEY_AND_ISSUER_REVOCATION_DURABLE"),
    ("SINGLE_WRITER_COMPATIBILITY", "FUTURE_FENCE_WRITER_EPOCH_FOR_G6_05"),
    ("ATOMIC_PERSISTENCE_COMPATIBILITY", "FUTURE_VERIFY_CRASH_CONSISTENCY_FOR_G6_06"),
    ("RESTART_ROLLBACK_DEFENSE", "FUTURE_PROVE_POST_RESTART_HISTORY_AND_STOP"),
    ("PRIVATE_CONTENT_SEPARATION", "FUTURE_KEEP_RAW_ACCOUNT_KEYS_LOGS_OUT_OF_GIT"),
    ("ISSUER_EPOCH_AUTHORITY", "FUTURE_PROVE_ISSUER_AND_EPOCH_WITH_G6_03"),
    ("NO_STOP_RELEASE_ON_GAP", "FUTURE_DENY_TRADING_AND_RELEASE_ON_UNKNOWN_HISTORY"),
)
_ENTRIES = (
    "GENESIS", "ISSUER_REGISTER", "WRITER_FENCE", "JOURNAL_COMMIT",
    "KEY_ROTATION_PREPARE", "KEY_ROTATION_COMMIT",
    "KEY_REVOKE_TOMBSTONE", "ISSUER_REVOKE_TOMBSTONE",
    "STOP_LATCH", "RESTART_CHECKPOINT", "AUDIT_MARKER", "HANDOFF_REJECTED",
)
_THREATS = (
    ("RECORD_DELETION", "MISSING_INTERIOR_RECORD"),
    ("PREFIX_TRUNCATION", "HISTORY_PREFIX_ERASED"),
    ("RECORD_REORDER", "SEQUENCE_OUT_OF_ORDER"),
    ("RECORD_DUPLICATE", "DUPLICATE_SEQUENCE_OR_TAG"),
    ("SEQUENCE_GAP", "NONCONTIGUOUS_SEQUENCE"),
    ("PREVIOUS_LINK_REBIND", "UNAUTHENTICATED_PREDECESSOR"),
    ("GENESIS_REWRITE", "MUTATED_TRUST_ROOT"),
    ("KEY_TOMBSTONE_LOSS", "REVOKED_KEY_REACTIVATED"),
    ("ISSUER_TOMBSTONE_LOSS", "REVOKED_ISSUER_REACTIVATED"),
    ("FORKED_TIP", "DUAL_COMPETING_HISTORY_HEADS"),
    ("PARTIAL_CRASH_WRITE", "TORN_OR_UNCOMMITTED_RECORD"),
    ("RESTART_ROLLBACK", "OLD_PREFIX_ACCEPTED_AS_CURRENT"),
    ("PRIVATE_DATA_EGRESS", "SECRET_OR_ACCOUNT_ID_IN_PUBLIC_METADATA"),
    ("FENCE_EPOCH_BYPASS", "CONCURRENT_WRITER_REPLACES_TIP"),
)
_POLICIES = {
    "append_policy": "NEVER_DELETE_REWRITE_OR_BACKFILL_COMMITTED_RECORD",
    "chain_policy": "SYNTHETIC_TAG_LINKS_ARE_NOT_CRYPTOGRAPHIC_PROOF",
    "tip_policy": "INDEPENDENT_PINNED_TIP_FUTURE_PROOF_REQUIRED",
    "revocation_policy": "TOMBSTONE_MUST_OUTLIVE_RESTART_ROLLBACK_AND_KEY_CHANGE",
    "writer_policy": "SINGLE_WRITER_FENCE_REQUIRED_BEFORE_REAL_COMMIT",
    "restart_policy": "UNKNOWN_OR_MISSING_HISTORY_MEANS_STOP_LATCHED",
    "privacy_policy": "NO_REAL_KEYS_ACCOUNTS_LOGS_OR_EVIDENCE_IN_GIT",
    "approval_policy": "DESIGN_TESTS_AND_PR_MERGE_NEVER_APPROVE_REAL_IO",
}
_CONTRACT_FALSE = (
    "real_journal_created", "real_append_performed", "real_delete_prevented",
    "real_tombstone_persisted", "real_chain_authenticated",
    "real_independent_tip_verified", "real_writer_fence_verified",
    "real_atomic_recovery_verified", "real_os_io_approved",
    "real_mt4_io_approved", "real_stop_release_approved",
)
_FIXTURE_FALSE = (
    "real_history_read", "real_history_write", "real_history_delete",
    "real_secret_scan", "real_attestation_collected",
    "real_stop_release_requested", "real_mt4_requested",
)
_CONTRACT_KEYS = frozenset((
    "origin", "schema_version", "scope", "target_criterion",
    "predecessor_criterion", "cross_boundary_requirements",
    "required_controls", "entry_ids", "threat_ids",
    *_POLICIES, *_CONTRACT_FALSE, "phase_1", "runtime_go_no_go",
    "verified_values",
))
_FIXTURE_KEYS = frozenset((
    "origin", "schema_version", "scope", "journal_entries",
    "controls", "threats", "trusted_genesis", "independent_tip",
    "real_private_journal_path", "real_observed_utc",
    *_FIXTURE_FALSE, "account_identity_consistency",
    "current_positions", "current_pending_orders", "current_ea_state",
    "unresolved_gates", "safety_hold_latched",
))
_ENTRY_KEYS = frozenset((
    "sequence", "entry_id", "previous_tag", "entry_tag",
    "issuer_alias", "epoch_label", "record_class",
    "private_payload", "actual_signature", "real_timestamp",
    "real_persisted", "real_witness_verified",
))
_CONTROL_KEYS = frozenset((
    "control_id", "future_proof", "review_state", "real_evidence",
    "real_control_verified",
))
_THREAT_KEYS = frozenset((
    "threat_id", "attack", "simulated_outcome", "expected_reaction",
    "real_fault_executed", "real_attack_detected",
    "real_recovery_verified", "stop_release_authorized",
))
_PARENT_KEYS = (
    "d543_contract", "d543_matrix", "d543_predecessor",
)
_FALSE = (*_D543_FALSE,
          "g6_04_real_append_only_enforced",
          "g6_04_real_tombstone_persisted",
          "g6_04_real_history_rollback_detected",
          "g6_04_real_independent_tip_attested",
          "g6_04_real_history_verified",
          "g6_04_real_stop_release_authorized",
          "g6_04_real_writer_fence_verified",
          "g6_04_real_crash_recovery_verified",
          "g6_04_actual_private_journal_created",
          "g6_04_actual_history_scanned")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {name: False for name in _FALSE}
    result.update({
        "status": status,
        "d543_status": upstream,
        "journal_control_requirements": len(_CONTROLS),
        "synthetic_journal_entries": len(_ENTRIES),
        "synthetic_threats": len(_THREATS),
        "real_journal_entries_written": 0,
        "real_tombstones_verified": 0,
        "real_independent_tips_verified": 0,
        "real_trust_anchors_implemented": 0,
        "real_evidence_items_collected": 0,
        "real_work_packages_executed": 0,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _valid_contract(c: object) -> bool:
    return (
        type(c) is dict and set(c) == _CONTRACT_KEYS
        and c.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(c.get("schema_version")) is int and c["schema_version"] == 1
        and c.get("scope") ==
            "D544_G6_04_APPEND_ONLY_JOURNAL_TOMBSTONES_REQUIREMENTS_ONLY"
        and c.get("target_criterion") == "G6-04"
        and c.get("predecessor_criterion") == "G6-01"
        and c.get("cross_boundary_requirements") ==
            ["G6-03", "G6-05", "G6-06", "G2-06", "G2-07"]
        and c.get("required_controls") == [x[0] for x in _CONTROLS]
        and c.get("entry_ids") == list(_ENTRIES)
        and c.get("threat_ids") == [x[0] for x in _THREATS]
        and all(c.get(k) == val for k, val in _POLICIES.items())
        and all(c.get(k) is False for k in _CONTRACT_FALSE)
        and c.get("phase_1") == "BLOCKED"
        and c.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in c and c["verified_values"] is None
    )


def _valid_fixture(f: object) -> bool:
    if not (
        type(f) is dict and set(f) == _FIXTURE_KEYS
        and f.get("origin") == "SYNTHETIC_ONLY"
        and type(f.get("schema_version")) is int and f["schema_version"] == 1
        and f.get("scope") == "D544_LABEL_ONLY_JOURNAL_NO_PERSISTENCE"
        and f.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(f.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and f.get("unresolved_gates") == [f"G{i}" for i in range(1, 10)]
        and f.get("safety_hold_latched") is True
        and all(f.get(k) is None for k in (
            "trusted_genesis", "independent_tip",
            "real_private_journal_path", "real_observed_utc"))
        and all(f.get(k) is False for k in _FIXTURE_FALSE)
    ):
        return False
    entries = f.get("journal_entries")
    if type(entries) is not list or len(entries) != len(_ENTRIES):
        return False
    for idx, (entry, ident) in enumerate(zip(entries, _ENTRIES)):
        if not (
            type(entry) is dict and set(entry) == _ENTRY_KEYS
            and type(entry.get("sequence")) is int
            and entry["sequence"] == idx + 1
            and entry.get("entry_id") == ident
            and entry.get("previous_tag") == (
                "GENESIS_PARENT_DESIGN_ONLY" if idx == 0
                else f"TAG_DESIGN_{idx:02}")
            and entry.get("entry_tag") == f"TAG_DESIGN_{idx+1:02}"
            and entry.get("issuer_alias") == "SYNTHETIC_ISSUER_ALPHA"
            and entry.get("epoch_label") == "SYNTHETIC_EPOCH_1"
            and entry.get("record_class") == "DESIGN_ONLY"
            and all(entry.get(k) is None for k in (
                "private_payload", "actual_signature", "real_timestamp"))
            and entry.get("real_persisted") is False
            and entry.get("real_witness_verified") is False
        ):
            return False
    controls = f.get("controls")
    if type(controls) is not list or len(controls) != len(_CONTROLS):
        return False
    for row, (ident, proof) in zip(controls, _CONTROLS):
        if not (
            type(row) is dict and set(row) == _CONTROL_KEYS
            and row.get("control_id") == ident
            and row.get("future_proof") == proof
            and row.get("review_state") == "DESIGN_REQUIRED"
            and "real_evidence" in row and row["real_evidence"] is None
            and row.get("real_control_verified") is False
        ):
            return False
    threats = f.get("threats")
    if type(threats) is not list or len(threats) != len(_THREATS):
        return False
    for row, (ident, attack) in zip(threats, _THREATS):
        if not (
            type(row) is dict and set(row) == _THREAT_KEYS
            and row.get("threat_id") == ident
            and row.get("attack") == attack
            and row.get("simulated_outcome") in (
                "UNTESTED", "SIMULATED_ATTACK", "SIMULATED_MITIGATED")
            and row.get("expected_reaction") == "DENY_AND_HOLD_STOP"
            and all(row.get(k) is False for k in (
                "real_fault_executed", "real_attack_detected",
                "real_recovery_verified", "stop_release_authorized"))
        ):
            return False
    return True


def _parent_safe(child: object) -> bool:
    return (
        type(child) is dict
        and type(child.get("status")) is str
        and type(child.get("d542_status")) is str
        and all(type(child.get(k)) is int and child[k] == expected
                for k, expected in (
                    ("custody_requirements_documented", 12),
                    ("lifecycle_transitions_documented", 10),
                    ("threat_cases_documented", 10),
                    ("real_keys_generated", 0),
                    ("real_issuers_authenticated", 0),
                    ("real_revocations_attested", 0),
                    ("real_trust_anchors_implemented", 0),
                    ("real_candidates_selected", 0),
                    ("real_evidence_items_collected", 0),
                    ("real_work_packages_executed", 0),
                    ("real_acceptance_criteria_completed", 0)))
        and type(child.get("effective_approved_actions")) is list
        and child["effective_approved_actions"] == []
        and child.get("safety_hold_latched") is True
        and child.get("phase_1") == "BLOCKED"
        and child.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in child and child["verified_values"] is None
        and child.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(child.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(child.get(k) is False for k in _D543_FALSE)
        and set(child) == set(_D543_FALSE) | {
            "status", "d542_status", "custody_requirements_documented",
            "lifecycle_transitions_documented", "threat_cases_documented",
            "real_keys_generated", "real_issuers_authenticated",
            "real_revocations_attested", "real_trust_anchors_implemented",
            "real_candidates_selected", "real_evidence_items_collected",
            "real_work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state", "phase_1",
            "runtime_go_no_go", "verified_values",
        }
    )


def review_d544_journal(
    contract: object, synthetic_journal: object, predecessor: object,
) -> dict[str, object]:
    """Reject corrupt synthetic history; never claim real append-only safety."""
    try:
        if not _valid_contract(contract):
            return _deny("D544_JOURNAL_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _valid_fixture(synthetic_journal):
            return _deny("D544_JOURNAL_STRUCTURE_REJECTED_FAIL_CLOSED")
        if (type(predecessor) is not dict or
                set(predecessor) != set(_PARENT_KEYS)):
            return _deny("D544_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED")
        child = review_d543_key_lifecycle(
            *(predecessor[k] for k in _PARENT_KEYS)
        )
        if not _parent_safe(child):
            return _deny("D544_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != "D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS":
            return _deny("D544_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        upstream = child["status"]
        if any(row["simulated_outcome"] == "SIMULATED_ATTACK"
               for row in synthetic_journal["threats"]):
            return _deny("D544_SYNTHETIC_JOURNAL_ATTACK_DENIED_NO_GO", upstream)
        if any(row["simulated_outcome"] == "SIMULATED_MITIGATED"
               for row in synthetic_journal["threats"]):
            return _deny("D544_SIMULATED_MITIGATION_NOT_REAL_PROOF", upstream)
        return _deny("D544_JOURNAL_DESIGN_COHERENT_REAL_PERSISTENCE_BLOCKED",
                     upstream)
    except Exception:
        return _deny("D544_INPUT_EXCEPTION_FAIL_CLOSED")
