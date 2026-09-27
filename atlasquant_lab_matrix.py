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
_METRICS = (
    "samples", "win_rate_pct", "expectancy_r", "profit_factor",
    "max_drawdown_r", "net_result",
)

_STRATEGY_TO_SETUP = {
    "BOS_CHOCH_OB": "bos-choch-ob",
    "BOS/CHOCH + ORDER BLOCK": "bos-choch-ob",
    "FVG": "fvg",
    "OTE": "ote",
    "OTE / FIBONACCI": "ote",
    "CRT": "crt",
    "AMD": "amd-po3",
    "AMD_PO3": "amd-po3",
    "BREAKER": "breaker-mitigation",
}


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
        "asset": "",
        "period_start": "",
        "period_end": "",
        "rules_version": "",
        "executed_at": "",
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
        "asset": str(evidence.get("asset") or "").strip()[:32],
        "period_start": str(evidence.get("period_start") or "").strip()[:64],
        "period_end": str(evidence.get("period_end") or "").strip()[:64],
        "rules_version": str(evidence.get("rules_version") or "").strip()[:80],
        "executed_at": str(evidence.get("executed_at") or "").strip()[:64],
        "state": "EVIDENCIA_REGISTRADA" if complete else "EVIDENCIA_INCOMPLETA",
        "reason": (
            "Métricas registradas com fonte. Isto não é recomendação nem probabilidade de lucro."
            if complete else
            "Registro parcial: métricas ou fonte ausentes ficam vazias, sem estimativa."
        ),
    }


def evidence_rows_from_research_records(
    records: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Adapt only explicit persisted/session evidence fields into matrix rows."""
    rows: list[dict[str, Any]] = []
    for raw in list(records or []):
        if not isinstance(raw, Mapping):
            continue
        strategy = str(raw.get("strategy") or "").strip()
        setup_id = _STRATEGY_TO_SETUP.get(strategy.upper(), strategy.casefold())
        if setup_id not in set(_setup_ids()):
            continue
        evidence = raw.get("evidence") if isinstance(raw.get("evidence"), Mapping) else {}
        passport = raw.get("passport") if isinstance(raw.get("passport"), Mapping) else {}
        observed = passport.get("observed_metrics") if isinstance(passport.get("observed_metrics"), Mapping) else {}
        timeframe = str(evidence.get("timeframe") or passport.get("timeframe") or "").strip()
        if not timeframe:
            continue
        rows.append({
            "setup_id": setup_id,
            "timeframe": timeframe,
            "asset": str(raw.get("pair") or ""),
            "samples": evidence.get("trades", evidence.get("executed_trades", observed.get("trades"))),
            "win_rate_pct": evidence.get("win_rate_pct", observed.get("win_rate_pct")),
            "expectancy_r": evidence.get("expectancy_r", observed.get("expectancy_r")),
            "profit_factor": evidence.get("profit_factor", observed.get("profit_factor")),
            "max_drawdown_r": evidence.get("max_drawdown_r", observed.get("max_drawdown_r")),
            "net_result": evidence.get("net_r", observed.get("net_r")),
            "period_start": evidence.get("period_start"),
            "period_end": evidence.get("period_end"),
            "rules_version": evidence.get("rules_version"),
            "executed_at": raw.get("captured_at"),
            "source": str(raw.get("source") or ""),
        })
    return rows


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
    "evidence_rows_from_research_records",
    "lab_matrix",
]
