"""RISK-3P-193..198: offline, read-only post-merge safety ledger regression.

No MT4, broker, secrets, orders, source-archive reading or approval writes.
These tests assert the *current blocked baseline*, not live-trading safety.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(relative_path: str) -> dict:
    with (ROOT / relative_path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _safe_snapshot(acceptance: object, review: object, trace: object) -> bool:
    """Strict fail-closed snapshot: malformed, extra authorizations or unknown state fail."""
    if type(acceptance) is not dict or type(review) is not dict or type(trace) is not dict:
        return False

    tasks = acceptance.get("tasks")
    modules = acceptance.get("modules")
    phases = acceptance.get("phases")
    items = review.get("items")
    mappings = trace.get("offline_synthetic_mappings")
    if any(type(v) is not list for v in (tasks, modules, phases, items, mappings)):
        return False
    if len(items) != 15 or len(mappings) != 45 or not modules or not phases:
        return False

    for entry in tasks + modules + phases:
        if type(entry) is not dict or type(entry.get("id")) is not str:
            return False
        if "approval" not in entry or entry["approval"] is not None:
            return False
    for entry in modules:
        if type(entry.get("safety_critical")) is not bool:
            return False
        if entry["safety_critical"] and entry.get("status") != "BLOCKED":
            return False
    for entry in phases:
        if entry.get("status") not in ("BLOCKED", "NOT_STARTED"):
            return False

    seen_requirements: set[str] = set()
    for item in items:
        if type(item) is not dict:
            return False
        identifier = item.get("requirement_id")
        if type(identifier) is not str or identifier in seen_requirements:
            return False
        seen_requirements.add(identifier)
        if (item.get("source_review") != "PENDING_ORIGINAL"
                or item.get("spec_comparison") != "NOT_REVIEWED"
                or item.get("confidentiality_review") != "NOT_REVIEWED"
                or type(item.get("human_safety_approval")) is not bool
                or item["human_safety_approval"] is not False
                or type(item.get("github_excerpt_refs")) is not list
                or item["github_excerpt_refs"]):
            return False
    if seen_requirements != {f"FX-SAF-{index:03d}" for index in range(1, 16)}:
        return False

    sources: set[str] = set()
    for mapping in mappings:
        if type(mapping) is not dict:
            return False
        source = mapping.get("source")
        if type(source) is not str or source in sources:
            return False
        sources.add(source)
        if (type(mapping.get("production_authorized")) is not bool
                or mapping["production_authorized"] is not False):
            return False
        if (type(mapping.get("spec_ids")) is not list
                or type(mapping.get("tests")) is not list
                or not mapping["tests"]):
            return False
        if any(type(p) is not str for p in mapping["tests"]):
            return False
    return True


class TestPostMergeSafetyLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acceptance = _load("specs/acceptance_registry.json")
        cls.review = _load("specs/source_review_priority.json")
        cls.trace = _load("specs/traceability.json")

    def assertRejected(self, kind: str, change):
        documents = [copy.deepcopy(self.acceptance), copy.deepcopy(self.review), copy.deepcopy(self.trace)]
        index = {"acceptance": 0, "review": 1, "trace": 2}[kind]
        change(documents[index])
        self.assertFalse(_safe_snapshot(*documents))

    def test_193_real_repository_remains_unapproved(self):
        self.assertTrue(_safe_snapshot(self.acceptance, self.review, self.trace))

    def test_194_no_module_can_claim_acceptance(self):
        self.assertRejected("acceptance", lambda d: d["modules"][0].update(status="ACCEPTED"))

    def test_194_no_phase_can_claim_completion(self):
        self.assertRejected("acceptance", lambda d: d["phases"][0].update(status="ACCEPTED"))

    def test_194_no_fake_owner_approval(self):
        self.assertRejected("acceptance", lambda d: d["modules"][0].update(approval="synthetic"))

    def test_195_no_verified_original_without_review(self):
        self.assertRejected("review", lambda d: d["items"][0].update(source_review="VERIFIED"))

    def test_195_no_fake_original_reference(self):
        self.assertRejected("review", lambda d: d["items"][0].update(github_excerpt_refs=["fake"]))

    def test_195_no_int_disguised_as_boolean(self):
        self.assertRejected("review", lambda d: d["items"][0].update(human_safety_approval=0))

    def test_196_no_fake_production_authorization(self):
        self.assertRejected("trace", lambda d: d["offline_synthetic_mappings"][0].update(production_authorized=True))

    def test_196_no_numeric_false_as_authorization(self):
        self.assertRejected("trace", lambda d: d["offline_synthetic_mappings"][0].update(production_authorized=0))

    def test_196_no_missing_test_binding(self):
        self.assertRejected("trace", lambda d: d["offline_synthetic_mappings"][0].update(tests=[]))

    def test_197_no_duplicate_safety_ids(self):
        self.assertRejected("review", lambda d: d["items"][1].update(requirement_id=d["items"][0]["requirement_id"]))

    def test_197_no_dropped_safety_requirement(self):
        self.assertRejected("review", lambda d: d["items"].pop())

    def test_197_no_dropped_traceability_source(self):
        self.assertRejected("trace", lambda d: d["offline_synthetic_mappings"].pop())

    def test_198_reject_injected_mapping_subclass(self):
        class UnsafeMapping(dict):
            pass
        self.assertFalse(_safe_snapshot(UnsafeMapping(self.acceptance), self.review, self.trace))

    def test_198_reject_non_dict_review_entry(self):
        self.assertRejected("review", lambda d: d["items"].__setitem__(0, "invalid"))

    def test_198_reject_missing_approval_key(self):
        self.assertRejected("acceptance", lambda d: d["modules"][0].pop("approval"))


if __name__ == "__main__":
    unittest.main()
