"""FINAL-AUTO: complete H1 -> audited news -> two AIs -> virtual signal.

Integrates existing strict ResearchRoleRegistry and saved independent
two-model ledgers with the new separately approved JPY reservation book.
No model call until the caller's risk, calendar, clock, spread, carry and
budget evidence are ALL ready. No silent retry of possibly charged requests.
"""
from __future__ import annotations

import hashlib
from datetime import datetime,timezone
from pathlib import Path

from research import final_demo_periodic as period
from research import final_demo_periodic_ai as ai
from research import final_paper_auto_budget as budget
from research import final_paper_engine as paper
from research.offline_backtest import InputError


def decisions(state:dict,captures:Path|None,bundles:list[Path],
              root:Path,now:datetime,*,policy:dict,
              analyst_model:str,reviewer_model:str
              )->tuple[list[dict],list[str],list[str],int]:
    """Returns signals, considered H1 keys, new reserve receipts, paid calls.

    The caller MUST atomically append all receipt SHA IDs to its normal
    journal after this completes, or the next resume fails accounting.
    """
    if captures is None or not bundles:
        return [],[],[],0
    try:
        source=period._read_h1(captures,now)
    except InputError:
        return [],[],[],0
    folder=root/"auto_ai_research"
    ledger_folder=root/"auto_budget_journal"
    if (not folder.is_dir() or folder.is_symlink()
            or not ledger_folder.is_dir() or ledger_folder.is_symlink()):
        raise InputError("FINAL_AUTO_LEDGER_FOLDERS_UNSAFE")
    # Cannot dispatch if previously completed requests are absent from the
    # durable paper journal, or a network-uncertain intent remains pending.
    prior_receipts=state.get("auto_budget_reservation_receipts",[])
    budget.check(policy,ledger_folder,journal_reserve_shas=prior_receipts)
    result=[]
    seen=[]
    receipts=[]
    used=0
    for pair in paper.PAIRS:
        bar=source["captures"][period.PAIRS[pair]]["candles"][-1][
            "server_epoch"]
        key=f"{pair}:{bar}"
        if key in state["processed_h1_keys"]:
            continue
        packet=period.run(captures,bundles,pair,root/"unused.json",
                          now=now,output_must_be_new=False)
        if packet["macro_coverage_complete_research_only"] is not True:
            seen.append(key)
            continue
        identity=ai._identity(packet,analyst_model,reviewer_model)
        packet_sha=identity["packet_sha256"]
        stamp=now.strftime("%Y%m%d_%H%M%S")
        ledger=folder/(
            f"ai_{paper.SYMS[paper.PAIRS.index(pair)]}_{bar}_{stamp}.json")
        if ledger.exists() or ledger.is_symlink():
            # A previously billed result that did not enter the paper
            # journal is not an opportunity to retry.
            raise InputError("FINAL_AUTO_POTENTIALLY_BILLED_LEDGER_ALREADY_EXISTS")
        try:
            reservation=budget.reserve(
                policy,ledger_folder,
                journal_reserve_shas=prior_receipts+receipts,
                pair=pair,packet_sha=packet_sha,now=now)
        except InputError as exc:
            if exc.args==("FINAL_BUDGET_LIMIT_OR_REPEAT_REACHED",):
                # An exhausted cap means HOLD, not a new paid call.
                seen.append(key)
                continue
            raise
        # RESERVE is durable before any external request. On failure the
        # intent remains pending and next run MUST stop for human review.
        result_ai=ai.run(
            captures,bundles,pair,ledger,
            analyst_model=analyst_model,reviewer_model=reviewer_model,
            allow_external_api=True,max_api_calls=2,now=now)
        if (result_ai.get("stage")!="COMPLETE"
                or result_ai.get("paid_calls_this_run")!=2
                or result_ai.get("packet_sha256_local_only")!=packet_sha
                or result_ai.get("status")!=
                    "PERIODIC_AI_TWO_MODELS_REVIEWED_RESEARCH_NO_GO"):
            raise InputError("FINAL_AUTO_PARTIAL_OR_UNMATCHED_BILLED_RESULT")
        budget.settle(ledger_folder,reserve_sha=reservation,
                      ledger=ledger,now=datetime.now(timezone.utc))
        receipts.append(reservation)
        used+=2
        sig={
            "id":hashlib.sha256((
                pair+":"+str(bar)+":"+packet_sha+":"+reservation
            ).encode("ascii")).hexdigest(),
            "pair":pair,
            "action":result_ai["model_action_research_only"],
            "verdict":result_ai["model_verdict"],
            # No same-quote lookahead: reviewed after actual AI completion.
            "reviewed_epoch":int(datetime.now(timezone.utc).timestamp()),
            "atr14":str(packet["technical"]["atr14"]),
            "packet_sha256":packet_sha,
        }
        if not paper._valid_signal(sig):
            raise InputError("FINAL_AUTO_MODEL_SIGNAL_CONTRACT_INVALID")
        result.append(sig)
        seen.append(key)
    return result,seen,receipts,used
