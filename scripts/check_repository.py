"""Repository baseline checks for the Fx solo-maintainer project.

These checks do NOT certify strategy, brokerage integration, or trading safety.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    required = ["README.md", "AGENTS.md", ".gitignore"]
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit(f"Missing required repository files: {', '.join(missing)}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agent = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if "実口座での自動売買は無効" not in readme:
        raise SystemExit("README must explicitly state live trading is disabled")
    if "LIVE TRADING IS NOT AUTHORIZED" not in agent:
        raise SystemExit("Codex policy must prohibit live trading")

    # Validate available interchange data without assuming the planned schemas exist yet.
    json_files = list((ROOT / "schemas").rglob("*.json")) if (ROOT / "schemas").exists() else []
    for item in json_files:
        with item.open("r", encoding="utf-8") as file:
            json.load(file)

    # Only on PR events: require an auditable, self-reviewable description.
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request" and event_path:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        body = event.get("pull_request", {}).get("body") or ""
        for required_heading in ("関連仕様ID", "テスト結果", "本人確認"):
            if required_heading not in body:
                raise SystemExit(f"PR description is missing section: {required_heading}")

    print(f"Repository baseline check: PASS ({len(json_files)} JSON file(s) checked)")
    if not (ROOT / "tests").is_dir():
        print("NOTE: No tests/ directory yet; trade-safety tests have NOT been run.")


if __name__ == "__main__":
    main()
