"""A296 LAB: fail-closed evidence contract for future independent authority.

No credible off-host trust root is available here. Even a perfectly formed,
fully populated 'Ed25519' claim is UNVERIFIED without independent public
key / custody evidence. This is a syntax and negative-evidence audit ONLY.
"""
import base64
import binascii
import hashlib
import json
import secrets
import time

SCHEMA = "ATLASQUANT_AION_EXTERNAL_AUTHORITY_EVIDENCE_CONTRACT_LAB_V1"
PACK_FIELDS = frozenset((
    "schema", "subject_digest", "epoch_digest", "claims",
))
CLAIM_FIELDS = frozenset((
    "obligation", "issuer_id", "issuer_domain",
    "verifier_id", "verifier_domain", "subject_digest",
    "epoch_digest", "nonce", "artifact_digest", "signature_algorithm",
    "signature_base64", "observed_at", "expires_at", "artifact_locator",
))
OBLIGATIONS = (
    "independent_owner_identity",
    "independent_custodian_identity",
    "cryptographic_intent_binding",
    "durable_off_host_epoch_and_nonce",
    "atomic_effect_and_ack_receipt",
    "authenticated_native_sqlite_vfs_fd",
    "host_resistant_antirollback_witness",
    "independent_uncertain_outcome_recovery",
)
HOST_DOMAINS = frozenset((
    "same_host", "same_process", "local_test", "self_attested",
))
ROLES = frozenset((
    "owner_independent",
    "custodian_independent",
    "provider_independent",
    "native_attestor_independent",
))
HEX = frozenset("0123456789abcdef")


def _valid_hex(value, length):
    return (
        type(value) is str and len(value) == length
        and all(c in HEX for c in value)
    )


def _base():
    return {
        "schema": SCHEMA,
        "research_only": True,
        "no_trusted_root_configured": True,
        "cryptographic_signatures_verified": 0,
        "no_authenticated_external_custody": True,
        "real_world_gate_block_reason": (
            "NO_EXTERNALLY_VERIFIED_TRUST_ROOT_OR_ATOMIC_EFFECT_EVIDENCE"
        ),
        "authenticated_obligations": 0,
        "p0_homologated": 0,
        "zero_auto_resend": True,
        "can_authorize_real_effect": False,
        "can_activate_worker": False,
        "can_deploy": False,
        "no_new_paid_services": True,
        "hard_no_go": True,
        "decision": "HARD_NO_GO",
    }


def _proof_shape(proof, now):
    """Syntactic only: even 64 fake bytes can look like an Ed25519 signature."""
    issues = []
    if type(proof) is not dict or frozenset(proof) != CLAIM_FIELDS:
        return ["CLAIM_FIELDS_INVALID"]
    for f in ("issuer_id", "verifier_id", "artifact_locator"):
        s = proof[f]
        if type(s) is not str or not s.strip() or len(s) > 256:
            issues.append("CLAIM_ID_OR_LOCATOR_INVALID:" + f)
    for f in ("subject_digest", "epoch_digest", "artifact_digest"):
        if not _valid_hex(proof[f], 64):
            issues.append("INVALID_DIGEST:" + f)
    if not _valid_hex(proof["nonce"], 32):
        issues.append("INVALID_NONCE")
    if proof["signature_algorithm"] != "Ed25519":
        issues.append("UNSUPPORTED_SIGNATURE_LABEL")
    sig = proof["signature_base64"]
    try:
        if type(sig) is not str:
            raise ValueError("signature not str")
        raw = base64.b64decode(sig, validate=True)
        if len(raw) != 64:
            raise ValueError("wrong signature size")
    except (binascii.Error, ValueError):
        issues.append("SIGNATURE_SHAPE_INVALID")
    observed, expiry = proof["observed_at"], proof["expires_at"]
    if (
        type(observed) is not int or type(expiry) is not int
        or observed > now or expiry <= now or expiry <= observed
        or expiry > now + 300
    ):
        issues.append("EVIDENCE_TIME_INVALID")
    if type(proof["issuer_domain"]) is not str:
        issues.append("ISSUER_DOMAIN_INVALID")
    if type(proof["verifier_domain"]) is not str:
        issues.append("VERIFIER_DOMAIN_INVALID")
    if proof["issuer_id"] == proof["verifier_id"]:
        issues.append("SELF_VERIFICATION_UNTRUSTED")
    if type(proof["issuer_domain"]) is str:
        if proof["issuer_domain"] in HOST_DOMAINS:
            issues.append("SAME_HOST_ISSUER_UNTRUSTED")
        if proof["issuer_domain"] not in ROLES:
            issues.append("ISSUER_TRUST_DOMAIN_NOT_ALLOWED")
    if type(proof["verifier_domain"]) is str:
        if proof["verifier_domain"] in HOST_DOMAINS:
            issues.append("SAME_HOST_VERIFIER_UNTRUSTED")
        if proof["verifier_domain"] not in ROLES:
            issues.append("VERIFIER_TRUST_DOMAIN_NOT_ALLOWED")
    if proof["issuer_domain"] == proof["verifier_domain"]:
        issues.append("NO_ROLE_DOMAIN_SEPARATION")
    return issues


def evaluate_evidence_contract(pack, *, now=None):
    """Never returns production GO. No trust roots or independent verifier."""
    result = _base()
    checked_at = int(time.time()) if now is None else now
    if type(checked_at) is not int:
        raise ValueError("invalid observation time")
    result.update({
        "required_obligations": list(OBLIGATIONS),
        "required_count": len(OBLIGATIONS),
        "present_obligations": [],
        "missing_obligations": list(OBLIGATIONS),
        "syntactically_complete_count": 0,
        "structurally_plausible": False,
        "issues": [],
    })
    issues = result["issues"]
    if type(pack) is not dict or frozenset(pack) != PACK_FIELDS:
        issues.append("PACK_FIELDS_INVALID")
        return result
    if pack["schema"] != SCHEMA:
        issues.append("PACK_SCHEMA_INVALID")
    for field in ("subject_digest", "epoch_digest"):
        if not _valid_hex(pack[field], 64):
            issues.append("PACK_DIGEST_INVALID:" + field)
    claims = pack["claims"]
    if type(claims) is not list or len(claims) > 64:
        issues.append("PACK_CLAIMS_INVALID")
        return result
    present = []
    nonces = set()
    for index, claim in enumerate(claims):
        if type(claim) is not dict:
            issues.append("CLAIM_FIELDS_INVALID:" + str(index))
            continue
        obligation = claim.get("obligation")
        if type(obligation) is not str or obligation not in OBLIGATIONS:
            issues.append("UNKNOWN_OBLIGATION:" + str(index))
        else:
            present.append(obligation)
        for issue in _proof_shape(claim, checked_at):
            issues.append(issue + ":" + str(index))
        if claim.get("subject_digest") != pack["subject_digest"]:
            issues.append("SUBJECT_BINDING_MISMATCH:" + str(index))
        if claim.get("epoch_digest") != pack["epoch_digest"]:
            issues.append("EPOCH_BINDING_MISMATCH:" + str(index))
        nonce = claim.get("nonce")
        if type(nonce) is str:
            if nonce in nonces:
                issues.append("NONCE_REPLAY:" + str(index))
            nonces.add(nonce)
    if len(present) != len(set(present)):
        issues.append("DUPLICATE_OBLIGATION")
    missing = sorted(set(OBLIGATIONS) - set(present))
    if missing:
        issues.append("MISSING_OBLIGATIONS")
    result["present_obligations"] = sorted(set(present))
    result["missing_obligations"] = missing
    result["issues"] = sorted(set(issues))
    result["syntactically_complete_count"] = (
        len(OBLIGATIONS) if not issues else 0
    )
    result["structurally_plausible"] = not issues
    # CRUCIAL: labels, fake signatures and structured data cannot establish
    # issuer custody, external verification, antirollback or real owner consent.
    # No caller-supplied 'verified' boolean ever overrides this rule.
    result["no_authenticated_external_custody"] = True
    result["real_world_gate_block_reason"] = (
        "NO_EXTERNALLY_VERIFIED_TRUST_ROOT_OR_ATOMIC_EFFECT_EVIDENCE"
    )
    return result


def synthetic_forged_complete_pack(*, now=None):
    """Explicit FORGED fixture: 8 syntactically valid, unverified fake proofs."""
    t = int(time.time()) if now is None else now
    subject = "a" * 64
    epoch = "b" * 64
    claims = []
    domains = sorted(ROLES)
    for i, obligation in enumerate(OBLIGATIONS):
        issuer = domains[i % len(domains)]
        verifier = domains[(i + 1) % len(domains)]
        claims.append({
            "obligation": obligation,
            "issuer_id": "self-claimed-" + issuer + "-" + str(i),
            "issuer_domain": issuer,
            "verifier_id": "self-claimed-" + verifier + "-" + str(i),
            "verifier_domain": verifier,
            "subject_digest": subject,
            "epoch_digest": epoch,
            "nonce": f"{i + 1:032x}",
            "artifact_digest": hashlib.sha256(
                ("UNTRUSTED_" + obligation).encode()
            ).hexdigest(),
            "signature_algorithm": "Ed25519",
            # Completely fake bytes, yet a valid base64/length shape.
            "signature_base64": base64.b64encode(
                bytes([i + 1]) * 64
            ).decode("ascii"),
            "observed_at": t,
            "expires_at": t + 120,
            "artifact_locator": "fixture-only:" + obligation,
        })
    return {
        "schema": SCHEMA,
        "subject_digest": subject,
        "epoch_digest": epoch,
        "claims": claims,
    }


def local_a295_self_claims_pack(*, now=None):
    """Structurally populated but explicitly same-host/self-verified claims."""
    pack = synthetic_forged_complete_pack(now=now)
    for claim in pack["claims"]:
        claim["issuer_domain"] = "same_host"
        claim["verifier_domain"] = "same_host"
        claim["verifier_id"] = claim["issuer_id"]
    return pack


def probe_canonical_lab_counterexamples():
    """Execute A292-A295 negative probes to ground the A296 threat matrix."""
    from labs.a292_staged_chat_write_inventory_lab import (
        probe_real_raw_helper_bypasses,
    )
    from labs.a293_host_sqlite_boundary_lab import (
        probe_closed_store_rollback, probe_external_process_write,
    )
    from labs.a294_volatile_witness_sim_lab import (
        probe_witness_reset_and_bootstrap_bypass,
    )
    from labs.a295_dual_local_authority_contract_lab import (
        probe_partial_signer_failure, probe_untrusted_approval_flag,
        probe_same_host_reset_bootstrap,
    )
    helper = probe_real_raw_helper_bypasses()
    external = probe_external_process_write(strict=False)
    rollback = probe_closed_store_rollback()
    reset = probe_witness_reset_and_bootstrap_bypass()
    partial = probe_partial_signer_failure()
    impersonation = probe_untrusted_approval_flag()
    double_reset = probe_same_host_reset_bootstrap()
    negatives = {
        "same_process_raw_commit_bypass": (
            helper["raw_update_helper_changed_title"]
            and helper["pending_commit_marker_absent"]
        ),
        "other_process_raw_sql_commit": (
            external["external_process_sql_changed_title"]
            and not external["guard_rejected_next_read"]
        ),
        "older_host_db_accepted": rollback["older_history_silently_accepted"],
        "witness_reset_rebootstraps_rollback": (
            reset["unsafe_reset_can_reanchor_old_history"]
        ),
        "one_signer_partial_ack_unknown": (
            partial["first_partial_denied"]
            and partial["owner_side_effect_may_have_occurred"]
        ),
        "local_owner_flag_forgery": (
            impersonation["fake_owner_scope_accepted_by_local_flags"]
        ),
        "two_signers_reset_replay_intent": (
            double_reset["same_intent_reaccepted_after_host_reset"]
        ),
    }
    result = _base()
    result.update({
        "negative_findings": negatives,
        "negative_findings_observed": sum(bool(v) for v in negatives.values()),
        "can_authorize_real_effect": False,
        "synthetic_evidence_is_not_canonical_p0_proof": True,
    })
    return result


__all__ = [
    "SCHEMA", "OBLIGATIONS", "PACK_FIELDS", "CLAIM_FIELDS",
    "evaluate_evidence_contract", "synthetic_forged_complete_pack",
    "local_a295_self_claims_pack", "probe_canonical_lab_counterexamples",
]
