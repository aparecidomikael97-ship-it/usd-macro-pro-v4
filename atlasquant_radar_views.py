"""P0 adapter from existing Home Radar rows to Agora/Preparando/Geral views."""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from atlasquant_opportunity_ranking import build_rankings
from atlasquant_gate_chain import evaluate_gate_chain, execution_gate_passed

def _trigger(row:Mapping[str,Any])->str:
    code=str(row.get("signal_status_code","")).upper()
    return "CONFIRMED" if code=="CONFIRMED" else "WAITING"

def ranking_input_from_home(row:Mapping[str,Any], *, system_state:str="NORMAL")->dict[str,Any]:
    r=dict(row)
    blocks=[*list(r.get("hard_blocks",[]) or []),*list(r.get("blockers",[]) or [])]
    sys=str(system_state or "UNKNOWN").upper()
    if sys!="NORMAL": blocks.append(f"SYSTEM_HEALTH_{sys}")
    data_ready=bool(r.get("data_ready",False))
    gate=str(r.get("gate","")).upper()
    risk=str(r.get("risk_gate","")).upper()
    # Legacy Home has no authoritative Risk Gate yet. Fail closed.
    if risk not in {"APPROVED","CONSTRAINED","BLOCKED"}:
        risk="BLOCKED"
        blocks.append("RISK_GATE_AINDA_NAO_INTEGRADO")
    supplied=dict(r.get("gates",{}) or {})
    gates=supplied
    legacy_gate=gate or "WAIT"
    macro_policy=str(r.get("macro_policy","WAIT"))
    authoritative=evaluate_gate_chain(gates,macro_policy=macro_policy) if supplied else None
    maturity=float(r.get("priority",0) or 0)
    gate_waits=[]
    if authoritative is not None and not execution_gate_passed(authoritative):
        blocks.extend(authoritative.get("hard_blocks",[]) or [])
        gate_waits.extend(authoritative.get("waits",[]) or [])
    return {
        "pair":r.get("pair"),"direction":r.get("bias"),"quality_score":r.get("quality",0),
        "confidence":r.get("data_score",0),"data_ready":data_ready,"trigger":_trigger(r),
        "risk_gate":risk,"hard_blocks":blocks,"missing":gate_waits,"gates":gates,"legacy_gate":legacy_gate,"macro_policy":macro_policy,"maturity":maturity,
        "authoritative_gate_chain":authoritative,
        "session_bucket":r.get("session_bucket"),"reason":r.get("reason"),
        "next_action":r.get("next_action"),"system_state":sys,"source_row":r,
    }

def build_radar_views(home_rows:Sequence[Mapping[str,Any]]|None, *, limit:int=10, system_state:str="NORMAL")->dict[str,Any]:
    out=build_rankings([ranking_input_from_home(r,system_state=system_state) for r in (home_rows or [])],limit=limit)
    out["system_state"]=str(system_state).upper(); out["execution_surface_enabled"]=str(system_state).upper()=="NORMAL"
    return out
