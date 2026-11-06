"""Narrow AST review for selected *pure synthetic* validation modules.

It blocks explicit unsafe import/call patterns but is NOT a security sandbox,
taint analysis, provenance proof or guarantee about dependencies/callers.
It reads only public repository Python source. Never reads private files.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_STATIC_SOURCE_CHARS = 65536  # synthetic AST resource bound, not a sandbox
TARGETS = (
    "scripts/risk_3p_49_synthetic_evidence_chain.py",
    "scripts/risk_3p_50_synthetic_dual_witness.py",
    "scripts/risk_3p_51_mock_approval_separation.py",
    "scripts/risk_3p_55_synthetic_ingress_contract.py",
    "scripts/risk_3p_57_synthetic_temporal_coherence.py",
    "scripts/risk_3p_58_safe_diagnostic_projection.py",
)
ALLOWED_IMPORT_ROOTS = frozenset((
    "__future__", "ast", "copy", "datetime", "decimal", "hashlib", "json",
    "re", "typing", "scripts",
))
DISALLOWED_CALLS = frozenset((
    "eval", "exec", "compile", "open", "input", "__import__",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
    "breakpoint",
))
DISALLOWED_ATTR_CALLS = frozenset((
    "open", "read_text", "read_bytes", "write_text", "write_bytes",
    "unlink", "rmdir", "mkdir", "chmod", "chown", "rename", "replace",
    "system", "popen", "Popen", "run", "check_call", "check_output",
    "connect", "send", "recv", "urlopen", "request", "OrderSend",
    "OrderClose", "OrderModify", "OrderDelete", "ShellExecute",
))
DISALLOWED_IDENTIFIERS = frozenset((
    "MetaTrader5", "OrderSend", "OrderClose", "OrderModify",
    "AutoTrading", "ShellExecute", "WinDLL",
))

# Explicitly pin the only mock-only dependencies permitted in the six
# selected pure validators. This is a narrow syntactic allowlist, not a
# guarantee that module imports are side-effect free.
REFLECTION_ESCAPE_ATTRIBUTES = frozenset((
    "__globals__", "__builtins__", "__dict__", "__getattribute__",
    "__subclasses__", "__mro__", "__bases__", "__class__",
    "__code__", "__closure__", "__loader__", "__spec__",
))

ALLOWED_SCRIPT_MODULES = frozenset((
    "validate_risk_3p_34_synthetic_provenance",
    "risk_3p_49_synthetic_evidence_chain",
    "risk_3p_50_synthetic_dual_witness",
    "risk_3p_51_mock_approval_separation",
    "risk_3p_55_synthetic_ingress_contract",
))


def _inspect_source(source: object) -> list[str]:
    """Fixed error codes only; never echo or run untrusted source."""
    if type(source) is not str or not source:
        return ["P56_INVALID_SOURCE"]
    if len(source) > MAX_STATIC_SOURCE_CHARS:
        return ["P56_SOURCE_TOO_LARGE"]
    if not source.strip():
        return ["P56_INVALID_SOURCE"]
    try:
        tree = ast.parse(source)
    except (SyntaxError, TypeError, ValueError, RecursionError):
        return ["P56_INVALID_PYTHON_SYNTAX"]
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORT_ROOTS:
                    errors.append("P56_DISALLOWED_IMPORT")
                elif alias.name == "scripts" or (
                        alias.name.startswith("scripts.") and
                        alias.name.removeprefix("scripts.")
                        not in ALLOWED_SCRIPT_MODULES):
                    errors.append("P56_UNAPPROVED_LOCAL_MODULE_IMPORT")
        elif isinstance(node, ast.ImportFrom):
            if (node.level != 0 or node.module is None
                    or node.module.split(".")[0] not in ALLOWED_IMPORT_ROOTS
                    or any(alias.name == "*" for alias in node.names)):
                errors.append("P56_DISALLOWED_IMPORT_FROM")
            elif node.module == "scripts":
                if any(alias.name not in ALLOWED_SCRIPT_MODULES
                       for alias in node.names):
                    errors.append("P56_UNAPPROVED_LOCAL_MODULE_IMPORT")
            elif node.module.startswith("scripts."):
                errors.append("P56_UNAPPROVED_LOCAL_MODULE_IMPORT")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in DISALLOWED_CALLS:
                errors.append("P56_UNSAFE_DIRECT_CALL")
            if isinstance(fn, ast.Attribute) and fn.attr in DISALLOWED_ATTR_CALLS:
                errors.append("P56_UNSAFE_ATTRIBUTE_CALL")
        elif isinstance(node, ast.Attribute):
            if node.attr in REFLECTION_ESCAPE_ATTRIBUTES:
                errors.append("P56_REFLECTION_ESCAPE_ATTRIBUTE")
        elif isinstance(node, ast.Name):
            if node.id in DISALLOWED_IDENTIFIERS:
                errors.append("P56_PRIVILEGED_SYMBOL_REFERENCE")
    return list(dict.fromkeys(errors))


def audit(root: Path = ROOT, overrides: dict | None = None) -> list[str]:
    errors = []
    # Inspect the actual built-in dict key/value types before any membership
    # test or dict lookup. A poisoned object key may execute custom __eq__
    # if compared to an expected filename, even after construction.
    if overrides is not None:
        if (type(overrides) is not dict
                or len(overrides) > len(TARGETS)
                or any(type(k) is not str or type(v) is not str
                       or k not in TARGETS
                       or len(v) > MAX_STATIC_SOURCE_CHARS
                       for k, v in overrides.items())):
            return ["P56_UNKNOWN_OR_PRIVATE_PATH_OVERRIDE"]
    for position, path in enumerate(TARGETS, 1):
        try:
            source = (
                overrides[path] if type(overrides) is dict and path in overrides
                else (root / path).read_text(encoding="utf-8"))
            findings = _inspect_source(source)
        except (OSError, UnicodeError, ValueError):
            findings = ["P56_TARGET_MISSING_OR_UNREADABLE"]
        errors.extend(f"P56_TARGET_{position}:" + code for code in findings)
    return errors


def snapshot(root: Path = ROOT, overrides: dict | None = None) -> dict:
    errors = audit(root, overrides)
    return {
        "status": "PASS_NARROW_STATIC_REVIEW_ONLY" if not errors
        else "FAIL_CLOSED",
        "pure_synthetic_modules_scanned": len(TARGETS),
        "full_runtime_isolation_proven": False,
        "transitive_imports_or_reflection_proven_safe": False,
        "p05_passed": 0, "g1_real_verified": 0,
        "real_mt4_access_authorized": False,
        "order_execution_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
