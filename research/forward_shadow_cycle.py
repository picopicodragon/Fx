"""FX-FWD-005A: one-shot no-order shadow report from verified local journal.

Suitable for Windows Task Scheduler repeatedly invoking --cycle-id unique.
No internal daemon, no broker/network/paid AI calls; outputs are immutable
and never overwrite earlier evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone

from research import forward_quality as quality
from research import forward_paper as paper
from research.offline_backtest import InputError

CYCLE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


def run_once(store: Path, output_dir: Path, cycle_id: str,
             scenario: dict, *, asof_utc: str) -> dict:
    if (type(cycle_id) is not str or not CYCLE_ID.fullmatch(cycle_id)
            or not output_dir.is_dir()):
        raise InputError("invalid shadow cycle identity")
    paper.scenario_validate(scenario)
    qa_file = output_dir / (cycle_id + "_quality.json")
    paper_file = output_dir / (cycle_id + "_paper.json")
    if qa_file.exists() or paper_file.exists():
        raise InputError("shadow cycle already exists")
    verified_quality = quality.quality_report(
        store, asof_utc=asof_utc)
    simulation = paper.replay(store, scenario, asof_utc=asof_utc)
    # No production claims: simulation may include unverified quotes and
    # review-only synthetic hypotheses.
    if simulation["real_orders_permitted"] is not False or (
            verified_quality["source_authenticity_verified"]):
        raise InputError("shadow gate violation")
    with qa_file.open("x", encoding="utf-8") as f:
        json.dump(verified_quality, f, ensure_ascii=False, indent=2)
    with paper_file.open("x", encoding="utf-8") as f:
        json.dump(simulation, f, ensure_ascii=False, indent=2)
    return {
        "status": "FORWARD_SHADOW_CYCLE_NO_GO",
        "cycle_id": cycle_id,
        "quality_path": str(qa_file),
        "paper_path": str(paper_file),
        "observation_count": verified_quality["record_count"],
        "hypothetical_position": (
            simulation["hypothetical_position"] is not None),
        "source_authenticity_verified": False,
        "mt4_connected": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="One-shot offline shadow observation and paper audit")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--scenario", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.scenario.stat().st_size > 3000:
            raise InputError("oversize scenario")
        scenario = json.loads(
            args.scenario.read_text(encoding="utf-8-sig"))
        stamp = datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        result = run_once(args.store, args.out_dir, args.cycle_id,
                          scenario, asof_utc=stamp)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, ValueError, TypeError, OSError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "FORWARD_SHADOW_CYCLE_INVALID_OR_INCOMPLETE",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
