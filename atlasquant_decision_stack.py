"""AtlasQuant evidence-aware decision stack.

This module combines already-computed evidence for research/explanation only.
It prevents duplicate evidence from being counted multiple times and surfaces
cross-layer conflicts. It never sends orders or converts a score into a profit
probability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Iterable

SCHEMA = "ATLASQUANT_DECISION_STACK_V1"
LAYERS = ("FUNDAMENTAL", "SMC", "ICT", "PRICE_ACTION", "SAFETY")
DIRECTIONS = {"BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"}


@dataclass(frozen=True)
class EvidenceSignal:
    evidence_id: str
    layer: str
    direction: str
    strength: float
    source_family: str
    description: str = ""
    veto: bool = False


def _normal(value: object) -> str:
    return str(value or "").strip().upper()


def _validated(signal: EvidenceSignal) -> EvidenceSignal:
    layer = _normal(signal.layer)
    direction = _normal(signal.direction)
    if layer not in LAYERS:
        raise ValueError("layer inválida")
    if direction not in DIRECTIONS:
        raise ValueError("direction inválida")
    strength = float(signal.strength)
    if not isfinite(strength):
        raise ValueError("strength deve ser finito")
    strength = max(0.0, min(100.0, strength))
    return EvidenceSignal(
        evidence_id=str(signal.evidence_id),
        layer=layer,
        direction=direction,
        strength=strength,
        source_family=str(signal.source_family or signal.evidence_id),
        description=str(signal.description),
        veto=bool(signal.veto),
    )


def deduplicate_evidence(signals: Iterable[EvidenceSignal]) -> dict[str, object]:
    """Keep one strongest signal per source family.

    SMC/ICT/Price Action often describe the same price event with different
    vocabulary. source_family is the explicit deduplication key.
    """
    unique: dict[str, EvidenceSignal] = {}
    duplicates: list[dict[str, object]] = []
    for raw in signals:
        signal = _validated(raw)
        key = _normal(signal.source_family) or _normal(signal.evidence_id)
        existing = unique.get(key)
        if existing is None or signal.strength > existing.strength:
            if existing is not None:
                duplicates.append(
                    {
                        "kept": signal.evidence_id,
                        "suppressed": existing.evidence_id,
                        "source_family": key,
                    }
                )
            unique[key] = signal
        else:
            duplicates.append(
                {
                    "kept": existing.evidence_id,
                    "suppressed": signal.evidence_id,
                    "source_family": key,
                }
            )
    return {
        "signals": list(unique.values()),
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
    }


def evaluate_decision_stack(signals: Iterable[EvidenceSignal]) -> dict[str, object]:
    deduped = deduplicate_evidence(signals)
    rows: list[EvidenceSignal] = list(deduped["signals"])
    vetoes = [x for x in rows if x.veto]
    directional = [x for x in rows if x.direction in {"BULLISH", "BEARISH"}]

    bull = sum(x.strength for x in directional if x.direction == "BULLISH")
    bear = sum(x.strength for x in directional if x.direction == "BEARISH")
    directional_total = bull + bear
    if directional_total <= 0:
        dominant = "UNKNOWN"
        alignment = 0.0
    elif bull > bear:
        dominant = "BULLISH"
        alignment = 100.0 * bull / directional_total
    elif bear > bull:
        dominant = "BEARISH"
        alignment = 100.0 * bear / directional_total
    else:
        dominant = "NEUTRAL"
        alignment = 50.0

    layer_map: dict[str, set[str]] = {layer: set() for layer in LAYERS}
    for row in directional:
        layer_map[row.layer].add(row.direction)
    active_layer_directions = {
        layer: next(iter(values)) if len(values) == 1 else "CONFLICT"
        for layer, values in layer_map.items()
        if values
    }

    cross_directions = {
        value for value in active_layer_directions.values()
        if value in {"BULLISH", "BEARISH"}
    }
    cross_layer_conflict = len(cross_directions) > 1
    within_layer_conflict = any(v == "CONFLICT" for v in active_layer_directions.values())
    conflict = bool(cross_layer_conflict or within_layer_conflict)

    if vetoes:
        state = "BLOCKED_BY_SAFETY"
    elif conflict:
        state = "CONFLICT_REVIEW"
    elif dominant == "UNKNOWN":
        state = "INSUFFICIENT_EVIDENCE"
    elif alignment >= 70:
        state = "ALIGNED_CONTEXT"
    else:
        state = "MIXED_CONTEXT"

    return {
        "schema": SCHEMA,
        "state": state,
        "dominant_direction": dominant,
        "alignment_index": round(alignment, 1),
        "cross_layer_conflict": cross_layer_conflict,
        "within_layer_conflict": within_layer_conflict,
        "layer_directions": active_layer_directions,
        "vetoes": [asdict(x) for x in vetoes],
        "evidence_used": [asdict(x) for x in rows],
        "duplicates_suppressed": deduped["duplicates"],
        "automatic_execution": False,
        "real_orders_enabled": False,
        "interpretation": (
            "O índice mede alinhamento entre evidências deduplicadas; não é probabilidade "
            "de lucro. Conflito ou veto deve permanecer explícito para revisão."
        ),
    }


__all__ = [
    "SCHEMA",
    "LAYERS",
    "DIRECTIONS",
    "EvidenceSignal",
    "deduplicate_evidence",
    "evaluate_decision_stack",
]
