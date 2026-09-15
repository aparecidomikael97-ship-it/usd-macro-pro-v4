"""USD Macro Pro V11.0 — Institutional Execution Engine.

Camada determinística/observacional inspirada em conceitos ICT/Smart Money:
- Displacement normalizado por ATR
- MSS / mudança de estrutura
- SMT divergence entre pares correlacionados
- Premium/Discount do dealing range H1
- Internal/External liquidity pools
- Judas Swing / sessão
- Breaker / Mitigation heuristic

Importante: isto NÃO imita ordens reais de instituições e NÃO produz
probabilidade de lucro. O objetivo é transformar contexto em regras objetivas,
auditáveis e testáveis para timing/execução.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import math

import numpy as np
import pandas as pd

try:
    from zoneinfo import ZoneInfo
    NY_TZ = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    NY_TZ = None


SMT_COMPANIONS = {
    "EUR/USD": "GBP/USD",
    "GBP/USD": "EUR/USD",
    "AUD/USD": "NZD/USD",
    "NZD/USD": "AUD/USD",
    "USD/CHF": "USD/JPY",
    "USD/JPY": "USD/CHF",
}


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
    d = d.dropna(subset=["open", "high", "low", "close"]).copy()
    if "datetime" in d.columns:
        d = d.dropna(subset=["datetime"])
        d = d.sort_values("datetime")
    return d.reset_index(drop=True)


def _atr(d: pd.DataFrame, length: int = 14) -> pd.Series:
    if d.empty:
        return pd.Series(dtype=float)
    prev = d["close"].shift(1)
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - prev).abs(),
        (d["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(length, min_periods=max(4, length // 3)).mean()


def _finite(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else float(default)
    except Exception:
        return float(default)


def _pivot_points(d: pd.DataFrame, left: int = 2, right: int = 2) -> tuple[list[tuple[int,float]], list[tuple[int,float]]]:
    highs: list[tuple[int,float]] = []
    lows: list[tuple[int,float]] = []
    if len(d) < left + right + 3:
        return highs, lows
    for i in range(left, len(d) - right):
        h = float(d.loc[i, "high"])
        l = float(d.loc[i, "low"])
        if h >= float(d.loc[i-left:i+right, "high"].max()):
            highs.append((i, h))
        if l <= float(d.loc[i-left:i+right, "low"].min()):
            lows.append((i, l))
    return highs, lows


def detect_displacement(df: pd.DataFrame | None, side: str, lookback: int = 8) -> dict[str, Any]:
    d = _frame(df)
    if len(d) < 20 or side not in ("BUY", "SELL"):
        return {"status":"⚪ SEM DISPLACEMENT", "score":0, "text":"Aguardando candles válidos e direção macro."}
    a = _atr(d)
    candidates = []
    for i in range(max(1, len(d)-lookback), len(d)):
        atr = _finite(a.iloc[i], 0)
        if atr <= 0:
            continue
        o,h,l,c = map(float, (d.loc[i,"open"], d.loc[i,"high"], d.loc[i,"low"], d.loc[i,"close"]))
        body = abs(c-o)
        rng = max(h-l, 1e-12)
        body_atr = body / atr
        range_atr = rng / atr
        close_pos = (c-l)/rng
        aligned = (c > o and close_pos >= .72) if side == "BUY" else (c < o and close_pos <= .28)
        if aligned:
            strength = min(100.0, 35.0 + body_atr*38.0 + max(0.0, range_atr-1.0)*18.0)
            candidates.append((i, strength, body_atr, range_atr, c))
    if not candidates:
        return {"status":"⚪ SEM DISPLACEMENT", "score":25, "text":"Não há candle recente com expansão/fechamento forte no lado macro."}
    i, strength, body_atr, range_atr, c = max(candidates, key=lambda x: x[1])
    if body_atr >= 1.0 and range_atr >= 1.15:
        status = "🟢 DISPLACEMENT FORTE"
        score = max(85.0, strength)
    elif body_atr >= .65 and range_atr >= .9:
        status = "🟡 DISPLACEMENT MODERADO"
        score = max(62.0, min(84.0, strength))
    else:
        status = "⚪ IMPULSO FRACO"
        score = min(55.0, strength)
    ts = d.loc[i, "datetime"] if "datetime" in d.columns else None
    return {
        "status": status,
        "score": round(float(score),1),
        "body_atr": round(float(body_atr),2),
        "range_atr": round(float(range_atr),2),
        "candle_time": pd.Timestamp(ts).isoformat() if ts is not None and pd.notna(ts) else "",
        "close": c,
        "text": f"Candle de expansão com corpo {body_atr:.2f}×ATR e range {range_atr:.2f}×ATR no lado macro.",
    }


def detect_mss(df: pd.DataFrame | None, side: str) -> dict[str, Any]:
    d = _frame(df)
    if len(d) < 20 or side not in ("BUY", "SELL"):
        return {"status":"⚪ SEM MSS", "score":0, "text":"MSS aguarda estrutura válida."}
    highs, lows = _pivot_points(d, 2, 2)
    if side == "BUY":
        refs = [(i,p) for i,p in highs if i <= len(d)-3]
        if not refs:
            return {"status":"⚪ SEM MSS", "score":20, "text":"Sem swing high confirmado para medir mudança de estrutura."}
        i_ref, level = refs[-1]
        breaks = d.iloc[i_ref+1:]
        hit = breaks[breaks["close"] > level]
        if hit.empty:
            return {"status":"🟡 MSS PENDENTE", "score":45, "level":level, "text":"Ainda falta fechamento acima do último swing high confirmado."}
        row = hit.iloc[0]
    else:
        refs = [(i,p) for i,p in lows if i <= len(d)-3]
        if not refs:
            return {"status":"⚪ SEM MSS", "score":20, "text":"Sem swing low confirmado para medir mudança de estrutura."}
        i_ref, level = refs[-1]
        breaks = d.iloc[i_ref+1:]
        hit = breaks[breaks["close"] < level]
        if hit.empty:
            return {"status":"🟡 MSS PENDENTE", "score":45, "level":level, "text":"Ainda falta fechamento abaixo do último swing low confirmado."}
        row = hit.iloc[0]
    disp = detect_displacement(d, side, lookback=10)
    strong = _finite(disp.get("score"),0) >= 70
    score = 100 if strong else 78
    status = "🟢 MSS + DISPLACEMENT" if strong else "🟢 MSS CONFIRMADO"
    ts = row.get("datetime")
    return {
        "status":status,
        "score":score,
        "level":float(level),
        "break_time":pd.Timestamp(ts).isoformat() if ts is not None and pd.notna(ts) else "",
        "displacement_confirmed":strong,
        "text":f"Estrutura rompeu o swing de referência ({level:.5f}) com fechamento no lado macro." if abs(level)<20 else f"Estrutura rompeu o swing de referência ({level:.3f}) com fechamento no lado macro.",
    }


def detect_dealing_range(h1: pd.DataFrame | None, side: str, lookback: int = 60) -> dict[str, Any]:
    d = _frame(h1).tail(lookback).reset_index(drop=True)
    if len(d) < 12 or side not in ("BUY", "SELL"):
        return {"status":"⚪ RANGE INDEFINIDO", "score":0, "zone":"INDEFINIDO", "text":"Sem H1 suficiente para dealing range."}
    highs, lows = _pivot_points(d, 2, 2)
    if not highs or not lows:
        lo, hi = float(d["low"].min()), float(d["high"].max())
    else:
        # Usa os últimos pivôs opostos que formam um range válido.
        hi_i, hi = highs[-1]
        lo_i, lo = lows[-1]
        if hi <= lo:
            lo, hi = float(d["low"].min()), float(d["high"].max())
    if hi <= lo:
        return {"status":"⚪ RANGE INDEFINIDO", "score":0, "zone":"INDEFINIDO", "text":"Dealing range inválido."}
    px = float(d.iloc[-1]["close"])
    pos = (px-lo)/(hi-lo)*100.0
    if pos < 45:
        zone = "DESCONTO"
    elif pos > 55:
        zone = "PRÊMIO"
    else:
        zone = "EQUILÍBRIO"
    favorable = (side=="BUY" and pos <= 50) or (side=="SELL" and pos >= 50)
    ideal = (side=="BUY" and 15 <= pos <= 45) or (side=="SELL" and 55 <= pos <= 85)
    score = 100 if ideal else 78 if favorable else 35
    status = "🟢 LOCALIZAÇÃO FAVORÁVEL" if ideal else "🟡 LOCALIZAÇÃO ACEITÁVEL" if favorable else "🔴 LOCALIZAÇÃO CARA"
    return {
        "status":status, "score":score, "zone":zone, "position_pct":round(pos,1),
        "range_low":lo, "range_high":hi, "equilibrium":(lo+hi)/2, "price":px,
        "text":f"Preço em {zone.lower()} ({pos:.1f}% do dealing range H1).",
    }


def detect_liquidity_engine(h1: pd.DataFrame | None, m15: pd.DataFrame | None, side: str) -> dict[str, Any]:
    h = _frame(h1).tail(80).reset_index(drop=True)
    m = _frame(m15).tail(120).reset_index(drop=True)
    if len(h) < 12 or side not in ("BUY", "SELL"):
        return {"status":"⚪ LIQUIDEZ INDEFINIDA", "score":0, "text":"Sem estrutura H1 suficiente."}
    a = _atr(h)
    atr = _finite(a.iloc[-1] if len(a) else 0, max(float(h.iloc[-1]["close"])*.001,1e-8))
    highs, lows = _pivot_points(h,2,2)
    px = float((m if not m.empty else h).iloc[-1]["close"])
    tol = max(atr*.18, abs(px)*0.00008)

    eqh=[]; eql=[]
    hp=[p for _,p in highs[-10:]]
    lp=[p for _,p in lows[-10:]]
    for i in range(len(hp)):
        for j in range(i+1,len(hp)):
            if abs(hp[i]-hp[j]) <= tol:
                eqh.append((hp[i]+hp[j])/2)
    for i in range(len(lp)):
        for j in range(i+1,len(lp)):
            if abs(lp[i]-lp[j]) <= tol:
                eql.append((lp[i]+lp[j])/2)
    nearest_bsl = min([x for x in (hp+eqh) if x>px], default=None)
    nearest_ssl = max([x for x in (lp+eql) if x<px], default=None)
    external_high = max(hp, default=float(h["high"].max()))
    external_low = min(lp, default=float(h["low"].min()))
    target = nearest_bsl if side=="BUY" else nearest_ssl
    target_kind = "BSL" if side=="BUY" else "SSL"
    dist_atr = abs(target-px)/atr if target is not None and atr>0 else None
    score = 80 if target is not None and dist_atr is not None and dist_atr>=.6 else 60 if target is not None else 35
    return {
        "status":"🟢 DRAW ON LIQUIDITY DEFINIDO" if score>=75 else "🟡 LIQUIDEZ PARCIAL" if target is not None else "⚪ SEM ALVO CLARO",
        "score":score,
        "target_type":target_kind,
        "target_price":target,
        "distance_atr":round(dist_atr,2) if dist_atr is not None else None,
        "eqh_count":len(eqh), "eql_count":len(eql),
        "external_high":external_high, "external_low":external_low,
        "text":f"Próximo draw {target_kind} a {dist_atr:.2f}×ATR." if dist_atr is not None else f"Nenhum {target_kind} H1 claro à frente do preço.",
    }


def detect_orderflow_zone(h1: pd.DataFrame | None, side: str) -> dict[str, Any]:
    d = _frame(h1).tail(60).reset_index(drop=True)
    if len(d) < 20 or side not in ("BUY","SELL"):
        return {"status":"⚪ SEM PD ARRAY", "score":0, "text":"Sem H1 suficiente para breaker/mitigation."}
    disp = detect_displacement(d, side, lookback=12)
    if _finite(disp.get("score"),0) < 60:
        return {"status":"⚪ SEM PD ARRAY", "score":25, "text":"Nenhum displacement forte para ancorar zona de origem."}
    # Localiza o candle de expansão reportado e procura candle oposto anterior.
    ts = pd.to_datetime(disp.get("candle_time"), utc=True, errors="coerce")
    if pd.isna(ts) or "datetime" not in d.columns:
        i_disp = len(d)-1
    else:
        matches = d.index[d["datetime"]==ts].tolist()
        i_disp = matches[0] if matches else len(d)-1
    candidate=None
    for j in range(i_disp-1, max(-1,i_disp-8), -1):
        o,c=float(d.loc[j,"open"]),float(d.loc[j,"close"])
        opposite = c<o if side=="BUY" else c>o
        if opposite:
            candidate=j; break
    if candidate is None:
        return {"status":"⚪ SEM PD ARRAY", "score":30, "text":"Displacement existe, mas não foi encontrada vela de origem clara."}
    zlo=float(d.loc[candidate,"low"]); zhi=float(d.loc[candidate,"high"])
    px=float(d.iloc[-1]["close"])
    inside=zlo <= px <= zhi
    if side=="BUY":
        invalidated = px < zlo
    else:
        invalidated = px > zhi
    if invalidated:
        # A zona falhou; tratamos como breaker candidato do lado oposto, não como confirmação.
        status="🟡 BREAKER CANDIDATO"; score=55
        text="Zona de origem foi rompida; possível breaker, exige reteste/estrutura antes de usar."
    elif inside:
        status="🟢 MITIGATION / ORIGIN EM TESTE"; score=90
        text="Preço retornou à zona de origem do displacement sem invalidá-la."
    else:
        status="🟡 MITIGATION ZONE ATIVA"; score=68
        text="Zona de origem segue válida; aguarde retorno/reação se fizer parte do plano."
    return {"status":status,"score":score,"zone_low":zlo,"zone_high":zhi,"price":px,"invalidated":invalidated,"text":text}


def detect_session_judas(m15: pd.DataFrame | None, side: str) -> dict[str, Any]:
    d = _frame(m15)
    if len(d) < 40 or side not in ("BUY","SELL") or "datetime" not in d.columns or NY_TZ is None:
        return {"status":"⚪ SESSÃO INDEFINIDA", "score":0, "text":"Sem M15 suficiente para perfil de sessão."}
    x=d.copy()
    x["ny"] = x["datetime"].dt.tz_convert(NY_TZ)
    # Usa a data NY mais recente com dados.
    day=x["ny"].dt.date.iloc[-1]
    # Ásia: 19:00 do dia anterior até 00:00 do dia atual.
    start=pd.Timestamp(day)-pd.Timedelta(days=1)+pd.Timedelta(hours=19)
    end=pd.Timestamp(day)
    start=start.tz_localize(NY_TZ); end=end.tz_localize(NY_TZ)
    asia=x[(x["ny"]>=start)&(x["ny"]<end)]
    if asia.empty:
        # fallback madrugada 00-02 para bases onde o histórico começa depois.
        start2=pd.Timestamp(day).tz_localize(NY_TZ)
        end2=start2+pd.Timedelta(hours=2)
        asia=x[(x["ny"]>=start2)&(x["ny"]<end2)]
    if asia.empty:
        return {"status":"⚪ SEM RANGE ÁSIA", "score":20, "text":"Range asiático não disponível no cache M15."}
    ah=float(asia["high"].max()); al=float(asia["low"].min())
    day_start=pd.Timestamp(day).tz_localize(NY_TZ)
    london=x[(x["ny"]>=day_start+pd.Timedelta(hours=2))&(x["ny"]<day_start+pd.Timedelta(hours=5))]
    ny=x[(x["ny"]>=day_start+pd.Timedelta(hours=7))&(x["ny"]<day_start+pd.Timedelta(hours=10))]
    active=pd.concat([london,ny]).sort_values("datetime") if not london.empty or not ny.empty else pd.DataFrame()
    if active.empty:
        return {"status":"🟡 AGUARDANDO KILLZONE", "score":45, "asia_high":ah,"asia_low":al,"text":"Range Ásia definido; Londres/NY ainda sem dados suficientes."}
    if side=="BUY":
        sweeps=active[(active["low"]<al)&(active["close"]>al)]
        wrong=active[(active["high"]>ah)&(active["close"]<ah)]
        wanted="Asia Low"
    else:
        sweeps=active[(active["high"]>ah)&(active["close"]<ah)]
        wrong=active[(active["low"]<al)&(active["close"]>al)]
        wanted="Asia High"
    if not sweeps.empty:
        r=sweeps.iloc[0]
        return {"status":"🟢 JUDAS / MANIPULAÇÃO COERENTE","score":100,"asia_high":ah,"asia_low":al,"sweep_level":wanted,
                "sweep_time":pd.Timestamp(r["datetime"]).isoformat(),"text":f"Sessão varreu {wanted} contra o lado macro e fechou de volta no range."}
    if not wrong.empty:
        return {"status":"🔴 MANIPULAÇÃO CONTRÁRIA","score":25,"asia_high":ah,"asia_low":al,"text":"A sessão varreu o lado oposto ao esperado para o viés macro."}
    return {"status":"🟡 SEM JUDAS CONFIRMADO","score":55,"asia_high":ah,"asia_low":al,"text":"Range Ásia definido, mas não houve sweep/rejeição coerente nas killzones observadas."}


def _align_frames(a: pd.DataFrame, b: pd.DataFrame, bars: int = 40) -> tuple[pd.DataFrame,pd.DataFrame]:
    """SMT só pode comparar candles que compartilham o mesmo timestamp."""
    aa=_frame(a).tail(bars).copy(); bb=_frame(b).tail(bars).copy()
    if aa.empty or bb.empty or "datetime" not in aa.columns or "datetime" not in bb.columns:
        return pd.DataFrame(),pd.DataFrame()
    aa["datetime"]=pd.to_datetime(aa["datetime"],utc=True,errors="coerce")
    bb["datetime"]=pd.to_datetime(bb["datetime"],utc=True,errors="coerce")
    aa=aa.dropna(subset=["datetime"]); bb=bb.dropna(subset=["datetime"])
    m=aa.merge(bb,on="datetime",how="inner",suffixes=("_a","_b"))
    if len(m)<12:
        return pd.DataFrame(),pd.DataFrame()
    acols={"datetime":"datetime","open_a":"open","high_a":"high","low_a":"low","close_a":"close"}
    bcols={"datetime":"datetime","open_b":"open","high_b":"high","low_b":"low","close_b":"close"}
    return m[list(acols)].rename(columns=acols).reset_index(drop=True), m[list(bcols)].rename(columns=bcols).reset_index(drop=True)


def detect_smt(primary: pd.DataFrame | None, companion: pd.DataFrame | None, pair: str, companion_pair: str, side: str) -> dict[str, Any]:
    a,b=_align_frames(_frame(primary),_frame(companion),48)
    if len(a)<16 or len(b)<16 or side not in ("BUY","SELL"):
        return {"status":"⚪ SMT INDISPONÍVEL","score":0,"companion":companion_pair or "—","text":"Sem dados sincronizados suficientes para SMT."}
    split=max(8,len(a)-8)
    a_prev=a.iloc[:split]; a_now=a.iloc[split:]
    b_prev=b.iloc[:split]; b_now=b.iloc[split:]
    if side=="BUY":
        a_ext=float(a_now["low"].min()) < float(a_prev["low"].min())
        b_ext=float(b_now["low"].min()) < float(b_prev["low"].min())
        if a_ext and not b_ext:
            return {"status":"🟢 SMT BULLISH","score":100,"companion":companion_pair,"text":f"{pair} fez nova mínima e {companion_pair} não confirmou: divergência favorável ao BUY."}
        if b_ext and not a_ext:
            return {"status":"🟡 SMT NO COMPANHEIRO","score":55,"companion":companion_pair,"text":f"{companion_pair} fez a mínima não confirmada; SMT existe, mas não no par selecionado."}
    else:
        a_ext=float(a_now["high"].max()) > float(a_prev["high"].max())
        b_ext=float(b_now["high"].max()) > float(b_prev["high"].max())
        if a_ext and not b_ext:
            return {"status":"🟢 SMT BEARISH","score":100,"companion":companion_pair,"text":f"{pair} fez nova máxima e {companion_pair} não confirmou: divergência favorável ao SELL."}
        if b_ext and not a_ext:
            return {"status":"🟡 SMT NO COMPANHEIRO","score":55,"companion":companion_pair,"text":f"{companion_pair} fez a máxima não confirmada; SMT existe, mas não no par selecionado."}
    return {"status":"⚪ SEM SMT","score":40,"companion":companion_pair,"text":"Os mercados correlacionados confirmaram o extremo ou não houve divergência recente."}


def build_institutional_snapshot(
    pair: str,
    h1: pd.DataFrame | None,
    m15: pd.DataFrame | None,
    side: str,
    companion_m15: pd.DataFrame | None = None,
    companion_pair: str | None = None,
) -> dict[str, Any]:
    disp=detect_displacement(m15,side)
    mss=detect_mss(m15,side)
    pdloc=detect_dealing_range(h1,side)
    liq=detect_liquidity_engine(h1,m15,side)
    session=detect_session_judas(m15,side)
    zone=detect_orderflow_zone(h1,side)
    smt=detect_smt(m15,companion_m15,pair,companion_pair or "",side) if companion_pair else {"status":"⚪ SEM PAR SMT","score":45,"companion":"—","text":"Não há companion SMT primário configurado para este par."}

    parts={"displacement":disp,"mss":mss,"smt":smt,"dealing_range":pdloc,"liquidity":liq,"session":session,"pd_array":zone}
    weights={"displacement":.18,"mss":.22,"smt":.14,"dealing_range":.12,"liquidity":.12,"session":.10,"pd_array":.12}
    scores={k:_finite(v.get("score"),0) for k,v in parts.items()}
    readiness=float(np.clip(sum(scores[k]*weights[k] for k in weights),0,100))

    hard_confirm = scores["mss"]>=75 and scores["displacement"]>=60
    if side not in ("BUY","SELL"):
        label="⚪ MACRO AGUARDAR"
        readiness=0.0
    elif readiness>=82 and hard_confirm:
        label="🟢 FLUXO INSTITUCIONAL FORTE"
    elif readiness>=67 and hard_confirm:
        label="🟡 FLUXO EM CONFIRMAÇÃO"
    elif readiness>=52:
        label="🟡 CONTEXTO INSTITUCIONAL PARCIAL"
    else:
        label="⚪ FLUXO INCOMPLETO"
    return {
        "pair":pair,"side":side,"readiness":round(readiness,1),"label":label,
        **parts,
        "updated_at":pd.Timestamp.now(tz="UTC").isoformat(),
        "algorithm_note":"Score de prontidão observacional; não é probabilidade de lucro.",
    }
