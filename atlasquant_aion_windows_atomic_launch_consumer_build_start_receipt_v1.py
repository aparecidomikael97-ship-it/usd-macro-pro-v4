"""AION Windows Atomic Launch Consumer + Build Start Receipt V1.

Design-only launch boundary after #1053.

Critical rule:
database/state persistence and an OS process spawn are not treated as one
fictional atomic operation.

Future flow:
1. final pre-spawn revalidation is independently trusted;
2. one CAS transaction consumes HUMAN_OWNER authorization + build token and
   persists a LAUNCH_COMMITTED write-ahead record;
3. exactly one spawn attempt may occur for that committed launch_id;
4. a durable build-start observation/receipt records what happened;
5. crash/timeout/ambiguity after commit becomes BUILD_START_OUTCOME_UNKNOWN;
6. automatic retry is forbidden until separate reconciliation.

This module writes nothing, spawns nothing, opens no process, issues no token,
starts no build, calls no network/GitHub and mutates no production state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_windows_build_token_prelaunch_revalidation_v1 import (
    PRELAUNCH_CONTRACT_SCHEMA,
    TOKEN_TEMPLATE_SCHEMA,
    READY_PRELAUNCH_CONTRACT_STATE,
    READY_TOKEN_TEMPLATE_STATE,
)

SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_LAUNCH_CONSUMER_BUILD_START_RECEIPT_V1"
CONTRACT_SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_LAUNCH_CONSUMER_CONTRACT_V1"
COMMIT_SCHEMA="ATLASQUANT_AION_WINDOWS_LAUNCH_COMMITMENT_CANDIDATE_V1"
COMMIT_ATTESTATION_SCHEMA="ATLASQUANT_AION_WINDOWS_LAUNCH_COMMITMENT_PERSISTENCE_ATTESTATION_V1"
SPAWN_BOUNDARY_SCHEMA="ATLASQUANT_AION_WINDOWS_SINGLE_SPAWN_BOUNDARY_V1"
START_RECEIPT_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_START_RECEIPT_V1"
RECONCILIATION_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_START_RECONCILIATION_CONTRACT_V1"
REVIEW_SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_LAUNCH_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_LAUNCH_POLICY_V1"

READY_CONTRACT_STATE="ATOMIC_LAUNCH_CONSUMER_CONTRACT_READY"
READY_COMMIT_STATE="READY_FOR_DURABLE_LAUNCH_COMMITMENT_WRITE"
READY_COMMIT_ATTESTATION_SHAPE="LAUNCH_COMMITMENT_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED"
READY_SPAWN_BOUNDARY_STATE="READY_FOR_SINGLE_BUILD_SPAWN_ATTEMPT"
READY_START_RECEIPT_TEMPLATE_STATE="BUILD_START_RECEIPT_TEMPLATE_READY_UNISSUED"
READY_RECONCILIATION_STATE="BUILD_START_RECONCILIATION_CONTRACT_READY"
READY_REVIEW_STATE="READY_FOR_WINDOWS_ATOMIC_LAUNCH_CONSUMER_IMPLEMENTATION"
BLOCKED_STATE="BLOCKED"

COMMIT_STATE="LAUNCH_COMMITTED"
START_CONFIRMED="BUILD_START_CONFIRMED"
START_FAILED="BUILD_START_CONFIRMED_TERMINAL_FAILURE"
START_UNKNOWN="BUILD_START_OUTCOME_UNKNOWN"
ALLOWED_START_OUTCOMES=(START_CONFIRMED,START_FAILED,START_UNKNOWN)

MAX_COMMIT_TO_SPAWN_SECONDS=5
MAX_START_OBSERVATION_SECONDS=5

_SHA256_RE=re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")

def _clean(v:Any,n:int=1000)->str:
    return " ".join(str(v or "").replace("\x00","").split())[:n]

def _canonical(v:Any)->str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False,default=str)

def _digest(v:Any)->str:
    return "sha256:"+sha256(_canonical(v).encode()).hexdigest()

def _sha256(v:Any)->str:
    t=_clean(v,90)
    return t if _SHA256_RE.fullmatch(t) else ""

def _identity(v:Any,n:int=240)->str:
    if type(v) is not str:return ""
    t=_clean(v,n)
    return t if t==v and _ID_RE.fullmatch(t) else ""

def _aware(v:Any)->datetime:
    dt=v if isinstance(v,datetime) else datetime.fromisoformat(str(v).replace("Z","+00:00"))
    if dt.tzinfo is None: raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)

def build_atomic_launch_contract(
    prelaunch_contract:Mapping[str,Any]|None,
    token_template:Mapping[str,Any]|None,
    *,
    launch_writer_manifest_digest:Any,
    launch_consumer_manifest_digest:Any,
    start_observer_manifest_digest:Any,
    reconciliation_policy_digest:Any,
)->dict[str,Any]:
    pre=dict(prelaunch_contract or {});token=dict(token_template or {});blockers=[]
    if pre.get("schema")!=PRELAUNCH_CONTRACT_SCHEMA:blockers.append("PRELAUNCH_CONTRACT_SCHEMA_MISMATCH")
    if pre.get("state")!=READY_PRELAUNCH_CONTRACT_STATE:blockers.append("READY_PRELAUNCH_CONTRACT_REQUIRED")
    if token.get("schema")!=TOKEN_TEMPLATE_SCHEMA:blockers.append("BUILD_TOKEN_TEMPLATE_SCHEMA_MISMATCH")
    if token.get("state")!=READY_TOKEN_TEMPLATE_STATE:blockers.append("READY_UNISSUED_BUILD_TOKEN_TEMPLATE_REQUIRED")
    for k in ("token_issued","token_signed","token_persisted","token_consumed","owner_authorization_consumed",
              "launch_authorized","build_authorized","build_started","process_spawned"):
        if token.get(k) is not False:blockers.append("UPSTREAM_"+k.upper()+"_MUST_REMAIN_FALSE")
    vals={}
    for k,v,label in (
        ("launch_writer_manifest_digest",launch_writer_manifest_digest,"LAUNCH_WRITER_MANIFEST_DIGEST_REQUIRED"),
        ("launch_consumer_manifest_digest",launch_consumer_manifest_digest,"LAUNCH_CONSUMER_MANIFEST_DIGEST_REQUIRED"),
        ("start_observer_manifest_digest",start_observer_manifest_digest,"START_OBSERVER_MANIFEST_DIGEST_REQUIRED"),
        ("reconciliation_policy_digest",reconciliation_policy_digest,"RECONCILIATION_POLICY_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "prelaunch_contract_digest":_sha256(pre.get("prelaunch_contract_digest")),
        "token_template_digest":_sha256(token.get("token_template_digest")),
        "gate_contract_digest":_sha256(token.get("gate_contract_digest")),
        "host_binding_digest":_sha256(token.get("host_binding_digest")),
        "owner_authorization_verification_digest":_sha256(token.get("owner_authorization_verification_digest")),
        "authorization_persistence_attestation_digest":_sha256(token.get("authorization_persistence_attestation_digest")),
        "build_token_nonce_digest":_sha256(token.get("token_nonce_digest")),
        "launch_binary_path_digest":_sha256(token.get("launch_binary_path_digest")),
        "launch_binary_sha256":_sha256(token.get("launch_binary_sha256")),
        "build_script_sha256":_sha256(token.get("build_script_sha256")),
        **vals,
        "commit_state":COMMIT_STATE,
        "max_commit_to_spawn_seconds":MAX_COMMIT_TO_SPAWN_SECONDS,
        "max_start_observation_seconds":MAX_START_OBSERVATION_SECONDS,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":CONTRACT_SCHEMA,
        "state":READY_CONTRACT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "atomic_launch_contract_digest":_digest(material) if not blockers else "",
        "write_ahead_launch_commit_required":True,
        "owner_authorization_and_token_consumed_in_same_cas_required":True,
        "os_spawn_in_database_transaction_claim_allowed":False,
        "single_spawn_attempt_required":True,
        "automatic_retry_after_commit_allowed":False,
        "post_commit_crash_becomes_unknown":True,
        "post_commit_timeout_becomes_unknown":True,
        "post_commit_ambiguous_spawn_becomes_unknown":True,
        "separate_reconciliation_required":True,
        "launch_commitment_written":False,
        "owner_authorization_consumed":False,
        "build_token_consumed":False,
        "spawn_attempted":False,
        "build_started":False,
        "build_authorized":False,
        "process_spawned":False,
        "filesystem_modified":False,
        "network_called":False,
    }

def build_launch_commitment_candidate(
    contract:Mapping[str,Any]|None,
    *,
    launch_id:Any,
    owner_authorization_record_digest:Any,
    build_token_record_digest:Any,
    final_pre_spawn_revalidation_digest:Any,
    expected_owner_auth_state:Any,
    expected_token_state:Any,
    expected_pre_launch_revision:int,
)->dict[str,Any]:
    row=dict(contract or {});blockers=[]
    if row.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_ATOMIC_LAUNCH_CONTRACT_REQUIRED")
    launch=_identity(launch_id,180)
    if not launch:blockers.append("LAUNCH_ID_REQUIRED")
    vals={}
    for k,v,label in (
        ("owner_authorization_record_digest",owner_authorization_record_digest,"OWNER_AUTHORIZATION_RECORD_DIGEST_REQUIRED"),
        ("build_token_record_digest",build_token_record_digest,"BUILD_TOKEN_RECORD_DIGEST_REQUIRED"),
        ("final_pre_spawn_revalidation_digest",final_pre_spawn_revalidation_digest,"FINAL_PRE_SPAWN_REVALIDATION_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    if _clean(expected_owner_auth_state,80)!="UNCONSUMED":blockers.append("OWNER_AUTHORIZATION_EXPECTED_STATE_MUST_BE_UNCONSUMED")
    if _clean(expected_token_state,80)!="UNCONSUMED":blockers.append("BUILD_TOKEN_EXPECTED_STATE_MUST_BE_UNCONSUMED")
    try:
        revision=int(expected_pre_launch_revision)
        if revision<0:blockers.append("EXPECTED_PRE_LAUNCH_REVISION_INVALID")
    except Exception:
        revision=-1;blockers.append("EXPECTED_PRE_LAUNCH_REVISION_INVALID")
    identity={
        "launch_id":launch,
        "atomic_launch_contract_digest":_sha256(row.get("atomic_launch_contract_digest")),
        "owner_authorization_record_digest":vals.get("owner_authorization_record_digest",""),
        "build_token_record_digest":vals.get("build_token_record_digest",""),
    }
    material={
        **identity,**vals,
        "record_key":_digest(identity),
        "expected_owner_auth_state":"UNCONSUMED",
        "expected_token_state":"UNCONSUMED",
        "post_commit_owner_auth_state":"CONSUMED_FOR_LAUNCH",
        "post_commit_token_state":"CONSUMED_FOR_LAUNCH",
        "post_commit_launch_state":COMMIT_STATE,
        "expected_pre_launch_revision":revision,
        "committed_launch_revision_if_written":revision+1 if revision>=0 else -1,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":COMMIT_SCHEMA,"state":READY_COMMIT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "launch_commitment_digest":_digest(material) if not blockers else "",
        "atomic_compare_and_set_required":True,
        "owner_authorization_consumed_if_written":True,
        "build_token_consumed_if_written":True,
        "launch_record_persisted_if_written":True,
        "launch_commitment_written":False,
        "owner_authorization_consumed":False,
        "build_token_consumed":False,
        "spawn_attempted":False,
        "build_started":False,
    }

def validate_future_commitment_attestation_shape(
    candidate:Mapping[str,Any]|None,**evidence:Any
)->dict[str,Any]:
    row=dict(candidate or {});blockers=[]
    if row.get("state")!=READY_COMMIT_STATE:blockers.append("READY_LAUNCH_COMMITMENT_CANDIDATE_REQUIRED")
    required=("launch_commitment_record_digest","writer_manifest_digest","write_receipt_digest",
              "cas_observation_digest","read_after_write_observation_digest","reopen_observation_digest",
              "owner_authorization_consumption_observation_digest","token_consumption_observation_digest")
    vals={}
    for k in required:
        d=_sha256(evidence.get(k));vals[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    if evidence.get("caller_claims_commitment_trusted") is True:blockers.append("CALLER_LAUNCH_COMMITMENT_TRUST_CLAIM_NOT_ACCEPTED")
    material={
        "launch_commitment_digest":_sha256(row.get("launch_commitment_digest")),
        "launch_id":row.get("launch_id"),
        **vals,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":COMMIT_ATTESTATION_SCHEMA,
        "state":READY_COMMIT_ATTESTATION_SHAPE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "commitment_attestation_candidate_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,
        "commitment_persisted_trusted":False,
        "cas_verified":False,
        "read_after_write_verified":False,
        "reopen_verified":False,
        "owner_authorization_consumption_verified":False,
        "build_token_consumption_verified":False,
        "spawn_allowed":False,
        "spawn_attempted":False,
        "build_started":False,
    }

def build_single_spawn_boundary(
    contract:Mapping[str,Any]|None,
    commitment_candidate:Mapping[str,Any]|None,
    *,
    commitment_persistence_attestation_digest:Any,
    launch_lease_digest:Any,
    process_command_digest:Any,
    process_environment_digest:Any,
    job_object_policy_digest:Any,
    committed_at:Any,
    spawn_deadline:Any,
)->dict[str,Any]:
    con=dict(contract or {});commit=dict(commitment_candidate or {});blockers=[]
    if con.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_ATOMIC_LAUNCH_CONTRACT_REQUIRED")
    if commit.get("state")!=READY_COMMIT_STATE:blockers.append("READY_LAUNCH_COMMITMENT_CANDIDATE_REQUIRED")
    vals={}
    for k,v,label in (
        ("commitment_persistence_attestation_digest",commitment_persistence_attestation_digest,"COMMITMENT_PERSISTENCE_ATTESTATION_DIGEST_REQUIRED"),
        ("launch_lease_digest",launch_lease_digest,"LAUNCH_LEASE_DIGEST_REQUIRED"),
        ("process_command_digest",process_command_digest,"PROCESS_COMMAND_DIGEST_REQUIRED"),
        ("process_environment_digest",process_environment_digest,"PROCESS_ENVIRONMENT_DIGEST_REQUIRED"),
        ("job_object_policy_digest",job_object_policy_digest,"JOB_OBJECT_POLICY_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    try:
        committed=_aware(committed_at);deadline=_aware(spawn_deadline)
        window=(deadline-committed).total_seconds()
        if window<=0:blockers.append("SPAWN_WINDOW_INVALID")
        if window>MAX_COMMIT_TO_SPAWN_SECONDS:blockers.append("SPAWN_WINDOW_TOO_LONG")
    except Exception:
        committed=deadline=None;blockers.append("SPAWN_WINDOW_TIME_INVALID")
    material={
        "atomic_launch_contract_digest":_sha256(con.get("atomic_launch_contract_digest")),
        "launch_commitment_digest":_sha256(commit.get("launch_commitment_digest")),
        "launch_id":commit.get("launch_id"),
        **vals,
        "launch_binary_path_digest":_sha256(con.get("launch_binary_path_digest")),
        "launch_binary_sha256":_sha256(con.get("launch_binary_sha256")),
        "build_script_sha256":_sha256(con.get("build_script_sha256")),
        "committed_at":committed.isoformat() if committed else "",
        "spawn_deadline":deadline.isoformat() if deadline else "",
        "max_spawn_attempts":1,
        "max_process_count":1,
        "max_child_process_count":0,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":SPAWN_BOUNDARY_SCHEMA,
        "state":READY_SPAWN_BOUNDARY_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "spawn_boundary_digest":_digest(material) if not blockers else "",
        "single_spawn_attempt_required":True,
        "path_lookup_allowed":False,
        "shell_allowed":False,
        "child_process_allowed":False,
        "automatic_retry_allowed":False,
        "spawn_attempted":False,
        "process_spawned":False,
        "build_started":False,
    }

def build_unissued_start_receipt_template(
    spawn_boundary:Mapping[str,Any]|None
)->dict[str,Any]:
    row=dict(spawn_boundary or {});blockers=[]
    if row.get("state")!=READY_SPAWN_BOUNDARY_STATE:blockers.append("READY_SINGLE_SPAWN_BOUNDARY_REQUIRED")
    material={
        "launch_id":row.get("launch_id"),
        "spawn_boundary_digest":_sha256(row.get("spawn_boundary_digest")),
        "launch_commitment_digest":_sha256(row.get("launch_commitment_digest")),
        "launch_binary_sha256":_sha256(row.get("launch_binary_sha256")),
        "build_script_sha256":_sha256(row.get("build_script_sha256")),
        "allowed_outcomes":list(ALLOWED_START_OUTCOMES),
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":START_RECEIPT_SCHEMA,
        "state":READY_START_RECEIPT_TEMPLATE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "receipt_template_digest":_digest(material) if not blockers else "",
        "outcome":"NOT_OBSERVED",
        "spawn_attempted":False,
        "process_spawned":False,
        "process_identity_digest":"",
        "process_handle_observation_digest":"",
        "job_object_membership_observation_digest":"",
        "image_hash_observation_digest":"",
        "command_observation_digest":"",
        "started_at":"",
        "receipt_issued":False,
        "receipt_persisted":False,
        "build_started":False,
        "automatic_retry_allowed":False,
    }

def classify_future_start_observation(
    receipt_template:Mapping[str,Any]|None,
    *,
    requested_outcome:Any,
    spawn_attempted:bool,
    process_spawned:bool,
    process_identity_digest:Any="",
    process_handle_observation_digest:Any="",
    job_object_membership_observation_digest:Any="",
    image_hash_observation_digest:Any="",
    command_observation_digest:Any="",
    terminal_failure_evidence_digest:Any="",
    ambiguity_evidence_digest:Any="",
)->dict[str,Any]:
    row=dict(receipt_template or {});blockers=[]
    if row.get("state")!=READY_START_RECEIPT_TEMPLATE_STATE:blockers.append("READY_START_RECEIPT_TEMPLATE_REQUIRED")
    requested=_clean(requested_outcome,80)
    if requested not in ALLOWED_START_OUTCOMES:blockers.append("BUILD_START_OUTCOME_INVALID")
    positive={
        "process_identity_digest":_sha256(process_identity_digest),
        "process_handle_observation_digest":_sha256(process_handle_observation_digest),
        "job_object_membership_observation_digest":_sha256(job_object_membership_observation_digest),
        "image_hash_observation_digest":_sha256(image_hash_observation_digest),
        "command_observation_digest":_sha256(command_observation_digest),
    }
    terminal=_sha256(terminal_failure_evidence_digest)
    ambiguity=_sha256(ambiguity_evidence_digest)
    if ambiguity:
        final=START_UNKNOWN
    elif requested==START_CONFIRMED:
        if spawn_attempted is True and process_spawned is True and all(positive.values()):
            final=START_CONFIRMED
        else:
            final=START_UNKNOWN
    elif requested==START_FAILED:
        if spawn_attempted is True and process_spawned is False and terminal:
            final=START_FAILED
        else:
            final=START_UNKNOWN
    else:
        final=START_UNKNOWN
    material={
        "receipt_template_digest":_sha256(row.get("receipt_template_digest")),
        "launch_id":row.get("launch_id"),
        "requested_outcome":requested,
        "final_outcome":final,
        "spawn_attempted":spawn_attempted is True,
        "process_spawned":process_spawned is True,
        **positive,
        "terminal_failure_evidence_digest":terminal,
        "ambiguity_evidence_digest":ambiguity,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":START_RECEIPT_SCHEMA,
        "state":"BUILD_START_OBSERVATION_CLASSIFIED" if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "start_observation_digest":_digest(material) if not blockers else "",
        "build_started_confirmed":final==START_CONFIRMED,
        "terminal_failure_confirmed":final==START_FAILED,
        "outcome_unknown":final==START_UNKNOWN,
        "automatic_retry_allowed":False,
        "reconciliation_required":final==START_UNKNOWN,
        "observation_is_physical_truth_trusted":False,
        "receipt_issued":False,
        "receipt_persisted":False,
    }

def build_reconciliation_contract(
    start_observation:Mapping[str,Any]|None,
    *,
    reconciliation_reader_manifest_digest:Any,
    process_table_readback_policy_digest:Any,
    durable_store_readback_policy_digest:Any,
)->dict[str,Any]:
    row=dict(start_observation or {});blockers=[]
    if row.get("state")!="BUILD_START_OBSERVATION_CLASSIFIED":blockers.append("CLASSIFIED_BUILD_START_OBSERVATION_REQUIRED")
    if row.get("final_outcome")!=START_UNKNOWN:blockers.append("BUILD_START_OUTCOME_UNKNOWN_REQUIRED")
    vals={}
    for k,v,label in (
        ("reconciliation_reader_manifest_digest",reconciliation_reader_manifest_digest,"RECONCILIATION_READER_MANIFEST_DIGEST_REQUIRED"),
        ("process_table_readback_policy_digest",process_table_readback_policy_digest,"PROCESS_TABLE_READBACK_POLICY_DIGEST_REQUIRED"),
        ("durable_store_readback_policy_digest",durable_store_readback_policy_digest,"DURABLE_STORE_READBACK_POLICY_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "start_observation_digest":_sha256(row.get("start_observation_digest")),
        "launch_id":row.get("launch_id"),
        **vals,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":RECONCILIATION_SCHEMA,
        "state":READY_RECONCILIATION_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "reconciliation_contract_digest":_digest(material) if not blockers else "",
        "automatic_retry_allowed":False,
        "new_spawn_attempt_authorized":False,
        "process_readback_executed":False,
        "durable_store_readback_executed":False,
        "reconciliation_completed":False,
    }

def build_implementation_review(
    contract:Mapping[str,Any]|None,
    start_receipt_template:Mapping[str,Any]|None,
    *,
    launch_writer_source_digest:Any,
    launch_consumer_source_digest:Any,
    start_observer_source_digest:Any,
    reconciliation_source_digest:Any,
)->dict[str,Any]:
    con=dict(contract or {});receipt=dict(start_receipt_template or {});blockers=[]
    if con.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_ATOMIC_LAUNCH_CONTRACT_REQUIRED")
    if receipt.get("state")!=READY_START_RECEIPT_TEMPLATE_STATE:blockers.append("READY_START_RECEIPT_TEMPLATE_REQUIRED")
    vals={}
    for k,v,label in (
        ("launch_writer_source_digest",launch_writer_source_digest,"LAUNCH_WRITER_SOURCE_DIGEST_REQUIRED"),
        ("launch_consumer_source_digest",launch_consumer_source_digest,"LAUNCH_CONSUMER_SOURCE_DIGEST_REQUIRED"),
        ("start_observer_source_digest",start_observer_source_digest,"START_OBSERVER_SOURCE_DIGEST_REQUIRED"),
        ("reconciliation_source_digest",reconciliation_source_digest,"RECONCILIATION_SOURCE_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "atomic_launch_contract_digest":_sha256(con.get("atomic_launch_contract_digest")),
        "start_receipt_template_digest":_sha256(receipt.get("receipt_template_digest")),
        **vals,
        "next_pc_phase":"IMPLEMENT_WRITE_AHEAD_LAUNCH_COMMIT_AND_SINGLE_SPAWN_WITH_SYNTHETIC_BUILD",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":REVIEW_SCHEMA,
        "state":READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "implementation_review_digest":_digest(material) if not blockers else "",
        "launch_writer_implemented":False,
        "launch_consumer_implemented":False,
        "start_observer_implemented":False,
        "reconciliation_implemented":False,
        "launch_commitment_written":False,
        "owner_authorization_consumed":False,
        "build_token_consumed":False,
        "spawn_attempted":False,
        "process_spawned":False,
        "build_started":False,
        "start_receipt_issued":False,
        "start_receipt_persisted":False,
        "network_called":False,
        "github_api_called":False,
        "live_repository_mutation_performed":False,
    }

def atomic_launch_policy()->dict[str,Any]:
    return {
        "schema":POLICY_SCHEMA,
        "write_ahead_launch_commit_required":True,
        "owner_authorization_and_token_consumed_in_same_cas_required":True,
        "os_spawn_in_database_transaction_claim_allowed":False,
        "single_spawn_attempt_required":True,
        "max_commit_to_spawn_seconds":MAX_COMMIT_TO_SPAWN_SECONDS,
        "max_start_observation_seconds":MAX_START_OBSERVATION_SECONDS,
        "post_commit_crash_becomes_unknown":True,
        "post_commit_timeout_becomes_unknown":True,
        "post_commit_ambiguous_spawn_becomes_unknown":True,
        "automatic_retry_after_commit_allowed":False,
        "separate_reconciliation_required":True,
        "start_success_requires_positive_process_evidence":True,
        "terminal_failure_requires_authoritative_no_process_evidence":True,
        "ambiguity_wins_over_requested_success":True,
        "generic_chat_is_launch_authority":False,
        "launch_writer_implemented":False,
        "launch_consumer_implemented":False,
        "start_observer_implemented":False,
        "reconciliation_implemented":False,
        "launch_commitment_written":False,
        "owner_authorization_consumed":False,
        "build_token_consumed":False,
        "spawn_attempted":False,
        "process_spawned":False,
        "build_started":False,
        "start_receipt_issued":False,
        "start_receipt_persisted":False,
        "build_authorized":False,
        "package_built":False,
        "package_installed":False,
        "filesystem_modified":False,
        "network_called":False,
        "github_api_called":False,
        "live_repository_mutation_authorized":False,
        "live_repository_mutation_performed":False,
        "production_repository_mutation_performed":False,
        "deploy_executed":False,
        "worker_activated":False,
        "provider_activated":False,
        "production_persistence_activated":False,
    }

__all__=[name for name in globals() if name.isupper() or name.startswith("build_") or name.startswith("validate_") or name.startswith("classify_")]
