"""AION Windows synthetic terminal store and reboot verification harness V1.

Test-only, in-memory simulation. No durable device storage, Windows API,
OS reads, process execution, reboot, privilege, deployment or live trust grant.

The word "reopen" below means a deep-copied *memory snapshot*, NEVER a real
fresh disk read. Independently constructed evidence is NOT attested evidence.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from atlasquant_aion_windows_terminal_receipt_persistence_postreboot_health_v1 import (
    ATTEST_READY, BLOCKED, HEALTHY, INTENT_FIELDS, INTENT_READY,
    REBOOT_CHECKS, REBOOT_READY, UNKNOWN,
    _digest, _sha,
    build_postreboot_verification_plan,
    classify_postreboot_health_evidence,
    validate_terminal_persistence_attestation_shape,
)

SCHEMA = "ATLASQUANT_AION_WINDOWS_SYNTHETIC_STORE_REBOOT_HARNESS_V1"
READY = "READY_FOR_WINDOWS_SYNTHETIC_HARNESS_SECURITY_REVIEW"
STORE_COMMITTED = "SYNTHETIC_CAS_COMMITTED_UNTRUSTED"
STORE_UNKNOWN = "SYNTHETIC_CAS_OUTCOME_UNKNOWN"
STORE_REJECTED = "SYNTHETIC_CAS_REJECTED_NO_MUTATION"
REOPEN_ONLY = "SYNTHETIC_REOPEN_INSPECTION_ONLY"
SIMULATOR_POLICY = {
    "schema": SCHEMA,
    "test_only": True,
    "physical_durable_store_used": False,
    "physical_windows_reads_used": False,
    "real_windows_reboot_performed": False,
    "trusted_witness_generated": False,
    "write_ahead_install_commitment_executed": False,
    "owner_authorization_consumed": False,
    "install_token_consumed": False,
    "journal_persisted": False,
    "terminal_receipt_persisted": False,
    "files_copied": False,
    "acl_changed": False,
    "startup_changed": False,
    "aion_started": False,
    "package_installed": False,
    "rollback_executed": False,
    "network_called": False,
    "github_api_called": False,
    "deploy_executed": False,
    "worker_activated": False,
    "automatic_retry_on_unknown": False,
    "automatic_reinstall_on_unhealthy": False,
}

def _result(state: str, reason: str, *, record_digest: str = "") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "record_digest": record_digest,
        "synthetic_only": True,
        "physical_write_performed": False,
        "trusted_persistence_certificate": False,
        "automatic_retry_allowed": False,
        "new_install_authorized": False,
    }

def _valid_intent(intent: Mapping[str, Any]) -> bool:
    if intent.get("state") != INTENT_READY:
        return False
    if _sha(intent.get("write_intent_digest")) != _digest({
        k: intent.get(k) for k in INTENT_FIELDS
    }):
        return False
    return bool(
        _sha(intent.get("terminal_candidate_digest"))
        and _sha(intent.get("journal_plan_digest"))
        and _sha(intent.get("write_nonce_digest"))
        and _sha(intent.get("record_key_digest"))
        and intent.get("expected_terminal_state") == "NONE"
        and type(intent.get("expected_revision")) is int
        and intent["expected_revision"] >= 0
        and type(intent.get("next_revision_if_written")) is int
        and intent["next_revision_if_written"] == intent["expected_revision"] + 1
        and intent.get("committed_terminal_state_if_written") == intent.get("terminal_outcome")
    )

class SyntheticCASStore:
    """Deterministic one-shot CAS state machine with in-memory fault injection.

    It is intentionally NOT a durable storage implementation. No filesystem or
    database is touched. No disk persistence is promised by the word 'reopen'.
    """
    def __init__(self, store_identity_digest: str, *, initial_revision: int = 0):
        if not _sha(store_identity_digest) or type(initial_revision) is not int or initial_revision < 0:
            raise ValueError("synthetic store id/revision invalid")
        self.identity = store_identity_digest
        self.revision = initial_revision
        self._records: dict[str, dict[str, Any]] = {}
        self._uncertain_install_ids: set[str] = set()

    def snapshot(self) -> dict[str, Any]:
        return deepcopy({
            "schema": SCHEMA,
            "store_identity_digest": self.identity,
            "revision": self.revision,
            "records": self._records,
            "unknown_install_ids": sorted(self._uncertain_install_ids),
        })

    def simulated_reopen(self) -> "SyntheticCASStore":
        """Clone in memory: does NOT simulate disk power-loss durability."""
        store = SyntheticCASStore(self.identity, initial_revision=self.revision)
        store._records = deepcopy(self._records)
        store._uncertain_install_ids = set(self._uncertain_install_ids)
        return store

    def read(self, installation_id: str) -> dict[str, Any] | None:
        return deepcopy(self._records.get(installation_id))

    def apply(self, intent: Mapping[str, Any], *, fault: str = "none") -> dict[str, Any]:
        if fault not in ("none", "before_commit", "after_commit_unknown"):
            return _result(STORE_REJECTED, "UNKNOWN_FAULT_MODE")
        if not _valid_intent(intent):
            return _result(STORE_REJECTED, "INVALID_OR_TAMPERED_WRITE_INTENT")
        if intent.get("durable_store_identity_digest") != self.identity:
            return _result(STORE_REJECTED, "WRONG_STORE_IDENTITY")
        install_id = intent["installation_id"]
        if not isinstance(install_id, str) or not install_id:
            return _result(STORE_REJECTED, "INSTALLATION_ID_REQUIRED")
        if install_id in self._uncertain_install_ids:
            return _result(STORE_REJECTED, "UNKNOWN_WRITE_REQUIRES_SEPARATE_RECONCILIATION")
        if install_id in self._records:
            return _result(STORE_REJECTED, "TERMINAL_RECORD_ALREADY_EXISTS_READ_ONLY")
        if intent["expected_revision"] != self.revision:
            return _result(STORE_REJECTED, "STALE_COMPARE_AND_SET_REVISION")
        if fault == "before_commit":
            return _result(STORE_REJECTED, "INJECTED_CONFIRMED_NO_WRITE")
        record = {
            "installation_id": install_id,
            "store_identity_digest": self.identity,
            "record_key_digest": intent["record_key_digest"],
            "write_intent_digest": intent["write_intent_digest"],
            "terminal_candidate_digest": intent["terminal_candidate_digest"],
            "terminal_outcome": intent["terminal_outcome"],
            "journal_plan_digest": intent["journal_plan_digest"],
            "owner_sid_digest": intent["owner_sid_digest"],
            "host_identity_digest": intent["host_identity_digest"],
            "package_manifest_digest": intent["package_manifest_digest"],
            "target_snapshot_digest": intent["target_snapshot_digest"],
            "write_nonce_digest": intent["write_nonce_digest"],
            "prior_state": "NONE",
            "prior_revision": self.revision,
            "terminal_state": intent["committed_terminal_state_if_written"],
            "revision": intent["next_revision_if_written"],
        }
        self._records[install_id] = deepcopy(record)
        self.revision += 1
        if fault == "after_commit_unknown":
            self._uncertain_install_ids.add(install_id)
            return _result(STORE_UNKNOWN, "INJECTED_ACK_LOSS_POSSIBLE_WRITE")
        return _result(STORE_COMMITTED, "SYNTHETIC_COMPARE_AND_SET_APPLIED",
                       record_digest=_digest(record))

    def reconcile_snapshot(self, installation_id: str) -> dict[str, Any]:
        """Inspect without granting retry/reinstall authority or clearing UNKNOWN."""
        record = self.simulated_reopen().read(installation_id)
        out = _result(REOPEN_ONLY, "MEMORY_CLONE_RECONCILIATION_ONLY",
                      record_digest=_digest(record) if record else "")
        out["record_present_in_simulated_clone"] = record is not None
        out["ack_uncertain"] = installation_id in self._uncertain_install_ids
        return out

def synthetic_persistence_shape(
    store: SyntheticCASStore,
    intent: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    verifier_manifest_digest: str,
) -> dict[str, Any]:
    """Exercise upstream envelope; do not grant trust or process ambiguous commits."""
    if result.get("state") != STORE_COMMITTED:
        return {"state": BLOCKED, "blockers": ["POSITIVE_SYNTHETIC_CAS_RESULT_REQUIRED"],
                "terminal_receipt_persisted_trusted": False}
    if not _sha(verifier_manifest_digest) or store.identity != intent.get("durable_store_identity_digest"):
        return {"state": BLOCKED, "blockers": ["VERIFIER_OR_STORE_BINDING_INVALID"],
                "terminal_receipt_persisted_trusted": False}
    record = store.simulated_reopen().read(intent.get("installation_id"))
    if not record or _digest(record) != result.get("record_digest"):
        return {"state": BLOCKED, "blockers": ["SYNTHETIC_REOPEN_RECORD_MISMATCH"],
                "terminal_receipt_persisted_trusted": False}
    receipts = {
        "observed_record_digest": _digest(record),
        "cas_write_receipt_digest": _digest({
            "synthetic": True, "intent": intent["write_intent_digest"], "record": record,
        }),
        "cas_observation_digest": _digest({
            "synthetic": True, "prior": record["prior_revision"], "after": record["revision"],
        }),
        "read_after_write_digest": _digest({"synthetic": True, "record": store.read(record["installation_id"])}),
        "independent_reopen_digest": _digest({"synthetic_memory_clone": True, "record": record}),
        "independent_verifier_manifest_digest": verifier_manifest_digest,
        "observed_prior_state": record["prior_state"],
        "observed_prior_revision": record["prior_revision"],
        "observed_terminal_state": record["terminal_state"],
        "observed_revision": record["revision"],
        "observed_installation_id": record["installation_id"],
        "observed_record_key_digest": record["record_key_digest"],
        "observed_terminal_candidate_digest": record["terminal_candidate_digest"],
        "observed_owner_sid_digest": record["owner_sid_digest"],
        "observed_host_identity_digest": record["host_identity_digest"],
        "observed_terminal_outcome": record["terminal_outcome"],
        "write_attempt_nonce_digest": record["write_nonce_digest"],
    }
    shape = validate_terminal_persistence_attestation_shape(intent, **receipts)
    shape["synthetic_only"] = True
    shape["physical_persistence_verified"] = False
    return shape

def _evaluate_reboot_check(
    name: str, plan: Mapping[str, Any], snapshot: Mapping[str, Any],
    terminal_record: Mapping[str, Any] | None, postboot_epoch: str,
) -> bool | None:
    """Only fixture comparisons; booleans never reflect physical OS measurements."""
    p = plan
    s = snapshot
    def matches(*fields: str) -> bool | None:
        if any(field not in s for field in fields):
            return None
        return all(s[field] == p.get(field) for field in fields)
    if name == "TERMINAL_RECEIPT_FRESH_REOPEN":
        if not terminal_record:
            return None
        return bool(
            terminal_record.get("terminal_candidate_digest") == p.get("terminal_candidate_digest")
            and terminal_record.get("installation_id") == p.get("installation_id")
            and terminal_record.get("journal_plan_digest") == p.get("journal_plan_digest")
            and terminal_record.get("owner_sid_digest") == p.get("owner_sid_digest")
            and terminal_record.get("host_identity_digest") == p.get("host_identity_digest")
            and terminal_record.get("record_key_digest") == s.get("terminal_record_key_digest")
        )
    if name == "INSTALL_COMMITMENT_AND_JOURNAL_REOPEN":
        match = matches("journal_plan_digest")
        if match is None or "journal_chain_valid" not in s:
            return None
        return bool(match and s["journal_chain_valid"] is True)
    if name == "HOST_AND_OWNER_SID_MATCH":
        return matches("host_identity_digest", "owner_sid_digest")
    if name == "BOOT_EPOCH_PROVES_REBOOT":
        if not postboot_epoch:
            return None
        return postboot_epoch != p.get("preboot_epoch_digest")
    if name == "PACKAGE_AND_TARGET_FILES_READBACK":
        return matches("package_manifest_digest", "target_snapshot_digest")
    if name == "OWNER_EFFECTIVE_ACL_REOPEN":
        return matches("owner_acl_policy_digest")
    if name == "STARTUP_ENTRY_TARGET_READBACK":
        return matches("startup_policy_digest")
    if name == "AION_PROCESS_BINARY_AND_VERSION_MATCH":
        return matches("runtime_identity_policy_digest")
    if name == "AION_RUNTIME_HANDSHAKE_HEALTH":
        m = matches("runtime_health_policy_digest")
        if m is None or "runtime_handshake_ok" not in s:
            return None
        return bool(m and s["runtime_handshake_ok"] is True)
    if name == "NO_UNEXPECTED_MUTATION":
        if "unexpected_mutation" not in s:
            return None
        return s["unexpected_mutation"] is False
    if name == "FRESH_CHALLENGE_ATTESTATION":
        if "challenge_response_digest" not in s or "challenge_response_ok" not in s:
            return None
        return bool(s["challenge_response_digest"] == p.get("reboot_challenge_digest")
                    and s["challenge_response_ok"] is True)
    return None

def simulate_postreboot_probe(
    plan: Mapping[str, Any],
    store: SyntheticCASStore,
    snapshot: Mapping[str, Any],
    *,
    simulated_boot_epoch_digest: str,
    simulated_challenge_digest: str,
    synthetic_attestor_digest: str,
) -> dict[str, Any]:
    """Build upstream evidence from an injected fixture, not a live Windows read."""
    p = dict(plan)
    if p.get("state") != REBOOT_READY:
        return {"state": BLOCKED, "postreboot_disposition": UNKNOWN,
                "blockers": ["READY_REBOOT_PLAN_REQUIRED"], "synthetic_only": True}
    if not all(_sha(v) for v in (
        simulated_boot_epoch_digest, simulated_challenge_digest, synthetic_attestor_digest
    )):
        return {"state": BLOCKED, "postreboot_disposition": UNKNOWN,
                "blockers": ["SYNTHETIC_PROBE_DIGESTS_REQUIRED"], "synthetic_only": True}
    if simulated_challenge_digest != p.get("reboot_challenge_digest"):
        return {"state": BLOCKED, "postreboot_disposition": UNKNOWN,
                "blockers": ["CHALLENGE_MISMATCH"], "synthetic_only": True}
    record = store.simulated_reopen().read(p.get("installation_id"))
    checks = p.get("checks", [])
    evaluations: list[bool | None] = [
        _evaluate_reboot_check(c.get("check_id"), p, snapshot, record, simulated_boot_epoch_digest)
        for c in checks
    ]
    evidence = []
    for c, evaluation in zip(checks, evaluations):
        check_id = c.get("check_id")
        row = {
            "check_id": check_id,
            "proof_binding_digest": c.get("expected_proof_binding_digest"),
            "observed_postboot_epoch_digest": simulated_boot_epoch_digest,
            "observed_challenge_digest": simulated_challenge_digest,
            "reopened_after_reboot": True,  # synthetic clone only
            "independent_verifier_observed": True,  # test verifier only
            "independent_readback_receipt_digest": _digest({
                "test_only": True, "check_id": check_id, "observed_fixture": dict(snapshot),
                "store_record_digest": _digest(record) if record else "",
                "postboot_epoch": simulated_boot_epoch_digest,
                "challenge": simulated_challenge_digest,
            }),
            "result": "VERIFIED_POSITIVE" if evaluation is True else (
                "VERIFIED_NEGATIVE" if evaluation is False else "UNKNOWN"
            ),
            "ambiguity_detected": evaluation is None,
        }
        if evaluation is False:
            row["authoritative_negative_evidence_digest"] = _digest({
                "test_only": True, "negative_check": check_id,
                "fixture": dict(snapshot),
            })
        evidence.append(row)
    requested_result = "UNHEALTHY" if False in evaluations else "HEALTHY"
    classification = classify_postreboot_health_evidence(
        p, evidence,
        observed_postboot_epoch_digest=simulated_boot_epoch_digest,
        observed_challenge_digest=simulated_challenge_digest,
        independent_reboot_attestor_digest=synthetic_attestor_digest,
        requested_result=requested_result,
    )
    classification["synthetic_only"] = True
    classification["physical_boot_epoch_attested"] = False
    classification["physical_windows_state_observed"] = False
    classification["trusted_independent_verifier_used"] = False
    classification["actual_reboot_performed"] = False
    classification["real_postreboot_healthy"] = False
    return classification

def synthetic_harness_review(*, test_cases_passed: int, test_cases_expected: int,
                             source_digest: str, test_digest: str) -> dict[str, Any]:
    ok = (type(test_cases_passed) is int and type(test_cases_expected) is int
          and test_cases_expected > 0 and test_cases_passed == test_cases_expected
          and _sha(source_digest) and _sha(test_digest))
    return {
        "schema": SCHEMA,
        "state": READY if ok else BLOCKED,
        "synthetic_harness_review_digest": _digest({
            "passed": test_cases_passed, "expected": test_cases_expected,
            "source_digest": _sha(source_digest), "test_digest": _sha(test_digest),
        }) if ok else "",
        "test_only": True,
        "ready_for_real_windows_install": False,
        **{k: v for k, v in SIMULATOR_POLICY.items() if k != "schema"},
    }

__all__ = [
    "SyntheticCASStore", "synthetic_persistence_shape", "simulate_postreboot_probe",
    "synthetic_harness_review", "SIMULATOR_POLICY", "SCHEMA", "READY",
    "STORE_COMMITTED", "STORE_UNKNOWN", "STORE_REJECTED", "REOPEN_ONLY",
]
