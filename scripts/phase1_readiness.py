"""Offline-only PHASE-1 evidence metadata audit.

Does not submit orders, validate identities, or grant any approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_IDS = {f"FX-SAF-{number:03d}" for number in range(1, 16)}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def audit(root: Path) -> dict[str, Any]:
    """Inspect metadata only. Human authorization is never inferred."""
    priority = load_json(root / "specs" / "source_review_priority.json")
    reconciliation = load_json(root / "specs" / "reconciliation_registry.json")
    acceptance = load_json(root / "specs" / "acceptance_registry.json")
    review_items, rec_items, phases = (
        priority.get("items"), reconciliation.get("items"), acceptance.get("phases")
    )
    if not isinstance(review_items, list) or not review_items:
        raise ValueError("Missing safety review items: fail closed")
    if not isinstance(rec_items, list) or not rec_items:
        raise ValueError("Missing reconciliation items: fail closed")
    if not isinstance(phases, list):
        raise ValueError("Missing phase acceptance records: fail closed")

    def keyed(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("requirement_id"), str):
                raise ValueError("Invalid requirement record: fail closed")
            key = item["requirement_id"]
            if key in result:
                raise ValueError("Duplicate requirement record: fail closed")
            result[key] = item
        return result

    reviewed = keyed(review_items)
    reconciled = keyed(rec_items)
    pending_source_ids = sorted(
        key for key in REQUIRED_IDS
        if key not in reviewed
        or reviewed[key].get("source_review") != "EXCERPT_VERIFIED"
        or reviewed[key].get("spec_comparison") != "COMPARISON_MATCHED"
        or reviewed[key].get("human_safety_approval") is not True
    )
    pending_reconciliation_ids = []
    for key in sorted(REQUIRED_IDS):
        item = reconciled.get(key)
        if item is None:
            pending_reconciliation_ids.append(key)
            continue
        approval = item.get("owner_approval")
        valid_approval_metadata = (
            isinstance(approval, dict)
            and all(isinstance(approval.get(name), str) and approval[name].strip()
                    for name in ("approved_by", "approved_at", "decision_reference"))
        )
        if (
            item.get("source_kind") != "ORIGINAL"
            or item.get("comparison_status") not in ("MATCH", "RESOLVED")
            or item.get("implementation_approved") is not True
            or not valid_approval_metadata
            or not isinstance(item.get("source_reference"), str)
            or not item["source_reference"].strip()
            or bool(item.get("issues"))
        ):
            pending_reconciliation_ids.append(key)
    phase1 = next(
        (item for item in phases
         if isinstance(item, dict) and item.get("id") == "PHASE-1"), None
    )
    return {
        "phase": "PHASE-1",
        "phase_status": phase1.get("status") if phase1 else "MISSING",
        "review_item_count": len(review_items),
        "pending_source_ids": pending_source_ids,
        "pending_reconciliation_ids": pending_reconciliation_ids,
        "evidence_metadata_complete": not pending_source_ids and not pending_reconciliation_ids,
        "safety_implementation_authorized": False,
        "ready_for_live_trading": False,
        "note": "Metadata inspection only. Human approval and safety validation are independent.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--require-evidence-complete", action="store_true")
    args = parser.parse_args()
    try:
        result = audit(args.root)
    except (ValueError, OSError) as exc:
        print(json.dumps({
            "evidence_metadata_complete": False,
            "safety_implementation_authorized": False,
            "ready_for_live_trading": False,
            "error": str(exc),
        }, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.require_evidence_complete and not result["evidence_metadata_complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
