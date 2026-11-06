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


def _literal_only(node: object) -> bool:
    """Only immutable literal structures; no names, subscripts, operators or calls."""
    if isinstance(node, ast.Constant):
        return type(node.value) in (str, bytes, int, float, bool, type(None))
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_literal_only(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _literal_only(k) and _literal_only(v)
                   for k, v in zip(node.keys, node.values))
    if isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.USub, ast.UAdd)):
        return isinstance(node.operand, ast.Constant) and type(
            node.operand.value) in (int, float)
    return False


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
            defaults = list(stmt.args.defaults) + [
                x for x in stmt.args.kw_defaults if x is not None]
            annotations = [arg.annotation for arg in (
                list(stmt.args.posonlyargs) + list(stmt.args.args)
                + list(stmt.args.kwonlyargs)
                + ([stmt.args.vararg] if stmt.args.vararg else [])
                + ([stmt.args.kwarg] if stmt.args.kwarg else []))
                if arg.annotation is not None]
            if stmt.returns is not None:
                annotations.append(stmt.returns)
            if (stmt.decorator_list
                    or any(not _literal_only(x) for x in defaults)
                    or any(isinstance(n, (ast.Call, ast.Await, ast.Yield,
                                         ast.NamedExpr))
                           for a in annotations for n in ast.walk(a))):
                errors.append("P69_IMPORT_TIME_DECORATOR_OR_DEFAULT_CALL")
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            if isinstance(stmt, ast.AnnAssign) and any(
                    isinstance(n, (ast.Call, ast.Await, ast.Yield,
                                   ast.NamedExpr))
                    for n in ast.walk(stmt.annotation)):
                errors.append("P69_IMPORT_TIME_INITIALIZER_EXECUTION")
            value = stmt.value
            if value is None:
                continue
            # Narrow existing exception for a constant regular expression
            # assigned to the mock chain's HEX64. Other calls and expressions
            # are not permitted as module-level values.
            allow_regex = (
                isinstance(stmt, ast.Assign)
                and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and value.func.value.id == "re"
                and value.func.attr == "compile"
                and len(value.args) == 1
                and isinstance(value.args[0], ast.Constant)
                and type(value.args[0].value) is str
                and value.args[0].value == r"[0-9a-f]{64}\\Z"
                and not value.keywords
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == "HEX64"
            )
            if not (_literal_only(value) or allow_regex):
                errors.append("P69_IMPORT_TIME_INITIALIZER_EXECUTION")
            if isinstance(stmt, ast.Assign) and any(
                    not isinstance(t, ast.Name) for t in stmt.targets):
                errors.append("P69_IMPORT_TIME_ASSIGNMENT_TARGET")
            elif isinstance(stmt, ast.AnnAssign) and not isinstance(
                    stmt.target, ast.Name):
                errors.append("P69_IMPORT_TIME_ASSIGNMENT_TARGET")
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
        except (OSError, UnicodeError, ValueError, RecursionError):
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
