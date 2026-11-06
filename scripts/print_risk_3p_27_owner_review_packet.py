"""RISK-3P-27: read-only 43-choice owner review packet printer.

This is an offline draft for reading, not an approval form, browser flow,
signature collector or broker interface. Output is stdout only; never writes,
connects, changes a safety gate, or treats a recommendation as a decision.
"""
from __future__ import annotations

from pathlib import Path

from scripts.audit_risk_3p_23_26_decision_critical_path import (
    ROOT, PLAN, DOCKET, _read, audit, snapshot,
)


def render(root: Path = ROOT) -> str:
    errors = audit(root)
    if errors:
        raise ValueError("unsafe or inconsistent source; packet suppressed: "
                         + ", ".join(errors))
    state = snapshot(root)
    if state["readiness"] != "BLOCKED_OWNER_ORIGINALS_AND_G1_REAL_EVIDENCE":
        raise ValueError("only blocked documentary packets can be printed")
    plan, docket = _read(root, PLAN), _read(root, DOCKET)
    if len(docket["decisions"]) != 43:
        raise ValueError("incomplete 43-item docket")
    lines: list[str] = [
        "# RISK-3P-27 FORM-01〜10 本人審査用の未決事項一覧",
        "",
        "> **提案・未承認**。この資料に掲載された推奨文は本人の決定ではなく、",
        "> G1・FX-SAF・MT4へのアクセス許可・新規発注・STOP解除を成立させない。",
        "> 元の台帳・原議に対する本人照合が別途必要。",
        "",
        f"- 未決のFORM詳細：{state['owner_decisions_pending']}件 / 43件",
        f"- 新G1主要属性の実証：{state['g1_real_fields_verified']}件 / 15件",
        f"- FX-SAF原議確認：{state['fx_saf_originals_reviewed']}件 / 15件",
        "- 安全状態：PHASE-1 BLOCKED / runtime NO_GO / 停止ラッチ維持",
        "- 今回の出力は閲覧用。記入・承認・MT4操作を自動実行しない",
        "",
        "## 本人承認済みの方法と次の実作業（実MT4操作は未許可）",
        "",
        "1. **P02方法承認済み**：FX-SAF-001〜015とFORMの原議照合方法は本人が承認。",
        "   ただし原議の現物照合は0/15、各FORM実装判断は0/43。",
        "**G1対象範囲（P03）**：本人が新3×5を正式審査対象として承認済み。旧4×5は保存。実契約証拠は0/15でG1はUNRESOLVED。",
        "2. **P04方法承認済み**：既存EA・注文・単一セッション保全を条件とする",
        "   非破壊閲覧の手順。P05の現在環境安全確認は0/8で未実施。",
        "   MT4接続・ログイン・スクリプト・EA・注文変更を実行しない。",
        "",
    ]
    for cohort in plan["cohorts"]:
        lines.extend([
            f"## {cohort['sequence']}. {cohort['topic']}（提案のみ）",
            "",
            f"対象：{', '.join(cohort['forms'])}",
            "",
            f"**安全側の提案：** {cohort['proposal']}",
            "",
            f"**必要な実証・未解決：** {cohort['evidence_gap']}",
            "",
        ])
        group = [item for item in docket["decisions"]
                 if item["form_id"] in cohort["forms"]]
        group.sort(key=lambda x: (x["review_sequence"], x["form_id"],
                                  docket["decisions"].index(x)))
        for item in group:
            if (item.get("owner_decision") != "NOT_RECORDED"
                    or item.get("implementation_approved") is not False
                    or item.get("ready_for_owner_signoff") is not False):
                raise ValueError("an allegedly approved owner decision was introduced")
            lines.extend([
                f"### {item['id']}（本人未決）",
                "",
                f"**審査する事項：** {item['original_question']}",
                "",
                ("**元ドラフトの提案：** " + item["source_recommendation"]
                 if item["source_recommendation"] is not None
                 else "**元ドラフトの個別提案：未設定（本人判断待ち）**"),
                "",
                f"**原資料：** {item['source']}",
                "",
            ])
    ids = [x["id"] for x in docket["decisions"]]
    if len(ids) != len(set(ids)) or len(ids) != 43:
        raise ValueError("duplicate or missing FORM decision")
    lines.extend([
        "## 現時点で実施できないこと",
        "",
        "未確認のG1契約属性/EA/建玉・安全要件のまま、実MT4の起動・操作・",
        "注文/SL変更・追加口座申請・停止解除・本番運用は行わない。",
        "",
        "本資料と統合PRのマージは**仕様承認・実環境試験承認ではない**。",
        "原議、G1の実証、本人の明示決定、Q110のMODULE/PHASEの個別受入が",
        "成立しない限り、**すべてNO_GO**。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    print(render())


if __name__ == "__main__":
    main()
