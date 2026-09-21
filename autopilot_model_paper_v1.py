"""AtlasQuant automatic model-specific Paper cycle.

Reuses already persisted scanner/input/Market Map data. No market-data provider
is called here. The output is a separate runtime ledger so generic Paper
behavior stays untouched.
"""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

import autopilot_v107 as base
from atlasquant_model_paper import MODEL_PAPER_EXECUTION_PROFILES, run_model_paper_cycle, summarize_model_paper
from paper_friction_v116 import apply_paper_friction, summarize_net

MODEL_PAPER_CSV_PATH="dados/model_paper_trades_v1.csv"
MODEL_PAPER_SUMMARY_PATH="dados/model_paper_summary_v1.json"


def _model_paper_cycle()->tuple[bool,dict[str,Any],list[str]]:
    errors=[]

    inputs,err=base.gh_get_json(base.INPUT_PATH,{})
    if err:
        errors.append("Model Paper inputs: "+str(err))
    scanner,err=base.gh_get_json(base.SCANNER_PATH,{})
    if err:
        errors.append("Model Paper scanner: "+str(err))
    master,err=base.gh_get_json(base.MASTER_PATH,{})
    if err:
        errors.append("Model Paper Market Map: "+str(err))
    existing,err=base.gh_get_csv(MODEL_PAPER_CSV_PATH)
    if err:
        if "404" not in str(err):
            errors.append("Model Paper ledger: "+str(err))
        existing=pd.DataFrame()

    try:
        updated,cycle=run_model_paper_cycle(
            inputs if isinstance(inputs,dict) else {},
            scanner if isinstance(scanner,dict) else {},
            master if isinstance(master,dict) else {},
            existing,
            now=base.utcnow(),
        )
    except Exception as exc:
        return False,{},errors+[f"Model Paper engine: {type(exc).__name__}: {exc}"]

    costed=apply_paper_friction(updated)
    ok1,err1=base.gh_put_csv(
        MODEL_PAPER_CSV_PATH,
        costed,
        "AtlasQuant Model Paper: atualiza ledger prospectivo por operacional",
    )
    if not ok1:
        errors.append("Salvar Model Paper ledger: "+str(err1))

    summary=summarize_model_paper(costed)
    friction=summarize_net(costed)
    summary["last_cycle"]=cycle
    summary["friction"]=friction
    summary["gross_r_before_friction"]=friction.get("gross_r",0.0)
    summary["friction_r"]=friction.get("friction_r",0.0)
    summary["net_r_after_friction"]=friction.get("net_r",0.0)
    supported_timeframes=list(MODEL_PAPER_EXECUTION_PROFILES.keys())
    summary["execution_contract"]={
        "supported_timeframes":supported_timeframes,
        "exact_execution_frame_required":True,
        "lower_timeframe_substitution":False,
    }
    summary["safety"]={
        "real_orders":False,
        "broker_connection":False,
        "additional_market_data_calls":False,
        "source":"scanner cache + runtime context",
        "setup_inference_from_outcome":False,
        "auto_strategy_selection":False,
        "auto_promotion":False,
        "supported_execution_timeframes":supported_timeframes,
        "exact_execution_frame_required":True,
        "lower_timeframe_substitution":False,
    }

    ok2,err2=base.gh_put_json(
        MODEL_PAPER_SUMMARY_PATH,
        summary,
        "AtlasQuant Model Paper: atualiza resumo por operacional",
    )
    if not ok2:
        errors.append("Salvar Model Paper resumo: "+str(err2))

    status,_=base.gh_get_json(base.STATUS_PATH,{})
    status=status if isinstance(status,dict) else {}
    status["model_paper_v1"]={
        "enabled":True,
        "real_orders":False,
        "supported_execution_timeframes":list(MODEL_PAPER_EXECUTION_PROFILES.keys()),
        "exact_execution_frame_required":True,
        "lower_timeframe_substitution":False,
        "candidates_total":summary.get("candidates_total",0),
        "blocked_context":summary.get("blocked_context",0),
        "blocked_data":summary.get("blocked_data",0),
        "blocked_timeframe":summary.get("blocked_timeframe",0),
        "pending_entries":summary.get("pending_entries",0),
        "open_positions":summary.get("open_positions",0),
        "closed_trades":summary.get("closed_trades",0),
        "wins":summary.get("wins",0),
        "losses":summary.get("losses",0),
        "win_rate_pct":summary.get("win_rate_pct",0.0),
        "net_r":summary.get("net_r",0.0),
        "net_r_after_friction":summary.get("net_r_after_friction",0.0),
        "by_setup":summary.get("by_setup",{}),
        "by_session":summary.get("by_session",{}),
        "last_cycle":cycle,
        "errors":errors[:10],
    }
    existing_errors=list(status.get("errors",[]) or [])
    status["errors"]=(existing_errors+errors)[:20]
    ok3,err3=base.gh_put_json(
        base.STATUS_PATH,
        status,
        "AtlasQuant: status do Model Paper por operacional",
    )
    if not ok3:
        errors.append("Salvar status Model Paper: "+str(err3))

    return bool(ok1 and ok2 and ok3),summary,errors


def main()->int:
    ok,summary,errors=_model_paper_cycle()
    print(json.dumps({
        "model_paper_v1":summary,
        "model_paper_ok":ok,
        "model_paper_errors":errors,
    },ensure_ascii=False,indent=2,default=str))
    return 0 if ok else 1


if __name__=="__main__":
    raise SystemExit(main())
