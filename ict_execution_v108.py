"""USD Macro Pro V10.8 — ICT Execution Engine.

Deterministic/observational execution layer for CRT, OTE, AMD/Power of Three
and recent FVG context. It never decides macro direction and never calls an API.
"""
from __future__ import annotations
from typing import Any
import math
import numpy as np
import pandas as pd


def _frame(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    if "datetime" in d.columns:
        d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    for c in ("open", "high", "low", "close"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    if not all(c in d.columns for c in ("open", "high", "low", "close")):
        return pd.DataFrame()
    return d.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)


def detect_crt(h1: pd.DataFrame | None, side: str) -> dict[str, Any]:
    d = _frame(h1)
    if len(d) < 3 or side not in ("BUY", "SELL"):
        return {"status":"⚪ AGUARDANDO", "score":0, "phase":"SEM DADOS", "text":"CRT aguarda H1 válido + direção macro."}
    c1, c2, c3 = d.iloc[-3], d.iloc[-2], d.iloc[-1]
    ah, al = float(c1.high), float(c1.low)
    if ah <= al:
        return {"status":"⚪ AGUARDANDO", "score":0, "phase":"SEM RANGE", "text":"Candle âncora H1 sem range válido."}
    if side == "BUY":
        raid = float(c2.low) < al and float(c2.close) > al
        delivery = float(c3.close) > float(c2.close) and float(c3.close) > (ah + al) / 2
        target, invalidation, raid_side = ah, min(float(c2.low), al), "SSL"
    else:
        raid = float(c2.high) > ah and float(c2.close) < ah
        delivery = float(c3.close) < float(c2.close) and float(c3.close) < (ah + al) / 2
        target, invalidation, raid_side = al, max(float(c2.high), ah), "BSL"
    if raid and delivery:
        return {"status":"🟢 CRT CONFIRMADO", "score":100, "phase":"DISTRIBUIÇÃO", "raid_side":raid_side,
                "anchor_high":ah, "anchor_low":al, "target":target, "invalidation":invalidation,
                "text":f"Range H1 varrido em {raid_side}, fechamento voltou ao range e a distribuição confirmou o lado macro."}
    if raid:
        return {"status":"🟡 MANIPULAÇÃO DETECTADA", "score":70, "phase":"MANIPULAÇÃO", "raid_side":raid_side,
                "anchor_high":ah, "anchor_low":al, "target":target, "invalidation":invalidation,
                "text":f"Sweep {raid_side} + retorno ao range detectados; falta a vela de distribuição confirmar."}
    return {"status":"⚪ SEM CRT", "score":30, "phase":"ACUMULAÇÃO / ESPERA", "raid_side":"",
            "anchor_high":ah, "anchor_low":al, "target":target, "invalidation":invalidation,
            "text":"Ainda não ocorreu a varredura válida do candle-range contra o lado macro."}


def _impulse_range(h1: pd.DataFrame, side: str, lookback: int = 28):
    d = _frame(h1).tail(lookback).reset_index(drop=True)
    if len(d) < 8:
        return None
    if side == "BUY":
        hi_idx = int(d["high"].tail(12).idxmax())
        before = d.loc[:hi_idx]
        if before.empty: return None
        lo_idx = int(before["low"].idxmin())
        lo, hi = float(d.loc[lo_idx,"low"]), float(d.loc[hi_idx,"high"])
        if hi_idx <= lo_idx or hi <= lo: return None
    elif side == "SELL":
        lo_idx = int(d["low"].tail(12).idxmin())
        before = d.loc[:lo_idx]
        if before.empty: return None
        hi_idx = int(before["high"].idxmax())
        hi, lo = float(d.loc[hi_idx,"high"]), float(d.loc[lo_idx,"low"])
        if lo_idx <= hi_idx or hi <= lo: return None
    else:
        return None
    return lo, hi


def detect_ote(h1: pd.DataFrame | None, side: str) -> dict[str, Any]:
    d = _frame(h1)
    imp = _impulse_range(d, side)
    if imp is None or d.empty:
        return {"status":"⚪ SEM OTE", "score":0, "text":"Não há impulso H1 válido para ancorar o OTE."}
    lo, hi = imp
    px = float(d.iloc[-1]["close"])
    rng = hi - lo
    if rng <= 0:
        return {"status":"⚪ SEM OTE", "score":0, "text":"Range do impulso inválido."}
    if side == "BUY":
        retr = (hi - px) / rng
        z62, sweet, z79 = hi - .62*rng, hi - .705*rng, hi - .79*rng
    else:
        retr = (px - lo) / rng
        z62, sweet, z79 = lo + .62*rng, lo + .705*rng, lo + .79*rng
    zone_low, zone_high = min(z62,z79), max(z62,z79)
    inside = .62 <= retr <= .79
    dist = min(abs(retr-.62), abs(retr-.79)) if not inside else abs(retr-.705)
    near = (not inside) and dist <= .10
    if inside:
        status, score = "🟢 DENTRO DO OTE", 100 if abs(retr-.705) <= .04 else 90
        text = f"Preço retraiu {retr*100:.1f}% do impulso H1 e está na zona OTE 62–79%."
    elif near:
        status, score = "🟡 PRÓXIMO DO OTE", 65
        text = f"Retração em {retr*100:.1f}%; OTE está próximo, mas o preço ainda não entrou na zona."
    else:
        status, score = "⚪ FORA DO OTE", 35
        text = f"Retração atual {retr*100:.1f}% está fora da zona OTE 62–79%."
    return {"status":status, "score":score, "retracement_pct":retr*100, "zone_low":zone_low,
            "zone_high":zone_high, "sweet_705":sweet, "swing_low":lo, "swing_high":hi, "price":px, "text":text}


def detect_amd(m15: pd.DataFrame | None, side: str) -> dict[str, Any]:
    d = _frame(m15).tail(16).reset_index(drop=True)
    if len(d) < 12 or side not in ("BUY", "SELL"):
        return {"status":"⚪ AGUARDANDO AMD", "score":0, "phase":"SEM DADOS", "text":"AMD aguarda M15 válido + direção macro."}
    n_acc = max(6, len(d)//2)
    acc, after = d.iloc[:n_acc], d.iloc[n_acc:]
    ah, al = float(acc.high.max()), float(acc.low.min())
    mid = (ah+al)/2
    if ah <= al or after.empty:
        return {"status":"⚪ AGUARDANDO AMD", "score":0, "phase":"SEM RANGE", "text":"Acumulação não pôde ser definida."}
    if side == "BUY":
        manip = bool(((after.low < al) & (after.close > al)).any())
        distribution = manip and float(d.iloc[-1].close) > mid
        target, manipulation_side = ah, "SSL"
    else:
        manip = bool(((after.high > ah) & (after.close < ah)).any())
        distribution = manip and float(d.iloc[-1].close) < mid
        target, manipulation_side = al, "BSL"
    if distribution:
        return {"status":"🟢 AMD / PO3 EM DISTRIBUIÇÃO", "score":100, "phase":"DISTRIBUIÇÃO", "acc_high":ah,
                "acc_low":al, "target":target, "manipulation_side":manipulation_side,
                "text":f"Acumulação → sweep {manipulation_side} → distribuição no lado macro detectados no M15."}
    if manip:
        return {"status":"🟡 AMD EM MANIPULAÇÃO", "score":70, "phase":"MANIPULAÇÃO", "acc_high":ah,
                "acc_low":al, "target":target, "manipulation_side":manipulation_side,
                "text":f"A liquidez {manipulation_side} foi varrida; aguarda expansão/distribuição no lado macro."}
    return {"status":"⚪ AMD EM ACUMULAÇÃO", "score":40, "phase":"ACUMULAÇÃO", "acc_high":ah,
            "acc_low":al, "target":target, "manipulation_side":manipulation_side,
            "text":"Range de acumulação identificado; manipulação ainda não confirmou."}


def detect_fvg(m15: pd.DataFrame | None, side: str) -> dict[str, Any]:
    d = _frame(m15).tail(20).reset_index(drop=True)
    if len(d) < 3 or side not in ("BUY","SELL"):
        return {"status":"⚪ SEM FVG", "score":0, "text":"FVG aguarda candles M15 válidos."}
    candidates=[]
    invalidated=0
    for i in range(2,len(d)):
        if side=="BUY" and float(d.loc[i,"low"]) > float(d.loc[i-2,"high"]):
            lo,hi=float(d.loc[i-2,"high"]),float(d.loc[i,"low"])
            future=d.iloc[i+1:]
            # Bullish FVG deixa de existir se o preço atravessa toda a zona.
            is_invalid=not future.empty and float(future["low"].min()) <= lo
            if is_invalid: invalidated += 1
            else: candidates.append((i,lo,hi))
        elif side=="SELL" and float(d.loc[i,"high"]) < float(d.loc[i-2,"low"]):
            lo,hi=float(d.loc[i,"high"]),float(d.loc[i-2,"low"])
            future=d.iloc[i+1:]
            is_invalid=not future.empty and float(future["high"].max()) >= hi
            if is_invalid: invalidated += 1
            else: candidates.append((i,lo,hi))
    if not candidates:
        if invalidated:
            return {"status":"⚪ FVG INVALIDADO", "score":20, "text":"O FVG recente foi totalmente atravessado; revisita posterior não reativa a zona antiga."}
        return {"status":"⚪ SEM FVG RECENTE", "score":30, "text":"Nenhum desequilíbrio M15 recente no lado macro."}
    _,lo,hi=candidates[-1]
    px=float(d.iloc[-1].close)
    inside=lo <= px <= hi
    return {"status":"🟢 FVG EM TESTE" if inside else "🟡 FVG PRESENTE", "score":90 if inside else 65,
            "zone_low":lo, "zone_high":hi, "price":px,
            "text":"Preço está dentro de um FVG M15 ainda válido." if inside else "Há FVG M15 ainda válido no lado macro; aguarde retorno/continuação conforme o plano."}


def build_ict_snapshot(h1: pd.DataFrame | None, m15: pd.DataFrame | None, side: str) -> dict[str, Any]:
    crt, ote, amd, fvg = detect_crt(h1,side), detect_ote(h1,side), detect_amd(m15,side), detect_fvg(m15,side)
    weights=(.30,.25,.30,.15)
    scores=[float(x.get("score",0) or 0) for x in (crt,ote,amd,fvg)]
    readiness=float(np.clip(sum(s*w for s,w in zip(scores,weights)),0,100))
    label = "⚪ MACRO AGUARDAR" if side not in ("BUY","SELL") else "🟢 ICT MUITO ALINHADO" if readiness>=80 else "🟡 ICT EM PREPARAÇÃO" if readiness>=60 else "⚪ ICT AINDA INCOMPLETO"
    return {"side":side, "readiness":round(readiness,1), "label":label, "crt":crt, "ote":ote, "amd":amd, "fvg":fvg,
            "updated_at":pd.Timestamp.now(tz="UTC").isoformat()}
