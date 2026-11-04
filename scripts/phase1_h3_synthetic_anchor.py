"""H3-3 pure synthetic CAS/WORM model; not an external trust anchor.

No network, files, broker, clock, credentials or host interaction. "advanced"
means only that a fictional transition passed validation. It never authorizes
an order, release, production use, or G6 acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Snapshot:
    epoch: int = 1
    sequence: int = 0
    tip: str = "GENESIS"


@dataclass(frozen=True)
class SyntheticAnchor:
    local: Snapshot = Snapshot()
    witness: Snapshot = Snapshot()
    audit: Snapshot = Snapshot()
    phase: str = "IDLE"
    issuer_generation: int = 1
    revoked_generations: frozenset[int] = frozenset()
    request_id: str | None = None
    candidate_tip: str | None = None
    audit_request_id: str | None = None
    hold_latched: bool = True


@dataclass(frozen=True)
class Review:
    state: SyntheticAnchor | None
    advanced: bool
    reason: str
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    order_allowed: bool = False
    stop_release_allowed: bool = False
    automatic_retry_allowed: bool = False
    verified_values: None = None


_ACTIVE = {"IDLE", "PREPARED", "WITNESS_COMMITTED", "AUDIT_COMMITTED", "VERIFIED"}
_HALTED = {"WITNESS_UNKNOWN", "AUDIT_UNKNOWN", "QUARANTINED"}
_PHASES = _ACTIVE | _HALTED


def _snapshot_ok(value: object) -> bool:
    return (
        type(value) is Snapshot
        and type(value.epoch) is int and value.epoch >= 1
        and type(value.sequence) is int and value.sequence >= 0
        and type(value.tip) is str and bool(value.tip)
    )


def _valid(value: object) -> bool:
    if type(value) is not SyntheticAnchor:
        return False
    s = value
    if not all(_snapshot_ok(x) for x in (s.local, s.witness, s.audit)):
        return False
    if (type(s.phase) is not str or s.phase not in _PHASES
            or type(s.issuer_generation) is not int
            or s.issuer_generation < 1
            or type(s.revoked_generations) is not frozenset
            or any(type(x) is not int or x < 1 for x in s.revoked_generations)
            or s.hold_latched is not True
            or (s.request_id is not None and
                (type(s.request_id) is not str or not s.request_id))
            or (s.candidate_tip is not None and
                (type(s.candidate_tip) is not str or not s.candidate_tip))
            or (s.audit_request_id is not None and
                (type(s.audit_request_id) is not str or not s.audit_request_id))):
        return False
    if len({s.local.epoch, s.witness.epoch, s.audit.epoch}) != 1:
        return False
    if s.phase in {"IDLE", "VERIFIED"}:
        return (s.local == s.witness == s.audit
                and ((s.phase == "IDLE" and s.request_id is None
                      and s.candidate_tip is None and s.audit_request_id is None)
                     or (s.phase == "VERIFIED" and s.request_id is not None
                         and s.candidate_tip == s.local.tip
                         and s.audit_request_id == s.request_id)))
    if s.phase in {"PREPARED", "WITNESS_UNKNOWN"}:
        return (s.local == s.witness == s.audit
                and s.request_id is not None and s.candidate_tip is not None
                and s.candidate_tip != s.local.tip
                and s.audit_request_id is None)
    if s.phase in {"WITNESS_COMMITTED", "AUDIT_UNKNOWN", "AUDIT_COMMITTED"}:
        if not (s.request_id is not None and s.candidate_tip is not None
                and s.witness.sequence == s.local.sequence + 1
                and s.witness.tip == s.candidate_tip):
            return False
        if s.phase == "AUDIT_COMMITTED":
            return s.audit == s.witness and s.audit_request_id == s.request_id
        return s.audit == s.local and s.audit_request_id is None
    # A quarantined record is deliberately unusable, even if internally divergent.
    return True


def _deny(state: SyntheticAnchor | None, reason: str) -> Review:
    return Review(state, False, reason)


def _quarantine(state: SyntheticAnchor, reason: str) -> Review:
    return _deny(replace(state, phase="QUARANTINED"), reason)


def prepare(state: object, request_id: object, candidate_tip: object,
            issuer_generation: object) -> Review:
    """Create one fictional pending write, never a new order permission."""
    if not _valid(state):
        return _deny(None, "INVALID_STATE")
    if state.phase not in {"IDLE", "VERIFIED"}:
        return _deny(state, "UNRESOLVED_PREVIOUS_OPERATION")
    if (type(request_id) is not str or not request_id
            or type(candidate_tip) is not str or not candidate_tip
            or candidate_tip == state.local.tip):
        return _deny(state, "INVALID_REQUEST")
    if type(issuer_generation) is not int or issuer_generation != state.issuer_generation:
        return _deny(state, "ISSUER_MISMATCH")
    if issuer_generation in state.revoked_generations:
        return _deny(state, "ISSUER_REVOKED")
    return Review(replace(state, phase="PREPARED", request_id=request_id,
                          candidate_tip=candidate_tip, audit_request_id=None),
                  True, "SYNTHETIC_PREPARED")


def witness_result(state: object, outcome: object) -> Review:
    """Model the result of one compare-and-swap; no real CAS takes place."""
    if not _valid(state):
        return _deny(None, "INVALID_STATE")
    if state.phase != "PREPARED":
        return _deny(state, "WITNESS_NOT_PREPARED")
    if state.issuer_generation in state.revoked_generations:
        return _quarantine(state, "ISSUER_REVOKED")
    if outcome == "COMMITTED":
        new = replace(state, phase="WITNESS_COMMITTED",
                      witness=Snapshot(state.local.epoch,
                                       state.local.sequence + 1,
                                       state.candidate_tip))
        return Review(new, True, "SYNTHETIC_WITNESS_COMMIT")
    if outcome in ("UNKNOWN", "UNAVAILABLE"):
        return _deny(replace(state, phase="WITNESS_UNKNOWN"),
                     "WITNESS_OUTCOME_UNKNOWN")
    if outcome in ("CONFLICT", "REVOKED"):
        return _quarantine(state, "WITNESS_CONFLICT_OR_REVOKED")
    return _deny(state, "INVALID_WITNESS_OUTCOME")


def audit_result(state: object, outcome: object, request_id: object) -> Review:
    """Model an independent immutable audit receipt; no WORM write occurs."""
    if not _valid(state):
        return _deny(None, "INVALID_STATE")
    if state.phase != "WITNESS_COMMITTED":
        return _deny(state, "WITNESS_COMMIT_NOT_CONFIRMED")
    if state.issuer_generation in state.revoked_generations:
        return _quarantine(state, "ISSUER_REVOKED")
    if request_id != state.request_id or type(request_id) is not str:
        return _quarantine(state, "AUDIT_REQUEST_MISMATCH")
    if outcome == "APPENDED":
        return Review(replace(state, phase="AUDIT_COMMITTED",
                              audit=state.witness, audit_request_id=request_id),
                      True, "SYNTHETIC_AUDIT_RECEIPT")
    if outcome in ("UNKNOWN", "UNAVAILABLE"):
        return _deny(replace(state, phase="AUDIT_UNKNOWN"),
                     "AUDIT_OUTCOME_UNKNOWN")
    if outcome == "CONFLICT":
        return _quarantine(state, "AUDIT_CONFLICT")
    return _deny(state, "INVALID_AUDIT_OUTCOME")


def reconcile(state: object, journal: object, witness: object, audit: object,
              *, witness_available: object, audit_available: object,
              stop_tombstone_present: object) -> Review:
    """Check three independent *simulated* observations before local finalize.

    Observations being equal is not proof of a real trust boundary. All
    outcomes preserve NO_GO, and any unverifiable evidence quarantines.
    """
    if not _valid(state):
        return _deny(None, "INVALID_STATE")
    if state.phase != "AUDIT_COMMITTED":
        return _deny(state, "RECONCILIATION_NOT_READY")
    if state.issuer_generation in state.revoked_generations:
        return _quarantine(state, "ISSUER_REVOKED")
    if (witness_available is not True or audit_available is not True
            or stop_tombstone_present is not True):
        return _quarantine(state, "EVIDENCE_OR_TOMBSTONE_MISSING")
    if not all(_snapshot_ok(x) for x in (journal, witness, audit)):
        return _quarantine(state, "INVALID_OBSERVATION")
    if not (journal == witness == audit == state.witness == state.audit):
        return _quarantine(state, "ROLLBACK_OR_DIVERGENCE")
    return Review(replace(state, local=journal, phase="VERIFIED"),
                  True, "SYNTHETIC_EQUALITY_ONLY_NO_GO")


def review_restore(local: object, witness: object, audit: object,
                   *, witness_available: object, audit_available: object,
                   stop_tombstone_present: object) -> Review:
    """Review fictional restart evidence without promoting any runtime state."""
    if not all(_snapshot_ok(x) for x in (local, witness, audit)):
        return _deny(None, "INVALID_RESTORE_EVIDENCE")
    if (witness_available is not True or audit_available is not True
            or stop_tombstone_present is not True):
        return _deny(None, "RESTORE_PROOF_UNAVAILABLE")
    if not (local == witness == audit):
        return _deny(None, "RESTORE_ROLLBACK_OR_DIVERGENCE")
    return _deny(None, "SYNTHETIC_RESTORE_MATCH_NOT_AUTHORIZATION")


def revoke_issuer(state: object, generation: object) -> Review:
    """Represent a revocation tombstone as a permanent model quarantine."""
    if not _valid(state):
        return _deny(None, "INVALID_STATE")
    if type(generation) is not int or generation < 1:
        return _deny(state, "INVALID_ISSUER_GENERATION")
    return _deny(replace(
        state, phase="QUARANTINED",
        revoked_generations=state.revoked_generations | frozenset({generation})
    ), "ISSUER_REVOKED_QUARANTINED")
