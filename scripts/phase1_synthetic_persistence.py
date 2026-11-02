"""Offline G6-05/G6-06 state model. Never authorizes host or broker operations.

The model assumes a serialized compare-and-swap. It does not implement a lock,
durable journal, independent witness, atomic file save, or stop release.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticState:
    generation: int = 0
    writer: str | None = None
    tip: int = 0
    hold_latched: bool = True


@dataclass(frozen=True)
class Review:
    state: SyntheticState | None
    accepted: bool
    reason: str
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"


def _valid(state: object) -> bool:
    return (type(state) is SyntheticState
            and type(state.generation) is int and state.generation >= 0
            and (state.writer is None or
                 (type(state.writer) is str and bool(state.writer)))
            and type(state.tip) is int and state.tip >= 0
            and state.hold_latched is True)


def acquire(state: object, writer: object, observed_generation: object,
            *, independently_reconciled: bool = False) -> Review:
    """Model a serialized generation CAS; takeover requires external proof.

    ``independently_reconciled`` is a synthetic test input, never an actual
    attestation. All results retain BLOCKED/NO_GO and the hold latch.
    """
    if not _valid(state):
        return Review(None, False, "INVALID_STATE")
    if type(writer) is not str or not writer:
        return Review(state, False, "INVALID_WRITER")
    if type(observed_generation) is not int or observed_generation != state.generation:
        return Review(state, False, "STALE_GENERATION")
    if type(independently_reconciled) is not bool:
        return Review(state, False, "INVALID_RECONCILIATION_CLAIM")
    if state.writer is not None and independently_reconciled is not True:
        return Review(state, False, "TAKEOVER_UNPROVEN")
    if state.writer == writer:
        return Review(state, False, "DUPLICATE_ACQUIRE")
    return Review(SyntheticState(state.generation + 1, writer, state.tip),
                  True, "SYNTHETIC_CAS_ACQUIRED")


def append(state: object, writer: object, generation: object,
           observed_tip: object) -> Review:
    """Model one append under an active generation and expected tip."""
    if not _valid(state):
        return Review(None, False, "INVALID_STATE")
    if state.writer is None or type(writer) is not str or writer != state.writer:
        return Review(state, False, "WRITER_NOT_ACTIVE")
    if type(generation) is not int or generation != state.generation:
        return Review(state, False, "STALE_GENERATION")
    if type(observed_tip) is not int or observed_tip != state.tip:
        return Review(state, False, "TIP_CONFLICT")
    return Review(SyntheticState(state.generation, state.writer, state.tip + 1),
                  True, "SYNTHETIC_APPEND_ONLY")


def recover(state: object, observed_generation: object,
            observed_tip: object, *, commit_outcome: str) -> Review:
    """Reject ambiguous persistence; a visible commit remains untrusted."""
    if not _valid(state):
        return Review(None, False, "INVALID_STATE")
    if (type(observed_generation) is not int
            or observed_generation != state.generation
            or type(observed_tip) is not int or observed_tip != state.tip):
        return Review(state, False, "RECOVERY_DIVERGENCE")
    if type(commit_outcome) is not str:
        return Review(state, False, "INVALID_COMMIT_OUTCOME")
    if commit_outcome == "UNKNOWN":
        return Review(state, False, "COMMIT_OUTCOME_UNKNOWN")
    if commit_outcome == "ROLLED_BACK":
        return Review(state, False, "ROLLED_BACK_HOLD")
    if commit_outcome == "COMMITTED":
        return Review(state, False, "COMMIT_VISIBLE_INDEPENDENT_PROOF_MISSING")
    return Review(state, False, "INVALID_COMMIT_OUTCOME")
