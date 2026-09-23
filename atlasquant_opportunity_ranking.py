"""AtlasQuant P0 opportunity ranking.

Separates Quality Score from executability. A blocked 94 cannot outrank an
executable 88 in TOP_AGORA. No score here is a probability of profit.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence
import math

QUALITY_BANDS=((85,"ALTA QUALIDADE"),(75,"QUASE PRONTO"),(60,"PREPARANDO"),(0,"OBSERVANDO"))

def _num(v:Any, default:float=0.0)->float:
    try:
        x=float(v); return x if math.isfinite(x) else default
    except Exception: return default

def quality_band(score:Any)->str:
    x=max(0.0,min(100.0,_num(score)))
    return next(label for floor,label in QUALITY_BANDS if x>=floor)

def _row(raw:Mapping[str,Any])->dict[str,Any]:
    r=dict(raw); q=max(0.0,min(100.0,_num(r.get("quality_score",r.get("quality",0)))))
    conf=max(0.0,min(100.0,_num(r.get("confidence",r.get("data_score",0)))))
    gates=dict(r.get("gates",{}) or {})
    hard=[str(x) for x in r.get("hard_blocks",[]) or [] if str(x).strip()]
    gate_block=any(str(v).upper().startswith(("BLOCK","LOCK")) for v in gates.values())
    data_ok=bool(r.get("data_ready",False))
    trigger=str(r.get("trigger",r.get("trigger_gate","WAITING"))).upper()
    risk=str(r.get("risk_gate","BLOCKED")).upper()
    executable=bool(data_ok and not hard and not gate_block and trigger=="CONFIRMED" and risk in {"APPROVED","CONSTRAINED"})
    maturity=max(0.0,min(100.0,_num(r.get("maturity",0))))
    # Execution priority is a ranking index, not a win probability.
    execution_priority=(1000 if executable else 0)+(q*4)+(conf*1.5)+(maturity*.5)
    missing=[str(x) for x in r.get("missing",[]) or [] if str(x).strip()]
    return {**r,"quality_score":q,"quality_band":quality_band(q),"confidence":conf,
            "executable":executable,"execution_priority":execution_priority,
            "operational_status":"LIBERADO PELO MODELO" if executable else ("BLOQUEADO" if hard or gate_block or not data_ok else "AGUARDANDO GATILHO"),
            "missing":missing,"hard_blocks":hard}

def build_rankings(rows:Sequence[Mapping[str,Any]]|None, *, limit:int=10)->dict[str,list[dict[str,Any]]]:
    normalized=[_row(x) for x in (rows or []) if isinstance(x,Mapping)]
    n=max(0,int(limit))
    agora=sorted(normalized,key=lambda r:(r["executable"],r["execution_priority"],r["quality_score"]),reverse=True)
    preparando=sorted([r for r in normalized if not r["executable"] and not r["hard_blocks"]],
                      key=lambda r:(r.get("maturity",0),r["quality_score"],r["confidence"]),reverse=True)
    geral=sorted(normalized,key=lambda r:(r["quality_score"],r["confidence"]),reverse=True)
    return {"TOP_AGORA":agora[:n],"TOP_PREPARANDO":preparando[:n],"TOP_GERAL":geral[:n],
            "total":len(normalized),"score_is_probability":False}

def top10_is_honest(result:Mapping[str,Any])->bool:
    for row in result.get("TOP_AGORA",[]) or []:
        if row.get("executable") and (not row.get("data_ready") or row.get("hard_blocks")):
            return False
    return True
