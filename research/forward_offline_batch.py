"""FWD-033/034/035: single-run offline integrity and readiness orchestration.

All input reports are immutable local research artifacts. This orchestrator
never starts MT4, invokes a model, reaches the network, or places orders.
It does not certify genuine market data or grant demo/live trade permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research.offline_backtest import InputError, timestamp
from research.forward_restart_receipts import verify_receipt
from research.forward_demo_gate_board import board
from research.forward_shadow_campaign import audit as campaign

SCHEMA = "fx_forward_offline_batch_v1"
MAX_REPORT_BYTES = 1_000_000
SHA = re.compile(r"^[0-9a-f]{64}$")
INPUTS = ("receipt", "watchdog", "intake", "demo", "mt4", "calendar")
STATUSES = {
    "receipt": "FORWARD_RESTART_RECEIPT_NO_GO",
    "watchdog": "FORWARD_SHADOW_WATCH_HOLD_NO_GO",
    "intake": "SOURCE_INTAKE_RESEARCH_HOLD_NO_GO",
    "demo": "FWD_DEMO_READINESS_RESEARCH_NO_GO",
    "mt4": "MT4_READONLY_EXPORT_RESEARCH_NO_GO",
    "calendar": "CALENDAR_REVISION_RESEARCH_NO_GO",
}


def _load(path: Path) -> tuple[dict, str]:
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_REPORT_BYTES:
        raise InputError("absent or oversized research evidence")
    raw = path.read_bytes()
    try:
        obj = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise InputError("invalid research JSON") from exc
    if type(obj) is not dict:
        raise InputError("research report is not an object")
    return obj, hashlib.sha256(raw).hexdigest()


def audit(manifest: dict, directory: Path, *,
          ai_ledgers: list[dict] | None = None) -> dict:
    """Report evidence linkage without claiming proof of external origin."""
    if (type(manifest) is not dict or
            set(manifest) != {"schema", "artifacts", "asof_utc"} or
            manifest["schema"] != SCHEMA or
            type(manifest["artifacts"]) is not dict or
            set(manifest["artifacts"]) != set(INPUTS)):
        raise InputError("unexpected batch manifest")
    target_time = timestamp(manifest["asof_utc"])
    paths = []
    reports = {}
    hashes = {}
    for name in INPUTS:
        entry = manifest["artifacts"][name]
        if (type(entry) is not dict or set(entry) != {"filename", "sha256"} or
                type(entry["filename"]) is not str or
                not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\.json",
                                 entry["filename"]) or
                type(entry["sha256"]) is not str or
                not SHA.fullmatch(entry["sha256"])):
            raise InputError("invalid manifest entry")
        name_path = directory / entry["filename"]
        if entry["filename"] in paths:
            raise InputError("duplicate evidence path")
        paths.append(entry["filename"])
        report, digest = _load(name_path)
        if digest != entry["sha256"]:
            raise InputError("evidence sha256 mismatch")
        if (report.get("status") != STATUSES[name] or
                report.get("runtime_go_no_go") != "NO_GO" or
                report.get("safety_hold_latched") is not True or
                report.get("real_orders_permitted") is not False):
            raise InputError("untrusted research evidence")
        reports[name], hashes[name] = report, digest
    verify_receipt(reports["receipt"])
    for name in ("receipt", "watchdog", "mt4"):
        stamp = timestamp(reports[name]["asof_utc"])
        if stamp > target_time:
            raise InputError("report captured after cutoff")
    if timestamp(reports["watchdog"]["asof_utc"]) < (
            timestamp(reports["receipt"]["asof_utc"])):
        raise InputError("watchdog older than the receipt")
    # Reuse existing project risk/audit modules. They always return NO_GO.
    gate = board({
        "demo": reports["demo"], "watch": reports["watchdog"],
        "mt4": reports["mt4"], "calendar": reports["calendar"],
    })
    quality = campaign(ai_ledgers or [], reports["watchdog"],
                       reports["intake"], reports["receipt"])
    reasons = set(gate["blocking_reasons"] + quality["blocking_reasons"])
    reasons.update(("LOCAL_HASHES_ARE_NOT_EXTERNAL_AUTHENTICATION",
                    "ACTUAL_BROKER_FORWARD_RUN_NOT_VERIFIED"))
    return {
        "schema": SCHEMA,
        "status": "FORWARD_OFFLINE_BATCH_EVIDENCE_HOLD_NO_GO",
        "asof_utc": manifest["asof_utc"],
        "evidence_sha256": hashes,
        "receipt_sequence": reports["receipt"]["sequence"],
        "demo_board": gate, "shadow_campaign": quality,
        "blocking_reasons": sorted(reasons),
        "all_evidence_is_locally_supplied": True,
        "independent_clock_attested": False,
        "market_data_source_authenticated": False,
        "mt4_session_authenticated": False,
        "external_request_count": 0,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="One-shot offline no-order evidence audit (never GO)")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--reports-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if (args.out.exists() or not args.out.parent.is_dir() or
                not args.reports_dir.is_dir() or
                not args.manifest.is_file() or
                args.manifest.stat().st_size > 100_000):
            raise InputError("unsafe file path")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        report = audit(manifest, args.reports_dir)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": report["status"],
            "evidence_count": len(report["evidence_sha256"]),
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "INVALID_OFFLINE_FORWARD_BATCH",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True, "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
