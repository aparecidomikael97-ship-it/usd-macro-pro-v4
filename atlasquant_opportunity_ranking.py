"""AtlasQuant P0 opportunity ranking.

Separates Quality Score from executability. A blocked 94 cannot outrank an
executable 88 in TOP_AGORA. No score here is a probability of profit.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence
import math
from atlasquant_gate_chain import evaluate_gate_chain, execution_gate_passed

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
    waits=[]
    authoritative=None
    if gates:
        authoritative=evaluate_gate_chain(gates,macro_policy=str(r.get("macro_policy","WAIT")))
        hard.extend(str(x) for x in authoritative.get("hard_blocks",[]) or [] if str(x).strip())
        waits.extend(str(x) for x in authoritative.get("waits",[]) or [] if str(x).strip())
    data_ok=bool(r.get("data_ready",False))
    trigger=str(r.get("trigger",r.get("trigger_gate","WAITING"))).upper()
    risk=str(r.get("risk_gate","BLOCKED")).upper()
    risk_ok=risk in {"APPROVED","CONSTRAINED"}
    gates_ok=True if authoritative is None else execution_gate_passed(authoritative)
    executable=bool(data_ok and not hard and gates_ok and trigger=="CONFIRMED" and risk_ok)
    maturity=max(0.0,min(100.0,_num(r.get("maturity",0))))
    # Execution priority is a ranking index, not a win probability.
    execution_priority=(1000 if executable else 0)+(q*4)+(conf*1.5)+(maturity*.5)
    missing=[str(x) for x in r.get("missing",[]) or [] if str(x).strip()]
    blocked=bool(hard or not data_ok or risk=="BLOCKED" or (authoritative is not None and authoritative.get("overall")=="BLOCKED"))
    if executable: operational="LIBERADO PELO MODELO"
    elif blocked: operational="BLOQUEADO"
    elif waits or trigger!="CONFIRMED" or not risk_ok: operational="AGUARDANDO GATILHO"
    else: operational="PREPARANDO"
    return {**r,"quality_score":q,"quality_band":quality_band(q),"confidence":conf,
            "executable":executable,"execution_priority":execution_priority,
            "operational_status":operational,"missing":missing,"hard_blocks":list(dict.fromkeys(hard)),
            "gate_waits":list(dict.fromkeys(waits)),"authoritative_gate_chain":authoritative}

def build_rankings(rows:Sequence[Mapping[str,Any]]|None, *, limit:int=10)->dict[str,Any]:
    normalized=[_row(x) for x in (rows or []) if isinstance(x,Mapping)]
    n=max(0,int(limit))
    agora=sorted(normalized,key=lambda r:(r["executable"],r["execution_priority"],r["quality_score"]),reverse=True)
    preparando=sorted([r for r in normalized if not r["executable"] and not r["hard_blocks"] and str(r.get("risk_gate","")).upper()!="BLOCKED"],
                      key=lambda r:(r.get("maturity",0),r["quality_score"],r["confidence"]),reverse=True)
    geral=sorted(normalized,key=lambda r:(r["quality_score"],r["confidence"]),reverse=True)
    return {"TOP_AGORA":agora[:n],"TOP_PREPARANDO":preparando[:n],"TOP_GERAL":geral[:n],
            "total":len(normalized),"score_is_probability":False}

def top10_is_honest(result:Mapping[str,Any])->bool:
    for row in result.get("TOP_AGORA",[]) or []:
        if row.get("executable") and (not row.get("data_ready") or row.get("hard_blocks")):
            return False
        chain=row.get("authoritative_gate_chain")
        if row.get("executable") and isinstance(chain,Mapping) and not execution_gate_passed(chain):
            return False
    return True
