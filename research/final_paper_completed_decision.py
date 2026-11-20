"""Reuse only a RECENT, fully completed and packet-matched two-model ledger.

Strictly local. No model request, broker access, orders, or ledger repair.
The ledger file's mtime is a PC-derived lower-confidence completion marker,
not independent provider timestamp attestation. A stale saved decision never
becomes a new live instruction.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from research import final_demo_http401_recovery as ledger_reader
from research import final_demo_periodic as period
from research import final_demo_periodic_ai as ai
from research import final_paper_engine as paper
from research.offline_backtest import InputError

MAX_REVIEW_AGE_SECONDS = 4200
MAX_FOLDER_ITEMS = 1000


def load_completed(root: Path, captures: Path, bundles: list[Path],
                   pair: str, bar_epoch: int, now: datetime) -> dict | None:
    """Validate source-linked saved decisions; return an internal signal or None."""
    if (pair not in paper.PAIRS or type(bar_epoch) is not int
            or bar_epoch <= 0 or now.tzinfo is None
            or not bundles or len(bundles) > 5):
        raise InputError("invalid saved decision context")
    folder = root / "ai_research"
    if not folder.is_dir() or folder.is_symlink():
        raise InputError("missing AI evidence folder")
    symbol = paper.SYMS[paper.PAIRS.index(pair)]
    name = re.compile(
        r"^ai_" + symbol + r"_" + str(bar_epoch) +
        r"_[0-9]{8}_[0-9]{6}\.json$")
    # Reject unknown ledger names and ambiguous two-ledger candidates for
    # one pair/bar. Completed AI results must not be silently cherry-picked.
    files = sorted(folder.glob("ai_*.json"))
    if len(files) > MAX_FOLDER_ITEMS:
        raise InputError("too many saved AI ledgers")
    matches = [f for f in files if name.fullmatch(f.name)]
    if not matches:
        return None
    if len(matches) != 1:
        raise InputError("ambiguous repeated independent review")
    source = matches[0]
    if (source.is_symlink() or not source.is_file()
            or any(p.is_symlink() for p in source.parents)
            or not 0 < source.stat().st_size <= 30_000):
        raise InputError("unsafe saved AI decision")
    state, digest = ledger_reader._read_ledger(source)
    if state["stage"] != "COMPLETE" or state["pending_role"] is not None:
        raise InputError("saved AI decision pending review")
    if state["analyst_model"] == state["reviewer_model"]:
        raise InputError("two independent model identities required")
    # Use the saved final file modification time, never the beginning of the
    # request, as the conservative local completion timestamp.
    finished = source.stat().st_mtime
    elapsed = now.timestamp() - finished
    if not 0 <= elapsed <= MAX_REVIEW_AGE_SECONDS:
        raise InputError("saved AI decision expired or future dated")
    capture = period._read_h1(captures, now)
    if (finished < datetime.fromisoformat(
            capture["captured_at_utc_pc_unattested"].replace(
                "Z", "+00:00")).timestamp()):
        raise InputError("AI decision predates quoted H1 packet")
    report = period.run(captures, bundles, pair, source,
                        now=now, output_must_be_new=False)
    if not report["macro_coverage_complete_research_only"]:
        raise InputError("original news/H1 provenance incomplete")
    ident = ai._identity(report, state["analyst_model"],
                         state["reviewer_model"])
    ai._valid(state, ident)
    if state["packet_sha256"] != ident["packet_sha256"]:
        raise InputError("saved decision not linked to original AI packet")
    return {
        "id": hashlib.sha256(
            (pair + ":" + str(bar_epoch) + ":" +
             ident["packet_sha256"] + ":" + digest).encode("utf-8")
        ).hexdigest(),
        "pair": pair,
        "action": state["analyst"]["action"],
        "verdict": state["reviewer"]["verdict"],
        "reviewed_epoch": int(finished),
        "atr14": str(report["technical"]["atr14"]),
        "packet_sha256": ident["packet_sha256"],
    }
