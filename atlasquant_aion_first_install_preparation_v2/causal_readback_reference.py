"""Fresh read-only SQLite causal evidence, not an independent trust anchor.

Reuses the existing CAS chain verifier; never calls its writing constructor,
snapshot, CAS or journal claim during recovery. No remote providers.
"""
from pathlib import Path
import sqlite3
import json

from atlasquant_aion_v2_isolated_sqlite_witness_cas_reference import (
    ReferenceIsolatedSqliteWitnessCAS, _digest, _valid_config, _valid_head)
from atlasquant_aion_v2_external_witness_rollback_reference import signed_receipt_sha256
from atlasquant_aion_first_install_preparation.contracts import result, token, integer

def read_operation_reference(path, *, config, genesis_head, operation_id,
        expected_query, signed_read, signed_next_collector_receipt,
        minimum_sequence, minimum_epoch):
    """Pinned scope + full append chain + exact operation/input, one snapshot.

    Pins/floors are supplied simulation inputs, NOT trusted external enrollment.
    Absence is not permission to retry. Fresh connection avoids stale handles.
    """
    connection = None
    try:
        if (not _valid_config(config) or not _valid_head(genesis_head)
                or not token(operation_id) or not integer(minimum_sequence, 1)
                or not integer(minimum_epoch, 1)):
            return result("BLOCKED", "READ_BINDING_INVALID")
        if type(expected_query) is not dict or type(signed_read) is not dict or type(signed_next_collector_receipt) is not dict:
            return result("BLOCKED", "READ_INPUT_SCHEMA_INVALID")
        encoded = json.dumps([expected_query,signed_read,signed_next_collector_receipt],allow_nan=False)
        if len(encoded) > 32768:
            return result("BLOCKED", "REFERENCE_INPUT_BOUND_EXCEEDED")
        query_hash = _digest({"query": expected_query, "signed_read": signed_read})
        receipt_hash = signed_receipt_sha256(signed_next_collector_receipt)
        # mode=ro prevents creating a missing DB; no WAL mode changes or writes.
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        if connection.execute("SELECT COUNT(*) FROM witness_ref_appends").fetchone()[0] > 1024:
            return result("BLOCKED", "REFERENCE_HISTORY_BOUND_EXCEEDED")
        verifier = object.__new__(ReferenceIsolatedSqliteWitnessCAS)
        verifier.config = dict(config); verifier.genesis = dict(genesis_head)
        verifier.db = connection
        head, count = verifier._verified_head()
        if head["sequence"] < minimum_sequence or head["witness_epoch"] < minimum_epoch:
            return result("BLOCKED", "HEAD_OR_EPOCH_REGRESSION")
        row = connection.execute("SELECT * FROM witness_ref_appends WHERE operation_id=?",
                                 (operation_id,)).fetchone()
        if row is None:
            return result("RECONCILIATION_REQUIRED", "CAUSAL_EFFECT_NOT_FOUND_NO_RETRY")
        if row["query_sha256"] != query_hash or row["next_receipt_sha256"] != receipt_hash:
            return result("BLOCKED", "OPERATION_PAYLOAD_CONFLICT")
        return result("REFERENCE_CAUSAL_MATCH_UNTRUSTED", "LOCAL_FILE_NOT_EXTERNAL_PROOF",
            operation_digest=_digest({"operation_id":operation_id,"query":query_hash,"receipt":receipt_hash}),
            current_head=head, local_append_count=count, reference_causal_match=True)
    except (sqlite3.Error, ValueError, TypeError, KeyError, OverflowError, OSError, RecursionError):
        return result("UNKNOWN_OUTCOME", "INDEPENDENT_READ_UNAVAILABLE_NO_RETRY")
    finally:
        if connection is not None:
            connection.close()

def reconcile_simulated_domains(observations, *, revoked=False):
    """Three fixture domains; separate labels/processes are NOT independence.

    Reads are observations, never write authorization. No quorum fallback.
    """
    if type(revoked) is not bool or revoked:
        return result("BLOCKED", "REVOCATION_UNKNOWN_OR_REVOKED")
    if type(observations) is not list or len(observations) != 3:
        return result("UNKNOWN_OUTCOME", "THREE_DOMAIN_READS_REQUIRED")
    seen = set(); controllers = set(); pins = set(); matches = []
    for value in observations:
        if (type(value) is not dict or set(value) != {"domain", "controller", "key_pin", "read"}
                or not all(token(value[k]) for k in ("domain", "controller", "key_pin"))):
            return result("BLOCKED", "DOMAIN_CONTRACT_INVALID")
        seen.add(value["domain"]); controllers.add(value["controller"]); pins.add(value["key_pin"])
        read = value["read"]
        if type(read) is not dict:
            return result("UNKNOWN_OUTCOME", "READ_UNAVAILABLE")
        if read.get("state") != "REFERENCE_CAUSAL_MATCH_UNTRUSTED":
            state = read.get("state")
            return result(state if state in ("BLOCKED", "RECONCILIATION_REQUIRED") else "UNKNOWN_OUTCOME",
                          "DOMAIN_NOT_RECONCILED_NO_RETRY")
        from atlasquant_aion_first_install_preparation.contracts import digest_value
        if (read.get("reference_causal_match") is not True
                or not digest_value(read.get("operation_digest"))
                or not _valid_head(read.get("current_head"))
                or not integer(read.get("local_append_count"),1,1024)):
            return result("BLOCKED", "CAUSAL_READ_CONTRACT_INVALID")
        matches.append((read.get("operation_digest"), read.get("current_head")))
    if len(seen) != 3 or len(controllers) != 3 or len(pins) != 3:
        return result("BLOCKED", "SHARED_AUTHORITY_NOT_INDEPENDENT")
    if any(value != matches[0] for value in matches[1:]) or matches[0][0] is None:
        return result("BLOCKED", "CONFLICTING_DOMAIN_EVIDENCE")
    return result("REFERENCE_CONFIRMED_UNTRUSTED", "SIMULATED_DOMAINS_NOT_INDEPENDENT_CUSTODY",
                  reference_outcome="CONFIRMED", independent_administrative_domains_verified=False)

class SimulatedProvider:
    """Deterministic fault wrapper around existing local CAS; not new CAS."""
    FAULTS = ("NONE", "BEFORE_COMMIT", "AFTER_COMMIT", "LOST_ACK", "FAKE_SUCCESS")

    def __init__(self, cas, *, fault="NONE"):
        if fault not in self.FAULTS:
            raise ValueError("UNKNOWN_FIXTURE_FAULT")
        self.cas = cas; self.fault = fault; self.write_attempts = 0

    def write_reference(self, **inputs):
        self.write_attempts += 1
        if self.fault == "BEFORE_COMMIT":
            raise OSError("FIXTURE_PRECOMMIT_FAILURE")
        if self.fault == "FAKE_SUCCESS":
            return {"state":"REFERENCE_SQLITE_CAS_COMMITTED_UNTRUSTED"}
        outcome = self.cas.cas_reference_only(**inputs)
        if self.fault in ("AFTER_COMMIT", "LOST_ACK"):
            raise OSError("FIXTURE_ACK_UNAVAILABLE")
        return outcome

def attempt_simulated_once(journal, intent, providers, inputs):
    """Existing durable one-shot claim BEFORE fake writes; ACK never success.

    Recovery only reads; a restarted journal cannot claim again. This does not
    defeat privileged restoration of every file or establish external custody.
    """
    from atlasquant_aion_v2_one_shot_unknown_outcome_journal_reference import LOCAL_CLAIM
    from copy import deepcopy
    if (type(providers) is not list or len(providers) != 3
            or any(type(p) is not SimulatedProvider for p in providers)
            or type(inputs) is not dict):
        return result("BLOCKED", "FIXTURE_ADAPTERS_REQUIRED")
    if set(inputs) != {"operation_id","expected_query","signed_read","signed_next_collector_receipt","witness_public_pin","collector_public_pin"}:
        return result("BLOCKED", "FIXTURE_CAS_INPUT_SCHEMA_INVALID")
    try:
        encoded = json.dumps([intent,inputs],allow_nan=False)
        if len(encoded) > 32768:
            return result("BLOCKED", "FIXTURE_INPUT_BOUND_EXCEEDED")
        frozen_intent = deepcopy(intent); frozen_inputs = deepcopy(inputs)
    except (TypeError, ValueError, RecursionError):
        return result("BLOCKED", "FIXTURE_INPUT_INVALID")
    # Exact payload identity persists in the existing full-request digest slot.
    if (type(frozen_intent) is not dict
            or frozen_intent.get("full_provider_request_sha256") != _digest(frozen_inputs)):
        return result("BLOCKED", "DURABLE_INTENT_PAYLOAD_MISMATCH")
    claim = journal.claim_reference_only(intent=frozen_intent)
    if claim["state"] != LOCAL_CLAIM:
        return result("BLOCKED", "DURABLE_CLAIM_DENIED_NO_WRITES")
    try:
        for provider in providers:
            outcome = provider.write_reference(**frozen_inputs)
            if outcome.get("state") != "REFERENCE_SQLITE_CAS_COMMITTED_UNTRUSTED":
                raise OSError("FIXTURE_UNCONFIRMED_WRITE")
    except (OSError, ValueError, TypeError, sqlite3.Error):
        journal.mark_unknown_reference_only(nonce_hex=frozen_intent["nonce_hex"])
        return result("UNKNOWN_OUTCOME", "READBACK_REQUIRED_NO_RESEND")
    # Even three positive ACKs are not causal readback.
    return result("RECONCILIATION_REQUIRED", "ACKS_NOT_COMMIT_PROOF_NO_RETRY")
