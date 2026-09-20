"""Point-in-time context join for AtlasQuant backtests.

Historical context rows must be snapshots captured at or before each signal.
The join fills missing diagnostic metadata only and never overwrites explicit
signal metadata. Future snapshots are never used.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

import pandas as pd

SCHEMA="ATLASQUANT_BACKTEST_CONTEXT_V1"

CONTEXT_FIELDS=(
    "macro_alignment",
    "technical_confirmation",
    "liquidity_confirmation",
    "regime_fit",
    "regime",
    "known_high_impact_event",
    "data_quality_pct",
    "plan_followed",
    "event_time",
    "event_label",
    "event_impact",
    "event_known_before_entry",
)

_CONTEXT_ALIASES={
    "captured_at":("captured_at","snapshot_time","decision_captured_at","datetime","time"),
    "pair":("pair","par","asset","ativo","symbol","ticker"),
    "macro_alignment":("macro_alignment","macro","macro_context"),
    "technical_confirmation":("technical_confirmation","technical_ok","tecnico_confirmado"),
    "liquidity_confirmation":("liquidity_confirmation","liquidity_ok","liquidez_confirmada"),
    "regime_fit":("regime_fit","regime_ok","regime_alinhado"),
    "regime":("regime","market_regime"),
    "known_high_impact_event":("known_high_impact_event","high_impact_event","evento_alto_impacto"),
    "data_quality_pct":("data_quality_pct","data_quality","qualidade_dados"),
    "plan_followed":("plan_followed","followed_plan","plano_seguido"),
    "event_time":("event_time","news_time","noticia_hora"),
    "event_label":("event_label","event","news_event","evento"),
    "event_impact":("event_impact","impact","impacto"),
    "event_known_before_entry":("event_known_before_entry","event_known","evento_conhecido_antes"),
}

def _norm(value:Any)->str:
    return str(value or "").strip().lower()

def _rename_aliases(frame:pd.DataFrame)->pd.DataFrame:
    out=frame.copy()
    by_norm={_norm(c):c for c in out.columns}
    rename={}
    for canonical,names in _CONTEXT_ALIASES.items():
        if canonical in out.columns:
            continue
        for alias in names:
            actual=by_norm.get(_norm(alias))
            if actual is not None:
                rename[actual]=canonical
                break
    return out.rename(columns=rename)

def normalize_context_snapshots(frame:pd.DataFrame|None)->pd.DataFrame:
    columns=["captured_at","pair",*CONTEXT_FIELDS]
    if not isinstance(frame,pd.DataFrame) or frame.empty:
        return pd.DataFrame(columns=columns)
    out=_rename_aliases(frame)
    if "captured_at" not in out.columns or "pair" not in out.columns:
        return pd.DataFrame(columns=columns)
    out=out.copy()
    out["captured_at"]=pd.to_datetime(out["captured_at"],utc=True,errors="coerce",format="mixed")
    out["pair"]=out["pair"].fillna("").astype(str).str.strip().str.upper()
    if "event_time" in out.columns:
        out["event_time"]=pd.to_datetime(out["event_time"],utc=True,errors="coerce",format="mixed")
    for field in CONTEXT_FIELDS:
        if field not in out.columns:
            out[field]=None
    out=out.dropna(subset=["captured_at"])
    out=out[out["pair"].ne("")]
    out=out.sort_values(["pair","captured_at"],kind="stable")
    out=out.drop_duplicates(subset=["pair","captured_at"],keep="last")
    return out.reindex(columns=columns).reset_index(drop=True)

def context_template_csv()->str:
    return ",".join(["captured_at","pair",*CONTEXT_FIELDS])+"\n"

def _signal_time(signal:Mapping[str,Any])->pd.Timestamp|None:
    try:
        ts=pd.Timestamp(signal.get("signal_time"))
        if ts.tzinfo is None:
            ts=ts.tz_localize("UTC")
        else:
            ts=ts.tz_convert("UTC")
        return ts
    except Exception:
        return None

def enrich_signals_point_in_time(
    signals:Iterable[Mapping[str,Any]],
    context_snapshots:pd.DataFrame|None,
)->dict[str,object]:
    rows=[dict(x) for x in signals]
    context=normalize_context_snapshots(context_snapshots)
    if context.empty:
        return {
            "schema":SCHEMA,
            "signals":rows,
            "matched":0,
            "unmatched":len(rows),
            "future_context_used":False,
            "overwritten_explicit_fields":0,
        }

    matched=0
    enriched=[]
    for signal in rows:
        row=dict(signal)
        ts=_signal_time(row)
        pair=str(row.get("pair",row.get("asset","")) or "").strip().upper()
        if ts is None or not pair:
            enriched.append(row)
            continue
        candidates=context[(context["pair"]==pair)&(context["captured_at"]<=ts)]
        if candidates.empty:
            enriched.append(row)
            continue
        snap=candidates.iloc[-1]
        matched+=1
        if row.get("decision_captured_at") in (None,""):
            row["decision_captured_at"]=pd.Timestamp(snap["captured_at"]).isoformat()
        for field in CONTEXT_FIELDS:
            # Explicit signal metadata wins over joined context.
            if field in row and row.get(field) not in (None,""):
                continue
            value=snap.get(field)
            if pd.isna(value):
                continue
            if isinstance(value,pd.Timestamp):
                value=value.isoformat()
            row[field]=value
        enriched.append(row)

    return {
        "schema":SCHEMA,
        "signals":enriched,
        "matched":matched,
        "unmatched":max(0,len(rows)-matched),
        "future_context_used":False,
        "overwritten_explicit_fields":0,
    }

__all__=[
    "SCHEMA",
    "CONTEXT_FIELDS",
    "normalize_context_snapshots",
    "context_template_csv",
    "enrich_signals_point_in_time",
]
