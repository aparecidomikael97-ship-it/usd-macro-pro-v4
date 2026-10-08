"""AION Windows Immutable Evidence Store + Verification Receipt Persistence V1.

Design-only persistence contract for future physical Windows probe evidence.

This layer defines:
- canonical append-only evidence record identities;
- a twelve-record hash chain matching the physical probe plan;
- exactly-once/CAS replay semantics;
- immutable verification-receipt persistence requirements;
- read-after-write/reopen evidence requirements;
- structural validation for future persistence attestations.

It does NOT open SQLite, write files, create directories, persist evidence,
issue a verification receipt, execute a verifier, authorize a build, call
GitHub, or mutate a repository.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence

from atlasquant_aion_windows_sandbox_physical_probe_plan_evidence_v1 import (
    PLAN_SCHEMA,
    PROBE_REQUIREMENTS,
    PROBE_SPECS,
    READY_PLAN_STATE,
)
from atlasquant_aion_windows_probe_collector_independent_verifier_contract_v1 import (
    READY_COLLECTOR_STATE,
    READY_VERIFIER_STATE,
    READY_SEPARATION_STATE,
)


SCHEMA = "ATLASQUANT_AION_WINDOWS_IMMUTABLE_EVIDENCE_RECEIPT_PERSISTENCE_V1"
STORE_SCHEMA = "ATLASQUANT_AION_WINDOWS_IMMUTABLE_EVIDENCE_STORE_CONTRACT_V1"
EVIDENCE_RECORD_SCHEMA = "ATLASQUANT_AION_WINDOWS_PHYSICAL_EVIDENCE_APPEND_RECORD_V1"
EVIDENCE_CHAIN_SCHEMA = "ATLASQUANT_AION_WINDOWS_PHYSICAL_EVIDENCE_CHAIN_V1"
RECEIPT_PERSISTENCE_SCHEMA = "ATLASQUANT_AION_WINDOWS_VERIFICATION_RECEIPT_PERSISTENCE_CONTRACT_V1"
PERSISTENCE_ATTESTATION_SCHEMA = "ATLASQUANT_AION_WINDOWS_EVIDENCE_PERSISTENCE_ATTESTATION_CANDIDATE_V1"
REVIEW_SCHEMA = "ATLASQUANT_AION_WINDOWS_EVIDENCE_RECEIPT_PERSISTENCE_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA = "ATLASQUANT_AION_WINDOWS_EVIDENCE_RECEIPT_PERSISTENCE_POLICY_V1"

READY_STORE_STATE = "IMMUTABLE_EVIDENCE_STORE_CONTRACT_READY"
READY_EVIDENCE_STATE = "EVIDENCE_APPEND_RECORD_CANDIDATE_READY"
READY_CHAIN_STATE = "TWELVE_RECORD_EVIDENCE_CHAIN_CANDIDATE_READY_UNTRUSTED"
READY_RECEIPT_PERSISTENCE_STATE = "VERIFICATION_RECEIPT_PERSISTENCE_CONTRACT_READY_UNISSUED"
READY_ATTESTATION_SHAPE_STATE = "PERSISTENCE_ATTESTATION_SHAPE_VALID_BUT_UNTRUSTED"
READY_REVIEW_STATE = "READY_FOR_WINDOWS_EVIDENCE_PERSISTENCE_IMPLEMENTATION"
BLOCKED_STATE = "BLOCKED"

PERSISTENCE_MODE = "APPEND_ONLY_CAS_EXACTLY_ONCE"
RECORD_ENCODING = "UTF8_CANONICAL_JSON"
DIGEST_ALGORITHM = "SHA256"
MAX_EVIDENCE_RECORD_BYTES = 1_048_576
MAX_RECEIPT_RECORD_BYTES = 1_048_576
EXPECTED_RECEIPT_REVISION = 1

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")


class EvidencePersistenceError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _clean(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(value: Any) -> str:
    token = _clean(value, 90)
    return token if _SHA256_RE.fullmatch(token) else ""


def _identity(value: Any, limit: int = 240) -> str:
    if type(value) is not str:
        return ""
    text = _clean(value, limit)
    if text != value or not _ID_RE.fullmatch(text):
        return ""
    return text


def _aware(value: Any, label: str) -> datetime:
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception as exc:
        raise EvidencePersistenceError(label + "_INVALID") from exc
    if dt.tzinfo is None:
        raise EvidencePersistenceError(label + "_TIMEZONE_REQUIRED")
    return dt.astimezone(timezone.utc)


def build_store_contract(
    plan: Mapping[str, Any] | None,
    collector_manifest: Mapping[str, Any] | None,
    verifier_manifest: Mapping[str, Any] | None,
    separation: Mapping[str, Any] | None,
    *,
    store_namespace: Any,
    writer_manifest_digest: Any,
    evidence_store_design_digest: Any,
    receipt_store_design_digest: Any,
) -> dict[str, Any]:
    """Define one append-only namespace for evidence + receipt records."""
    plan_row = dict(plan or {})
    collector = dict(collector_manifest or {})
    verifier = dict(verifier_manifest or {})
    sep = dict(separation or {})
    blockers: list[str] = []

    if plan_row.get("schema") != PLAN_SCHEMA or plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")
    if collector.get("state") != READY_COLLECTOR_STATE:
        blockers.append("READY_COLLECTOR_MANIFEST_REQUIRED")
    if verifier.get("state") != READY_VERIFIER_STATE:
        blockers.append("READY_VERIFIER_MANIFEST_REQUIRED")
    if sep.get("state") != READY_SEPARATION_STATE:
        blockers.append("COLLECTOR_VERIFIER_SEPARATION_REQUIRED")

    namespace = _identity(store_namespace, 180)
    if not namespace:
        blockers.append("STORE_NAMESPACE_REQUIRED")

    writer_digest = _sha256(writer_manifest_digest)
    evidence_design = _sha256(evidence_store_design_digest)
    receipt_design = _sha256(receipt_store_design_digest)
    if not writer_digest:
        blockers.append("WRITER_MANIFEST_DIGEST_REQUIRED")
    if not evidence_design:
        blockers.append("EVIDENCE_STORE_DESIGN_DIGEST_REQUIRED")
    if not receipt_design:
        blockers.append("RECEIPT_STORE_DESIGN_DIGEST_REQUIRED")

    material = {
        "store_namespace": namespace,
        "persistence_mode": PERSISTENCE_MODE,
        "record_encoding": RECORD_ENCODING,
        "digest_algorithm": DIGEST_ALGORITHM,
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "sandbox_preflight_digest": _sha256(plan_row.get("sandbox_preflight_digest")),
        "host_binding_digest": _sha256(plan_row.get("host_binding_digest")),
        "collector_manifest_digest": _sha256(
            collector.get("collector_manifest_digest")
        ),
        "collector_key_fingerprint": _sha256(
            collector.get("collector_key_fingerprint")
        ),
        "verifier_manifest_digest": _sha256(
            verifier.get("verifier_manifest_digest")
        ),
        "verifier_key_fingerprint": _sha256(
            verifier.get("verifier_key_fingerprint")
        ),
        "separation_contract_digest": _sha256(
            sep.get("separation_contract_digest")
        ),
        "writer_manifest_digest": writer_digest,
        "evidence_store_design_digest": evidence_design,
        "receipt_store_design_digest": receipt_design,
        "required_evidence_records": len(PROBE_REQUIREMENTS),
        "receipt_revision": EXPECTED_RECEIPT_REVISION,
    }
    genesis_material = {
        "store_namespace": namespace,
        "probe_plan_digest": material["probe_plan_digest"],
        "host_binding_digest": material["host_binding_digest"],
        "purpose": "EVIDENCE_CHAIN_GENESIS",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": STORE_SCHEMA,
        "state": READY_STORE_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "evidence_chain_genesis_digest": (
            _digest(genesis_material) if not blockers else ""
        ),
        "store_contract_digest": _digest(material) if not blockers else "",
        "append_only_required": True,
        "compare_and_set_required": True,
        "exactly_once_required": True,
        "single_writer_commit_required": True,
        "read_after_write_required": True,
        "reopen_consistency_required": True,
        "delete_allowed": False,
        "replace_allowed": False,
        "truncate_allowed": False,
        "record_reorder_allowed": False,
        "receipt_rewrite_allowed": False,
        "same_identity_same_digest_is_idempotent": True,
        "same_identity_different_digest_is_conflict": True,
        "store_opened": False,
        "database_opened": False,
        "transaction_started": False,
        "cas_attempted": False,
        "record_written": False,
        "receipt_written": False,
        "filesystem_modified": False,
        "physical_persistence_verified": False,
        "build_authorized": False,
    }


def build_evidence_record_candidate(
    store_contract: Mapping[str, Any] | None,
    plan: Mapping[str, Any] | None,
    collector_manifest: Mapping[str, Any] | None,
    *,
    requirement: Any,
    sequence: int,
    measurement_plan_digest: Any,
    raw_evidence_digest: Any,
    evidence_payload_digest: Any,
    collector_binary_digest: Any,
    collector_release_payload_digest: Any,
    collector_signature_evidence_digest: Any,
    observed_value: Any,
    negative_test_observed_value: Any,
    collected_at: Any,
    valid_until: Any,
    previous_record_digest: Any,
    expected_pre_store_revision: int,
) -> dict[str, Any]:
    """Build one immutable evidence-record candidate; persist nothing."""
    store = dict(store_contract or {})
    plan_row = dict(plan or {})
    collector = dict(collector_manifest or {})
    blockers: list[str] = []

    if store.get("state") != READY_STORE_STATE:
        blockers.append("READY_STORE_CONTRACT_REQUIRED")
    if plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")
    if collector.get("state") != READY_COLLECTOR_STATE:
        blockers.append("READY_COLLECTOR_MANIFEST_REQUIRED")

    req = _clean(requirement, 140)
    if req not in PROBE_REQUIREMENTS:
        blockers.append("UNKNOWN_PHYSICAL_PROBE_REQUIREMENT")
        expected_sequence = 0
        spec = None
        measurement = None
    else:
        expected_sequence = PROBE_REQUIREMENTS.index(req) + 1
        spec = PROBE_SPECS[req]
        measurement = next(
            (
                row
                for row in plan_row.get("measurements", [])
                if isinstance(row, Mapping) and row.get("requirement") == req
            ),
            None,
        )
    try:
        seq = int(sequence)
    except Exception:
        seq = 0
    if seq != expected_sequence:
        blockers.append("EVIDENCE_SEQUENCE_MISMATCH")

    measurement_digest = _sha256(measurement_plan_digest)
    if measurement is None:
        blockers.append("MEASUREMENT_PLAN_NOT_FOUND")
    elif measurement_digest != _sha256(measurement.get("measurement_plan_digest")):
        blockers.append("MEASUREMENT_PLAN_DIGEST_MISMATCH")

    raw_digest = _sha256(raw_evidence_digest)
    payload_digest = _sha256(evidence_payload_digest)
    collector_binary = _sha256(collector_binary_digest)
    collector_release = _sha256(collector_release_payload_digest)
    collector_signature = _sha256(collector_signature_evidence_digest)
    for label, value in (
        ("RAW_EVIDENCE_DIGEST_REQUIRED", raw_digest),
        ("EVIDENCE_PAYLOAD_DIGEST_REQUIRED", payload_digest),
        ("COLLECTOR_BINARY_DIGEST_REQUIRED", collector_binary),
        ("COLLECTOR_RELEASE_PAYLOAD_DIGEST_REQUIRED", collector_release),
        ("COLLECTOR_SIGNATURE_EVIDENCE_DIGEST_REQUIRED", collector_signature),
    ):
        if not value:
            blockers.append(label)
    if collector_binary and collector_binary != _sha256(
        collector.get("collector_binary_digest")
    ):
        blockers.append("COLLECTOR_BINARY_DIGEST_MISMATCH")

    try:
        collected = _aware(collected_at, "EVIDENCE_COLLECTED_AT")
        expires = _aware(valid_until, "EVIDENCE_VALID_UNTIL")
        if expires <= collected:
            blockers.append("EVIDENCE_VALIDITY_WINDOW_INVALID")
        if spec is not None and (
            expires - collected
        ).total_seconds() > int(spec["freshness_seconds"]):
            blockers.append("EVIDENCE_VALIDITY_WINDOW_TOO_LONG")
    except EvidencePersistenceError as exc:
        collected = None
        expires = None
        blockers.append(exc.code)

    if spec is not None:
        if observed_value != spec["expected_observation"]:
            blockers.append("EXPECTED_OBSERVATION_NOT_MET")
        if negative_test_observed_value != spec["negative_test"]:
            blockers.append("NEGATIVE_TEST_OBSERVATION_NOT_MET")

    try:
        pre_revision = int(expected_pre_store_revision)
    except Exception:
        pre_revision = -1
    if pre_revision != seq - 1:
        blockers.append("EXPECTED_PRE_STORE_REVISION_MISMATCH")

    previous = _sha256(previous_record_digest)
    if seq == 1:
        if previous != _sha256(store.get("evidence_chain_genesis_digest")):
            blockers.append("EVIDENCE_GENESIS_BINDING_MISMATCH")
    elif not previous:
        blockers.append("PREVIOUS_EVIDENCE_RECORD_DIGEST_REQUIRED")

    identity_material = {
        "store_namespace": store.get("store_namespace"),
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "host_binding_digest": _sha256(plan_row.get("host_binding_digest")),
        "requirement": req,
        "sequence": seq,
    }
    record_key = _digest(identity_material)
    material = {
        **identity_material,
        "record_key": record_key,
        "store_contract_digest": _sha256(store.get("store_contract_digest")),
        "sandbox_preflight_digest": _sha256(plan_row.get("sandbox_preflight_digest")),
        "measurement_plan_digest": measurement_digest,
        "collector_manifest_digest": _sha256(
            collector.get("collector_manifest_digest")
        ),
        "collector_binary_digest": collector_binary,
        "collector_release_payload_digest": collector_release,
        "collector_signature_evidence_digest": collector_signature,
        "raw_evidence_digest": raw_digest,
        "evidence_payload_digest": payload_digest,
        "observed_value": observed_value,
        "negative_test_observed_value": negative_test_observed_value,
        "collected_at": collected.isoformat() if collected else "",
        "valid_until": expires.isoformat() if expires else "",
        "previous_record_digest": previous,
        "expected_pre_store_revision": pre_revision,
        "committed_store_revision_if_written": seq,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": EVIDENCE_RECORD_SCHEMA,
        "state": READY_EVIDENCE_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "evidence_record_digest": _digest(material) if not blockers else "",
        "append_only": True,
        "immutable": True,
        "delete_allowed": False,
        "replace_allowed": False,
        "physical_evidence_verified_by_this_module": False,
        "record_persisted": False,
        "cas_attempted": False,
        "read_after_write_verified": False,
        "reopen_verified": False,
        "build_authorized": False,
    }


def build_evidence_chain_candidate(
    store_contract: Mapping[str, Any] | None,
    records: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Validate exact canonical order and digest linkage for all twelve records."""
    store = dict(store_contract or {})
    rows = [dict(row) for row in (records or []) if isinstance(row, Mapping)]
    blockers: list[str] = []

    if store.get("state") != READY_STORE_STATE:
        blockers.append("READY_STORE_CONTRACT_REQUIRED")
    if len(rows) != len(PROBE_REQUIREMENTS):
        blockers.append("EXACT_TWELVE_EVIDENCE_RECORDS_REQUIRED")

    expected_previous = _sha256(store.get("evidence_chain_genesis_digest"))
    record_keys: list[str] = []
    record_digests: list[str] = []
    canonical_rows: list[dict[str, Any]] = []

    for expected_sequence, requirement in enumerate(PROBE_REQUIREMENTS, start=1):
        row = rows[expected_sequence - 1] if len(rows) >= expected_sequence else {}
        if row.get("state") != READY_EVIDENCE_STATE:
            blockers.append(
                "READY_EVIDENCE_RECORD_REQUIRED:" + str(expected_sequence)
            )
            continue
        if row.get("requirement") != requirement:
            blockers.append(
                "EVIDENCE_REQUIREMENT_ORDER_MISMATCH:" + str(expected_sequence)
            )
        if int(row.get("sequence") or 0) != expected_sequence:
            blockers.append(
                "EVIDENCE_SEQUENCE_ORDER_MISMATCH:" + str(expected_sequence)
            )
        if _sha256(row.get("store_contract_digest")) != _sha256(
            store.get("store_contract_digest")
        ):
            blockers.append(
                "EVIDENCE_STORE_BINDING_MISMATCH:" + str(expected_sequence)
            )
        if _sha256(row.get("previous_record_digest")) != expected_previous:
            blockers.append(
                "EVIDENCE_CHAIN_LINK_MISMATCH:" + str(expected_sequence)
            )
        digest = _sha256(row.get("evidence_record_digest"))
        key = _sha256(row.get("record_key"))
        if not digest:
            blockers.append(
                "EVIDENCE_RECORD_DIGEST_REQUIRED:" + str(expected_sequence)
            )
        if not key:
            blockers.append(
                "EVIDENCE_RECORD_KEY_REQUIRED:" + str(expected_sequence)
            )
        record_digests.append(digest)
        record_keys.append(key)
        canonical_rows.append(
            {
                "sequence": expected_sequence,
                "requirement": requirement,
                "record_key": key,
                "evidence_record_digest": digest,
            }
        )
        expected_previous = digest

    if len(set(record_keys)) != len(record_keys):
        blockers.append("DUPLICATE_EVIDENCE_RECORD_KEY")
    if len(set(record_digests)) != len(record_digests):
        blockers.append("DUPLICATE_EVIDENCE_RECORD_DIGEST")

    material = {
        "store_contract_digest": _sha256(store.get("store_contract_digest")),
        "genesis_digest": _sha256(store.get("evidence_chain_genesis_digest")),
        "records": canonical_rows,
        "chain_head_digest": expected_previous,
        "record_count": len(canonical_rows),
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": EVIDENCE_CHAIN_SCHEMA,
        "state": READY_CHAIN_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "evidence_chain_digest": _digest(material) if not blockers else "",
        "physical_proof_verified": False,
        "records_persisted": False,
        "chain_reopened_verified": False,
        "build_authorized": False,
    }


def classify_append_replay(
    existing_record: Mapping[str, Any] | None,
    candidate_record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Classify exactly-once append replay without writing anything."""
    existing = dict(existing_record or {})
    candidate = dict(candidate_record or {})
    existing_key = _sha256(existing.get("record_key"))
    candidate_key = _sha256(candidate.get("record_key"))
    existing_digest = _sha256(existing.get("evidence_record_digest"))
    candidate_digest = _sha256(candidate.get("evidence_record_digest"))

    if not all((existing_key, candidate_key, existing_digest, candidate_digest)):
        return {
            "state": BLOCKED_STATE,
            "classification": "INVALID_RECORD_IDENTITY",
            "append_allowed": False,
            "idempotent_replay": False,
            "conflict": True,
        }
    if existing_key != candidate_key:
        return {
            "state": "DISTINCT_RECORD_IDENTITY",
            "classification": "NEW_RECORD_IDENTITY",
            "append_allowed": True,
            "idempotent_replay": False,
            "conflict": False,
        }
    if existing_digest == candidate_digest:
        return {
            "state": "IDEMPOTENT_REPLAY",
            "classification": "SAME_IDENTITY_SAME_DIGEST",
            "append_allowed": False,
            "idempotent_replay": True,
            "conflict": False,
        }
    return {
        "state": BLOCKED_STATE,
        "classification": "SAME_IDENTITY_DIFFERENT_DIGEST_CONFLICT",
        "append_allowed": False,
        "idempotent_replay": False,
        "conflict": True,
    }


def build_receipt_persistence_contract(
    store_contract: Mapping[str, Any] | None,
    evidence_chain: Mapping[str, Any] | None,
    plan: Mapping[str, Any] | None,
    verifier_manifest: Mapping[str, Any] | None,
    separation: Mapping[str, Any] | None,
    receipt_template: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Define immutable receipt persistence, while receipt remains unissued."""
    store = dict(store_contract or {})
    chain = dict(evidence_chain or {})
    plan_row = dict(plan or {})
    verifier = dict(verifier_manifest or {})
    sep = dict(separation or {})
    template = dict(receipt_template or {})
    blockers: list[str] = []

    if store.get("state") != READY_STORE_STATE:
        blockers.append("READY_STORE_CONTRACT_REQUIRED")
    if chain.get("state") != READY_CHAIN_STATE:
        blockers.append("READY_EVIDENCE_CHAIN_CANDIDATE_REQUIRED")
    if plan_row.get("state") != READY_PLAN_STATE:
        blockers.append("READY_PROBE_PLAN_REQUIRED")
    if verifier.get("state") != READY_VERIFIER_STATE:
        blockers.append("READY_VERIFIER_MANIFEST_REQUIRED")
    if sep.get("state") != READY_SEPARATION_STATE:
        blockers.append("COLLECTOR_VERIFIER_SEPARATION_REQUIRED")
    if template.get("state") != "VERIFICATION_RECEIPT_TEMPLATE_READY_UNISSUED":
        blockers.append("UNISSUED_RECEIPT_TEMPLATE_REQUIRED")
    if template.get("receipt_issued") is not False:
        blockers.append("RECEIPT_MUST_REMAIN_UNISSUED")
    if int(template.get("verified_total") or 0) != 0:
        blockers.append("UNISSUED_RECEIPT_VERIFIED_TOTAL_MUST_BE_ZERO")

    receipt_identity_material = {
        "store_namespace": store.get("store_namespace"),
        "probe_plan_digest": _sha256(plan_row.get("probe_plan_digest")),
        "host_binding_digest": _sha256(plan_row.get("host_binding_digest")),
        "verifier_manifest_digest": _sha256(
            verifier.get("verifier_manifest_digest")
        ),
        "receipt_revision": EXPECTED_RECEIPT_REVISION,
    }
    material = {
        **receipt_identity_material,
        "receipt_record_key": _digest(receipt_identity_material),
        "store_contract_digest": _sha256(store.get("store_contract_digest")),
        "evidence_chain_digest": _sha256(chain.get("evidence_chain_digest")),
        "evidence_chain_head_digest": _sha256(chain.get("chain_head_digest")),
        "receipt_template_digest": _sha256(template.get("receipt_template_digest")),
        "separation_contract_digest": _sha256(
            sep.get("separation_contract_digest")
        ),
        "expected_pre_receipt_store_revision": len(PROBE_REQUIREMENTS),
        "committed_receipt_store_revision_if_written":
            len(PROBE_REQUIREMENTS) + 1,
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": RECEIPT_PERSISTENCE_SCHEMA,
        "state": READY_RECEIPT_PERSISTENCE_STATE
        if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "receipt_persistence_contract_digest": (
            _digest(material) if not blockers else ""
        ),
        "receipt_append_only": True,
        "receipt_immutable": True,
        "receipt_exactly_once": True,
        "receipt_compare_and_set_required": True,
        "receipt_read_after_write_required": True,
        "receipt_reopen_consistency_required": True,
        "receipt_delete_allowed": False,
        "receipt_replace_allowed": False,
        "receipt_rewrite_allowed": False,
        "receipt_revision_increment_allowed": False,
        "evidence_chain_mutation_after_receipt_allowed": False,
        "receipt_issued": False,
        "receipt_signed": False,
        "receipt_persisted": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
    }


def validate_future_persistence_attestation_shape(
    store_contract: Mapping[str, Any] | None,
    *,
    record_kind: Any,
    record_key: Any,
    record_digest: Any,
    expected_pre_store_revision: int,
    committed_store_revision: int,
    writer_manifest_digest: Any,
    write_receipt_digest: Any,
    cas_observation_digest: Any,
    read_after_write_observation_digest: Any,
    reopen_observation_digest: Any,
    persisted_at: Any,
    caller_claims_persistence_verified: bool = False,
) -> dict[str, Any]:
    """Validate future persistence evidence shape without trusting it."""
    store = dict(store_contract or {})
    blockers: list[str] = []

    if store.get("state") != READY_STORE_STATE:
        blockers.append("READY_STORE_CONTRACT_REQUIRED")

    kind = _clean(record_kind, 40).upper()
    if kind not in ("EVIDENCE", "VERIFICATION_RECEIPT"):
        blockers.append("PERSISTENCE_RECORD_KIND_INVALID")

    key = _sha256(record_key)
    digest = _sha256(record_digest)
    writer = _sha256(writer_manifest_digest)
    write_receipt = _sha256(write_receipt_digest)
    cas_digest = _sha256(cas_observation_digest)
    readback = _sha256(read_after_write_observation_digest)
    reopen = _sha256(reopen_observation_digest)
    for label, value in (
        ("PERSISTENCE_RECORD_KEY_REQUIRED", key),
        ("PERSISTENCE_RECORD_DIGEST_REQUIRED", digest),
        ("WRITER_MANIFEST_DIGEST_REQUIRED", writer),
        ("WRITE_RECEIPT_DIGEST_REQUIRED", write_receipt),
        ("CAS_OBSERVATION_DIGEST_REQUIRED", cas_digest),
        ("READ_AFTER_WRITE_OBSERVATION_DIGEST_REQUIRED", readback),
        ("REOPEN_OBSERVATION_DIGEST_REQUIRED", reopen),
    ):
        if not value:
            blockers.append(label)

    if writer and writer != _sha256(store.get("writer_manifest_digest")):
        blockers.append("WRITER_MANIFEST_DIGEST_MISMATCH")

    try:
        pre = int(expected_pre_store_revision)
        committed = int(committed_store_revision)
        if pre < 0 or committed != pre + 1:
            blockers.append("STORE_REVISION_TRANSITION_INVALID")
    except Exception:
        pre = -1
        committed = -1
        blockers.append("STORE_REVISION_INVALID")

    try:
        persisted = _aware(persisted_at, "PERSISTED_AT")
    except EvidencePersistenceError as exc:
        persisted = None
        blockers.append(exc.code)

    if caller_claims_persistence_verified is True:
        blockers.append("CALLER_PERSISTENCE_VERIFICATION_CLAIM_NOT_TRUSTED")

    material = {
        "store_contract_digest": _sha256(store.get("store_contract_digest")),
        "record_kind": kind,
        "record_key": key,
        "record_digest": digest,
        "expected_pre_store_revision": pre,
        "committed_store_revision": committed,
        "writer_manifest_digest": writer,
        "write_receipt_digest": write_receipt,
        "cas_observation_digest": cas_digest,
        "read_after_write_observation_digest": readback,
        "reopen_observation_digest": reopen,
        "persisted_at": persisted.isoformat() if persisted else "",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": PERSISTENCE_ATTESTATION_SCHEMA,
        "state": READY_ATTESTATION_SHAPE_STATE
        if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "persistence_attestation_candidate_digest": (
            _digest(material) if not blockers else ""
        ),
        "shape_valid": not blockers,
        "physical_persistence_verified": False,
        "cas_verified": False,
        "read_after_write_verified": False,
        "reopen_verified": False,
        "record_persisted_trusted": False,
        "build_authorized": False,
    }


def build_implementation_review(
    store_contract: Mapping[str, Any] | None,
    receipt_persistence_contract: Mapping[str, Any] | None,
    *,
    writer_source_digest: Any,
    writer_test_digest: Any,
    reopen_verifier_design_digest: Any,
    crash_recovery_design_digest: Any,
) -> dict[str, Any]:
    store = dict(store_contract or {})
    receipt = dict(receipt_persistence_contract or {})
    blockers: list[str] = []

    if store.get("state") != READY_STORE_STATE:
        blockers.append("READY_STORE_CONTRACT_REQUIRED")
    if receipt.get("state") != READY_RECEIPT_PERSISTENCE_STATE:
        blockers.append("READY_RECEIPT_PERSISTENCE_CONTRACT_REQUIRED")

    digests = {}
    for key, value, label in (
        ("writer_source_digest", writer_source_digest, "WRITER_SOURCE_DIGEST_REQUIRED"),
        ("writer_test_digest", writer_test_digest, "WRITER_TEST_DIGEST_REQUIRED"),
        (
            "reopen_verifier_design_digest",
            reopen_verifier_design_digest,
            "REOPEN_VERIFIER_DESIGN_DIGEST_REQUIRED",
        ),
        (
            "crash_recovery_design_digest",
            crash_recovery_design_digest,
            "CRASH_RECOVERY_DESIGN_DIGEST_REQUIRED",
        ),
    ):
        digest = _sha256(value)
        digests[key] = digest
        if not digest:
            blockers.append(label)

    material = {
        "store_contract_digest": _sha256(store.get("store_contract_digest")),
        "receipt_persistence_contract_digest": _sha256(
            receipt.get("receipt_persistence_contract_digest")
        ),
        **digests,
        "next_pc_phase":
            "IMPLEMENT_APPEND_ONLY_EVIDENCE_WRITER_AND_REOPEN_VERIFIER_WITH_SYNTHETIC_DATA",
    }
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": REVIEW_SCHEMA,
        "state": READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers": blockers,
        **material,
        "implementation_review_digest": _digest(material) if not blockers else "",
        "writer_implemented": False,
        "writer_executed": False,
        "database_opened": False,
        "evidence_persisted": False,
        "verification_receipt_persisted": False,
        "read_after_write_verified": False,
        "reopen_verified": False,
        "crash_recovery_verified": False,
        "physical_persistence_verified": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
    }


def evidence_persistence_policy() -> dict[str, Any]:
    return {
        "schema": POLICY_SCHEMA,
        "persistence_mode": PERSISTENCE_MODE,
        "record_encoding": RECORD_ENCODING,
        "digest_algorithm": DIGEST_ALGORITHM,
        "required_evidence_records": len(PROBE_REQUIREMENTS),
        "receipt_revision": EXPECTED_RECEIPT_REVISION,
        "append_only_required": True,
        "compare_and_set_required": True,
        "exactly_once_required": True,
        "single_writer_commit_required": True,
        "read_after_write_required": True,
        "reopen_consistency_required": True,
        "same_identity_same_digest_is_idempotent": True,
        "same_identity_different_digest_is_conflict": True,
        "evidence_delete_allowed": False,
        "evidence_replace_allowed": False,
        "evidence_reorder_allowed": False,
        "chain_truncate_allowed": False,
        "receipt_delete_allowed": False,
        "receipt_replace_allowed": False,
        "receipt_rewrite_allowed": False,
        "receipt_revision_increment_allowed": False,
        "evidence_chain_mutation_after_receipt_allowed": False,
        "caller_persistence_verification_is_authority": False,
        "document_digest_is_persistence_proof": False,
        "store_opened": False,
        "database_opened": False,
        "transaction_started": False,
        "cas_attempted": False,
        "cas_succeeded": False,
        "writer_implemented": False,
        "writer_executed": False,
        "record_written": False,
        "evidence_persisted": False,
        "verification_receipt_issued": False,
        "verification_receipt_signed": False,
        "verification_receipt_persisted": False,
        "read_after_write_verified": False,
        "reopen_verified": False,
        "crash_recovery_verified": False,
        "physical_persistence_verified": False,
        "physical_proof_verified": False,
        "windows_sandbox_verified": False,
        "build_authorized": False,
        "build_started": False,
        "package_built": False,
        "package_installed": False,
        "process_spawned": False,
        "filesystem_modified": False,
        "network_called": False,
        "github_api_called": False,
        "live_repository_mutation_authorized": False,
        "live_repository_mutation_performed": False,
        "production_repository_mutation_performed": False,
        "deploy_executed": False,
        "worker_activated": False,
        "provider_activated": False,
        "production_persistence_activated": False,
    }


__all__ = [
    "SCHEMA",
    "STORE_SCHEMA",
    "EVIDENCE_RECORD_SCHEMA",
    "EVIDENCE_CHAIN_SCHEMA",
    "RECEIPT_PERSISTENCE_SCHEMA",
    "PERSISTENCE_ATTESTATION_SCHEMA",
    "REVIEW_SCHEMA",
    "POLICY_SCHEMA",
    "READY_STORE_STATE",
    "READY_EVIDENCE_STATE",
    "READY_CHAIN_STATE",
    "READY_RECEIPT_PERSISTENCE_STATE",
    "READY_ATTESTATION_SHAPE_STATE",
    "READY_REVIEW_STATE",
    "BLOCKED_STATE",
    "PERSISTENCE_MODE",
    "RECORD_ENCODING",
    "DIGEST_ALGORITHM",
    "EvidencePersistenceError",
    "build_store_contract",
    "build_evidence_record_candidate",
    "build_evidence_chain_candidate",
    "classify_append_replay",
    "build_receipt_persistence_contract",
    "validate_future_persistence_attestation_shape",
    "build_implementation_review",
    "evidence_persistence_policy",
]
