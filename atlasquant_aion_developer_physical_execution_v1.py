"""AION Developer Physical Execution V1 — pre-execution evidence gate.

This module consumes a trusted, already-verified physical attestation and the
raw measurement record. It still does not execute commands or write files.

READY_FOR_PHYSICAL_EXECUTOR means the authority-free pre-execution evidence
contract is satisfied. It is not merge/deploy/production authority and the
actual host adapter must revalidate immediately before use.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_physical_evidence_attestation_v1 import (
    REQUIRED_PROOFS,
    RESULT_SCHEMA as PHYSICAL_VERIFICATION_SCHEMA,
    physical_evidence_digest,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PHYSICAL_EXECUTION_V1"
READY = "READY_FOR_PHYSICAL_EXECUTOR"
BLOCKED = "PHYSICAL_EXECUTION_BLOCKED"
FORBIDDEN_ENV_KEYS = frozenset({
    "OPENAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "AWS_SECRET_ACCESS_KEY",
    "AZURE_CLIENT_SECRET", "GOOGLE_APPLICATION_CREDENTIALS",
})


def _text(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _proofs(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_PROOFS:
        raw = value.get(name)
        if not isinstance(raw, Mapping):
            continue
        out[name] = {
            "verified": raw.get("verified") is True,
            "evidence_ref": _text(raw.get("evidence_ref"), 500),
            "evidence_digest": _text(raw.get("evidence_digest"), 160),
            "measured_by": _text(raw.get("measured_by"), 160),
        }
    return out


def evaluate_physical_executor_readiness(
    *,
    handoff: Mapping[str, Any] | None,
    physical_evidence: Mapping[str, Any] | None,
    trusted_attestation: Mapping[str, Any] | None,
    environment: Mapping[str, Any] | None,
    allowed_files: Sequence[Any] | None,
    current_input_digest: str,
) -> dict[str, Any]:
    h = dict(handoff or {})
    evidence = dict(physical_evidence or {})
    attestation = dict(trusted_attestation or {})
    env = dict(environment or {})
    blockers: list[str] = []

    if h.get("state") != "READY_FOR_CAPABILITY_EXECUTOR":
        blockers.append("CONTROLLED_HANDOFF_NOT_READY")
    if h.get("execution_class") not in {"SANDBOX_CODE", "SANDBOX_TEST"}:
        blockers.append("HANDOFF_EXECUTION_CLASS_NOT_SANDBOX")
    if h.get("automatic_merge") is not False or h.get("automatic_deploy") is not False:
        blockers.append("HANDOFF_RELEASE_BOUNDARY_UNSAFE")
    if h.get("handoff_grants_authority") is not False:
        blockers.append("HANDOFF_AUTHORITY_UNSAFE")
    expected = _text(h.get("expected_input_digest"), 160)
    current = _text(current_input_digest, 160)
    if not expected.startswith("sha256:") or current != expected:
        blockers.append("INPUT_DIGEST_MISMATCH")

    evidence_digest = ""
    try:
        evidence_digest = physical_evidence_digest(evidence)
    except Exception:
        blockers.append("PHYSICAL_EVIDENCE_INVALID")

    if attestation.get("schema") != PHYSICAL_VERIFICATION_SCHEMA:
        blockers.append("TRUSTED_PHYSICAL_ATTESTATION_SCHEMA_MISMATCH")
    for field in (
        "trust_root_configured", "signature_verified", "nonce_registered",
        "physical_attestation_verified", "trusted_probe_attestation",
    ):
        if attestation.get(field) is not True:
            blockers.append("TRUSTED_PHYSICAL_ATTESTATION_REQUIRED:" + field)
    for field in ("execution_allowed", "executes_action", "private_key_used"):
        if attestation.get(field) is not False:
            blockers.append("TRUSTED_PHYSICAL_ATTESTATION_UNSAFE:" + field)
    if attestation.get("state") != "VERIFIED" or list(attestation.get("blockers") or []):
        blockers.append("TRUSTED_PHYSICAL_ATTESTATION_NOT_VERIFIED")
    if attestation.get("platform") != "WINDOWS":
        blockers.append("WINDOWS_PLATFORM_REQUIRED")
    if attestation.get("handoff_digest") != h.get("handoff_digest"):
        blockers.append("PHYSICAL_ATTESTATION_HANDOFF_MISMATCH")
    if attestation.get("input_digest") != expected:
        blockers.append("PHYSICAL_ATTESTATION_INPUT_MISMATCH")
    if attestation.get("physical_evidence_digest") != evidence_digest:
        blockers.append("PHYSICAL_ATTESTATION_EVIDENCE_MISMATCH")
    attested_proofs = attestation.get("verified_proofs")
    if not isinstance(attested_proofs, (list, tuple)) or set(attested_proofs) != set(REQUIRED_PROOFS):
        blockers.append("PHYSICAL_ATTESTATION_PROOF_SET_MISMATCH")

    if _text(evidence.get("platform"), 40).upper() != "WINDOWS":
        blockers.append("PHYSICAL_EVIDENCE_PLATFORM_INVALID")
    if evidence.get("handoff_digest") != h.get("handoff_digest"):
        blockers.append("PHYSICAL_EVIDENCE_HANDOFF_MISMATCH")
    if evidence.get("input_digest") != expected:
        blockers.append("PHYSICAL_EVIDENCE_INPUT_MISMATCH")
    if not _text(evidence.get("probe_principal_id"), 160):
        blockers.append("PHYSICAL_PROBE_PRINCIPAL_REQUIRED")
    if not _text(evidence.get("probe_session_id"), 160):
        blockers.append("PHYSICAL_PROBE_SESSION_REQUIRED")
    if evidence.get("probe_principal_id") != attestation.get("probe_principal_id"):
        blockers.append("PHYSICAL_PROBE_PRINCIPAL_MISMATCH")
    if evidence.get("probe_session_id") != attestation.get("probe_session_id"):
        blockers.append("PHYSICAL_PROBE_SESSION_MISMATCH")

    proofs = _proofs(evidence.get("proofs"))
    for name in REQUIRED_PROOFS:
        row = proofs.get(name) or {}
        if row.get("verified") is not True:
            blockers.append(name + "_REQUIRED")
            continue
        if not str(row.get("evidence_digest") or "").startswith("sha256:"):
            blockers.append(name + "_DIGEST_REQUIRED")
        if not row.get("evidence_ref") or not row.get("measured_by"):
            blockers.append(name + "_ATTRIBUTION_REQUIRED")

    normalized_env: dict[str, str] = {}
    for raw_key, raw_value in env.items():
        key = _text(raw_key, 120).upper()
        if not key:
            blockers.append("ENVIRONMENT_KEY_INVALID")
            continue
        if key in FORBIDDEN_ENV_KEYS or any(token in key for token in ("SECRET", "TOKEN", "PASSWORD", "PRIVATE_KEY")):
            blockers.append("SECRET_ENVIRONMENT_KEY_FORBIDDEN:" + key)
            continue
        normalized_env[key] = _text(raw_value, 500)
    if env.get("PYTHONPATH"):
        blockers.append("PYTHONPATH_OVERRIDE_FORBIDDEN")

    files: list[str] = []
    if not isinstance(allowed_files, (list, tuple)) or not allowed_files:
        blockers.append("ALLOWED_FILES_REQUIRED")
    else:
        for raw in allowed_files[:200]:
            path = _text(raw, 500).replace("\\", "/")
            if (
                not path or path.startswith("/") or ":" in path
                or path.startswith("../") or "/../" in path or path.startswith("//")
            ):
                blockers.append("UNSAFE_ALLOWED_FILE")
                continue
            if path not in files:
                files.append(path)

    blockers = list(dict.fromkeys(blockers))
    material = {
        "schema": SCHEMA,
        "state": READY if not blockers else BLOCKED,
        "blockers": blockers,
        "handoff_digest": h.get("handoff_digest"),
        "input_digest": expected,
        "physical_evidence_digest": evidence_digest,
        "physical_attestation_id": _text(attestation.get("attestation_id"), 160),
        "physical_key_id": _text(attestation.get("key_id"), 160),
        "physical_key_version": attestation.get("key_version"),
        "required_proofs": list(REQUIRED_PROOFS),
        "verified_proofs": list(REQUIRED_PROOFS) if not blockers else [],
        "allowed_files": files,
        "environment_keys": sorted(normalized_env),
        "executor_must_revalidate_immediately_before_use": True,
        "ephemeral_workspace_required": True,
        "protected_core_read_only": True,
        "production_runtime_read_only": True,
        "network_default_deny": True,
        "secrets_mounted": False,
        "patch_applied": False,
        "commands_executed": False,
        "writes_repository": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
        "executes_action": False,
    }
    material["readiness_digest"] = _digest(material)
    return material


def expected_executor_receipt_template(readiness: Mapping[str, Any]) -> dict[str, Any]:
    if readiness.get("schema") != SCHEMA or readiness.get("state") != READY:
        raise ValueError("physical executor readiness is not READY")
    return {
        "schema": "ATLASQUANT_AION_DEVELOPER_PHYSICAL_EXECUTION_RECEIPT_V1",
        "readiness_digest": readiness.get("readiness_digest"),
        "handoff_digest": readiness.get("handoff_digest"),
        "input_digest": readiness.get("input_digest"),
        "state": "OUTCOME_UNKNOWN",
        "attributed": False,
        "changed_files": [],
        "test_receipts": [],
        "output_digest": "",
        "receipt_digest": "",
        "automatic_retry_allowed": False,
        "automatic_commit": False,
        "automatic_merge": False,
        "automatic_deploy": False,
        "production_change_allowed": False,
        "real_trading_enabled": False,
    }


__all__ = [
    "SCHEMA", "READY", "BLOCKED", "REQUIRED_PROOFS", "FORBIDDEN_ENV_KEYS",
    "evaluate_physical_executor_readiness", "expected_executor_receipt_template",
]
