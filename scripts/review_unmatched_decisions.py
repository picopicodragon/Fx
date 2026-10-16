"""Offline review of user replies not assigned an explicit Q number.

Q115 follow-up. The tool NEVER turns an assistant's Q prompt into an
approved decision; it emits review hints and raw surrounding text locally.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Match the exact recognition rules of extract_original_decisions.py.
USER_Q = (
    re.compile(r"^\s*第\s*(\d{1,3})\s*問\s*(?:は|[:：])", re.MULTILINE),
    re.compile(r"^\s*Q\s*([1-9]\d{0,2})\s*[:：]", re.MULTILINE),
)
ASSISTANT_Q = re.compile(r"第\s*([1-9]\d{0,2})\s*問|(?<![A-Za-z0-9_])Q\s*([1-9]\d{0,2})(?![0-9])", re.IGNORECASE)


def question_in_user_message(text: str) -> str | None:
    for pattern in USER_Q:
        hit = pattern.search(text)
        if hit:
            return f"Q{int(hit.group(1))}"
    return None


def parts_text(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return ""
    return "\n".join(part for part in parts if isinstance(part, str)).strip()


def original_chat(data: object, conversation_id: str) -> dict:
    if isinstance(data, dict) and isinstance(data.get("conversations"), list):
        data = data["conversations"]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of exported conversations")
    choices = [
        item for item in data
        if isinstance(item, dict) and item.get("id") == conversation_id
    ]
    if len(choices) != 1:
        raise ValueError("Expected exactly one conversation matching --conversation-id")
    mapping = choices[0].get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("Selected conversation has no supported mapping object")
    return mapping


def preceding_assistant(mapping: dict, node_key: str) -> dict | None:
    """Use parent chain, not time sorting or arbitrary adjacent nodes."""
    node = mapping.get(node_key)
    parent = node.get("parent") if isinstance(node, dict) else None
    seen = {node_key}
    for _ in range(100):
        if not isinstance(parent, str) or parent in seen:
            return None
        seen.add(parent)
        ancestor = mapping.get(parent)
        if not isinstance(ancestor, dict):
            return None
        message = ancestor.get("message")
        if isinstance(message, dict):
            author = message.get("author")
            if isinstance(author, dict) and author.get("role") == "assistant":
                raw = parts_text(message)
                if raw:
                    return {"message_id": message.get("id") or parent, "text": raw}
        parent = ancestor.get("parent")
    return None


def context_question_hints(text: str) -> list[str]:
    """Potential IDs in assistant's text. NEVER auto-bind a user reply."""
    ids: list[str] = []
    for match in ASSISTANT_Q.finditer(text):
        n = int(match.group(1) or match.group(2))
        q = f"Q{n}"
        if q not in ids:
            ids.append(q)
    return ids


def make_review(mapping: dict, conversation_id: str, max_q: int = 115) -> dict:
    unmatched = []
    explicit_ids = set()
    user_messages = 0
    for key, node in mapping.items():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        author = message.get("author")
        if not isinstance(author, dict) or author.get("role") != "user":
            continue
        text = parts_text(message)
        if not text:
            continue
        user_messages += 1
        explicit = question_in_user_message(text)
        if explicit:
            explicit_ids.add(explicit)
            continue
        context = preceding_assistant(mapping, key)
        # List ALL IDs mentioned; even the most recent is just a hint.
        hints = context_question_hints(context["text"]) if context else []
        unmatched.append({
            "user_message_id": message.get("id") or key,
            "user_text": text,
            "create_time": message.get("create_time"),
            "preceding_assistant_message_id": context["message_id"] if context else None,
            "preceding_assistant_text": context["text"] if context else None,
            "possible_question_ids_from_assistant": hints,
            "review_status": "UNASSIGNED_REQUIRES_HUMAN_CONTEXT_REVIEW",
            "assigned_question_id": None,
            "safe_for_github": False,
            "owner_approved_for_safety": False,
        })

    return {
        "schema_version": 1,
        "conversation_id": conversation_id,
        "total_text_user_messages": user_messages,
        "explicitly_recognized_unique_questions": len(explicit_ids),
        "unmatched_user_messages": len(unmatched),
        "missing_question_ids_in_this_conversation": [
            f"Q{i}" for i in range(1, max_q + 1) if f"Q{i}" not in explicit_ids
        ],
        "notes": [
            "Assistant question numbers are context hints only; a response such as C does not verify any Q number.",
            "The conversation may contain branches and edited messages. Inspect the original message chain.",
            "Missing IDs may belong to other conversations; do not invent their original user text.",
            "No candidate is approved or uploaded to GitHub. This local file may contain sensitive chat data.",
        ],
        "unmatched": unmatched,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review unmatched user replies with their parent-chain assistant context"
    )
    parser.add_argument("--input", required=True, help="Local conversations.json")
    parser.add_argument("--conversation-id", required=True, help="Exact target conversation ID")
    parser.add_argument("--out-dir", required=True, help="Local output folder OUTSIDE Fx repository")
    parser.add_argument("--max-question", type=int, default=115, help="Maximum expected Q number")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source = Path(args.input).expanduser().resolve()
    target = Path(args.out_dir).expanduser().resolve()
    if target == root or root in target.parents:
        parser.error("Output must be outside the Fx Git repository")
    if not source.is_file():
        parser.error("Input file does not exist")
    if args.max_question < 1 or args.max_question > 999:
        parser.error("--max-question must be between 1 and 999")
    output = target / "unmatched_review.json"
    if output.exists():
        parser.error("Output exists; choose a fresh output directory")
    try:
        data = json.loads(source.read_text(encoding="utf-8-sig"))
        mapping = original_chat(data, args.conversation_id)
        report = make_review(mapping, args.conversation_id, args.max_question)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    target.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Unmatched user messages: {report['unmatched_user_messages']}")
    print(f"Missing explicit Q IDs: {len(report['missing_question_ids_in_this_conversation'])}")
    print(f"Wrote local review only: {output}")
    print("All Q hints require human verification. No GitHub uploads or safety approvals.")


if __name__ == "__main__":
    main()
