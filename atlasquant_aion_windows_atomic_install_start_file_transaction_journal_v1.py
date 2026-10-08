"""AION Windows Atomic Installation Start + File Transaction Journal V1.

Design-only installation mutation boundary after #1057.

Critical rule:
durable state and Windows filesystem/ACL/startup mutations are not treated as
one fictional atomic transaction.

Future flow:
1. independently trust final pre-copy revalidation;
2. CAS-consume HUMAN_OWNER install authorization + install token and persist
   INSTALL_COMMITTED before any mutation;
3. create a deterministic append-only transaction journal plan;
4. execute at most one planned mutation at a time;
5. persist/read-back an observation after every mutation;
6. ambiguity blocks forward progress and requires reconciliation/rollback;
7. automatic continuation/retry after ambiguity is forbidden.

This module copies no files, changes no ACL/Registry/startup state, persists no
journal, consumes no token/authorization, spawns no process, calls no network/
GitHub and mutates no production state.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping

from atlasquant_aion_windows_install_token_preinstall_revalidation_v1 import (
    PREINSTALL_CONTRACT_SCHEMA,
    TOKEN_TEMPLATE_SCHEMA,
    READY_PREINSTALL_CONTRACT_STATE,
    READY_TOKEN_TEMPLATE_STATE,
)

SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_INSTALL_START_FILE_TRANSACTION_JOURNAL_V1"
CONTRACT_SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_INSTALL_CONSUMER_CONTRACT_V1"
COMMIT_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_COMMITMENT_CANDIDATE_V1"
COMMIT_ATTESTATION_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_COMMITMENT_PERSISTENCE_ATTESTATION_V1"
JOURNAL_PLAN_SCHEMA="ATLASQUANT_AION_WINDOWS_FILE_TRANSACTION_JOURNAL_PLAN_V1"
JOURNAL_ENTRY_SCHEMA="ATLASQUANT_AION_WINDOWS_FILE_TRANSACTION_JOURNAL_ENTRY_V1"
OP_OBSERVATION_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_OPERATION_OBSERVATION_V1"
RECOVERY_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_RECOVERY_CONTRACT_V1"
REVIEW_SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_INSTALL_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA="ATLASQUANT_AION_WINDOWS_ATOMIC_INSTALL_POLICY_V1"

READY_CONTRACT_STATE="ATOMIC_INSTALL_CONSUMER_CONTRACT_READY"
READY_COMMIT_STATE="READY_FOR_DURABLE_INSTALL_COMMITMENT_WRITE"
READY_COMMIT_ATTESTATION_SHAPE="INSTALL_COMMITMENT_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED"
READY_JOURNAL_PLAN_STATE="INSTALL_TRANSACTION_JOURNAL_PLAN_READY"
READY_JOURNAL_ENTRY_STATE="INSTALL_TRANSACTION_JOURNAL_ENTRY_CANDIDATE_READY"
CLASSIFIED_OPERATION_STATE="INSTALL_OPERATION_OBSERVATION_CLASSIFIED"
READY_RECOVERY_STATE="INSTALL_RECOVERY_CONTRACT_READY"
READY_REVIEW_STATE="READY_FOR_WINDOWS_ATOMIC_INSTALL_CONSUMER_IMPLEMENTATION"
BLOCKED_STATE="BLOCKED"

COMMIT_STATE="INSTALL_COMMITTED"
OP_APPLIED="INSTALL_OPERATION_APPLIED_CONFIRMED"
OP_FAILED="INSTALL_OPERATION_CONFIRMED_TERMINAL_FAILURE"
OP_UNKNOWN="INSTALL_OPERATION_OUTCOME_UNKNOWN"
ALLOWED_OPERATION_OUTCOMES=(OP_APPLIED,OP_FAILED,OP_UNKNOWN)

ALLOWED_OPERATION_KINDS=(
    "COPY_NEW_FILE",
    "REPLACE_EXISTING_FILE",
    "SET_OWNER_ACL",
    "CREATE_STARTUP_ENTRY",
)
MAX_JOURNAL_OPERATIONS=256

_SHA256_RE=re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")

def _clean(v:Any,n:int=1000)->str:
    return " ".join(str(v or "").replace("\x00","").split())[:n]

def _canonical(v:Any)->str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False,default=str)

def _digest(v:Any)->str:
    return "sha256:"+sha256(_canonical(v).encode("utf-8")).hexdigest()

def _sha256(v:Any)->str:
    t=_clean(v,90)
    return t if _SHA256_RE.fullmatch(t) else ""

def _identity(v:Any,n:int=240)->str:
    if type(v) is not str:return ""
    t=_clean(v,n)
    return t if t==v and _ID_RE.fullmatch(t) else ""

def build_atomic_install_contract(
    preinstall_contract:Mapping[str,Any]|None,
    token_template:Mapping[str,Any]|None,
    *,
    install_writer_manifest_digest:Any,
    journal_writer_manifest_digest:Any,
    mutation_executor_manifest_digest:Any,
    recovery_policy_digest:Any,
)->dict[str,Any]:
    pre=dict(preinstall_contract or {});token=dict(token_template or {});blockers=[]
    if pre.get("schema")!=PREINSTALL_CONTRACT_SCHEMA:blockers.append("PREINSTALL_CONTRACT_SCHEMA_MISMATCH")
    if pre.get("state")!=READY_PREINSTALL_CONTRACT_STATE:blockers.append("READY_PREINSTALL_CONTRACT_REQUIRED")
    if token.get("schema")!=TOKEN_TEMPLATE_SCHEMA:blockers.append("INSTALL_TOKEN_TEMPLATE_SCHEMA_MISMATCH")
    if token.get("state")!=READY_TOKEN_TEMPLATE_STATE:blockers.append("READY_UNISSUED_INSTALL_TOKEN_TEMPLATE_REQUIRED")
    for k in (
        "token_issued","token_signed","token_persisted","token_consumed",
        "owner_install_authorization_consumed","installation_authorized",
        "installation_started","files_copied","package_installed",
    ):
        if token.get(k) is not False:blockers.append("UPSTREAM_"+k.upper()+"_MUST_REMAIN_FALSE")
    vals={}
    for k,v,label in (
        ("install_writer_manifest_digest",install_writer_manifest_digest,"INSTALL_WRITER_MANIFEST_DIGEST_REQUIRED"),
        ("journal_writer_manifest_digest",journal_writer_manifest_digest,"JOURNAL_WRITER_MANIFEST_DIGEST_REQUIRED"),
        ("mutation_executor_manifest_digest",mutation_executor_manifest_digest,"MUTATION_EXECUTOR_MANIFEST_DIGEST_REQUIRED"),
        ("recovery_policy_digest",recovery_policy_digest,"RECOVERY_POLICY_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "preinstall_contract_digest":_sha256(pre.get("preinstall_contract_digest")),
        "token_template_digest":_sha256(token.get("token_template_digest")),
        "installation_gate_digest":_sha256(token.get("installation_gate_digest")),
        "package_attestation_digest":_sha256(token.get("package_attestation_digest")),
        "installation_manifest_digest":_sha256(token.get("installation_manifest_digest")),
        "installation_target_digest":_sha256(token.get("installation_target_digest")),
        "owner_acl_policy_digest":_sha256(token.get("owner_acl_policy_digest")),
        "startup_policy_digest":_sha256(token.get("startup_policy_digest")),
        "rollback_archive_digest":_sha256(token.get("rollback_archive_digest")),
        "rollback_manifest_digest":_sha256(token.get("rollback_manifest_digest")),
        "uninstall_manifest_digest":_sha256(token.get("uninstall_manifest_digest")),
        "install_plan_digest":_sha256(token.get("install_plan_digest")),
        "owner_install_authorization_verification_digest":_sha256(token.get("owner_install_authorization_verification_digest")),
        "install_auth_persistence_attestation_digest":_sha256(token.get("install_auth_persistence_attestation_digest")),
        "install_token_nonce_digest":_sha256(token.get("token_nonce_digest")),
        **vals,
        "commit_state":COMMIT_STATE,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":CONTRACT_SCHEMA,
        "state":READY_CONTRACT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "atomic_install_contract_digest":_digest(material) if not blockers else "",
        "write_ahead_install_commit_required":True,
        "owner_authorization_and_token_consumed_in_same_cas_required":True,
        "filesystem_mutation_in_database_transaction_claim_allowed":False,
        "journal_append_only_required":True,
        "one_mutation_at_a_time_required":True,
        "before_state_capture_required":True,
        "after_state_readback_required":True,
        "rollback_binding_required_for_every_mutation":True,
        "automatic_forward_retry_after_unknown_allowed":False,
        "automatic_forward_continue_after_unknown_allowed":False,
        "separate_reconciliation_required":True,
        "install_commitment_written":False,
        "owner_install_authorization_consumed":False,
        "install_token_consumed":False,
        "journal_persisted":False,
        "installation_started":False,
        "files_copied":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "startup_entry_created":False,
        "package_installed":False,
        "network_called":False,
    }

def build_install_commitment_candidate(
    contract:Mapping[str,Any]|None,
    *,
    installation_id:Any,
    owner_install_authorization_record_digest:Any,
    install_token_record_digest:Any,
    final_pre_copy_revalidation_digest:Any,
    expected_owner_auth_state:Any,
    expected_token_state:Any,
    expected_pre_install_revision:int,
)->dict[str,Any]:
    c=dict(contract or {});blockers=[]
    if c.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_ATOMIC_INSTALL_CONTRACT_REQUIRED")
    install_id=_identity(installation_id,180)
    if not install_id:blockers.append("INSTALLATION_ID_REQUIRED")
    vals={}
    for k,v,label in (
        ("owner_install_authorization_record_digest",owner_install_authorization_record_digest,"OWNER_INSTALL_AUTHORIZATION_RECORD_DIGEST_REQUIRED"),
        ("install_token_record_digest",install_token_record_digest,"INSTALL_TOKEN_RECORD_DIGEST_REQUIRED"),
        ("final_pre_copy_revalidation_digest",final_pre_copy_revalidation_digest,"FINAL_PRE_COPY_REVALIDATION_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    if _clean(expected_owner_auth_state,80)!="UNCONSUMED":blockers.append("OWNER_INSTALL_AUTH_EXPECTED_STATE_MUST_BE_UNCONSUMED")
    if _clean(expected_token_state,80)!="UNCONSUMED":blockers.append("INSTALL_TOKEN_EXPECTED_STATE_MUST_BE_UNCONSUMED")
    try:
        revision=int(expected_pre_install_revision)
        if revision<0:blockers.append("EXPECTED_PRE_INSTALL_REVISION_INVALID")
    except Exception:
        revision=-1;blockers.append("EXPECTED_PRE_INSTALL_REVISION_INVALID")
    identity={
        "installation_id":install_id,
        "atomic_install_contract_digest":_sha256(c.get("atomic_install_contract_digest")),
        "owner_install_authorization_record_digest":vals.get("owner_install_authorization_record_digest",""),
        "install_token_record_digest":vals.get("install_token_record_digest",""),
    }
    material={
        **identity,**vals,
        "record_key":_digest(identity),
        "expected_owner_auth_state":"UNCONSUMED",
        "expected_token_state":"UNCONSUMED",
        "post_commit_owner_auth_state":"CONSUMED_FOR_INSTALL",
        "post_commit_token_state":"CONSUMED_FOR_INSTALL",
        "post_commit_install_state":COMMIT_STATE,
        "expected_pre_install_revision":revision,
        "committed_install_revision_if_written":revision+1 if revision>=0 else -1,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":COMMIT_SCHEMA,
        "state":READY_COMMIT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "install_commitment_digest":_digest(material) if not blockers else "",
        "atomic_compare_and_set_required":True,
        "owner_install_authorization_consumed_if_written":True,
        "install_token_consumed_if_written":True,
        "install_record_persisted_if_written":True,
        "install_commitment_written":False,
        "owner_install_authorization_consumed":False,
        "install_token_consumed":False,
        "installation_started":False,
        "files_copied":False,
    }

def validate_future_install_commitment_attestation_shape(
    candidate:Mapping[str,Any]|None,
    **evidence:Any,
)->dict[str,Any]:
    row=dict(candidate or {});blockers=[]
    if row.get("state")!=READY_COMMIT_STATE:blockers.append("READY_INSTALL_COMMITMENT_CANDIDATE_REQUIRED")
    required=(
        "install_commitment_record_digest","writer_manifest_digest","write_receipt_digest",
        "cas_observation_digest","read_after_write_observation_digest","reopen_observation_digest",
        "owner_install_authorization_consumption_observation_digest","install_token_consumption_observation_digest",
    )
    vals={}
    for k in required:
        d=_sha256(evidence.get(k));vals[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    if evidence.get("caller_claims_commitment_trusted") is True:
        blockers.append("CALLER_INSTALL_COMMITMENT_TRUST_CLAIM_NOT_ACCEPTED")
    material={
        "install_commitment_digest":_sha256(row.get("install_commitment_digest")),
        "installation_id":row.get("installation_id"),
        **vals,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":COMMIT_ATTESTATION_SCHEMA,
        "state":READY_COMMIT_ATTESTATION_SHAPE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "commitment_attestation_candidate_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,
        "commitment_persisted_trusted":False,
        "cas_verified":False,
        "read_after_write_verified":False,
        "reopen_verified":False,
        "owner_install_authorization_consumption_verified":False,
        "install_token_consumption_verified":False,
        "journal_creation_allowed":False,
        "installation_started":False,
        "files_copied":False,
    }

def build_transaction_journal_plan(
    contract:Mapping[str,Any]|None,
    commitment:Mapping[str,Any]|None,
    operations:Iterable[Mapping[str,Any]]|None,
)->dict[str,Any]:
    c=dict(contract or {});commit=dict(commitment or {});blockers=[]
    if c.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_ATOMIC_INSTALL_CONTRACT_REQUIRED")
    if commit.get("state")!=READY_COMMIT_STATE:blockers.append("READY_INSTALL_COMMITMENT_CANDIDATE_REQUIRED")
    rows=[dict(x) for x in (operations or []) if isinstance(x,Mapping)]
    if not rows:blockers.append("INSTALL_JOURNAL_OPERATIONS_REQUIRED")
    if len(rows)>MAX_JOURNAL_OPERATIONS:blockers.append("INSTALL_JOURNAL_OPERATION_LIMIT_EXCEEDED")
    normalized=[];seen=set()
    for idx,row in enumerate(rows,1):
        op_id=_identity(row.get("operation_id"),160)
        kind=_clean(row.get("operation_kind"),80)
        if not op_id:blockers.append(f"JOURNAL_OPERATION_ID_REQUIRED:{idx}")
        if op_id in seen:blockers.append(f"DUPLICATE_JOURNAL_OPERATION_ID:{op_id}")
        seen.add(op_id)
        if kind not in ALLOWED_OPERATION_KINDS:blockers.append(f"JOURNAL_OPERATION_KIND_INVALID:{idx}")
        vals={}
        for k in (
            "target_digest","before_state_digest","intended_after_state_digest",
            "rollback_action_digest","source_artifact_digest",
        ):
            d=_sha256(row.get(k));vals[k]=d
            if not d:blockers.append(f"{k.upper()}_REQUIRED:{idx}")
        normalized.append({
            "sequence":idx,
            "operation_id":op_id,
            "operation_kind":kind,
            **vals,
        })
    genesis=_digest({
        "installation_id":commit.get("installation_id"),
        "install_commitment_digest":_sha256(commit.get("install_commitment_digest")),
        "journal_kind":"WINDOWS_INSTALL_FILE_TRANSACTION_V1",
    })
    material={
        "atomic_install_contract_digest":_sha256(c.get("atomic_install_contract_digest")),
        "install_commitment_digest":_sha256(commit.get("install_commitment_digest")),
        "installation_id":commit.get("installation_id"),
        "journal_genesis_digest":genesis,
        "operation_count":len(normalized),
        "operations":normalized,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":JOURNAL_PLAN_SCHEMA,
        "state":READY_JOURNAL_PLAN_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "journal_plan_digest":_digest(material) if not blockers else "",
        "append_only_required":True,
        "sequence_strictly_increasing_required":True,
        "before_state_capture_required":True,
        "after_state_readback_required":True,
        "rollback_binding_required":True,
        "operation_reorder_allowed":False,
        "operation_delete_allowed":False,
        "operation_replace_allowed":False,
        "journal_persisted":False,
        "installation_started":False,
        "filesystem_modified":False,
    }

def build_journal_entry_candidate(
    journal_plan:Mapping[str,Any]|None,
    *,
    sequence:int,
    previous_entry:Mapping[str,Any]|None=None,
    previous_entry_digest:Any="",
)->dict[str,Any]:
    plan=dict(journal_plan or {});prior=dict(previous_entry or {});blockers=[]
    if plan.get("state")!=READY_JOURNAL_PLAN_STATE:blockers.append("READY_INSTALL_JOURNAL_PLAN_REQUIRED")
    try:
        seq=int(sequence)
    except Exception:
        seq=-1
    ops=list(plan.get("operations") or [])
    if seq<1 or seq>len(ops):blockers.append("JOURNAL_ENTRY_SEQUENCE_INVALID")
    op=ops[seq-1] if 1<=seq<=len(ops) else {}
    if seq==1:
        prev=_sha256(previous_entry_digest)
        expected_prev=_sha256(plan.get("journal_genesis_digest"))
        if prior:
            blockers.append("FIRST_JOURNAL_ENTRY_MUST_NOT_HAVE_PRIOR_ENTRY")
        if prev!=expected_prev:
            blockers.append("FIRST_JOURNAL_ENTRY_MUST_BIND_GENESIS")
    else:
        if prior.get("schema")!=JOURNAL_ENTRY_SCHEMA:
            blockers.append("PRIOR_JOURNAL_ENTRY_SCHEMA_REQUIRED")
        if prior.get("state")!=READY_JOURNAL_ENTRY_STATE:
            blockers.append("READY_PRIOR_JOURNAL_ENTRY_REQUIRED")
        if prior.get("installation_id")!=plan.get("installation_id"):
            blockers.append("PRIOR_JOURNAL_ENTRY_INSTALLATION_MISMATCH")
        if _sha256(prior.get("journal_plan_digest"))!=_sha256(plan.get("journal_plan_digest")):
            blockers.append("PRIOR_JOURNAL_ENTRY_PLAN_MISMATCH")
        if int(prior.get("sequence") or -1)!=seq-1:
            blockers.append("PRIOR_JOURNAL_ENTRY_SEQUENCE_MISMATCH")
        expected_prev=_sha256(prior.get("journal_entry_digest"))
        prev=_sha256(previous_entry_digest) or expected_prev
        if not expected_prev:
            blockers.append("PRIOR_JOURNAL_ENTRY_DIGEST_REQUIRED")
        if prev!=expected_prev:
            blockers.append("PREVIOUS_JOURNAL_ENTRY_DIGEST_MISMATCH")
    material={
        "journal_plan_digest":_sha256(plan.get("journal_plan_digest")),
        "installation_id":plan.get("installation_id"),
        "sequence":seq,
        "operation_id":op.get("operation_id"),
        "operation_kind":op.get("operation_kind"),
        "target_digest":_sha256(op.get("target_digest")),
        "before_state_digest":_sha256(op.get("before_state_digest")),
        "intended_after_state_digest":_sha256(op.get("intended_after_state_digest")),
        "rollback_action_digest":_sha256(op.get("rollback_action_digest")),
        "source_artifact_digest":_sha256(op.get("source_artifact_digest")),
        "previous_entry_digest":prev,
        "expected_previous_entry_digest":expected_prev,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":JOURNAL_ENTRY_SCHEMA,
        "state":READY_JOURNAL_ENTRY_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "journal_entry_digest":_digest(material) if not blockers else "",
        "entry_persisted":False,
        "operation_started":False,
        "operation_applied":False,
        "filesystem_modified":False,
        "rollback_performed":False,
    }

def classify_future_operation_observation(
    entry:Mapping[str,Any]|None,
    *,
    requested_outcome:Any,
    operation_attempted:bool,
    before_state_observation_digest:Any="",
    mutation_write_observation_digest:Any="",
    after_state_observation_digest:Any="",
    rollback_material_presence_digest:Any="",
    terminal_failure_evidence_digest:Any="",
    ambiguity_evidence_digest:Any="",
)->dict[str,Any]:
    e=dict(entry or {});blockers=[]
    if e.get("state")!=READY_JOURNAL_ENTRY_STATE:blockers.append("READY_JOURNAL_ENTRY_REQUIRED")
    requested=_clean(requested_outcome,100)
    if requested not in ALLOWED_OPERATION_OUTCOMES:blockers.append("INSTALL_OPERATION_OUTCOME_INVALID")
    before=_sha256(before_state_observation_digest)
    write=_sha256(mutation_write_observation_digest)
    after=_sha256(after_state_observation_digest)
    rollback=_sha256(rollback_material_presence_digest)
    terminal=_sha256(terminal_failure_evidence_digest)
    ambiguity=_sha256(ambiguity_evidence_digest)
    positive=(
        operation_attempted is True
        and bool(before) and bool(write) and bool(after) and bool(rollback)
        and before==_sha256(e.get("before_state_digest"))
        and after==_sha256(e.get("intended_after_state_digest"))
    )
    if ambiguity:
        final=OP_UNKNOWN
    elif requested==OP_APPLIED:
        final=OP_APPLIED if positive else OP_UNKNOWN
    elif requested==OP_FAILED:
        final=OP_FAILED if operation_attempted is True and terminal and not write else OP_UNKNOWN
    else:
        final=OP_UNKNOWN
    material={
        "journal_entry_digest":_sha256(e.get("journal_entry_digest")),
        "installation_id":e.get("installation_id"),
        "sequence":e.get("sequence"),
        "operation_id":e.get("operation_id"),
        "requested_outcome":requested,
        "final_outcome":final,
        "operation_attempted":operation_attempted is True,
        "before_state_observation_digest":before,
        "mutation_write_observation_digest":write,
        "after_state_observation_digest":after,
        "rollback_material_presence_digest":rollback,
        "terminal_failure_evidence_digest":terminal,
        "ambiguity_evidence_digest":ambiguity,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":OP_OBSERVATION_SCHEMA,
        "state":CLASSIFIED_OPERATION_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "operation_observation_digest":_digest(material) if not blockers else "",
        "operation_applied_confirmed":final==OP_APPLIED,
        "operation_terminal_failure_confirmed":final==OP_FAILED,
        "operation_outcome_unknown":final==OP_UNKNOWN,
        "forward_progress_allowed":final==OP_APPLIED,
        "automatic_retry_allowed":False,
        "automatic_continue_allowed":False if final!=OP_APPLIED else True,
        "reconciliation_required":final==OP_UNKNOWN,
        "rollback_required":final in (OP_UNKNOWN,OP_FAILED),
        "observation_is_physical_truth_trusted":False,
    }

def build_recovery_contract(
    journal_plan:Mapping[str,Any]|None,
    operation_observation:Mapping[str,Any]|None,
    *,
    journal_reopen_policy_digest:Any,
    filesystem_readback_policy_digest:Any,
    rollback_executor_manifest_digest:Any,
)->dict[str,Any]:
    plan=dict(journal_plan or {});obs=dict(operation_observation or {});blockers=[]
    if plan.get("state")!=READY_JOURNAL_PLAN_STATE:blockers.append("READY_INSTALL_JOURNAL_PLAN_REQUIRED")
    if obs.get("state")!=CLASSIFIED_OPERATION_STATE:blockers.append("CLASSIFIED_INSTALL_OPERATION_OBSERVATION_REQUIRED")
    if obs.get("final_outcome") not in (OP_UNKNOWN,OP_FAILED):
        blockers.append("UNKNOWN_OR_FAILED_INSTALL_OPERATION_REQUIRED")
    vals={}
    for k,v,label in (
        ("journal_reopen_policy_digest",journal_reopen_policy_digest,"JOURNAL_REOPEN_POLICY_DIGEST_REQUIRED"),
        ("filesystem_readback_policy_digest",filesystem_readback_policy_digest,"FILESYSTEM_READBACK_POLICY_DIGEST_REQUIRED"),
        ("rollback_executor_manifest_digest",rollback_executor_manifest_digest,"ROLLBACK_EXECUTOR_MANIFEST_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    sequence=int(obs.get("sequence") or 0)
    rollback_sequences=list(range(max(sequence,0),0,-1))
    material={
        "journal_plan_digest":_sha256(plan.get("journal_plan_digest")),
        "operation_observation_digest":_sha256(obs.get("operation_observation_digest")),
        "installation_id":plan.get("installation_id"),
        "failed_or_unknown_sequence":sequence,
        "rollback_sequences":rollback_sequences,
        **vals,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":RECOVERY_SCHEMA,
        "state":READY_RECOVERY_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "recovery_contract_digest":_digest(material) if not blockers else "",
        "journal_reopen_required":True,
        "filesystem_readback_required":True,
        "rollback_reverse_order_required":True,
        "automatic_forward_retry_allowed":False,
        "automatic_forward_continue_allowed":False,
        "new_installation_authorized":False,
        "rollback_authorized_by_this_contract":False,
        "rollback_performed":False,
        "filesystem_readback_executed":False,
        "journal_reopen_executed":False,
        "reconciliation_completed":False,
        "package_installed":False,
    }

def build_implementation_review(
    contract:Mapping[str,Any]|None,
    journal_plan:Mapping[str,Any]|None,
    *,
    install_commit_writer_source_digest:Any,
    journal_writer_source_digest:Any,
    mutation_executor_source_digest:Any,
    recovery_reconciler_source_digest:Any,
)->dict[str,Any]:
    c=dict(contract or {});j=dict(journal_plan or {});blockers=[]
    if c.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_ATOMIC_INSTALL_CONTRACT_REQUIRED")
    if j.get("state")!=READY_JOURNAL_PLAN_STATE:blockers.append("READY_INSTALL_JOURNAL_PLAN_REQUIRED")
    vals={}
    for k,v,label in (
        ("install_commit_writer_source_digest",install_commit_writer_source_digest,"INSTALL_COMMIT_WRITER_SOURCE_DIGEST_REQUIRED"),
        ("journal_writer_source_digest",journal_writer_source_digest,"JOURNAL_WRITER_SOURCE_DIGEST_REQUIRED"),
        ("mutation_executor_source_digest",mutation_executor_source_digest,"MUTATION_EXECUTOR_SOURCE_DIGEST_REQUIRED"),
        ("recovery_reconciler_source_digest",recovery_reconciler_source_digest,"RECOVERY_RECONCILER_SOURCE_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "atomic_install_contract_digest":_sha256(c.get("atomic_install_contract_digest")),
        "journal_plan_digest":_sha256(j.get("journal_plan_digest")),
        **vals,
        "next_pc_phase":"IMPLEMENT_WRITE_AHEAD_INSTALL_COMMIT_AND_APPEND_ONLY_FILE_JOURNAL_WITH_SYNTHETIC_TARGET",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":REVIEW_SCHEMA,
        "state":READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "implementation_review_digest":_digest(material) if not blockers else "",
        "install_commit_writer_implemented":False,
        "journal_writer_implemented":False,
        "mutation_executor_implemented":False,
        "recovery_reconciler_implemented":False,
        "install_commitment_written":False,
        "owner_install_authorization_consumed":False,
        "install_token_consumed":False,
        "journal_persisted":False,
        "installation_started":False,
        "files_copied":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "windows_registry_modified":False,
        "startup_entry_created":False,
        "rollback_performed":False,
        "package_installed":False,
        "network_called":False,
        "github_api_called":False,
    }

def atomic_install_policy()->dict[str,Any]:
    return {
        "schema":POLICY_SCHEMA,
        "write_ahead_install_commit_required":True,
        "owner_authorization_and_token_consumed_in_same_cas_required":True,
        "filesystem_mutation_in_database_transaction_claim_allowed":False,
        "journal_append_only_required":True,
        "journal_sequence_strict_required":True,
        "operation_reorder_allowed":False,
        "operation_delete_allowed":False,
        "operation_replace_allowed":False,
        "one_mutation_at_a_time_required":True,
        "before_state_capture_required":True,
        "after_state_readback_required":True,
        "rollback_binding_required_for_every_mutation":True,
        "automatic_forward_retry_after_unknown_allowed":False,
        "automatic_forward_continue_after_unknown_allowed":False,
        "unknown_requires_reconciliation":True,
        "unknown_requires_rollback_review":True,
        "terminal_failure_requires_authoritative_evidence":True,
        "ambiguity_overrides_requested_success":True,
        "rollback_reverse_order_required":True,
        "generic_chat_is_install_mutation_authority":False,
        "install_commit_writer_implemented":False,
        "journal_writer_implemented":False,
        "mutation_executor_implemented":False,
        "recovery_reconciler_implemented":False,
        "install_commitment_written":False,
        "owner_install_authorization_consumed":False,
        "install_token_consumed":False,
        "journal_persisted":False,
        "installation_started":False,
        "files_copied":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "windows_registry_modified":False,
        "startup_entry_created":False,
        "scheduled_task_installed":False,
        "windows_service_installed":False,
        "rollback_performed":False,
        "package_installed":False,
        "process_spawned":False,
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
