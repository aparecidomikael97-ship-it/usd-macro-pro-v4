"""AtlasQuant private setup journal.

Schema and aggregation helpers for setup-tagged Forward/Paper observations.
No broker calls, order routing, automatic promotion or live P&L assumptions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping, Sequence

import pandas as pd

SCHEMA="ATLASQUANT_SETUP_JOURNAL_V1"
REQUIRED_FIELDS=(
    "setup_id","pair","observed_at","session","regime","direction",
    "entry","stop","target","result_r","data_quality","decision_state",
)


def _finite(value:Any)->float|None:
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def normalize_setup_record(raw:Mapping[str,Any]|None)->dict[str,Any]:
    r=dict(raw or {})
    observed=pd.to_datetime(r.get("observed_at"),utc=True,errors="coerce")
    entry=_finite(r.get("entry"))
    stop=_finite(r.get("stop"))
    target=_finite(r.get("target"))
    result_r=_finite(r.get("result_r"))
    quality=_finite(r.get("data_quality"))
    direction=str(r.get("direction") or "").strip().upper()
    if direction in {"BUY","COMPRA"}:
        direction="BUY"
    elif direction in {"SELL","VENDA"}:
        direction="SELL"
    else:
        direction="WAIT"
    return {
        "schema":SCHEMA,
        "setup_id":str(r.get("setup_id") or "").strip().casefold(),
        "pair":str(r.get("pair") or "").strip().upper(),
        "observed_at":None if pd.isna(observed) else pd.Timestamp(observed).isoformat(),
        "session":str(r.get("session") or "").strip(),
        "regime":str(r.get("regime") or "").strip(),
        "direction":direction,
        "entry":entry,
        "stop":stop,
        "target":target,
        "result_r":result_r,
        "data_quality":quality,
        "decision_state":str(r.get("decision_state") or "").strip(),
        "hard_blocks":[str(x) for x in list(r.get("hard_blocks",[]) or []) if str(x).strip()],
        "soft_blocks":[str(x) for x in list(r.get("soft_blocks",[]) or []) if str(x).strip()],
        "invalidation":str(r.get("invalidation") or "").strip(),
        "notes":str(r.get("notes") or "").strip(),
        "paper_only":True,
        "real_order":False,
    }


def validate_setup_record(raw:Mapping[str,Any]|None)->dict[str,Any]:
    r=normalize_setup_record(raw)
    errors=[]
    for field in ("setup_id","pair","observed_at","session","regime","decision_state"):
        if not r.get(field):
            errors.append(f"{field} ausente")
    if r["direction"] not in {"BUY","SELL"}:
        errors.append("direction deve ser BUY/SELL para observação concluída")
    for field in ("entry","stop","target","result_r","data_quality"):
        value=r.get(field)
        if value is None:
            errors.append(f"{field} inválido")
    if r["data_quality"] is not None and not (0<=r["data_quality"]<=100):
        errors.append("data_quality fora de 0–100")
    if r["entry"] is not None and r["stop"] is not None and r["entry"]==r["stop"]:
        errors.append("entry e stop não podem ser iguais")
    if r["entry"] is not None and r["target"] is not None and r["entry"]==r["target"]:
        errors.append("entry e target não podem ser iguais")
    return {
        "valid":not errors,
        "errors":errors,
        "record":r,
        "paper_only":True,
        "real_order":False,
    }


def records_frame(records:Sequence[Mapping[str,Any]]|None)->pd.DataFrame:
    rows=[]
    for raw in list(records or []):
        checked=validate_setup_record(raw)
        row=dict(checked["record"])
        row["valid"]=bool(checked["valid"])
        row["validation_errors"]=" · ".join(checked["errors"])
        rows.append(row)
    return pd.DataFrame(rows)


def setup_forward_summary(records:Sequence[Mapping[str,Any]]|None)->dict[str,dict[str,Any]]:
    df=records_frame(records)
    if df.empty:
        return {}
    df=df[df["valid"]==True].copy()  # noqa: E712
    if df.empty:
        return {}
    out={}
    for setup_id,g in df.groupby("setup_id"):
        vals=pd.to_numeric(g["result_r"],errors="coerce").dropna().astype(float)
        n=int(len(vals))
        if not n:
            continue
        wins=int((vals>0).sum())
        losses=int((vals<0).sum())
        gross_win=float(vals[vals>0].sum()) if wins else 0.0
        gross_loss=abs(float(vals[vals<0].sum())) if losses else 0.0
        pf=(gross_win/gross_loss) if gross_loss>0 else None
        equity=vals.cumsum()
        peak=equity.cummax()
        dd=peak-equity
        out[str(setup_id)]={
            "forward_samples":n,
            "forward_expectancy_r":round(float(vals.mean()),4),
            "forward_win_rate_pct":round(wins/n*100.0,2),
            "forward_profit_factor":None if pf is None else round(pf,4),
            "forward_max_drawdown_r":round(float(dd.max()),4),
            "regimes":sorted({str(x) for x in g["regime"].dropna().tolist() if str(x).strip()}),
            "sessions":sorted({str(x) for x in g["session"].dropna().tolist() if str(x).strip()}),
            "pairs":sorted({str(x) for x in g["pair"].dropna().tolist() if str(x).strip()}),
            "paper_only":True,
        }
    return out


def journal_template()->pd.DataFrame:
    return pd.DataFrame([{
        "setup_id":"session-liquidity-mss",
        "pair":"EUR/USD",
        "observed_at":datetime.now(timezone.utc).isoformat(),
        "session":"London",
        "regime":"trend",
        "direction":"BUY",
        "entry":"",
        "stop":"",
        "target":"",
        "result_r":"",
        "data_quality":"",
        "decision_state":"PAPER",
        "hard_blocks":"",
        "soft_blocks":"",
        "invalidation":"",
        "notes":"",
    }])


__all__=[
    "SCHEMA","REQUIRED_FIELDS","normalize_setup_record","validate_setup_record",
    "records_frame","setup_forward_summary","journal_template",
]
