"""FWD-038..042: full-chain offline audit regression and Windows handoff tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_restart_receipts import make_receipt
from research.forward_receipt_chain import verify_chain, from_manifest, main as chain_main
from research.forward_receipt_manifest import build, main as manifest_main
from research.offline_backtest import InputError


def sample():
    a = make_receipt("c001", "2026-11-10T00:00:00Z", "a" * 64)
    b = make_receipt("c002", "2026-11-10T00:01:00Z", "b" * 64, a)
    c = make_receipt("c003", "2026-11-10T00:02:00Z", "c" * 64, b)
    return [a, b, c]


class ReceiptChainTests(unittest.TestCase):
    def test_full_history_verified_never_go(self):
        out = verify_chain(sample())
        self.assertEqual(out["receipt_count"], 3)
        self.assertEqual(out["oversized_gap_count"], 0)
        self.assertTrue(out["local_hash_consistency_verified"])
        self.assertFalse(out["real_orders_permitted"])
        self.assertFalse(out["automatic_resume_permitted"])

    def test_missing_first_cycle_refused(self):
        with self.assertRaises(InputError):
            verify_chain(sample()[1:])

    def test_missing_middle_cycle_refused(self):
        a, b, c = sample()
        with self.assertRaises(InputError):
            verify_chain([a, c])

    def test_reordered_cycle_refused(self):
        a, b, c = sample()
        with self.assertRaises(InputError):
            verify_chain([b, a, c])

    def test_corrupt_hash_refused(self):
        rows = sample()
        rows[1]["cycle_id"] = "evil"
        with self.assertRaises(InputError):
            verify_chain(rows)

    def test_repeat_identity_not_permitted(self):
        rows = sample()
        new = make_receipt("c001", "2026-11-10T00:03:00Z", "d" * 64, rows[-1])
        with self.assertRaises(InputError):
            verify_chain(rows + [new])

    def test_gap_is_recorded_no_autorestart(self):
        a = sample()[0]
        b = make_receipt("c002", "2026-11-10T00:15:00Z", "b" * 64, a)
        report = verify_chain([a, b])
        self.assertEqual(report["oversized_gap_count"], 1)
        self.assertEqual(report["gaps"][0]["gap_seconds"], 900)
        self.assertFalse(report["automatic_resume_permitted"])

    def test_invalid_gap_limit_refused(self):
        with self.assertRaises(InputError):
            verify_chain(sample(), max_gap_seconds=0)

    def test_single_cycle_never_certified_for_clock(self):
        result = verify_chain(sample()[:1])
        self.assertFalse(result["independent_clock_attested"])
        self.assertFalse(result["missing_history_outside_supplied_bundle_excluded"])

    def test_manifest_roundtrip_exact_hash(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            names = []
            for n, item in enumerate(sample(), 1):
                name = f"cycle_{n:03d}.json"
                (d / name).write_text(json.dumps(item))
                names.append(name)
            manifest, chain = build(d, names)
            self.assertEqual(chain["receipt_count"], 3)
            loaded = from_manifest(manifest, d)
            self.assertEqual(verify_chain(loaded)["receipt_count"], 3)
            self.assertEqual(manifest["receipts"][0]["sha256"],
                             hashlib.sha256((d/names[0]).read_bytes()).hexdigest())
            (d / "input_manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(chain_main([
                "--manifest", str(d / "input_manifest.json"),
                "--receipts-dir", str(d),
                "--out", str(d / "audited.json"),
            ]), 0)

    def test_manifest_rejects_modified_receipt_file(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            (d/"cycle.json").write_text(json.dumps(sample()[0]))
            manifest, _ = build(d, ["cycle.json"])
            (d/"cycle.json").write_text(json.dumps({**sample()[0], "sequence": 5}))
            with self.assertRaises(InputError):
                from_manifest(manifest, d)

    def test_manifest_refuses_parent_path(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(InputError):
                build(Path(root), ["../private.json"])

    def test_manifest_refuses_duplicate_file(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            (d/"cycle.json").write_text(json.dumps(sample()[0]))
            with self.assertRaises(InputError):
                build(d, ["cycle.json", "cycle.json"])

    def test_manifest_cli_collision(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            (d/"c.json").write_text(json.dumps(sample()[0]))
            args = ["--receipts-dir", str(d), "--receipt", "c.json",
                    "--out", str(d/"manifest.json")]
            self.assertEqual(manifest_main(args), 0)
            self.assertEqual(manifest_main(args), 2)

    def test_manifest_cli_bad_input_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            out = d/"manifest.json"
            self.assertEqual(manifest_main([
                "--receipts-dir", str(d), "--receipt", "absent.json",
                "--out", str(out),
            ]), 2)
            self.assertFalse(out.exists())

    def test_chain_cli_broken_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            manifest_path = d/"manifest.json"
            manifest_path.write_text(json.dumps({
                "schema": "fx_forward_receipt_chain_audit_v1",
                "receipts": [{"filename": "../notallowed.json",
                              "sha256": "a" * 64}],
            }))
            output = d/"audit.json"
            self.assertEqual(chain_main([
                "--manifest", str(manifest_path),
                "--receipts-dir", str(d),
                "--out", str(output),
            ]), 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
