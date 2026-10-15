# Codex instructions (Fx project)

This project is in design stage. **LIVE TRADING IS NOT AUTHORIZED.**

## Mandatory process

1. Read `README.md`, and when available `MASTER_SPEC.md`, `DECISIONS.md`, `TRACEABILITY.md`, and related files under `specs/` before implementing a task.
2. Work on a feature branch and open a Pull Request. Explain related specification IDs, changed code, tests run, and any risks. Do not merge a Pull Request without user approval.
3. Do not silently change hard risk limits, account-level stop logic, required stop-loss handling, reconciliation, recovery gates, AI independent verification, or live-order permission controls.
4. Never run live orders or connect live brokerage credentials as part of automated tests. Use synthetic fixtures, offline simulation, then approved demo testing.
5. A passing test does not authorize live trading. The user must explicitly approve any live activation after required verification.
6. Do not commit API keys, private account information, operational databases/backups, or copyrighted/licensed market-data dumps.
7. If requirements have not yet been transcribed from design conversation, mark them as **UNVERIFIED / PENDING**; do not invent missing details or claim coverage.
8. Log implementation decisions, failures, acceptance test results, and any API-cost implications.

The separate ChatGPT Web <-> Codex/Python bridge is a design artifact. Manual file transfer does not itself authorize orders.
