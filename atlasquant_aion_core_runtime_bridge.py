"""Authenticated read-only bridge from the AtlasQuant runtime into AION Core Intelligence.

This module does not open a checkpoint, call a provider, perform network I/O,
run subprocesses, execute commands, deploy, publish, pay or trade. It binds
already-authenticated host identity and already-present runtime observations to
the opt-in AionCore application service.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping

from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_core_intelligence.evidence import Evidence, Origin, assess, utc
from atlasquant_aion_core_intelligence.router import route
from atlasquant_aion_core_intelligence.service import AionCore, ScopedEvidence
from atlasquant_aion_core_voice_automation import (
    AtlasQuantVoiceAdapter,
    CheckpointAutomationAdapter,
)
from atlasquant_aion_core_master_checkpoint_bootstrap import (
    augment_system_context_with_master_checkpoint,
)


SCHEMA = "ATLASQUANT_AION_CORE_RUNTIME_BRIDGE_V1"
MAX_RUNTIME_EVIDENCE = 200
_ADMIN_PERMISSION = "aion:admin"

SAFETY_GATES = {
    "execution_authorized": False,
    "external_action_executed": False,
    "real_trading_enabled": False,
    "provider_called": False,
    "automatic_merge": False,
    "automatic_deploy": False,
    "commands_executed": False,
    "subprocess_called": False,
    "network_called": False,
    "payment_executed": False,
    "publication_executed": False,
}


def _authenticated_session(access: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(access, Mapping):
        raise ValueError("AUTHENTICATED_SESSION_REQUIRED")
    if access.get("allowed") is not True or str(access.get("mode") or "") != "AUTHENTICATED":
        raise ValueError("AUTHENTICATED_SESSION_REQUIRED")
    session = access.get("session")
    if not isinstance(session, Mapping):
        raise ValueError("AUTHENTICATED_SESSION_REQUIRED")
    role = str(session.get("role") or "").strip().upper()
    access_role = str(access.get("role") or "").strip().upper()
    if not role or role != access_role:
        raise ValueError("AUTHORITY_MISMATCH")
    username = str(session.get("username") or "").strip().lower()
    fingerprint = str(session.get("credential_fingerprint") or "").strip().lower()
    if not username or not fingerprint:
        raise ValueError("AUTHENTICATED_IDENTITY_REQUIRED")
    permissions = session.get("permissions")
    if not isinstance(permissions, (list, tuple, set, frozenset)):
        raise ValueError("AUTHENTICATED_PERMISSIONS_REQUIRED")
    if role == "ADMIN" and _ADMIN_PERMISSION not in {str(x) for x in permissions}:
        raise ValueError("ADMIN_PERMISSION_REQUIRED")
    return session


def authenticated_context(
    access: Mapping[str, Any] | None,
    domain: Domain = Domain.ADMIN,
) -> Context:
    """Create scope only from the host-authenticated session.

    Query parameters, model output, request bodies and arbitrary session-state
    keys are not accepted as identity inputs.
    """
    if not isinstance(domain, Domain):
        raise ValueError("TYPED_DOMAIN_REQUIRED")
    session = _authenticated_session(access)
    role_raw = str(session.get("role") or "").strip().upper()
    role = "ADMIN" if role_raw == "ADMIN" else "USER"
    username = str(session.get("username") or "").strip().lower()
    fingerprint = str(session.get("credential_fingerprint") or "").strip().lower()
    tenant_id = "tenant:" + fingerprint[:48]
    workspace_id = "workspace:" + username
    actor_id = username
    task_id = "runtime:" + fingerprint[:20] + ":" + domain.value.lower()
    return Context(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        actor_id=actor_id,
        task_id=task_id,
        domain=domain,
        role=role,
    )


def _bounded_value(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
    else:
        try:
            text = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            return ""
    return text if 0 < len(text) <= 3500 else ""


def _runtime_rows(system_context: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(system_context, Mapping):
        return []
    rows: list[Mapping[str, Any]] = []
    for key in ("core_evidence", "source_observations"):
        raw = system_context.get(key)
        if isinstance(raw, (list, tuple)):
            rows.extend(x for x in raw if isinstance(x, Mapping))
    return rows[:MAX_RUNTIME_EVIDENCE]


def _origin_for(row: Mapping[str, Any]) -> Origin:
    truth = str(row.get("truth_state") or row.get("kind") or "UNKNOWN").strip().upper()
    if truth == "CONFIRMED":
        return Origin.SYSTEM_OBSERVED
    if truth == "INFERENCE":
        return Origin.INFERRED
    return Origin.UNKNOWN


def _evidence_from_row(row: Mapping[str, Any]) -> Evidence | None:
    claim = str(row.get("claim") or row.get("id") or "").strip()
    value = _bounded_value(row.get("value"))
    source = str(row.get("source") or "").strip()
    source_ref = str(
        row.get("source_ref")
        or row.get("reference")
        or row.get("url")
        or ""
    ).strip()
    if not claim or not value:
        return None

    time_sensitive_raw = row.get("time_sensitive", True)
    time_sensitive = time_sensitive_raw if type(time_sensitive_raw) is bool else True
    observed_at = row.get("observed_at") or row.get("timestamp")
    observed_at = str(observed_at).strip() if observed_at not in (None, "") else None
    ttl_raw = row.get("ttl_seconds")
    ttl_seconds = ttl_raw if type(ttl_raw) is int and ttl_raw > 0 else None

    origin = _origin_for(row)
    if origin == Origin.SYSTEM_OBSERVED:
        if not source or not source_ref:
            origin = Origin.UNKNOWN
        elif time_sensitive and (observed_at is None or ttl_seconds is None):
            origin = Origin.UNKNOWN

    try:
        return Evidence(
            claim=claim,
            value=value,
            origin=origin,
            source=source or "UNKNOWN",
            source_ref=source_ref or "UNKNOWN",
            observed_at=observed_at,
            ttl_seconds=ttl_seconds,
            time_sensitive=time_sensitive,
            uncertainty=(
                "Bound from authenticated AtlasQuant runtime context; "
                "external source identity is not independently re-authenticated here."
            ),
        )
    except Exception:
        return None


def scoped_runtime_evidence(
    context: Context,
    system_context: Mapping[str, Any] | None,
) -> tuple[ScopedEvidence, dict[str, int]]:
    rows = _runtime_rows(system_context)
    records = tuple(
        item
        for item in (_evidence_from_row(row) for row in rows)
        if isinstance(item, Evidence)
    )
    return (
        ScopedEvidence(context=context, records=records),
        {
            "input_rows": len(rows),
            "accepted_records": len(records),
            "rejected_records": max(0, len(rows) - len(records)),
        },
    )


def _context_for_intent(
    access: Mapping[str, Any],
    intent: str,
    core: AionCore,
    *,
    capability: str | None = None,
) -> tuple[Context, dict[str, Any]]:
    admin_context = authenticated_context(access, Domain.ADMIN)
    selection = route(
        intent,
        admin_context,
        core.registry,
        capability=capability,
    )
    domain = Domain.ADMIN
    if selection.required_context:
        try:
            domain = Domain(selection.required_context)
        except Exception:
            domain = Domain.ADMIN
    context = authenticated_context(access, domain)
    return context, {
        "status": selection.status,
        "capability": selection.capability,
        "reason": selection.reason,
        "required_context": selection.required_context,
        "candidates": list(selection.candidates),
    }


def persistence_contract(connected: bool = False) -> dict[str, Any]:
    if connected:
        return {
            "state": "STAGED_CHECKPOINT",
            "reason": "CHECKPOINT_MASTER_REQUIRES_EXPLICIT_SAVE",
            "storage": "CHECKPOINT_MASTER_STAGED",
            "automatic_directory_creation": False,
            "automatic_database_creation": False,
            "memory_auto_write": False,
            "remote_persistence": "REQUIRES_EXPLICIT_CHECKPOINT_SAVE",
            "backup_restore": "INHERITS_CHECKPOINT_MASTER_HISTORY",
        }
    return {
        "state": "UNAVAILABLE",
        "reason": "PERSISTENCE_NOT_CONNECTED_IN_RUNTIME_BRIDGE_V1",
        "storage": "NONE",
        "automatic_directory_creation": False,
        "automatic_database_creation": False,
        "memory_auto_write": False,
        "remote_persistence": "UNAVAILABLE",
        "backup_restore": "UNAVAILABLE",
    }


def handle_runtime_intent(
    access: Mapping[str, Any] | None,
    intent: str,
    *,
    system_context: Mapping[str, Any] | None = None,
    legacy_checkpoint: Mapping[str, Any] | None = None,
    voice_status: Mapping[str, Any] | None = None,
    capability: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run the data-only Core against the current authenticated runtime context."""
    current = utc(now or datetime.now(timezone.utc))
    try:
        session = _authenticated_session(access)
        if str(session.get("role") or "").strip().upper() != "ADMIN":
            raise ValueError("ADMIN_REQUIRED")
    except ValueError as exc:
        return {
            "schema": SCHEMA,
            "status": "DENIED",
            "reason": str(exc),
            "route": {},
            "payload": None,
            "truth_state": "UNKNOWN",
            "evidence": {"status": "UNKNOWN", "records": []},
            "evidence_ingress": {"input_rows": 0, "accepted_records": 0, "rejected_records": 0},
            "persistence": persistence_contract(False),
            "master_checkpoint": {
                "state": "NOT_EVALUATED",
                "evidence_ready": False,
                "runtime_authorized": False,
                "merge_authorized": False,
                "deploy_authorized": False,
            },
            **SAFETY_GATES,
        }

    admin_context = authenticated_context(access, Domain.ADMIN)
    voice_adapter = AtlasQuantVoiceAdapter(voice_status)
    automation_adapter = (
        CheckpointAutomationAdapter(admin_context, legacy_checkpoint)
        if isinstance(legacy_checkpoint, Mapping)
        else None
    )
    bootstrap_core = AionCore(
        store=None,
        voice_adapter=voice_adapter,
        automation_adapter=automation_adapter,
        clock=lambda: current,
    )
    context, preliminary = _context_for_intent(
        access,
        intent,
        bootstrap_core,
        capability=capability,
    )
    store = None
    checkpoint_state = {"state": "UNAVAILABLE"}
    if isinstance(legacy_checkpoint, Mapping):
        from atlasquant_aion_core_checkpoint_bridge import load_checkpoint_store
        store, checkpoint_state = load_checkpoint_store(context, legacy_checkpoint)
    core = AionCore(
        store=store,
        voice_adapter=voice_adapter,
        automation_adapter=(
            automation_adapter if context.domain == Domain.ADMIN else None
        ),
        clock=lambda: current,
    )
    enriched_system_context, master_checkpoint_snapshot = (
        augment_system_context_with_master_checkpoint(system_context)
    )
    scoped, ingress = scoped_runtime_evidence(context, enriched_system_context)
    evidence_truth = assess(scoped.records, current)
    try:
        result = core.handle(
            intent,
            context,
            evidence=scoped,
            capability=capability,
        )
    finally:
        if store is not None:
            store.close()

    route_result = result.get("route") if isinstance(result.get("route"), Mapping) else preliminary
    payload = result.get("payload")
    return {
        "schema": SCHEMA,
        "status": str(result.get("status") or "UNKNOWN"),
        "reason": str(result.get("reason") or route_result.get("reason") or ""),
        "route": dict(route_result),
        "context": {
            "domain": context.domain.value,
            "role": context.role,
            "scope_bound": True,
        },
        "payload": payload,
        "truth_state": str(evidence_truth.get("status") or "UNKNOWN"),
        "evidence": evidence_truth,
        "evidence_ingress": ingress,
        "persistence": {
            **persistence_contract(isinstance(legacy_checkpoint, Mapping)),
            "checkpoint_state": str(checkpoint_state.get("state") or "UNKNOWN"),
        },
        "master_checkpoint": {
            "state": str(master_checkpoint_snapshot.get("state") or "UNKNOWN"),
            "reason": str(master_checkpoint_snapshot.get("reason") or ""),
            "latest_date": str(master_checkpoint_snapshot.get("latest_date") or ""),
            "snapshot_digest": str(master_checkpoint_snapshot.get("snapshot_digest") or ""),
            "decision_count": len(master_checkpoint_snapshot.get("decisions") or []),
            "pending_count": len(master_checkpoint_snapshot.get("pending") or []),
            "evidence_ready": master_checkpoint_snapshot.get("evidence_ready") is True,
            "runtime_authorized": False,
            "merge_authorized": False,
            "deploy_authorized": False,
        },
        "capabilities": core.registry.snapshot(),
        "adapters": {
            "voice": voice_adapter.snapshot(),
            "automation": (
                automation_adapter.snapshot(current)
                if automation_adapter is not None
                else {
                    "status": "UNAVAILABLE",
                    "execution_adapter": "UNAVAILABLE",
                    "automatic_execution": False,
                }
            ),
        },
        "memory_auto_written": False,
        **SAFETY_GATES,
    }


__all__ = [
    "SCHEMA",
    "SAFETY_GATES",
    "authenticated_context",
    "scoped_runtime_evidence",
    "persistence_contract",
    "handle_runtime_intent",
]
