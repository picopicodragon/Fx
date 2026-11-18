"""Offline cross-pair audit of COMPLETED two-model research-only MT4 ledgers.

No API, network, trading intent, broker access or simulated order. Research
APPROVED/HOLD never equals execution approval. Cross-pair capture simultaneity
cannot be inferred from a ledger hash, so it is explicitly NOT_ATTESTED.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from research import final_demo_http401_recovery as recovery
from research.offline_backtest import InputError

SCHEMA = "fx_final_demo_three_pair_completed_ai_ledger_audit_v1"
SYMBOLS = ("USDJPY", "EURJPY", "EURUSD")
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
FAILURE_CODES = frozenset({
    "LEDGER_DIRECTORY_INVALID",
    "PAID_LEDGER_PENDING_OR_UNRECONCILED",
    "MISSING_COMPLETE_THREE_PAIR_LEDGER",
    "INVALID_LATEST_PAIR_LEDGER",
    "MODEL_IDENTITIES_INCONSISTENT",
    "INVALID_LEDGER_DIGEST",
    "UNSAFE_OUTPUT_LOCATION",
})


def audit(folder: Path) -> dict:
    if (not isinstance(folder, Path) or not folder.is_dir()
            or folder.is_symlink()
            or any(path.is_symlink() for path in folder.parents)):
        raise InputError("LEDGER_DIRECTORY_INVALID")
    # This guard allows an old 401 analyst attempt only when a separately
    # recorded, hash-bound manual review exists. Other pendings always block.
    checked = recovery.check_directory(folder)
    details = []
    models = set()
    for symbol, pair in zip(SYMBOLS, PAIRS):
        paths = sorted(folder.glob(f"ai_{symbol}_*.json"),
                       key=lambda path: path.name, reverse=True)
        if not paths:
            raise InputError("MISSING_COMPLETE_THREE_PAIR_LEDGER")
        latest = paths[0]
        state, digest = recovery._read_ledger(latest)
        if (state["stage"] != "COMPLETE"
                or state["pending_role"] is not None
                or state["analyst"] is None
                or state["reviewer"] is None):
            raise InputError("INVALID_LATEST_PAIR_LEDGER")
        packet = state["packet_sha256"]
        if (type(packet) is not str or DIGEST.fullmatch(packet) is None
                or packet == "0" * 64):
            raise InputError("INVALID_LEDGER_DIGEST")
        model_ids = (state["analyst_model"], state["reviewer_model"])
        models.add(model_ids)
        details.append({
            "pair": pair,
            "research_status": "TWO_MODELS_COMPLETED",
            "analyst_action": state["analyst"]["action"],
            "reviewer_verdict": state["reviewer"]["verdict"],
            "analyst_model": model_ids[0],
            "reviewer_model": model_ids[1],
            "packet_sha256_local_only": packet,
            "ledger_sha256_local_only": digest,
            "ledger_file": latest.name,
            "candidate_is_not_executable": True,
        })
    if len(models) != 1:
        raise InputError("MODEL_IDENTITIES_INCONSISTENT")
    return {
        "schema": SCHEMA,
        "status": "THREE_PAIR_AI_RESEARCH_AUDITED_HOLD_NO_GO",
        "completed_pairs": 3,
        "results": details,
        "all_analyst_actions_hold": all(
            row["analyst_action"] == "HOLD" for row in details),
        "all_review_verdicts_approved": all(
            row["reviewer_verdict"] == "APPROVED" for row in details),
        "previous_401_rejections_manually_reviewed":
            checked["operator_reviewed_http401"],
        "audit_is_local_ledger_only": True,
        "cross_pair_same_snapshot": "NOT_ATTESTED",
        "point_in_time_news_consensus": "NOT_ATTESTED",
        "broker_server_clock": "NOT_ATTESTED",
        "market_execution_verified": False,
        "api_inference_calls_this_run": 0,
        "demo_orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline, no-API three-pair completed research audit")
    parser.add_argument("--ledger-directory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(args.ledger_directory)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("UNSAFE_OUTPUT_LOCATION")
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False,
                      indent=2, allow_nan=False)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, TypeError, ValueError, KeyError,
            UnicodeError, OverflowError) as exc:
        code = (exc.args[0] if isinstance(exc, InputError)
                and exc.args and type(exc.args[0]) is str else "")
        print(json.dumps({
            "schema": SCHEMA,
            "status": "THREE_PAIR_AI_AUDIT_FAIL_CLOSED_NO_GO",
            "failure_reason_code": code if code in FAILURE_CODES
            else "LEDGER_AUDIT_VALIDATION_FAILED",
            "api_inference_calls_this_run": 0,
            "demo_orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
