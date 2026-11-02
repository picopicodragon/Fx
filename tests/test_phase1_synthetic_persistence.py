"""Offline protocol tests; no actual writer, witness, or power-loss claim."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.phase1_synthetic_persistence import (
    SyntheticState, acquire, append, recover,
)


class GenerationFenceModelTests(unittest.TestCase):
    def assert_held(self, result):
        self.assertTrue(result.state.hold_latched)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")

    def test_competing_writers_old_generation_cannot_append(self):
        initial = SyntheticState()
        first = acquire(initial, "writer-A", 0)
        self.assertTrue(first.accepted)
        self.assertEqual(first.state.generation, 1)
        self.assertFalse(acquire(first.state, "writer-B", 0).accepted)
        self.assertFalse(acquire(first.state, "writer-B", 1).accepted)
        takeover = acquire(first.state, "writer-B", 1,
                           independently_reconciled=True)
        self.assertTrue(takeover.accepted)
        self.assertFalse(append(takeover.state, "writer-A", 1, 0).accepted)
        self.assertTrue(append(takeover.state, "writer-B", 2, 0).accepted)
        for result in (first, takeover):
            self.assert_held(result)

    def test_tip_race_and_aba_are_denied(self):
        first = acquire(SyntheticState(), "A", 0).state
        commit = append(first, "A", 1, 0)
        self.assertTrue(commit.accepted)
        self.assertFalse(append(commit.state, "A", 1, 0).accepted)
        self.assertFalse(append(commit.state, "A", True, 1).accepted)
        self.assertFalse(acquire(commit.state, "A", 1,
                                 independently_reconciled=True).accepted)
        self.assert_held(commit)

    def test_unknown_crash_outcome_and_rollback_never_clear_hold(self):
        state = SyntheticState(4, "A", 9)
        for outcome in ("UNKNOWN", "ROLLED_BACK", "COMMITTED", "INVALID"):
            result = recover(state, 4, 9, commit_outcome=outcome)
            self.assertFalse(result.accepted)
            self.assertEqual(result.state, state)
            self.assert_held(result)
        self.assertEqual(recover(state, 3, 9, commit_outcome="COMMITTED").reason,
                         "RECOVERY_DIVERGENCE")
        self.assertEqual(recover(state, 4, 8, commit_outcome="COMMITTED").reason,
                         "RECOVERY_DIVERGENCE")

    def test_invalid_state_cannot_be_promoted(self):
        for state in (SyntheticState(True), SyntheticState(-1),
                      SyntheticState(0, ""), SyntheticState(tip=-1),
                      SyntheticState(hold_latched=False), object()):
            denied = acquire(state, "A", 0)
            self.assertFalse(denied.accepted)
            self.assertIsNone(denied.state)
            self.assertEqual(denied.runtime_go_no_go, "NO_GO")
            self.assertFalse(acquire(denied.state, "A", 0).accepted)
            self.assertFalse(append(state, "A", 0, 0).accepted)
            self.assertFalse(recover(state, 0, 0, commit_outcome="COMMITTED").accepted)


class IsolatedSqliteFaultTests(unittest.TestCase):
    def test_transaction_rollback_and_restart_visibility(self):
        """Synthetic SQLite rollback; not a power-loss or fsync test."""
        with tempfile.TemporaryDirectory(prefix="fx-g6-synthetic-") as folder:
            db = Path(folder) / "fixture.sqlite3"
            with closing(sqlite3.connect(db)) as connection:
                with connection:
                    connection.execute("CREATE TABLE marker (id INTEGER PRIMARY KEY, value TEXT)")
                    connection.execute("INSERT INTO marker VALUES (1, 'HELD')")
            with self.assertRaises(RuntimeError):
                with closing(sqlite3.connect(db)) as connection:
                    with connection:
                        connection.execute("UPDATE marker SET value = 'RELEASED' WHERE id = 1")
                        raise RuntimeError("synthetic interruption before commit")
            with closing(sqlite3.connect(db)) as connection:
                self.assertEqual(connection.execute(
                    "SELECT value FROM marker WHERE id = 1").fetchone(), ("HELD",))

    def test_committed_marker_still_requires_independent_proof(self):
        state = SyntheticState(2, "A", 5)
        result = recover(state, 2, 5, commit_outcome="COMMITTED")
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "COMMIT_VISIBLE_INDEPENDENT_PROOF_MISSING")
        self.assertTrue(result.state.hold_latched)
