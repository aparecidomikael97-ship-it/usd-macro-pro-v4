"""AtlasQuant V11.2 — Paper Trading Engine.

Simulação determinística e auditável. Nunca envia ordens reais e nunca se
conecta a corretora. Uma operação simulada só nasce quando o Decision
Integrity está EXECUTÁVEL e sem bloqueios duros ou brandos.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from decision_integrity_v110 import evaluate_decision_integrity
from atlasquant_risk_guardian import daily_gain_lock

PAPER_VERSION = "V11.2_PAPER_TRADING"
PAPER_COLUMNS = [
    "trade_id", "signal_id", "pair", "side", "setup_id", "setup_attribution", "status", "result",
    "signal_time", "signal_candle_time", "entry_time", "entry_price",
    "stop_price", "target_price", "risk_distance", "target_rr",
    "exit_time", "exit_price", "exit_reason", "realized_r",
    "bars_held", "mfe_r", "mae_r", "ambiguous_touch",
    "score_master", "quality", "rank_index", "h4", "h1", "m15",
    "ict_readiness", "institutional_readiness", "gate", "gate_score",
    "adr_used_pct", "event_risk", "technical_age_min", "map_age_min",
    "data_sufficient", "data_quality_pct", "d1_regime", "w1_regime", "active_session",
    "checklist_passed", "checklist_note",
    "created_at", "updated_at", "engine_version",
]
ACTIVE_STATUSES = {"WAIT_ENTRY", "OPEN"}
TRUSTED_SETUP_ATTRIBUTIONS = {"EXPLICIT_INPUT", "MANUAL_TAG", "SOURCE_MODEL_EXPLICIT"}
MAX_HOLD_BARS = 96
STOP_ATR_MULT = 1.0
TARGET_R = 2.0


def _finite(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _missing(v: Any) -> bool:
    if v is None:
        return True
    try:
        flag = pd.isna(v)
        return bool(flag) if isinstance(flag, (bool, np.bool_)) else False
    except Exception:
        return False


def _as_utc(v: Any) -> pd.Timestamp | None:
    if _missing(v) or v == "":
        return None
    try:
        t = pd.to_datetime(v, utc=True, errors="coerce")
        return None if pd.isna(t) else pd.Timestamp(t)
    except Exception:
        return None


def _age_minutes(v: Any, now: pd.Timestamp) -> float | None:
    t = _as_utc(v)
    if t is None:
        return None
    age = float((now - t).total_seconds() / 60.0)
    # Future-dated evidence is not fresh evidence. Fail closed instead of
    # clamping clock/data errors to age zero.
    if age < 0:
        return None
    return age


def _side(direction: Any) -> str:
    u = str(direction or "").upper()
    if "COMPRA" in u or u == "BUY":
        return "BUY"
    if "VENDA" in u or u == "SELL":
        return "SELL"
    return "WAIT"


def _explicit_setup_id(input_row: Mapping[str, Any] | None) -> str:
    """Return only an explicitly supplied setup identifier.

    No ICT/SMC component, score or outcome is used to infer a setup. This keeps
    Paper/Forward attribution auditable and avoids retroactive labeling.
    """
    row=dict(input_row or {})
    for key in ("setup_id","Setup ID","setup","Setup","operacional","Operacional"):
        value=str(row.get(key) or "").strip()
        if value:
            return value.casefold()
    return ""


def normalize_m15(records: Any) -> pd.DataFrame:
    try:
        d = pd.DataFrame(records or []).copy()
    except Exception:
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close"])
    req = ["datetime", "open", "high", "low", "close"]
    if any(c not in d.columns for c in req):
        return pd.DataFrame(columns=req)
    d = d[req].copy()
    d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    for c in ("open", "high", "low", "close"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=req)
    if d.empty:
        return d.reset_index(drop=True)
    finite = np.isfinite(d[["open", "high", "low", "close"]]).all(axis=1)
    positive = (d[["open", "high", "low", "close"]] > 0).all(axis=1)
    geometry = (
        d["high"].ge(d[["open", "close", "low"]].max(axis=1))
        & d["low"].le(d[["open", "close", "high"]].min(axis=1))
    )
    return (
        d[finite & positive & geometry]
        .sort_values("datetime")
        .drop_duplicates("datetime", keep="last")
        .reset_index(drop=True)
    )


def _atr_before_entry(frame: pd.DataFrame, entry_time: pd.Timestamp, length: int = 14) -> float | None:
    d = frame[frame["datetime"] < entry_time].copy()
    if len(d) < 8:
        return None
    prev = d["close"].shift(1)
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - prev).abs(),
        (d["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(length, min_periods=5).mean().iloc[-1]
    if pd.isna(atr) or not math.isfinite(float(atr)) or float(atr) <= 0:
        return None
    return float(atr)


def _pair_rows(inputs: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in (inputs or {}).get("pairs", []) or []:
        if isinstance(row, Mapping) and row.get("Par"):
            out[str(row["Par"])] = dict(row)
    return out


def _scanner_rows(scanner: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = (scanner or {}).get("resultados", {})
    return {str(k): dict(v or {}) for k, v in raw.items()} if isinstance(raw, Mapping) else {}


def _map_rows(master: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = (master or {}).get("contexts", {})
    return {str(k): dict(v or {}) for k, v in raw.items()} if isinstance(raw, Mapping) else {}


def _m15_frame(scanner_pair: Mapping[str, Any]) -> pd.DataFrame:
    tec = dict((scanner_pair or {}).get("tecnico", {}) or {})
    cache = dict(tec.get("cache_v110", {}) or {})
    return normalize_m15(cache.get("m15", []))


def evaluate_pair_checklist(
    pair: str,
    input_row: Mapping[str, Any],
    scanner_pair: Mapping[str, Any],
    map_ctx: Mapping[str, Any],
    *,
    now: pd.Timestamp | None = None,
    execution_timeframe: str = "M15",
) -> dict[str, Any]:
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    direction = str((input_row or {}).get("Direção", (input_row or {}).get("Direcao", "")))
    side = _side(direction)
    tec = dict((scanner_pair or {}).get("tecnico", {}) or {})
    h4 = str((tec.get("h4", {}) or {}).get("status", ""))
    h1 = str((tec.get("h1", {}) or {}).get("status", ""))
    m15 = str((tec.get("m15", {}) or {}).get("status", ""))
    ict = dict(tec.get("ict", {}) or {})
    inst = dict(tec.get("institutional", {}) or {})
    execution_tf=str(execution_timeframe or "M15").strip().upper()
    fetched_key={"M15":"m15_fetched_at","H1":"h1_fetched_at","H4":"h4_fetched_at"}.get(execution_tf,"")
    technical_age = _age_minutes(
        ((scanner_pair or {}).get(fetched_key) if fetched_key else None)
        or tec.get("ultima_atualizacao"),
        now,
    )
    map_age = _age_minutes((map_ctx or {}).get("updated_at"), now)
    tec_available = bool(tec.get("dados_disponiveis", tec.get("disponivel", False)))
    map_current = map_age is not None and map_age <= 75.0
    technical_current = technical_age is not None and technical_age <= 75.0
    data_sufficient = bool(tec_available and map_current and technical_current)
    data_score = 100.0 if data_sufficient else 0.0
    adr_raw = (map_ctx or {}).get("adr_used_pct")
    adr = None if _missing(adr_raw) or adr_raw == "" else _finite(adr_raw)

    decision = evaluate_decision_integrity(
        side=side,
        score=_finite((input_row or {}).get("Score final", 0)),
        quality=_finite((input_row or {}).get("Qualidade", 0)),
        rank_index=_finite((input_row or {}).get("Índice ranking", (input_row or {}).get("Indice ranking", 0))),
        h4=h4,
        h1=h1,
        m15=m15,
        ict_readiness=_finite(ict.get("readiness", 0)),
        institutional_readiness=_finite(inst.get("readiness", 0)),
        gate=str((map_ctx or {}).get("readiness_grade", "WAIT")),
        gate_score=_finite((map_ctx or {}).get("readiness_score", 0)),
        adr_used_pct=adr,
        event_risk=str((map_ctx or {}).get("event_risk", "DESCONHECIDO")),
        technical_age_min=technical_age,
        data_sufficient=data_sufficient,
        data_readiness_score=data_score,
        execution_timeframe=execution_tf,
    )

    # Higher-timeframe reading is part of the execution contract, not a bonus.
    # H1 entries use H4 as technical context/trigger chain and require D1 bias
    # to agree with the macro side. Missing/neutral/opposite D1 fails closed.
    d1_ctx=dict((map_ctx or {}).get("d1",{}) or {})
    w1_ctx=dict((map_ctx or {}).get("w1",{}) or {})
    d1_bias=str(d1_ctx.get("bias","") or "").strip().upper()
    w1_bias=str(w1_ctx.get("bias","") or "").strip().upper()
    expected_bias="ALTISTA" if side=="BUY" else "BAIXISTA" if side=="SELL" else ""
    higher_context_required=[]
    higher_context_aligned=True
    higher_context_reason="NOT_REQUIRED"
    if execution_tf=="H1":
        higher_context_required=["H4","D1"]
        higher_context_aligned=bool(expected_bias and d1_bias==expected_bias)
        higher_context_reason=(
            "H4_D1_ALIGNED"
            if higher_context_aligned
            else ("D1_CONTEXT_MISSING" if not d1_bias else f"D1_{d1_bias}_VS_{expected_bias or 'SEM_DIRECAO'}")
        )
        if not higher_context_aligned:
            decision=dict(decision or {})
            hard=list(decision.get("hard_blocks",[]) or [])
            message=(
                "Contexto D1 ausente para execução H1"
                if not d1_bias
                else f"Contexto D1 não alinha com execução H1 ({d1_bias} vs {expected_bias or 'SEM DIREÇÃO'})"
            )
            if message not in hard:
                hard.append(message)
            decision["hard_blocks"]=hard
            decision["executable"]=False
            decision["state"]="🔴 BLOQUEADO"
            decision["next_action"]="Aguardar D1 alinhar com a direção antes de considerar o gatilho H1."

    all_clear = bool(
        data_sufficient
        and decision.get("executable")
        and not (decision.get("hard_blocks") or [])
        and not (decision.get("soft_blocks") or [])
    )
    killzone=dict((map_ctx or {}).get("killzone",{}) or {})
    active=killzone.get("active")
    if isinstance(active,Mapping):
        active_session=str(active.get("name","") or "")
    else:
        active_session=str(active or "")
    d1_regime=str(
        dict(dict((map_ctx or {}).get("d1",{}) or {}).get("structure",{}) or {}).get("regime","")
        or ""
    )
    w1_regime=str(
        dict(dict((map_ctx or {}).get("w1",{}) or {}).get("structure",{}) or {}).get("regime","")
        or ""
    )
    setup_id=_explicit_setup_id(input_row)

    return {
        "pair": pair,
        "side": side,
        "execution_timeframe": execution_tf,
        "higher_timeframe_context":{
            "required":higher_context_required,
            "expected_bias":expected_bias,
            "d1_bias":d1_bias,
            "w1_bias":w1_bias,
            "aligned":bool(higher_context_aligned),
            "reason":higher_context_reason,
        },
        "direction": direction,
        "setup_id":setup_id,
        "setup_attribution":"EXPLICIT_INPUT" if setup_id else "UNATTRIBUTED",
        "decision": decision,
        "all_checks_passed": all_clear,
        "technical_age_min": technical_age,
        "map_age_min": map_age,
        "data_sufficient": data_sufficient,
        "data_quality_pct": data_score,
        "d1_regime": d1_regime,
        "w1_regime": w1_regime,
        "active_session": active_session,
        "h4": h4,
        "h1": h1,
        "m15": m15,
        "ict_readiness": _finite(ict.get("readiness", 0)),
        "institutional_readiness": _finite(inst.get("readiness", 0)),
        "gate": str((map_ctx or {}).get("readiness_grade", "WAIT")),
        "gate_score": _finite((map_ctx or {}).get("readiness_score", 0)),
        "adr_used_pct": adr,
        "event_risk": str((map_ctx or {}).get("event_risk", "DESCONHECIDO")),
        "score_master": _finite((input_row or {}).get("Score final", 0)),
        "quality": _finite((input_row or {}).get("Qualidade", 0)),
        "rank_index": _finite((input_row or {}).get("Índice ranking", (input_row or {}).get("Indice ranking", 0))),
    }


def _empty_trades() -> pd.DataFrame:
    return pd.DataFrame(columns=PAPER_COLUMNS)


def normalize_trades(trades: pd.DataFrame | None) -> pd.DataFrame:
    if trades is None or trades.empty:
        return _empty_trades()
    d = trades.copy()
    for c in PAPER_COLUMNS:
        if c not in d.columns:
            d[c] = None
    return d[PAPER_COLUMNS].copy()


def _signal_id(pair: str, side: str, candle_time: pd.Timestamp) -> str:
    raw = f"{PAPER_VERSION}|{pair}|{side}|{candle_time.isoformat()}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def _active_pairs(trades: pd.DataFrame) -> set[str]:
    if trades.empty:
        return set()
    mask = trades["status"].astype(str).isin(ACTIVE_STATUSES)
    return set(trades.loc[mask, "pair"].astype(str))


def _make_wait_entry(
    chk: Mapping[str, Any],
    frame: pd.DataFrame,
    *,
    now: pd.Timestamp,
    bar_minutes: int = 15,
) -> dict[str, Any] | None:
    if not chk.get("all_checks_passed") or frame.empty:
        return None
    candle_time = pd.Timestamp(frame.iloc[-1]["datetime"])
    bar_minutes=max(1,int(bar_minutes))
    signal_time = candle_time + pd.Timedelta(minutes=bar_minutes)
    sid = _signal_id(str(chk["pair"]), str(chk["side"]), candle_time)
    row = {c: None for c in PAPER_COLUMNS}
    row.update({
        "trade_id": sid,
        "signal_id": sid,
        "pair": chk["pair"],
        "side": chk["side"],
        "setup_id": chk.get("setup_id",""),
        "setup_attribution": chk.get("setup_attribution","UNATTRIBUTED"),
        "status": "WAIT_ENTRY",
        "result": "",
        "signal_time": signal_time.isoformat(),
        "signal_candle_time": candle_time.isoformat(),
        "target_rr": TARGET_R,
        "score_master": chk["score_master"],
        "quality": chk["quality"],
        "rank_index": chk["rank_index"],
        "h4": chk["h4"],
        "h1": chk["h1"],
        "m15": chk["m15"],
        "ict_readiness": chk["ict_readiness"],
        "institutional_readiness": chk["institutional_readiness"],
        "gate": chk["gate"],
        "gate_score": chk["gate_score"],
        "adr_used_pct": chk["adr_used_pct"],
        "event_risk": chk["event_risk"],
        "technical_age_min": chk["technical_age_min"],
        "map_age_min": chk["map_age_min"],
        "data_sufficient": chk["data_sufficient"],
        "data_quality_pct": chk.get("data_quality_pct"),
        "d1_regime": chk.get("d1_regime",""),
        "w1_regime": chk.get("w1_regime",""),
        "active_session": chk.get("active_session",""),
        "checklist_passed": True,
        "checklist_note": "Checklist 100% liberado: executável e sem bloqueios duros/brandos.",
        "ambiguous_touch": False,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "engine_version": PAPER_VERSION,
    })
    return row


def _fill_entry(row: pd.Series, frame: pd.DataFrame, *, now: pd.Timestamp) -> dict[str, Any]:
    out = row.to_dict()
    if str(out.get("status")) != "WAIT_ENTRY" or frame.empty:
        return out
    signal_time = _as_utc(out.get("signal_time"))
    if signal_time is None:
        return out
    eligible = frame[frame["datetime"] >= signal_time]
    if eligible.empty:
        return out
    entry_bar = eligible.iloc[0]
    entry_time = pd.Timestamp(entry_bar["datetime"])
    atr = _atr_before_entry(frame, entry_time)
    if atr is None:
        return out
    entry = float(entry_bar["open"])
    side = str(out.get("side"))
    risk = atr * STOP_ATR_MULT
    if side == "BUY":
        stop, target = entry - risk, entry + risk * TARGET_R
    elif side == "SELL":
        stop, target = entry + risk, entry - risk * TARGET_R
    else:
        return out
    out.update({
        "status": "OPEN",
        "entry_time": entry_time.isoformat(),
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        "risk_distance": risk,
        "updated_at": now.isoformat(),
    })
    return out


def _close_open(
    row: pd.Series,
    frame: pd.DataFrame,
    *,
    now: pd.Timestamp,
    bar_minutes: int = 15,
    max_hold_bars: int = MAX_HOLD_BARS,
) -> dict[str, Any]:
    out = row.to_dict()
    if str(out.get("status")) != "OPEN" or frame.empty:
        return out
    et = _as_utc(out.get("entry_time"))
    if et is None:
        return out
    entry = _finite(out.get("entry_price"), float("nan"))
    stop = _finite(out.get("stop_price"), float("nan"))
    target = _finite(out.get("target_price"), float("nan"))
    risk = _finite(out.get("risk_distance"), float("nan"))
    if not all(math.isfinite(x) and x > 0 for x in (entry, stop, target, risk)):
        return out
    side = str(out.get("side"))
    bars = frame[frame["datetime"] >= et].copy()
    if bars.empty:
        return out

    favorable: list[float] = []
    adverse: list[float] = []
    exit_idx = None
    exit_price = None
    exit_reason = ""
    result = ""
    ambiguous = False

    for j, (_, b) in enumerate(bars.iterrows(), start=1):
        high, low, close = float(b["high"]), float(b["low"]), float(b["close"])
        if side == "BUY":
            favorable.append((high - entry) / risk)
            adverse.append((entry - low) / risk)
            hit_stop, hit_target = low <= stop, high >= target
        else:
            favorable.append((entry - low) / risk)
            adverse.append((high - entry) / risk)
            hit_stop, hit_target = high >= stop, low <= target

        if hit_stop and hit_target:
            exit_idx, exit_price, exit_reason, result, ambiguous = (
                j, stop, "STOP_AND_TARGET_SAME_CANDLE", "LOSS", True
            )
            break
        if hit_stop:
            exit_idx, exit_price, exit_reason, result = j, stop, "STOP", "LOSS"
            break
        if hit_target:
            exit_idx, exit_price, exit_reason, result = j, target, "TARGET", "WIN"
            break
        if j >= max(1,int(max_hold_bars)):
            total_minutes=max(1,int(bar_minutes))*max(1,int(max_hold_bars))
            if int(bar_minutes)==15 and int(max_hold_bars)==MAX_HOLD_BARS:
                exit_label="TIME_EXIT_24H"
            elif total_minutes % 1440 == 0:
                exit_label=f"TIME_EXIT_{total_minutes//1440}D"
            elif total_minutes % 60 == 0:
                exit_label=f"TIME_EXIT_{total_minutes//60}H"
            else:
                exit_label=f"TIME_EXIT_{total_minutes}M"
            exit_idx, exit_price, exit_reason = j, close, exit_label
            rr = ((exit_price - entry) / risk) if side == "BUY" else ((entry - exit_price) / risk)
            result = "WIN" if rr > 1e-12 else "LOSS" if rr < -1e-12 else "BREAKEVEN"
            break

    out["bars_held"] = int(exit_idx or len(bars))
    out["mfe_r"] = round(max(favorable), 4) if favorable else 0.0
    out["mae_r"] = round(max(adverse), 4) if adverse else 0.0
    if exit_idx is None:
        out["updated_at"] = now.isoformat()
        return out

    exit_bar = bars.iloc[exit_idx - 1]
    xp = float(exit_price)
    rr = ((xp - entry) / risk) if side == "BUY" else ((entry - xp) / risk)
    out.update({
        "status": "CLOSED",
        "result": result,
        "exit_time": (pd.Timestamp(exit_bar["datetime"]) + pd.Timedelta(minutes=max(1,int(bar_minutes)))).isoformat(),
        "exit_price": xp,
        "exit_reason": exit_reason,
        "realized_r": round(rr, 4),
        "ambiguous_touch": bool(ambiguous),
        "updated_at": now.isoformat(),
    })
    return out


def summarize_paper_trades(trades: pd.DataFrame) -> dict[str, Any]:
    d = normalize_trades(trades)
    closed = d[d["status"].astype(str) == "CLOSED"].copy()
    wins = int((closed["result"].astype(str) == "WIN").sum())
    losses = int((closed["result"].astype(str) == "LOSS").sum())
    breakeven = int((closed["result"].astype(str) == "BREAKEVEN").sum())
    rr = pd.to_numeric(closed["realized_r"], errors="coerce").dropna()
    rr = rr[rr.map(lambda x: math.isfinite(float(x)))]
    gross_win = float(rr[rr > 0].sum()) if not rr.empty else 0.0
    gross_loss = float(-rr[rr < 0].sum()) if not rr.empty else 0.0
    profit_factor = None if gross_loss <= 0 else gross_win / gross_loss
    by_setup: dict[str, Any] = {}
    if "setup_id" in closed.columns:
        setup_mask=closed["setup_id"].fillna("").astype(str).str.strip().ne("")
        if "setup_attribution" in closed.columns:
            attribution_mask=closed["setup_attribution"].fillna("").astype(str).str.upper().isin(TRUSTED_SETUP_ATTRIBUTIONS)
        else:
            attribution_mask=pd.Series(False,index=closed.index)
        tagged=closed[setup_mask & attribution_mask].copy()
        for setup_id,g in tagged.groupby("setup_id",dropna=False):
            gr=pd.to_numeric(g["realized_r"],errors="coerce").dropna()
            gr=gr[gr.map(lambda x: math.isfinite(float(x)))]
            gw=int((g["result"].astype(str)=="WIN").sum())
            gl=int((g["result"].astype(str)=="LOSS").sum())
            gross_win=float(gr[gr>0].sum()) if not gr.empty else 0.0
            gross_loss=float(-gr[gr<0].sum()) if not gr.empty else 0.0
            by_setup[str(setup_id)]={
                "trades":int(len(g)),
                "wins":gw,
                "losses":gl,
                "win_rate_pct":round(gw/max(gw+gl,1)*100.0,1),
                "net_r":round(float(gr.sum()) if not gr.empty else 0.0,3),
                "avg_r":round(float(gr.mean()) if not gr.empty else 0.0,3),
                "profit_factor_r":None if gross_loss<=0 else round(gross_win/gross_loss,3),
                "explicit_attribution_only":True,
            }

    by_pair: dict[str, Any] = {}
    for pair, g in closed.groupby("pair", dropna=False):
        gr = pd.to_numeric(g["realized_r"], errors="coerce").dropna()
        gr = gr[gr.map(lambda x: math.isfinite(float(x)))]
        gw = int((g["result"].astype(str) == "WIN").sum())
        gl = int((g["result"].astype(str) == "LOSS").sum())
        by_pair[str(pair)] = {
            "trades": int(len(g)),
            "wins": gw,
            "losses": gl,
            "win_rate_pct": round(gw / max(gw + gl, 1) * 100.0, 1),
            "net_r": round(float(gr.sum()) if not gr.empty else 0.0, 3),
            "avg_r": round(float(gr.mean()) if not gr.empty else 0.0, 3),
        }
    return {
        "version": PAPER_VERSION,
        "trades_total": int(len(d)),
        "pending_entries": int((d["status"].astype(str) == "WAIT_ENTRY").sum()),
        "open_positions": int((d["status"].astype(str) == "OPEN").sum()),
        "closed_trades": int(len(closed)),
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate_pct": round(wins / max(wins + losses, 1) * 100.0, 1),
        "net_r": round(float(rr.sum()) if not rr.empty else 0.0, 3),
        "avg_r": round(float(rr.mean()) if not rr.empty else 0.0, 3),
        "profit_factor_r": None if profit_factor is None else round(float(profit_factor), 3),
        "by_pair": by_pair,
        "by_setup": by_setup,
        "setup_attribution_inferred": False,
    }


def _daily_closed_wins(trades: pd.DataFrame, now: pd.Timestamp) -> int:
    """Count only wins whose audited exit timestamp belongs to the UTC paper day."""
    d = normalize_trades(trades)
    if d.empty:
        return 0
    closed = d[
        (d["status"].astype(str) == "CLOSED")
        & (d["result"].astype(str) == "WIN")
    ].copy()
    if closed.empty:
        return 0
    exits = pd.to_datetime(closed["exit_time"], utc=True, errors="coerce")
    day = pd.Timestamp(now).tz_convert("UTC").date()
    return int(sum(pd.notna(ts) and pd.Timestamp(ts).date() == day for ts in exits))


def _cancel_wait_entries_for_gain_lock(
    trades: pd.DataFrame,
    *,
    now: pd.Timestamp,
    reason: str,
) -> tuple[pd.DataFrame, int]:
    d = normalize_trades(trades)
    if d.empty:
        return d, 0
    mask = d["status"].astype(str) == "WAIT_ENTRY"
    count = int(mask.sum())
    if not count:
        return d, 0
    d.loc[mask, "status"] = "CANCELLED_RISK_LOCK"
    d.loc[mask, "updated_at"] = now.isoformat()
    note = "Risk Guardian: " + str(reason or "meta diária de gains atingida")
    d.loc[mask, "checklist_note"] = note
    return normalize_trades(d), count


def run_paper_cycle(
    inputs: Mapping[str, Any],
    scanner: Mapping[str, Any],
    master: Mapping[str, Any],
    trades: pd.DataFrame | None = None,
    *,
    now: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    d = normalize_trades(trades)
    inputs_by_pair = _pair_rows(inputs or {})
    scanner_by_pair = _scanner_rows(scanner or {})
    map_by_pair = _map_rows(master or {})
    opened = 0
    closed = 0
    pending_created = 0
    pending_cancelled_by_gain_lock = 0
    closed_pairs_this_cycle: set[str] = set()

    # Fase 1: fecha posições que já estavam abertas ANTES de permitir qualquer
    # nova entrada pendente. Assim, o segundo gain do dia trava a terceira
    # operação antes que um WAIT_ENTRY antigo possa virar OPEN no mesmo ciclo.
    if not d.empty:
        rows = []
        for _, row in d.iterrows():
            pair = str(row.get("pair", ""))
            frame = _m15_frame(scanner_by_pair.get(pair, {}))
            before = str(row.get("status", ""))
            if before == "OPEN":
                upd = _close_open(row, frame, now=now)
                if str(upd.get("status")) == "CLOSED":
                    closed += 1
                    closed_pairs_this_cycle.add(pair)
            else:
                upd = row.to_dict()
            rows.append(upd)
        d = normalize_trades(pd.DataFrame(rows))

    wins_today = _daily_closed_wins(d, now)
    daily_gain_locked, daily_gain_reason = daily_gain_lock(wins_today, 2)

    # Fase 2: só depois do fechamento auditado decide se WAIT_ENTRY pode abrir.
    # Se 2 gains já foram realizados hoje, pendências são canceladas, não abertas.
    if daily_gain_locked:
        d, pending_cancelled_by_gain_lock = _cancel_wait_entries_for_gain_lock(
            d,
            now=now,
            reason=daily_gain_reason,
        )
    elif not d.empty:
        rows = []
        for _, row in d.iterrows():
            pair = str(row.get("pair", ""))
            frame = _m15_frame(scanner_by_pair.get(pair, {}))
            before = str(row.get("status", ""))
            if before != "WAIT_ENTRY":
                rows.append(row.to_dict())
                continue

            upd = _fill_entry(row, frame, now=now)
            if str(upd.get("status")) == "OPEN":
                opened += 1
                upd2 = _close_open(pd.Series(upd), frame, now=now)
                if str(upd2.get("status")) == "CLOSED":
                    closed += 1
                    closed_pairs_this_cycle.add(pair)
                    if str(upd2.get("result")) == "WIN":
                        exit_ts = _as_utc(upd2.get("exit_time"))
                        if exit_ts is not None and exit_ts.date() == now.date():
                            wins_today += 1
                            daily_gain_locked, daily_gain_reason = daily_gain_lock(
                                wins_today, 2
                            )
                rows.append(upd2)
            else:
                rows.append(upd)

        d = normalize_trades(pd.DataFrame(rows))
        if daily_gain_locked:
            d, cancelled_now = _cancel_wait_entries_for_gain_lock(
                d,
                now=now,
                reason=daily_gain_reason,
            )
            pending_cancelled_by_gain_lock += cancelled_now

    active_pairs = _active_pairs(d)
    existing_signals = set(d["signal_id"].astype(str)) if not d.empty else set()
    checklist_states: dict[str, Any] = {}

    # Depois cria sinais novos. A entrada sempre espera o M15 posterior ao sinal.
    for pair, input_row in inputs_by_pair.items():
        scanner_pair = scanner_by_pair.get(pair, {})
        map_ctx = map_by_pair.get(pair, {})
        chk = evaluate_pair_checklist(pair, input_row, scanner_pair, map_ctx, now=now)
        _hard_blocks = list(chk["decision"].get("hard_blocks", []) or [])
        _passed = bool(chk["all_checks_passed"])
        _state = str(chk["decision"].get("state", ""))
        if daily_gain_locked:
            if daily_gain_reason and daily_gain_reason not in _hard_blocks:
                _hard_blocks.append(daily_gain_reason)
            _passed = False
            _state = "🔒 DAILY GAIN LOCK"
        checklist_states[pair] = {
            "side": chk["side"],
            "passed": _passed,
            "state": _state,
            "hard_blocks": _hard_blocks,
            "soft_blocks": list(chk["decision"].get("soft_blocks", []) or []),
            "daily_gain_lock": bool(daily_gain_locked),
        }
        if daily_gain_locked:
            continue
        if pair in active_pairs or pair in closed_pairs_this_cycle:
            continue
        frame = _m15_frame(scanner_pair)
        candidate = _make_wait_entry(chk, frame, now=now)
        if not candidate or str(candidate["signal_id"]) in existing_signals:
            continue
        d = pd.concat([d, pd.DataFrame([candidate])], ignore_index=True)
        active_pairs.add(pair)
        existing_signals.add(str(candidate["signal_id"]))
        pending_created += 1

    d = normalize_trades(d)
    summary = summarize_paper_trades(d)
    cycle = {
        "version": PAPER_VERSION,
        "ran_at": now.isoformat(),
        "pending_created": pending_created,
        "pending_cancelled_by_gain_lock": pending_cancelled_by_gain_lock,
        "entries_opened": opened,
        "trades_closed": closed,
        "wins_today": int(wins_today),
        "daily_gain_lock": bool(daily_gain_locked),
        "daily_gain_lock_reason": str(daily_gain_reason or ""),
        "closed_pairs_this_cycle": sorted(closed_pairs_this_cycle),
        "checklists": checklist_states,
        **{k: summary[k] for k in (
            "trades_total", "pending_entries", "open_positions", "closed_trades",
            "wins", "losses", "breakeven", "win_rate_pct", "net_r", "avg_r", "profit_factor_r",
        )},
    }
    return d, cycle
