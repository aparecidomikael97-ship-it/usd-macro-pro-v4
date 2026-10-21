"""H0 LAB only: cross-bind five SYNTHETIC signed envelopes from prior LABs.

Inputs: caller-supplied registry root and custodian test keys; registry
enrollment, revocation, nonce challenge; reservation and readback witnesses.
The registered synthetic role keys, not another set of caller-supplied
witness pins, MUST verify the reservation/readback Ed25519 signatures.

This is a cryptographic *consistency* experiment, NOT issuer enrollment,
nonce issuance/consumption, remote freshness, independent administration,
HUMAN_OWNER authentication, producer-effect attestation or any authorization.
Even a perfect five-envelope chain is permanently HARD_NO_GO.
"""
from __future__ import annotations

from typing import Any

import atlasquant_aion_p0_h0_enrollment_revocation_nonce_lab as registry
import atlasquant_aion_p0_h0_dual_signed_witness_transcript_lab as witness

SCHEMA = "AION_P0_H0_LINKED_FIVE_ENVELOPES_LAB_V1"
EXPECTED_FIELDS = frozenset((
    "attempt_nonce", "expected_head_epoch", "expected_version_id",
))
AUTHORITY_FALSE = {
    "external_issuer_independently_enrolled": False,
    "role_key_possession_externally_attested": False,
    "independent_admin_domains_authenticated": False,
    "current_revocation_authenticated": False,
    "nonce_independently_issued": False,
    "nonce_atomically_consumed_off_host": False,
    "nonce_replay_excluded": False,
    "trusted_clock_authenticated": False,
    "latest_remote_head_authenticated": False,
    "first_attempt_effect_causally_proven": False,
    "provider_effect_or_no_effect_authenticated": False,
    "human_owner_authenticated": False,
    "physical_rollback_ruled_out": False,
    "first_external_effect_allowed": False,
    "worker_arming_allowed": False,
    "automatic_retry_allowed": False,
    "external_action_executed": False,
}
PERMANENT_BLOCKERS = (
    "CALLER_PROVIDED_ROOT_KEYS_AND_EXPECTATIONS",
    "NO_INDEPENDENT_OUT_OF_BAND_ENROLLMENT",
    "NO_TRUSTED_LATEST_REVOCATION_OR_KEY_ROTATION",
    "NO_ATOMIC_DURABLE_OFF_HOST_NONCE_CONSUMPTION",
    "NO_TRUSTED_CLOCK_OR_LATEST_REMOTE_HEAD",
    "NO_ADMINISTRATIVE_INDEPENDENCE_PROOF",
    "NO_PROVIDER_ORIGIN_CAUSAL_EFFECT_RECEIPT",
    "NO_HUMAN_OWNER_IDENTITY_OR_CONSENT",
    "NO_PHYSICAL_ROLLBACK_PROOF",
    "CANONICAL_QUALITY_NOT_GREEN",
)


def _result(findings: set[str], registry_ok: bool = False,
            witness_ok: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "HARD_NO_GO",
        "allowed": False,
        "simulation_only": True,
        "synthetic_registry_chain_consistent_lab": registry_ok,
        "synthetic_witness_pair_consistent_lab": witness_ok,
        "synthetic_five_envelopes_linked_lab": (
            registry_ok and witness_ok and not findings
        ),
        "findings": tuple(sorted(findings)),
        "blockers": PERMANENT_BLOCKERS,
        **AUTHORITY_FALSE,
    }


def inspect_linked_five_envelopes_lab(
    enrollment: Any, revocation: Any, challenge: Any,
    reservation: Any, readback: Any,
    caller_registry_pins: Any, caller_expectations: Any, *,
    now_utc: Any,
) -> dict[str, Any]:
    """Verify only mathematical/transcript consistency; NEVER grant effects.

    Reject malformed expectations before dereference; never derive authority
    from a verified-looking caller claim. All payload access after verifying
    exact type/schema and valid Ed25519 signatures through the LAB validators.
    """
    if (type(caller_expectations) is not dict
            or any(type(k) is not str for k in caller_expectations)
            or frozenset(caller_expectations) != EXPECTED_FIELDS
            or not witness._is_id(caller_expectations["attempt_nonce"])
            or not witness._is_id(caller_expectations["expected_version_id"])
            or not registry._pos(caller_expectations["expected_head_epoch"])):
        return _result({"CALLER_EXPECTATIONS_INVALID"})

    registry_result = registry.inspect_enrollment_revocation_nonce_lab(
        enrollment, revocation, challenge, caller_registry_pins,
        now_utc=now_utc,
    )
    if not registry_result["synthetic_policy_consistent_lab"]:
        return _result(
            {"REGISTRY:" + finding for finding in registry_result["findings"]}
            or {"REGISTRY_INVALID_OR_INCOMPLETE"}
        )

    enrollment_payload = enrollment["payload"]
    revocation_payload = revocation["payload"]
    challenge_payload = challenge["payload"]
    roles = {role["role"]: role for role in enrollment_payload["roles"]}
    writer = roles["reservation_signer"]
    reader = roles["readback_witness"]

    # A caller can generate four independent private keys. Distinct bytes do
    # not prove distinct independent entities, but obvious key reuse is denied.
    public_keys = (
        caller_registry_pins["registry_root_public_key_b64url"],
        caller_registry_pins["custodian_public_key_b64url"],
        writer["public_key_b64url"],
        reader["public_key_b64url"],
    )
    if len(set(public_keys)) != len(public_keys):
        return _result({"ROOT_CUSTODIAN_OR_WITNESS_KEY_REUSED"}, registry_ok=True)

    # Witness key IDs and actual public bytes come from a *previously verified
    # synthetic signed enrollment*. DO NOT accept arbitrary independent
    # witness keys passed alongside this pair of signatures.
    dual_pins = {
        "reservation_public_key_b64url": writer["public_key_b64url"],
        "readback_public_key_b64url": reader["public_key_b64url"],
        "reservation_key_id": writer["key_id"],
        "readback_key_id": reader["key_id"],
        "issuer_id": enrollment_payload["issuer_id"],
        "scope_digest": enrollment_payload["scope_digest"],
        "request_id": challenge_payload["request_id"],
        "intent_id": challenge_payload["intent_id"],
        "attempt_nonce": caller_expectations["attempt_nonce"],
        "challenge_nonce": challenge_payload["challenge_nonce"],
        "minimum_epoch": caller_expectations["expected_head_epoch"],
        "minimum_sequence": challenge_payload["head_sequence"],
        "expected_version_id": caller_expectations["expected_version_id"],
        "expected_head_digest": challenge_payload["head_digest"],
    }
    paired = witness.inspect_dual_signed_witness_lab(
        reservation, readback, dual_pins, now_utc=now_utc,
    )
    if not paired["signed_transcripts_consistent_lab"]:
        return _result(
            {"WITNESS:" + finding for finding in paired["defects"]}
            or {"WITNESS_INVALID_OR_INCOMPLETE"},
            registry_ok=True,
        )

    findings: set[str] = set()
    reserve_payload = reservation["payload"]
    read_payload = readback["payload"]

    # Shared current head is bound to the signed challenge *and* readback,
    # not merely a caller-supplied second set of keys. Registry key epoch is
    # a different namespace from head epoch and should not be conflated.
    if reserve_payload["sequence"] != challenge_payload["head_sequence"]:
        findings.add("RESERVATION_HEAD_SEQUENCE_NOT_IN_SIGNED_CHALLENGE")
    if reserve_payload["head_digest"] != challenge_payload["head_digest"]:
        findings.add("RESERVATION_HEAD_DIGEST_NOT_IN_SIGNED_CHALLENGE")
    if reserve_payload["epoch"] != caller_expectations["expected_head_epoch"]:
        findings.add("HEAD_EPOCH_NOT_EXACT_CALLER_EXPECTATION")

    # Synthetic time comparison is *not* authenticated freshness. Challenge
    # must have been signed before reservation and remain unexpired through
    # the signed readback. No storage/replay state exists in this checker.
    issued_challenge = registry._date(challenge_payload["issued_at_utc"])
    expired_challenge = registry._date(challenge_payload["expires_at_utc"])
    issued_reserve = witness._date(reserve_payload["issued_at_utc"])
    observed_readback = witness._date(read_payload["observed_at_utc"])
    if (issued_challenge is None or expired_challenge is None
            or issued_reserve is None or observed_readback is None
            or not issued_challenge <= issued_reserve
                   <= observed_readback <= expired_challenge):
        findings.add("SIGNED_CHALLENGE_RESERVATION_READBACK_ORDER_INVALID")
    if revocation_payload["registry_seq"] != challenge_payload["registry_seq"]:
        findings.add("CHALLENGE_REVOCATION_SEQUENCE_DIVERGED")

    return _result(findings, registry_ok=True, witness_ok=True)
