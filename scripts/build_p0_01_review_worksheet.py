"""Build a private, unapproved review worksheet for P0-01 (Q5 through Q14).

All source text stays on the user's PC. No network, broker, order, or GitHub write.
This tool NEVER infers a binding from an assistant prompt or grants approvals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.review_unmatched_decisions import (
    context_question_hints,
    original_chat,
    parts_text,
    preceding_assistant,
    question_in_user_message,
)

TARGETS = tuple(f"Q{i}" for i in range(5, 15))


def build_worksheet(data: object, conversation_id: str, source_sha256: str) -> dict:
    mapping = original_chat(data, conversation_id)
    questions = {
        qid: {
            "question_id": qid,
            "explicit": [],
            "context_hints_unassigned": [],
            "review_status": "OWNER_CONTEXT_REVIEW_REQUIRED",
            "selected_user_message_id": None,
            "owner_approved_for_safety": False,
        }
        for qid in TARGETS
    }
    for node_key, node in mapping.items():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        if (message.get("author") or {}).get("role") != "user":
            continue
        user_text = parts_text(message)
        if not user_text:
            continue
        explicit = question_in_user_message(user_text)
        context = preceding_assistant(mapping, node_key)
        hints = context_question_hints(context["text"]) if context else []
        base = {
            "user_message_id": message.get("id") or node_key,
            "user_text": user_text,
            "user_created_at": message.get("create_time"),
            "preceding_assistant_message_id": context["message_id"] if context else None,
            "preceding_assistant_text": context["text"] if context else None,
            "assistant_question_hints": hints,
            "status": "UNVERIFIED_LOCAL_EVIDENCE",
        }
        if explicit:
            if explicit in questions:
                questions[explicit]["explicit"].append(
                    {**base, "identification": "USER_EXPLICIT_QUESTION"}
                )
            # A labelled response for a different Q is never re-assigned.
            continue
        for qid in TARGETS:
            if qid in hints:
                questions[qid]["context_hints_unassigned"].append(
                    {**base, "identification": "ASSISTANT_CONTEXT_HINT_ONLY"}
                )
    return {
        "schema_version": 1,
        "plan_id": "P0-01",
        "conversation_id": conversation_id,
        "source_file_sha256": source_sha256,
        "worksheet_status": "LOCAL_OWNER_REVIEW_PENDING",
        "source_verified_against_spec": False,
        "implementation_approved": False,
        "owner_approved_for_safety": False,
        "notices": [
            "This report contains private conversation text. Keep OUTSIDE the Git repository.",
            "An assistant's preceding Q number is only a hint, not a confirmed answer.",
            "An explicitly Q-labelled user reply is still not verified against the original full context.",
            "Edited branches, truncated exports and later overrides must be checked manually.",
            "Do not upload full exports or worksheets or mark safety implementation approved.",
        ],
        "questions": list(questions.values()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create a local-only P0-01 worksheet for Q5-Q14 (not approvals)"
    )
    ap.add_argument("--input", required=True, help="Private conversations.json")
    ap.add_argument("--conversation-id", required=True, help="Exact FX conversation ID")
    ap.add_argument("--out-dir", required=True, help="Output outside Fx Git checkout")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    source = Path(args.input).expanduser().resolve()
    target = Path(args.out_dir).expanduser().resolve()
    if not source.is_file():
        ap.error("Input export file does not exist")
    if source == root or root in source.parents:
        ap.error("Private input must be outside the Git repository")
    if target == root or root in target.parents:
        ap.error("Worksheet output must be outside the Git repository")
    output = target / "p0_01_worksheet.json"
    if output.exists():
        ap.error("Worksheet output already exists; select a new output folder")
    try:
        raw = source.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
        worksheet = build_worksheet(
            data, args.conversation_id, hashlib.sha256(raw).hexdigest()
        )
    except (OSError, ValueError, UnicodeError) as exc:
        ap.error(str(exc))

    target.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as f:
        json.dump(worksheet, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("Q     Explicit    Context hints (NOT matched)")
    for q in worksheet["questions"]:
        print(
            f'{q["question_id"]:<5} {len(q["explicit"]):>8} '
            f'{len(q["context_hints_unassigned"]):>16}'
        )
    print("Review status: OWNER_CONTEXT_REVIEW_REQUIRED for every question.")
    print("Private worksheet saved outside Fx. No data uploaded or approved.")


if __name__ == "__main__":
    main()
