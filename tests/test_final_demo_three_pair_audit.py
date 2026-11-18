"""Three-pair completed research ledger aggregator; no network/orders."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import final_demo_three_pair_audit as audit
from research import final_demo_http401_recovery as recovery
from research import final_demo_periodic_ai as pipeline
from research.offline_backtest import InputError


def write_ledger(root: Path, symbol: str, *,
                 stage: str = "COMPLETE",
                 action: str = "HOLD",
                 verdict: str = "APPROVED") -> Path:
    name = f"ai_{symbol}_20261118_090000_001.json"
    state = {
        "schema": pipeline.SCHEMA,
        "packet_sha256": "a" * 64,
        "analyst_model": "research-analyst",
        "reviewer_model": "research-reviewer",
        "stage": stage,
        "pending_role": None,
        "analyst": {
            "action": action,
            "hypothesis": "Sources do not prove the direction",
            "counterevidence": "Consensus unavailable",
        },
        "reviewer": {
            "verdict": verdict,
            "rationale": "Do not trade unsupported narratives",
        },
        "execution_authorized": False,
        "real_orders_permitted": False,
    }
    if stage == "ANALYST_PENDING":
        state["pending_role"] = "analyst"
        state["analyst"] = None
        state["reviewer"] = None
    path = root / name
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


class ThreePairResearchAudit(unittest.TestCase):
    def test_realistic_three_pair_complete_hold_is_research_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for symbol in audit.SYMBOLS:
                write_ledger(root, symbol)
            with patch.object(recovery.urllib.request, "urlopen") as network:
                result = audit.audit(root)
                network.assert_not_called()
            self.assertEqual(result["completed_pairs"], 3)
            self.assertTrue(result["all_analyst_actions_hold"])
            self.assertTrue(result["all_review_verdicts_approved"])
            self.assertEqual(
                [row["pair"] for row in result["results"]],
                list(audit.PAIRS))
            self.assertEqual(result["cross_pair_same_snapshot"],
                             "NOT_ATTESTED")
            self.assertEqual(result["api_inference_calls_this_run"], 0)
            self.assertEqual(result["demo_orders_sent_this_run"], 0)
            self.assertFalse(result["demo_orders_permitted"])
            self.assertFalse(result["real_orders_permitted"])
            out = root / "three_pair_audit.json"
            self.assertEqual(
                audit.main(["--ledger-directory", str(root),
                            "--out", str(out)]), 0)
            self.assertTrue(out.exists())
            self.assertEqual(json.loads(out.read_text())["completed_pairs"],3)
            self.assertEqual(
                audit.main(["--ledger-directory", str(root),
                            "--out", str(out)]), 2)

    def test_missing_pair_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_ledger(root, "USDJPY")
            write_ledger(root, "EURJPY")
            with self.assertRaises(InputError):
                audit.audit(root)
            out = root / "not_created.json"
            self.assertEqual(audit.main([
                "--ledger-directory", str(root), "--out", str(out)]), 2)
            self.assertFalse(out.exists())

    def test_unreconciled_pending_blocks_all(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for symbol in audit.SYMBOLS:
                write_ledger(root, symbol)
            pending = write_ledger(root, "EURJPY", stage="ANALYST_PENDING")
            with self.assertRaises(InputError):
                audit.audit(root)
            self.assertTrue(pending.exists())

    def test_non_hold_research_never_makes_trading_permitted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for symbol in audit.SYMBOLS:
                write_ledger(root, symbol,
                             action="LONG" if symbol=="EURUSD" else "HOLD")
            result = audit.audit(root)
            self.assertFalse(result["all_analyst_actions_hold"])
            self.assertFalse(result["demo_orders_permitted"])
            self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_differing_provider_models_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for symbol in audit.SYMBOLS:
                write_ledger(root, symbol)
            path = root / "ai_EURUSD_20261118_090000_001.json"
            payload = json.loads(path.read_text())
            payload["reviewer_model"] = "different-reviewer"
            path.write_text(json.dumps(payload))
            with self.assertRaises(InputError):
                audit.audit(root)

    def test_previously_reviewed_http401_is_not_counted_as_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for symbol in audit.SYMBOLS:
                write_ledger(root, symbol)
            pending = root / "ai_USDJPY_20261117_090000_001.json"
            state = json.loads((root/"ai_USDJPY_20261118_090000_001.json").read_text())
            state.update({"stage": "ANALYST_PENDING",
                          "pending_role": "analyst",
                          "analyst": None, "reviewer": None})
            pending.write_text(json.dumps(state))
            old, digest = recovery._read_ledger(pending)
            marker = {
                "schema": recovery.SCHEMA,
                "ledger_name": pending.name,
                "ledger_sha256": digest,
                "analyst_model": old["analyst_model"],
                "reviewer_model": old["reviewer_model"],
                "rejected_failure": recovery.HTTP401,
                "operator_confirmed_http401": True,
                "read_only_auth_http": 200,
                "read_only_models_present": True,
                "api_inference_calls_during_review": 0,
                "trading_authorized": False,
            }
            recovery._review_path(pending).write_text(json.dumps(marker))
            result = audit.audit(root)
            self.assertEqual(result[
                "previous_401_rejections_manually_reviewed"], 1)
            self.assertEqual(result["completed_pairs"], 3)

    def test_old_ledger_file_not_sufficient_if_newest_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for symbol in audit.SYMBOLS:
                write_ledger(root,symbol)
            newest=root/"ai_USDJPY_20261118_100000_001.json"
            state=json.loads((root/"ai_USDJPY_20261118_090000_001.json").read_text())
            state["stage"]="REVIEW_PENDING"
            state["pending_role"]="reviewer"
            state["reviewer"]=None
            newest.write_text(json.dumps(state))
            with self.assertRaises(InputError):
                audit.audit(root)


if __name__ == "__main__":
    unittest.main()
