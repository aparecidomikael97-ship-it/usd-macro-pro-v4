"""Safe traceability map for AION local Tool Hub evidence.

This module never executes a tool, reads a connector, inspects raw result
payloads, mutates checkpoint state, calls a provider, publishes, deploys or
trades. It maps already-produced local execution envelopes to deterministic,
sanitized evidence references.

Trace IDs are derived only from execution metadata. Raw tool result content is
excluded from both the ID seed and traceability output.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from atlasquant_aion_observability import redact_text
from atlasquant_aion_tool_hub import default_tool_hub

SCHEMA = "ATLASQUANT_AION_LOCAL_TRACEABILITY_V1"
MAX_RECORDS = 8
MAX_BLOCKERS = 6
MAX_CONFLICTS = 8

SOURCE_CATALOG = {
    "aion.memory.search": {
        "source_key": "canonical_memory",
        "source_label": "Memória canônica",
        "source_path": "atlasquant_aion_memory.search_canonical_memory",
        "derived": False,
    },
    "aion.memory.recall": {
        "source_key": "layered_memory",
        "source_label": "Memória em camadas",
        "source_path": "atlasquant_aion_memory_layers.recall",
        "derived": False,
    },
    "aion.checkpoint.inspect": {
        "source_key": "checkpoint_master",
        "source_label": "Checkpoint Mestre",
        "source_path": "checkpoint.local_metadata",
        "derived": False,
    },
    "aion.status.read": {
        "source_key": "master_status_board",
        "source_label": "Painel Mestre local",
        "source_path": "atlasquant_aion_status_board.build_master_status_board",
        "derived": True,
    },
    "aion.tasks.summary": {
        "source_key": "operating_tasks",
        "source_label": "Fila local de tarefas",
        "source_path": "checkpoint.operating.tasks",
        "derived": False,
    },
    "aion.missions.summary": {
        "source_key": "continuity_missions",
        "source_label": "Missões de continuidade",
        "source_path": "checkpoint.continuity.missions",
        "derived": False,
    },
    "aion.durable.summary": {
        "source_key": "durable_tasks",
        "source_label": "Tarefas duráveis",
        "source_path": "checkpoint.durable_tasks.records",
        "derived": False,
    },
    "aion.approvals.summary": {
        "source_key": "approval_inbox",
        "source_label": "Caixa local de aprovações",
        "source_path": "atlasquant_aion_approval_inbox.collect_approval_inbox",
        "derived": True,
    },
    "aion.events.summary": {
        "source_key": "operating_events",
        "source_label": "Eventos operacionais locais",
        "source_path": "checkpoint.operating.events",
        "derived": False,
    },
    "aion.specialists.snapshot": {
        "source_key": "specialist_snapshot",
        "source_label": "Snapshot local do especialista",
        "source_path": "atlasquant_aion_specialist_session.read_loaded_specialist_snapshot",
        "derived": True,
    },
    "aion.secretary.draft_brief": {
        "source_key": "secretary_draft",
        "source_label": "Briefing local da Secretaria",
        "source_path": "atlasquant_aion_secretary.executive_briefing",
        "derived": True,
    },
}

CONTRACT_FINGERPRINT_SCHEMA = "ATLASQUANT_AION_LOCAL_CONTRACT_FINGERPRINT_V1"
WRITE_TOOL_ID = "aion.checkpoint.prepare_save"


def local_contract_fingerprint(
    hub: Mapping[str, Any] | None = None,
    *,
    source_catalog: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    """Return a deterministic fingerprint of the local authority/provenance contract."""
    catalog = dict(source_catalog or SOURCE_CATALOG)
    hub_map = dict(hub) if isinstance(hub, Mapping) else default_tool_hub()
    rows = []
    for item in list(hub_map.get("tools") or []):
        if not isinstance(item, Mapping):
            continue
        tool_id = str(item.get("tool_id") or "")
        if tool_id not in catalog and tool_id != WRITE_TOOL_ID:
            continue
        rows.append({
            "tool_id": tool_id,
            "workspace_id": str(item.get("workspace_id") or ""),
            "kind": str(item.get("kind") or ""),
            "guardian_action": str(item.get("guardian_action") or ""),
            "state": str(item.get("state") or ""),
            "connector_id": str(item.get("connector_id") or ""),
            "required_scopes": sorted(str(x) for x in list(item.get("required_scopes") or [])),
            "external_side_effects": bool(item.get("external_side_effects", False)),
        })
    rows.sort(key=lambda item: item["tool_id"])

    sources = []
    for tool_id in sorted(catalog):
        source = catalog.get(tool_id)
        if not isinstance(source, Mapping):
            source = {}
        sources.append({
            "tool_id": str(tool_id),
            "source_key": str(source.get("source_key") or ""),
            "source_path": str(source.get("source_path") or ""),
            "derived": bool(source.get("derived", False)),
        })

    payload = {
        "schema": CONTRACT_FINGERPRINT_SCHEMA,
        "write_tool_id": WRITE_TOOL_ID,
        "tools": rows,
        "sources": sources,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "AION-LCL-" + sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _clean(value: Any, limit: int = 160) -> str:
    return " ".join(redact_text(value).split())[:limit]


def _valid_contract_fingerprint(value: Any) -> bool:
    text = str(value or "")
    if not text.startswith("AION-LCL-") or len(text) != 25:
        return False
    suffix = text[9:]
    return len(suffix) == 16 and all(ch in "0123456789ABCDEF" for ch in suffix)


def _trace_id(envelope: Mapping[str, Any], index: int) -> str:
    seed = "|".join((
        _clean(envelope.get("tool_id"), 96),
        _clean(envelope.get("request_id"), 80),
        _clean(envelope.get("workspace_id"), 64),
        _clean(envelope.get("kind"), 30),
        str(index),
    ))
    return "LCL-EV-" + sha256(seed.encode("utf-8")).hexdigest()[:12].upper()


def _safe_security(envelope: Mapping[str, Any]) -> tuple[bool, list[str]]:
    security = _mapping(envelope.get("security"))
    issues = []
    for key in (
        "network_called",
        "connector_called",
        "external_side_effects",
        "permissions_expanded",
        "secrets_included",
    ):
        if security.get(key) is not False:
            issues.append(key.upper() + "_NOT_FALSE")
    for key in (
        "executes_action",
        "external_action_executed",
        "real_orders_enabled",
        "tool_output_is_authority",
    ):
        if envelope.get(key) is not False:
            issues.append(key.upper() + "_NOT_FALSE")
    provenance = _mapping(envelope.get("provenance"))
    if provenance.get("local_only") is not True:
        issues.append("LOCAL_ONLY_NOT_TRUE")
    if not _valid_contract_fingerprint(envelope.get("contract_fingerprint")):
        issues.append("CONTRACT_FINGERPRINT_INVALID")
    return not issues, issues


def _synthesis_by_tool(synthesis: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for item in list(synthesis.get("items") or [])[:MAX_RECORDS]:
        if not isinstance(item, Mapping):
            continue
        tool_id = _clean(item.get("tool_id"), 96)
        if tool_id and tool_id not in out:
            out[tool_id] = dict(item)
    return out


def build_local_traceability(
    tool_results: Sequence[Mapping[str, Any]] | None,
    *,
    synthesis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build sanitized provenance references from local execution metadata only."""
    rows = [
        dict(item)
        for item in list(tool_results or [])[:MAX_RECORDS]
        if isinstance(item, Mapping)
    ]
    syn = _mapping(synthesis)
    syn_by_tool = _synthesis_by_tool(syn)
    syn_conflicts = [
        _clean(item, 180)
        for item in list(syn.get("conflicts") or [])[:MAX_CONFLICTS]
        if _clean(item, 180)
    ]

    records = []
    confirmed_content_refs = []
    unknown_refs = []
    conflict_refs = []
    execution_refs = []
    security_issues = []
    fingerprints: list[str] = []

    for index, envelope in enumerate(rows, start=1):
        tool_id = _clean(envelope.get("tool_id") or f"tool_{index}", 96)
        trace_id = _trace_id(envelope, index)
        contract_fingerprint = _clean(envelope.get("contract_fingerprint"), 40)
        if contract_fingerprint:
            fingerprints.append(contract_fingerprint)
        source = dict(SOURCE_CATALOG.get(tool_id) or {
            "source_key": "unknown_local_source",
            "source_label": "Origem local não catalogada",
            "source_path": "unknown",
            "derived": True,
        })
        syn_item = syn_by_tool.get(tool_id, {})
        truth = _mapping(envelope.get("truth"))
        preflight = _mapping(envelope.get("preflight"))
        provenance = _mapping(envelope.get("provenance"))
        safe, issues = _safe_security(envelope)

        truth_status = _clean(
            syn_item.get("truth_status") or truth.get("status") or "UNKNOWN", 40
        ).upper()
        freshness = _clean(
            syn_item.get("freshness") or truth.get("freshness") or "UNVERIFIED", 40
        ).upper()
        state = _clean(envelope.get("state") or "UNKNOWN", 40).upper()
        execution_confirmed = bool(
            syn_item.get("execution_confirmed", state == "SUCCESS" and safe)
        )
        content_confirmed = bool(syn_item.get("content_confirmed", False))
        blockers = [
            _clean(item, 100)
            for item in list(preflight.get("blockers") or [])[:MAX_BLOCKERS]
            if _clean(item, 100)
        ]
        item_conflicts = [
            conflict for conflict in syn_conflicts
            if tool_id and conflict.startswith(tool_id + ":")
        ]

        record = {
            "trace_id": trace_id,
            "contract_fingerprint": contract_fingerprint,
            "tool_id": tool_id,
            "workspace_id": _clean(envelope.get("workspace_id"), 64),
            "kind": _clean(envelope.get("kind"), 30).upper(),
            "source_key": source["source_key"],
            "source_label": source["source_label"],
            "source_path": source["source_path"],
            "derived": bool(source["derived"]),
            "execution_state": state,
            "preflight_state": _clean(preflight.get("state") or "UNKNOWN", 40).upper(),
            "truth_status": truth_status,
            "freshness": freshness,
            "execution_confirmed": execution_confirmed,
            "content_confirmed": content_confirmed,
            "blockers": blockers,
            "conflicts": item_conflicts[:MAX_CONFLICTS],
            "source_module": _clean(provenance.get("source_module"), 100),
            "source_function": _clean(provenance.get("source_function"), 100),
            "input_scope": _clean(provenance.get("input_scope") or "local", 40),
            "local_only": provenance.get("local_only") is True,
            "security_state": "SAFE_LOCAL" if safe else "BLOCK",
            "security_issues": issues,
            "authority": False,
        }
        records.append(record)

        if execution_confirmed:
            execution_refs.append(trace_id)
        if content_confirmed:
            confirmed_content_refs.append(trace_id)
        else:
            unknown_refs.append(trace_id)
        if item_conflicts:
            conflict_refs.append(trace_id)
        if not safe:
            security_issues.append({"trace_id": trace_id, "issues": issues})

    unique_fingerprints = sorted(set(fingerprints))
    contract_consistent = (
        len(rows) == len(fingerprints)
        and len(unique_fingerprints) <= 1
    )
    if len(unique_fingerprints) > 1:
        security_issues.append({
            "trace_id": "BUNDLE",
            "issues": ["CONTRACT_FINGERPRINT_MISMATCH"],
        })

    if security_issues:
        state = "SECURITY_BLOCK"
    elif conflict_refs:
        state = "CONFLICT"
    elif records and confirmed_content_refs and unknown_refs:
        state = "PARTIAL"
    elif records:
        state = "TRACED"
    else:
        state = "NO_EVIDENCE"

    return {
        "schema": SCHEMA,
        "state": state,
        "records": records,
        "record_count": len(records),
        "execution_refs": execution_refs,
        "confirmed_content_refs": confirmed_content_refs,
        "unknown_refs": unknown_refs,
        "conflict_refs": conflict_refs,
        "source_keys": sorted({str(row["source_key"]) for row in records}),
        "contract_fingerprints": unique_fingerprints,
        "contract_consistent": contract_consistent,
        "contract_mismatch": len(unique_fingerprints) > 1,
        "security": {
            "state": "BLOCK" if security_issues else "SAFE_LOCAL",
            "issues": security_issues,
            "network_called": False if not security_issues else None,
            "connector_called": False if not security_issues else None,
            "external_side_effects": False if not security_issues else None,
        },
        "raw_result_included": False,
        "tool_output_is_authority": False,
        "executes_action": False,
        "external_action_executed": False,
        "real_orders_enabled": False,
        "private_chain_of_thought_exposed": False,
    }


__all__ = [
    "SCHEMA",
    "MAX_RECORDS",
    "SOURCE_CATALOG",
    "CONTRACT_FINGERPRINT_SCHEMA",
    "local_contract_fingerprint",
    "build_local_traceability",
]
