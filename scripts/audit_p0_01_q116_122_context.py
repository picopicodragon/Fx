"""Local-only Q116-Q122 conversation context audit (no raw text output or writes).

A reference to an earlier question is only a human-review lead, not a
correction, acceptance, or safety approval. Other conversations and later
messages outside this export are not covered.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.review_unmatched_decisions import (
    context_question_hints,
    original_chat,
    parts_text,
    preceding_assistant,
    question_in_user_message,
)

TARGETS = tuple(f"Q{n}" for n in range(116, 123))
CHANGE_WORDS = ("修正", "訂正", "変更", "撤回", "追加", "補足", "上書き", "取り消", "再決定")


def user_nodes(mapping: dict) -> list[dict]:
    rows = []
    for key, node in mapping.items():
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
        rows.append({
            "node_key": key,
            "text": user_text,
            "qid": question_in_user_message(user_text),
            "time": message.get("create_time"),
        })
    return rows


def chain(mapping: dict, key: str) -> set[str] | None:
    """Parent-chain membership with cycle and missing-parent detection."""
    if not isinstance(key, str) or key not in mapping:
        return None
    visited: set[str] = set()
    current = key
    for _ in range(len(mapping) + 1):
        if current in visited:
            return None
        node = mapping.get(current)
        if not isinstance(node, dict):
            return None
        visited.add(current)
        parent = node.get("parent")
        if parent is None:
            return visited
        if not isinstance(parent, str) or parent not in mapping:
            return None
        current = parent
    return None


def q_reference(text: str, question: str) -> bool:
    n = int(question[1:])
    # Prevent Q116 matching Q1160 and permit Japanese/ASCII forms.
    return bool(re.search(
        rf"第\s*{n}\s*問|(?<![A-Za-z0-9_])Q\s*{n}(?![0-9])",
        text,
        flags=re.IGNORECASE,
    ))


def later_than(row: dict, anchor: dict) -> bool | None:
    t1, t0 = row["time"], anchor["time"]
    if not isinstance(t1, (int, float)) or isinstance(t1, bool):
        return None
    if not isinstance(t0, (int, float)) or isinstance(t0, bool):
        return None
    if t1 == t0:
        return None
    return t1 > t0


def build_report(data: object, conversation_id: str) -> list[dict]:
    mapping = original_chat(data, conversation_id)
    conversations = data.get("conversations") if isinstance(data, dict) else data
    selected = next(c for c in conversations if isinstance(c, dict) and c.get("id") == conversation_id)
    current_node = selected.get("current_node")
    active_chain = chain(mapping, current_node) if current_node else None
    rows = user_nodes(mapping)
    result = []
    for q in TARGETS:
        matches = [row for row in rows if row["qid"] == q]
        if len(matches) != 1:
            result.append({
                "question_id": q, "explicit": len(matches),
                "prompt_hint": "REVIEW_REQUIRED", "active_branch": "UNDETERMINED",
                "later_references": "N/A", "change_word_references": "N/A",
                "later_unlabeled_hints": "N/A", "order_uncertain_refs": "N/A"
            })
            continue
        anchor = matches[0]
        context = preceding_assistant(mapping, anchor["node_key"])
        hints = context_question_hints(context["text"]) if context else []
        if active_chain is None:
            active_status = "UNKNOWN"
        else:
            active_status = "YES" if anchor["node_key"] in active_chain else "NO"
        references = 0
        change_references = 0
        unlabeled_hints = 0
        uncertain = 0
        for row in rows:
            if row is anchor:
                continue
            order = later_than(row, anchor)
            if order is False:
                continue
            has_reference = q_reference(row["text"], q)
            if order is None:
                if has_reference:
                    uncertain += 1
                continue
            if has_reference:
                references += 1
                if any(keyword in row["text"] for keyword in CHANGE_WORDS):
                    change_references += 1
            if row["qid"] is None:
                previous = preceding_assistant(mapping, row["node_key"])
                if previous and q in context_question_hints(previous["text"]):
                    unlabeled_hints += 1
        result.append({
            "question_id": q, "explicit": 1,
            "prompt_hint": "YES" if q in hints else "NO_OR_UNCLEAR",
            "active_branch": active_status,
            "later_references": references,
            "change_word_references": change_references,
            "later_unlabeled_hints": unlabeled_hints,
            "order_uncertain_refs": uncertain
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Q116-Q122 context audit; prints counts only")
    parser.add_argument("--input", required=True)
    parser.add_argument("--conversation-id", required=True)
    args = parser.parse_args()
    inp = Path(args.input).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    if inp == root or root in inp.parents:
        parser.error("Private export must be stored outside the Fx repository")
    if not inp.is_file():
        parser.error("Export JSON does not exist")
    try:
        data = json.loads(inp.read_text(encoding="utf-8-sig"))
        rows = build_report(data, args.conversation_id)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    print("Q     Explicit PromptHint   ActiveBranch LaterRefs ChangeRefs UnlabeledHints OrderUnknown")
    for r in rows:
        print(
            f'{r["question_id"]:<5} {r["explicit"]:>8} {r["prompt_hint"]:<12} '
            f'{r["active_branch"]:<12} {str(r["later_references"]):>9} '
            f'{str(r["change_word_references"]):>10} '
            f'{str(r["later_unlabeled_hints"]):>14} '
            f'{str(r["order_uncertain_refs"]):>12}'
        )
    print("Reference/hint counts are leads only, not verified amendments.")
    print("Checks one conversation and one export; cannot exclude changes elsewhere or later.")
    print("No private text printed, no files written, no network, no safety approvals.")


if __name__ == "__main__":
    main()
