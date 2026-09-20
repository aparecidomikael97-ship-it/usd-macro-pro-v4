"""AtlasQuant research consensus for the four market layers.

This module is intentionally advisory/observational. It never changes the
operational Gate, Score Mestre, weights, broker state, or execution.
"""
from __future__ import annotations
from typing import Any, Mapping
import math

SCHEMA = "ATLASQUANT_LAYER_CONSENSUS_V1"
MIN_LAYERS = 2
MIN_EVIDENCE_FLOOR = 35.0
DIRECTION_THRESHOLD = 15.0
CONFLICT_SPREAD = 90.0


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def build_layer_consensus(result: Mapping[str, Any] | None) -> dict[str, Any]:
    r = dict(result or {})
    layers = [dict(x) for x in list(r.get("layers", []) or []) if isinstance(x, Mapping)]
    available = [x for x in layers if bool(x.get("available"))]
    blockers: list[str] = []

    if len(available) < MIN_LAYERS:
        blockers.append("EVIDÊNCIA INSUFICIENTE: menos de duas camadas independentes disponíveis.")

    floor = min((_finite(x.get("quality", 0)) for x in available), default=0.0)
    if available and floor < MIN_EVIDENCE_FLOOR:
        blockers.append(f"QUALIDADE BAIXA: piso de evidência {floor:.0f}/100.")

    balances = [_finite(x.get("balance", 0)) for x in available]
    spread = (max(balances) - min(balances)) if balances else 0.0
    strong_pos = any(x >= 35 for x in balances)
    strong_neg = any(x <= -35 for x in balances)
    if strong_pos and strong_neg and spread >= CONFLICT_SPREAD:
        blockers.append("CONFLITO FORTE: camadas independentes apontam direções opostas.")

    for layer in available:
        layer_name = str(layer.get("label") or layer.get("id") or "Camada")
        for item in list(layer.get("research_blockers", []) or []):
            msg = str(item).strip()
            if msg:
                blockers.append(f"{layer_name}: {msg}")
    blockers = list(dict.fromkeys(blockers))

    balance = _finite(r.get("research_balance", 0))
    direction = "COMPRA" if balance >= DIRECTION_THRESHOLD else "VENDA" if balance <= -DIRECTION_THRESHOLD else "NEUTRO"
    if blockers:
        state = "NÃO OPERAR"
    elif direction == "NEUTRO":
        state = "AGUARDAR"
    else:
        state = direction

    aligned = 0
    if direction == "COMPRA":
        aligned = sum(1 for x in balances if x >= 12)
    elif direction == "VENDA":
        aligned = sum(1 for x in balances if x <= -12)
    agreement = (aligned / len(available) * 100.0) if available and direction != "NEUTRO" else 0.0

    return {
        "schema": SCHEMA,
        "research_state": state,
        "research_direction": direction,
        "research_balance": round(balance, 1),
        "available_layers": len(available),
        "evidence_floor": round(floor, 1),
        "agreement_pct": round(agreement, 1),
        "conflict_spread": round(spread, 1),
        "blockers": blockers,
        "advisory_only": True,
        "changes_score_mestre": False,
        "changes_gate": False,
        "changes_weights": False,
        "real_orders_enabled": False,
        "automatic_execution": False,
    }


__all__ = ["SCHEMA", "build_layer_consensus"]