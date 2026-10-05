"""AION post-hardening readiness gate.

Aggregates the current hardening line only after every stage snapshot is
independently verified in the tamper-evident verification ledger. The strongest
result is owner review readiness; this module never authorizes merge, deploy,
freeze, production activation, restore, worker arming or external execution.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import json

from atlasquant_aion_verification_ledger import (
    find_verified_entry,
    verify_ledger_integrity,
)

SCHEMA = "ATLASQUANT_AION_POST_HARDENING_READINESS_V2"

STAGE_RULES = {
    "tenant_crypto": {
        "schema": "ATLASQUANT_AION_TENANT_CRYPTO_ENVELOPE_V1",
        "required": {
            "algorithm": "AES-256-GCM",
            "key_bytes": 32,
            "nonce_bytes": 12,
            "key_material_serialized": False,
            "key_resolver_injected": True,
            "tenant_workspace_bound_aad": True,
            "encryption_required_for_production": True,
            "homegrown_crypto": False,
            "production_kms_connected": False,
            "automatic_key_deletion": False,
            "executes_action": False,
        },
    },
    "durable_cas": {
        "schema": "ATLASQUANT_AION_DURABLE_TASK_REPOSITORY_V1",
        "required": {
            "state": "MATCH",
            "atomic_cas": True,
            "executes_action": False,
            "automatic_resume_executes": False,
        },
    },
    "finops": {
        "schema": "ATLASQUANT_AION_FINOPS_METERING_V1",
        "required": {
            "state": "ALLOW",
            "automatic_charge": False,
            "automatic_model_switch": False,
            "grants_authority": False,
            "executes_action": False,
        },
    },
    "behavioral_eval": {
        "schema": "ATLASQUANT_AION_BEHAVIORAL_EVAL_GATE_V1",
        "required": {
            "state": "HUMAN_REVIEW_CANDIDATE",
            "automatic_promotion": False,
            "production_change_allowed": False,
            "grants_authority": False,
            "executes_action": False,
        },
    },
    "incident_control": {
        "schema": "ATLASQUANT_AION_INCIDENT_CONTROL_AUTHORITY_V1",
        "required": {
            "internal_roles_can_recommend_but_not_mutate": True,
            "reenable_is_stricter_than_stop": True,
            "automatic_control_mutation": False,
            "executes_action": False,
        },
    },
    "operational_resilience": {
        "schema": "ATLASQUANT_AION_OPERATIONAL_RESILIENCE_DR_V1",
        "required": {
            "state": "READY_FOR_ADMIN_REVIEW",
            "release_claim_allowed": False,
            "recovery_authorized": False,
            "automatic_restore": False,
            "automatic_deploy": False,
            "executes_action": False,
        },
    },
}


def _text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.replace("\x00", "").split())[:limit]


def _scope(raw: Mapping[str, Any] | None) -> dict[str, str]:
    item = dict(raw) if isinstance(raw, Mapping) else {}
    return {
        "owner_id": _text(item.get("owner_id") or item.get("actor_id"), 120),
        "tenant_id": _text(item.get("tenant_id"), 120),
        "workspace_id": _text(item.get("workspace_id"), 120),
    }


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def stage_claim_digest(stage: Any, snapshot: Mapping[str, Any] | None) -> str:
    name = _text(stage, 80).lower()
    body = dict(snapshot) if isinstance(snapshot, Mapping) else {}
    return "sha256:" + sha256(
        _canonical({
            "readiness_schema": SCHEMA,
            "stage": name,
            "snapshot": body,
        }).encode("utf-8")
    ).hexdigest()


def _snapshot_rule_check(stage: str, snapshot: Mapping[str, Any]) -> list[str]:
    rule = STAGE_RULES[stage]
    blockers: list[str] = []
    if snapshot.get("schema") != rule["schema"]:
        blockers.append("STAGE_SCHEMA_MISMATCH")
    for key, expected in rule["required"].items():
        observed = snapshot.get(key)
        if type(observed) is not type(expected) or observed != expected:
            blockers.append(f"STAGE_CONTRACT_MISMATCH:{key}")
    return blockers


def evaluate_post_hardening_readiness(
    *,
    trusted_scope: Mapping[str, Any] | None,
    stage_snapshots: Mapping[str, Mapping[str, Any]] | None,
    verification_ledger: Mapping[str, Any] | None,
    verification_entry_ids: Mapping[str, Any] | None,
) -> dict[str, Any]:
    trusted = _scope(trusted_scope)
    blockers: list[str] = []
    if not all(trusted.values()):
        blockers.append("TRUSTED_SCOPE_REQUIRED")

    integrity = verify_ledger_integrity(verification_ledger)
    if integrity.get("state") != "MATCH":
        blockers.append("VERIFICATION_LEDGER_INTEGRITY_MISMATCH")

    if not isinstance(stage_snapshots, Mapping):
        if stage_snapshots is not None:
            blockers.append("STAGE_SNAPSHOTS_MAPPING_REQUIRED")
        snapshots = {}
    else:
        snapshots = dict(stage_snapshots)
    if not isinstance(verification_entry_ids, Mapping):
        if verification_entry_ids is not None:
            blockers.append("VERIFICATION_ENTRY_IDS_MAPPING_REQUIRED")
        entry_ids = {}
    else:
        entry_ids = dict(verification_entry_ids)
    rows: dict[str, dict[str, Any]] = {}

    for stage in STAGE_RULES:
        snapshot_raw = snapshots.get(stage)
        if not isinstance(snapshot_raw, Mapping):
            blockers.append(f"STAGE_MISSING:{stage}")
            rows[stage] = {
                "state": "BLOCKED",
                "blockers": ["STAGE_MISSING"],
                "claim_digest": "",
                "verified": False,
            }
            continue

        snapshot = dict(snapshot_raw)
        stage_blockers = _snapshot_rule_check(stage, snapshot)
        claim_digest = stage_claim_digest(stage, snapshot)
        entry_id = _text(entry_ids.get(stage), 120)
        if not entry_id:
            stage_blockers.append("VERIFICATION_ENTRY_ID_REQUIRED")
            verified = False
            verification_reason = "ENTRY_ID_MISSING"
        elif integrity.get("state") != "MATCH" or not all(trusted.values()):
            verified = False
            verification_reason = "LEDGER_OR_SCOPE_INVALID"
        else:
            found = find_verified_entry(
                verification_ledger,
                entry_id,
                claim_id=f"post-hardening:{stage}",
                claim_digest=claim_digest,
                trusted_context=trusted,
            )
            verified = found.get("state") == "VERIFIED" and found.get("verified") is True
            verification_reason = _text(found.get("reason"), 160) or str(found.get("state") or "UNKNOWN")
            if not verified:
                stage_blockers.append("INDEPENDENT_VERIFICATION_REQUIRED")

        rows[stage] = {
            "state": "VERIFIED" if not stage_blockers and verified else "BLOCKED",
            "blockers": list(dict.fromkeys(stage_blockers)),
            "claim_digest": claim_digest,
            "verification_entry_id": entry_id,
            "verified": verified,
            "verification_reason": verification_reason,
        }
        blockers.extend(f"{stage}:{item}" for item in rows[stage]["blockers"])

    unexpected = sorted(set(snapshots) - set(STAGE_RULES))
    if unexpected:
        blockers.append("UNEXPECTED_STAGE_INPUT")
    unexpected_entry_ids = sorted(set(entry_ids) - set(STAGE_RULES))
    if unexpected_entry_ids:
        blockers.append("UNEXPECTED_VERIFICATION_ENTRY_ID")

    blockers = list(dict.fromkeys(blockers))
    ready = not blockers and all(row.get("state") == "VERIFIED" for row in rows.values())

    material = {
        "scope": trusted,
        "stages": rows,
        "ledger_digest": _text((verification_ledger or {}).get("digest"), 80),
        "ledger_tip": _text((verification_ledger or {}).get("tip_hash"), 80),
    }
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_HUMAN_OWNER_REVIEW" if ready else "BLOCKED",
        "blockers": blockers,
        "scope": trusted,
        "required_stages": list(STAGE_RULES),
        "stages": rows,
        "verification_ledger_integrity": integrity.get("state") or "UNKNOWN",
        "verification_ledger_digest": _text((verification_ledger or {}).get("digest"), 80),
        "readiness_digest": "sha256:" + sha256(_canonical(material).encode("utf-8")).hexdigest(),
        "requires_human_owner_review": ready,
        "production_ready_claim": False,
        "activation_authorized": False,
        "merge_authorized": False,
        "deploy_authorized": False,
        "core_freeze_authorized": False,
        "worker_arming_authorized": False,
        "provider_activation_authorized": False,
        "recovery_authorized": False,
        "real_trading_authorized": False,
        "payment_authorized": False,
        "executes_action": False,
    }


def post_hardening_review_plan(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(snapshot) if isinstance(snapshot, Mapping) else {}
    ready = data.get("state") == "READY_FOR_HUMAN_OWNER_REVIEW"
    return {
        "schema": SCHEMA,
        "state": "REVIEW_PLAN_READY" if ready else "BLOCKED",
        "readiness_digest": _text(data.get("readiness_digest"), 96),
        "steps": [
            "Revalidar o head exato de cada Draft PR e seus checks canônicos.",
            "Comparar os claim digests com entradas VERIFIED do ledger independente.",
            "Confirmar que nenhum blocker operacional ou incidente crítico está aberto.",
            "Separar decisões de merge, deploy, provider, worker, recovery e trading.",
            "Obter decisão explícita do HUMAN_OWNER para qualquer mudança crítica.",
            "Executar a mudança crítica somente no gate específico correspondente.",
        ],
        "review_is_authority": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "automatic_activation": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "STAGE_RULES",
    "stage_claim_digest",
    "evaluate_post_hardening_readiness",
    "post_hardening_review_plan",
]
