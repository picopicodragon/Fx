"""One-use, operator-staged communication latch release for INTERNAL PAPER only.

No broker actions, no AI requests, no historic-journal mutations. The staging
command runs only while the existing Python supervisor is stopped. The next
fresh quote can consume the head-bound authorization once, within a tight
clock window. Calendar/clock/cost/AI entry gates remain separately closed.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_reentry_review as reentry
from research import final_paper_ai_continuation_audit as ai_audit
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_manual_comm_release_v1"
NAME = "manual_comm_release_20261118.json"
EVENT = "PAPER_20261118_CYCLE_106_TO_107"
APPROVAL = "APPROVE_INTERNAL_VIRTUAL_COMMUNICATION_LATCH_RELEASE_ONLY"
MAX_PERMIT_AGE = 300
MAX_CAPTURE_GAP = 180
MAX_QUOTE_AGE = 120
EXPECTED_KEYS = frozenset({
    "schema", "event_id", "operator_approval", "created_epoch_pc_unattested",
    "journal_cycles", "journal_head_sha256", "last_quote_epoch",
    "last_observed_mt4_epoch", "permit_sha256",
})


def _validate_current_state(state: dict) -> None:
    if (state.get("virtual_only") is not True
            or state.get("broker_orders_permitted") is not False
            or state.get("jev_required") is not False
            or state.get("communication_latched") is not True
            or state.get("dd4_latched") is not False
            or state.get("dd5_latched") is not False
            or state.get("daily_loss_latched") is not False
            or state.get("positions") != []
            or state.get("pending_signals") != []
            or state.get("manual_comm_release_sha256") is not None
            or type(state.get("cycle_number")) is not int
            or state["cycle_number"] < 118
            or type(state.get("last_quote_epoch")) is not int
            or state["last_quote_epoch"] <= 0):
        raise InputError("PAPER_COMM_RELEASE_RISK_STATE_UNSAFE")


def _reject_other_gaps(root: Path, state: dict) -> None:
    # The only historically attested >600s gap is #106 -> #107,
    # exactly 3420 seconds. All other cycles must be ordered and <=600s.
    journal = root / "journal"
    before = None
    for n in range(1, state["cycle_number"] + 1):
        file = journal / f"{n:08d}.json"
        if not file.is_file() or file.is_symlink():
            raise InputError("PAPER_COMM_RELEASE_JOURNAL_CHANGED")
        try:
            event = json.loads(file.read_text("utf-8-sig"))
            quote_epoch = event["state"]["last_quote_epoch"]
        except (KeyError, ValueError, UnicodeError, OSError, TypeError) as exc:
            raise InputError("PAPER_COMM_RELEASE_JOURNAL_CHANGED") from exc
        if type(quote_epoch) is not int:
            raise InputError("PAPER_COMM_RELEASE_JOURNAL_CHANGED")
        if before is not None:
            gap = quote_epoch - before
            if (gap <= 0 or (gap > 600 and
                    not (n == 107 and gap == 3420))):
                raise InputError("PAPER_COMM_RELEASE_OTHER_GAP_UNATTESTED")
        before = quote_epoch
    if before != state["last_quote_epoch"]:
        raise InputError("PAPER_COMM_RELEASE_JOURNAL_CHANGED")


def _fresh_observation(quote: dict, state: dict, now: datetime) -> int:
    epoch = quote["capture_epoch"]
    if (type(epoch) is not int or
            not 0 <= int(now.timestamp()) - epoch <= MAX_QUOTE_AGE or
            not state["last_quote_epoch"] <= epoch <=
                state["last_quote_epoch"] + MAX_CAPTURE_GAP):
        raise InputError("PAPER_COMM_RELEASE_MT4_QUOTE_UNSAFE")
    return epoch


def stage(root: Path, mt4: Path, *, now: datetime | None = None,
          operator_approval: str = "") -> dict:
    if operator_approval != APPROVAL:
        raise InputError("PAPER_COMM_RELEASE_EXPLICIT_APPROVAL_REQUIRED")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
        raise InputError("PAPER_COMM_RELEASE_CLOCK_UNSAFE")
    if (not root.is_dir() or root.is_symlink()
            or any(p.is_symlink() for p in root.parents)
            or not mt4.is_dir() or mt4.is_symlink()
            or not str(mt4.resolve()).lower().endswith(
                str(Path("MQL4") / "Files").lower())):
        raise InputError("PAPER_COMM_RELEASE_PATH_UNSAFE")
    if ((root / ".single_operator.lock").exists()
            or (root / ".single_operator.lock").is_symlink()):
        raise InputError("PAPER_COMM_RELEASE_SUPERVISOR_LOCK_PRESENT")
    target = root / NAME
    if target.exists() or target.is_symlink():
        raise InputError("PAPER_COMM_RELEASE_PERMIT_ALREADY_EXISTS")
    state, head = runtime._journal_load(root / "journal")
    _validate_current_state(state)
    _reject_other_gaps(root, state)
    paid = ai_audit.audit(root)
    if (paid.get("journal_cycles") != state["cycle_number"]
            or paid.get("journal_head_sha256_local_only") != head
            or paid.get("paid_calls_recorded_in_journal") !=
                paid.get("paid_calls_in_completed_ledgers")):
        raise InputError("PAPER_COMM_RELEASE_AI_LEDGER_UNRECONCILED")
    review = reentry.review(root)
    if (review.get("historical_event_id") != EVENT
            or review.get("recent_quote_continuity_and_risk_review_ok") is not True
            or review.get("release_plan_may_be_reviewed_by_operator") is not True
            or review.get("journal_cycles") != state["cycle_number"]
            or review.get("journal_head_sha256_local_only") != head):
        raise InputError("PAPER_COMM_RELEASE_REENTRY_REVIEW_INCOMPLETE")
    quote = runtime._latest_quote(mt4, now)
    if quote is None:
        raise InputError("PAPER_COMM_RELEASE_NO_FRESH_MT4_QUOTE")
    epoch = _fresh_observation(quote, state, now)
    # Detect journal movement during review. Never append an approval against
    # a stale head or under a running supervisor.
    again, new_head = runtime._journal_load(root / "journal")
    if (new_head != head or again != state
            or (root / ".single_operator.lock").exists()):
        raise InputError("PAPER_COMM_RELEASE_CONCURRENT_CHANGE")
    record = {
        "schema": SCHEMA, "event_id": EVENT,
        "operator_approval": APPROVAL,
        "created_epoch_pc_unattested": int(now.timestamp()),
        "journal_cycles": state["cycle_number"],
        "journal_head_sha256": head,
        "last_quote_epoch": state["last_quote_epoch"],
        "last_observed_mt4_epoch": epoch,
    }
    record["permit_sha256"] = runtime._digest(record)
    with target.open("x", encoding="utf-8") as out:
        json.dump(record, out, indent=2, ensure_ascii=False)
        out.flush()
        import os
        os.fsync(out.fileno())
    return {
        "status": "VIRTUAL_COMM_RELEASE_STAGED_NOT_YET_APPLIED_NO_GO",
        "permit_path": str(target),
        "bound_journal_cycles": state["cycle_number"],
        "bound_head_sha256": head,
        "permit_sha256": record["permit_sha256"],
        "communication_latch_cleared": False,
        "new_virtual_entries_permitted": False,
        "new_paid_calls_permitted": False,
        "broker_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
    }


def apply_if_valid(root: Path, state: dict, head: str, quote: dict,
                   now: datetime) -> tuple[dict, bool]:
    # A consumed marker persists through later cycles. Never reuse this
    # historical approval to clear a new interruption's latch.
    marker = state.get("manual_comm_release_sha256")
    if marker is not None:
        if type(marker) is not str or runtime.SHA.fullmatch(marker) is None:
            raise InputError("PAPER_COMM_RELEASE_MARKER_UNSAFE")
        return state, False
    permit = root / NAME
    if not permit.exists() and not permit.is_symlink():
        return state, False
    if (not permit.is_file() or permit.is_symlink()
            or not 0 < permit.stat().st_size <= 4096):
        raise InputError("PAPER_COMM_RELEASE_PERMIT_UNSAFE")
    try:
        record = json.loads(permit.read_text("utf-8-sig"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise InputError("PAPER_COMM_RELEASE_PERMIT_UNSAFE") from exc
    if (type(record) is not dict or set(record) != EXPECTED_KEYS
            or record.get("schema") != SCHEMA
            or record.get("event_id") != EVENT
            or record.get("operator_approval") != APPROVAL
            or type(record.get("created_epoch_pc_unattested")) is not int
            or type(record.get("journal_cycles")) is not int
            or type(record.get("last_quote_epoch")) is not int
            or type(record.get("last_observed_mt4_epoch")) is not int
            or record.get("permit_sha256") != runtime._digest(
                {k: v for k, v in record.items() if k != "permit_sha256"})):
        raise InputError("PAPER_COMM_RELEASE_PERMIT_TAMPERED")
    age = int(now.timestamp()) - record["created_epoch_pc_unattested"]
    if not 0 <= age <= MAX_PERMIT_AGE:
        raise InputError("PAPER_COMM_RELEASE_PERMIT_EXPIRED")
    _validate_current_state(state)
    if (record["journal_cycles"] != state["cycle_number"]
            or record["journal_head_sha256"] != head
            or record["last_quote_epoch"] != state["last_quote_epoch"]):
        raise InputError("PAPER_COMM_RELEASE_JOURNAL_HEAD_MISMATCH")
    _fresh_observation(quote, state, now)
    if (quote["capture_epoch"] <= record["last_observed_mt4_epoch"]
            or quote["capture_epoch"] <= state["last_quote_epoch"]):
        # Wait for a strictly new quote; do not clear a latch on stale data.
        return state, False
    candidate = dict(state)
    candidate["communication_latched"] = False
    candidate["manual_comm_release_sha256"] = record["permit_sha256"]
    return candidate, True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stage ONE virtual-only manual communication release")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--mt4-files", required=True, type=Path)
    parser.add_argument("--operator-approval", default="")
    args = parser.parse_args(argv)
    try:
        result = stage(args.state_root, args.mt4_files,
                       operator_approval=args.operator_approval)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, OverflowError):
        print(json.dumps({
            "status": "PAPER_COMM_RELEASE_STAGING_FAIL_CLOSED_NO_GO",
            "communication_latch_cleared": False,
            "new_virtual_entries_permitted": False,
            "new_paid_calls_permitted": False,
            "broker_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
