"""Executive, non-authoritative presentation of AION local synthesis.

This module does not execute tools, inspect connectors, mutate state, call
providers or authorize actions. It only turns a previously-built local
synthesis plus already-sanitized summary lines into a compact executive view.

The "known" section contains execution facts and only content explicitly marked
CONFIRMED+fresh by the synthesis. UNKNOWN content stays in the "unknown" section.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_LOCAL_EXECUTIVE_RESPONSE_V1"
MAX_LINES = 8
MAX_TEXT = 420


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = MAX_TEXT) -> str:
    return " ".join(redact_text(value).split())[:limit]


def _summary_map(
    synthesis: Mapping[str, Any],
    summaries: Sequence[str] | None,
) -> dict[str, str]:
    items = [row for row in list(synthesis.get("items") or []) if isinstance(row, Mapping)]
    clean_summaries = [_clean(item) for item in list(summaries or [])[:MAX_LINES]]
    mapped: dict[str, str] = {}
    for index, item in enumerate(items):
        tool_id = _clean(item.get("tool_id"), 96)
        if not tool_id:
            continue
        mapped[tool_id] = clean_summaries[index] if index < len(clean_summaries) else tool_id
    return mapped


def compose_local_executive_response(
    synthesis: Mapping[str, Any] | None,
    *,
    summaries: Sequence[str] | None = None,
    traceability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a four-part executive response without changing truth state."""
    syn = _mapping(synthesis)
    truth = _mapping(syn.get("truth"))
    security = _mapping(syn.get("security"))
    items = [dict(row) for row in list(syn.get("items") or [])[:MAX_LINES] if isinstance(row, Mapping)]
    by_tool = _summary_map(syn, summaries)
    trace = _mapping(traceability)
    trace_records = [
        dict(row)
        for row in list(trace.get("records") or [])[:MAX_LINES]
        if isinstance(row, Mapping)
    ]
    trace_by_tool = {
        _clean(row.get("tool_id"), 96): row
        for row in trace_records
        if _clean(row.get("tool_id"), 96)
    }

    known: list[str] = []
    unknown: list[str] = []
    conflicts = [_clean(item) for item in list(syn.get("conflicts") or [])[:MAX_LINES] if _clean(item)]

    executed = int(syn.get("execution_confirmed_count") or 0)
    total = int(syn.get("tool_count") or 0)
    if executed:
        known.append(
            f"{executed}/{total} ferramenta(s) local(is) concluíram com invariantes de segurança preservadas."
        )

    for item in items:
        tool_id = _clean(item.get("tool_id"), 96)
        line = by_tool.get(tool_id) or tool_id
        trace_row = trace_by_tool.get(tool_id, {})
        trace_id = _clean(trace_row.get("trace_id"), 40)
        source_label = _clean(trace_row.get("source_label"), 100)
        reference = f" [Fonte {trace_id} · {source_label}]" if trace_id else ""
        if bool(item.get("content_confirmed")):
            known.append(line + reference)
            continue
        reason = "conteúdo não confirmado"
        state = _clean(item.get("state"), 40).upper()
        truth_status = _clean(item.get("truth_status"), 40).upper()
        freshness = _clean(item.get("freshness"), 40).upper()
        blockers = [_clean(x, 100) for x in list(item.get("blockers") or [])[:3] if _clean(x, 100)]
        if state != "SUCCESS":
            reason = f"execução {state or 'UNKNOWN'}"
        elif truth_status != "CONFIRMED":
            reason = f"verdade {truth_status or 'UNKNOWN'}"
        elif freshness not in {"FRESH", "NOT_APPLICABLE"}:
            reason = f"frescor {freshness or 'UNVERIFIED'}"
        if blockers:
            reason += " · " + " · ".join(blockers)
        unknown.append(f"{line} [{reason}]{reference}")

    synthesis_security_state = _clean(security.get("state") or "UNKNOWN", 40).upper()
    trace_security = _mapping(trace.get("security"))
    trace_security_state = _clean(trace_security.get("state") or "UNKNOWN", 40).upper()
    trace_contract_consistent = trace.get("contract_consistent")
    trace_blocked = (
        trace_security_state == "BLOCK"
        or trace_contract_consistent is False
    )
    security_state = "BLOCK" if synthesis_security_state == "BLOCK" or trace_blocked else synthesis_security_state

    if synthesis_security_state == "BLOCK":
        conflicts.insert(0, "Invariante de segurança violada; o conteúdo local não deve ser usado.")
    if trace_blocked:
        conflicts.insert(
            0,
            "Rastreabilidade bloqueada: evidências sem selo válido ou produzidas sob contratos locais diferentes.",
        )

    aggregate_truth = _clean(truth.get("status") or "UNKNOWN", 40).upper()
    aggregate_freshness = _clean(truth.get("freshness") or "UNVERIFIED", 40).upper()
    next_step = _clean(syn.get("next_step") or "Nenhum próximo passo confirmado.", MAX_TEXT)
    if trace_blocked:
        aggregate_truth = "UNKNOWN"
        aggregate_freshness = "UNVERIFIED"
        next_step = "Reexecutar a leitura sob um único contrato local válido antes de usar o conteúdo."

    if security_state == "BLOCK":
        posture = "SECURITY_BLOCK"
        headline = "Leitura local bloqueada por segurança."
    elif conflicts:
        posture = "CONFLICT"
        headline = "Leitura local concluída com conflito que exige revisão."
    elif aggregate_truth == "CONFIRMED":
        posture = "CONFIRMED"
        headline = "Leitura local consolidada com conteúdo confirmado e fresco."
    elif total:
        posture = "PARTIAL"
        headline = "Leitura local concluída, mas parte do conteúdo continua não confirmada."
    else:
        posture = "NO_DATA"
        headline = "Nenhuma leitura local executada para consolidar."

    known = known[:MAX_LINES]
    unknown = unknown[:MAX_LINES]
    conflicts = conflicts[:MAX_LINES]
    if security_state == "BLOCK":
        known = []
        unknown = []

    sections = {
        "known": known,
        "unknown": unknown,
        "conflicts": conflicts,
        "next_step": next_step,
    }
    evidence_refs = {
        "known": [_clean(x, 40) for x in list(trace.get("confirmed_content_refs") or [])[:MAX_LINES] if _clean(x, 40)],
        "unknown": [_clean(x, 40) for x in list(trace.get("unknown_refs") or [])[:MAX_LINES] if _clean(x, 40)],
        "conflicts": [_clean(x, 40) for x in list(trace.get("conflict_refs") or [])[:MAX_LINES] if _clean(x, 40)],
        "execution": [_clean(x, 40) for x in list(trace.get("execution_refs") or [])[:MAX_LINES] if _clean(x, 40)],
    }

    text_parts = [headline]
    text_parts.append("O que sabemos: " + (" | ".join(known) if known else "nenhum conteúdo confirmado."))
    text_parts.append("O que não sabemos: " + (" | ".join(unknown) if unknown else "nenhum ponto pendente identificado."))
    text_parts.append("Conflitos: " + (" | ".join(conflicts) if conflicts else "nenhum conflito explícito."))
    text_parts.append("Próximo passo: " + next_step)

    return {
        "schema": SCHEMA,
        "posture": posture,
        "headline": headline,
        "sections": sections,
        "evidence_refs": evidence_refs,
        "traceability_state": _clean(trace.get("state") or "NO_EVIDENCE", 40).upper(),
        "truth": {
            "status": aggregate_truth,
            "freshness": aggregate_freshness,
            "authority": False,
        },
        "security": {
            "state": security_state,
            "external_action_executed": False,
            "real_orders_enabled": False,
        },
        "plain_text": " ".join(text_parts),
        "safe_to_display": security_state != "BLOCK",
        "tool_output_is_authority": False,
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "private_chain_of_thought_exposed": False,
    }


__all__ = ["SCHEMA", "MAX_LINES", "compose_local_executive_response"]
