"""Evidence-preserving synthesis for AION local Tool Hub results.

This module combines execution envelopes only. It never executes tools, reads
connectors, mutates checkpoints, calls providers, publishes, deploys, moves
money or enables real trading.

A successful handler execution is not the same as confirmed content. Aggregate
truth is promoted to CONFIRMED only when every successful tool explicitly
declares CONFIRMED content with acceptable freshness and no conflict/security
issue. Tool output remains non-authoritative.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from atlasquant_aion_observability import redact_text

SCHEMA = "ATLASQUANT_AION_LOCAL_SYNTHESIS_V1"
TRUTH_STATES = frozenset({"CONFIRMED", "INFERENCE", "HYPOTHESIS", "UNKNOWN"})
FRESH_ENOUGH = frozenset({"FRESH", "NOT_APPLICABLE"})
MAX_RESULTS = 8
MAX_ISSUES = 16


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 220) -> str:
    return " ".join(redact_text(value).split())[:limit]


def _truth(value: Any) -> str:
    item = _clean(value, 40).upper()
    return item if item in TRUTH_STATES else "UNKNOWN"


def _freshness(value: Any) -> str:
    item = _clean(value, 40).upper()
    return item if item else "UNVERIFIED"


def _security_issues(envelope: Mapping[str, Any]) -> list[str]:
    security = _mapping(envelope.get("security"))
    issues = []
    if security.get("network_called") is not False:
        issues.append("NETWORK_NOT_FALSE")
    if security.get("connector_called") is not False:
        issues.append("CONNECTOR_NOT_FALSE")
    if security.get("external_side_effects") is not False:
        issues.append("EXTERNAL_SIDE_EFFECTS_NOT_FALSE")
    if security.get("permissions_expanded") is not False:
        issues.append("PERMISSIONS_EXPANDED_NOT_FALSE")
    if security.get("secrets_included") is not False:
        issues.append("SECRETS_INCLUDED_NOT_FALSE")
    if envelope.get("external_action_executed") is not False:
        issues.append("EXTERNAL_ACTION_NOT_FALSE")
    if envelope.get("real_orders_enabled") is not False:
        issues.append("REAL_ORDERS_NOT_FALSE")
    if envelope.get("tool_output_is_authority") is not False:
        issues.append("TOOL_OUTPUT_AUTHORITY_NOT_FALSE")
    if envelope.get("executes_action") is not False:
        issues.append("EXECUTES_ACTION_NOT_FALSE")
    provenance = _mapping(envelope.get("provenance"))
    if provenance and provenance.get("local_only") is not True:
        issues.append("LOCAL_ONLY_NOT_TRUE")
    return issues


def _explicit_conflicts(tool_id: str, result: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    count = result.get("conflict_count")
    try:
        if int(count or 0) > 0:
            found.append(f"{tool_id}:CONFLICT_COUNT={int(count)}")
    except (TypeError, ValueError):
        pass
    conflicts = result.get("conflicts")
    if isinstance(conflicts, (list, tuple)) and conflicts:
        found.append(f"{tool_id}:EXPLICIT_CONFLICTS={min(len(conflicts), 99)}")
    integrity = _mapping(result.get("integrity"))
    mismatches = integrity.get("mismatches")
    if isinstance(mismatches, (list, tuple)) and mismatches:
        found.append(f"{tool_id}:INTEGRITY_MISMATCHES={min(len(mismatches), 99)}")
    return found[:MAX_ISSUES]


def synthesize_local_tool_results(
    tool_results: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Synthesize bounded metadata without treating tool output as authority."""
    rows = [
        dict(item)
        for item in list(tool_results or [])[:MAX_RESULTS]
        if isinstance(item, Mapping)
    ]
    items = []
    conflicts: list[str] = []
    unknowns: list[dict[str, str]] = []
    security_issues: list[dict[str, Any]] = []
    execution_confirmed: list[str] = []
    content_confirmed: list[str] = []
    truth_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()

    for index, envelope in enumerate(rows):
        tool_id = _clean(envelope.get("tool_id") or f"tool_{index + 1}", 96)
        state = _clean(envelope.get("state") or "UNKNOWN", 40).upper()
        truth_map = _mapping(envelope.get("truth"))
        truth = _truth(truth_map.get("status"))
        freshness = _freshness(truth_map.get("freshness"))
        preflight = _mapping(envelope.get("preflight"))
        blockers = [
            _clean(item, 100)
            for item in list(preflight.get("blockers") or [])[:6]
            if _clean(item, 100)
        ]
        result = _mapping(envelope.get("result"))
        item_security = _security_issues(envelope)
        item_conflicts = _explicit_conflicts(tool_id, result)
        conflicts.extend(item_conflicts)
        state_counts[state] += 1
        truth_counts[truth] += 1

        if item_security:
            security_issues.append({
                "tool_id": tool_id,
                "issues": item_security[:MAX_ISSUES],
            })

        successful = state == "SUCCESS"
        if successful and not item_security:
            execution_confirmed.append(tool_id)

        content_ok = (
            successful
            and not item_security
            and not item_conflicts
            and truth == "CONFIRMED"
            and freshness in FRESH_ENOUGH
        )
        if content_ok:
            content_confirmed.append(tool_id)
        else:
            if not successful:
                reason = "EXECUTION_NOT_SUCCESS"
            elif item_security:
                reason = "SECURITY_INVARIANT_FAILED"
            elif item_conflicts:
                reason = "EXPLICIT_CONFLICT"
            elif truth != "CONFIRMED":
                reason = f"CONTENT_TRUTH_{truth}"
            else:
                reason = f"FRESHNESS_{freshness}"
            unknowns.append({
                "tool_id": tool_id,
                "reason": reason,
            })

        items.append({
            "tool_id": tool_id,
            "kind": _clean(envelope.get("kind"), 30).upper(),
            "state": state,
            "preflight_state": _clean(preflight.get("state") or "UNKNOWN", 40).upper(),
            "blockers": blockers,
            "truth_status": truth,
            "freshness": freshness,
            "execution_confirmed": bool(successful and not item_security),
            "content_confirmed": bool(content_ok),
            "local_only": bool(_mapping(envelope.get("provenance")).get("local_only", False)),
            "tool_output_is_authority": False,
        })

    if security_issues:
        synthesis_state = "SECURITY_BLOCK"
    elif conflicts:
        synthesis_state = "CONFLICT"
    elif any(item["state"] != "SUCCESS" for item in items):
        synthesis_state = "PARTIAL"
    elif items:
        synthesis_state = "SYNTHESIZED"
    else:
        synthesis_state = "NO_RESULTS"

    if (
        items
        and not security_issues
        and not conflicts
        and len(content_confirmed) == len(items)
    ):
        aggregate_truth = "CONFIRMED"
        aggregate_freshness = "FRESH"
    elif any(item["truth_status"] == "INFERENCE" for item in items) and not conflicts:
        aggregate_truth = "INFERENCE"
        aggregate_freshness = "UNVERIFIED"
    elif any(item["truth_status"] == "HYPOTHESIS" for item in items) and not conflicts:
        aggregate_truth = "HYPOTHESIS"
        aggregate_freshness = "UNVERIFIED"
    else:
        aggregate_truth = "UNKNOWN"
        aggregate_freshness = "UNVERIFIED"

    if synthesis_state == "SECURITY_BLOCK":
        next_step = "Revisar o envelope inseguro; não usar o conteúdo nem continuar execução automática."
    elif synthesis_state == "CONFLICT":
        next_step = "Revisar as evidências conflitantes; nenhuma versão deve ser escolhida silenciosamente."
    elif any(item["state"] != "SUCCESS" for item in items):
        next_step = "Resolver o primeiro bloqueio/erro de preflight antes de ampliar a leitura."
    elif unknowns:
        next_step = "Buscar ou fornecer evidência com proveniência e frescor antes de afirmar os pontos UNKNOWN."
    elif items:
        next_step = "Usar a síntese apenas como contexto; qualquer ação continua sujeita a aprovação e Guardian."
    else:
        next_step = "Nenhum resultado local foi fornecido para síntese."

    summary = (
        f"{len(execution_confirmed)}/{len(items)} ferramenta(s) executaram localmente com invariantes seguras; "
        f"{len(content_confirmed)}/{len(items)} conteúdo(s) ficaram CONFIRMED+FRESH; "
        f"{len(conflicts)} conflito(s); {len(unknowns)} ponto(s) não confirmado(s). "
        "Saída de ferramenta não é autoridade e nenhuma ação externa foi autorizada."
    )

    return {
        "schema": SCHEMA,
        "state": synthesis_state,
        "items": items,
        "tool_count": len(items),
        "execution_confirmed_count": len(execution_confirmed),
        "execution_confirmed_tools": execution_confirmed,
        "content_confirmed_count": len(content_confirmed),
        "content_confirmed_tools": content_confirmed,
        "truth_counts": {state: int(truth_counts[state]) for state in sorted(TRUTH_STATES)},
        "state_counts": dict(state_counts),
        "truth": {
            "status": aggregate_truth,
            "freshness": aggregate_freshness,
            "authority": False,
        },
        "conflicts": conflicts[:MAX_ISSUES],
        "unknowns": unknowns[:MAX_ISSUES],
        "security": {
            "state": "BLOCK" if security_issues else "SAFE_LOCAL",
            "issues": security_issues[:MAX_ISSUES],
            "network_called": False if not security_issues else None,
            "connector_called": False if not security_issues else None,
            "external_side_effects": False if not security_issues else None,
            "external_action_executed": False if not security_issues else None,
            "real_orders_enabled": False if not security_issues else None,
        },
        "summary": summary,
        "next_step": next_step,
        "tool_output_is_authority": False,
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "private_chain_of_thought_exposed": False,
    }


__all__ = [
    "SCHEMA",
    "TRUTH_STATES",
    "FRESH_ENOUGH",
    "MAX_RESULTS",
    "synthesize_local_tool_results",
]
