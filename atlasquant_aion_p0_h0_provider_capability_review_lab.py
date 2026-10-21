"""AION P0/H0 — supplier protocol screening, not supplier attestation (LAB).

The entire manifest is CALLER-SUPPLIED. A declared capability, an HTTPS
documentation URL, a 2xx response, a signed-looking receipt, or an absent list
entry NEVER proves an external effect or its absence. This model performs NO
network access, cryptography, persistence, Outbox mutation, provider enrollment,
Worker arming or action execution. Results are permanently HARD_NO_GO.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "AION_P0_H0_PROVIDER_CAPABILITY_REVIEW_LAB_V1"
MANIFEST_SCHEMA = "AION_P0_H0_CALLER_PROVIDER_CLAIMS_V1"
MANIFEST_FIELDS = frozenset((
    "schema", "provider_id", "api_surface", "claims", "source_refs", "symptom",
))
CAPABILITIES = (
    "server_side_idempotency",
    "idempotency_scope_and_retention",
    "replay_dedup_after_timeout",
    "exact_attempt_lookup",
    "exhaustive_late_effect_readback",
    "fenced_no_effect",
    "producer_origin_receipt",
    "latest_head_authenticated",
    "atomically_offhost_first_attempt",
)
CRITICAL = frozenset((
    "server_side_idempotency",
    "replay_dedup_after_timeout",
    "fenced_no_effect",
    "atomically_offhost_first_attempt",
))
CLAIM_STATES = frozenset(("CLAIMED_SUPPORTED", "DECLARED_UNSUPPORTED", "UNKNOWN"))
API_SURFACES = frozenset((
    "TWILIO_PROGRAMMABLE_MESSAGING_CLASSIC",
    "TWILIO_COMMS_V1",
    "OTHER",
))
SYMPTOM_MEANING = {
    "POST_TIMEOUT": "TIMEOUT_NOT_PROOF_OF_NO_EFFECT",
    "HTTP_404": "NOT_FOUND_NOT_PROOF_OF_NO_EFFECT",
    "EMPTY_LIST": "ABSENT_FROM_SEARCH_NOT_PROOF_OF_NO_EFFECT",
    "PAGINATED_LIST_INCOMPLETE": "INCOMPLETE_HISTORY_NOT_PROOF_OF_NO_EFFECT",
    "HTTP_2XX": "ACK_NOT_INDEPENDENT_CAUSAL_EFFECT_ATTESTATION",
    "STATUS_DELIVERED": "STATUS_NOT_ATOMIC_FIRST_ATTEMPT_CUSTODY",
    "SCHEDULED_CANCELLED": "SCHEDULE_CANCEL_NOT_GENERAL_EFFECT_FENCE",
    "CALLER_SIGNED_RECEIPT": "CALLER_KEY_NOT_PROVIDER_ORIGIN",
    "UNKNOWN": "NO_PROVIDER_ORIGIN_OUTCOME_ESTABLISHED",
}
PROVIDER_ID = re.compile(r"[A-Za-z][A-Za-z0-9._-]{2,63}\Z")
REFERENCE = re.compile(r"https://[^\s<>\"']{1,292}\Z")
PERMANENT_BLOCKERS = (
    "PROVIDER_CLAIMS_AND_SOURCE_URLS_NOT_INDEPENDENTLY_VERIFIED",
    "NO_AUTHENTICATED_PROVIDER_ORIGIN_CAUSAL_RESULT",
    "NO_CURRENT_EXHAUSTIVE_PROVIDER_HEAD_OR_EFFECT_FENCE",
    "NO_INDEPENDENT_ATOMIC_FIRST_ATTEMPT_CUSTODY",
    "HUMAN_OWNER_AND_ISSUER_IDENTITY_NOT_ATTESTED",
    "NO_EXTERNAL_PRODUCER_ENROLLED_IN_AION",
    "QUALITY_AND_SIX_P0_NOT_HOMOLOGATED",
)
AUTHORITY_FALSE = {
    "provider_capabilities_independently_verified": False,
    "supplier_documentation_authenticated": False,
    "independent_provider_identity_enrolled": False,
    "provider_effect_authenticated": False,
    "provider_no_effect_authenticated": False,
    "complete_readback_authenticated": False,
    "latest_head_authenticated": False,
    "atomic_offhost_reservation_verified": False,
    "human_owner_authenticated": False,
    "first_external_effect_allowed": False,
    "automatic_retry_allowed": False,
    "manual_resend_allowed": False,
    "outbox_terminal_transition_allowed": False,
    "worker_arming_allowed": False,
    "external_action_executed": False,
}


def _plain(value: Any, fields: frozenset[str]) -> bool:
    return (
        type(value) is dict
        and all(type(k) is str for k in value)
        and frozenset(value) == fields
    )


def _result(findings: set[str], *, shape_ok: bool = False,
            provider_id: str = "", api_surface: str = "",
            symptom: str = "UNKNOWN", stated_supported: tuple[str, ...] = (),
            stated_unsupported: tuple[str, ...] = (),
            unstated: tuple[str, ...] = (),
            sources_count: int = 0, path: str = "INPUT_REJECTED") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "HARD_NO_GO",
        "allowed": False,
        "simulation_only": True,
        "read_only": True,
        "profile_shape_valid_lab": shape_ok,
        "provider_id": provider_id,
        "api_surface": api_surface,
        "symptom_interpretation": SYMPTOM_MEANING[symptom],
        "stated_supported_but_unverified": stated_supported,
        "stated_unsupported_not_independently_confirmed": stated_unsupported,
        "unresolved_claims": unstated,
        "source_links_supplied_not_verified": sources_count,
        "recommended_path": path,
        "external_truth": "UNKNOWN",
        "reconciliation_state": "UNKNOWN_BLOCKED",
        "findings": tuple(sorted(findings)),
        "blockers": PERMANENT_BLOCKERS,
        **AUTHORITY_FALSE,
    }


def inspect_provider_capability_review_lab(manifest: Any) -> dict[str, Any]:
    """Inspect only shape and caller-declared gaps; NEVER certify a provider."""
    if not _plain(manifest, MANIFEST_FIELDS):
        return _result({"MANIFEST_SHAPE_INVALID"})
    if manifest["schema"] != MANIFEST_SCHEMA or type(manifest["schema"]) is not str:
        return _result({"MANIFEST_SCHEMA_INVALID"})
    provider = manifest["provider_id"]
    if type(provider) is not str or PROVIDER_ID.fullmatch(provider) is None:
        return _result({"PROVIDER_IDENTIFIER_INVALID"})
    surface = manifest["api_surface"]
    if type(surface) is not str or surface not in API_SURFACES:
        return _result({"API_SURFACE_INVALID"})
    symptom = manifest["symptom"]
    if type(symptom) is not str or symptom not in SYMPTOM_MEANING:
        return _result({"SYMPTOM_INVALID"})
    claims = manifest["claims"]
    if not _plain(claims, frozenset(CAPABILITIES)):
        return _result({"CLAIM_MAP_INVALID"})
    if any(type(claims[k]) is not str or claims[k] not in CLAIM_STATES
           for k in CAPABILITIES):
        return _result({"CLAIM_STATUS_INVALID"})
    sources = manifest["source_refs"]
    if (type(sources) is not list or len(sources) > 8
            or any(type(s) is not str or REFERENCE.fullmatch(s) is None
                   for s in sources)
            or sources != sorted(set(sources))):
        return _result({"SOURCE_REFS_INVALID"})

    supported = tuple(k for k in CAPABILITIES if claims[k] == "CLAIMED_SUPPORTED")
    unsupported = tuple(k for k in CAPABILITIES if claims[k] == "DECLARED_UNSUPPORTED")
    unknown = tuple(k for k in CAPABILITIES if claims[k] == "UNKNOWN")
    findings = {"CAPABILITIES_ONLY_CALLER_DECLARATIONS"}
    findings.update("CLAIMED_UNSUPPORTED:" + k for k in unsupported)
    findings.update("NOT_ESTABLISHED:" + k for k in unknown)
    # A URL to the official vendor can help a future human review but does
    # NOT authenticate which API/account/protocol received the first attempt.
    if sources:
        findings.add("LINKS_ARE_NOT_VALIDATED_RECEIPTS_OR_FENCES")
    if any(claims[k] == "DECLARED_UNSUPPORTED" for k in CRITICAL):
        path = "SUPERVISED_RECONCILIATION_NO_RESEND"
    else:
        path = "PROTOCOL_AND_INDEPENDENT_ATTESTATION_REQUIRED_NO_RESEND"
    return _result(
        findings, shape_ok=True, provider_id=provider, api_surface=surface,
        symptom=symptom, stated_supported=supported,
        stated_unsupported=unsupported, unstated=unknown,
        sources_count=len(sources), path=path,
    )
