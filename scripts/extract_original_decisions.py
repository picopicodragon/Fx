"""Q114: Extract unreviewed *candidate* decision quotes from local ChatGPT data.

No web access, no GitHub writes, no model interpretation, no automatic approvals.
The ChatGPT export structure may vary: inspect real files before relying on it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

DECISION = re.compile(r"^\s*第\s*(\d{1,3})\s*問\s*(?:は|[:：])", re.MULTILINE)
ALT_DECISION = re.compile(r"^\s*Q\s*([1-9]\d{0,2})\s*[:：]", re.MULTILINE)


def detect_question(message: str) -> str | None:
    """Return ID only when explicitly identified in a decision message."""
    for pattern in (DECISION, ALT_DECISION):
        match = pattern.search(message)
        if match:
            return f"Q{int(match.group(1))}"
    return None


def export_messages(data: object, conversation_id: str) -> list[dict]:
    """Select only user-authored text from one explicitly selected conversation.

    Conversation exports can contain alternate edited-message branches; duplicates
    remain candidates requiring human review, never automatic approval.
    """
    if isinstance(data, dict) and isinstance(data.get("conversations"), list):
        data = data["conversations"]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of exported conversations")
    conversations = [
        entry for entry in data
        if isinstance(entry, dict) and entry.get("id") == conversation_id
    ]
    if len(conversations) != 1:
        raise ValueError("Expected exactly one conversation matching --conversation-id")
    conversation = conversations[0]
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("Selected conversation has no supported mapping object")

    rows = []
    for index, (node_key, node) in enumerate(mapping.items()):
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        if (message.get("author") or {}).get("role") != "user":
            continue
        content = message.get("content")
        parts = content.get("parts", []) if isinstance(content, dict) else []
        if not isinstance(parts, list):
            continue
        text = "\n".join(part for part in parts if isinstance(part, str)).strip()
        if not text:
            continue
        rows.append({
            "text": text,
            "message_id": message.get("id") or node_key,
            "create_time": message.get("create_time"),
            "conversation_id": conversation_id,
            "_position": index,
        })
    rows.sort(key=lambda item: (
        item["create_time"] is None,
        item["create_time"] if isinstance(item["create_time"], (int, float)) else float("inf"),
        item["_position"],
    ))
    for row in rows:
        row.pop("_position")
    return rows


def find_candidates(messages: list[dict]) -> tuple[list[dict], int]:
    candidates = []
    unmatched = 0
    for row in messages:
        qid = detect_question(row["text"])
        if not qid:
            unmatched += 1
            continue
        candidates.append({
            "question_id": qid,
            "user_text": row["text"],
            "message_id": row.get("message_id"),
            "conversation_id": row.get("conversation_id"),
            "create_time": row.get("create_time"),
            "status": "CANDIDATE_NOT_VERIFIED",
            "safe_for_github": False,
            "owner_approved_for_safety": False,
        })
    return candidates, unmatched


def build_result(raw: bytes, mode: str, conversation_id: str | None,
                 question: str | None) -> dict:
    if mode == "export":
        if not conversation_id:
            raise ValueError("--conversation-id is required for an export")
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Invalid UTF-8 JSON export") from exc
        messages = export_messages(parsed, conversation_id)
    else:
        if not question or not re.fullmatch(r"Q[1-9]\d{0,2}", question):
            raise ValueError("--question Qxxx is required for a manual user-message text")
        text = raw.decode("utf-8-sig").strip()
        if not text:
            raise ValueError("The user-message text is empty")
        detected = detect_question(text)
        if detected and detected != question:
            raise ValueError(f"Text refers to {detected}, not requested {question}")
        messages = [{
            "text": text,
            "message_id": None,
            "conversation_id": None,
            "create_time": None,
        }]
    candidates, unmatched = find_candidates(messages)
    if mode == "manual":
        candidates = [{
            "question_id": question,
            "user_text": messages[0]["text"],
            "message_id": None,
            "conversation_id": None,
            "create_time": None,
            "status": "CANDIDATE_NOT_VERIFIED",
            "safe_for_github": False,
            "owner_approved_for_safety": False,
        }]
        unmatched = 0
    counts: dict[str, int] = {}
    for item in candidates:
        qid = item["question_id"]
        counts[qid] = counts.get(qid, 0) + 1
    return {
        "schema_version": 1,
        "source_file_sha256": hashlib.sha256(raw).hexdigest(),
        "mode": mode,
        "conversation_id": conversation_id,
        "candidate_count": len(candidates),
        "unmatched_user_messages": unmatched,
        "duplicate_question_ids": sorted(q for q, count in counts.items() if count > 1),
        "notes": [
            "This is a local candidate extraction, not verified source evidence.",
            "Unmatched responses such as 'CでOK' cannot be assigned automatically.",
            "Alternate edited-message branches may appear in exports; review duplicates.",
            "Review context, completeness, secrets, and original local archive before GitHub registration.",
        ],
        "candidates": candidates,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate local unverified FX decision candidates")
    ap.add_argument("--input", required=True, help="Local conversation JSON or user-only UTF-8 text")
    ap.add_argument("--format", choices=("export", "manual"), required=True)
    ap.add_argument("--conversation-id", help="Exact ID of target conversation within an export")
    ap.add_argument("--question", help="Required with --format manual, e.g., Q114")
    ap.add_argument("--out-dir", required=True, help="Local output directory OUTSIDE the repository")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    inp = Path(args.input).expanduser().resolve()
    dest = Path(args.out_dir).expanduser().resolve()
    if dest == root or root in dest.parents:
        ap.error("Output must be outside the Git repository")
    if not inp.is_file():
        ap.error("Input file does not exist")
    out = dest / "candidate_decisions.json"
    if out.exists():
        ap.error("Candidate output exists; use a new directory to avoid accidental overwrite")
    try:
        result = build_result(inp.read_bytes(), args.format, args.conversation_id, args.question)
    except (ValueError, UnicodeError) as exc:
        ap.error(str(exc))
    dest.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {result['candidate_count']} unverified candidates to {out}")
    print("No source extract or safety approval was committed to GitHub.")


if __name__ == "__main__":
    main()
