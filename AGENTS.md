# Codex instructions (Fx project)

This is a **solo-maintainer** project at the design stage. **LIVE TRADING IS NOT AUTHORIZED.**

## Mandatory process

1. Read `README.md`, and when available `MASTER_SPEC.md`, `DECISIONS.md`, `TRACEABILITY.md`, and related files under `specs/` before implementing a task.
2. Implement routine changes and tests on a dedicated feature branch. Open a Pull Request as an auditable **self-review checkpoint**. Do not request or require a separate reviewer: this project has one human maintainer.
3. Include specification IDs, change summary, risk impact, test results, and a personal-review checklist in the PR description. Wait for the human maintainer to inspect the diff and CI results and **manually merge**; Codex must not merge `main` autonomously.
4. Never silently alter hard risk limits, stop-loss protection, drawdown/day-loss halts, reconciliation, failure recovery, independent AI review, approved production models, or live-order permission. Any such **specification change** requires express prior human approval and a decision-log entry.
5. **Q109 traceability gate:** Any new or changed safety-critical code for trading risk limits, SL, orders, reconciliation, shutdown/recovery, or AI order approval must be mapped in `specs/traceability.json` to specification IDs and existing automated test files. Update tests and run them before a PR can be merged. Do not change guarded source-folder conventions to evade the gate. Current gate checks registration/execution, not actual financial safety.
6. **Q110 three-level acceptance:** Track TASK, MODULE, and PHASE separately in `specs/acceptance_registry.json`. A passing unit test means a task may complete; it does not complete its module or phase. Human sign-off is required for safety-critical MODULE acceptance and every PHASE acceptance; records must cite the evidence and approval decision. Do not fabricate approvals, and do not treat PR merge as approval for live trading.
7. **Q111 specification gate:** Read `MASTER_SPEC.md` and the safety draft `specs/safety_foundation.md` before PHASE 1 safety implementation. The decision index was transcribed from discussion and is awaiting the human maintainer's original-record verification; do not infer that the index itself is an approved implementation-level safety specification. Unresolved safety parameters are blockers, not invitations to guess. Run `python scripts/check_master_spec.py`; this verifies numbering only, not correctness.
8. **Q112 original-source reconciliation:** AI may draft a difference/omission register, but safety-critical requirements must not be marked implementation-approved until the human maintainer has verified the **original user decision**, resolved all listed issues, and recorded an explicit approval reference. `SUMMARY_ONLY`/`UNAVAILABLE` are not original evidence. See `specs/reconciliation_policy.md` and `specs/reconciliation_registry.json`. Never invent user approvals or original-conversation citations. Run `python scripts/check_reconciliation.py`.
9. **Q113 local-source archive policy:** The complete design conversation must remain outside Git/GitHub on the user's local PC. Only minimally necessary, provenance-tagged, reviewed excerpts may be committed to `specs/source_excerpts/`. Read `specs/source_archive_policy.md` and `specs/source_evidence.json`. Never simulate ChatGPT exports, fabricate original user quotations, or mark Q1-Q112 originals as verified from a summary. Run `python scripts/check_source_evidence.py`. Source evidence registration does not authorize safety implementation.
10. **Q114 hybrid extraction:** See `docs/local_archive_guide.md`. `scripts/extract_original_decisions.py` only creates candidate files outside the Git repository. Do not upload originals, treat candidate text as proven evidence, automatically commit excerpts, or infer a question ID from responses like 'CでOK'. User must check original context and confidential data before selective registration.
16. Use GitHub Actions for automated checks. Never mark work as complete when required checks fail or are missing. Initial documentation/syntax checks are not a substitute for unit, integration, fault-injection, and demo/paper-trading safety tests.
11. Never submit live orders or connect live brokerage credentials as part of automated tests. Use synthetic fixtures, offline simulation, then separately approved demo tests.
12. No passing test or PR merge by itself authorizes live trading. The human maintainer must explicitly approve live activation only after all required evaluations.
13. Do not commit API keys, private account information, operational SQLite databases/backups, or copyrighted/licensed market-data dumps.
14. If requirements have not yet been transcribed from design conversation, mark them as **UNVERIFIED / PENDING**; do not invent missing details or claim coverage.
15. Log implementation decisions, failures, acceptance-test evidence, and any AI API cost implications.

## GitHub settings caveat

Do **not** configure a mandatory "one approving review" branch rule for this solo-maintainer repository. A PR author cannot satisfy an independent self-review requirement via GitHub approval. Prefer required status checks (if supported), self-checklist, and **manual merge by the owner**. At present repository rules may not enforce this policy technically, so verify settings before claiming branch protection is active.

The separate ChatGPT Web <-> Codex/Python bridge is a development artifact. Manual file transfer does not itself authorize orders.
