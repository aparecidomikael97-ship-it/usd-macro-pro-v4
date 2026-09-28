"""Source-bound patch proof for the AION Developer chain.

This boundary is not structural integrity, not source provenance, and not
independent external verification.

Structural integrity accepts a coherent reseal of the sealed patch document.
Source-bound verification closes that reseal only while the original unified
diff is supplied as transient input: the digest, the parse, the manifest and
the validation id are re-derived and the entire representation is compared
with the sealed document. The raw patch is not stored.

Source provenance records that those bytes were caller-supplied. That label
is not an independent root of trust. Independent external verification stays
false: no git object is read, no binary is hashed, and no probe runs.

A stored proof record without the transient bytes is not a replay. Rebuilding
the record to match a mutated document does not prove the original diff.
That limitation is accepted for storage only. The stored record is not
consumption authorization. Any future physical execution or probe that
depends on the patch must pass the source-bound consumption gate with the
transient diff. Design-only readiness does not call that gate and does not
become physical execution.
"""
from __future__ import annotations

from typing import Any, Mapping

from atlasquant_aion_developer_builder_sandbox import assert_builder_sandbox_request_integrity
from atlasquant_aion_developer_manifest import stable_digest
from atlasquant_aion_developer_patch_validation import (
    assert_patch_validation_integrity,
    expected_patch_validation_id,
    parse_patch_semantics,
    patch_text_digest,
    patch_validation_manifest,
    patch_validation_manifest_id,
)
from atlasquant_aion_developer_sandbox_preflight import assert_sandbox_preflight_integrity

SCHEMA = "ATLASQUANT_AION_DEVELOPER_SOURCE_BOUND_PATCH_PROOF_V1"
READY_STATE = "SOURCE_BOUND_PATCH_MATCH"
STRUCTURAL_INTEGRITY = "STRUCTURAL_INTEGRITY"
SOURCE_BOUND_VERIFICATION = "SOURCE_BOUND_VERIFICATION"
SOURCE_PROVENANCE = "CALLER_SUPPLIED_TRANSIENT_PATCH"
INDEPENDENT_EXTERNAL_VERIFICATION = "INDEPENDENT_EXTERNAL_VERIFICATION"
VERIFICATION_LAYERS = (
    STRUCTURAL_INTEGRITY,
    SOURCE_BOUND_VERIFICATION,
    SOURCE_PROVENANCE,
    INDEPENDENT_EXTERNAL_VERIFICATION,
)
_FALSE_FLAGS = (
    "patch_applied",
    "execution_authorized",
    "executor_attached",
    "commands_executed",
    "writes_files",
    "runs_tests",
    "network_called",
    "subprocess_called",
    "automatic_commit",
    "automatic_merge",
    "automatic_deploy",
    "production_change_allowed",
    "real_trading_enabled",
    "symlink_physical_boundary_verified",
    "hardlink_physical_boundary_verified",
    "tool_output_is_authority",
    "physical_probe_passed",
    "physical_proof_verified",
)
_CONTRACT_KEYS = frozenset({
    "schema",
    "proof_id",
    "state",
    "builder_request_id",
    "preflight_id",
    "validation_id",
    "patch_digest",
    "patch_manifest_id",
    "baseline_ref",
    "candidate_ref",
    "verification_layers",
    "structural_integrity",
    "source_bound_verification",
    "source_provenance",
    "independent_external_verification",
    "caller_input_is_independent_authority",
    "source_provenance_is_independent_authority",
    "replay_requires_transient_patch",
    "patch_text_included",
    "human_patch_review_required",
    "source_bound_proof_required_before_physical_execution",
    "content_binding_requires_external_verification",
}) | frozenset(_FALSE_FLAGS)
_MANIFEST_KEYS = tuple(sorted(_CONTRACT_KEYS - {"proof_id"}))


def _reject_closed(document: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} field {unknown[0]}")
    missing = sorted(allowed - set(document))
    if missing:
        raise ValueError(f"{label} is missing {missing[0]}")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _reject_caller_claims(caller_claims: Mapping[str, Any]) -> None:
    if not caller_claims:
        return
    field = sorted(caller_claims)[0]
    raise ValueError(f"caller source-bound claim is not authority: {field}")


def source_bound_patch_proof_manifest(proof: Mapping[str, Any]) -> dict[str, Any]:
    """Authority fields of a proof record. ``proof_id`` is not an input."""
    if not isinstance(proof, Mapping):
        raise ValueError("source-bound patch proof must be an object")
    return {key: proof.get(key) for key in _MANIFEST_KEYS}


def expected_source_bound_patch_proof_id(proof: Mapping[str, Any]) -> str:
    """Digest the proof manifest. A caller-supplied id is not an input."""
    return stable_digest(
        source_bound_patch_proof_manifest(proof),
        prefix="DEVSRCBIND-",
        length=24,
    )


def _require_token(value: Any, expected: str, label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} is not {expected}")


def assert_source_bound_patch_proof_record(
    proof: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> str:
    """Check that a stored record names this sealed patch document.

    This is structural binding of the record. It does not replay the transient
    patch and it does not establish independent external verification.
    """
    assert_builder_sandbox_request_integrity(builder_request)
    assert_sandbox_preflight_integrity(preflight, builder_request)
    assert_patch_validation_integrity(patch_validation, builder_request, preflight)
    if not isinstance(proof, Mapping):
        raise ValueError("source-bound patch proof must be an object")
    if proof.get("schema") != SCHEMA:
        raise ValueError("invalid source-bound patch proof")
    _reject_closed(proof, _CONTRACT_KEYS, "source-bound patch proof")
    if list(proof.get("verification_layers") or []) != list(VERIFICATION_LAYERS):
        raise ValueError("verification layers are not the separated quartet")
    _require_token(proof.get("structural_integrity"), STRUCTURAL_INTEGRITY, "structural integrity")
    _require_token(
        proof.get("source_bound_verification"),
        SOURCE_BOUND_VERIFICATION,
        "source-bound verification",
    )
    _require_token(proof.get("source_provenance"), SOURCE_PROVENANCE, "source provenance")
    if proof.get("independent_external_verification") is not False:
        raise ValueError("independent external verification cannot be claimed")
    if proof.get("caller_input_is_independent_authority") is not False:
        raise ValueError("caller input is not independent authority")
    if proof.get("source_provenance_is_independent_authority") is not False:
        raise ValueError("source provenance is not independent authority")
    if proof.get("replay_requires_transient_patch") is not True:
        raise ValueError("source-bound replay requires the transient patch")
    if proof.get("patch_text_included") is not False:
        raise ValueError("patch text must stay outside the source-bound proof")
    if proof.get("human_patch_review_required") is not True:
        raise ValueError("human patch review remains required")
    if proof.get("source_bound_proof_required_before_physical_execution") is not True:
        raise ValueError("source-bound proof does not authorize physical execution")
    if proof.get("content_binding_requires_external_verification") is not True:
        raise ValueError("independent external content binding is still required")
    for field in _FALSE_FLAGS:
        if proof.get(field) is not False:
            raise ValueError(f"source-bound proof cannot claim {field}")
    if proof.get("state") != READY_STATE:
        raise ValueError("source-bound proof state was not derived")
    for field in (
        "proof_id",
        "builder_request_id",
        "preflight_id",
        "validation_id",
        "patch_digest",
        "patch_manifest_id",
        "baseline_ref",
        "candidate_ref",
    ):
        value = proof.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field} is required")
    if proof.get("builder_request_id") != builder_request.get("request_id"):
        raise ValueError("source-bound proof request lineage mismatch")
    if proof.get("preflight_id") != preflight.get("preflight_id"):
        raise ValueError("source-bound proof preflight lineage mismatch")
    if proof.get("validation_id") != patch_validation.get("validation_id"):
        raise ValueError("source-bound proof validation lineage mismatch")
    if proof.get("patch_digest") != patch_validation.get("patch_digest"):
        raise ValueError("source-bound proof digest lineage mismatch")
    if proof.get("patch_manifest_id") != patch_validation_manifest_id(patch_validation):
        raise ValueError("source-bound proof manifest lineage mismatch")
    revision = patch_validation.get("revision_binding")
    if not isinstance(revision, Mapping):
        raise ValueError("patch revision binding must be an object")
    if proof.get("baseline_ref") != revision.get("baseline_ref"):
        raise ValueError("source-bound proof baseline mismatch")
    if proof.get("candidate_ref") != revision.get("candidate_ref"):
        raise ValueError("source-bound proof candidate mismatch")
    proof_id = proof.get("proof_id")
    if proof_id != expected_source_bound_patch_proof_id(proof):
        raise ValueError("source-bound proof id mismatch")
    return str(proof_id)


def verify_source_bound_patch(
    builder_request: Mapping[str, Any],
    preflight: Mapping[str, Any],
    patch_validation: Mapping[str, Any],
    patch_text: Any,
    *,
    baseline_ref: Any,
    candidate_ref: Any,
    **caller_claims: Any,
) -> dict[str, Any]:
    """Re-derive the sealed patch from transient text and compare all of it.

    Caller claims are rejected. A match is source-bound verification of the
    supplied bytes, not independent external verification and not permission
    to execute, merge or deploy.
    """
    _reject_caller_claims(caller_claims)
    if not isinstance(patch_text, str):
        raise ValueError("transient patch text must be a string")
    assert_patch_validation_integrity(patch_validation, builder_request, preflight)
    rederived = parse_patch_semantics(
        builder_request,
        preflight,
        patch_text,
        baseline_ref=baseline_ref,
        candidate_ref=candidate_ref,
    )
    digest = patch_text_digest(patch_text)
    if rederived.get("patch_digest") != digest or patch_validation.get("patch_digest") != digest:
        raise ValueError("patch digest was not derived from the transient patch")
    if patch_validation_manifest(patch_validation) != patch_validation_manifest(rederived):
        raise ValueError("patch manifest was not derived from the transient patch")
    if (
        patch_validation.get("validation_id") != rederived.get("validation_id")
        or patch_validation.get("validation_id") != expected_patch_validation_id(rederived)
    ):
        raise ValueError("patch validation id was not derived from the transient patch")
    if _plain(patch_validation) != rederived:
        raise ValueError("sealed patch document was not derived from the transient patch")
    revision = rederived["revision_binding"]
    record = {
        "schema": SCHEMA,
        "proof_id": "",
        "state": READY_STATE,
        "builder_request_id": rederived["builder_request_id"],
        "preflight_id": rederived["preflight_id"],
        "validation_id": rederived["validation_id"],
        "patch_digest": digest,
        "patch_manifest_id": patch_validation_manifest_id(rederived),
        "baseline_ref": revision["baseline_ref"],
        "candidate_ref": revision["candidate_ref"],
        "verification_layers": list(VERIFICATION_LAYERS),
        "structural_integrity": STRUCTURAL_INTEGRITY,
        "source_bound_verification": SOURCE_BOUND_VERIFICATION,
        "source_provenance": SOURCE_PROVENANCE,
        "independent_external_verification": False,
        "caller_input_is_independent_authority": False,
        "source_provenance_is_independent_authority": False,
        "replay_requires_transient_patch": True,
        "patch_text_included": False,
        "human_patch_review_required": True,
        "source_bound_proof_required_before_physical_execution": True,
        "content_binding_requires_external_verification": True,
        **{field: False for field in _FALSE_FLAGS},
    }
    record["proof_id"] = expected_source_bound_patch_proof_id(record)
    assert_source_bound_patch_proof_record(record, patch_validation, builder_request, preflight)
    return record


__all__ = [
    "SCHEMA",
    "READY_STATE",
    "STRUCTURAL_INTEGRITY",
    "SOURCE_BOUND_VERIFICATION",
    "SOURCE_PROVENANCE",
    "INDEPENDENT_EXTERNAL_VERIFICATION",
    "VERIFICATION_LAYERS",
    "source_bound_patch_proof_manifest",
    "expected_source_bound_patch_proof_id",
    "assert_source_bound_patch_proof_record",
    "verify_source_bound_patch",
]
