"""AtlasQuant model-specific Paper research ledger.

Consumes explicit setup candidates frozen by the source ICT detector. It keeps
one research episode per model structure/zone and evaluates the global context
gate at capture time. Paper execution uses the exact source timeframe when that
frame is explicitly supported and cached (currently M15 and H1). Unsupported
or missing execution frames fail closed instead of being substituted by M15.
It never places real orders and never infers a setup from outcomes.
"""
from __future__ import annotations

import json
import math
from typing import Any, Mapping

import pandas as pd

from paper_trading_v112 import (
    PAPER_COLUMNS,
    TARGET_R,
    _close_open,
    _fill_entry,
    _make_wait_entry,
    evaluate_pair_checklist,
    normalize_m15,
)

MODEL_PAPER_VERSION="ATLASQUANT_MODEL_PAPER_V1"
MODEL_ATTRIBUTION="SOURCE_MODEL_EXPLICIT"
MODEL_EXTRA_COLUMNS=[
    "candidate_id","episode_id","source_model","source_timeframe",
    "candidate_captured_at","candidate_status","candidate_score",
    "model_evidence_json","context_gate_passed","context_gate_state",
    "context_hard_blocks","context_soft_blocks","candidate_observation",
    "execution_timeframe","timeframe_alignment_passed","timeframe_alignment_reason",
]
MODEL_PAPER_COLUMNS=PAPER_COLUMNS+[
    c for c in MODEL_EXTRA_COLUMNS if c not in PAPER_COLUMNS
]
TERMINAL_STATUSES={"CLOSED","BLOCKED_CONTEXT","BLOCKED_DATA","BLOCKED_TIMEFRAME"}


def _mapping(value:Any)->dict[str,Any]:
    return dict(value) if isinstance(value,Mapping) else {}


def _as_utc(value:Any)->pd.Timestamp|None:
    try:
        ts=pd.to_datetime(value,utc=True,errors="coerce")
        return None if pd.isna(ts) else pd.Timestamp(ts)
    except Exception:
        return None


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def normalize_model_paper(frame:pd.DataFrame|None)->pd.DataFrame:
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=MODEL_PAPER_COLUMNS)
    out=frame.copy()
    for col in MODEL_PAPER_COLUMNS:
        if col not in out.columns:
            out[col]=None
    return out[MODEL_PAPER_COLUMNS].copy()


def _inputs_by_pair(inputs:Mapping[str,Any]|None)->dict[str,dict[str,Any]]:
    out={}
    for raw in list(_mapping(inputs).get("pairs",[]) or []):
        if not isinstance(raw,Mapping):
            continue
        pair=str(raw.get("Par") or raw.get("pair") or "").strip().upper()
        if pair:
            out[pair]=dict(raw)
    return out


def _scanner_rows(scanner:Mapping[str,Any]|None)->dict[str,dict[str,Any]]:
    raw=_mapping(_mapping(scanner).get("resultados"))
    return {str(k).strip().upper():_mapping(v) for k,v in raw.items()}


def _map_rows(master:Mapping[str,Any]|None)->dict[str,dict[str,Any]]:
    raw=_mapping(_mapping(master).get("contexts"))
    return {str(k).strip().upper():_mapping(v) for k,v in raw.items()}


MODEL_PAPER_EXECUTION_PROFILES={
    "M15":{"cache_key":"m15","bar_minutes":15,"max_hold_bars":96},
    "H1":{"cache_key":"h1","bar_minutes":60,"max_hold_bars":48},
}


def _execution_profile(timeframe:Any)->dict[str,Any]|None:
    tf=str(timeframe or "").strip().upper()
    profile=MODEL_PAPER_EXECUTION_PROFILES.get(tf)
    return dict(profile) if isinstance(profile,Mapping) else None


def _execution_frame(
    scanner_pair:Mapping[str,Any]|None,
    timeframe:Any,
)->pd.DataFrame:
    profile=_execution_profile(timeframe)
    if profile is None:
        return pd.DataFrame(columns=["datetime","open","high","low","close"])
    tec=_mapping(_mapping(scanner_pair).get("tecnico"))
    cache=_mapping(tec.get("cache_v110"))
    return normalize_m15(cache.get(str(profile["cache_key"]),[]))


def _m15(scanner_pair:Mapping[str,Any]|None)->pd.DataFrame:
    return _execution_frame(scanner_pair,"M15")


def current_setup_candidates(scanner:Mapping[str,Any]|None)->list[dict[str,Any]]:
    rows=[]
    for pair,scanner_pair in _scanner_rows(scanner).items():
        tec=_mapping(scanner_pair.get("tecnico"))
        ict=_mapping(tec.get("ict"))
        pack=_mapping(ict.get("setup_candidates"))
        for raw in list(pack.get("candidates",[]) or []):
            if not isinstance(raw,Mapping):
                continue
            row=dict(raw)
            row["pair"]=str(row.get("pair") or pair).strip().upper()
            if not row.get("research_candidate"):
                continue
            if not str(row.get("setup_id") or "").strip():
                continue
            if not str(row.get("episode_id") or "").strip():
                continue
            rows.append(row)
    rows.sort(
        key=lambda x:(
            str(x.get("captured_at") or ""),
            str(x.get("pair") or ""),
            str(x.get("setup_id") or ""),
        )
    )
    return rows


def _synthetic_input(
    base_row:Mapping[str,Any]|None,
    candidate:Mapping[str,Any],
)->dict[str,Any]:
    row=dict(base_row or {})
    side=str(candidate.get("side") or "").strip().upper()
    row["Direção"]="COMPRA" if side=="BUY" else "VENDA" if side=="SELL" else side
    row["setup_id"]=str(candidate.get("setup_id") or "").strip()
    return row


def _block_row(
    candidate:Mapping[str,Any],
    checklist:Mapping[str,Any]|None,
    *,
    status:str,
    now:pd.Timestamp,
)->dict[str,Any]:
    chk=dict(checklist or {})
    decision=_mapping(chk.get("decision"))
    row={col:None for col in MODEL_PAPER_COLUMNS}
    row.update({
        "trade_id":str(candidate.get("episode_id") or ""),
        "signal_id":str(candidate.get("episode_id") or ""),
        "pair":str(candidate.get("pair") or "").strip().upper(),
        "side":str(candidate.get("side") or "").strip().upper(),
        "setup_id":str(candidate.get("setup_id") or "").strip(),
        "setup_attribution":MODEL_ATTRIBUTION,
        "status":status,
        "result":"",
        "signal_time":str(candidate.get("captured_at") or ""),
        "signal_candle_time":None,
        "target_rr":TARGET_R,
        "score_master":chk.get("score_master"),
        "quality":chk.get("quality"),
        "rank_index":chk.get("rank_index"),
        "h4":chk.get("h4"),
        "h1":chk.get("h1"),
        "m15":chk.get("m15"),
        "ict_readiness":chk.get("ict_readiness"),
        "institutional_readiness":chk.get("institutional_readiness"),
        "gate":chk.get("gate"),
        "gate_score":chk.get("gate_score"),
        "adr_used_pct":chk.get("adr_used_pct"),
        "event_risk":chk.get("event_risk"),
        "technical_age_min":chk.get("technical_age_min"),
        "map_age_min":chk.get("map_age_min"),
        "data_sufficient":bool(chk.get("data_sufficient",False)),
        "data_quality_pct":chk.get("data_quality_pct"),
        "d1_regime":chk.get("d1_regime",""),
        "w1_regime":chk.get("w1_regime",""),
        "active_session":chk.get("active_session",""),
        "checklist_passed":bool(chk.get("all_checks_passed",False)),
        "checklist_note":"Candidato observado, mas não qualificado para simulação pelo contexto global.",
        "created_at":now.isoformat(),
        "updated_at":now.isoformat(),
        "engine_version":MODEL_PAPER_VERSION,
        "candidate_id":str(candidate.get("candidate_id") or ""),
        "episode_id":str(candidate.get("episode_id") or ""),
        "source_model":str(candidate.get("source_model") or ""),
        "source_timeframe":str(candidate.get("source_timeframe") or ""),
        "candidate_captured_at":str(candidate.get("captured_at") or ""),
        "candidate_status":str(candidate.get("status") or ""),
        "candidate_score":candidate.get("score"),
        "model_evidence_json":json.dumps(candidate.get("evidence",{}),ensure_ascii=False,sort_keys=True,default=str),
        "context_gate_passed":bool(chk.get("all_checks_passed",False)),
        "context_gate_state":str(decision.get("state") or ""),
        "context_hard_blocks":" | ".join(str(x) for x in list(decision.get("hard_blocks",[]) or [])),
        "context_soft_blocks":" | ".join(str(x) for x in list(decision.get("soft_blocks",[]) or [])),
        "candidate_observation":True,
        "execution_timeframe":(
            str(candidate.get("source_timeframe") or "").strip().upper()
            if _execution_profile(candidate.get("source_timeframe")) is not None
            else ""
        ),
        "timeframe_alignment_passed":_execution_profile(candidate.get("source_timeframe")) is not None,
        "timeframe_alignment_reason":(
            "SOURCE_EQUALS_EXECUTION"
            if _execution_profile(candidate.get("source_timeframe")) is not None
            else "EXECUTION_FRAME_NOT_AVAILABLE:"+str(candidate.get("source_timeframe") or "").strip().upper()
        ),
    })
    return row


def _qualified_row(
    candidate:Mapping[str,Any],
    checklist:Mapping[str,Any],
    frame:pd.DataFrame,
    *,
    now:pd.Timestamp,
    execution_timeframe:str,
    bar_minutes:int,
)->dict[str,Any]:
    base=_make_wait_entry(checklist,frame,now=now,bar_minutes=bar_minutes)
    if not base:
        return _block_row(candidate,checklist,status="BLOCKED_DATA",now=now)
    captured=_as_utc(candidate.get("captured_at"))
    if captured is None:
        return _block_row(candidate,checklist,status="BLOCKED_DATA",now=now)
    decision=_mapping(checklist.get("decision"))
    base.update({
        "trade_id":str(candidate.get("episode_id") or ""),
        "signal_id":str(candidate.get("episode_id") or ""),
        "setup_id":str(candidate.get("setup_id") or "").strip(),
        "setup_attribution":MODEL_ATTRIBUTION,
        "checklist_note":(
            "Candidato explícito do modelo + contexto global qualificado; "
            f"Paper de pesquisa aguardando candle {execution_timeframe} posterior."
        ),
        "engine_version":MODEL_PAPER_VERSION,
        "candidate_id":str(candidate.get("candidate_id") or ""),
        "episode_id":str(candidate.get("episode_id") or ""),
        "source_model":str(candidate.get("source_model") or ""),
        "source_timeframe":str(candidate.get("source_timeframe") or ""),
        "candidate_captured_at":captured.isoformat(),
        "candidate_status":str(candidate.get("status") or ""),
        "candidate_score":candidate.get("score"),
        "model_evidence_json":json.dumps(candidate.get("evidence",{}),ensure_ascii=False,sort_keys=True,default=str),
        "context_gate_passed":True,
        "context_gate_state":str(decision.get("state") or ""),
        "context_hard_blocks":"",
        "context_soft_blocks":"",
        "candidate_observation":True,
        "execution_timeframe":execution_timeframe,
        "timeframe_alignment_passed":True,
        "timeframe_alignment_reason":"SOURCE_EQUALS_EXECUTION",
    })
    return base


def summarize_model_paper(frame:pd.DataFrame|None)->dict[str,Any]:
    d=normalize_model_paper(frame)
    if d.empty:
        closed=d
    else:
        closed=d[d["status"].astype(str).str.upper().eq("CLOSED")].copy()
    rr=pd.to_numeric(closed.get("realized_r"),errors="coerce").dropna() if not closed.empty else pd.Series(dtype=float)
    rr=rr[rr.map(lambda x:math.isfinite(float(x)))] if len(rr) else rr

    by_setup={}
    if not d.empty:
        for setup_id,g in d.groupby(d["setup_id"].fillna("").astype(str),dropna=False):
            setup=str(setup_id).strip()
            if not setup:
                continue
            gc=g[g["status"].astype(str).str.upper().eq("CLOSED")].copy()
            gr=pd.to_numeric(gc.get("realized_r"),errors="coerce").dropna()
            gr=gr[gr.map(lambda x:math.isfinite(float(x)))] if len(gr) else gr
            wins=int((gc["result"].astype(str).str.upper()=="WIN").sum()) if not gc.empty else 0
            losses=int((gc["result"].astype(str).str.upper()=="LOSS").sum()) if not gc.empty else 0
            gross_profit=float(gr[gr>0].sum()) if len(gr) else 0.0
            gross_loss=float(-gr[gr<0].sum()) if len(gr) else 0.0
            by_setup[setup]={
                "candidates":int(len(g)),
                "blocked_context":int(g["status"].astype(str).str.upper().eq("BLOCKED_CONTEXT").sum()),
                "blocked_data":int(g["status"].astype(str).str.upper().eq("BLOCKED_DATA").sum()),
                "blocked_timeframe":int(g["status"].astype(str).str.upper().eq("BLOCKED_TIMEFRAME").sum()),
                "pending":int(g["status"].astype(str).str.upper().eq("WAIT_ENTRY").sum()),
                "open":int(g["status"].astype(str).str.upper().eq("OPEN").sum()),
                "closed":int(len(gc)),
                "wins":wins,
                "losses":losses,
                "win_rate_pct":round(100.0*wins/max(wins+losses,1),1),
                "net_r":round(float(gr.sum()) if len(gr) else 0.0,3),
                "avg_r":round(float(gr.mean()) if len(gr) else 0.0,3),
                "profit_factor_r":None if gross_loss<=0 else round(gross_profit/gross_loss,3),
                "explicit_source_model_only":True,
            }

    by_timeframe={}
    if not d.empty and "source_timeframe" in d.columns:
        for timeframe,g in d.groupby(d["source_timeframe"].fillna("").astype(str).str.upper(),dropna=False):
            tf=str(timeframe).strip() or "(SEM TIMEFRAME)"
            gc=g[g["status"].astype(str).str.upper().eq("CLOSED")].copy()
            gr=pd.to_numeric(gc.get("realized_r"),errors="coerce").dropna()
            gr=gr[gr.map(lambda x:math.isfinite(float(x)))] if len(gr) else gr
            wins_tf=int((gc["result"].astype(str).str.upper()=="WIN").sum()) if not gc.empty else 0
            losses_tf=int((gc["result"].astype(str).str.upper()=="LOSS").sum()) if not gc.empty else 0
            by_timeframe[tf]={
                "candidates":int(len(g)),
                "blocked_context":int(g["status"].astype(str).str.upper().eq("BLOCKED_CONTEXT").sum()),
                "blocked_data":int(g["status"].astype(str).str.upper().eq("BLOCKED_DATA").sum()),
                "blocked_timeframe":int(g["status"].astype(str).str.upper().eq("BLOCKED_TIMEFRAME").sum()),
                "pending":int(g["status"].astype(str).str.upper().eq("WAIT_ENTRY").sum()),
                "open":int(g["status"].astype(str).str.upper().eq("OPEN").sum()),
                "closed":int(len(gc)),
                "wins":wins_tf,
                "losses":losses_tf,
                "net_r":round(float(gr.sum()) if len(gr) else 0.0,3),
            }

    by_session={}
    if not closed.empty and "active_session" in closed.columns:
        for session,g in closed.groupby(closed["active_session"].fillna("").astype(str),dropna=False):
            name=str(session).strip() or "(SEM SESSÃO)"
            gr=pd.to_numeric(g["realized_r"],errors="coerce").dropna()
            gr=gr[gr.map(lambda x:math.isfinite(float(x)))] if len(gr) else gr
            by_session[name]={
                "trades":int(len(g)),
                "net_r":round(float(gr.sum()) if len(gr) else 0.0,3),
                "avg_r":round(float(gr.mean()) if len(gr) else 0.0,3),
            }

    wins=int((closed["result"].astype(str).str.upper()=="WIN").sum()) if not closed.empty else 0
    losses=int((closed["result"].astype(str).str.upper()=="LOSS").sum()) if not closed.empty else 0
    return {
        "version":MODEL_PAPER_VERSION,
        "candidates_total":int(len(d)),
        "blocked_context":int(d["status"].astype(str).str.upper().eq("BLOCKED_CONTEXT").sum()) if not d.empty else 0,
        "blocked_data":int(d["status"].astype(str).str.upper().eq("BLOCKED_DATA").sum()) if not d.empty else 0,
        "blocked_timeframe":int(d["status"].astype(str).str.upper().eq("BLOCKED_TIMEFRAME").sum()) if not d.empty else 0,
        "pending_entries":int(d["status"].astype(str).str.upper().eq("WAIT_ENTRY").sum()) if not d.empty else 0,
        "open_positions":int(d["status"].astype(str).str.upper().eq("OPEN").sum()) if not d.empty else 0,
        "closed_trades":int(len(closed)),
        "wins":wins,
        "losses":losses,
        "breakeven":int((closed["result"].astype(str).str.upper()=="BREAKEVEN").sum()) if not closed.empty else 0,
        "win_rate_pct":round(100.0*wins/max(wins+losses,1),1),
        "net_r":round(float(rr.sum()) if len(rr) else 0.0,3),
        "avg_r":round(float(rr.mean()) if len(rr) else 0.0,3),
        "by_setup":by_setup,
        "by_timeframe":by_timeframe,
        "by_session":by_session,
        "setup_inference_used":False,
        "automatic_promotion":False,
        "automatic_execution":False,
        "real_orders_enabled":False,
    }


def run_model_paper_cycle(
    inputs:Mapping[str,Any]|None,
    scanner:Mapping[str,Any]|None,
    master:Mapping[str,Any]|None,
    ledger:pd.DataFrame|None=None,
    *,
    now:pd.Timestamp|None=None,
)->tuple[pd.DataFrame,dict[str,Any]]:
    now=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now=now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    d=normalize_model_paper(ledger)
    scanner_by_pair=_scanner_rows(scanner)
    inputs_by_pair=_inputs_by_pair(inputs)
    map_by_pair=_map_rows(master)

    opened=0
    closed_count=0
    if not d.empty:
        updated=[]
        for _,series in d.iterrows():
            row=series.copy()
            status=str(row.get("status") or "").upper()
            if status in {"WAIT_ENTRY","OPEN"}:
                source_tf=str(row.get("source_timeframe") or "M15").strip().upper()
                profile=_execution_profile(source_tf)
                if profile is None:
                    blocked_row=row.to_dict()
                    blocked_row["status"]="BLOCKED_TIMEFRAME"
                    blocked_row["execution_timeframe"]=""
                    blocked_row["timeframe_alignment_passed"]=False
                    blocked_row["timeframe_alignment_reason"]="EXECUTION_FRAME_NOT_AVAILABLE:"+source_tf
                    blocked_row["checklist_note"]="Paper preservado sem execução: timeframe de origem ainda não possui executor exato."
                    blocked_row["updated_at"]=now.isoformat()
                    updated.append(blocked_row)
                    continue
                frame=_execution_frame(
                    scanner_by_pair.get(str(row.get("pair") or "").upper(),{}),
                    source_tf,
                )
                if frame.empty:
                    waiting=row.to_dict()
                    waiting["execution_timeframe"]=source_tf
                    waiting["timeframe_alignment_passed"]=False
                    waiting["timeframe_alignment_reason"]="EXECUTION_FRAME_EMPTY:"+source_tf
                    waiting["checklist_note"]="Aguardando candles do mesmo timeframe de execução; nenhum timeframe inferior é usado como substituto."
                    waiting["updated_at"]=now.isoformat()
                    updated.append(waiting)
                    continue
                before=status
                first=_fill_entry(row,frame,now=now)
                if before=="WAIT_ENTRY" and str(first.get("status") or "").upper()=="OPEN":
                    opened+=1
                second=_close_open(
                    pd.Series(first),
                    frame,
                    now=now,
                    bar_minutes=int(profile["bar_minutes"]),
                    max_hold_bars=int(profile["max_hold_bars"]),
                )
                if str(first.get("status") or "").upper()=="OPEN" and str(second.get("status") or "").upper()=="CLOSED":
                    closed_count+=1
                updated.append(second)
            else:
                updated.append(row.to_dict())
        d=normalize_model_paper(pd.DataFrame(updated))

    existing_episodes=set(
        d["episode_id"].fillna("").astype(str)
    ) if not d.empty else set()
    observed=0
    qualified=0
    blocked=0

    for candidate in current_setup_candidates(scanner):
        episode=str(candidate.get("episode_id") or "").strip()
        if not episode or episode in existing_episodes:
            continue
        pair=str(candidate.get("pair") or "").strip().upper()
        base_input=inputs_by_pair.get(pair,{})
        synthetic=_synthetic_input(base_input,candidate)
        scanner_pair=scanner_by_pair.get(pair,{})
        map_ctx=map_by_pair.get(pair,{})
        source_tf=str(candidate.get("source_timeframe") or "").strip().upper()
        profile=_execution_profile(source_tf)
        checklist=evaluate_pair_checklist(
            pair,
            synthetic,
            scanner_pair,
            map_ctx,
            now=now,
            execution_timeframe=source_tf or "UNSUPPORTED",
        )
        frame=_execution_frame(scanner_pair,source_tf)
        observed+=1
        if profile is None:
            row=_block_row(candidate,checklist,status="BLOCKED_TIMEFRAME",now=now)
            blocked+=1
        elif frame.empty:
            row=_block_row(candidate,checklist,status="BLOCKED_DATA",now=now)
            row["execution_timeframe"]=source_tf
            row["timeframe_alignment_passed"]=False
            row["timeframe_alignment_reason"]="EXECUTION_FRAME_EMPTY:"+source_tf
            row["checklist_note"]="Candidato alinhado somente pode avançar com candles do mesmo timeframe; frame exato indisponível."
            blocked+=1
        elif checklist.get("all_checks_passed"):
            row=_qualified_row(
                candidate,
                checklist,
                frame,
                now=now,
                execution_timeframe=source_tf,
                bar_minutes=int(profile["bar_minutes"]),
            )
            if str(row.get("status") or "").upper()=="WAIT_ENTRY":
                qualified+=1
            else:
                blocked+=1
        else:
            row=_block_row(candidate,checklist,status="BLOCKED_CONTEXT",now=now)
            blocked+=1
        d=pd.concat([d,pd.DataFrame([row])],ignore_index=True)
        existing_episodes.add(episode)

    d=normalize_model_paper(d)
    summary=summarize_model_paper(d)
    cycle={
        "version":MODEL_PAPER_VERSION,
        "ran_at":now.isoformat(),
        "new_candidates_observed":observed,
        "new_qualified":qualified,
        "new_blocked":blocked,
        "entries_opened":opened,
        "trades_closed":closed_count,
        **summary,
    }
    return d,cycle


__all__=[
    "MODEL_PAPER_VERSION",
    "MODEL_ATTRIBUTION",
    "MODEL_PAPER_COLUMNS",
    "normalize_model_paper",
    "MODEL_PAPER_EXECUTION_PROFILES",
    "current_setup_candidates",
    "summarize_model_paper",
    "run_model_paper_cycle",
]
