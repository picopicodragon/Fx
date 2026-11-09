"""Offline forward observation journal tests: never broker/AI/API calls."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import forward_observation as forward
from research.offline_backtest import InputError

BASE = datetime(2026, 11, 9, 7, 0, 0, tzinfo=timezone.utc)


def snapshot(kind, payload, *, moment=BASE):
    return {
        "schema": forward.SCHEMA, "kind": kind,
        "observed_at_utc": moment.isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source_id": "local_fixture",
        "payload": payload,
    }


def price(pair="USD/JPY"):
    return {
        "pair": pair, "bid": "150.001", "ask": "150.012",
        "quote_to_jpy": "1", "source_status": "USER_SUPPLIED_UNVERIFIED",
    }


def event():
    return {
        "pair": "USD/JPY", "title": "Synthetic non-live test report",
        "source_url": "https://example.invalid/synthetic-event",
        "published_at_utc": "2026-11-09T06:59:00Z",
        "content": "Fixture content only, no real-world event.",
        "consensus": "", "released_value": "sample only",
        "source_status": "USER_SUPPLIED_UNVERIFIED",
    }


class ForwardObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "session-001"
        forward.initialize(self.store, "session-001", now=BASE)

    def write_input(self, sample, name="input.json"):
        p = self.root / name
        p.write_text(json.dumps(sample), encoding="utf-8")
        return p

    def capture(self, sample, *, time=BASE, name="input.json"):
        return forward.ingest(self.store, self.write_input(sample, name),
                              now=time)

    def test_initialize_and_quote_snapshot_no_order(self):
        with self.assertRaises(InputError):
            forward.initialize(self.store, "again", now=BASE)
        r = self.capture(snapshot("PRICE_QUOTE", price()))
        self.assertEqual(r["status"], "FORWARD_OBSERVATION_CAPTURED_NO_GO")
        self.assertFalse(r["real_orders_permitted"])
        self.assertFalse(r["demo_order_execution_enabled"])
        a = forward.audit(self.store)
        self.assertEqual(a["record_count"], 1)
        self.assertEqual(a["by_kind"]["PRICE_QUOTE"], 1)
        self.assertEqual(a["runtime_go_no_go"], "NO_GO")
        self.assertFalse(a["source_authenticity_verified"])
        self.assertFalse(a["mt4_connection_enabled"])

    def test_evidence_hypothesis_independent_review_ordering(self):
        e = self.capture(snapshot("MACRO_EVENT", event()))
        basis = e["record_sha256"]
        h = snapshot("MACRO_HYPOTHESIS", {
            "pair": "USD/JPY", "direction": "HOLD",
            "thesis": "Synthetic research-only hypothesis",
            "counterevidence": "No verified consensus",
            "model_id": "mock-model",
            "basis_sha256": basis, "research_only": True,
        })
        h_result = self.capture(h, time=BASE + timedelta(seconds=1),
                                name="hypothesis.json")
        review = snapshot("INDEPENDENT_REVIEW", {
            "pair": "USD/JPY", "review_of_sha256":
                h_result["record_sha256"],
            "verdict": "PENDING", "rationale": "No live permission",
            "model_id": "independent-mock",
            "research_only": True,
        })
        self.capture(review, time=BASE + timedelta(seconds=2),
                     name="review.json")
        a = forward.audit(self.store)
        self.assertEqual(a["record_count"], 3)
        self.assertEqual(a["by_kind"]["MACRO_EVENT"], 1)
        self.assertEqual(a["by_kind"]["MACRO_HYPOTHESIS"], 1)
        self.assertEqual(a["by_kind"]["INDEPENDENT_REVIEW"], 1)

    def test_unmatched_hypothesis_and_review_rejected(self):
        h = snapshot("MACRO_HYPOTHESIS", {
            "pair": "USD/JPY", "direction": "LONG",
            "thesis": "Not referenced", "counterevidence": "unknown",
            "model_id": "mock", "basis_sha256": "a" * 64,
            "research_only": True,
        })
        with self.assertRaises(InputError):
            self.capture(h)
        self.assertEqual(forward.audit(self.store)["record_count"], 0)
        review = snapshot("INDEPENDENT_REVIEW", {
            "pair": "USD/JPY", "review_of_sha256": "a" * 64,
            "verdict": "APPROVED", "rationale": "not enough",
            "model_id": "mock", "research_only": True,
        })
        with self.assertRaises(InputError):
            self.capture(review)

    def test_bad_price_and_future_timestamp_fail_closed(self):
        for invalid in (
            {**price(), "ask": "149.99"},
            {**price(), "pair": "GBP/USD"},
            {**price(), "source_status": "VERIFIED"},
            {**price(), "bid": "NaN"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(InputError):
                forward.snapshot_validate(
                    snapshot("PRICE_QUOTE", invalid),
                    received_at="2026-11-09T07:00:00Z")
        with self.assertRaises(InputError):
            forward.snapshot_validate(
                snapshot("PRICE_QUOTE", price(),
                         moment=BASE + timedelta(minutes=3)),
                received_at="2026-11-09T07:00:00Z")
        self.assertEqual(forward.audit(self.store)["record_count"], 0)

    def test_synthetic_forged_credentials_rejected(self):
        sample = snapshot("MACRO_EVENT", {
            **event(), "content": "bearer SECRET_TOKEN_HERE"})
        with self.assertRaises(InputError):
            self.capture(sample)
        with self.assertRaises(InputError):
            self.capture(snapshot("PRICE_QUOTE", {
                **price(), "account_id": "FAKE"}))
        self.assertEqual(forward.audit(self.store)["record_count"], 0)

    def test_lock_prevents_parallel_writer_and_preserves_file(self):
        lock = self.store / ".capture.lock"
        lock.write_text("owned-by-another-process", encoding="utf-8")
        with self.assertRaisesRegex(InputError, "locked"):
            self.capture(snapshot("PRICE_QUOTE", price()))
        self.assertTrue(lock.exists())
        lock.unlink()
        r = self.capture(snapshot("PRICE_QUOTE", price()))
        self.assertEqual(r["sequence"], 1)

    def test_tamper_and_missing_chain_detected(self):
        self.capture(snapshot("PRICE_QUOTE", price()))
        self.capture(snapshot("PRICE_QUOTE", price()),
                     time=BASE + timedelta(seconds=1),
                     name="input2.json")
        file1 = self.store / "00000001.json"
        saved = file1.read_text(encoding="utf-8")
        item = json.loads(saved)
        item["snapshot"]["payload"]["bid"] = "149"
        file1.write_text(json.dumps(item), encoding="utf-8")
        with self.assertRaises(InputError):
            forward.audit(self.store)
        file1.write_text(saved, encoding="utf-8")
        (self.store / "00000002.json").unlink()
        with self.assertRaises(InputError):
            # Renamed record introduces sequence gap.
            (self.store / "00000003.json").write_text(
                saved, encoding="utf-8")
            forward.audit(self.store)

    def test_invalid_manifest_and_unexpected_file_are_blocked(self):
        (self.store / "account.dat").write_text("synthetic",
                                                encoding="utf-8")
        with self.assertRaises(InputError):
            forward.audit(self.store)
        (self.store / "account.dat").unlink()
        m = self.store / "manifest.json"
        obj = json.loads(m.read_text(encoding="utf-8"))
        obj["real_orders_permitted"] = True
        m.write_text(json.dumps(obj), encoding="utf-8")
        with self.assertRaises(InputError):
            forward.audit(self.store)

    def test_cli_fixtures_and_audit_without_external_network(self):
        root = self.root / "created-by-cli"
        report = self.root / "audit.json"
        inp = self.write_input(snapshot("PRICE_QUOTE", price()))
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(forward.main([
                "--store", str(root), "--init", "--session", "cli-01"]), 0)
            self.assertEqual(forward.main([
                "--store", str(root), "--ingest", str(inp)]), 0)
            self.assertEqual(forward.main([
                "--store", str(root), "--audit",
                "--report", str(report)]), 0)
        self.assertIn("NO_GO", buf.getvalue())
        self.assertEqual(
            json.loads(report.read_text(encoding="utf-8"))["record_count"], 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(forward.main([
                "--store", str(root), "--audit",
                "--report", str(report)]), 2)


if __name__ == "__main__":
    unittest.main()
