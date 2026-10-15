"""Q110 acceptance registry consistency checks (not human-authentication)."""
from __future__ import annotations

import json
from pathlib import Path

STATES = {"NOT_STARTED", "IN_PROGRESS", "TESTED", "ACCEPTED", "BLOCKED"}


def check_registry(doc: object) -> list[str]:
    if not isinstance(doc, dict):
        return ["registry must be an object"]
    errors: list[str] = []
    if doc.get("schema_version") != 1:
        errors.append("unsupported schema_version")
    maps: dict[str, dict[str, dict]] = {}
    for kind in ("tasks", "modules", "phases"):
        items = doc.get(kind)
        if not isinstance(items, list):
            errors.append(f"{kind} must be a list")
            continue
        result: dict[str, dict] = {}
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{kind}: item must be an object")
                continue
            ident = item.get("id")
            status = item.get("status")
            if not isinstance(ident, str) or not ident.strip() or ident in result:
                errors.append(f"{kind}: invalid/duplicate id {ident!r}")
                continue
            result[ident] = item
            if status not in STATES:
                errors.append(f"{kind}/{ident}: invalid status {status!r}")
            evidence = item.get("evidence", [])
            if not isinstance(evidence, list) or any(not isinstance(x, str) or not x.strip() for x in evidence):
                errors.append(f"{kind}/{ident}: evidence must be list of nonblank references")
            elif status in ("TESTED", "ACCEPTED") and not evidence:
                errors.append(f"{kind}/{ident}: TESTED/ACCEPTED requires evidence")
        maps[kind] = result

    tasks = maps.get("tasks", {})
    modules = maps.get("modules", {})
    phases = maps.get("phases", {})

    def approval_present(item: dict) -> bool:
        approval = item.get("approval")
        return isinstance(approval, dict) and all(
            isinstance(approval.get(name), str) and approval[name].strip()
            for name in ("actor", "approved_at", "decision_ref")
        )

    for ident, task in tasks.items():
        if not isinstance(task.get("spec_ids"), list) or not task["spec_ids"]:
            errors.append(f"tasks/{ident}: missing spec_ids")
        if not isinstance(task.get("module_id"), str) or task["module_id"] not in modules:
            errors.append(f"tasks/{ident}: unknown module_id")

    for ident, module in modules.items():
        ids = module.get("task_ids")
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            errors.append(f"modules/{ident}: task_ids must be a list")
            continue
        for child in ids:
            if child not in tasks:
                errors.append(f"modules/{ident}: unknown task {child}")
            elif tasks[child].get("module_id") != ident:
                errors.append(f"modules/{ident}: task {child} points to different module")
        if module.get("status") == "ACCEPTED":
            if not ids or any(child not in tasks or tasks[child].get("status") != "ACCEPTED" for child in ids):
                errors.append(f"modules/{ident}: cannot accept before every task is accepted")
            if module.get("safety_critical") is True and not approval_present(module):
                errors.append(f"modules/{ident}: human approval required for safety-critical module")

    for ident, phase in phases.items():
        ids = phase.get("module_ids")
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            errors.append(f"phases/{ident}: module_ids must be a list")
            continue
        for child in ids:
            if child not in modules:
                errors.append(f"phases/{ident}: unknown module {child}")
        if phase.get("status") == "ACCEPTED":
            if not ids or any(child not in modules or modules[child].get("status") != "ACCEPTED" for child in ids):
                errors.append(f"phases/{ident}: cannot accept before every module is accepted")
            if not approval_present(phase):
                errors.append(f"phases/{ident}: human approval required")
    return errors


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "acceptance_registry.json"
    if not path.is_file():
        raise SystemExit("Missing specs/acceptance_registry.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Invalid acceptance registry: {exc}") from exc
    errors = check_registry(data)
    if errors:
        raise SystemExit("Acceptance check FAILED:\n" + "\n".join(f"- {error}" for error in errors))
    print("Q110 three-level acceptance registry: PASS (not proof of safety or human identity)")


if __name__ == "__main__":
    main()
