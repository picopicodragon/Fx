"""FWD-649..660: initializing the one-command plan from existing saved sources."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_evidence_runbook as runbook


def invoke(args):
    with patch("sys.stdout", new_callable=io.StringIO) as out:
        code = runbook.main(args)
    return code, json.loads(out.getvalue())


class SafeRunbookInitializationTests(unittest.TestCase):
    def test_initialize_plan_from_one_real_existing_folder_without_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bls = root / "bls-original"
            bls.mkdir()
            (bls / "manifest_marker").write_text("original")
            plan = root / "plan.json"
            result, response = invoke([
                "--init-plan", str(plan),
                "--init-bls-snapshot-dir", str(bls)])
            self.assertEqual(result, 0)
            self.assertEqual(response["runtime_go_no_go"], "NO_GO")
            data = json.loads(plan.read_text())
            self.assertEqual(Path(data["bls_snapshot_dir"]), bls)
            self.assertEqual(data["forecast_archives"], [])
            self.assertEqual((bls / "manifest_marker").read_text(), "original")

    def test_initialize_plan_from_both_known_source_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bls = root / "bls"
            news = root / "news"
            bls.mkdir()
            news.mkdir()
            plan = root / "config.json"
            rc, _ = invoke([
                "--init-plan", str(plan),
                "--init-bls-snapshot-dir", str(bls),
                "--init-official-news-bundle", str(news)])
            self.assertEqual(rc, 0)
            contents = json.loads(plan.read_text())
            self.assertEqual(contents["official_news_bundle"], str(news))
            self.assertEqual(contents["bls_snapshot_dir"], str(bls))
            self.assertEqual(contents["sessions"], [])

    def test_nonexistent_bls_source_prevents_plan_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / "plan.json"
            rc, result = invoke([
                "--init-plan", str(dest),
                "--init-bls-snapshot-dir", str(root / "missing")])
            self.assertEqual(rc, 2)
            self.assertFalse(dest.exists())
            self.assertFalse(result["real_orders_permitted"])

    def test_init_plan_refuses_writing_inside_immutable_bls_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bls = root / "bls"
            bls.mkdir()
            dest = bls / "plan.json"
            rc, _ = invoke([
                "--init-plan", str(dest),
                "--init-bls-snapshot-dir", str(bls)])
            self.assertEqual(rc, 2)
            self.assertFalse(dest.exists())

    def test_init_plan_refuses_writing_inside_immutable_news_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            news = root / "news"
            news.mkdir()
            dest = news / "plan.json"
            rc, _ = invoke([
                "--init-plan", str(dest),
                "--init-official-news-bundle", str(news)])
            self.assertEqual(rc, 2)
            self.assertFalse(dest.exists())

    def test_init_options_cannot_override_an_existing_plan_at_run_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bls = root / "bls"
            bls.mkdir()
            plan = root / "plan.json"
            plan.write_text(json.dumps(runbook.empty_plan()))
            rc, response = invoke([
                "--plan-file", str(plan),
                "--init-bls-snapshot-dir", str(bls)])
            self.assertEqual(rc, 2)
            self.assertEqual(response["runtime_go_no_go"], "NO_GO")

    def test_init_source_paths_must_be_real_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            news = root / "fake-news.txt"
            news.write_text("not a bundle folder")
            dest = root / "plan.json"
            rc, _ = invoke([
                "--init-plan", str(dest),
                "--init-official-news-bundle", str(news)])
            self.assertEqual(rc, 2)
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
