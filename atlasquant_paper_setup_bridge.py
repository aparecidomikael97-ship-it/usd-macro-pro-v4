"""Bridge explicitly tagged Paper trades into Setup Forward/Paper evidence.

No setup is inferred from FVG/ICT/SMC component states, score, outcome or
post-trade behavior. A Paper trade contributes to a setup only when the setup
identifier was explicitly present at signal creation (or explicitly manual
tagged with provenance).
"""
from __future__ import annotations

import base64
from io import BytesIO
from math import isfinite
from typing import Any

import pandas as pd
import requests

from atlasquant_runtime_store import require_runtime_branch
from atlasquant_setup_journal import setup_forward_summary, validate_setup_record

SCHEMA="ATLASQUANT_PAPER_SETUP_BRIDGE_V1"
PAPER_AUDIT_PATH="dados/paper_setup_audit_v114.csv"
DEFAULT_MAX_RUNTIME_ROWS=10000

SETUP_ALIASES={
    "bos-choch-ob":"bos-choch-ob",
    "bos_choch_ob":"bos-choch-ob",
    "bos/choch + order block":"bos-choch-ob",
    "fvg":"fvg",
    "fair value gap":"fvg",
    "fvg / desequilíbrio":"fvg",
    "fvg / desequilibrio":"fvg",
    "ote":"ote",
    "ote / fibonacci":"ote",
    "crt":"crt",
    "amd":"amd-po3",
    "amd-po3":"amd-po3",
    "amd_po3":"amd-po3",
    "amd / po3":"amd-po3",
    "power of three":"amd-po3",
    "breaker-mitigation":"breaker-mitigation",
    "breaker_mitigation":"breaker-mitigation",
    "breaker / mitigation block":"breaker-mitigation",
    "session-liquidity-mss":"session-liquidity-mss",
    "session_liquidity_mss":"session-liquidity-mss",
    "liquidez de sessão + mss":"session-liquidity-mss",
    "liquidez de sessao + mss":"session-liquidity-mss",
    "opening-range":"opening-range",
    "opening_range":"opening-range",
    "opening range":"opening-range",
    "volume-profile":"volume-profile",
    "volume_profile":"volume-profile",
    "volume profile":"volume-profile",
}

TRUSTED_ATTRIBUTIONS={"EXPLICIT_INPUT","MANUAL_TAG","SOURCE_MODEL_EXPLICIT"}


def _norm(value:Any)->str:
    return str(value or "").strip().casefold()


def canonical_setup_id(value:Any)->str:
    raw=_norm(value)
    return SETUP_ALIASES.get(raw,"")


def _finite(value:Any)->float|None:
    try:
        out=float(value)
        return out if isfinite(out) else None
    except Exception:
        return None


def _row_to_forward_record(raw:dict[str,Any])->tuple[dict[str,Any]|None,str]:
    status=str(raw.get("status") or "").strip().upper()
    if status!="CLOSED":
        return None,"NOT_CLOSED"

    attribution=str(raw.get("setup_attribution") or "").strip().upper()
    if attribution not in TRUSTED_ATTRIBUTIONS:
        return None,"ATTRIBUTION_NOT_EXPLICIT"

    setup_id=canonical_setup_id(raw.get("setup_id"))
    if not setup_id:
        return None,"UNKNOWN_SETUP_ID"

    result_r=_finite(raw.get("realized_r"))
    if result_r is None:
        return None,"INVALID_RESULT_R"

    quality=_finite(raw.get("data_quality_pct"))
    if quality is None or not 0<=quality<=100:
        return None,"MISSING_DATA_QUALITY"

    session=str(raw.get("active_session") or raw.get("session") or "").strip()
    regime=str(raw.get("d1_regime") or raw.get("regime") or raw.get("w1_regime") or "").strip()
    signal_time=str(raw.get("signal_time") or raw.get("created_at") or "").strip()
    side=str(raw.get("side") or "").strip().upper()

    record={
        "setup_id":setup_id,
        "pair":str(raw.get("pair") or "").strip().upper(),
        "observed_at":signal_time,
        "session":session,
        "regime":regime,
        "direction":side,
        "entry":raw.get("entry_price"),
        "stop":raw.get("stop_price"),
        "target":raw.get("target_price"),
        "result_r":result_r,
        "data_quality":quality,
        "decision_state":"PAPER",
        "hard_blocks":[],
        "soft_blocks":[],
        "invalidation":"",
        "notes":(
            "Importado do Paper Audit com atribuição explícita; "
            f"trade_id={str(raw.get('trade_id') or '')}"
        ),
    }
    checked=validate_setup_record(record)
    if not checked["valid"]:
        return None,"INVALID_FORWARD_RECORD:"+",".join(checked["errors"])
    return dict(checked["record"]),"OK"


def bridge_paper_audit(audit:pd.DataFrame|None)->dict[str,Any]:
    if not isinstance(audit,pd.DataFrame) or audit.empty:
        return {
            "schema":SCHEMA,
            "rows_total":0,
            "closed_rows":0,
            "explicit_rows":0,
            "eligible_records":0,
            "records":[],
            "summary_by_setup":{},
            "excluded":{},
            "setup_inference_used":False,
        }

    records=[]
    excluded={}
    closed_rows=0
    explicit_rows=0
    for raw in audit.to_dict("records"):
        status=str(raw.get("status") or "").strip().upper()
        if status=="CLOSED":
            closed_rows+=1
        attribution=str(raw.get("setup_attribution") or "").strip().upper()
        if attribution in TRUSTED_ATTRIBUTIONS and str(raw.get("setup_id") or "").strip():
            explicit_rows+=1
        record,reason=_row_to_forward_record(dict(raw))
        if record is None:
            excluded[reason]=excluded.get(reason,0)+1
        else:
            records.append(record)

    summary=setup_forward_summary(records)
    return {
        "schema":SCHEMA,
        "rows_total":int(len(audit)),
        "closed_rows":closed_rows,
        "explicit_rows":explicit_rows,
        "eligible_records":len(records),
        "records":records,
        "summary_by_setup":summary,
        "excluded":excluded,
        "setup_inference_used":False,
        "interpretation":(
            "Somente trades Paper com setup explicitamente atribuído entram na evidência "
            "Forward/Paper. Estados ICT/SMC e resultado não são usados para adivinhar o setup."
        ),
    }



def load_paper_audit_runtime(
    *,
    repo:str,
    branch:str,
    token:str,
    timeout:int=15,
    max_rows:int=DEFAULT_MAX_RUNTIME_ROWS,
)->tuple[pd.DataFrame,dict[str,Any]]:
    """Read the prospective Paper audit from the dedicated runtime branch.

    Read-only. It never writes runtime data and never falls back to a code branch.
    """
    try:
        safe=require_runtime_branch(branch)
    except Exception as exc:
        return pd.DataFrame(),{
            "ok":False,"reason":"UNSAFE_BRANCH","rows":0,"error":str(exc),
        }
    repo=str(repo or "").strip()
    token=str(token or "").strip()
    if not repo or not token:
        return pd.DataFrame(),{
            "ok":False,"reason":"NOT_CONFIGURED","rows":0,"branch":safe,"error":"",
        }
    url=f"https://api.github.com/repos/{repo}/contents/{PAPER_AUDIT_PATH}"
    headers={
        "Authorization":f"Bearer {token}",
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    }
    try:
        response=requests.get(
            url,
            headers=headers,
            params={"ref":safe},
            timeout=timeout,
        )
        if response.status_code==404:
            return pd.DataFrame(),{
                "ok":True,"reason":"NOT_FOUND","rows":0,"branch":safe,"error":"",
            }
        response.raise_for_status()
        payload=response.json()
        raw=base64.b64decode(payload.get("content",""))
        frame=pd.read_csv(BytesIO(raw))
        limit=max(1,int(max_rows))
        if len(frame)>limit:
            frame=frame.tail(limit).reset_index(drop=True)
        return frame,{
            "ok":True,"reason":"LOADED","rows":int(len(frame)),
            "branch":safe,"error":"",
        }
    except Exception as exc:
        return pd.DataFrame(),{
            "ok":False,"reason":"IO_ERROR","rows":0,"branch":safe,
            "error":f"{type(exc).__name__}: {exc}",
        }


__all__=[
    "SCHEMA",
    "SETUP_ALIASES",
    "TRUSTED_ATTRIBUTIONS",
    "PAPER_AUDIT_PATH",
    "canonical_setup_id",
    "bridge_paper_audit",
    "load_paper_audit_runtime",
]
