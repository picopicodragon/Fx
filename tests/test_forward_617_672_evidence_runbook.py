"""FWD-617..672: reusable explicit research evidence plan and prioritized tasks."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_evidence_runbook as runbook
from research.offline_backtest import InputError

ASOF = "2026-11-13T04:00:00Z"
ASOF_LATER = "2026-11-13T05:00:00Z"


def planfile(root: Path, data=None):
    path = root / "plan.json"
    path.write_text(json.dumps(
        runbook.empty_plan() if data is None else data,
        ensure_ascii=False), encoding="utf-8")
    return path


def call(args):
    with patch("sys.stdout", new_callable=io.StringIO) as output:
        rc = runbook.main(args)
    return rc, json.loads(output.getvalue())


class EvidenceRunbookTests(unittest.TestCase):
    def test_empty_plan_is_still_safe_and_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            p = planfile(Path(td))
            rc, r = call(["--plan-file", str(p), "--asof-utc", ASOF])
        self.assertEqual(rc, 0)
        self.assertEqual(r["status"], "RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO")
        self.assertFalse(r["input_evidence_counts"]["bls_bundle"])
        self.assertEqual(r["input_evidence_counts"]["forecast_archives"], 0)
        self.assertEqual(r["fullstack_report"]["mt4_copied_observation_session_count"], 0)
        self.assertFalse(r["fullstack_report"]["price_ai_campaign_inspected"])
        self.assertFalse(r["no_go_cannot_be_cleared_by_runbook"] is False)
        self.assertFalse(r["real_orders_permitted"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertTrue(r["safety_hold_latched"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_plan_file_paths_resolve_from_plan_location_not_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "news").mkdir()
            (root / "forecast.json").write_text('{"not":"real"}')
            data = runbook.empty_plan()
            data["official_news_bundle"] = "news"
            data["forecast_archives"] = ["forecast.json"]
            plan = planfile(root, data)
            d, digest = runbook.read_plan(plan)
            self.assertEqual(d["official_news_bundle"], root / "news")
            self.assertEqual(d["forecast_archives"], [root / "forecast.json"])
            self.assertEqual(len(digest), 64)

    def test_explicit_missing_evidence_is_error_not_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            data = runbook.empty_plan()
            data["bls_snapshot_dir"] = "missing"
            p = planfile(Path(td), data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)
            rc, r = call(["--plan-file", str(p), "--asof-utc", ASOF])
        self.assertEqual(rc, 2)
        self.assertEqual(r["status"], "RUNBOOK_RESEARCH_FAIL_CLOSED_NO_GO")
        self.assertFalse(r["real_orders_permitted"])

    def test_init_plan_once_then_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "plan.json"
            rc, result = call(["--init-plan", str(p)])
            self.assertEqual(rc, 0)
            self.assertFalse(result["evidence_sources_populated"])
            contents = p.read_bytes()
            self.assertEqual(json.loads(contents), runbook.empty_plan())
            rc2, result2 = call(["--init-plan", str(p)])
            self.assertEqual(rc2, 2)
            self.assertEqual(contents, p.read_bytes())
            self.assertEqual(result2["runtime_go_no_go"], "NO_GO")

    def test_init_plan_cannot_be_combined_with_output(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "plan.json"
            rc, _ = call(["--init-plan", str(p),
                          "--out", str(Path(td) / "report.json")])
            self.assertEqual(rc, 2)
            self.assertFalse(p.exists())

    def test_unknown_plan_keys_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            data = runbook.empty_plan()
            data["auto_trade"] = True
            p = planfile(Path(td), data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_invalid_schema_version_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            data = runbook.empty_plan()
            data["schema"] = "fx_fwd_evidence_runbook_v2"
            p = planfile(Path(td), data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_untrusted_globbed_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            data = runbook.empty_plan()
            data["bls_snapshot_dir"] = "Fx-FWD*/out/snapshot"
            p = planfile(Path(td), data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_duplicate_evidence_path_in_two_roles_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "same.json").write_text("{}")
            data = runbook.empty_plan()
            data["external_macro_file"] = "same.json"
            data["ai_ledgers"] = ["same.json"]
            p = planfile(root, data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_duplicate_session_labels_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a").mkdir()
            (root / "b").mkdir()
            data = runbook.empty_plan()
            data["sessions"] = [
                {"label": "one", "directory": "a",
                 "experts_log": None, "compile_log": None},
                {"label": "one", "directory": "b",
                 "experts_log": None, "compile_log": None},
            ]
            p = planfile(root, data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_25_sessions_rejected_before_accessing_folders(self):
        with tempfile.TemporaryDirectory() as td:
            data = runbook.empty_plan()
            data["sessions"] = [
                {"label": "s"+str(i), "directory": "missing"+str(i),
                 "experts_log": None, "compile_log": None}
                for i in range(25)]
            p = planfile(Path(td), data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_empty_session_directory_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "session").mkdir()
            data = runbook.empty_plan()
            data["sessions"] = [{
                "label": "demo", "directory": "session",
                "experts_log": None, "compile_log": None}]
            p = planfile(root, data)
            rc, response = call([
                "--plan-file", str(p), "--asof-utc", ASOF])
        self.assertEqual(rc, 2)
        self.assertEqual(response["runtime_go_no_go"], "NO_GO")

    def test_symlink_file_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "raw.json").write_text("{}")
            link = root / "alias.json"
            try:
                link.symlink_to(root / "raw.json")
            except (OSError, NotImplementedError):
                self.skipTest("host forbids test symlinks")
            data = runbook.empty_plan()
            data["external_macro_file"] = "alias.json"
            p = planfile(root, data)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_output_one_shot_then_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = planfile(root)
            out = root / "report.json"
            rc, r = call([
                "--plan-file", str(p), "--asof-utc", ASOF,
                "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out.read_text())["status"],
                             "RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO")
            before = out.read_bytes()
            again, failure = call([
                "--plan-file", str(p), "--asof-utc", ASOF,
                "--out", str(out)])
            self.assertEqual(again, 2)
            self.assertEqual(out.read_bytes(), before)
            self.assertFalse(failure["real_orders_permitted"])

    def test_output_cannot_equal_plan(self):
        with tempfile.TemporaryDirectory() as td:
            p = planfile(Path(td))
            before = p.read_bytes()
            rc, _ = call([
                "--plan-file", str(p), "--out", str(p),
                "--asof-utc", ASOF])
            self.assertEqual(rc, 2)
            self.assertEqual(before, p.read_bytes())

    def test_prior_report_diff_can_run_without_any_broker_or_api(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = planfile(root)
            previous = root / "previous.json"
            first, old = call([
                "--plan-file", str(p), "--asof-utc", ASOF,
                "--out", str(previous)])
            self.assertEqual(first, 0)
            newer, report = call([
                "--plan-file", str(p), "--asof-utc", ASOF_LATER,
                "--previous-report", str(previous)])
        self.assertEqual(newer, 0)
        self.assertTrue(report["compared_prior_report_self_attested_only"])
        delta = report["previous_report_change_summary"]
        self.assertTrue(delta["holding_reason_disappearance_is_not_safety_clearance"])
        self.assertFalse(delta["human_or_runtime_reauthorization_permitted"])
        self.assertEqual(delta["runtime_go_no_go"], "NO_GO")

    def test_prior_report_with_fake_go_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = planfile(root)
            _, result = call(["--plan-file", str(p), "--asof-utc", ASOF])
            result["fullstack_report"]["real_orders_permitted"] = True
            prev = root / "forged.json"
            prev.write_text(json.dumps(result))
            rc, response = call([
                "--plan-file", str(p),
                "--previous-report", str(prev),
                "--asof-utc", ASOF_LATER])
        self.assertEqual(rc, 2)
        self.assertEqual(response["status"],
                         "RUNBOOK_RESEARCH_FAIL_CLOSED_NO_GO")

    def test_previous_report_in_future_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = planfile(root)
            _, newer = call([
                "--plan-file", str(p), "--asof-utc", ASOF_LATER])
            prev = root / "future.json"
            prev.write_text(json.dumps(newer))
            rc, _ = call([
                "--plan-file", str(p),
                "--previous-report", str(prev),
                "--asof-utc", ASOF])
        self.assertEqual(rc, 2)

    def test_task_priority_is_deterministic_not_trading_advice(self):
        tasks = ["REVIEW_QUOTE_DATA", "VERIFY_MT4_CLOCK",
                 "CAPTURE_PRE_RELEASE_CONSENSUS",
                 "OBTAIN_FRESH_BLS_CALENDAR", "REVIEW_QUOTE_DATA"]
        groups = runbook.prioritize(tasks)
        self.assertEqual(groups[0]["category"],
                         "PRIORITY_1_PRE_RELEASE_CONSENSUS_EVIDENCE")
        self.assertEqual(groups[1]["category"],
                         "PRIORITY_2_GLOBAL_EVENT_SOURCE_COVERAGE")
        self.assertEqual(groups[2]["category"],
                         "PRIORITY_3_MT4_NOORDER_SAFETY_EVIDENCE")
        self.assertEqual(groups[3]["category"],
                         "PRIORITY_4_PRICE_AI_RESEARCH")
        self.assertEqual(groups[3]["action_count"], 1)

    def test_more_than_256_action_strings_rejected(self):
        with self.assertRaises(InputError):
            runbook.prioritize(["ACTION"+str(i) for i in range(257)])

    def test_no_network_api_or_mt4_operations_in_empty_run(self):
        with tempfile.TemporaryDirectory() as td:
            plan = planfile(Path(td))
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("unexpected HTTP call")):
                rc, report = call([
                    "--plan-file", str(plan), "--asof-utc", ASOF])
        self.assertEqual(rc, 0)
        self.assertEqual(report["API_calls_this_run"], 0)
        self.assertEqual(report["network_calls_this_run"], 0)
        self.assertEqual(report["orders_sent_this_run"], 0)
        self.assertFalse(report["automatic_network_or_api_calls"])


if __name__ == "__main__":
    unittest.main()
