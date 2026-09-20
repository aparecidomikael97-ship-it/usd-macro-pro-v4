"""AtlasQuant intermarket research adapter.

Consumes explicit, already-computed intermarket drivers and aggregates them by
independent group. It does not fetch markets, infer unavailable relationships,
or change the operational engine.

Expected state example:
{
  "EUR/USD": {
    "drivers": [
      {"group":"rates","name":"US-DE 2Y spread","direction":"SELL",
       "strength":70,"quality":90,"fresh":true,"reason":"spread widened"},
      {"group":"risk","name":"risk regime","direction":"SELL",
       "strength":45,"quality":75,"fresh":true}
    ]
  }
}
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping
import math

SCHEMA = "ATLASQUANT_INTERMARKET_CONTEXT_V1"
MIN_INDEPENDENT_GROUPS = 2


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _vote(value: object) -> int:
    raw = str(value or "").upper().strip()
    if raw in {"BUY","COMPRA","BULL","ALTISTA"}:
        return 1
    if raw in {"SELL","VENDA","BEAR","BAIXISTA"}:
        return -1
    return 0


def build_intermarket_snapshot(pair: object, state: Mapping[str,Any] | None) -> dict[str,Any]:
    p = str(pair or "").upper().replace("-","/").strip()
    raw_state = dict(state or {})
    raw = raw_state.get(p, raw_state.get("default"))
    if not isinstance(raw, Mapping):
        return {
            "schema":SCHEMA,"pair":p,"available":False,"direction":"INDISPONÍVEL",
            "balance":0.0,"quality":0.0,"groups":0,"reasons":[],
            "decision_effect":False,"changes_gate":False,"changes_score_mestre":False,
            "detail":"Sem drivers intermarket explícitos e atuais para este par.",
        }

    buckets: dict[str,list[dict[str,Any]]] = defaultdict(list)
    stale = 0
    for item in list(raw.get("drivers",[]) or []):
        if not isinstance(item, Mapping):
            continue
        if not bool(item.get("fresh", True)):
            stale += 1
            continue
        group = str(item.get("group") or "").strip().lower()
        vote = _vote(item.get("direction"))
        strength = max(0.0,min(100.0,_finite(item.get("strength",0))))
        quality = max(0.0,min(100.0,_finite(item.get("quality",0))))
        if not group or vote == 0 or strength <= 0 or quality <= 0:
            continue
        buckets[group].append({
            "vote":vote,"strength":strength,"quality":quality,
            "name":str(item.get("name") or group),
            "reason":str(item.get("reason") or "").strip(),
        })

    rows=[]
    reasons=[]
    for group,items in buckets.items():
        denom=sum(x["strength"]*x["quality"]/100.0 for x in items)
        net=sum(x["vote"]*x["strength"]*x["quality"]/100.0 for x in items)
        normalized=0.0 if denom<=0 else max(-1.0,min(1.0,net/denom))
        group_quality=sum(x["quality"] for x in items)/len(items)
        rows.append({"group":group,"net":normalized,"quality":group_quality,"items":len(items)})
        best=max(items,key=lambda x:x["strength"]*x["quality"])
        side="COMPRA" if normalized>0.15 else "VENDA" if normalized<-0.15 else "NEUTRO"
        why=(" · "+best["reason"]) if best["reason"] else ""
        reasons.append(f"{best['name']}: {side}{why}.")

    active=[x for x in rows if abs(x["net"])>0.15]
    if len(active) < MIN_INDEPENDENT_GROUPS:
        return {
            "schema":SCHEMA,"pair":p,"available":False,"direction":"INDISPONÍVEL",
            "balance":0.0,"quality":0.0,"groups":len(active),"reasons":reasons[:6],
            "stale_drivers":stale,"decision_effect":False,"changes_gate":False,
            "changes_score_mestre":False,
            "detail":"Intermarket exige pelo menos dois grupos independentes atuais; um único proxy não vira confirmação.",
        }

    balance=sum(x["net"]*(0.35+0.65*x["quality"]/100.0) for x in active)
    denom=sum(0.35+0.65*x["quality"]/100.0 for x in active)
    balance=100.0*balance/denom if denom else 0.0
    direction="COMPRA" if balance>=18 else "VENDA" if balance<=-18 else "NEUTRO"
    quality=sum(x["quality"] for x in active)/len(active)
    agreement=sum(1 for x in active if (balance>0 and x["net"]>0) or (balance<0 and x["net"]<0))
    agreement_pct=(agreement/len(active)*100.0) if abs(balance)>=18 else 0.0

    return {
        "schema":SCHEMA,"pair":p,"available":True,"direction":direction,
        "balance":round(max(-100.0,min(100.0,balance)),1),
        "quality":round(max(0.0,min(100.0,quality)),1),
        "groups":len(active),"agreement_pct":round(agreement_pct,1),
        "group_rows":sorted(rows,key=lambda x:x["group"]),
        "reasons":reasons[:6],"stale_drivers":stale,
        "decision_effect":False,"changes_gate":False,"changes_score_mestre":False,
        "real_orders_enabled":False,
        "detail":"Intermarket agrupa evidências por família para reduzir dupla contagem de proxies correlacionados.",
    }


__all__=["SCHEMA","MIN_INDEPENDENT_GROUPS","build_intermarket_snapshot"]
