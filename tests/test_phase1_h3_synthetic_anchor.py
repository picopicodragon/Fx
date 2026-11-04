"""H3-3 synthetic-only negative cases, never real cloud or broker evidence."""
import unittest
from dataclasses import replace

from scripts.phase1_h3_synthetic_anchor import (
    Snapshot, SyntheticAnchor, prepare, witness_result, audit_result,
    reconcile, review_restore, revoke_issuer,
)


def prepared():
    result = prepare(SyntheticAnchor(), "request-1", "digest-1", 1)
    assert result.advanced
    return result.state


def committed():
    result = witness_result(prepared(), "COMMITTED")
    assert result.advanced
    return result.state


def audited():
    result = audit_result(committed(), "APPENDED", "request-1")
    assert result.advanced
    return result.state


class H3SyntheticAnchorTests(unittest.TestCase):
    def held(self, review):
        self.assertEqual(review.runtime_go_no_go, "NO_GO")
        self.assertEqual(review.phase_1, "BLOCKED")
        self.assertIs(review.safety_hold_latched, True)
        self.assertIs(review.order_allowed, False)
        self.assertIs(review.stop_release_allowed, False)
        self.assertIs(review.automatic_retry_allowed, False)
        self.assertIsNone(review.verified_values)
        if review.state is not None:
            self.assertIs(review.state.hold_latched, True)

    def test_model_never_returns_go_even_when_all_synthetic_evidence_matches(self):
        start = SyntheticAnchor()
        self.assertEqual(start.phase, "IDLE")
        staged = prepare(start, "request-1", "digest-1", 1)
        witness = witness_result(staged.state, "COMMITTED")
        audit = audit_result(witness.state, "APPENDED", "request-1")
        result = reconcile(audit.state, audit.state.witness,
                           audit.state.witness, audit.state.audit,
                           witness_available=True, audit_available=True,
                           stop_tombstone_present=True)
        for r in (staged, witness, audit, result):
            self.assertTrue(r.advanced)
            self.held(r)
        self.assertEqual(result.state.phase, "VERIFIED")
        self.assertEqual(result.state.local.sequence, 1)
        self.assertEqual(result.state.local.tip, "digest-1")

    def test_witness_unavailable_or_unknown_requires_new_review(self):
        for outcome in ("UNKNOWN", "UNAVAILABLE"):
            with self.subTest(outcome=outcome):
                r = witness_result(prepared(), outcome)
                self.held(r)
                self.assertFalse(r.advanced)
                self.assertEqual(r.state.phase, "WITNESS_UNKNOWN")
                self.held(witness_result(r.state, "COMMITTED"))
                self.assertFalse(witness_result(r.state, "COMMITTED").advanced)
                self.assertFalse(prepare(r.state, "request-2", "digest-2", 1).advanced)

    def test_witness_conflict_revocation_and_stale_phase(self):
        for outcome in ("CONFLICT", "REVOKED"):
            with self.subTest(outcome=outcome):
                result = witness_result(prepared(), outcome)
                self.assertEqual(result.state.phase, "QUARANTINED")
                self.held(result)
                self.assertFalse(result.advanced)
        self.assertEqual(witness_result(SyntheticAnchor(), "COMMITTED").reason,
                         "WITNESS_NOT_PREPARED")
        self.assertEqual(witness_result(committed(), "COMMITTED").reason,
                         "WITNESS_NOT_PREPARED")

    def test_audit_append_is_required_and_cannot_follow_unknown_witness(self):
        r = witness_result(prepared(), "UNKNOWN")
        self.assertEqual(audit_result(r.state, "APPENDED", "request-1").reason,
                         "WITNESS_COMMIT_NOT_CONFIRMED")
        self.assertEqual(reconcile(r.state, Snapshot(), Snapshot(), Snapshot(),
                                   witness_available=True, audit_available=True,
                                   stop_tombstone_present=True).reason,
                         "RECONCILIATION_NOT_READY")

    def test_audit_unavailable_or_unknown_does_not_retry(self):
        for outcome in ("UNKNOWN", "UNAVAILABLE"):
            with self.subTest(outcome=outcome):
                r = audit_result(committed(), outcome, "request-1")
                self.assertFalse(r.advanced)
                self.assertEqual(r.state.phase, "AUDIT_UNKNOWN")
                self.held(r)
                self.assertFalse(audit_result(r.state, "APPENDED", "request-1").advanced)
                self.assertFalse(prepare(r.state, "new", "tip-2", 1).advanced)

    def test_audit_conflict_and_wrong_id_quarantine(self):
        for outcome, request in (("CONFLICT", "request-1"),
                                 ("APPENDED", "request-OLD")):
            with self.subTest(outcome=outcome, request=request):
                r = audit_result(committed(), outcome, request)
                self.assertFalse(r.advanced)
                self.assertEqual(r.state.phase, "QUARANTINED")
                self.held(r)

    def test_audit_is_not_witness_commit_and_vice_versa(self):
        r = committed()
        self.assertEqual(r.witness.sequence, 1)
        self.assertEqual(r.audit.sequence, 0)
        self.assertEqual(r.local.sequence, 0)
        self.assertFalse(reconcile(r, r.witness, r.witness, r.witness,
                                   witness_available=True, audit_available=True,
                                   stop_tombstone_present=True).advanced)
        r = audited()
        self.assertEqual(r.audit.sequence, 1)
        self.assertEqual(r.local.sequence, 0)

    def test_reconcile_rejects_stale_journal_witness_and_audit(self):
        s = audited()
        cases = ((s.local, s.witness, s.audit),
                 (s.witness, s.local, s.audit),
                 (s.witness, s.witness, s.local),
                 (Snapshot(epoch=2, sequence=1, tip="digest-1"), s.witness, s.audit),
                 (Snapshot(epoch=1, sequence=1, tip="wrong"), s.witness, s.audit))
        for journal, witness, audit in cases:
            with self.subTest(journal=journal, witness=witness, audit=audit):
                r = reconcile(s, journal, witness, audit,
                              witness_available=True, audit_available=True,
                              stop_tombstone_present=True)
                self.assertFalse(r.advanced)
                self.assertEqual(r.state.phase, "QUARANTINED")
                self.held(r)

    def test_reconcile_rejects_witness_outage_audit_outage_and_lost_tombstone(self):
        s = audited()
        for flags in ((False, True, True), (True, False, True),
                      (True, True, False), (1, True, True),
                      (True, 1, True), (True, True, 1)):
            with self.subTest(flags=flags):
                r = reconcile(s, s.witness, s.witness, s.audit,
                              witness_available=flags[0],
                              audit_available=flags[1],
                              stop_tombstone_present=flags[2])
                self.assertEqual(r.reason, "EVIDENCE_OR_TOMBSTONE_MISSING")
                self.assertFalse(r.advanced)
                self.held(r)

    def test_reconcile_invalid_observation_quarantines(self):
        s = audited()
        for invalid in (object(), None, True,
                        Snapshot(sequence=True), Snapshot(sequence=-1),
                        Snapshot(tip=""), Snapshot(epoch=0)):
            with self.subTest(invalid=repr(invalid)):
                r = reconcile(s, invalid, s.witness, s.audit,
                              witness_available=True, audit_available=True,
                              stop_tombstone_present=True)
                self.assertFalse(r.advanced)
                self.assertEqual(r.reason, "INVALID_OBSERVATION")
                self.held(r)

    def test_restore_never_promotes_even_on_matching_triple(self):
        snap = Snapshot(7, 42, "a")
        r = review_restore(snap, snap, snap,
                           witness_available=True, audit_available=True,
                           stop_tombstone_present=True)
        self.assertFalse(r.advanced)
        self.assertEqual(r.reason, "SYNTHETIC_RESTORE_MATCH_NOT_AUTHORIZATION")
        self.held(r)

    def test_restore_rejects_local_rollback_even_with_valid_shapes(self):
        newer = Snapshot(7, 43, "later")
        old = Snapshot(7, 42, "earlier")
        for snapshots in ((old, newer, newer), (newer, old, newer),
                          (newer, newer, old)):
            with self.subTest(snapshots=snapshots):
                r = review_restore(*snapshots, witness_available=True,
                                   audit_available=True,
                                   stop_tombstone_present=True)
                self.assertEqual(r.reason, "RESTORE_ROLLBACK_OR_DIVERGENCE")
                self.held(r)

    def test_restore_requires_live_observation_and_tombstone(self):
        snap = Snapshot()
        for flags in ((False, True, True), (True, False, True),
                      (True, True, False), (None, True, True)):
            with self.subTest(flags=flags):
                r = review_restore(snap, snap, snap,
                                   witness_available=flags[0],
                                   audit_available=flags[1],
                                   stop_tombstone_present=flags[2])
                self.assertEqual(r.reason, "RESTORE_PROOF_UNAVAILABLE")
                self.held(r)

    def test_revocation_is_a_model_tombstone_not_unlock(self):
        s = revoke_issuer(prepared(), 1)
        self.assertFalse(s.advanced)
        self.assertEqual(s.state.phase, "QUARANTINED")
        self.assertIn(1, s.state.revoked_generations)
        self.held(s)
        self.assertFalse(witness_result(s.state, "COMMITTED").advanced)
        self.assertFalse(prepare(s.state, "next", "new", 1).advanced)

    def test_revoked_generation_rejected_on_prepare(self):
        s = replace(SyntheticAnchor(), revoked_generations=frozenset({1}))
        r = prepare(s, "r", "tip", 1)
        self.assertEqual(r.reason, "ISSUER_REVOKED")
        self.held(r)

    def test_stale_generation_or_duplicate_digest_rejected(self):
        s = SyntheticAnchor()
        for generation in (0, 2, True, "1"):
            with self.subTest(generation=generation):
                r = prepare(s, "a", "new", generation)
                self.assertEqual(r.reason, "ISSUER_MISMATCH")
                self.held(r)
        self.assertEqual(prepare(s, "a", "GENESIS", 1).reason,
                         "INVALID_REQUEST")
        self.assertEqual(prepare(s, "", "new", 1).reason, "INVALID_REQUEST")

    def test_repeated_commit_without_new_prepare_is_rejected(self):
        s = audited()
        r = reconcile(s, s.witness, s.witness, s.audit,
                      witness_available=True, audit_available=True,
                      stop_tombstone_present=True)
        self.assertTrue(r.advanced)
        self.assertFalse(witness_result(r.state, "COMMITTED").advanced)
        next_op = prepare(r.state, "request-2", "digest-2", 1)
        self.assertTrue(next_op.advanced)
        self.assertEqual(next_op.state.local.sequence, 1)
        self.assertEqual(next_op.state.witness.sequence, 1)
        self.assertEqual(next_op.state.audit.sequence, 1)
        self.held(next_op)

    def test_malformed_model_state_never_advances(self):
        bad_states = (
            object(), None, replace(SyntheticAnchor(), hold_latched=False),
            replace(SyntheticAnchor(), local=Snapshot(sequence=-1)),
            replace(SyntheticAnchor(), witness=Snapshot(epoch=2)),
            replace(SyntheticAnchor(), issuer_generation=True),
            replace(SyntheticAnchor(), revoked_generations=frozenset({False})),
            replace(SyntheticAnchor(), phase="GO"),
            replace(SyntheticAnchor(), request_id="forged"),
            replace(SyntheticAnchor(), witness=Snapshot(sequence=1)),
        )
        for bad in bad_states:
            with self.subTest(bad=repr(bad)):
                r = prepare(bad, "a", "new", 1)
                self.assertFalse(r.advanced)
                self.assertEqual(r.reason, "INVALID_STATE")
                self.held(r)

    def test_outcome_injection_does_not_count_as_success(self):
        s = prepared()
        for outcome in (None, 1, True, "REPLAY", "ACK", "COMMIT"):
            with self.subTest(outcome=outcome):
                r = witness_result(s, outcome)
                self.assertFalse(r.advanced)
                self.assertEqual(r.reason, "INVALID_WITNESS_OUTCOME")
                self.held(r)
        s = committed()
        for outcome in (None, 1, True, "REPLAY", "SUCCESS"):
            with self.subTest(outcome=outcome):
                r = audit_result(s, outcome, "request-1")
                self.assertFalse(r.advanced)
                self.assertEqual(r.reason, "INVALID_AUDIT_OUTCOME")
                self.held(r)


if __name__ == "__main__":
    unittest.main()
