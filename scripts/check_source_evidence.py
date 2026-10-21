"""Q113 evidence manifest checks.

Structural checks only. Cannot independently authenticate the original chat,
inspect the user's local archive, or certify redaction quality.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ALLOWED_SOURCES = {"ORIGINAL", "SUMMARY_ONLY", "UNAVAILABLE", "DERIVED"}
ALLOWED_VERIFICATION = {"DIRECT_CHAT", "LOCAL_ARCHIVE", "PENDING", "STANDING_USER_DIRECTIVE_PLUS_AI_RECOMMENDATION"}
ALLOWED_ARCHIVES = {"PENDING_LOCAL_ARCHIVE", "CONFIRMED_LOCAL_ARCHIVE"}
ALLOWED_REVIEW = {"REVIEWED_FOR_GITHUB", "NOT_REVIEWED"}


def audit(root: Path, data: object) -> list[str]:
    if not isinstance(data, dict):
        return ["manifest must be an object"]
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    records = data.get("records")
    if not isinstance(records, list):
        return errors + ["records must be an array"]
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            errors.append("each record must be an object")
            continue
        qid = record.get("question_id")
        if not isinstance(qid, str) or not re.fullmatch(r"Q[1-9][0-9]*", qid) or qid in seen:
            errors.append(f"invalid/duplicate question_id: {qid!r}")
            continue
        seen.add(qid)
        source = record.get("source_kind")
        verification = record.get("verification")
        archive = record.get("archive_locator_status")
        reviewed = record.get("confidentiality_review")
        locator = record.get("source_locator")
        path = record.get("excerpt_path")
        if source not in ALLOWED_SOURCES:
            errors.append(f"{qid}: invalid source_kind")
        if verification not in ALLOWED_VERIFICATION:
            errors.append(f"{qid}: invalid verification")
        if archive not in ALLOWED_ARCHIVES:
            errors.append(f"{qid}: invalid archive_locator_status")
        if reviewed not in ALLOWED_REVIEW:
            errors.append(f"{qid}: invalid confidentiality_review")
        if not isinstance(record.get("owner_approved_for_safety"), bool):
            errors.append(f"{qid}: owner_approved_for_safety must be boolean")
        if record.get("owner_approved_for_safety") is True:
            errors.append(f"{qid}: archive evidence cannot act as a safety implementation approval")
        if source == "ORIGINAL":
            if verification not in {"DIRECT_CHAT", "LOCAL_ARCHIVE"}:
                errors.append(f"{qid}: ORIGINAL requires actual direct verification")
            if not isinstance(locator, str) or not locator.strip():
                errors.append(f"{qid}: ORIGINAL requires source_locator")
        # Q199+: derived design recommendations are NOT direct user answers.
        if source == "DERIVED":
            if verification != "STANDING_USER_DIRECTIVE_PLUS_AI_RECOMMENDATION":
                errors.append(f"{qid}: DERIVED must identify the standing user directive plus AI recommendation")
            if int(qid[1:]) < 199:
                errors.append(f"{qid}: DERIVED source is only allowed after the standing policy")
            if not isinstance(locator, str) or "standing_recommendation_policy.md" not in locator:
                errors.append(f"{qid}: DERIVED must reference the standing policy provenance")
        elif verification == "STANDING_USER_DIRECTIVE_PLUS_AI_RECOMMENDATION":
            errors.append(f"{qid}: standing directive verification requires DERIVED source_kind")
        if verification == "LOCAL_ARCHIVE" and archive != "CONFIRMED_LOCAL_ARCHIVE":
            errors.append(f"{qid}: local archive verification needs confirmed archive")
        if not isinstance(path, str) or not re.fullmatch(r"specs/source_excerpts/Q[1-9][0-9]*\.md", path):
            errors.append(f"{qid}: excerpt_path must be specs/source_excerpts/Qxxx.md")
            continue
        if path != f"specs/source_excerpts/{qid}.md":
            errors.append(f"{qid}: excerpt filename does not match question_id")
            continue
        excerpt_file = root / path
        if not excerpt_file.is_file():
            errors.append(f"{qid}: referenced excerpt file is missing")
            continue
        excerpt_text = excerpt_file.read_text(encoding="utf-8")
        if source == "DERIVED" and (
            "推奨" not in excerpt_text
            or "個別回答したものではない" not in excerpt_text
        ):
            errors.append(f"{qid}: DERIVED excerpt must distinguish AI recommendation from direct user answer")
        if qid not in excerpt_text:
            errors.append(f"{qid}: excerpt file does not mention its question_id")
        if reviewed != "REVIEWED_FOR_GITHUB":
            errors.append(f"{qid}: excerpt must be reviewed for confidentiality before GitHub")
    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = root / "specs" / "source_evidence.json"
    if not manifest.is_file():
        raise SystemExit("Missing specs/source_evidence.json")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    problems = audit(root, data)
    if problems:
        raise SystemExit("Q113 evidence audit FAILED:\n" + "\n".join(f"- {x}" for x in problems))
    print("Q113 source excerpt registry: PASS (structural validation only; full local archive pending)")


if __name__ == "__main__":
    main()
