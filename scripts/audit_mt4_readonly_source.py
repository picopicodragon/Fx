"""Conservative text-only audit for the one-shot MQL4 read-only probe.

This is NOT a MetaEditor compiler or runtime safety attestation.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mt4/read_only/P0_01_ManualSymbolSnapshot_ReadOnly.mq4"

EXPECTED_FIELDS = {
    "min_lot": "MODE_MINLOT",
    "lot_step": "MODE_LOTSTEP",
    "point_quote": "MODE_POINT",
    "tick_size_points": "MODE_TICKSIZE",
    "tick_value_deposit_currency": "MODE_TICKVALUE",
}
EXPECTED_SYMBOLS = ("USDJPY", "EURJPY", "GBPUSD", "AUDUSD")
KNOWN_SAFE_CALLS = {
    "OnStart", "IsPlausibleSymbolForPair", "ReadPositiveProperty", "InspectPair",
    "StringLen", "StringFind", "ResetLastError", "MarketInfo", "GetLastError",
    "MathIsValidNumber", "Print", "DoubleToString", "SymbolInfoInteger",
    "IsConnected", "TimeToString", "TimeLocal",
}
REJECTED_CALLS = {
    "OrderSend", "OrderClose", "OrderModify", "OrderDelete", "OrderCloseBy",
    "OrderSelect", "OrderPrint", "SymbolSelect", "FileOpen", "FileWrite",
    "FileReadString", "FileWriteString", "FileClose", "FolderCreate",
    "WebRequest", "SendMail", "SendNotification", "SendFTP",
    "TerminalClose", "ShellExecuteW", "GlobalVariableSet",
    "EventSetTimer", "EventChartCustom", "ChartOpen", "ChartSetInteger",
    "ChartSetDouble", "ChartSetString",
}
# Strip comments and literal strings to avoid false positives and to inspect
# actual executable tokens; this is not a full language parser.
LITERALS_AND_COMMENTS = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"'
)


def audit_mql4_readonly(text: str) -> list[str]:
    issues = []
    source = LITERALS_AND_COMMENTS.sub(" ", text)
    if "#property strict" not in source or "#property script_show_inputs" not in source:
        issues.append("SCRIPT_PROPERTIES")
    if not re.search(r"\bvoid\s+OnStart\s*\(\s*\)", source):
        issues.append("SCRIPT_ONSTART_MISSING")
    if re.search(r"\b(?:OnTick|OnTimer|OnInit|OnDeinit|OnChartEvent)\s*\(", source):
        issues.append("UNAUTHORIZED_EVENT_HANDLER")
    if re.search(r"(?m)^\s*#\s*(?:include|import|resource|define)\b", source):
        issues.append("UNAUTHORIZED_EXTERNAL_SOURCE_OR_MACRO")
    if not re.search(r"\binput\s+bool\s+InpExplicitReadApproval\s*=\s*false\s*;", source):
        issues.append("DEFAULT_DENY_MISSING")
    guard = source.find("if(!InpExplicitReadApproval)")
    connection = source.find("if(!IsConnected())")
    read = source.find('ReadPositiveProperty(symbol_name,')  # call site in InspectPair
    if guard < 0 or connection < guard or read < 0:
        issues.append("EXECUTION_GUARD_OR_READ_PATH")
    # The only allowed market read helpers are the ones being audited.
    calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", source))
    unknown = calls - KNOWN_SAFE_CALLS - {"if", "return"}
    if unknown:
        issues.append("UNEXPECTED_FUNCTION_CALLS")
    if calls & REJECTED_CALLS:
        issues.append("SIDE_EFFECT_FUNCTION")
    if any(c.startswith(("Order", "File", "Socket")) for c in calls):
        issues.append("TRADING_OR_FILE_IO_CALL")
    for field, identifier in EXPECTED_FIELDS.items():
        snippet = r'ReadPositiveProperty\s*\(\s*symbol_name\s*,\s*"' + (
            re.escape(field) + r'"\s*,\s*' + re.escape(identifier) + r'\s*\)')
        if not re.search(snippet, text):
            issues.append("MISSING_FIVE_FIELD_MAP")
            break
    for sym in EXPECTED_SYMBOLS:
        if not re.search(
            rf'\binput\s+string\s+Inp{sym}\s*=\s*"{sym}"\s*;', text
        ):
            issues.append("EXPLICIT_FOUR_SYMBOL_INPUTS")
            break
        if not re.search(
            rf'\bInspectPair\s*\(\s*"{sym}"\s*,\s*Inp{sym}\s*\)', text
        ):
            issues.append("MISSING_SYMBOL_READ")
            break
    if not re.search(r"\bSymbolInfoInteger\s*\(\s*symbol_name\s*,\s*SYMBOL_SELECT\s*\)", source):
        issues.append("NO_SELECTED_SYMBOL_CHECK")
    if "UNVERIFIED" not in text or "OBSERVED_NOT_VERIFIED" not in text:
        issues.append("NO_NONAUTHORIZING_STATUS")
    return sorted(set(issues))


def main() -> int:
    try:
        issues = audit_mql4_readonly(SOURCE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        print("REVIEW_REQUIRED: READONLY_SOURCE_UNAVAILABLE")
        return 1
    if issues:
        print("REVIEW_REQUIRED: " + ", ".join(issues))
        return 1
    print("PASS: Static MQL4 read-only guard audit (NO MetaEditor compilation).")
    print("Deployment/execution not approved; PHASE-1 BLOCKED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
