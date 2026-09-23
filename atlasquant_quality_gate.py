"""P0 Quality Gate report. Pure aggregation; never upgrades unexecuted tests to PASS."""
from __future__ import annotations
from typing import Any,Mapping,Sequence

CRITICAL=("instrument_registry","scanner_28","data_health","gate_chain","risk","paper","result_store","restart_recovery")

def quality_gate(checks:Mapping[str,Any]|None)->dict[str,Any]:
    src=dict(checks or {}); rows=[]; blocked=[]; pending=[]
    for name in CRITICAL:
        state=str((src.get(name,{}) or {}).get("state","NOT_RUN")).upper()
        evidence=(src.get(name,{}) or {}).get("evidence")
        if state=="PASS" and evidence:
            decision="PASS"
        elif state in {"FAIL","BLOCKED"}:
            decision="FAIL"; blocked.append(name)
        else:
            decision="PENDING"; pending.append(name)
        rows.append({"check":name,"reported_state":state,"decision":decision,"evidence":evidence})
    if blocked: release="BLOCKED"
    elif pending: release="NOT_READY"
    else: release="RC_ELIGIBLE"
    return {"release_state":release,"checks":rows,"blocked":blocked,"pending":pending,
            "production_promotion_allowed":False,"real_orders_enabled":False}

def initial_unvalidated_gate()->dict[str,Any]:
    return quality_gate({})
