"""Laboratório: timeframe × trading style × setup research matrix.

Reuses the existing timeframe profiles and setup catalog. Every cell starts as
SEM_EVIDENCIA and only changes when a recorded evidence row for that exact
combination is supplied. No backtest is run or simulated here, no metric is
filled in, and nothing touches gates, scores or execution.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from atlasquant_setup_validation import SETUP_CATALOG
from atlasquant_timeframe_profiles import normalize_execution_timeframe, timeframe_profile

SCHEMA = "ATLASQUANT_LAB_MATRIX_V1"

LAB_TIMEFRAMES = ("M15", "M30", "H1", "H4", "D1", "W1")
LAB_TIMEFRAME_LABELS = {"W1": "Semanal"}
TRADING_STYLES = ("DAY_TRADE", "INTRADAY", "SWING", "POSITION")
TRADING_STYLE_LABELS = {
    "DAY_TRADE": "Day trade",
    "INTRADAY": "Intraday",
    "SWING": "Swing",
    "POSITION": "Position",
}
# Families used to group setups in the Laboratório; SMC and ICT are families, not single setups.
SETUP_FAMILIES = ("ICT/SMC", "Sessões", "Volume")

CELL_STATES = ("SEM_EVIDENCIA", "EVIDENCIA_INCOMPLETA", "EVIDENCIA_REGISTRADA", "BLOQUEADO")
_METRICS = ("samples", "expectancy_r", "profit_factor", "max_drawdown_r")


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _setup_ids() -> list[str]:
    return [str(item["id"]) for item in SETUP_CATALOG]


def _cell_key(timeframe: str, setup_id: str) -> tuple[str, str]:
    return (timeframe, setup_id)


def _index_evidence(rows: Iterable[Mapping[str, Any]] | None) -> dict[tuple[str, str], dict[str, Any]]:
    known = set(_setup_ids())
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in list(rows or []):
        if not isinstance(raw, Mapping):
            continue
        setup_id = str(raw.get("setup_id") or "").strip().casefold()
        tf_raw = str(raw.get("timeframe") or "").strip()
        if setup_id not in known or not tf_raw:
            continue
        timeframe = normalize_execution_timeframe(tf_raw, default="M15")
        # Unknown labels fall back to the default; two different defaults expose that.
        if timeframe != normalize_execution_timeframe(tf_raw, default="D1"):
            continue
        key = _cell_key(timeframe, setup_id)
        if key not in found:
            found[key] = dict(raw)
    return found


def _cell(timeframe: str, setup: Mapping[str, Any], evidence: Mapping[str, Any] | None) -> dict[str, Any]:
    profile = timeframe_profile(timeframe)
    base = {
        "timeframe": timeframe,
        "timeframe_label": LAB_TIMEFRAME_LABELS.get(timeframe, timeframe),
        "trading_style": profile["trading_style"],
        "trading_style_label": TRADING_STYLE_LABELS[profile["trading_style"]],
        "setup_id": str(setup["id"]),
        "setup_name": str(setup["name"]),
        "family": str(setup["family"]),
        "metrics": {name: None for name in _METRICS},
        "source": "",
        "real_orders_enabled": False,
    }
    if setup.get("definition_pending"):
        return {**base, "state": "BLOQUEADO", "reason": "Setup sem definição objetiva; nada pode ser atribuído a ele."}
    if not evidence:
        return {**base, "state": "SEM_EVIDENCIA", "reason": "Nenhum backtest registrado para esta combinação."}
    metrics = {name: _finite(evidence.get(name)) for name in _METRICS}
    samples = metrics["samples"]
    if samples is not None and (samples < 0 or not float(samples).is_integer()):
        metrics["samples"] = None
    source = str(evidence.get("source") or "").strip()[:160]
    complete = all(value is not None for value in metrics.values()) and bool(source)
    return {
        **base,
        "metrics": metrics,
        "source": source,
        "state": "EVIDENCIA_REGISTRADA" if complete else "EVIDENCIA_INCOMPLETA",
        "reason": (
            "Métricas registradas com fonte. Isto não é recomendação nem probabilidade de lucro."
            if complete else
            "Registro parcial: métricas ou fonte ausentes ficam vazias, sem estimativa."
        ),
    }


def lab_matrix(evidence_rows: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    index = _index_evidence(evidence_rows)
    cells = [
        _cell(tf, setup, index.get(_cell_key(tf, str(setup["id"]))))
        for tf in LAB_TIMEFRAMES
        for setup in SETUP_CATALOG
    ]
    counts = {state: sum(1 for c in cells if c["state"] == state) for state in CELL_STATES}
    return {
        "schema": SCHEMA,
        "timeframes": list(LAB_TIMEFRAMES),
        "trading_styles": list(TRADING_STYLES),
        "setups": _setup_ids(),
        "cells": cells,
        "counts": counts,
        "fabricated_values": False,
        "runs_backtest": False,
        "real_orders_enabled": False,
    }


def cells_for_style(matrix: Mapping[str, Any], style: str) -> list[dict[str, Any]]:
    key = str(style or "").strip().upper()
    return [dict(c) for c in list(matrix.get("cells") or []) if c.get("trading_style") == key]


__all__ = [
    "CELL_STATES",
    "LAB_TIMEFRAMES",
    "SCHEMA",
    "SETUP_FAMILIES",
    "TRADING_STYLES",
    "cells_for_style",
    "lab_matrix",
]
