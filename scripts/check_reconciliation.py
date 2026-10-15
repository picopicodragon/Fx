"""Q112: inspect reconciliation evidence and approval invariants.

No automated content comparison or authentication is claimed.
"""
from __future__ import annotations

import json
from pathlib import Path

SOURCE_TYPES = {"ORIGINAL", "SUMMARY_ONLY", "UNAVAILABLE"}
COMPARE_STATES = {
    "NOT_REVIEWED", "MATCH", "DISCREPANCY", "OMISSION",
    "NEEDS_CLARIFICATION", "SOURCE_UNAVAILABLE", "RESOLVED"
}
SAFETY_IDS = {f"FX-SAF-{number:03d}" for number in range(1, 16)}


def check_reconciliation(data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["registry must be an object"]
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    items = data.get("items")
    if not isinstance(items, list):
        return errors + ["items must be a list"]
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("items must contain objects")
            continue
        ident = item.get("requirement_id")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            errors.append(f"invalid/duplicate requirement_id: {ident!r}")
            continue
        seen.add(ident)
        if item.get("source_kind") not in SOURCE_TYPES:
            errors.append(f"{ident}: invalid source_kind")
        if item.get("comparison_status") not in COMPARE_STATES:
            errors.append(f"{ident}: invalid comparison_status")
        questions = item.get("question_ids")
        if not isinstance(questions, list) or not questions or any(
            not isinstance(q, str) or not q.startswith("Q") or not q[1:].isdigit()
            for q in questions
        ):
            errors.append(f"{ident}: question_ids must be Q numbers")
        if not isinstance(item.get("safety_critical"), bool):
            errors.append(f"{ident}: safety_critical must be boolean")
        if not isinstance(item.get("implementation_approved"), bool):
            errors.append(f"{ident}: implementation_approved must be boolean")
        issues = item.get("issues")
        if not isinstance(issues, list) or any(not isinstance(x, str) for x in issues):
            errors.append(f"{ident}: issues must be string array")
        approval = item.get("owner_approval")
        if item.get("implementation_approved") is True:
            if item.get("source_kind") != "ORIGINAL":
                errors.append(f"{ident}: approval requires ORIGINAL source evidence")
            if item.get("comparison_status") not in ("MATCH", "RESOLVED"):
                errors.append(f"{ident}: approval requires MATCH/RESOLVED status")
            if not isinstance(item.get("source_reference"), str) or not item["source_reference"].strip():
                errors.append(f"{ident}: approval requires source_reference")
            if not isinstance(item.get("spec_reference"), str) or not item["spec_reference"].strip():
                errors.append(f"{ident}: approval requires spec_reference")
            if not isinstance(approval, dict) or any(
                not isinstance(approval.get(field), str) or not approval[field].strip()
                for field in ("approved_by", "approved_at", "decision_reference")
            ):
                errors.append(f"{ident}: approval requires human decision record")
            if issues:
                errors.append(f"{ident}: approved entry still has open issues")
        elif approval is not None:
            errors.append(f"{ident}: approval record present but implementation_approved=false")
    for ident in sorted(SAFETY_IDS - seen):
        errors.append(f"Missing mandatory safety reconciliation: {ident}")
    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "specs" / "reconciliation_registry.json"
    if not path.is_file():
        raise SystemExit("Missing specs/reconciliation_registry.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = check_reconciliation(data)
    if problems:
        raise SystemExit("Reconciliation check FAILED:\n" + "\n".join(f"- {p}" for p in problems))
    print("Q112 reconciliation registry: PASS (record format only; original review NOT complete)")


if __name__ == "__main__":
    main()
