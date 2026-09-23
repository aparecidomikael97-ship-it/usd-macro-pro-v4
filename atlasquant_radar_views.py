"""P0 adapter from existing Home Radar rows to Agora/Preparando/Geral views."""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from atlasquant_opportunity_ranking import build_rankings

def _trigger(row:Mapping[str,Any])->str:
    code=str(row.get("signal_status_code","")).upper()
    return "CONFIRMED" if code=="CONFIRMED" else "WAITING"

def ranking_input_from_home(row:Mapping[str,Any])->dict[str,Any]:
    r=dict(row)
    blocks=[*list(r.get("hard_blocks",[]) or []),*list(r.get("blockers",[]) or [])]
    data_ready=bool(r.get("data_ready",False))
    gate=str(r.get("gate","")).upper()
    risk=str(r.get("risk_gate","")).upper()
    # Legacy Home has no authoritative Risk Gate yet. Fail closed.
    if risk not in {"APPROVED","CONSTRAINED","BLOCKED"}:
        risk="BLOCKED"
        blocks.append("RISK_GATE_AINDA_NAO_INTEGRADO")
    gates={"LEGACY_GATE":gate or "WAIT"}
    maturity=float(r.get("priority",0) or 0)
    return {
        "pair":r.get("pair"),"direction":r.get("bias"),"quality_score":r.get("quality",0),
        "confidence":r.get("data_score",0),"data_ready":data_ready,"trigger":_trigger(r),
        "risk_gate":risk,"hard_blocks":blocks,"gates":gates,"maturity":maturity,
        "session_bucket":r.get("session_bucket"),"reason":r.get("reason"),
        "next_action":r.get("next_action"),"source_row":r,
    }

def build_radar_views(home_rows:Sequence[Mapping[str,Any]]|None, *, limit:int=10)->dict[str,Any]:
    return build_rankings([ranking_input_from_home(r) for r in (home_rows or [])],limit=limit)
