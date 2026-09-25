"""Operational intelligence layer for AtlasQuant/AION.

This module implements four read-only capabilities:
- Commander briefing: organizes the current mission, blockers and next action.
- Evidence Auditor: classifies and reconciles supplied evidence.
- Evidence Confidence: measures evidence quality, never probability of profit.
- Macro Scenario Simulator: produces explicit hypotheses, not live forecasts.

It does not call the web, brokers, paid providers, deployment APIs or social
platforms. It does not mutate checkpoints or enable real-money execution.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence
import json
import unicodedata

SCHEMA = "ATLASQUANT_AION_OPERATIONAL_INTELLIGENCE_V1"

TRUTH_KINDS = ("CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN")
CONFIDENCE_LABELS = (
    (85, "MUITO_ALTA"),
    (70, "ALTA"),
    (45, "MODERADA"),
    (1, "BAIXA"),
    (0, "SEM_EVIDENCIA"),
)

_SCENARIO_LIBRARY = {
    "CPI": {
        "ABOVE": {
            "headline": "Inflação acima da referência",
            "channels": [
                ("USD/DXY", "pressão de alta", "expectativa de juros mais restritivos"),
                ("Treasuries", "yields podem subir", "reprecificação de juros"),
                ("Nasdaq/S&P 500", "pressão negativa possível", "taxa de desconto mais alta"),
                ("Ouro", "reação mista", "USD/yields podem pesar, mas hedge pode compensar"),
            ],
            "invalidators": [
                "núcleo ou componentes internos contradizem o headline",
                "mercado já precificou surpresa maior",
                "Fed sinaliza tolerância ao dado isolado",
            ],
        },
        "BELOW": {
            "headline": "Inflação abaixo da referência",
            "channels": [
                ("USD/DXY", "pressão de baixa", "menor necessidade de aperto"),
                ("Treasuries", "yields podem cair", "reprecificação mais dovish"),
                ("Nasdaq/S&P 500", "alívio positivo possível", "taxa de desconto menor"),
                ("Ouro", "apoio possível", "queda de yields/real yields pode ajudar"),
            ],
            "invalidators": [
                "serviços/núcleo seguem resistentes",
                "atividade forte mantém risco inflacionário",
                "Fed mantém comunicação hawkish apesar do dado",
            ],
        },
    },
    "PCE": {
        "ABOVE": {
            "headline": "PCE acima da referência",
            "channels": [
                ("USD/DXY", "pressão de alta", "inflação preferida do Fed mais forte"),
                ("Treasuries", "yields podem subir", "juros esperados mais altos"),
                ("Índices EUA", "pressão negativa possível", "condições financeiras mais apertadas"),
            ],
            "invalidators": [
                "revisões reduzem a surpresa",
                "núcleo desacelera apesar do headline",
                "mercado já incorporou o dado",
            ],
        },
        "BELOW": {
            "headline": "PCE abaixo da referência",
            "channels": [
                ("USD/DXY", "pressão de baixa", "alívio na inflação acompanhada pelo Fed"),
                ("Treasuries", "yields podem cair", "maior espaço para flexibilização"),
                ("Índices EUA", "alívio positivo possível", "condições financeiras menos restritivas"),
            ],
            "invalidators": [
                "consumo/renda continuam pressionando preços",
                "núcleo segue alto",
                "Fed minimiza o dado isolado",
            ],
        },
    },
    "PAYROLL": {
        "ABOVE": {
            "headline": "Emprego acima da referência",
            "channels": [
                ("USD/DXY", "pressão de alta possível", "atividade e juros podem ser reprecificados"),
                ("Treasuries", "yields podem subir", "menor urgência para cortar juros"),
                ("Índices EUA", "reação pode ser mista", "crescimento ajuda, juros mais altos podem pesar"),
            ],
            "invalidators": [
                "desemprego sobe de forma relevante",
                "salários desaceleram fortemente",
                "revisões anteriores anulam a surpresa",
            ],
        },
        "BELOW": {
            "headline": "Emprego abaixo da referência",
            "channels": [
                ("USD/DXY", "pressão de baixa possível", "atividade mais fraca pode antecipar cortes"),
                ("Treasuries", "yields podem cair", "maior probabilidade de flexibilização"),
                ("Índices EUA", "reação pode ser mista", "juros menores ajudam, medo de recessão pode pesar"),
            ],
            "invalidators": [
                "salários aceleram",
                "desemprego cai",
                "revisões anteriores compensam o dado fraco",
            ],
        },
    },
    "FOMC": {
        "ABOVE": {
            "headline": "Surpresa mais hawkish/restritiva",
            "channels": [
                ("USD/DXY", "pressão de alta", "diferencial de juros favorece o dólar"),
                ("Treasuries", "yields podem subir", "curva repricing hawkish"),
                ("Nasdaq/S&P 500", "pressão negativa possível", "condições financeiras mais apertadas"),
                ("Ouro", "pressão negativa possível", "USD e real yields mais altos"),
            ],
            "invalidators": [
                "coletiva suaviza a decisão",
                "dot plot não confirma o tom",
                "mercado interpreta medida como fim do ciclo",
            ],
        },
        "BELOW": {
            "headline": "Surpresa mais dovish/flexível",
            "channels": [
                ("USD/DXY", "pressão de baixa", "diferencial de juros pode diminuir"),
                ("Treasuries", "yields podem cair", "curva repricing dovish"),
                ("Nasdaq/S&P 500", "alívio positivo possível", "condições financeiras menos apertadas"),
                ("Ouro", "apoio possível", "USD/real yields mais baixos"),
            ],
            "invalidators": [
                "coletiva endurece o tom",
                "inflação limita cortes",
                "mercado já precificou flexibilização maior",
            ],
        },
    },
    "GEOPOLITICAL_RISK": {
        "ABOVE": {
            "headline": "Escalada do risco geopolítico",
            "channels": [
                ("Petróleo", "pressão de alta possível", "risco de oferta/rotas"),
                ("Ouro", "demanda defensiva possível", "busca por proteção"),
                ("JPY/CHF", "fluxo defensivo possível", "moedas historicamente usadas em risk-off"),
                ("Índices globais", "pressão negativa possível", "aversão a risco"),
                ("USD", "pode receber fluxo defensivo", "liquidez e busca por segurança"),
            ],
            "invalidators": [
                "evento é rapidamente contido",
                "não há impacto em energia/rotas/fluxos",
                "mercado já precificou a escalada",
            ],
        },
        "BELOW": {
            "headline": "Redução do risco geopolítico",
            "channels": [
                ("Petróleo", "prêmio de risco pode cair", "menor risco de oferta"),
                ("Ouro", "demanda defensiva pode diminuir", "redução de hedge"),
                ("Índices globais", "alívio positivo possível", "retorno do apetite a risco"),
            ],
            "invalidators": [
                "novos focos de tensão surgem",
                "oferta de energia continua afetada",
                "redução de risco é apenas temporária",
            ],
        },
    },
}


def _clean(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).strip().casefold()


def _stable_value(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return repr(value)


def _truth_kind(value: Any) -> str:
    raw = _clean(value, 40).upper()
    return raw if raw in TRUTH_KINDS else "UNKNOWN"


def normalize_evidence(
    evidence: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(list(evidence or [])):
        if not isinstance(item, Mapping):
            continue
        rows.append({
            "claim": _clean(item.get("claim") or item.get("id") or f"claim_{index+1}", 180),
            "kind": _truth_kind(item.get("kind") or item.get("truth_state")),
            "source": _clean(item.get("source") or "unknown", 180),
            "value": item.get("value"),
            "note": _clean(item.get("note"), 500),
        })
    return rows


def evidence_audit(
    evidence: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    rows = normalize_evidence(evidence)
    counts = Counter(row["kind"] for row in rows)
    source_names = {
        _norm(row["source"]) for row in rows
        if _norm(row["source"]) not in {"", "unknown", "desconhecido"}
    }

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_norm(row["claim"])].append(row)

    conflicts: list[dict[str, Any]] = []
    for key, group in grouped.items():
        confirmed = [row for row in group if row["kind"] == "CONFIRMED"]
        values = {_stable_value(row["value"]) for row in confirmed}
        if len(values) > 1:
            conflicts.append({
                "claim": group[0]["claim"] if group else key,
                "confirmed_values": len(values),
                "sources": sorted({row["source"] for row in confirmed}),
            })

    missing_source_count = sum(
        1 for row in rows
        if _norm(row["source"]) in {"", "unknown", "desconhecido"}
    )
    status = "UNKNOWN"
    if conflicts:
        status = "CONFLICT"
    elif rows and counts["UNKNOWN"] == 0:
        status = "AUDITED"
    elif rows:
        status = "PARTIAL"

    return {
        "schema": SCHEMA,
        "status": status,
        "total": len(rows),
        "counts": {kind: int(counts[kind]) for kind in TRUTH_KINDS},
        "independent_sources": len(source_names),
        "missing_source_count": missing_source_count,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "rows": rows,
        "executes_action": False,
        "real_orders_enabled": False,
    }


def evidence_confidence(
    audit_or_evidence: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    audit = (
        dict(audit_or_evidence)
        if isinstance(audit_or_evidence, Mapping)
        else evidence_audit(audit_or_evidence)
    )
    counts = audit.get("counts") if isinstance(audit.get("counts"), Mapping) else {}
    confirmed = int(counts.get("CONFIRMED") or 0)
    inference = int(counts.get("INFERENCE") or 0)
    hypothesis = int(counts.get("HYPOTHESIS") or 0)
    unknown = int(counts.get("UNKNOWN") or 0)
    sources = int(audit.get("independent_sources") or 0)
    conflicts = int(audit.get("conflict_count") or 0)
    missing_sources = int(audit.get("missing_source_count") or 0)

    if int(audit.get("total") or 0) <= 0:
        score = 0
    else:
        score = (
            min(confirmed, 4) * 18
            + min(inference, 2) * 7
            + min(hypothesis, 2) * 2
            + min(sources, 4) * 5
            - min(unknown, 4) * 8
            - min(missing_sources, 4) * 6
        )
        score = max(0, min(100, score))
        if sources <= 1:
            score = min(score, 60)
        if confirmed == 0:
            score = min(score, 45)
        if conflicts:
            score = min(score, 35)

    label = "SEM_EVIDENCIA"
    for threshold, candidate in CONFIDENCE_LABELS:
        if score >= threshold:
            label = candidate
            break

    return {
        "schema": SCHEMA,
        "score": int(score),
        "label": label,
        "basis": "EVIDENCE_QUALITY",
        "is_profit_probability": False,
        "is_market_outcome_probability": False,
        "conflicts_cap_applied": bool(conflicts),
        "single_source_cap_applied": bool(int(audit.get("total") or 0) and sources <= 1),
        "executes_action": False,
        "real_orders_enabled": False,
    }


def commander_briefing(
    *,
    checkpoint: Mapping[str, Any] | None = None,
    system_context: Mapping[str, Any] | None = None,
    executive_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cp = dict(checkpoint or {})
    system = dict(system_context or {})
    executive = dict(executive_snapshot or {})

    continuity = cp.get("continuity") if isinstance(cp.get("continuity"), Mapping) else {}
    missions = [
        dict(item) for item in list((continuity or {}).get("missions", []) or [])
        if isinstance(item, Mapping)
    ]
    active = [
        item for item in missions
        if str(item.get("status") or "").upper() in {"PLANNED", "IN_PROGRESS", "BLOCKED"}
    ]
    current = active[0] if active else {}

    primary = (
        executive.get("primary")
        if isinstance(executive.get("primary"), Mapping)
        else {}
    )
    release_gate = (
        system.get("release_gate")
        if isinstance(system.get("release_gate"), Mapping)
        else {}
    )
    publication = (
        system.get("publication_truth")
        if isinstance(system.get("publication_truth"), Mapping)
        else {}
    )

    evidence = [
        {
            "claim": "runtime_truth",
            "kind": "CONFIRMED" if _clean(system.get("truth_state")).upper() == "CONFIRMED" else "UNKNOWN",
            "source": "system_context",
            "value": _clean(system.get("truth_state") or "UNKNOWN"),
        },
        {
            "claim": "release_gate",
            "kind": "CONFIRMED" if release_gate else "UNKNOWN",
            "source": "release_gate",
            "value": _clean(release_gate.get("state") or "UNKNOWN"),
        },
        {
            "claim": "publication",
            "kind": "CONFIRMED" if publication else "UNKNOWN",
            "source": "publication_truth",
            "value": _clean(publication.get("state") or "UNKNOWN"),
        },
        {
            "claim": "executive_priority",
            "kind": "CONFIRMED" if primary else "UNKNOWN",
            "source": "executive_pulse",
            "value": _clean(primary.get("title") or "UNKNOWN"),
        },
    ]
    audit = evidence_audit(evidence)
    confidence = evidence_confidence(audit)

    release_state = _clean(release_gate.get("state") or "UNKNOWN", 80).upper()
    if release_state == "BLOCKED":
        posture = "BLOCKED"
    elif str(primary.get("priority") or "").upper() in {"P0", "P1"}:
        posture = "ATTENTION"
    elif release_state and release_state != "COMPLETE":
        posture = "VALIDATION"
    else:
        posture = "CONTROLLED"

    objective = _clean(current.get("title") or primary.get("title") or "Nenhuma missão ativa confirmada.")
    next_action = _clean(
        primary.get("next_action")
        or current.get("next_action")
        or release_gate.get("next_action")
        or "Nenhuma próxima ação confirmada."
    )
    blockers: list[str] = []
    if _clean(current.get("blocker")):
        blockers.append(_clean(current.get("blocker")))
    if release_state == "BLOCKED":
        blockers.append(_clean(release_gate.get("next_action") or "Gate de liberação bloqueado."))

    return {
        "schema": SCHEMA,
        "mode": "COMMANDER",
        "posture": posture,
        "objective": objective,
        "next_action": next_action,
        "blockers": blockers,
        "active_missions": len(active),
        "release_gate_state": release_state or "UNKNOWN",
        "publication_state": _clean(publication.get("state") or "UNKNOWN", 80).upper(),
        "executive_priority": _clean(primary.get("priority") or "P3", 20).upper(),
        "executive_area": _clean(primary.get("area") or "🧠 Central", 120),
        "audit": audit,
        "evidence_confidence": confidence,
        "truth_rule": "Somente evidência fornecida é tratada como conhecida; ausência permanece UNKNOWN.",
        "executes_action": False,
        "automatic_repair": False,
        "automatic_deploy": False,
        "real_orders_enabled": False,
    }


def simulate_macro_scenario(
    event_type: Any,
    surprise: Any,
    *,
    evidence: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    event = _clean(event_type, 80).upper().replace("NFP", "PAYROLL")
    direction_raw = _clean(surprise, 80).upper()
    direction = "ABOVE" if direction_raw in {
        "ABOVE", "HIGHER", "HOTTER", "STRONGER", "HAWKISH", "ESCALATION", "ACIMA", "FORTE"
    } else "BELOW" if direction_raw in {
        "BELOW", "LOWER", "COOLER", "WEAKER", "DOVISH", "DEESCALATION", "ABAIXO", "FRACO"
    } else "UNKNOWN"

    library = _SCENARIO_LIBRARY.get(event)
    if not library or direction == "UNKNOWN":
        scenario = {
            "headline": "Cenário não mapeado",
            "channels": [],
            "invalidators": [
                "evento/direção não possui template determinístico no simulador",
            ],
        }
        state = "UNKNOWN"
    else:
        scenario = library[direction]
        state = "HYPOTHESIS"

    audit = evidence_audit(evidence)
    confidence = evidence_confidence(audit)
    rows = [
        {
            "asset": asset,
            "direction": move,
            "mechanism": mechanism,
            "truth_kind": "HYPOTHESIS",
        }
        for asset, move, mechanism in list(scenario.get("channels", []))
    ]

    return {
        "schema": SCHEMA,
        "state": state,
        "event": event or "UNKNOWN",
        "surprise": direction,
        "headline": scenario.get("headline"),
        "channels": rows,
        "invalidators": list(scenario.get("invalidators", [])),
        "evidence_audit": audit,
        "evidence_confidence": confidence,
        "requires_live_confirmation": True,
        "is_live_forecast": False,
        "is_trade_signal": False,
        "is_profit_probability": False,
        "scenario_truth_kind": "HYPOTHESIS" if state == "HYPOTHESIS" else "UNKNOWN",
        "executes_action": False,
        "real_orders_enabled": False,
    }


def scenario_events() -> tuple[str, ...]:
    return tuple(_SCENARIO_LIBRARY.keys())


__all__ = [
    "SCHEMA",
    "TRUTH_KINDS",
    "normalize_evidence",
    "evidence_audit",
    "evidence_confidence",
    "commander_briefing",
    "simulate_macro_scenario",
    "scenario_events",
]
