"""AtlasQuant Model Consensus Engine.

Aggregates independent evidence *groups* instead of raw correlated indicators.
Only one net vote per group is allowed, which reduces simple double counting.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from typing import Iterable
import math


@dataclass(frozen=True)
class Evidence:
    group: str
    direction: int
    weight: float = 1.0
    quality: float = 100.0
    label: str = ""


def aggregate_consensus(evidence: Iterable[Evidence], *, min_active_groups: int = 3,
                        decision_threshold: float = 0.25) -> dict[str, object]:
    buckets: dict[str, list[Evidence]] = defaultdict(list)
    for ev in evidence:
        if ev.direction not in (-1, 0, 1):
            raise ValueError("direction deve ser -1, 0 ou 1")
        if not (math.isfinite(float(ev.weight)) and float(ev.weight) >= 0):
            raise ValueError("weight inválido")
        if not (math.isfinite(float(ev.quality)) and 0 <= float(ev.quality) <= 100):
            raise ValueError("quality inválida")
        buckets[str(ev.group).strip() or "UNGROUPED"].append(ev)

    group_rows = []
    for group, rows in buckets.items():
        denom = sum(float(r.weight) * float(r.quality) / 100.0 for r in rows)
        net = sum(int(r.direction) * float(r.weight) * float(r.quality) / 100.0 for r in rows)
        normalized = 0.0 if denom <= 0 else max(-1.0, min(1.0, net / denom))
        group_rows.append({"group": group, "net": normalized, "raw_items": len(rows)})

    active = [g for g in group_rows if abs(float(g["net"])) > 1e-12]
    if len(active) < int(min_active_groups):
        side = "NEUTRAL"
        normalized_total = 0.0 if not active else sum(float(g["net"]) for g in active) / len(active)
    else:
        normalized_total = sum(float(g["net"]) for g in active) / len(active)
        if normalized_total > float(decision_threshold):
            side = "BUY"
        elif normalized_total < -float(decision_threshold):
            side = "SELL"
        else:
            side = "NEUTRAL"

    aligned = sum(1 for g in active if (normalized_total > 0 and g["net"] > 0) or (normalized_total < 0 and g["net"] < 0))
    agreement = 0.0 if not active or abs(normalized_total) < 1e-12 else aligned / len(active) * 100.0
    return {
        "side": side,
        "consensus_index": round(normalized_total, 4),
        "agreement_pct": round(agreement, 2),
        "active_groups": len(active),
        "groups": sorted(group_rows, key=lambda x: x["group"]),
        "sufficient_independence": len(active) >= int(min_active_groups),
    }
