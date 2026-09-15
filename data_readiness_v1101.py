"""USD Macro Pro V11.0.1 — Data Readiness & Institutional Integrity.

Avalia se os dados persistidos são recentes e suficientes para uma decisão
operacional. Não faz chamadas de API e não produz probabilidade de lucro.
"""
from __future__ import annotations
from typing import Any, Mapping
import math
import pandas as pd

TF_LIMITS = {
    "m15": {"fresh": 60.0, "warn": 90.0},
    "h1":  {"fresh": 150.0, "warn": 210.0},
    "h4":  {"fresh": 360.0, "warn": 480.0},
}
MIN_CACHE = {"m15": 32, "h1": 12}


def _age_minutes(value: Any, now: pd.Timestamp | None = None) -> float | None:
    if value in (None, "", 0, 0.0):
        return None
    try:
        ts = pd.Timestamp(float(value), unit="s", tz="UTC") if isinstance(value, (int, float)) else pd.to_datetime(value, utc=True)
        ref = now if now is not None else pd.Timestamp.now(tz="UTC")
        return max(0.0, (ref - ts).total_seconds() / 60.0)
    except Exception:
        return None


def _freshness(tf: str, age: float | None) -> dict[str, Any]:
    lim = TF_LIMITS[tf]
    if age is None:
        return {"age_minutes": None, "state": "⚪ SEM TIMESTAMP", "score": 0.0, "fresh": False, "usable": False}
    if age <= lim["fresh"]:
        return {"age_minutes": round(age, 1), "state": "🟢 FRESCO", "score": 100.0, "fresh": True, "usable": True}
    if age <= lim["warn"]:
        return {"age_minutes": round(age, 1), "state": "🟡 ENVELHECENDO", "score": 55.0, "fresh": False, "usable": True}
    return {"age_minutes": round(age, 1), "state": "🔴 DESATUALIZADO", "score": 0.0, "fresh": False, "usable": False}


def _status_present(v: Any) -> bool:
    s = str(v or "").strip()
    return bool(s and s not in ("—", "None", "nan"))


def _map_ready(map_context: Mapping[str, Any] | None) -> bool:
    c = dict(map_context or {})
    if not c:
        return False
    keys = ("w1_bias", "d1_bias", "w1", "d1", "readiness_grade", "event_risk", "adr_used_pct")
    return any(c.get(k) not in (None, "", "—") for k in keys)


def assess_pair_data_readiness(
    scanner_row: Mapping[str, Any] | None,
    map_context: Mapping[str, Any] | None = None,
    *,
    now: pd.Timestamp | None = None,
) -> dict[str, Any]:
    raw = dict(scanner_row or {})
    tec = dict(raw.get("tecnico", {}) or {})
    cache = dict(tec.get("cache_v110", {}) or {})

    ages = {
        "m15": _age_minutes(raw.get("m15_fetched_at", raw.get("processado_em")), now),
        "h1": _age_minutes(raw.get("h1_fetched_at"), now),
        "h4": _age_minutes(raw.get("h4_fetched_at"), now),
    }
    tf = {k: _freshness(k, ages[k]) for k in ("m15", "h1", "h4")}

    m15_bars = len(cache.get("m15", []) or [])
    h1_bars = len(cache.get("h1", []) or [])
    cache_m15_score = 100.0 if m15_bars >= MIN_CACHE["m15"] else 55.0 if m15_bars >= 16 else 0.0
    cache_h1_score = 100.0 if h1_bars >= MIN_CACHE["h1"] else 55.0 if h1_bars >= 8 else 0.0

    statuses = {
        "h4": str((tec.get("h4", {}) or {}).get("status", "—")),
        "h1": str((tec.get("h1", {}) or {}).get("status", "—")),
        "m15": str((tec.get("m15", {}) or {}).get("status", "—")),
    }
    status_complete = all(_status_present(v) for v in statuses.values())
    map_ok = _map_ready(map_context)

    score = (
        tf["m15"]["score"] * .25 + tf["h1"]["score"] * .20 + tf["h4"]["score"] * .15 +
        cache_m15_score * .15 + cache_h1_score * .15 +
        (100.0 if status_complete else 0.0) * .05 + (100.0 if map_ok else 0.0) * .05
    )

    missing: list[str] = []
    if not tf["m15"]["fresh"]:
        missing.append("M15 sem frescor operacional" if ages["m15"] is not None else "M15 sem timestamp")
    if not tf["h1"]["fresh"]:
        missing.append("H1 sem frescor operacional" if ages["h1"] is not None else "H1 sem timestamp")
    if not tf["h4"]["fresh"]:
        missing.append("H4 sem frescor operacional" if ages["h4"] is not None else "H4 sem timestamp")
    if m15_bars < MIN_CACHE["m15"]:
        missing.append(f"cache M15 insuficiente ({m15_bars}/{MIN_CACHE['m15']})")
    if h1_bars < MIN_CACHE["h1"]:
        missing.append(f"cache H1 insuficiente ({h1_bars}/{MIN_CACHE['h1']})")
    if not status_complete:
        missing.append("H4/H1/M15 sem leitura completa")

    sufficient = (
        tf["m15"]["fresh"] and tf["h1"]["fresh"] and tf["h4"]["fresh"] and
        m15_bars >= MIN_CACHE["m15"] and h1_bars >= MIN_CACHE["h1"] and status_complete
    )
    institutional_data_ready = (
        tf["m15"]["fresh"] and tf["h1"]["fresh"] and
        m15_bars >= MIN_CACHE["m15"] and h1_bars >= MIN_CACHE["h1"]
    )

    if sufficient and score >= 85:
        label = "🟢 DADOS SUFICIENTES"
    elif score >= 55:
        label = "🟡 DADOS PARCIAIS"
    else:
        label = "🔴 DADOS INSUFICIENTES"

    return {
        "score": round(float(score), 1),
        "label": label,
        "sufficient": bool(sufficient),
        "institutional_data_ready": bool(institutional_data_ready),
        "timeframes": tf,
        "cache_m15_bars": int(m15_bars),
        "cache_h1_bars": int(h1_bars),
        "status_complete": bool(status_complete),
        "map_ready": bool(map_ok),
        "missing": missing,
        "note": "Readiness de dados; não é probabilidade de lucro.",
    }


def display_component_status(component: Mapping[str, Any] | None, key: str, readiness: Mapping[str, Any]) -> tuple[str, str]:
    """Evita confundir 'sem dados' com uma leitura neutra do mercado."""
    comp = dict(component or {})
    status = str(comp.get("status", "—"))
    text = str(comp.get("text", ""))
    low = text.lower()

    h1_keys = {"dealing_range", "pd_array", "liquidity"}
    m15_keys = {"mss", "displacement", "session", "smt"}
    tf = dict(readiness.get("timeframes", {}) or {})

    if key in h1_keys and not bool(readiness.get("institutional_data_ready", False)):
        if not tf.get("h1", {}).get("fresh", False) or readiness.get("cache_h1_bars", 0) < MIN_CACHE["h1"]:
            return "⏳ DADOS H1 INSUFICIENTES", "A leitura existe somente quando H1 recente e cache mínimo estão disponíveis."
    if key in m15_keys and not bool(readiness.get("institutional_data_ready", False)):
        if not tf.get("m15", {}).get("fresh", False) or readiness.get("cache_m15_bars", 0) < MIN_CACHE["m15"]:
            return "⏳ DADOS M15 INSUFICIENTES", "A leitura existe somente quando M15 recente e cache mínimo estão disponíveis."

    no_data_markers = (
        "sem h1 suficiente", "sem m15 suficiente", "sem dados sincronizados",
        "aguardando candles válidos", "aguarda estrutura válida", "range indefinido",
    )
    if float(comp.get("score", 0) or 0) == 0 and any(x in low for x in no_data_markers):
        return "⏳ DADOS INSUFICIENTES", text or "Dados insuficientes para avaliar esta camada."
    return status, text


def premium_discount_operational(side: str, component: Mapping[str, Any] | None, readiness: Mapping[str, Any]) -> dict[str, str]:
    comp = dict(component or {})
    if not bool(readiness.get("institutional_data_ready", False)):
        return {"status": "⏳ AGUARDANDO H1 FRESCO", "text": "Sem H1 recente suficiente para validar Premium/Discount."}
    zone = str(comp.get("zone", "INDEFINIDO")).upper()
    pos = comp.get("position_pct")
    side = str(side).upper()
    pos_txt = f" ({float(pos):.1f}% do range)" if pos is not None else ""
    if zone == "DESCONTO":
        if side == "BUY": return {"status": "🟢 BUY EM DESCONTO", "text": "Localização favorece compra" + pos_txt + "."}
        if side == "SELL": return {"status": "🔴 SELL EM DESCONTO", "text": "Venda está barata demais no dealing range" + pos_txt + "."}
    if zone in ("PRÊMIO", "PREMIO"):
        if side == "SELL": return {"status": "🟢 SELL EM PRÊMIO", "text": "Localização favorece venda" + pos_txt + "."}
        if side == "BUY": return {"status": "🔴 BUY EM PRÊMIO", "text": "Compra está cara no dealing range" + pos_txt + "."}
    if zone == "EQUILÍBRIO":
        return {"status": "🟡 EM EQUILÍBRIO", "text": "Preço próximo de 50% do dealing range; localização não oferece vantagem clara."}
    return {"status": "⚪ RANGE INDEFINIDO", "text": "Não foi possível validar a localização no dealing range."}
