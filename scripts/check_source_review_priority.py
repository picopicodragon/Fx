"""Q115: validate the safety-critical original-record review queue.

Checks order, coverage and consistency with reconciliation; does NOT verify any
real ChatGPT export or constitute human approval.
"""
from __future__ import annotations

import json
from pathlib import Path

SAFETY_IDS = {f"FX-SAF-{i:03d}" for i in range(1, 16)}
REVIEW_STATUSES = {"PENDING_ORIGINAL", "EXCERPT_VERIFIED"}
COMPARE_STATUSES = {"NOT_REVIEWED", "DIFFERENCE_FOUND", "COMPARISON_MATCHED"}
CONFIDENTIALITY = {"NOT_REVIEWED", "REVIEWED_FOR_GITHUB"}


def audit(plan: object, reconciliation: object, evidence: object) -> list[str]:
    if not isinstance(plan, dict):
        return ["priority plan must be an object"]
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("decision_ref") != "Q115":
        errors.append("unsupported Q115 priority schema")
    batches, items = plan.get("batches"), plan.get("items")
    if not isinstance(batches, list) or not isinstance(items, list):
        return errors + ["batches and items must be lists"]
    if not isinstance(reconciliation, dict) or not isinstance(reconciliation.get("items"), list):
        return errors + ["missing reconciliation items"]
    if not isinstance(evidence, dict) or not isinstance(evidence.get("records"), list):
        return errors + ["missing source evidence records"]

    batch_ids = []
    grouped: set[str] = set()
    for i, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict):
            errors.append("batch must be an object")
            continue
        ident = batch.get("batch_id")
        if ident in batch_ids or not isinstance(ident, str):
            errors.append(f"duplicate/invalid batch id {ident}")
        batch_ids.append(ident)
        if batch.get("order") != i:
            errors.append(f"{ident}: batches must have sequential order")
        refs = batch.get("requirement_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{ident}: requirement_ids missing")
            continue
        for ref in refs:
            if ref in grouped:
                errors.append(f"{ident}: duplicate assigned requirement {ref}")
            grouped.add(ref)

    by_id = {}
    for item in items:
        if not isinstance(item, dict):
            errors.append("requirement items must be objects")
            continue
        ident = item.get("requirement_id")
        if not isinstance(ident, str) or ident in by_id:
            errors.append(f"duplicate/invalid requirement id {ident}")
            continue
        by_id[ident] = item
        if item.get("batch_id") not in batch_ids:
            errors.append(f"{ident}: invalid batch_id")
        if item.get("source_review") not in REVIEW_STATUSES:
            errors.append(f"{ident}: invalid source_review")
        if item.get("spec_comparison") not in COMPARE_STATUSES:
            errors.append(f"{ident}: invalid spec_comparison")
        if item.get("confidentiality_review") not in CONFIDENTIALITY:
            errors.append(f"{ident}: invalid confidentiality_review")
        if not isinstance(item.get("human_safety_approval"), bool):
            errors.append(f"{ident}: human_safety_approval must be boolean")
        refs = item.get("github_excerpt_refs")
        if not isinstance(refs, list) or any(not isinstance(r, str) for r in refs):
            errors.append(f"{ident}: github_excerpt_refs must be strings")
            refs = []
        issues = item.get("outstanding_issues")
        if not isinstance(issues, list) or any(not isinstance(s, str) for s in issues):
            errors.append(f"{ident}: outstanding_issues must be list of strings")

        if item.get("source_review") == "EXCERPT_VERIFIED":
            if not refs:
                errors.append(f"{ident}: verified excerpt requires evidence references")
            if item.get("confidentiality_review") != "REVIEWED_FOR_GITHUB":
                errors.append(f"{ident}: verified excerpt requires confidentiality review")
        if item.get("spec_comparison") == "COMPARISON_MATCHED" and item.get("source_review") != "EXCERPT_VERIFIED":
            errors.append(f"{ident}: cannot claim a match before original excerpts verified")

    if grouped != SAFETY_IDS or set(by_id) != SAFETY_IDS:
        errors.append("exact coverage of all 15 safety requirements is required")
    for batch in batches:
        if not isinstance(batch, dict) or not isinstance(batch.get("requirement_ids"), list):
            continue
        for ident in batch["requirement_ids"]:
            if ident in by_id and by_id[ident].get("batch_id") != batch.get("batch_id"):
                errors.append(f"{ident}: batch assignment mismatch")

    recon = {
        x.get("requirement_id"): x for x in reconciliation["items"]
        if isinstance(x, dict) and isinstance(x.get("requirement_id"), str)
    }
    ev = {
        x.get("question_id"): x for x in evidence["records"]
        if isinstance(x, dict) and isinstance(x.get("question_id"), str)
    }
    for ident, item in by_id.items():
        r = recon.get(ident)
        if r is None:
            errors.append(f"{ident}: missing reconciliation entry")
            continue
        if item.get("question_ids") != r.get("question_ids"):
            errors.append(f"{ident}: original question IDs conflict with reconciliation")
        if item.get("source_review") == "EXCERPT_VERIFIED":
            refs = item.get("question_ids") or []
            if any(q not in ev or ev[q].get("source_kind") != "ORIGINAL" for q in refs):
                errors.append(f"{ident}: at least one question has no verified original evidence")
        if item.get("human_safety_approval") is True:
            if (not r.get("implementation_approved")
                or not isinstance(r.get("owner_approval"), dict)
                or item.get("spec_comparison") != "COMPARISON_MATCHED"
                or item.get("outstanding_issues")):
                errors.append(f"{ident}: priority approval unsupported by reconciliation and resolved evidence")
        if r.get("implementation_approved") and not item.get("human_safety_approval"):
            errors.append(f"{ident}: reconciliation says approved but priority register disagrees")
    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    try:
        files = [
            json.loads((root / p).read_text(encoding="utf-8"))
            for p in (
                "specs/source_review_priority.json",
                "specs/reconciliation_registry.json",
                "specs/source_evidence.json",
            )
        ]
    except (OSError, ValueError) as e:
        raise SystemExit(f"Missing or invalid Q115 input: {e}") from e
    problems = audit(*files)
    if problems:
        raise SystemExit("Q115 priority validation FAILED:\n" + "\n".join(f"- {x}" for x in problems))
    print("Q115: 15 safety-source review entries registered, not yet original-verified or approved.")


if __name__ == "__main__":
    main()
