"""Read-only administrative review for tenant persistence evidence.

Loads the local review artifact explicitly, revalidates its source-bound digests,
and evaluates the persistence gate. It never activates persistence, writes files,
changes ACLs, or grants authority.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import json

from atlasquant_aion_core_intelligence.context import Domain
from atlasquant_aion_core_runtime_bridge import authenticated_context
from atlasquant_aion_tenant_evidence_bundle import verify_local_evidence_bundle
from atlasquant_aion_tenant_persistence_gate import tenant_persistence_readiness

SCHEMA = "ATLASQUANT_AION_TENANT_PERSISTENCE_ADMIN_REVIEW_V1"
DEFAULT_RELATIVE_PATH = Path("docs/aion/evidence/tenant_persistence_local_evidence.json")
MAX_EVIDENCE_BYTES = 2_000_000


def build_tenant_persistence_admin_review(
    access: Mapping[str, Any] | None,
    *,
    repository_root: str | Path,
    evidence_path: str | Path | None = None,
) -> dict[str, Any]:
    try:
        context = authenticated_context(access, Domain.ADMIN)
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": type(exc).__name__,
            "bundle_valid": False,
            "gate_state": "BLOCKED",
            "activation_authorized": False,
            "production_persistence_activated": False,
            "external_action_executed": False,
            "network_called": False,
        }
    if context.role != "ADMIN":
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "ADMIN_CONTEXT_REQUIRED",
            "bundle_valid": False,
            "gate_state": "BLOCKED",
            "activation_authorized": False,
            "production_persistence_activated": False,
            "external_action_executed": False,
            "network_called": False,
        }

    root = Path(repository_root).resolve()
    target = (
        Path(evidence_path).resolve()
        if evidence_path is not None
        else (root / DEFAULT_RELATIVE_PATH).resolve()
    )
    if target != root and root not in target.parents:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "EVIDENCE_PATH_OUTSIDE_REPOSITORY",
            "bundle_valid": False,
            "gate_state": "BLOCKED",
            "activation_authorized": False,
            "production_persistence_activated": False,
            "external_action_executed": False,
            "network_called": False,
        }
    if not target.exists() or not target.is_file():
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "EVIDENCE_BUNDLE_NOT_FOUND",
            "bundle_valid": False,
            "gate_state": "BLOCKED",
            "activation_authorized": False,
            "production_persistence_activated": False,
            "external_action_executed": False,
            "network_called": False,
        }
    try:
        size = target.stat().st_size
    except Exception:
        size = MAX_EVIDENCE_BYTES + 1
    if size <= 0 or size > MAX_EVIDENCE_BYTES:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "EVIDENCE_BUNDLE_SIZE_INVALID",
            "bundle_valid": False,
            "gate_state": "BLOCKED",
            "activation_authorized": False,
            "production_persistence_activated": False,
            "external_action_executed": False,
            "network_called": False,
        }

    try:
        bundle = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": type(exc).__name__,
            "bundle_valid": False,
            "gate_state": "BLOCKED",
            "activation_authorized": False,
            "production_persistence_activated": False,
            "external_action_executed": False,
            "network_called": False,
        }
    if not isinstance(bundle, Mapping):
        return {
            "schema": SCHEMA,
            "state": "BLOCKED",
            "reason": "EVIDENCE_BUNDLE_INVALID",
            "bundle_valid": False,
            "gate_state": "BLOCKED",
            "activation_authorized": False,
            "production_persistence_activated": False,
            "external_action_executed": False,
            "network_called": False,
        }

    verified = verify_local_evidence_bundle(root, bundle)
    records = bundle.get("records") if isinstance(bundle.get("records"), Mapping) else {}
    gate = tenant_persistence_readiness(records if verified.get("valid") else {})
    ready = (
        verified.get("valid") is True
        and gate.get("state") == "READY_FOR_ADMIN_REVIEW"
        and gate.get("code_ready") is True
        and gate.get("evidence_ready") is True
        and gate.get("persistence_activation_authorized") is False
    )
    evidence_rows = []
    for name, row in sorted(records.items()):
        if not isinstance(row, Mapping):
            continue
        evidence_rows.append({
            "kind": str(name),
            "status": str(row.get("status") or "UNKNOWN"),
            "digest": str(row.get("digest") or ""),
            "test_count": int(row.get("test_count") or 0),
        })
    return {
        "schema": SCHEMA,
        "state": "READY_FOR_ADMIN_REVIEW" if ready else "BLOCKED",
        "reason": "EVIDENCE_REVALIDATED" if ready else "EVIDENCE_OR_GATE_NOT_READY",
        "path": str(target),
        "bundle_valid": verified.get("valid") is True,
        "bundle_reasons": list(verified.get("reasons") or []),
        "bundle_digest": str(bundle.get("bundle_digest") or ""),
        "source_head_sha": str(bundle.get("source_head_sha") or ""),
        "generated_at": str(bundle.get("generated_at") or ""),
        "test_count": int(bundle.get("test_count") or 0),
        "evidence_rows": evidence_rows,
        "gate_state": str(gate.get("state") or "BLOCKED"),
        "code_ready": gate.get("code_ready") is True,
        "evidence_ready": gate.get("evidence_ready") is True,
        "activation_authorized": False,
        "production_persistence_activated": False,
        "automatic_activation": False,
        "external_action_executed": False,
        "network_called": False,
        "review_only": True,
    }


__all__ = [
    "SCHEMA",
    "DEFAULT_RELATIVE_PATH",
    "build_tenant_persistence_admin_review",
]
