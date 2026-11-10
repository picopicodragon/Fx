"""FWD-033..037 reproducible offline bundle tests, never broker IO."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_offline_batch import INPUTS, audit, main as batch_main
from research.forward_bundle_manifest import build, main as manifest_main
from research.forward_restart_receipts import make_receipt
from research.offline_backtest import InputError

NOW = "2026-11-10T03:00:00Z"


def fixtures():
    common = {"runtime_go_no_go": "NO_GO",
              "safety_hold_latched": True, "real_orders_permitted": False}
    receipt = make_receipt("cycle1", "2026-11-10T02:59:00Z", "a" * 64)
    watch = {**common, "status": "FORWARD_SHADOW_WATCH_HOLD_NO_GO",
             "asof_utc": NOW, "watchdog_latched": False,
             "demo_order_execution_enabled": False}
    intake = {**common, "status": "SOURCE_INTAKE_RESEARCH_HOLD_NO_GO",
              "blocking_reasons": ["BROKER_AND_DATA_LICENSE_NOT_VERIFIED"]}
    demo = {**common, "status": "FWD_DEMO_READINESS_RESEARCH_NO_GO",
            "blocking_reasons": [], "demo_order_execution_enabled": False}
    mt4 = {**common, "status": "MT4_READONLY_EXPORT_RESEARCH_NO_GO",
           "asof_utc": NOW, "missing_pairs": [],
           "demo_order_execution_enabled": False}
    calendar = {**common, "status": "CALENDAR_REVISION_RESEARCH_NO_GO",
                "change_count": 0, "demo_order_execution_enabled": False}
    return {"receipt": receipt, "watchdog": watch, "intake": intake,
            "demo": demo, "mt4": mt4, "calendar": calendar}


def write_bundle(directory: Path, data=None):
    values = fixtures() if data is None else data
    names = {}
    for key, report in values.items():
        filename = key + ".json"
        (directory / filename).write_text(json.dumps(report), encoding="utf-8")
        names[key] = filename
    return names


class OfflineBatchTests(unittest.TestCase):
    def test_build_and_audit_end_to_end(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            manifest = build(path, names, asof_utc=NOW)
            result = audit(manifest, path)
            self.assertEqual(result["status"],
                             "FORWARD_OFFLINE_BATCH_EVIDENCE_HOLD_NO_GO")
            self.assertEqual(set(result["evidence_sha256"]), set(INPUTS))
            self.assertFalse(result["real_orders_permitted"])
            self.assertFalse(result["demo_order_execution_enabled"])
            self.assertIn("ACTUAL_BROKER_FORWARD_RUN_NOT_VERIFIED",
                          result["blocking_reasons"])

    def test_corrupt_report_refused_by_hash(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            manifest = build(path, names, asof_utc=NOW)
            (path / names["watchdog"]).write_text(
                json.dumps({**fixtures()["watchdog"],
                            "real_orders_permitted": True}))
            with self.assertRaises(InputError):
                audit(manifest, path)

    def test_future_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            values = fixtures()
            values["receipt"] = make_receipt(
                "cycle1", "2026-11-10T05:00:00Z", "a" * 64)
            names = write_bundle(path, values)
            with self.assertRaises(InputError):
                build(path, names, asof_utc=NOW)

    def test_missing_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            names.pop("demo")
            with self.assertRaises(InputError):
                build(path, names, asof_utc=NOW)

    def test_manifest_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            names["calendar"] = "../calendar.json"
            with self.assertRaises(InputError):
                build(path, names, asof_utc=NOW)

    def test_same_report_repeated_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            names["calendar"] = names["mt4"]
            with self.assertRaises(InputError):
                build(path, names, asof_utc=NOW)

    def test_forged_go_report_refused_before_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            values = fixtures()
            values["demo"]["runtime_go_no_go"] = "GO"
            names = write_bundle(path, values)
            with self.assertRaises(InputError):
                build(path, names, asof_utc=NOW)

    def test_reversed_watchdog_time_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            values = fixtures()
            values["watchdog"]["asof_utc"] = "2026-11-10T02:00:00Z"
            names = write_bundle(path, values)
            with self.assertRaises(InputError):
                audit(build(path, names, asof_utc=NOW), path)

    def test_local_report_compromised_after_hash_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            manifest = build(path, names, asof_utc=NOW)
            values = fixtures()
            values["intake"]["blocking_reasons"] = []
            (path / names["intake"]).write_text(json.dumps(values["intake"]))
            with self.assertRaises(InputError):
                audit(manifest, path)

    def test_manifest_cli_and_audit_cli(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            args = ["--reports-dir", str(path), "--asof-utc", NOW]
            for key in INPUTS:
                args += ["--" + key, names[key]]
            args += ["--out", str(path / "manifest.json")]
            self.assertEqual(manifest_main(args), 0)
            call = ["--manifest", str(path / "manifest.json"),
                    "--reports-dir", str(path),
                    "--out", str(path / "batch.json")]
            self.assertEqual(batch_main(call), 0)
            self.assertEqual(batch_main(call), 2)

    def test_extra_manifest_key_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            names = write_bundle(path)
            manifest = build(path, names, asof_utc=NOW)
            manifest["real_orders_permitted"] = True
            with self.assertRaises(InputError):
                audit(manifest, path)

    def test_bad_receipt_sha_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            values = fixtures()
            values["receipt"]["receipt_sha256"] = "f" * 64
            names = write_bundle(path, values)
            with self.assertRaises(InputError):
                audit(build(path, names, asof_utc=NOW), path)


if __name__ == "__main__":
    unittest.main()
