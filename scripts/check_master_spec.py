"""Q111: Validate the 110-entry design decision index.

Checks indexing completeness only, not semantic correctness against chat history.
"""
from __future__ import annotations

import re
from pathlib import Path

ENTRY = re.compile(r"^\| Q([1-9]\d*) \|", re.MULTILINE)


def check_index(text: str, required_max: int = 110) -> list[str]:
    ids = [int(x) for x in ENTRY.findall(text)]
    errors: list[str] = []
    if len(ids) != required_max:
        errors.append(f"Expected {required_max} indexed decisions, found {len(ids)}")
    unique = set(ids)
    missing = sorted(set(range(1, required_max + 1)) - unique)
    if missing:
        errors.append(f"Missing Q numbers: {missing}")
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        errors.append(f"Duplicate Q numbers: {duplicates}")
    unexpected = sorted(unique - set(range(1, required_max + 1)))
    if unexpected:
        errors.append(f"Unexpected Q numbers: {unexpected}")
    if ids != sorted(ids):
        errors.append("Q numbers must appear in ascending order")
    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    index = root / "MASTER_SPEC.md"
    if not index.is_file():
        raise SystemExit("Missing MASTER_SPEC.md")
    errors = check_index(index.read_text(encoding="utf-8"))
    if errors:
        raise SystemExit("Master index check FAILED:\n" + "\n".join(f"- {e}" for e in errors))
    if not (root / "specs" / "safety_foundation.md").is_file():
        raise SystemExit("Missing safety requirements draft specs/safety_foundation.md")
    print("Q111: 110 decision IDs present; safety draft exists. Semantic verification still PENDING.")


if __name__ == "__main__":
    main()
