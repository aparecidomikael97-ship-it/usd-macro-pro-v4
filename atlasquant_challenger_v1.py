"""AtlasQuant Challenger V1 — strict-gate observation model.

Experimental challenger used only in Shadow Mode. It never changes production
signals and never authorizes a trade that the Champion did not already allow.
"""
from __future__ import annotations

from typing import Any, Mapping
import math


VERSION="AtlasQuant Challenger StrictGate V1"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out=float(value)
        return out if math.isfinite(out) else float(default)
    except Exception:
        return float(default)


def _clean_side(value: Any) -> str:
    side=str(value or "NEUTRAL").upper()
    return side if side in {"BUY","SELL"} else "NEUTRAL"


def _status_ok(value: Any) -> bool:
    s=str(value or "").upper()
    if any(x in s for x in ("🔴","SEM GATILHO","CONTRA","INVALID","BLOQUE")):
        return False
    return any(x in s for x in ("🟢","CONFIRMA","PULLBACK OK","GATILHO","ALINHADO"))


def build_challenger_snapshot(pack: Mapping[str,Any] | None) -> dict[str,Any]:
    p=dict(pack or {})
    dr=dict(p.get("data_ready",{}) or {})
    side=_clean_side(p.get("side"))
    score=_num(p.get("score"))
    quality=_num(p.get("quality"))
    data_score=_num(dr.get("score"))
    macro_abs=abs(_num(p.get("macro_diff")))
    hard=tuple(str(x) for x in (p.get("hard_blocks",[]) or []) if str(x).strip())

    strict_ready=bool(
        bool(p.get("executable",False))
        and bool(dr.get("sufficient",False))
        and not hard
        and side in {"BUY","SELL"}
        and score >= 75.0
        and quality >= 80.0
        and data_score >= 85.0
        and macro_abs >= 7.0
        and _status_ok(p.get("h4"))
        and _status_ok(p.get("h1"))
        and _status_ok(p.get("m15"))
    )

    reasons=[]
    if score < 75: reasons.append("score<75")
    if quality < 80: reasons.append("quality<80")
    if data_score < 85: reasons.append("data_score<85")
    if macro_abs < 7: reasons.append("macro_diff<7")
    if not _status_ok(p.get("h4")): reasons.append("h4_not_strict")
    if not _status_ok(p.get("h1")): reasons.append("h1_not_strict")
    if not _status_ok(p.get("m15")): reasons.append("m15_not_strict")
    if hard: reasons.append("hard_block")
    if not bool(p.get("executable",False)): reasons.append("champion_not_executable")

    return {
        "pair":str(p.get("pair","—")),
        "side":side,
        "state":"STRICT_EXECUTABLE" if strict_ready else "STRICT_WAIT",
        "score":score,
        "data_quality":data_score,
        "executable":strict_ready,
        "version":VERSION,
        "timestamp":str(
            p.get("updated_at")
            or p.get("candle_m15")
            or p.get("timestamp")
            or ""
        ),
        "strict_reasons":reasons,
    }


def champion_snapshot(pack: Mapping[str,Any] | None, *, version: str) -> dict[str,Any]:
    p=dict(pack or {})
    dr=dict(p.get("data_ready",{}) or {})
    return {
        "pair":str(p.get("pair","—")),
        "side":_clean_side(p.get("side")),
        "state":str(p.get("state","—")),
        "score":_num(p.get("score")),
        "data_quality":_num(dr.get("score")),
        "executable":bool(p.get("executable",False)),
        "version":str(version),
        "timestamp":str(
            p.get("updated_at")
            or p.get("candle_m15")
            or p.get("timestamp")
            or ""
        ),
    }
