"""List conversation IDs/titles from a local ChatGPT export, no uploads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def list_conversations(data: object, title_filter: str = "") -> list[tuple[str, str]]:
    if isinstance(data, dict) and isinstance(data.get("conversations"), list):
        data = data["conversations"]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of exported conversations")
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        ident, title = item.get("id"), item.get("title")
        if isinstance(ident, str) and ident and isinstance(title, str):
            if title_filter.casefold() in title.casefold():
                result.append((ident, title))
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="List local ChatGPT export conversation IDs")
    ap.add_argument("--input", required=True, help="Path to extracted conversations.json")
    ap.add_argument("--filter", default="", help="Optional case-insensitive title filter")
    args = ap.parse_args()
    inp = Path(args.input).expanduser()
    if not inp.is_file():
        ap.error("Input JSON file not found")
    try:
        data = json.loads(inp.read_text(encoding="utf-8-sig"))
        conversations = list_conversations(data, args.filter)
    except (ValueError, UnicodeError) as exc:
        ap.error(str(exc))
    for ident, title in conversations:
        print(f"{ident}\t{title.replace(chr(9), ' ').replace(chr(10), ' ')}")
    print(f"Matched {len(conversations)} conversation(s). No files uploaded.")


if __name__ == "__main__":
    main()
