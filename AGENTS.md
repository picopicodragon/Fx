# Codex instructions (Fx project)

This is a **solo-maintainer** project at the design stage. **LIVE TRADING IS NOT AUTHORIZED.**

## Mandatory process

1. Read `README.md`, and when available `MASTER_SPEC.md`, `DECISIONS.md`, `TRACEABILITY.md`, and related files under `specs/` before implementing a task.
2. Implement routine changes and tests on a dedicated feature branch. Open a Pull Request as an auditable **self-review checkpoint**. Do not request or require a separate reviewer: this project has one human maintainer.
3. Include specification IDs, change summary, risk impact, test results, and a personal-review checklist in the PR description. Wait for the human maintainer to inspect the diff and CI results and **manually merge**; Codex must not merge `main` autonomously.
4. Never silently alter hard risk limits, stop-loss protection, drawdown/day-loss halts, reconciliation, failure recovery, independent AI review, approved production models, or live-order permission. Any such **specification change** requires express prior human approval and a decision-log entry.
5. **Q109 traceability gate:** Any new or changed safety-critical code for trading risk limits, SL, orders, reconciliation, shutdown/recovery, or AI order approval must be mapped in `specs/traceability.json` to specification IDs and existing automated test files. Update tests and run them before a PR can be merged. Do not change guarded source-folder conventions to evade the gate. Current gate checks registration/execution, not actual financial safety.
6. **Q110 three-level acceptance:** Track TASK, MODULE, and PHASE separately in `specs/acceptance_registry.json`. A passing unit test means a task may complete; it does not complete its module or phase. Human sign-off is required for safety-critical MODULE acceptance and every PHASE acceptance; records must cite the evidence and approval decision. Do not fabricate approvals, and do not treat PR merge as approval for live trading.
7. Use GitHub Actions for automated checks. Never mark work as complete when required checks fail or are missing. Initial documentation/syntax checks are not a substitute for unit, integration, fault-injection, and demo/paper-trading safety tests.
8. Never submit live orders or connect live brokerage credentials as part of automated tests. Use synthetic fixtures, offline simulation, then separately approved demo tests.
9. No passing test or PR merge by itself authorizes live trading. The human maintainer must explicitly approve live activation only after all required evaluations.
10. Do not commit API keys, private account information, operational SQLite databases/backups, or copyrighted/licensed market-data dumps.
11. If requirements have not yet been transcribed from design conversation, mark them as **UNVERIFIED / PENDING**; do not invent missing details or claim coverage.
12. Log implementation decisions, failures, acceptance-test evidence, and any AI API cost implications.

## GitHub settings caveat

Do **not** configure a mandatory "one approving review" branch rule for this solo-maintainer repository. A PR author cannot satisfy an independent self-review requirement via GitHub approval. Prefer required status checks (if supported), self-checklist, and **manual merge by the owner**. At present repository rules may not enforce this policy technically, so verify settings before claiming branch protection is active.

The separate ChatGPT Web <-> Codex/Python bridge is a development artifact. Manual file transfer does not itself authorize orders.
