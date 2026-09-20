"""AtlasQuant structured macro research engine.

Purpose
-------
Build a transparent pair-level macro context from independent evidence groups:
rates, inflation, labour, growth, activity, expectations/surprises and central
banks. This is a research/presentation engine only. It never changes the
operational Score Mestre, Gate, weights, broker state or order permissions.

Upstream inputs should already be normalized when possible. A component score
uses the familiar 0..100 scale where 50 is neutral for the currency. Missing,
stale or low-quality inputs are not silently converted into neutral evidence.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence
import math
import unicodedata

SCHEMA = "ATLASQUANT_STRUCTURED_MACRO_V1"

GROUP_WEIGHTS = {
    "rates": 0.24,
    "inflation": 0.16,
    "labour": 0.14,
    "growth": 0.12,
    "activity": 0.10,
    "expectations": 0.12,
    "central_bank": 0.12,
}
CORE_GROUPS = ("rates", "inflation", "labour", "growth", "activity")


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def _clip(value: Any, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, _finite(value)))


def _norm(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold().strip()


def _pair(value: object) -> tuple[str, str]:
    raw = str(value or "").upper().replace("-", "/").strip()
    if "/" not in raw:
        return "", ""
    base, quote = raw.split("/", 1)
    return base.strip(), quote.strip()


def _direction(balance: float, deadband: float = 12.0) -> str:
    x = _finite(balance)
    if x >= deadband:
        return "COMPRA"
    if x <= -deadband:
        return "VENDA"
    return "NEUTRO"


def _component(raw: Any) -> dict[str, Any]:
    """Normalize an upstream component without inventing missing evidence."""
    if isinstance(raw, Mapping):
        if raw.get("available") is False or raw.get("fresh") is False or raw.get("stale") is True:
            return {"available": False, "score": 50.0, "quality": 0.0, "source": ""}
        value = raw.get("score", raw.get("value"))
        try:
            score = float(value)
        except Exception:
            return {"available": False, "score": 50.0, "quality": 0.0, "source": ""}
        if not math.isfinite(score):
            return {"available": False, "score": 50.0, "quality": 0.0, "source": ""}
        quality = max(0.0, min(100.0, _finite(raw.get("quality", 70.0), 70.0)))
        if quality <= 0:
            return {"available": False, "score": 50.0, "quality": 0.0, "source": ""}
        return {
            "available": True,
            "score": max(0.0, min(100.0, score)),
            "quality": quality,
            "source": str(raw.get("source") or ""),
        }
    try:
        score = float(raw)
    except Exception:
        return {"available": False, "score": 50.0, "quality": 0.0, "source": ""}
    if not math.isfinite(score):
        return {"available": False, "score": 50.0, "quality": 0.0, "source": ""}
    return {"available": True, "score": max(0.0, min(100.0, score)), "quality": 60.0, "source": ""}


def _tone_vote(tone: object, strength: Any = None) -> tuple[float, float]:
    """Return currency-support vote [-100,+100] and quality [0,100]."""
    text = _norm(tone)
    positive = (
        "hawk", "restritiv", "tighten", "alta de juros", "higher for longer",
        "menos cortes", "less easing",
    )
    negative = (
        "dov", "flexiv", "expansiv", "cut", "corte de juros",
        "mais cortes", "easing",
    )
    pos = any(x in text for x in positive)
    neg = any(x in text for x in negative)
    if pos == neg:
        return 0.0, 0.0
    raw_strength = _finite(strength, 0.55)
    if abs(raw_strength) <= 1.5:
        magnitude = max(0.20, min(1.0, abs(raw_strength)))
    else:
        magnitude = max(0.20, min(1.0, abs(raw_strength) / 100.0))
    return (100.0 if pos else -100.0) * magnitude, 70.0 + 20.0 * magnitude


def _indicator_vote(item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Normalize one explicit macro expectation/surprise item.

    Direction is only calculated when higher_supports_currency is explicitly
    supplied. This avoids pretending that every higher print is mechanically
    bullish for every currency/regime.
    """
    if item.get("fresh") is False or item.get("stale") is True:
        return None
    if "higher_supports_currency" not in item:
        return None
    higher_supports = bool(item.get("higher_supports_currency"))
    actual = item.get("actual")
    consensus = item.get("consensus", item.get("forecast"))
    previous = item.get("previous")
    scale = max(1e-9, abs(_finite(item.get("scale", 1.0), 1.0)))
    quality = max(0.0, min(100.0, _finite(item.get("quality", 70.0), 70.0)))
    if quality <= 0:
        return None

    kind = ""
    delta = None
    if actual is not None and consensus is not None:
        try:
            delta = float(actual) - float(consensus)
            kind = "surpresa"
        except Exception:
            delta = None
    elif consensus is not None and previous is not None:
        try:
            delta = float(consensus) - float(previous)
            kind = "expectativa"
        except Exception:
            delta = None
    if delta is None or not math.isfinite(delta):
        return None

    signed = delta if higher_supports else -delta
    vote = _clip((signed / scale) * 45.0)
    return {
        "currency": str(item.get("currency") or "").upper().strip(),
        "name": str(item.get("name", item.get("event", "Indicador")) or "Indicador"),
        "category": str(item.get("category") or "expectations"),
        "kind": kind,
        "vote": vote,
        "quality": quality,
        "delta": delta,
        "source": str(item.get("source") or ""),
    }


def _currency_rows(context: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    c = dict(context or {})
    raw = c.get("currencies", c.get("currency_macro", {}))
    return dict(raw or {}) if isinstance(raw, Mapping) else {}


def build_structured_macro(
    pair: object,
    context: Mapping[str, Any] | None,
    *,
    legacy_balance: float = 0.0,
    legacy_quality: float = 0.0,
) -> dict[str, Any]:
    base, quote = _pair(pair)
    c = dict(context or {})
    if not base or not quote:
        return {
            "schema": SCHEMA, "available": False, "direction": "INDISPONÍVEL",
            "balance": 0.0, "quality": 0.0, "coverage": 0.0, "mode": "invalid_pair",
            "groups": [], "reasons": [], "risks": ["Par inválido ou ausente."],
            "probability": False, "decision_effect": False, "changes_gate": False,
            "changes_score_mestre": False, "real_orders_enabled": False,
        }

    currencies = _currency_rows(c)
    base_row = dict(currencies.get(base, {}) or {})
    quote_row = dict(currencies.get(quote, {}) or {})
    groups: list[dict[str, Any]] = []
    reasons: list[str] = []
    risks: list[str] = []

    for group in CORE_GROUPS:
        b = _component(base_row.get(group))
        q = _component(quote_row.get(group))
        if not (b["available"] and q["available"]):
            continue
        diff = _clip((b["score"] - q["score"]) * 2.0)
        quality = min(b["quality"], q["quality"])
        groups.append({
            "group": group, "balance": diff, "quality": quality,
            "weight": GROUP_WEIGHTS[group], "base_score": round(b["score"], 1),
            "quote_score": round(q["score"], 1),
        })
        reasons.append(
            f"{group}: {base} {b['score']:.0f} × {quote} {q['score']:.0f} · saldo {diff:+.0f}."
        )

    event_votes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_indicators = c.get("indicators", c.get("events_data", []))
    if isinstance(raw_indicators, Sequence) and not isinstance(raw_indicators, (str, bytes)):
        for raw in raw_indicators:
            if not isinstance(raw, Mapping):
                continue
            normalized = _indicator_vote(raw)
            if normalized and normalized["currency"] in {base, quote}:
                event_votes[normalized["currency"]].append(normalized)
    if event_votes:
        def _event_side(ccy: str) -> tuple[float, float, int]:
            rows = event_votes.get(ccy, [])
            if not rows:
                return 0.0, 0.0, 0
            denom = sum(0.30 + 0.70 * r["quality"] / 100.0 for r in rows)
            score = sum(r["vote"] * (0.30 + 0.70 * r["quality"] / 100.0) for r in rows)
            avgq = sum(r["quality"] for r in rows) / len(rows)
            return (score / denom if denom else 0.0), avgq, len(rows)
        bv, bq, bn = _event_side(base)
        qv, qq, qn = _event_side(quote)
        if bn or qn:
            if bn and qn:
                ev_quality = min(bq, qq)
            else:
                ev_quality = (bq if bn else qq) * 0.72
                risks.append("Expectativas/surpresas disponíveis para apenas um lado do par.")
            ev_balance = _clip(bv - qv)
            groups.append({
                "group": "expectations", "balance": ev_balance,
                "quality": ev_quality, "weight": GROUP_WEIGHTS["expectations"],
                "base_items": bn, "quote_items": qn,
            })
            reasons.append(
                f"expectativas/surpresas: {base} {bv:+.0f} × {quote} {qv:+.0f} · saldo {ev_balance:+.0f}."
            )
            named = (event_votes.get(base, []) + event_votes.get(quote, []))[:4]
            for row in named:
                reasons.append(
                    f"{row['name']} ({row['currency']}): {row['kind']} {row['vote']:+.0f}."
                )

    banks = dict(c.get("central_banks", {}) or {}) if isinstance(c.get("central_banks", {}), Mapping) else {}
    if "USD" in {base, quote} and "USD" not in banks:
        fed = dict(c.get("fed", {}) or {})
        if fed:
            banks["USD"] = {"tone": fed.get("tom", fed.get("tone")), "strength": fed.get("forca", fed.get("strength"))}

    bank_votes = {}
    for ccy in (base, quote):
        raw = banks.get(ccy)
        if isinstance(raw, Mapping):
            vote, q = _tone_vote(raw.get("tone", raw.get("tom", raw.get("bias"))), raw.get("strength", raw.get("forca")))
            if q > 0:
                bank_votes[ccy] = (vote, q, str(raw.get("bank") or raw.get("name") or ccy))
    if bank_votes:
        bv, bq = bank_votes.get(base, (0.0, 0.0, base)), bank_votes.get(quote, (0.0, 0.0, quote))
        quality = min(bv[1], bq[1]) if base in bank_votes and quote in bank_votes else max(bv[1], bq[1]) * 0.72
        balance = _clip(bv[0] - bq[0])
        groups.append({
            "group": "central_bank", "balance": balance, "quality": quality,
            "weight": GROUP_WEIGHTS["central_bank"],
        })
        reasons.append(f"bancos centrais: {base} {bv[0]:+.0f} × {quote} {bq[0]:+.0f} · saldo {balance:+.0f}.")
        if len(bank_votes) == 1:
            risks.append("Comunicação de banco central disponível para apenas um lado do par.")

    upcoming = c.get("event", c.get("next_event"))
    if isinstance(upcoming, Mapping) and upcoming.get("disponivel", upcoming.get("available", False)):
        name = str(upcoming.get("evento", upcoming.get("event", "Evento macro")) or "Evento macro")
        impact = str(upcoming.get("impacto", upcoming.get("impact", "")) or "")
        risks.append(f"Próximo evento: {name}{' · '+impact if impact else ''}.")

    by_group={str(x.get("group")):float(x.get("balance",0)) for x in groups}
    strong_pos=[g for g,v in by_group.items() if v>=25]
    strong_neg=[g for g,v in by_group.items() if v<=-25]
    macro_conflict=bool(strong_pos and strong_neg)
    if macro_conflict:
        risks.append(
            "Divergência interna no macro: grupos relevantes apontam direções opostas "
            f"({', '.join(strong_pos[:3])} × {', '.join(strong_neg[:3])})."
        )
    if "rates" in by_group:
        real_side=by_group["rates"]
        growth_values=[by_group[g] for g in ("growth","activity","labour") if g in by_group]
        if growth_values:
            growth_side=sum(growth_values)/len(growth_values)
            if real_side*growth_side<0 and abs(real_side)>=25 and abs(growth_side)>=20:
                risks.append("Juros/política e crescimento-emprego divergem; cenário macro está em transição ou conflito.")

    nominal_coverage = sum(float(x["weight"]) for x in groups)
    total_weight = sum(GROUP_WEIGHTS.values())
    coverage = 100.0 * nominal_coverage / total_weight if total_weight else 0.0

    if groups and coverage >= 32.0:
        denom = 0.0
        weighted = 0.0
        for row in groups:
            effective = float(row["weight"]) * (0.25 + 0.75 * float(row["quality"]) / 100.0)
            weighted += float(row["balance"]) * effective
            denom += effective
        balance = _clip(weighted / denom if denom else 0.0)
        quality = (
            sum(float(x["quality"]) * float(x["weight"]) for x in groups)
            / max(1e-9, sum(float(x["weight"]) for x in groups))
        )
        if macro_conflict:
            quality *= 0.85
        mode = "structured"
        available = True
    elif abs(_finite(legacy_balance)) > 0.01 or _finite(legacy_quality) > 0:
        balance = _clip(legacy_balance)
        quality = max(0.0, min(100.0, _finite(legacy_quality)))
        coverage = max(coverage, min(30.0, quality * 0.30))
        mode = "legacy_fallback"
        available = True
        risks.append("Cobertura estruturada insuficiente; usando força macro relativa já calculada como fallback.")
    else:
        balance = 0.0
        quality = 0.0
        mode = "insufficient"
        available = False
        risks.append("Cobertura macro insuficiente para formar leitura estruturada.")

    return {
        "schema": SCHEMA,
        "pair": f"{base}/{quote}",
        "available": available,
        "direction": _direction(balance) if available else "INDISPONÍVEL",
        "balance": round(balance, 1),
        "quality": round(max(0.0, min(100.0, quality)), 1),
        "coverage": round(max(0.0, min(100.0, coverage)), 1),
        "mode": mode,
        "macro_conflict": bool(macro_conflict),
        "groups": groups,
        "reasons": reasons[:12],
        "risks": risks[:8],
        "probability": False,
        "decision_effect": False,
        "changes_gate": False,
        "changes_score_mestre": False,
        "changes_weights": False,
        "real_orders_enabled": False,
        "automatic_execution": False,
    }




_EVENT_RULES = (
    (("core pce", "pce nucleo"), True, 0.20, "inflation"),
    (("pce",), True, 0.20, "inflation"),
    (("core cpi", "ipc nucleo"), True, 0.20, "inflation"),
    (("cpi", "ipc anual", "inflation rate"), True, 0.20, "inflation"),
    (("nonfarm payroll", "payroll", "nfp"), True, 50.0, "labour"),
    (("unemployment", "desemprego"), False, 0.10, "labour"),
    (("ism manufacturing", "ism industrial", "manufacturing pmi"), True, 1.0, "activity"),
    (("ism services", "ism servicos", "services pmi"), True, 1.0, "activity"),
    (("gdp", "pib"), True, 0.50, "growth"),
)


def economic_rows_to_indicators(
    rows: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
    *,
    currency: str = "USD",
    quality: float = 82.0,
) -> list[dict[str, Any]]:
    """Adapt a current economic-event snapshot to explicit surprise inputs.

    Only an allow-list of well-known releases receives a directional rule.
    Unknown releases are skipped instead of being guessed.
    """
    normalized_rows: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(rows, Mapping):
        for name, payload in rows.items():
            if isinstance(payload, Mapping):
                normalized_rows.append((str(name), payload))
    elif isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
        for payload in rows:
            if isinstance(payload, Mapping):
                normalized_rows.append((str(payload.get("name", payload.get("event", "")) or ""), payload))

    out: list[dict[str, Any]] = []
    for fallback_name, payload in normalized_rows:
        name = str(payload.get("nome", payload.get("evento", payload.get("name", fallback_name))) or fallback_name)
        n = _norm(name)
        rule = next((r for r in _EVENT_RULES if any(alias in n for alias in r[0])), None)
        if rule is None:
            continue
        _, higher_supports, scale, category = rule
        consensus = payload.get("consenso", payload.get("consensus", payload.get("forecast")))
        previous = payload.get("anterior", payload.get("previous"))
        actual = payload.get("real", payload.get("actual"))
        if actual is None and consensus is None:
            continue
        out.append({
            "currency": str(payload.get("currency") or currency).upper().strip(),
            "name": name,
            "category": category,
            "actual": actual,
            "consensus": consensus,
            "previous": previous,
            "higher_supports_currency": higher_supports,
            "scale": scale,
            "quality": max(0.0, min(100.0, _finite(payload.get("quality", quality), quality))),
            "fresh": bool(payload.get("fresh", True)),
            "source": str(payload.get("source") or payload.get("fonte") or "economic snapshot"),
        })
    return out


def ranking_rows_to_currency_context(
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    usd_quality: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Adapt AtlasQuant ranking rows into the structured macro contract.

    Current AtlasQuant has real labour/activity sub-scores only for USD.
    Non-USD placeholder 50s are intentionally not promoted to evidence.
    """
    out: dict[str, dict[str, Any]] = {}
    for raw in list(rows or []):
        if not isinstance(raw, Mapping):
            continue
        code = str(raw.get("Código", raw.get("currency", raw.get("symbol", ""))) or "").upper().strip()
        if len(code) != 3:
            continue
        source = str(raw.get("fonte", raw.get("Fonte", "")) or "")
        source_norm = _norm(source)
        fallback = any(x in source_norm for x in ("fallback", "seguranca", "safety"))
        quality = 35.0 if fallback else 85.0
        if code == "USD" and usd_quality is not None:
            quality = max(0.0, min(100.0, _finite(usd_quality, quality)))

        row: dict[str, Any] = {}
        for group, key in (("rates", "n_juros"), ("inflation", "n_inflacao"), ("growth", "n_pib")):
            value = raw.get(key)
            try:
                score = float(value)
            except Exception:
                continue
            if math.isfinite(score):
                row[group] = {
                    "score": max(0.0, min(100.0, score)),
                    "quality": quality,
                    "fresh": not fallback,
                    "source": source,
                }

        if code == "USD":
            for group, key in (("labour", "n_emprego"), ("activity", "n_atividade")):
                value = raw.get(key)
                try:
                    score = float(value)
                except Exception:
                    continue
                if math.isfinite(score):
                    row[group] = {
                        "score": max(0.0, min(100.0, score)),
                        "quality": quality,
                        "fresh": not fallback,
                        "source": source,
                    }
        if row:
            out[code] = row
    return out


__all__ = ["SCHEMA", "GROUP_WEIGHTS", "CORE_GROUPS", "build_structured_macro", "ranking_rows_to_currency_context", "economic_rows_to_indicators"]