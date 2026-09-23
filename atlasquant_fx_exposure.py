"""P0 FX exposure and concentration engine."""
from __future__ import annotations
from typing import Any, Mapping, Sequence
from atlasquant_instrument_registry import normalize_fx_symbol

def decompose_fx(pair:str, side:str, weight:float=1.0)->dict[str,float]:
    s=normalize_fx_symbol(pair); base,quote=s[:3],s[3:]
    direction=str(side).upper()
    if direction in {"BUY","LONG","COMPRA"}: sign=1.0
    elif direction in {"SELL","SHORT","VENDA"}: sign=-1.0
    else: raise ValueError("side must be BUY/LONG/COMPRA or SELL/SHORT/VENDA")
    w=abs(float(weight))
    return {base:sign*w,quote:-sign*w}

def aggregate_currency_exposure(positions:Sequence[Mapping[str,Any]]|None)->dict[str,Any]:
    net={}; gross={}; valid=0; rejected=[]
    for p in positions or []:
        try:
            legs=decompose_fx(str(p.get("pair","")),str(p.get("side","")),float(p.get("weight",p.get("exposure",1)) or 0))
        except Exception as exc:
            rejected.append({"pair":str(p.get("pair","")),"reason":type(exc).__name__}); continue
        valid+=1
        for c,v in legs.items():
            net[c]=net.get(c,0.0)+v; gross[c]=gross.get(c,0.0)+abs(v)
    return {"net":net,"gross":gross,"valid_positions":valid,"rejected":rejected}

def concentration_gate(positions, candidate, *, max_currency_gross:float)->dict[str,Any]:
    before=aggregate_currency_exposure(positions)
    after=aggregate_currency_exposure([*(positions or []),candidate])
    breaches={c:v for c,v in after["gross"].items() if v>float(max_currency_gross)}
    return {"approved":not breaches,"breaches":breaches,"before":before,"after":after,
            "reason":"PASS" if not breaches else "RISK_CLUSTER_LIMIT"}
