"""Strict evidence environment guard for BACKTEST/PAPER/LIVE."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
VALID={"BACKTEST","PAPER","LIVE"}
def isolate_environment(rows:Sequence[Mapping[str,Any]]|None,expected:str)->dict[str,Any]:
 exp=str(expected).upper()
 if exp not in VALID:return {"ok":False,"environment":exp,"rows":[],"rejected":[],"reason":"ENVIRONMENT_INVALID"}
 accepted=[];rejected=[]
 for x in rows or []:
  r=dict(x); env=str(r.get("environment","")).upper()
  if env==exp:accepted.append(r)
  else:rejected.append(r)
 return {"ok":not rejected,"environment":exp,"rows":accepted,"rejected":rejected,
         "reason":"PASS" if not rejected else "ENVIRONMENT_MIX_DETECTED"}
