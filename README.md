# Fx | AI-driven FX Trading System

> Status: **design phase / no live trading enabled**  
> Specification version: **v10.6** (decision Q106)  
> Repository: `picopicodragon/Fx`

## Purpose

This repository is the version-controlled source of truth for a planned FX trading system using Python, SQLite, AI macroeconomic reasoning/review, and an MQL4 Expert Advisor (EA) for a planned Rakuten MT4 account.

**Current status:** The architecture and requirements have been discussed, but the production trading system, MT4 integration, and end-to-end tests are **not yet implemented**. No live trading is permitted by default.

## Development approach

1. Preserve confirmed requirements with unique specification IDs and track the link from requirement -> development task -> code -> acceptance test -> approval.
2. Build the safety/risk foundation before market-data integration, AI analysis, or order execution.
3. Develop on feature branches and review Pull Requests before merging into `main`.
4. Require explicit human authorization for changes to risk limits, stop-loss handling, trade suspension/recovery, live-trading gates, or production AI model approvals.
5. Test in stages: local simulation -> MT4 demo (if available) -> integrated paper trading -> explicit human approval prior to any real-money deployment.
6. Never commit secrets, broker credentials, personal account data, raw paid news feeds, or operational SQLite databases.

## Confirmed high-level constraints (selected examples)

- Initial account size: JPY 100,000.
- Risk per trade: at most 0.5% of applicable equity; aggregate initial-stop risk at most 1%.
- Daily loss limit: 1.5% (including unrealized losses); maximum equity drawdown: 5% with manual reauthorization.
- Economic reasoning is hypothesis based, with separate mandatory adversarial review; market-price analysis cannot bypass hard risk guards.
- Trading is disabled unless all required safety checks pass and live operation is expressly authorized.
- Regular AI API operating budget: JPY 3,000/month; separate development/validation AI API budget: JPY 3,000/month, with advance approval required for increases.
- During early development, ChatGPT Web may assist human-supervised research and design; unattended trading must use authorized programmatic interfaces.
- All API usage, model identities, token counts where available, estimated costs, and relevant decisions are logged.

The authoritative detailed requirements, including exceptions and edge conditions, must be transcribed and reviewed before implementing dependent modules. **Do not infer that this README is the full Q1–Q106 specification.**

## Planned repository structure

```text
MASTER_SPEC.md             # Master requirements index (to be prepared)
AGENTS.md                  # Codex working rules (to be prepared)
specs/                     # Risk, AI, data, MT4, cost, recovery requirements
schemas/                   # Versioned Web/Python/AI exchange formats
src/                       # Python implementation
mt4/                       # MQL4 EA
tests/                     # Acceptance, integration, and failure-injection tests
TASKS.md                   # Task tracking
TRACEABILITY.md            # Requirement -> code -> test matrix
DECISIONS.md               # Approved design decisions and change log
reports/                   # Sanitized test and review reports
```

The earlier *FX Web Bridge v1.0* exchange-format prototype is intended for integration into this repository, but has not yet been imported here.

## Repository and security policy

- `main` is the proposed stable documentation/code baseline.
- New work should use dedicated feature branches and Pull Requests; do not enable automerge for safety-sensitive changes.
- Keep credentials in local environment variables or a secret manager, never in Git.
- The repository is **private**, but privacy is not a substitute for secret management.
- Operational SQLite databases, backups, broker statements, and potentially licensed market/news data stay outside GitHub by default.
- CI can test code and schemas using synthetic data. No broker trading credentials or live orders in CI.

## Next design decision

Q107 will define Codex's degree of implementation autonomy and what requires human approval.
