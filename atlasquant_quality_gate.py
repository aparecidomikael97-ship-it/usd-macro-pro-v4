"""P0 Quality Gate. Executed evidence is required; runtime health cannot be hidden."""
from __future__ import annotations
from typing import Any,Mapping
CRITICAL=("instrument_registry","scanner_28","data_health","gate_chain","risk","system_health","paper","paper_entry","paper_close","paper_store_integrity","result_store","evidence_ledger","restart_recovery")
def quality_gate(checks:Mapping[str,Any]|None,*,system_health:Mapping[str,Any]|None=None)->dict[str,Any]:
 src=dict(checks or {});rows=[];blocked=[];pending=[]
 for name in CRITICAL:
  item=dict(src.get(name,{}) or {});state=str(item.get("state","NOT_RUN")).upper();evidence=item.get("evidence")
  if state=="PASS" and evidence:decision="PASS"
  elif state in {"FAIL","BLOCKED"}:decision="FAIL";blocked.append(name)
  else:decision="PENDING";pending.append(name)
  rows.append({"check":name,"reported_state":state,"decision":decision,"evidence":evidence})
 runtime=str((system_health or {}).get("state","UNKNOWN")).upper()
 runtime_ok=runtime=="NORMAL"
 if runtime not in {"UNKNOWN","NORMAL"}: blocked.append("system_health")
 if blocked:release="BLOCKED"
 elif pending or not runtime_ok:release="NOT_READY"
 else:release="RC_ELIGIBLE"
 return {"release_state":release,"checks":rows,"blocked":blocked,"pending":pending,"runtime_health":runtime,
         "runtime_health_ok":runtime_ok,"production_promotion_allowed":False,"real_orders_enabled":False}
def initial_unvalidated_gate()->dict[str,Any]:return quality_gate({})
