"""Fail-closed scheduling contract for the automatic 28-pair FX scanner.

This module does not fetch candles. It gives an external/background worker a
deterministic queue that never depends on a pair selected in the UI. Persisted
results are accepted only for the official G8 universe and remain unavailable
when H4/H1/M15 or provenance is missing.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_SCANNER_QUEUE_V1"
REQUIRED_TIMEFRAMES = ("h4", "h1", "m15")


def _timestamp(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def technical_result_state(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(raw or {})
    technical = row.get("tecnico") if isinstance(row.get("tecnico"), Mapping) else row
    checked = {}
    for timeframe in REQUIRED_TIMEFRAMES:
        block = technical.get(timeframe) if isinstance(technical.get(timeframe), Mapping) else {}
        status = str(block.get("status") or "").strip().upper()
        checked[timeframe] = bool(block) and not any(
            token in status for token in ("INDISPON", "NA FILA", "SEM DADOS", "ERRO")
        )
    updated_at = (
        _timestamp(row.get("processado_em"))
        or _timestamp(technical.get("ultima_atualizacao"))
    )
    source = str(row.get("source") or technical.get("source") or "").strip()
    complete = bool(technical.get("disponivel", False)) and all(checked.values())
    return {
        "complete": complete,
        "timeframes": checked,
        "updated_at": updated_at,
        "source": source,
        "provenance_confirmed": bool(source),
        "eligible_for_score": bool(complete and source),
    }


def scanner_queue(
    persisted_results: Mapping[str, Any] | None,
    *,
    now_ts: float | None = None,
    stale_after_minutes: float = 45.0,
) -> dict[str, Any]:
    """Return all 28 tasks, missing/stale first, with no UI-selected-pair input."""
    now = float(now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp())
    stale_after = max(1.0, float(stale_after_minutes)) * 60.0
    source = dict(persisted_results or {})
    rows = []
    for order, pair in enumerate(OFFICIAL_PAIRS):
        raw = source.get(pair) if isinstance(source.get(pair), Mapping) else {}
        state = technical_result_state(raw)
        age = None if state["updated_at"] is None else max(0.0, (now - state["updated_at"]) / 60.0)
        if not state["complete"]:
            status, priority = "MISSING", 0
        elif not state["provenance_confirmed"]:
            status, priority = "UNVERIFIED", 1
        elif age is None or age * 60.0 > stale_after:
            status, priority = "STALE", 2
        else:
            status, priority = "FRESH", 3
        rows.append({
            "pair": pair,
            "status": status,
            "queue_priority": priority,
            "official_order": order,
            "age_minutes": None if age is None else round(age, 2),
            "eligible_for_score": bool(state["eligible_for_score"] and status == "FRESH"),
            "timeframes": dict(state["timeframes"]),
            "source": state["source"],
            "real_orders_enabled": False,
        })
    queue = sorted(rows, key=lambda item: (item["queue_priority"], item["official_order"]))
    counts = {status: sum(1 for row in rows if row["status"] == status) for status in ("MISSING", "UNVERIFIED", "STALE", "FRESH")}
    return {
        "schema": SCHEMA,
        "population": len(rows),
        "pairs": rows,
        "queue": [row["pair"] for row in queue],
        "next_pair": queue[0]["pair"] if queue else "",
        "counts": counts,
        "selected_pair_required": False,
        "continuous_worker_configured": False,
        "real_orders_enabled": False,
    }


def next_batch(snapshot: Mapping[str, Any], size: int = 2) -> list[str]:
    try:
        limit = max(0, min(28, int(size)))
    except (TypeError, ValueError):
        limit = 0
    queue = [str(pair) for pair in list(snapshot.get("queue") or []) if str(pair) in OFFICIAL_PAIRS]
    return queue[:limit]


__all__ = [
    "REQUIRED_TIMEFRAMES",
    "SCHEMA",
    "next_batch",
    "scanner_queue",
    "technical_result_state",
]
