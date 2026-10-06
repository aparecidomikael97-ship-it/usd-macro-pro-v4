"""AION Developer Physical Execution V1 — pre-execution evidence gate.

This first operational slice is intentionally fail-closed. It models the exact
evidence required before a physical Windows sandbox executor may be attached.

It does NOT spawn a process, apply a patch, mutate git, write repository files,
use the network, mount secrets, merge, deploy, publish or trade.

Caller-supplied proof flags are never sufficient. A trusted verifier must bind
the exact handoff/input to the exact physical-evidence digest. Until then the
state remains PHYSICAL_EXECUTION_BLOCKED.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping, Sequence
import json

SCHEMA = "ATLASQUANT_AION_DEVELOPER_PHYSICAL_EXECUTION_V1"
READY = "READY_FOR_PHYSICAL_EXECUTOR"
BLOCKED = "PHYSICAL_EXECUTION_BLOCKED"
REQUIRED_PROOFS = (
    "WINDOWS_PLATFORM_VERIFIED",
    "EXECUTABLE_PINNING_VERIFIED",
    "FINAL_PATH_CONTAINMENT_VERIFIED",
    "FILESYSTEM_ISOLATION_VERIFIED",
    "NETWORK_ISOLATION_VERIFIED",
    "CHILD_PROCESS_POLICY_VERIFIED",
    "RESOURCE_LIMITS_VERIFIED",
    "OUTPUT_LIMITS_VERIFIED",
    "DISK_WRITE_LIMIT_VERIFIED",
    "ENVIRONMENT_ISOLATION_VERIFIED",
    "SYMLINK_BOUNDARY_VERIFIED",
    "HARDLINK_BOUNDARY_VERIFIED",
    "TOCTOU_RECHECK_VERIFIED",
    "SANDBOX_IDENTITY_VERIFIED",
)
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


def physical_evidence_digest(evidence: Mapping[str, Any]) -> str:
    material = {
        "platform": _text(evidence.get("platform"), 40).upper(),
        "handoff_digest": _text(evidence.get("handoff_digest"), 160),
        "input_digest": _text(evidence.get("input_digest"), 160),
        "probe_principal_id": _text(evidence.get("probe_principal_id"), 160),
        "probe_session_id": _text(evidence.get("probe_session_id"), 160),
        "proofs": _proofs(evidence.get("proofs")),
    }
    return _digest(material)


def _verify_physical_evidence(
    evidence: Mapping[str, Any],
    *,
    evidence_verifier: Any,
    handoff_digest: str,
    input_digest: str,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    computed = physical_evidence_digest(evidence)
    if _text(evidence.get("physical_evidence_digest"), 160) != computed:
        blockers.append("PHYSICAL_EVIDENCE_DIGEST_MISMATCH")
    if not callable(evidence_verifier):
        blockers.append("INDEPENDENT_PHYSICAL_EVIDENCE_VERIFIER_REQUIRED")
        return {}, blockers
    try:
        verdict = evidence_verifier(dict(evidence))
    except Exception:
        blockers.append("PHYSICAL_EVIDENCE_VERIFIER_FAILED")
        return {}, blockers
    if not isinstance(verdict, Mapping) or verdict.get("state") != "VERIFIED":
        blockers.append("PHYSICAL_EVIDENCE_VERIFIER_NOT_VERIFIED")
        return dict(verdict) if isinstance(verdict, Mapping) else {}, blockers

    expected_pairs = (
        ("handoff_digest", handoff_digest, "PHYSICAL_VERIFIER_HANDOFF_MISMATCH"),
        ("input_digest", input_digest, "PHYSICAL_VERIFIER_INPUT_MISMATCH"),
        ("physical_evidence_digest", computed, "PHYSICAL_VERIFIER_EVIDENCE_DIGEST_MISMATCH"),
    )
    for field, expected, blocker in expected_pairs:
        if verdict.get(field) != expected:
            blockers.append(blocker)
    if verdict.get("cryptographically_verified") is not True:
        blockers.append("PHYSICAL_EVIDENCE_CRYPTOGRAPHIC_VERIFICATION_REQUIRED")
    if verdict.get("independent") is not True:
        blockers.append("PHYSICAL_EVIDENCE_INDEPENDENCE_REQUIRED")
    return dict(verdict), blockers


def evaluate_physical_executor_readiness(
    *,
    handoff: Mapping[str, Any] | None,
    physical_evidence: Mapping[str, Any] | None,
    evidence_verifier: Any = None,
    environment: Mapping[str, Any] | None,
    allowed_files: Sequence[Any] | None,
    current_input_digest: str,
) -> dict[str, Any]:
    h = dict(handoff or {})
    evidence = dict(physical_evidence or {})
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

    platform = _text(evidence.get("platform"), 40).upper()
    if platform != "WINDOWS":
        blockers.append("WINDOWS_PLATFORM_REQUIRED")
    if evidence.get("independent") is not True:
        blockers.append("INDEPENDENT_PHYSICAL_EVIDENCE_REQUIRED")
    if evidence.get("handoff_digest") != h.get("handoff_digest"):
        blockers.append("PHYSICAL_EVIDENCE_HANDOFF_MISMATCH")
    if evidence.get("input_digest") != expected:
        blockers.append("PHYSICAL_EVIDENCE_INPUT_MISMATCH")
    if not _text(evidence.get("probe_principal_id"), 160):
        blockers.append("PHYSICAL_PROBE_PRINCIPAL_REQUIRED")
    if not _text(evidence.get("probe_session_id"), 160):
        blockers.append("PHYSICAL_PROBE_SESSION_REQUIRED")

    verifier_result, verifier_blockers = _verify_physical_evidence(
        evidence,
        evidence_verifier=evidence_verifier,
        handoff_digest=_text(h.get("handoff_digest"), 160),
        input_digest=expected,
    )
    blockers.extend(verifier_blockers)

    proofs = _proofs(evidence.get("proofs"))
    verifier_proofs = verifier_result.get("verified_proofs")
    verifier_proof_set = (
        {str(x) for x in verifier_proofs}
        if isinstance(verifier_proofs, (list, tuple))
        else set()
    )
    for name in REQUIRED_PROOFS:
        row = proofs.get(name) or {}
        if row.get("verified") is not True:
            blockers.append(name + "_REQUIRED")
            continue
        if name not in verifier_proof_set:
            blockers.append(name + "_NOT_BOUND_BY_VERIFIER")
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

    blockers = list(dict.fromkeys(blockers))
    material = {
        "schema": SCHEMA,
        "state": READY if not blockers else BLOCKED,
        "blockers": blockers,
        "handoff_digest": h.get("handoff_digest"),
        "input_digest": expected,
        "platform": platform,
        "physical_evidence_digest": _text(evidence.get("physical_evidence_digest"), 160),
        "physical_verifier_ref": _text(verifier_result.get("verifier_ref"), 160),
        "physical_evidence_cryptographically_verified": verifier_result.get("cryptographically_verified") is True,
        "required_proofs": list(REQUIRED_PROOFS),
        "verified_proofs": [name for name in REQUIRED_PROOFS if name in verifier_proof_set],
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
    "physical_evidence_digest", "evaluate_physical_executor_readiness",
    "expected_executor_receipt_template",
]
