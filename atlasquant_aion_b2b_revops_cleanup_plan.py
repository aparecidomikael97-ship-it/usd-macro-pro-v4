"""AION B2B RevOps Cleanup Planner V1.

Pure/offline remediation planner over the RevOps Foundation snapshot.

It converts data-quality signals into deterministic human-review tasks. It never
writes CRM data, merges records, deletes records, sends outreach, changes a stage,
assigns an owner, or mutates production.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

SCHEMA = "ATLASQUANT_AION_B2B_REVOPS_CLEANUP_PLAN_V1"
SOURCE_SCHEMA = "ATLASQUANT_AION_B2B_REVOPS_FOUNDATION_V1"
_ALLOWED_SOURCE_STATES = {"READY", "READY_WITH_REVIEW", "PARTIAL"}


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    data = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(data.get("owner_id"), 120),
        "tenant_id": _text(data.get("tenant_id"), 120),
        "workspace_id": _text(data.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _task_id(kind: str, key: str) -> str:
    return "REVOPS-" + sha256(f"{kind}:{key}".encode("utf-8")).hexdigest()[:20].upper()


def _lead_ids(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for raw in value[:5000]:
        item = _text(raw, 128)
        if item and item not in out:
            out.append(item)
    return out


def _task(
    *,
    kind: str,
    key: str,
    priority: str,
    title: str,
    record_refs: list[str],
    rationale: str,
    required_capability: str,
) -> dict[str, Any]:
    return {
        "task_id": _task_id(kind, key),
        "kind": kind,
        "priority": priority,
        "title": title,
        "record_refs": list(record_refs),
        "rationale": rationale,
        "required_capability": required_capability,
        "human_review_required": True,
        "automatic_execution": False,
        "crm_write": False,
        "outreach": False,
        "destructive_delete": False,
        "automatic_merge": False,
        "executes_action": False,
    }


def build_revops_cleanup_plan(
    snapshot: Mapping[str, Any] | None,
    *,
    trusted_scope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = dict(snapshot) if isinstance(snapshot, Mapping) else {}
    scope = _scope(trusted_scope)
    blockers: list[str] = []

    if not all(scope.values()):
        blockers.append("TRUSTED_SCOPE_INVALID")
    if source.get("schema") != SOURCE_SCHEMA:
        blockers.append("REVOPS_SOURCE_SCHEMA_INVALID")

    source_state = _text(source.get("state"), 40).upper()
    if source_state not in _ALLOWED_SOURCE_STATES:
        blockers.append("REVOPS_SOURCE_STATE_UNSAFE")

    if _scope(source.get("scope") if isinstance(source.get("scope"), Mapping) else {}) != scope:
        blockers.append("REVOPS_SOURCE_SCOPE_MISMATCH")

    for key in (
        "automatic_outreach",
        "automatic_followup",
        "automatic_stage_change",
        "automatic_owner_assignment",
        "automatic_price_commitment",
        "automatic_contract_commitment",
        "crm_write",
        "provider_called",
        "production_mutation",
        "grants_authority",
        "executes_action",
    ):
        if source.get(key) is not False:
            blockers.append(f"REVOPS_SOURCE_{key.upper()}_UNSAFE")

    source_digest = _text(source.get("snapshot_digest"), 180)
    if not source_digest:
        blockers.append("REVOPS_SOURCE_DIGEST_REQUIRED")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "source_state": source_state,
            "scope": scope,
            "blockers": blockers,
            "tasks": [],
            "task_counts": {},
            "human_review_required": True,
            "automatic_cleanup": False,
            "automatic_merge": False,
            "destructive_delete_enabled": False,
            "automatic_outreach": False,
            "crm_write": False,
            "grants_authority": False,
            "executes_action": False,
        }

    tasks: list[dict[str, Any]] = []

    duplicate_candidates = (
        source.get("duplicate_company_candidates")
        if isinstance(source.get("duplicate_company_candidates"), Mapping)
        else {}
    )
    for company_key in sorted(str(key) for key in duplicate_candidates):
        refs = _lead_ids(duplicate_candidates.get(company_key))
        if len(refs) < 2:
            continue
        tasks.append(
            _task(
                kind="REVIEW_COMPANY_DUPLICATE",
                key=company_key,
                priority="HIGH",
                title="Revisar possível duplicidade de empresa",
                record_refs=refs,
                rationale="Mais de um lead usa a mesma chave de empresa; revisão humana antes de qualquer consolidação.",
                required_capability="CRM_EDIT",
            )
        )

    for lead_id in sorted(_lead_ids(source.get("stale_lead_ids"))):
        tasks.append(
            _task(
                kind="REVIEW_STALE_RECORD",
                key=lead_id,
                priority="MEDIUM",
                title="Revalidar registro desatualizado",
                record_refs=[lead_id],
                rationale="O registro excedeu a janela de atualização definida pelo RevOps.",
                required_capability="CRM_EDIT",
            )
        )

    for lead_id in sorted(_lead_ids(source.get("due_next_action_lead_ids"))):
        tasks.append(
            _task(
                kind="REVIEW_DUE_NEXT_ACTION",
                key=lead_id,
                priority="HIGH",
                title="Revisar próxima ação vencida",
                record_refs=[lead_id],
                rationale="A próxima ação está vencida; revisar manualmente antes de qualquer follow-up.",
                required_capability="CRM_EDIT",
            )
        )

    for lead_id in sorted(_lead_ids(source.get("unknown_contact_lead_ids"))):
        tasks.append(
            _task(
                kind="REVIEW_CONTACT_EVIDENCE",
                key=lead_id,
                priority="HIGH",
                title="Validar evidência de contato",
                record_refs=[lead_id],
                rationale="O estado de contato é UNKNOWN; outreach não deve ser inferido.",
                required_capability="CRM_EDIT",
            )
        )

    for lead_id in sorted(_lead_ids(source.get("do_not_contact_lead_ids"))):
        tasks.append(
            _task(
                kind="PRESERVE_DO_NOT_CONTACT",
                key=lead_id,
                priority="HIGH",
                title="Preservar bloqueio de contato",
                record_refs=[lead_id],
                rationale="O registro está marcado DO_NOT_CONTACT e deve permanecer fora de qualquer outreach automático.",
                required_capability="CRM_EDIT",
            )
        )

    rejected_count = len(
        [
            item
            for item in list(source.get("rejected_records") or [])[:5000]
            if isinstance(item, Mapping)
        ]
    )
    if rejected_count:
        tasks.append(
            _task(
                kind="REVIEW_REJECTED_RECORDS",
                key=str(rejected_count),
                priority="HIGH",
                title="Corrigir registros rejeitados",
                record_refs=[],
                rationale=f"{rejected_count} registro(s) falharam no contrato de qualidade e devem ser corrigidos na origem.",
                required_capability="CRM_EDIT",
            )
        )

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    tasks.sort(
        key=lambda item: (
            priority_order.get(item["priority"], 9),
            item["kind"],
            item["task_id"],
        )
    )

    task_counts: dict[str, int] = {}
    for row in tasks:
        task_counts[row["kind"]] = task_counts.get(row["kind"], 0) + 1

    plan_material = {
        "scope": scope,
        "source_digest": source_digest,
        "tasks": [
            {
                "task_id": row["task_id"],
                "kind": row["kind"],
                "priority": row["priority"],
                "record_refs": row["record_refs"],
            }
            for row in tasks
        ],
    }

    return {
        "schema": SCHEMA,
        "state": "READY_FOR_HUMAN_REVIEW",
        "source_state": source_state,
        "scope": scope,
        "source_digest": source_digest,
        "tasks": tasks,
        "task_counts": task_counts,
        "total_tasks": len(tasks),
        "plan_digest": _digest(plan_material),
        "human_review_required": True,
        "automatic_cleanup": False,
        "automatic_merge": False,
        "destructive_delete_enabled": False,
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "crm_write": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = ["SCHEMA", "SOURCE_SCHEMA", "build_revops_cleanup_plan"]
