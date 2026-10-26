"""Q109 baseline: fail if critical trading code lacks a mapped Python test.

This gate checks *registrations*, not semantic safety or MQL4 execution.
"""
from __future__ import annotations

import json
from pathlib import Path

CODE_SUFFIXES = {".py", ".mq4", ".mqh"}
PROTECTED_PREFIXES = (
    "src/risk/", "src/safety/", "src/execution/",
    "src/recovery/", "src/ai/approval/", "mt4/",
)


def audit(root: Path) -> list[str]:
    errors: list[str] = []
    registry = root / "specs" / "traceability.json"
    if not registry.is_file():
        return ["Missing specs/traceability.json"]
    try:
        document = json.loads(registry.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return [f"Invalid traceability registry: {exc}"]
    if document.get("schema_version") != 1:
        errors.append("Unsupported traceability registry schema_version")
    groups = document.get("groups")
    if not isinstance(groups, list) or not groups:
        return errors + ["Traceability registry requires groups"]

    source_files = [
        file.relative_to(root).as_posix()
        for directory in ("src", "mt4")
        if (root / directory).is_dir()
        for file in (root / directory).rglob("*")
        if file.is_file() and file.suffix.lower() in CODE_SUFFIXES
    ]
    protected = {path for path in source_files if path.startswith(PROTECTED_PREFIXES)}
    covered: set[str] = set()
    seen: set[str] = set()
    # A read-only MT4 probe is still protected code. Assign each source to
    # the most-specific registered prefix, so a narrow, tested read-only group
    # does not activate the broad, still-unimplemented trading-execution group.
    # This does NOT change PROTECTED_PREFIXES or exempt any new MT4 files.
    registered_prefixes = [
        prefix
        for candidate in groups if isinstance(candidate, dict)
        for prefix in candidate.get("prefixes", [])
        if isinstance(prefix, str)
    ]

    for group in groups:
        if not isinstance(group, dict):
            errors.append("Registry group must be an object")
            continue
        ident = group.get("group_id")
        specs = group.get("spec_ids")
        prefixes = group.get("prefixes")
        tests = group.get("tests")
        status = group.get("status")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            errors.append(f"Missing/duplicate group_id: {ident!r}")
        else:
            seen.add(ident)
        if not isinstance(specs, list) or not specs or any(
            not isinstance(spec, str) or not spec.startswith("Q") for spec in specs
        ):
            errors.append(f"{ident}: invalid spec_ids")
        if not isinstance(prefixes, list) or not prefixes or any(
            not isinstance(prefix, str) or not prefix.startswith(PROTECTED_PREFIXES)
            or not prefix.endswith("/") or ".." in prefix
            for prefix in prefixes
        ):
            errors.append(f"{ident}: invalid critical source prefixes")
            continue
        if not isinstance(tests, list) or any(not isinstance(test, str) for test in tests):
            errors.append(f"{ident}: invalid tests list")
            continue
        if status not in ("planned", "active"):
            errors.append(f"{ident}: status must be planned or active")
        matching = [
            path for path in protected
            if any(
                path.startswith(prefix)
                and not any(
                    path.startswith(more_specific) and len(more_specific) > len(prefix)
                    for more_specific in registered_prefixes
                )
                for prefix in prefixes
            )
        ]
        covered.update(matching)
        if matching and status != "active":
            errors.append(f"{ident}: critical code exists but group is not active: {matching}")
        if matching and not tests:
            errors.append(f"{ident}: missing tests for critical code: {matching}")
        for test in tests:
            if not test.startswith("tests/test") or not test.endswith(".py") or ".." in test:
                errors.append(f"{ident}: test must be a Python tests/test*.py file: {test}")
            elif not (root / test).is_file():
                errors.append(f"{ident}: registered test file is missing: {test}")

    for path in sorted(protected - covered):
        errors.append(f"Unregistered safety-critical source: {path}")
    return errors


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    errors = audit(root)
    if errors:
        raise SystemExit("Traceability check FAILED:\n" + "\n".join(f"- {e}" for e in errors))
    print("Q109 safety-critical traceability registry: PASS (not a trading-safety certification)")


if __name__ == "__main__":
    main()
