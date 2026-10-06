"""AION Developer Physical Execution V1 — cryptographic pre-execution gate.

The gate performs structural validation first. Invalid requests do not consume
a physical-attestation nonce. Only after the request is structurally eligible
does it call the canonical Ed25519 physical-evidence verifier.

The module still does not execute commands or write files. A ready result is
pre-execution evidence, never merge/deploy/production authority.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

from atlasquant_aion_nonce_registry import PersistentNonceRegistry
from atlasquant_aion_physical_evidence_attestation_v1 import (
    REQUIRED_PROOFS,
    verify_physical_evidence_attestation,
    physical_evidence_digest,
)
from atlasquant_aion_trust_root import TrustRootRegistry

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PHYSICAL_EXECUTION_V1"
READY = "READY_FOR_PHYSICAL_EXECUTOR"
BLOCKED = "PHYSICAL_EXECUTION_BLOCKED"
FORBIDDEN_ENV_KEYS = frozenset({
    "OPENAI_API_KEY", "GITHUB_TOKEN", "GH_TOKEN", "AWS_SECRET_ACCESS_KEY",
    "AZURE_CLIENT_SECRET", "GOOGLE_APPLICATION_CREDENTIALS",
})
EVIDENCE_FIELDS = frozenset({
    "platform", "handoff_digest", "input_digest", "probe_principal_id",
    "probe_session_id", "proofs",
})
PROOF_FIELDS = frozenset({"verified", "evidence_ref", "evidence_digest", "measured_by"})


def _text(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256_token(value: Any) -> bool:
    text = _text(value, 160)
    if len(text) != 71 or not text.startswith("sha256:"):
        return False
    try:
        int(text[7:], 16)
    except ValueError:
        return False
    return True


def _validate_evidence_shape(evidence: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    blockers: list[str] = []
    unknown = sorted(set(evidence) - EVIDENCE_FIELDS)
    missing = sorted(EVIDENCE_FIELDS - set(evidence))
    if unknown:
        blockers.append("PHYSICAL_EVIDENCE_UNKNOWN_FIELD:" + unknown[0])
    if missing:
        blockers.append("PHYSICAL_EVIDENCE_MISSING_FIELD:" + missing[0])

    raw_proofs = evidence.get("proofs")
    if not isinstance(raw_proofs, Mapping):
        return {}, blockers + ["PHYSICAL_EVIDENCE_PROOFS_NOT_MAPPING"]

    unknown_proofs = sorted(set(raw_proofs) - set(REQUIRED_PROOFS))
    missing_proofs = sorted(set(REQUIRED_PROOFS) - set(raw_proofs))
    if unknown_proofs:
        blockers.append("PHYSICAL_EVIDENCE_UNKNOWN_PROOF:" + unknown_proofs[0])
    if missing_proofs:
        blockers.append("PHYSICAL_EVIDENCE_MISSING_PROOF:" + missing_proofs[0])

    out: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_PROOFS:
        raw = raw_proofs.get(name)
        if not isinstance(raw, Mapping):
            blockers.append(name + "_NOT_MAPPING")
            continue
        unknown_fields = sorted(set(raw) - PROOF_FIELDS)
        missing_fields = sorted(PROOF_FIELDS - set(raw))
        if unknown_fields:
            blockers.append(name + "_UNKNOWN_FIELD:" + unknown_fields[0])
        if missing_fields:
            blockers.append(name + "_MISSING_FIELD:" + missing_fields[0])

        row = {
            "verified": raw.get("verified") is True,
            "evidence_ref": _text(raw.get("evidence_ref"), 500),
            "evidence_digest": _text(raw.get("evidence_digest"), 160),
            "measured_by": _text(raw.get("measured_by"), 160),
        }
        if not row["verified"]:
            blockers.append(name + "_REQUIRED")
        if not _sha256_token(row["evidence_digest"]):
            blockers.append(name + "_DIGEST_REQUIRED")
        if not row["evidence_ref"] or not row["measured_by"]:
            blockers.append(name + "_ATTRIBUTION_REQUIRED")
        out[name] = row

    return out, list(dict.fromkeys(blockers))


def evaluate_physical_executor_readiness(
    *,
    handoff: Mapping[str, Any] | None,
    physical_evidence: Mapping[str, Any] | None,
    attestation_statement: Mapping[str, Any] | None,
    attestation_signature_b64: str,
    trust_roots: TrustRootRegistry,
    nonce_registry: PersistentNonceRegistry,
    now_ts: str,
    environment: Mapping[str, Any] | None,
    allowed_files: Sequence[Any] | None,
    current_input_digest: str,
) -> dict[str, Any]:
    h = dict(handoff) if isinstance(handoff, Mapping) else {}
    evidence = dict(physical_evidence) if isinstance(physical_evidence, Mapping) else {}
    env = dict(environment) if isinstance(environment, Mapping) else {}
    blockers: list[str] = []

    if not isinstance(handoff, Mapping):
        blockers.append("CONTROLLED_HANDOFF_NOT_MAPPING")
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
    if not _sha256_token(expected) or current != expected:
        blockers.append("INPUT_DIGEST_MISMATCH")
    if not _sha256_token(h.get("handoff_digest")):
        blockers.append("HANDOFF_DIGEST_INVALID")

    if not isinstance(physical_evidence, Mapping):
        blockers.append("PHYSICAL_EVIDENCE_NOT_MAPPING")
    proofs, evidence_blockers = (
        _validate_evidence_shape(evidence)
        if evidence
        else ({}, ["PHYSICAL_EVIDENCE_EMPTY"])
    )
    blockers.extend(evidence_blockers)

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

    if not isinstance(environment, Mapping):
        blockers.append("ENVIRONMENT_NOT_MAPPING")
    normalized_env: dict[str, str] = {}
    for raw_key, raw_value in env.items():
        key = _text(raw_key, 120).upper()
        if not key:
            blockers.append("ENVIRONMENT_KEY_INVALID")
            continue
        if key in FORBIDDEN_ENV_KEYS or any(
            token in key for token in ("SECRET", "TOKEN", "PASSWORD", "PRIVATE_KEY")
        ):
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
                not path
                or path.startswith("/")
                or ":" in path
                or path.startswith("../")
                or "/../" in path
                or path.startswith("//")
            ):
                blockers.append("UNSAFE_ALLOWED_FILE")
                continue
            if path not in files:
                files.append(path)

    evidence_digest = ""
    if not blockers:
        try:
            evidence_digest = physical_evidence_digest(evidence)
        except Exception:
            blockers.append("PHYSICAL_EVIDENCE_DIGEST_FAILURE")

    attestation: dict[str, Any]
    if blockers:
        attestation = {
            "state": "BLOCKED",
            "blockers": ["PHYSICAL_ATTESTATION_NOT_CONSUMED_DUE_TO_PREFLIGHT"],
        }
    else:
        attestation = verify_physical_evidence_attestation(
            attestation_statement,
            signature_b64=attestation_signature_b64,
            trust_roots=trust_roots,
            nonce_registry=nonce_registry,
            now_ts=_text(now_ts, 80),
            expected_handoff_digest=_text(h.get("handoff_digest"), 160),
            expected_input_digest=expected,
            expected_physical_evidence_digest=evidence_digest,
        )
        if attestation.get("state") != "VERIFIED" or list(attestation.get("blockers") or []):
            blockers.append("TRUSTED_PHYSICAL_ATTESTATION_NOT_VERIFIED")
        for field in (
            "trust_root_configured",
            "signature_verified",
            "nonce_registered",
            "physical_attestation_verified",
            "trusted_probe_attestation",
        ):
            if attestation.get(field) is not True:
                blockers.append("TRUSTED_PHYSICAL_ATTESTATION_REQUIRED:" + field)
        for field in ("execution_allowed", "executes_action", "private_key_used"):
            if attestation.get(field) is not False:
                blockers.append("TRUSTED_PHYSICAL_ATTESTATION_UNSAFE:" + field)
        if attestation.get("platform") != "WINDOWS":
            blockers.append("PHYSICAL_ATTESTATION_PLATFORM_MISMATCH")
        if attestation.get("probe_principal_id") != evidence.get("probe_principal_id"):
            blockers.append("PHYSICAL_PROBE_PRINCIPAL_MISMATCH")
        if attestation.get("probe_session_id") != evidence.get("probe_session_id"):
            blockers.append("PHYSICAL_PROBE_SESSION_MISMATCH")
        if set(attestation.get("verified_proofs") or []) != set(REQUIRED_PROOFS):
            blockers.append("PHYSICAL_ATTESTATION_PROOF_SET_MISMATCH")

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
        "physical_nonce_registered": attestation.get("nonce_registered") is True,
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
    "SCHEMA",
    "READY",
    "BLOCKED",
    "REQUIRED_PROOFS",
    "FORBIDDEN_ENV_KEYS",
    "evaluate_physical_executor_readiness",
    "expected_executor_receipt_template",
]
