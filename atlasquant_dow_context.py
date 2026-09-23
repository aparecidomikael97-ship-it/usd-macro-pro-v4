"""AtlasQuant Dow Theory context layer.

Deterministic context/confirmation only. It is NOT a standalone entry setup,
does not infer institutional intent, does not create orders and cannot bypass
the Gate Chain, Risk Engine or System Health.

AtlasQuant use:
- primary trend: Weekly + Daily structure;
- secondary trend: H4 + H1 structure;
- execution timing remains with ICT/SMC/trigger layers;
- cross-market confirmation is optional evidence, never a fabricated rule;
- volume is supporting evidence only when valid volume data exists.
"""
from __future__ import annotations
from typing import Any,Mapping

SCHEMA="ATLASQUANT_DOW_CONTEXT_V1"
VALID={"BULLISH","BEARISH","MIXED","UNKNOWN"}

def _trend(value:Any)->str:
    raw=str(value or "").strip().upper()
    if raw in VALID:return raw
    if any(x in raw for x in ("ALTA","BULL","BUY","COMPRA")):return "BULLISH"
    if any(x in raw for x in ("BAIXA","BEAR","SELL","VENDA")):return "BEARISH"
    if any(x in raw for x in ("MIST","MIX","NEUT","LATERAL")):return "MIXED"
    return "UNKNOWN"

def dow_context(*,weekly:Any,daily:Any,h4:Any,h1:Any,
                confirmation:Mapping[str,Any]|None=None,
                volume:Mapping[str,Any]|None=None)->dict[str,Any]:
    w,d,four,one=map(_trend,(weekly,daily,h4,h1))
    primary="BULLISH" if w==d=="BULLISH" else "BEARISH" if w==d=="BEARISH" else "MIXED" if "UNKNOWN" not in {w,d} else "UNKNOWN"
    secondary="BULLISH" if four==one=="BULLISH" else "BEARISH" if four==one=="BEARISH" else "MIXED" if "UNKNOWN" not in {four,one} else "UNKNOWN"
    aligned=primary in {"BULLISH","BEARISH"} and secondary==primary

    conf=dict(confirmation or {})
    conf_available=bool(conf.get("available",False))
    conf_aligned=bool(conf.get("aligned",False)) if conf_available else None
    conf_source=str(conf.get("source") or "").strip()

    vol=dict(volume or {})
    vol_available=bool(vol.get("available",False))
    vol_supports=bool(vol.get("supports_trend",False)) if vol_available else None
    vol_source=str(vol.get("source") or "").strip()

    evidence=[]
    blockers=[]
    if aligned:evidence.append("PRIMARY_SECONDARY_ALIGNED")
    elif primary=="UNKNOWN" or secondary=="UNKNOWN":blockers.append("DOW_STRUCTURE_INCOMPLETE")
    else:blockers.append("PRIMARY_SECONDARY_NOT_ALIGNED")
    if conf_available:
        evidence.append("CROSS_MARKET_CONFIRMATION" if conf_aligned else "CROSS_MARKET_DIVERGENCE")
    if vol_available:
        evidence.append("VOLUME_SUPPORTS_TREND" if vol_supports else "VOLUME_DOES_NOT_CONFIRM")

    status="CONFIRMED_CONTEXT" if aligned and conf_aligned is not False and vol_supports is not False else "WAIT"
    if primary=="UNKNOWN" or secondary=="UNKNOWN":status="INSUFFICIENT_DATA"
    return {
        "schema":SCHEMA,
        "role":"CONTEXT_CONFIRMATION_ONLY",
        "weekly":w,"daily":d,"h4":four,"h1":one,
        "primary_trend":primary,"secondary_trend":secondary,
        "aligned":aligned,"status":status,
        "confirmation":{"available":conf_available,"aligned":conf_aligned,"source":conf_source},
        "volume":{"available":vol_available,"supports_trend":vol_supports,"source":vol_source},
        "evidence":evidence,"blockers":blockers,
        "entry_setup":False,
        "execution_authorized":False,
        "real_orders_enabled":False,
        "bypasses_gate_chain":False,
        "bypasses_risk":False,
        "interpretation":(
            "Dow confirma o contexto; ICT/SMC e os gatilhos continuam responsáveis pelo timing."
            if status=="CONFIRMED_CONTEXT"
            else "Dow ainda não confirma o contexto completo; não usar esta camada como gatilho de entrada."
        ),
    }

def apply_dow_context(opportunity:Mapping[str,Any],dow:Mapping[str,Any])->dict[str,Any]:
    """Attach Dow evidence without changing execution permission or base score."""
    row=dict(opportunity or {});ctx=dict(dow or {})
    row["dow_context"]=ctx
    row["dow_status"]=str(ctx.get("status","INSUFFICIENT_DATA"))
    row["dow_primary"]=str(ctx.get("primary_trend","UNKNOWN"))
    row["dow_secondary"]=str(ctx.get("secondary_trend","UNKNOWN"))
    row["dow_aligned"]=bool(ctx.get("aligned",False))
    # Deliberately preserve all execution/risk/score fields from upstream.
    return row
