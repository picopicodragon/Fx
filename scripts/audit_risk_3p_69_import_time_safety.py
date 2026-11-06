"""Review import-time AST side effects in six already-selected pure mocks.

Covers module-body expressions, function decorators and default values,
not native extensions, imported dependencies or reflection. Checks public
repository Python source only; no executing source and no broker access.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from scripts import audit_risk_3p_56_static_offline_boundary as prior

ROOT = Path(__file__).resolve().parents[1]
TARGETS = prior.TARGETS


def inspect_source(source: object) -> list[str]:
    if type(source) is not str or not source.strip():
        return ["P69_EMPTY_OR_INVALID_SOURCE"]
    try:
        tree = ast.parse(source)
    except (SyntaxError, TypeError, ValueError, RecursionError):
        return ["P69_BAD_PYTHON_SYNTAX"]
    errors: list[str] = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.Pass)):
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (stmt.decorator_list or
                    any(isinstance(n, ast.Call)
                        for arg in list(stmt.args.defaults) + [
                            x for x in stmt.args.kw_defaults if x is not None]
                        for n in ast.walk(arg))):
                errors.append("P69_IMPORT_TIME_DECORATOR_OR_DEFAULT_CALL")
            continue
        if isinstance(stmt, ast.Assign):
            # One retained static regular-expression compilation used by
            # the synthetic hash validator. No general call is permitted.
            value = stmt.value
            allow_regex = (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and value.func.value.id == "re"
                and value.func.attr == "compile"
                and len(value.args) == 1
                and isinstance(value.args[0], ast.Constant)
                and type(value.args[0].value) is str
                and not value.keywords
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "HEX64"
            )
            if any(isinstance(n, ast.Call) for n in ast.walk(value)) and not (
                    allow_regex and sum(isinstance(n, ast.Call)
                                        for n in ast.walk(value)) == 1):
                errors.append("P69_IMPORT_TIME_INITIALIZER_EXECUTION")
            continue
        if isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None and any(
                    isinstance(n, ast.Call) for n in ast.walk(stmt.value)):
                errors.append("P69_IMPORT_TIME_INITIALIZER_EXECUTION")
            continue
        if isinstance(stmt, ast.Expr):
            if not (isinstance(stmt.value, ast.Constant)
                    and type(stmt.value.value) is str):
                errors.append("P69_IMPORT_TIME_EXPRESSION")
            continue
        errors.append("P69_UNREVIEWED_IMPORT_TIME_STATEMENT")
    return list(dict.fromkeys(errors))


def audit(root: Path = ROOT, overrides: dict | None = None) -> list[str]:
    errors = []
    if overrides is not None and (
            type(overrides) is not dict
            or set(overrides) - set(TARGETS)
            or any(type(v) is not str for v in overrides.values())):
        errors.append("P69_UNSAFE_OR_UNKNOWN_OVERRIDE")
    for i, path in enumerate(TARGETS, 1):
        try:
            source = (overrides[path] if type(overrides) is dict
                      and path in overrides else
                      (root / path).read_text(encoding="utf-8"))
            findings = inspect_source(source)
        except (OSError, UnicodeError, ValueError):
            findings = ["P69_SOURCE_UNAVAILABLE"]
        errors.extend("P69_SOURCE_" + str(i) + ":" + f for f in findings)
    return errors


def snapshot(root: Path = ROOT, overrides: dict | None = None) -> dict:
    errors = audit(root, overrides)
    return {
        "status": "PASS_NARROW_IMPORT_TIME_AST_ONLY" if not errors
        else "FAIL_CLOSED",
        "mock_source_modules_reviewed": len(TARGETS),
        "runtime_side_effect_freedom_proven": False,
        "transitive_dependencies_verified": False,
        "actual_mt4_access_performed": False,
        "p05_passed": 0, "g1_real_verified": 0,
        "real_mt4_read_authorized": False,
        "order_execution_authorized": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
