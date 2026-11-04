"""Read-only RISK-3P-07 FORM-02 draft audit. NO approval or broker I/O."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.phase1_three_pair_synthetic_stop_conversion import PAIRS


ROOT = Path(__file__).resolve().parents[1]
DRAFT = "specs/risk_3p_07_form02_stop_review_draft_20261104.json"
FORM = "specs/p0_01_risk_formula_open_decisions.json"
GAPS = "specs/p0_01_d5_25_gap_verification_matrix.json"
KINDS = ("MARKET", "LIMIT", "STOP")
STAGES = ("CANDIDATE", "PENDING", "POSITION")
CAPS = {"individual": "0.005", "aggregate": "0.010",
        "daily": "0.015", "max_dd": "0.05"}
DECISIONS = tuple(f"F02-{i}" for i in range(1, 7))
NEEDS = ("FORM-01", "FORM-03", "FORM-04", "FORM-05",
         "FORM-06", "FORM-07", "FORM-08", "FORM-09", "FORM-10",
         "G1", "FX-SAF-001", "FX-SAF-002")
NEGATIVES = (
    "SL_MISSING", "SL_WRONG_SIDE", "ZERO_STOP_DISTANCE",
    "MARKET_PLAN_NOT_GUARANTEED_FILL", "PENDING_TRIGGER_MISSING",
    "LIMIT_TRIGGER_WRONG_SIDE", "STOP_TRIGGER_WRONG_SIDE",
    "SERVER_STOP_NOT_CONFIRMED", "STOP_REPLACE_UNACKNOWLEDGED",
    "STOP_REMOVAL_UNCONFIRMED", "PARTIAL_FILL_UNRECONCILED",
    "CANCEL_REQUEST_PENDING", "ORDER_OUTCOME_UNKNOWN",
    "ADVERSE_GAP_OR_SLIPPAGE_UNKNOWN", "QUOTE_EPOCH_MISMATCH",
    "CROSSED_QUOTE", "ACCOUNT_OR_INFLIGHT_STATE_UNKNOWN",
)


def read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, draft: object = None) -> list[str]:
    errors: list[str] = []
    try:
        d = read(root, DRAFT) if draft is None else draft
        if type(d) is not dict:
            return ["INVALID_DRAFT"]
        if (type(d.get("schema_version")) is not int or d["schema_version"] != 1
                or d.get("id") != "RISK-3P-07-FORM02-STOP-REVIEW-DRAFT-20261104"
                or d.get("scope") != "SYNTHETIC_SHAPE_AND_OWNER_REVIEW_ONLY"
                or d.get("source_form") != FORM):
            errors.append("DRAFT_IDENTITY_DRIFT")
        if (d.get("target_pairs") != list(PAIRS)
                or d.get("order_kinds") != list(KINDS)
                or d.get("stages") != list(STAGES)):
            errors.append("PAIR_OR_ORDER_SCOPE_DRIFT")
        if d.get("risk_limits_unchanged") != CAPS:
            errors.append("HARD_LIMITS_DRIFT")
        if d.get("related_unresolved") != list(NEEDS):
            errors.append("UNRESOLVED_DEPENDENCY_DROPPED")
        for field in ("owner_approval_recorded", "form02_implementation_approved",
                      "broker_stop_verified", "real_loss_bound_verified",
                      "real_world_evidence_verified", "production_authorized",
                      "mt4_execution_authorized", "order_allowed",
                      "stop_release_allowed"):
            if d.get(field) is not False:
                errors.append("FALSE_APPROVAL:" + field)
        if (d.get("source_truth") != "SYNTHETIC_INPUT_ONLY"
                or d.get("historical_form02_status")
                != "UNDECIDED_IMPLEMENTATION_DETAIL"
                or d.get("phase_1") != "BLOCKED"
                or d.get("runtime_go_no_go") != "NO_GO"
                or d.get("safety_hold_latched") is not True
                or "verified_values" not in d or d["verified_values"] is not None):
            errors.append("FALSE_SOURCE_OR_STOP_STATUS")
        original = read(root, FORM)
        src = next(x for x in original["open_decisions"] if x["id"] == "FORM-02")
        if (src.get("owner_status") != "UNDECIDED_IMPLEMENTATION_DETAIL"
                or src.get("blocking") is not True):
            errors.append("FORM02_ORIGINAL_FALSELY_RESOLVED")
        gaps = read(root, GAPS)
        if not all(g["implementation_status"] == "UNRESOLVED"
                   and g["real_world_verified"] is False
                   and g["release_blocker"] is True for g in gaps["gaps"]):
            errors.append("FORMAL_GATES_FALSELY_RESOLVED")
        if gaps.get("phase_1") != "BLOCKED" or gaps.get("runtime_go_no_go") != "NO_GO":
            errors.append("PHASE_OR_RUNTIME_FALSELY_PROMOTED")
        candidates = d.get("review_scenarios")
        expected = {
            (stage, side, kind)
            for stage in STAGES for side in ("BUY", "SELL")
            for kind in KINDS if not (stage == "PENDING" and kind == "MARKET")
        }
        if type(candidates) is not list or len(candidates) != len(expected):
            errors.append("SCENARIO_SET_INCOMPLETE")
        else:
            actual = set()
            for c in candidates:
                if type(c) is not dict:
                    errors.append("INVALID_SCENARIO")
                    continue
                try:
                    key = (c["stage"], c["side"], c["order_kind"])
                    actual.add(key)
                    if (c.get("id") != "SYNTHETIC_" + "_".join(key)
                            or c.get("expected_claim") != "SHAPE_ONLY_NEVER_ORDER_ALLOWED"
                            or c.get("live_risk_covered") is not False):
                        errors.append("SCENARIO_FALSE_POSITIVE")
                except (KeyError, TypeError):
                    errors.append("INVALID_SCENARIO")
            if actual != expected:
                errors.append("SCENARIO_COVERAGE_DRIFT")
        negative = d.get("negative_scenarios")
        if (type(negative) is not list or len(negative) != len(NEGATIVES)
                or [x.get("id") for x in negative if type(x) is dict]
                != list(NEGATIVES)):
            errors.append("NEGATIVE_SCENARIO_COVERAGE_DRIFT")
        else:
            for row in negative:
                if (row.get("expected") != "DENY_NEW_ENTRY_NO_GO"
                        or row.get("real_world_verified") is not False):
                    errors.append("FALSE_NEGATIVE_SCENARIO_APPROVAL:" + row["id"])
        decisions = d.get("owner_decisions")
        if (type(decisions) is not list or len(decisions) != len(DECISIONS)
                or [x.get("id") for x in decisions if type(x) is dict]
                != list(DECISIONS)):
            errors.append("OWNER_DECISION_SET_DRIFT")
        else:
            for row in decisions:
                if (row.get("owner_status") != "UNDECIDED"
                        or row.get("approval_reference", "MISSING") is not None
                        or type(row.get("question")) is not str or not row["question"]
                        or type(row.get("recommendation")) is not str
                        or not row["recommendation"]):
                    errors.append("FALSE_OWNER_DECISION:" + row["id"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        errors.append("MALFORMED_OR_MISSING_EVIDENCE")
    return errors


def main() -> None:
    errors = audit()
    if errors:
        raise SystemExit("RISK-3P-07 FORM-02: FAIL\n" +
                         "\n".join("- " + e for e in errors))
    print("RISK-3P-07 FORM-02: PASS (SYNTHETIC SCENARIOS ONLY)")
    print("16 order/side/lifecycle shapes + 17 negative scenarios, no real evidence")
    print("FORM-02 UNDECIDED | G1-G9 UNRESOLVED | PHASE-1 BLOCKED")
    print("runtime NO_GO | safety_hold_latched=true")


if __name__ == "__main__":
    main()
