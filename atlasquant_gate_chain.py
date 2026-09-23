"""Authoritative P0 gate chain. Pure, strategy-policy aware and fail-closed."""
from __future__ import annotations
from typing import Any,Mapping
ORDER=("DATA","DIRECTION","MACRO","STRATEGY","TRIGGER","SESSION","NEWS","MARKET_CONDITION","RISK")
HARD_PREFIX=("BLOCK","LOCK","INVALID","MISSING","STALE","DIVERGENT_SOURCE","INSUFFICIENT_DATA")
PASS_VALUES={"PASS","PASS_LONG","PASS_SHORT","ALIGNED_LONG","ALIGNED_SHORT","TRIGGERED","CONFIRMED","OPTIMAL","VALID","CLEAR","NORMAL","APPROVED","CONSTRAINED"}
WAIT_VALUES={"WAIT","WAITING","CANDIDATE","SETUP","ARMED","CAUTION","POST_EVENT_VOLATILITY","LOW_QUALITY","NO_SETUP","NEUTRAL","DIVERGENT"}
def _state(v:Any)->str:return str(v or "").strip().upper().replace(" ","_")
def evaluate_gate_chain(gates:Mapping[str,Any]|None,*,macro_policy:str="WAIT")->dict[str,Any]:
 src={str(k).upper():_state(v) for k,v in dict(gates or {}).items()}; decisions=[]; hard=[]; waits=[]
 policy=_state(macro_policy)
 for name in ORDER:
  state=src.get(name,"")
  if not state: hard.append(f"{name}_GATE_UNKNOWN"); decisions.append({"gate":name,"state":"UNKNOWN","decision":"BLOCK"}); continue
  if name=="MACRO" and state in {"NEUTRAL","DIVERGENT"}:
   if policy=="PASS": decision="PASS"
   elif policy=="BLOCK": hard.append(f"MACRO:{state}"); decision="BLOCK"
   else: waits.append(f"MACRO:{state}"); decision="WAIT"
  elif state.startswith(HARD_PREFIX) or state in {"BLOCKED","BLOQUEADO","CLOSED_INVALID","EXPIRED","INVALIDATED"}:
   hard.append(f"{name}:{state}"); decision="BLOCK"
  elif state in PASS_VALUES or state.startswith("PASS_"): decision="PASS"
  else: waits.append(f"{name}:{state}"); decision="WAIT"
  decisions.append({"gate":name,"state":state,"decision":decision})
 return {"overall":"BLOCKED" if hard else ("WAIT" if waits else "PASS"),"hard_blocks":hard,"waits":waits,
         "decisions":decisions,"all_critical_known":not any(d["state"]=="UNKNOWN" for d in decisions),"macro_policy":policy}
def execution_gate_passed(result:Mapping[str,Any])->bool:
 return str(result.get("overall","")).upper()=="PASS" and bool(result.get("all_critical_known",False))
