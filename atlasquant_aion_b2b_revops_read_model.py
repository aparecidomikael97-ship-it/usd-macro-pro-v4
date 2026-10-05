"""Read-only aggregate RevOps model for the Negócios admin cockpit.

Consumes a validated AION B2B RevOps Foundation snapshot and projects only
aggregate CRM/funnel metrics. Raw lead/company records, contact references and
record-level evidence are deliberately excluded.

No CRM write, outreach, follow-up, stage change, owner assignment, pricing,
contract commitment or production mutation can occur here.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "ATLASQUANT_AION_B2B_REVOPS_READ_MODEL_V1"
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


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def build_revops_read_model(
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

    digest = _text(source.get("snapshot_digest"), 180)
    if not digest:
        blockers.append("REVOPS_SOURCE_DIGEST_REQUIRED")

    raw_metrics = source.get("metrics") if isinstance(source.get("metrics"), Mapping) else {}
    metric_keys = (
        "accepted_records",
        "rejected_records",
        "company_count",
        "duplicate_company_candidate_count",
        "stale_record_count",
        "due_next_action_count",
        "do_not_contact_count",
        "unknown_contact_count",
        "contact_evidence_coverage_pct",
        "next_action_coverage_pct",
        "owner_coverage_pct",
    )
    metrics = {key: _number(raw_metrics.get(key)) for key in metric_keys}

    raw_stages = source.get("stage_counts") if isinstance(source.get("stage_counts"), Mapping) else {}
    stage_counts: dict[str, int] = {}
    for key, value in raw_stages.items():
        name = _text(key, 40).upper()
        if not name:
            continue
        number = _number(value)
        if isinstance(number, int) and number >= 0:
            stage_counts[name] = number

    review_signals = [
        _text(item, 160)
        for item in list(source.get("warnings") or [])[:30]
        if _text(item, 160)
    ]

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "source_state": source_state,
            "blockers": blockers,
            "read_only": True,
            "raw_records_exposed": False,
            "contact_data_exposed": False,
            "grants_authority": False,
            "executes_action": False,
        }

    return {
        "schema": SCHEMA,
        "state": "PARTIAL" if source_state == "PARTIAL" else "READY",
        "source_state": source_state,
        "scope": scope,
        "metrics": metrics,
        "stage_counts": stage_counts,
        "review_signals": review_signals,
        "evidence_digest": digest,
        "read_only": True,
        "raw_records_exposed": False,
        "contact_data_exposed": False,
        "crm_write": False,
        "automatic_outreach": False,
        "automatic_followup": False,
        "automatic_stage_change": False,
        "automatic_owner_assignment": False,
        "automatic_price_commitment": False,
        "automatic_contract_commitment": False,
        "provider_called": False,
        "production_mutation": False,
        "grants_authority": False,
        "executes_action": False,
    }


__all__ = ["SCHEMA", "SOURCE_SCHEMA", "build_revops_read_model"]
