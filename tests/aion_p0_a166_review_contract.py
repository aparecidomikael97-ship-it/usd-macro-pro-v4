"""A166 test-only, offline documentary intake for real-custodian acceptance.

ALL references, identifiers, hashes, source channels, timestamps and claims are
caller supplied. Syntactic completeness is NOT independently observed provenance.
No IO, network, provider, secrets, production import, Worker, or GO path.
"""
from __future__ import annotations

import re
from typing import Any

SCHEMA = "AION_P0_A166_EXTERNAL_CUSTODIAN_CANDIDATE_NO_GO_V1"
AUDIENCE = "AION-H0-CUSTODIAN-REVIEW-READONLY"
MAX_FRESHNESS_NS = 20_000_000_000
_ID = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_FOR_KIND = {
    "LEGAL_IDENTITY": "OFFICIAL_REGISTRY_READBACK",
    "ADMIN_CONTROL": "PROVIDER_CONTROL_PLANE",
    "KEY_PROVENANCE": "HSM_POLICY_ATTESTATION",
    "ACCOUNT_SEGREGATION": "PROVIDER_CONTROL_PLANE",
    "WORM_READBACK": "IMMUTABLE_OBJECT_READBACK",
    "REVOCATION_PROPAGATION": "EXTERNAL_REVOCATION_CHALLENGE",
    "ROLLBACK_RESTORE": "INDEPENDENT_RESTORE_DRILL",
    "NONCE_TIME": "TRUSTED_TIME_READBACK",
}
SEPARATED_SOURCES = {
    "ADMIN_CONTROL", "KEY_PROVENANCE", "ACCOUNT_SEGREGATION",
    "WORM_READBACK", "REVOCATION_PROPAGATION", "ROLLBACK_RESTORE",
}
ROLES = ("r1", "r2")
FLOOR_KEYS = frozenset({
    "ledger_id", "epoch", "policy_generation", "policy_digest",
    "challenge_nonce", "observed_ns", "expires_ns", "audience",
})
CUSTODIAN_KEYS = frozenset({
    "role", "organization_id", "administrator_id", "provider_account_id",
    "storage_failure_domain_id", "custody_request_id",
})
RECORD_KEYS = frozenset({
    "role", "kind", "subject_org_id", "source_org_id", "source_record_id",
    "source_channel", "content_sha256", "ledger_id", "epoch",
    "policy_generation", "policy_digest", "challenge_nonce",
    "observed_ns", "expires_ns",
})
OPEN_GATES = (
    "E0_AUTHENTIC_FINANCE", "E1_INDEPENDENT_IAM", "E2_IMMUTABLE_CUSTODY",
    "E3_EXTERNAL_MONOTONIC_HEAD", "E4_RECOVERY_DRILLS",
    "E5_OWNER_AND_CANONICAL_SIGNOFF", "PROVIDER_32_EXTERNAL_PROOFS",
)

class InvalidDossier(ValueError):
    pass

def require(condition: bool, reason: str) -> None:
    if not condition:
        raise InvalidDossier(reason)

def exact_keys(item: Any, keys: frozenset[str], reason: str) -> None:
    require(type(item) is dict and set(item) == keys, reason)

def ident(value: Any, reason: str) -> None:
    require(type(value) is str and _ID.fullmatch(value) is not None, reason)

def hexdigest(value: Any, regex: re.Pattern[str], reason: str) -> None:
    require(type(value) is str and regex.fullmatch(value) is not None, reason)

def timestamp(value: Any, reason: str) -> None:
    require(type(value) is int and 0 < value <= 2**63-1, reason)

def report(reason: str, *, structurally_complete: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "verdict": "LAB_QUARANTINE_MANUAL_REVIEW"
            if structurally_complete else "LAB_HARD_BLOCKED",
        "reason": reason,
        "structural_inventory_complete": structurally_complete,
        "all_evidence_from_independent_sources_authenticated": False,
        "real_custodian_legal_identity_verified": False,
        "separate_administrator_control_verified": False,
        "key_custody_independence_verified": False,
        "provider_account_and_failure_domain_verified": False,
        "immutable_storage_nonrollbackability_verified": False,
        "real_revocation_and_restore_drills_verified": False,
        "freshness_source_externally_trusted": False,
        "real_owner_consent_verified": False,
        "real_provider_effect_or_no_effect_verified": False,
        "worker_allowed": False,
        "checkpoint_restore_allowed": False,
        "external_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_resend_allowed": False,
        "homologated_p0_count": 0,
        "open_gates": OPEN_GATES,
        "historical_provider_proof_obligations": 32,
    }

def assess_candidate_inventory(dossier: Any, *, now_ns: Any) -> dict[str, Any]:
    """Never authenticates a source or grants operational authority.

    This is only a machine-checkable *candidate dossier shape*. Even a
    fully complete fake dossier created by one adversary is quarantined.
    """
    try:
        timestamp(now_ns, "invalid_caller_clock")
        exact_keys(dossier, frozenset({"schema", "floor", "custodians", "records"}),
                   "dossier_schema_or_fields_invalid")
        require(dossier["schema"] == SCHEMA, "wrong_dossier_schema")
        floor = dossier["floor"]
        exact_keys(floor, FLOOR_KEYS, "floor_field_set_invalid")
        ident(floor["ledger_id"], "floor_ledger_invalid")
        hexdigest(floor["epoch"], _HEX32, "floor_epoch_invalid")
        timestamp(floor["policy_generation"], "floor_generation_invalid")
        hexdigest(floor["policy_digest"], _HEX64, "floor_digest_invalid")
        hexdigest(floor["challenge_nonce"], _HEX32, "floor_nonce_invalid")
        require(floor["audience"] == AUDIENCE
                and type(floor["audience"]) is str, "wrong_readonly_audience")
        timestamp(floor["observed_ns"], "floor_observation_invalid")
        timestamp(floor["expires_ns"], "floor_expiration_invalid")
        require(floor["observed_ns"] <= now_ns < floor["expires_ns"]
                and 0 < floor["expires_ns"] - floor["observed_ns"] <= MAX_FRESHNESS_NS,
                "unfresh_or_unbounded_floor")
        people = dossier["custodians"]
        require(type(people) is list and len(people) == 2, "exact_two_custodians_required")
        by_role: dict[str, dict[str, Any]] = {}
        for entry in people:
            exact_keys(entry, CUSTODIAN_KEYS, "custodian_fields_invalid")
            require(entry["role"] in ROLES and type(entry["role"]) is str
                    and entry["role"] not in by_role, "custodian_role_invalid")
            for name in CUSTODIAN_KEYS - {"role"}:
                ident(entry[name], "custodian_" + name + "_invalid")
            by_role[entry["role"]] = entry
        require(set(by_role) == set(ROLES), "custodian_pair_missing_role")
        for name in CUSTODIAN_KEYS - {"role"}:
            require(by_role["r1"][name] != by_role["r2"][name],
                    "claimed_shared_" + name)
        records = dossier["records"]
        require(type(records) is list
                and len(records) == len(ROLES) * len(SOURCE_FOR_KIND),
                "exact_sixteen_kind_records_required")
        seen: set[tuple[str, str]] = set()
        record_ids: set[str] = set()
        source_by_kind: dict[tuple[str, str], str] = {}
        for entry in records:
            exact_keys(entry, RECORD_KEYS, "record_field_set_invalid")
            role = entry["role"]
            kind = entry["kind"]
            require(type(role) is str and role in ROLES, "record_role_invalid")
            require(type(kind) is str and kind in SOURCE_FOR_KIND, "record_kind_invalid")
            pair = (role, kind)
            require(pair not in seen, "duplicate_role_kind")
            seen.add(pair)
            require(type(entry["source_channel"]) is str
                    and entry["source_channel"] == SOURCE_FOR_KIND[kind],
                    "source_channel_not_matching_obligation")
            ident(entry["subject_org_id"], "subject_org_invalid")
            require(entry["subject_org_id"] == by_role[role]["organization_id"],
                    "record_subject_claim_mismatch")
            ident(entry["source_org_id"], "source_org_invalid")
            require(entry["source_org_id"] not in (
                "AION_LOCAL", "SELF", "UNKNOWN", entry["subject_org_id"]),
                "self_attested_or_unknown_source")
            ident(entry["source_record_id"], "source_record_id_invalid")
            require(entry["source_record_id"] not in record_ids,
                    "duplicate_source_record_id")
            record_ids.add(entry["source_record_id"])
            hexdigest(entry["content_sha256"], _HEX64, "content_digest_invalid")
            for name in ("ledger_id", "epoch", "policy_generation",
                         "policy_digest", "challenge_nonce"):
                require(type(entry[name]) is type(floor[name])
                        and entry[name] == floor[name],
                        "record_floor_binding_mismatch:" + name)
            timestamp(entry["observed_ns"], "record_observation_invalid")
            timestamp(entry["expires_ns"], "record_expiry_invalid")
            require(floor["observed_ns"] <= entry["observed_ns"] <= now_ns
                    < entry["expires_ns"] <= floor["expires_ns"],
                    "record_outside_floor_freshness")
            source_by_kind[pair] = entry["source_org_id"]
        require(seen == {(r, k) for r in ROLES for k in SOURCE_FOR_KIND},
                "incomplete_kind_coverage")
        for kind in SEPARATED_SOURCES:
            require(source_by_kind["r1", kind] != source_by_kind["r2", kind],
                    "same_claimed_source_for_both_custodians:" + kind)
        return report("complete_caller_supplied_metadata_not_independent_proof",
                      structurally_complete=True)
    except (InvalidDossier, TypeError, KeyError, AttributeError) as exc:
        return report(str(exc))
    except Exception:
        return report("unavailable_or_unexpected_dossier_review_error")
