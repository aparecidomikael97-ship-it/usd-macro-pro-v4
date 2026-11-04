"""Matriz de viés por horizonte: avaliação local, apenas dados com carimbo válido.

NÃO consulta dados, NÃO executa ordens e NÃO estima chance de acerto.
A origem e autenticidade de cada observação dependem do validador anterior.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_BIAS_MATRIX_V1"
TIMEFRAMES = ("W1", "D1", "H4", "M15")
MAX_AGE = {
    "W1": timedelta(days=9),
    "D1": timedelta(hours=72),
    "H4": timedelta(hours=10),
    "M15": timedelta(minutes=60),
}
VALID_SIDES = frozenset({"ALTA", "BAIXA", "NEUTRO"})


def _stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def _observation(value: Any, *, timeframe: str, now: datetime) -> str | None:
    if not isinstance(value, Mapping):
        return None
    side = value.get("bias")
    if not isinstance(side, str) or side not in VALID_SIDES:
        return None
    observed = _stamp(value.get("as_of"))
    if observed is None or observed > now or now - observed > MAX_AGE[timeframe]:
        return None
    return side


def _evaluate(sides: Mapping[str, str | None]) -> tuple[str, str]:
    """Return *a filter status*, never a trade signal or probability."""
    if any(sides.get(tf) is None for tf in TIMEFRAMES):
        return "SEM_DADOS", "AGUARDAR"
    weekly, daily, h4, m15 = (sides[tf] for tf in TIMEFRAMES)
    if weekly == "NEUTRO" or daily == "NEUTRO":
        return "SEM_DIREÇÃO", "AGUARDAR"
    if weekly != daily:
        return "CONFLITO_W1_D1", "AGUARDAR"
    if h4 != daily:
        return "H4_CONTRÁRIO", "AGUARDAR"
    if m15 != daily:
        return "M15_SEM_CONFIRMAÇÃO", "AGUARDAR"
    return "ALINHADO", daily


def read_bias_matrix(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Normalize a trusted-upstream contract to all 28 G8 Forex pairs.

    Requires timestamped values per timeframe; missing/stale/contrary data wait.
    A validated flag alone is NOT evidence of authenticity or good performance.
    """
    current = (now or datetime.now(timezone.utc))
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must include timezone")
    current = current.astimezone(timezone.utc)
    default_sides = {tf: None for tf in TIMEFRAMES}
    empty_rows = {
        pair: {"timeframes": dict(default_sides), "status": "SEM_DADOS", "bias": "AGUARDAR"}
        for pair in OFFICIAL_PAIRS
    }
    out: dict[str, Any] = {
        "state": "NO_DATA", "source": "", "as_of": "",
        "rows": empty_rows, "validated_pairs": 0, "aligned_pairs": 0,
        "total_pairs": len(OFFICIAL_PAIRS),
    }
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return out
    if payload.get("state") != "VALIDATED_BIAS_EVIDENCE":
        return out
    source = payload.get("source")
    generated = _stamp(payload.get("as_of"))
    if not isinstance(source, str) or not source.strip() or generated is None:
        return out
    if generated > current or current - generated > timedelta(hours=1):
        return out
    raw_pairs = payload.get("pairs")
    if not isinstance(raw_pairs, Mapping):
        return out
    count, aligned = 0, 0
    for pair in OFFICIAL_PAIRS:
        item = raw_pairs.get(pair)
        if not isinstance(item, Mapping):
            continue
        sides = {
            tf: _observation(item.get(tf), timeframe=tf, now=current)
            for tf in TIMEFRAMES
        }
        status, bias = _evaluate(sides)
        if all(sides.values()):
            count += 1
        if status == "ALINHADO":
            aligned += 1
        out["rows"][pair] = {"timeframes": sides, "status": status, "bias": bias}
    out.update({
        "state": "READY" if count == len(OFFICIAL_PAIRS) else "PARTIAL" if count else "NO_DATA",
        "source": source.strip()[:150], "as_of": generated.isoformat(),
        "validated_pairs": count, "aligned_pairs": aligned,
    })
    return out


__all__ = ["SCHEMA", "TIMEFRAMES", "MAX_AGE", "read_bias_matrix"]
