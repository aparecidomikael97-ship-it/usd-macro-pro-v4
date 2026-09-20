"""Backtest intelligence adapters for AtlasQuant.

Converts completed historical trades into:
- mechanical outcome explanations;
- optional point-in-time decision diagnosis when historical context is supplied;
- an operational passport summary.

The adapter never fills missing macro/news/context with invented values.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from typing import Any, Iterable, Mapping

from atlasquant_operational_backtest import summarize_results
from atlasquant_operational_passport import OperationalPassportInput, build_operational_passport
from atlasquant_post_trade_diagnosis import (
    DecisionSnapshot,
    DuringTradeEvent,
    TradeOutcome,
    diagnose_trade,
)

SCHEMA="ATLASQUANT_BACKTEST_INTELLIGENCE_V1"

_CONTEXT_FIELDS=(
    "macro_alignment",
    "technical_confirmation",
    "liquidity_confirmation",
    "regime_fit",
    "known_high_impact_event",
    "data_quality_pct",
    "plan_followed",
)

_TRUE={"1","true","yes","sim","y","on","ok"}
_FALSE={"0","false","no","nao","não","n","off"}

def _text(value:Any)->str:
    return str(value or "").strip()

def _finite_or_none(value:Any)->float|None:
    try:
        out=float(value)
        return out if isfinite(out) else None
    except Exception:
        return None

def _bool_or_none(value:Any)->bool|None:
    if isinstance(value,bool):
        return value
    raw=_text(value).casefold()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    return None

def _timestamp(value:Any)->datetime|None:
    if value in (None,""):
        return None
    try:
        # pandas-free conversion for ISO-like values.
        text=str(value)
        if text.endswith("Z"):
            text=text[:-1]+"+00:00"
        dt=datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def _macro_alignment(value:Any)->int|None:
    if isinstance(value,bool):
        return None
    try:
        number=int(value)
        if number in {-1,0,1}:
            return number
    except Exception:
        pass
    raw=_text(value).casefold()
    if raw in {"aligned","alinhado","favor","supportive","bullish","buy"}:
        return 1
    if raw in {"conflict","conflito","contra","adverse","bearish","sell"}:
        return -1
    if raw in {"neutral","neutro","unknown","incerto"}:
        return 0
    return None

def _mechanical_explanation(record:Mapping[str,Any])->dict[str,str]:
    status=_text(record.get("status")).upper()
    outcome=_text(record.get("outcome")).upper()
    if status=="TARGET":
        return {
            "code":"TARGET_HIT",
            "summary":"GAIN mecânico: o preço tocou o alvo definido antes de tocar o stop.",
        }
    if status=="STOP":
        return {
            "code":"STOP_HIT",
            "summary":"LOSS mecânico: o preço tocou o stop definido antes de alcançar o alvo.",
        }
    if status=="AMBIGUOUS_SAME_BAR_STOP_FIRST":
        return {
            "code":"OHLC_AMBIGUOUS",
            "summary":"LOSS conservador: stop e alvo apareceram no mesmo candle OHLC; a ordem intrabar é desconhecida.",
        }
    if status=="TIME_EXIT":
        return {
            "code":"TIME_EXIT",
            "summary":f"Saída por tempo: o trade terminou como {outcome or 'resultado indefinido'} no limite de permanência.",
        }
    if outcome=="NO_TRADE":
        return {
            "code":"NO_TRADE",
            "summary":"Não houve trade executado nesta linha; não existe gain/loss para diagnosticar.",
        }
    return {
        "code":status or "UNKNOWN_MECHANICS",
        "summary":"O resultado mecânico não possui classificação mais específica neste registro.",
    }

def context_coverage(record:Mapping[str,Any])->dict[str,object]:
    available=[]
    missing=[]
    parsed:dict[str,object]={}
    for field in _CONTEXT_FIELDS:
        raw=record.get(field)
        if field=="macro_alignment":
            value=_macro_alignment(raw)
        elif field=="data_quality_pct":
            value=_finite_or_none(raw)
            if value is not None and not 0<=value<=100:
                value=None
        else:
            value=_bool_or_none(raw)
        if value is None:
            missing.append(field)
        else:
            available.append(field)
            parsed[field]=value
    pct=round(100.0*len(available)/len(_CONTEXT_FIELDS),1)
    return {
        "available_fields":available,
        "missing_fields":missing,
        "coverage_pct":pct,
        "parsed":parsed,
        "complete":not missing,
    }

def _trade_id(record:Mapping[str,Any], index:int=0)->str:
    supplied=_text(record.get("trade_id"))
    if supplied:
        return supplied
    pair=_text(record.get("pair")) or "ASSET"
    setup=_text(record.get("setup")) or "SETUP"
    stamp=_text(record.get("signal_time")) or str(index)
    return f"{pair}|{setup}|{stamp}"

def _event_from_record(record:Mapping[str,Any])->DuringTradeEvent|None:
    label=_text(record.get("event_label"))
    event_time=_timestamp(record.get("event_time"))
    impact=_text(record.get("event_impact"))
    if not label or event_time is None or not impact:
        return None
    known=_bool_or_none(record.get("event_known_before_entry"))
    return DuringTradeEvent(
        event_time=event_time,
        label=label,
        impact=impact,
        known_before_entry=bool(known),
    )

def diagnose_backtest_record(record:Mapping[str,Any], *, index:int=0)->dict[str,object]:
    row=dict(record or {})
    mechanics=_mechanical_explanation(row)
    coverage=context_coverage(row)
    outcome=_text(row.get("outcome")).upper()
    if outcome not in {"GAIN","LOSS","BREAKEVEN"}:
        return {
            "schema":SCHEMA,
            "trade_id":_trade_id(row,index),
            "outcome":outcome or "NO_TRADE",
            "mechanical":mechanics,
            "context_coverage_pct":coverage["coverage_pct"],
            "missing_context":coverage["missing_fields"],
            "context_diagnosis_available":False,
            "decision_outcome_relation":"NOT_APPLICABLE",
            "probable_explanations":[],
            "lookahead_used":False,
            "causality_claimed":False,
            "interpretation":"Sem trade executado, o AtlasQuant não inventa causa de gain/loss.",
        }

    # Mechanical explanation is always available. Rich contextual diagnosis is
    # only produced when every required field exists point-in-time.
    if not coverage["complete"]:
        explanations=[{
            "code":mechanics["code"],
            "detail":mechanics["summary"],
            "confidence":"HIGH" if mechanics["code"]!="OHLC_AMBIGUOUS" else "MEDIUM",
            "type":"MECHANICAL",
        }]
        if _finite_or_none(row.get("slippage_r")) not in (None,0.0):
            explanations.append({
                "code":"SLIPPAGE_RECORDED",
                "detail":f"slippage registrado: {_finite_or_none(row.get('slippage_r')):.2f}R",
                "confidence":"HIGH",
                "type":"EXECUTION",
            })
        return {
            "schema":SCHEMA,
            "trade_id":_trade_id(row,index),
            "outcome":outcome,
            "mechanical":mechanics,
            "context_coverage_pct":coverage["coverage_pct"],
            "missing_context":coverage["missing_fields"],
            "context_diagnosis_available":False,
            "decision_outcome_relation":"CONTEXT_INCOMPLETE",
            "probable_explanations":explanations,
            "lookahead_used":False,
            "causality_claimed":False,
            "interpretation":(
                "O resultado mecânico é conhecido, mas faltam dados históricos point-in-time "
                "para afirmar por que a decisão funcionou ou falhou. Macro, notícia ou regime "
                "ausentes permanecem como desconhecidos."
            ),
        }

    parsed=dict(coverage["parsed"])
    signal_time=_timestamp(row.get("decision_captured_at")) or _timestamp(row.get("signal_time"))
    entry_time=_timestamp(row.get("entry_time"))
    exit_time=_timestamp(row.get("exit_time"))
    net_r=_finite_or_none(row.get("net_r"))
    if signal_time is None or entry_time is None or exit_time is None or net_r is None:
        return {
            "schema":SCHEMA,
            "trade_id":_trade_id(row,index),
            "outcome":outcome,
            "mechanical":mechanics,
            "context_coverage_pct":coverage["coverage_pct"],
            "missing_context":["valid_timestamps_or_net_r"],
            "context_diagnosis_available":False,
            "decision_outcome_relation":"CONTEXT_INCOMPLETE",
            "probable_explanations":[{
                "code":mechanics["code"],
                "detail":mechanics["summary"],
                "confidence":"HIGH",
                "type":"MECHANICAL",
            }],
            "lookahead_used":False,
            "causality_claimed":False,
            "interpretation":"Contexto informado, mas timestamps/net R não permitem diagnóstico point-in-time seguro.",
        }

    snapshot=DecisionSnapshot(
        trade_id=_trade_id(row,index),
        captured_at=signal_time,
        entry_time=entry_time,
        side=_text(row.get("side")) or "UNKNOWN",
        macro_alignment=int(parsed["macro_alignment"]),
        technical_confirmation=bool(parsed["technical_confirmation"]),
        liquidity_confirmation=bool(parsed["liquidity_confirmation"]),
        regime_fit=bool(parsed["regime_fit"]),
        known_high_impact_event=bool(parsed["known_high_impact_event"]),
        data_quality_pct=float(parsed["data_quality_pct"]),
        plan_followed=bool(parsed["plan_followed"]),
        notes=tuple(x.strip() for x in _text(row.get("notes")).split("|") if x.strip()),
    )
    trade_outcome=TradeOutcome(
        exit_time=exit_time,
        outcome=outcome,
        net_r=net_r,
        exit_reason=_text(row.get("status")) or "UNKNOWN",
        slippage_r=_finite_or_none(row.get("slippage_r")) or 0.0,
        cost_r=_finite_or_none(row.get("cost_r")) or 0.0,
    )
    event=_event_from_record(row)
    rich=diagnose_trade(snapshot,trade_outcome,[event] if event is not None else [])
    probable=[dict(x) for x in rich.get("probable_explanations",[])]
    probable.insert(0,{
        "code":mechanics["code"],
        "detail":mechanics["summary"],
        "confidence":"HIGH" if mechanics["code"]!="OHLC_AMBIGUOUS" else "MEDIUM",
        "type":"MECHANICAL",
    })
    return {
        **rich,
        "schema":SCHEMA,
        "mechanical":mechanics,
        "context_coverage_pct":coverage["coverage_pct"],
        "missing_context":[],
        "context_diagnosis_available":True,
        "probable_explanations":probable,
    }

def diagnose_backtest_records(records:Iterable[Mapping[str,Any]])->list[dict[str,object]]:
    return [diagnose_backtest_record(row,index=i) for i,row in enumerate(records)]

def diagnosis_cause_summary(
    diagnoses:Iterable[Mapping[str,Any]],
)->list[dict[str,object]]:
    rows=[dict(x) for x in diagnoses]
    outcome_totals={}
    for row in rows:
        outcome=_text(row.get("outcome")).upper()
        if outcome in {"GAIN","LOSS","BREAKEVEN"}:
            outcome_totals[outcome]=outcome_totals.get(outcome,0)+1

    counts={}
    details={}
    confidences={}
    for row in rows:
        outcome=_text(row.get("outcome")).upper()
        if outcome not in {"GAIN","LOSS","BREAKEVEN"}:
            continue
        seen=set()
        for raw in list(row.get("probable_explanations",[]) or []):
            reason=dict(raw or {})
            code=_text(reason.get("code")).upper() or "UNKNOWN"
            key=(outcome,code)
            if key in seen:
                continue
            seen.add(key)
            counts[key]=counts.get(key,0)+1
            details[key]=_text(reason.get("detail"))
            confidences[key]=_text(reason.get("confidence")).upper() or "UNKNOWN"

    out=[]
    for (outcome,code),count in counts.items():
        total=outcome_totals.get(outcome,0)
        out.append({
            "outcome":outcome,
            "code":code,
            "trades":count,
            "outcome_trades":total,
            "share_of_outcome_pct":None if not total else round(100.0*count/total,1),
            "confidence":confidences.get((outcome,code),"UNKNOWN"),
            "detail":details.get((outcome,code),""),
            "causality_claimed":False,
        })
    return sorted(
        out,
        key=lambda x:(str(x["outcome"]),-int(x["trades"]),str(x["code"])),
    )


def diagnosis_table(records:Iterable[Mapping[str,Any]])->list[dict[str,object]]:
    out=[]
    for diag in diagnose_backtest_records(records):
        reasons=" | ".join(
            str(x.get("detail") or "") for x in diag.get("probable_explanations",[])[:4]
            if str(x.get("detail") or "").strip()
        )
        out.append({
            "trade_id":diag.get("trade_id"),
            "outcome":diag.get("outcome"),
            "relation":diag.get("decision_outcome_relation"),
            "context_coverage_pct":diag.get("context_coverage_pct"),
            "why":reasons,
            "missing_context":", ".join(diag.get("missing_context",[]) or []),
            "lookahead_used":diag.get("lookahead_used",False),
            "causality_claimed":diag.get("causality_claimed",False),
        })
    return out

def build_passport_from_backtest(
    records:Iterable[Mapping[str,Any]],
    *,
    strategy:str,
    paper_trades:int=0,
    paper_expectancy_r:float|None=None,
)->dict[str,object]:
    rows=[dict(x) for x in records]
    metrics=summarize_results(rows)
    pf=metrics.get("profit_factor")
    if pf is None:
        # Infinite/undefined PF (no gross losses) must not be converted into a
        # false readiness advantage. Keep a neutral finite placeholder and flag.
        pf_value=0.0
    else:
        pf_value=float(pf)
    assets={_text(x.get("pair")) for x in rows if _text(x.get("pair"))}
    sessions={_text(x.get("session")) for x in rows if _text(x.get("session"))}
    regimes={_text(x.get("regime")) for x in rows if _text(x.get("regime"))}
    qualities=[
        q for q in (_finite_or_none(x.get("data_quality_pct")) for x in rows)
        if q is not None and 0<=q<=100
    ]
    quality=None if not qualities else round(sum(qualities)/len(qualities),2)
    passport=build_operational_passport(OperationalPassportInput(
        strategy=str(strategy),
        state="TESTING",
        trades=int(metrics.get("trades",0) or 0),
        expectancy_r=float(metrics.get("expectancy_r") or 0.0),
        profit_factor=pf_value,
        net_r=float(metrics.get("net_r") or 0.0),
        max_drawdown_r=float(metrics.get("max_drawdown_r") or 0.0),
        assets_covered=len(assets),
        sessions_covered=len(sessions),
        regimes_covered=len(regimes),
        paper_trades=int(paper_trades),
        paper_expectancy_r=paper_expectancy_r,
        data_quality_pct=quality,
        last_validation_date=date.today(),
    ))
    flags=list(passport.get("evidence_flags",[]))
    if pf is None:
        flags.append("profit factor indefinido nesta amostra")
    passport["evidence_flags"]=list(dict.fromkeys(flags))
    passport["source"]="BACKTEST"
    passport["automatic_promotion"]=False
    return passport

def backtest_intelligence_bundle(
    records:Iterable[Mapping[str,Any]],
    *,
    strategy:str,
)->dict[str,object]:
    rows=[dict(x) for x in records]
    diagnoses=diagnose_backtest_records(rows)
    causes=diagnosis_cause_summary(diagnoses)
    passport=build_passport_from_backtest(rows,strategy=strategy)
    executed=[x for x in diagnoses if x.get("outcome") in {"GAIN","LOSS","BREAKEVEN"}]
    rich=sum(1 for x in executed if x.get("context_diagnosis_available"))
    return {
        "schema":SCHEMA,
        "strategy":strategy,
        "diagnoses":diagnoses,
        "diagnosis_table":diagnosis_table(rows),
        "cause_summary":causes,
        "passport":passport,
        "executed_trades":len(executed),
        "rich_context_trades":rich,
        "rich_context_pct":None if not executed else round(100.0*rich/len(executed),1),
        "automatic_execution":False,
        "automatic_promotion":False,
    }

__all__=[
    "SCHEMA",
    "context_coverage",
    "diagnose_backtest_record",
    "diagnose_backtest_records",
    "diagnosis_table",
    "diagnosis_cause_summary",
    "build_passport_from_backtest",
    "backtest_intelligence_bundle",
]
