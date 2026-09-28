"""Source-bound consumption gate for a future physical patch transition.

This is a consumption barrier. It does not execute, apply a patch, write the
filesystem, open a shell, spawn a process, mutate git, merge, deploy, trade,
or run a physical probe.

``assert_source_bound_patch_proof_record`` can still accept a stored proof
record that was resealed together with a coherently adulterated patch
document. That remains an accepted structural limitation of storage. The
record is not replay proof and is not consumption authorization.

This gate refuses that path. It requires the raw unified diff as transient
input, calls ``verify_source_bound_patch`` again, and accepts only a complete
correspondence among the builder request, the preflight, the sealed patch
validation, those bytes, and the baseline and candidate refs. Caller input is
not a root of trust. ``independent_external_verification`` stays false. The
raw patch is not stored.

Design-only readiness of Runner, Command Policy, OS Sandbox and Probe Result
does not call this gate. A future physical execution or probe that depends on
the patch must. ``SOURCE_BOUND_PATCH_MATCH`` on a saved record does not open
that transition.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from atlasquant_aion_developer_manifest import stable_digest
from atlasquant_aion_developer_source_bound_patch_proof import (
    READY_STATE as SOURCE_BOUND_PATCH_MATCH,
    SOURCE_BOUND_VERIFICATION,
    SOURCE_PROVENANCE,
    STRUCTURAL_INTEGRITY,
    VERIFICATION_LAYERS,
    source_bound_patch_proof_manifest,
    verify_source_bound_patch,
)

SCHEMA = "ATLASQUANT_AION_DEVELOPER_SOURCE_BOUND_CONSUMPTION_GATE_V1"
READY_STATE = "SOURCE_BOUND_CONSUMPTION_REPLAY_MATCH"
CONSUMPTION_BASIS = "TRANSIENT_REPLAY_NOT_STORED_RECORD"
STORED_PROOF_RELATION = "STORED_PROOF_IS_NOT_REPLAY_PROOF"
_STORED_RECORD_NOT_AUTHORIZATION = (
    "stored source-bound proof record is not replay proof and does not authorize consumption"
)
_MATCH_STATE_NOT_PHYSICAL = (
    "SOURCE_BOUND_PATCH_MATCH does not release the future physical consumption gate"
)
_FALSE_FLAGS = (
    "patch_applied",
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "filesystem_write_authorized",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "shell_authorized",
    "git_mutation_authorized",
    "automatic_commit",
    "automatic_merge",
    "automatic_deploy",
    "production_change_allowed",
    "real_trading_enabled",
    "physical_execution_authorized",
    "physical_probe_authorized",
    "physical_probe_executed",
    "physical_probe_passed",
    "physical_proof_verified",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "tool_output_is_authority",
    "stored_proof_is_replay_proof",
    "stored_proof_record_is_consumption_authorization",
    "source_bound_patch_match_authorizes_physical_consumption",
    "saved_receipt_authorizes_physical_execution",
    "caller_input_is_independent_authority",
    "source_provenance_is_independent_authority",
    "independent_external_verification",
    "patch_text_included",
    "design_only_readiness_requires_consumption_gate",
)
_TRUE_FLAGS = (
    "consumption_requires_transient_replay",
    "replay_performed",
    "stored_proof_is_not_replay_proof",
    "human_patch_review_required",
    "source_bound_replay_required_before_physical_execution",
    "future_physical_patch_execution_requires_consumption_gate",
    "content_binding_requires_external_verification",
)
_CONTRACT_KEYS = frozenset({
    "schema",
    "consumption_id",
    "state",
    "builder_request_id",
    "preflight_id",
    "validation_id",
    "patch_digest",
    "patch_manifest_id",
    "baseline_ref",
    "candidate_ref",
    "replay_proof_id",
    "verification_layers",
    "structural_integrity",
    "source_bound_verification",
    "source_provenance",
    "consumption_basis",
    "stored_proof_relation",
}) | frozenset(_FALSE_FLAGS) | frozenset(_TRUE_FLAGS)
_MANIFEST_KEYS = tuple(sorted(_CONTRACT_KEYS - {"consumption_id"}))
_STORED_AUTHORITY_FLAGS = (
    "execution_authorized",
    "physical_execution_authorized",
    "physical_probe_authorized",
    "physical_probe_passed",
    "caller_input_is_independent_authority",
    "source_provenance_is_independent_authority",
    "stored_proof_is_replay_proof",
    "stored_proof_record_is_consumption_authorization",
    "source_bound_patch_match_authorizes_physical_consumption",
)


def _reject_closed(document: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} field {unknown[0]}")
    missing = sorted(allowed - set(document))
    if missing:
        raise ValueError(f"{label} is missing {missing[0]}")


def _require_token(value: Any, expected: str, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} is not {expected}")


def _bare_match_state(value: Any) -> bool:
    if value == SOURCE_BOUND_PATCH_MATCH:
        return True
    return (
        isinstance(value, Mapping)
        and set(value) <= {"state"}
        and value.get("state") == SOURCE_BOUND_PATCH_MATCH
    )


def source_bound_consumption_manifest(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Authority fields of a consumption receipt. ``consumption_id`` is not an input."""
    if not isinstance(receipt, Mapping):
        raise ValueError("source-bound consumption receipt must be an object")
    return {key: receipt.get(key) for key in _MANIFEST_KEYS}


def expected_source_bound_consumption_id(receipt: Mapping[str, Any]) -> str:
    """Digest the consumption manifest. A caller-supplied id is not an input."""
    return stable_digest(
        source_bound_consumption_manifest(receipt),
        prefix="DEVSRCGATE-",
        length=24,
    )


def _reject_caller_claims(caller_claims: Mapping[str, Any]) -> None:
    if not caller_claims:
        return
    field = sorted(caller_claims)[0]
    raise ValueError(f"caller consumption claim is not authority: {field}")


def _reject_stored_proof_as_authority(stored_proof: Any) -> None:
    """A presented record is never the consumption decision."""
    if stored_proof is None or _bare_match_state(stored_proof):
        return
    if not isinstance(stored_proof, Mapping):
        raise ValueError(_STORED_RECORD_NOT_AUTHORIZATION)
    known = set(source_bound_patch_proof_manifest(stored_proof)) | {"proof_id"}
    unknown = sorted(set(stored_proof) - known)
    if unknown:
        raise ValueError(f"unknown source-bound consumption authority field {unknown[0]}")
    if stored_proof.get("independent_external_verification") is True:
        raise ValueError("independent external verification cannot be claimed")
    for field in _STORED_AUTHORITY_FLAGS:
        if stored_proof.get(field) is True:
            raise ValueError(f"stored source-bound proof record cannot authorize {field}")


def _assert_receipt(
    receipt: Mapping[str, Any],
    replay: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
) -> None:
    if not isinstance(receipt, Mapping):
        raise ValueError("source-bound consumption receipt must be an object")
    if receipt.get("schema") != SCHEMA:
        raise ValueError("invalid source-bound consumption receipt")
    _reject_closed(receipt, _CONTRACT_KEYS, "source-bound consumption receipt")
    if receipt.get("state") != READY_STATE:
        raise ValueError("source-bound consumption state was not derived")
    if list(receipt.get("verification_layers") or []) != list(VERIFICATION_LAYERS):
        raise ValueError("verification layers are not the separated quartet")
    _require_token(receipt.get("structural_integrity"), STRUCTURAL_INTEGRITY, "structural integrity")
    _require_token(
        receipt.get("source_bound_verification"),
        SOURCE_BOUND_VERIFICATION,
        "source-bound verification",
    )
    _require_token(receipt.get("source_provenance"), SOURCE_PROVENANCE, "source provenance")
    _require_token(receipt.get("consumption_basis"), CONSUMPTION_BASIS, "consumption basis")
    _require_token(
        receipt.get("stored_proof_relation"),
        STORED_PROOF_RELATION,
        "stored proof relation",
    )
    if receipt.get("independent_external_verification") is not False:
        raise ValueError("independent external verification cannot be claimed")
    for field in _TRUE_FLAGS:
        if receipt.get(field) is not True:
            raise ValueError(f"source-bound consumption gate requires {field}")
    for field in _FALSE_FLAGS:
        if receipt.get(field) is not False:
            raise ValueError(f"source-bound consumption gate cannot claim {field}")
    for field in (
        "consumption_id",
        "builder_request_id",
        "preflight_id",
        "validation_id",
        "patch_digest",
        "patch_manifest_id",
        "baseline_ref",
        "candidate_ref",
        "replay_proof_id",
    ):
        value = receipt.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} is required")
    if receipt.get("replay_proof_id") != replay.get("proof_id"):
        raise ValueError("consumption replay proof was not derived from the transient patch")
    for field in ("builder_request_id", "preflight_id", "validation_id", "patch_digest"):
        if receipt.get(field) != replay.get(field) or receipt.get(field) != patch_validation.get(field):
            raise ValueError("consumption lineage was not derived from the transient patch")
    for field in ("baseline_ref", "candidate_ref", "patch_manifest_id"):
        if receipt.get(field) != replay.get(field):
            raise ValueError("consumption lineage was not derived from the transient patch")
    revision = patch_validation.get("revision_binding")
    if not isinstance(revision, Mapping):
        raise ValueError("patch revision binding must be an object")
    if receipt.get("baseline_ref") != revision.get("baseline_ref"):
        raise ValueError("consumption baseline was not derived from the transient patch")
    if receipt.get("candidate_ref") != revision.get("candidate_ref"):
        raise ValueError("consumption candidate was not derived from the transient patch")
    if receipt.get("patch_digest") != patch_validation.get("patch_digest"):
        raise ValueError("consumption digest was not derived from the transient patch")
    if receipt.get("validation_id") != patch_validation.get("validation_id"):
        raise ValueError("consumption validation was not derived from the transient patch")
    if receipt.get("consumption_id") != expected_source_bound_consumption_id(receipt):
        raise ValueError("source-bound consumption id mismatch")


def assert_source_bound_consumption_gate(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    patch_text: Any,
    *,
    baseline_ref: Any,
    candidate_ref: Any,
    stored_proof: Any = None,
    **caller_claims: Any,
) -> dict[str, Any]:
    """Replay the transient patch before any future physical consumption.

    A stored source-bound proof record is ignored as authority. Omitting the
    transient patch, presenting only ``SOURCE_BOUND_PATCH_MATCH``, or asking
    the caller to certify independent verification does not open the gate.
    The returned receipt is the record of this replay. It does not authorize
    execution, and saving it does not become a later replay.
    """
    _reject_caller_claims(caller_claims)
    if _bare_match_state(patch_text) or (
        not isinstance(patch_text, str) and _bare_match_state(stored_proof)
    ):
        raise ValueError(_MATCH_STATE_NOT_PHYSICAL)
    if not isinstance(patch_text, str):
        raise ValueError(_STORED_RECORD_NOT_AUTHORIZATION)
    _reject_stored_proof_as_authority(stored_proof)
    replay = verify_source_bound_patch(
        builder_request,
        preflight,
        patch_validation,
        patch_text,
        baseline_ref=baseline_ref,
        candidate_ref=candidate_ref,
    )
    receipt = {
        "schema": SCHEMA,
        "consumption_id": "",
        "state": READY_STATE,
        "builder_request_id": replay["builder_request_id"],
        "preflight_id": replay["preflight_id"],
        "validation_id": replay["validation_id"],
        "patch_digest": replay["patch_digest"],
        "patch_manifest_id": replay["patch_manifest_id"],
        "baseline_ref": replay["baseline_ref"],
        "candidate_ref": replay["candidate_ref"],
        "replay_proof_id": replay["proof_id"],
        "verification_layers": list(VERIFICATION_LAYERS),
        "structural_integrity": STRUCTURAL_INTEGRITY,
        "source_bound_verification": SOURCE_BOUND_VERIFICATION,
        "source_provenance": SOURCE_PROVENANCE,
        "consumption_basis": CONSUMPTION_BASIS,
        "stored_proof_relation": STORED_PROOF_RELATION,
        "independent_external_verification": False,
        **{field: True for field in _TRUE_FLAGS},
        **{field: False for field in _FALSE_FLAGS},
    }
    receipt["consumption_id"] = expected_source_bound_consumption_id(receipt)
    _assert_receipt(receipt, replay, patch_validation)
    rendered = json.dumps(receipt)
    if patch_text in rendered:
        raise ValueError("consumption receipt must not retain the transient patch")
    if stored_proof is not None and isinstance(stored_proof, Mapping):
        presented = stored_proof.get("proof_id")
        if isinstance(presented, str) and presented and presented != replay["proof_id"]:
            if presented in rendered:
                raise ValueError("stored proof id must not enter the consumption receipt")
    return receipt


__all__ = [
    "SCHEMA",
    "READY_STATE",
    "CONSUMPTION_BASIS",
    "STORED_PROOF_RELATION",
    "source_bound_consumption_manifest",
    "expected_source_bound_consumption_id",
    "assert_source_bound_consumption_gate",
]
