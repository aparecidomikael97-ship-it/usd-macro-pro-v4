"""P0 FX gross/net exposure. Invalid portfolio evidence fails closed."""
from __future__ import annotations
from typing import Any,Mapping,Sequence
import math
from atlasquant_instrument_registry import normalize_fx_symbol
def decompose_fx(pair:str,side:str,weight:float=1.0)->dict[str,float]:
 s=normalize_fx_symbol(pair); base,quote=s[:3],s[3:]; direction=str(side).upper(); w=float(weight)
 if not math.isfinite(w) or w<=0: raise ValueError("weight must be finite and positive")
 if direction in {"BUY","LONG","COMPRA"}: sign=1.
 elif direction in {"SELL","SHORT","VENDA"}: sign=-1.
 else: raise ValueError("invalid side")
 return {base:sign*w,quote:-sign*w}
def aggregate_currency_exposure(positions:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
 net={};gross={};valid=0;rejected=[]
 for p in positions or []:
  try: legs=decompose_fx(str(p.get("pair","")),str(p.get("side","")),float(p.get("weight",p.get("exposure",1))))
  except Exception as exc: rejected.append({"pair":str(p.get("pair","")),"reason":type(exc).__name__});continue
  valid+=1
  for c,v in legs.items():net[c]=net.get(c,0.)+v;gross[c]=gross.get(c,0.)+abs(v)
 return {"net":net,"gross":gross,"valid_positions":valid,"rejected":rejected,"complete":not rejected}
def concentration_gate(positions,candidate,*,max_currency_gross:float)->dict[str,Any]:
 try:
  limit=float(max_currency_gross)
  if not math.isfinite(limit) or limit<=0: raise ValueError
 except Exception:return {"approved":False,"reason":"EXPOSURE_LIMIT_INVALID","breaches":{}}
 before=aggregate_currency_exposure(positions); after=aggregate_currency_exposure([*(positions or []),candidate])
 if not before["complete"] or not after["complete"]: return {"approved":False,"reason":"PORTFOLIO_EXPOSURE_UNKNOWN","breaches":{},"before":before,"after":after}
 breaches={c:v for c,v in after["gross"].items() if v>limit}
 return {"approved":not breaches,"breaches":breaches,"before":before,"after":after,"reason":"PASS" if not breaches else "RISK_CLUSTER_LIMIT"}
