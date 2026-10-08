"""AION Windows Build Token + Prelaunch Revalidation Contract V1.

Design-only. Defines the final prelaunch snapshot and an unissued, single-use
build-token template. It never trusts caller claims as physical truth and never
issues/consumes a token, spawns a process, starts a build, writes persistence,
calls network/GitHub, or mutates production.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_windows_physical_verification_build_authorization_gate_v1 import (
    GATE_CONTRACT_SCHEMA,
    READY_CONTRACT_STATE,
    PURPOSE as BUILD_AUTH_PURPOSE,
)

SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_TOKEN_PRELAUNCH_REVALIDATION_V1"
PRELAUNCH_CONTRACT_SCHEMA="ATLASQUANT_AION_WINDOWS_PRELAUNCH_REVALIDATION_CONTRACT_V1"
PRELAUNCH_SNAPSHOT_SCHEMA="ATLASQUANT_AION_WINDOWS_PRELAUNCH_REVALIDATION_SNAPSHOT_V1"
TOKEN_TEMPLATE_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_TOKEN_TEMPLATE_V1"
TOKEN_ATTESTATION_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_TOKEN_ISSUANCE_ATTESTATION_V1"
REVIEW_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_TOKEN_PRELAUNCH_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_TOKEN_PRELAUNCH_POLICY_V1"

READY_PRELAUNCH_CONTRACT_STATE="WINDOWS_PRELAUNCH_REVALIDATION_CONTRACT_READY"
READY_PRELAUNCH_SHAPE_STATE="PRELAUNCH_SNAPSHOT_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED"
READY_TOKEN_TEMPLATE_STATE="BUILD_TOKEN_TEMPLATE_READY_UNISSUED"
READY_TOKEN_ATTESTATION_SHAPE_STATE="BUILD_TOKEN_ISSUANCE_ATTESTATION_SHAPE_VALID_BUT_UNTRUSTED"
READY_REVIEW_STATE="READY_FOR_WINDOWS_BUILD_TOKEN_PRELAUNCH_IMPLEMENTATION"
BLOCKED_STATE="BLOCKED"

TOKEN_PURPOSE="SINGLE_USE_WINDOWS_LOCAL_AGENT_BUILD_LAUNCH"
TOKEN_AUDIENCE="AION_WINDOWS_OFFLINE_BUILD_SANDBOX"
MAX_PRELAUNCH_SNAPSHOT_AGE_SECONDS=10
MAX_BUILD_TOKEN_LIFETIME_SECONDS=15
MAX_CLOCK_SKEW_SECONDS=2
EXPECTED_VERIFIED_REQUIREMENTS=12

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

def build_prelaunch_contract(gate_contract:Mapping[str,Any]|None,**inputs:Any)->dict[str,Any]:
    gate=dict(gate_contract or {})
    blockers=[]
    if gate.get("schema")!=GATE_CONTRACT_SCHEMA:blockers.append("BUILD_AUTHORIZATION_GATE_SCHEMA_MISMATCH")
    if gate.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_BUILD_AUTHORIZATION_GATE_REQUIRED")
    for k in ("build_authorized","build_token_issued","build_started"):
        if gate.get(k) is not False:blockers.append("UPSTREAM_"+k.upper()+"_MUST_REMAIN_FALSE")
    required=(
        "physical_certificate_verifier_digest","authorization_persistence_verifier_digest",
        "token_signer_manifest_digest","token_signer_key_fingerprint","launch_writer_manifest_digest",
        "launch_binary_path_digest","launch_binary_sha256","build_script_sha256",
        "safety_stop_policy_digest","circuit_breaker_policy_digest","prelaunch_safety_policy_digest",
    )
    digests={}
    for k in required:
        d=_sha256(inputs.get(k));digests[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    material={
        "purpose":TOKEN_PURPOSE,"audience":TOKEN_AUDIENCE,"build_authorization_purpose":BUILD_AUTH_PURPOSE,
        "gate_contract_digest":_sha256(gate.get("gate_contract_digest")),
        "reproducible_build_recipe_digest":_sha256(gate.get("reproducible_build_recipe_digest")),
        "offline_input_promotion_digest":_sha256(gate.get("offline_input_promotion_digest")),
        "sandbox_preflight_digest":_sha256(gate.get("sandbox_preflight_digest")),
        "package_manifest_digest":_sha256(gate.get("package_manifest_digest")),
        "package_attestation_policy_digest":_sha256(gate.get("package_attestation_policy_digest")),
        "owner_binding_digest":_sha256(gate.get("owner_binding_digest")),
        "evidence_store_contract_digest":_sha256(gate.get("evidence_store_contract_digest")),
        "receipt_persistence_contract_digest":_sha256(gate.get("receipt_persistence_contract_digest")),
        **digests,
        "max_prelaunch_snapshot_age_seconds":MAX_PRELAUNCH_SNAPSHOT_AGE_SECONDS,
        "max_build_token_lifetime_seconds":MAX_BUILD_TOKEN_LIFETIME_SECONDS,
        "required_verified_requirements":EXPECTED_VERIFIED_REQUIREMENTS,
    }
    blockers=list(dict.fromkeys(blockers))
    return {"schema":PRELAUNCH_CONTRACT_SCHEMA,"state":READY_PRELAUNCH_CONTRACT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,"prelaunch_contract_digest":_digest(material) if not blockers else "",
        "prelaunch_revalidation_implemented":False,"prelaunch_revalidation_executed":False,
        "external_trust_verified":False,"safety_stop_physically_checked":False,
        "circuit_breaker_physically_checked":False,"build_token_implemented":False,
        "build_token_issued":False,"build_token_signed":False,"build_token_consumed":False,
        "build_authorized":False,"build_started":False,"process_spawned":False,
        "filesystem_modified":False,"network_called":False}

def validate_future_prelaunch_snapshot_shape(contract:Mapping[str,Any]|None,snapshot:Mapping[str,Any]|None,*,now:Any)->dict[str,Any]:
    row=dict(contract or {});snap=dict(snapshot or {});blockers=[]
    if row.get("state")!=READY_PRELAUNCH_CONTRACT_STATE:blockers.append("READY_PRELAUNCH_CONTRACT_REQUIRED")
    if snap.get("schema")!=PRELAUNCH_SNAPSHOT_SCHEMA:blockers.append("PRELAUNCH_SNAPSHOT_SCHEMA_MISMATCH")
    if snap.get("state")!="PRELAUNCH_REVALIDATION_VERIFIED":blockers.append("PRELAUNCH_REVALIDATION_VERIFIED_STATE_REQUIRED")
    exact=("gate_contract_digest","reproducible_build_recipe_digest","offline_input_promotion_digest",
           "sandbox_preflight_digest","package_manifest_digest","package_attestation_policy_digest",
           "owner_binding_digest","evidence_store_contract_digest","receipt_persistence_contract_digest",
           "launch_binary_path_digest","launch_binary_sha256","build_script_sha256",
           "safety_stop_policy_digest","circuit_breaker_policy_digest","prelaunch_safety_policy_digest")
    for k in exact:
        if _sha256(snap.get(k))!=_sha256(row.get(k)):blockers.append("PRELAUNCH_BINDING_MISMATCH:"+k)
    evidence=("snapshot_digest","physical_certificate_digest","verification_receipt_digest",
              "verification_receipt_signature_digest","receipt_persistence_attestation_digest",
              "receipt_reopen_observation_digest","evidence_chain_digest","evidence_chain_reopen_observation_digest",
              "collector_manifest_digest","verifier_manifest_digest","host_binding_digest",
              "owner_authorization_verification_digest","authorization_persistence_attestation_digest",
              "authorization_record_digest","authorization_reopen_observation_digest",
              "nonce_registry_record_digest","nonce_replay_guard_observation_digest",
              "nonce_single_use_observation_digest","environment_contract_digest","process_contract_digest",
              "network_contract_digest","safety_stop_observation_digest","circuit_breaker_observation_digest",
              "safety_state_digest")
    for k in evidence:
        if not _sha256(snap.get(k)):blockers.append(k.upper()+"_REQUIRED")
    if int(snap.get("verified_total") or -1)!=12:blockers.append("ALL_12_REQUIREMENTS_MUST_BE_REVERIFIED")
    if int(snap.get("required_total") or -1)!=12:blockers.append("PRELAUNCH_REQUIRED_TOTAL_INVALID")
    true_fields=(
        "physical_certificate_trust_verified","all_requirements_reverified",
        "verification_receipt_signature_reverified","verification_receipt_persistence_reverified",
        "receipt_reopen_reverified","evidence_chain_reopen_reverified","owner_signature_reverified",
        "owner_authorization_persistence_reverified","owner_authorization_reopen_reverified",
        "owner_authorization_fresh","owner_authorization_unconsumed",
        "persistent_nonce_replay_guard_reverified","nonce_single_use_reverified",
        "host_binding_reverified","package_manifest_reverified","build_recipe_reverified",
        "offline_input_promotion_reverified","sandbox_preflight_reverified","pinned_python_binary_reverified",
        "build_script_reverified","environment_scrub_reverified","process_allowlist_reverified",
        "network_deny_reverified","safety_stop_armed","circuit_breaker_armed",
        "circuit_breaker_healthy","no_new_safety_blockers")
    for k in true_fields:
        if snap.get(k) is not True:blockers.append("PRELAUNCH_REQUIRED_TRUE:"+k)
    if snap.get("safety_stop_engaged") is not False:blockers.append("SAFETY_STOP_MUST_NOT_BE_ENGAGED")
    if snap.get("authorization_consumed") is not False:blockers.append("OWNER_AUTHORIZATION_ALREADY_CONSUMED")
    if snap.get("build_started") is not False:blockers.append("BUILD_ALREADY_STARTED")
    try:
        captured=_aware(snap.get("captured_at"));current=_aware(now);age=(current-captured).total_seconds()
        if age < -MAX_CLOCK_SKEW_SECONDS:blockers.append("PRELAUNCH_SNAPSHOT_FROM_FUTURE")
        if age > MAX_PRELAUNCH_SNAPSHOT_AGE_SECONDS:blockers.append("PRELAUNCH_SNAPSHOT_STALE")
    except Exception:
        captured=current=None;blockers.append("PRELAUNCH_TIME_INVALID")
    material={
        "prelaunch_contract_digest":_sha256(row.get("prelaunch_contract_digest")),
        "snapshot_digest":_sha256(snap.get("snapshot_digest")),
        "physical_certificate_digest":_sha256(snap.get("physical_certificate_digest")),
        "verification_receipt_digest":_sha256(snap.get("verification_receipt_digest")),
        "evidence_chain_digest":_sha256(snap.get("evidence_chain_digest")),
        "owner_authorization_verification_digest":_sha256(snap.get("owner_authorization_verification_digest")),
        "authorization_persistence_attestation_digest":_sha256(snap.get("authorization_persistence_attestation_digest")),
        "nonce_registry_record_digest":_sha256(snap.get("nonce_registry_record_digest")),
        "host_binding_digest":_sha256(snap.get("host_binding_digest")),
        "safety_state_digest":_sha256(snap.get("safety_state_digest")),
        "captured_at":captured.isoformat() if captured else "","checked_at":current.isoformat() if current else ""}
    blockers=list(dict.fromkeys(blockers))
    return {"schema":PRELAUNCH_SNAPSHOT_SCHEMA,"state":READY_PRELAUNCH_SHAPE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,"prelaunch_snapshot_review_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,"external_trust_verified_by_this_module":False,
        "physical_revalidation_trusted":False,"authorization_persistence_trusted":False,
        "nonce_state_trusted":False,"safety_stop_state_trusted":False,
        "circuit_breaker_state_trusted":False,"build_token_issuance_allowed":False,
        "build_authorized":False,"build_started":False}

def build_unissued_token_template(contract:Mapping[str,Any]|None,prelaunch_review:Mapping[str,Any]|None,*,token_id:Any,token_nonce_digest:Any,issued_at:Any,expires_at:Any)->dict[str,Any]:
    row=dict(contract or {});review=dict(prelaunch_review or {});blockers=[]
    if row.get("state")!=READY_PRELAUNCH_CONTRACT_STATE:blockers.append("READY_PRELAUNCH_CONTRACT_REQUIRED")
    if review.get("state")!=READY_PRELAUNCH_SHAPE_STATE:blockers.append("VALID_PRELAUNCH_SNAPSHOT_SHAPE_REQUIRED")
    token=_identity(token_id,180)
    if not token:blockers.append("BUILD_TOKEN_ID_REQUIRED")
    nonce=_sha256(token_nonce_digest)
    if not nonce:blockers.append("BUILD_TOKEN_NONCE_DIGEST_REQUIRED")
    try:
        issued=_aware(issued_at);expires=_aware(expires_at);lifetime=(expires-issued).total_seconds()
        if lifetime<=0:blockers.append("BUILD_TOKEN_LIFETIME_INVALID")
        if lifetime>MAX_BUILD_TOKEN_LIFETIME_SECONDS:blockers.append("BUILD_TOKEN_LIFETIME_TOO_LONG")
    except Exception:
        issued=expires=None;blockers.append("BUILD_TOKEN_TIME_INVALID")
    material={
        "token_id":token,"purpose":TOKEN_PURPOSE,"audience":TOKEN_AUDIENCE,
        "prelaunch_contract_digest":_sha256(row.get("prelaunch_contract_digest")),
        "prelaunch_snapshot_review_digest":_sha256(review.get("prelaunch_snapshot_review_digest")),
        "gate_contract_digest":_sha256(row.get("gate_contract_digest")),
        "reproducible_build_recipe_digest":_sha256(row.get("reproducible_build_recipe_digest")),
        "offline_input_promotion_digest":_sha256(row.get("offline_input_promotion_digest")),
        "sandbox_preflight_digest":_sha256(row.get("sandbox_preflight_digest")),
        "package_manifest_digest":_sha256(row.get("package_manifest_digest")),
        "owner_binding_digest":_sha256(row.get("owner_binding_digest")),
        "physical_certificate_digest":_sha256(review.get("physical_certificate_digest")),
        "verification_receipt_digest":_sha256(review.get("verification_receipt_digest")),
        "evidence_chain_digest":_sha256(review.get("evidence_chain_digest")),
        "owner_authorization_verification_digest":_sha256(review.get("owner_authorization_verification_digest")),
        "authorization_persistence_attestation_digest":_sha256(review.get("authorization_persistence_attestation_digest")),
        "nonce_registry_record_digest":_sha256(review.get("nonce_registry_record_digest")),
        "host_binding_digest":_sha256(review.get("host_binding_digest")),
        "launch_binary_path_digest":_sha256(row.get("launch_binary_path_digest")),
        "launch_binary_sha256":_sha256(row.get("launch_binary_sha256")),
        "build_script_sha256":_sha256(row.get("build_script_sha256")),
        "token_signer_manifest_digest":_sha256(row.get("token_signer_manifest_digest")),
        "token_signer_key_fingerprint":_sha256(row.get("token_signer_key_fingerprint")),
        "token_nonce_digest":nonce,"issued_at":issued.isoformat() if issued else "",
        "expires_at":expires.isoformat() if expires else "","max_uses":1,"max_process_count":1,"max_child_process_count":0}
    blockers=list(dict.fromkeys(blockers))
    return {"schema":TOKEN_TEMPLATE_SCHEMA,"state":READY_TOKEN_TEMPLATE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,"token_template_digest":_digest(material) if not blockers else "",
        "single_use":True,"requires_atomic_authorization_consumption_with_launch":True,
        "requires_atomic_token_consumption_with_launch":True,"requires_final_pre_spawn_revalidation":True,
        "token_implemented":False,"token_issued":False,"token_signed":False,"token_persisted":False,
        "token_consumed":False,"owner_authorization_consumed":False,"launch_authorized":False,
        "build_authorized":False,"build_started":False,"process_spawned":False}

def validate_future_token_issuance_attestation_shape(token_template:Mapping[str,Any]|None,**evidence:Any)->dict[str,Any]:
    token=dict(token_template or {});blockers=[]
    if token.get("state")!=READY_TOKEN_TEMPLATE_STATE:blockers.append("READY_UNISSUED_TOKEN_TEMPLATE_REQUIRED")
    if evidence.get("owner_authorization_consumed") is not False:blockers.append("OWNER_AUTHORIZATION_MUST_BE_UNCONSUMED_BEFORE_LAUNCH")
    if evidence.get("token_consumed") is not False:blockers.append("BUILD_TOKEN_MUST_BE_UNCONSUMED_BEFORE_LAUNCH")
    required=("token_digest","token_signature_digest","token_signer_manifest_digest","token_record_digest",
              "token_nonce_record_digest","write_receipt_digest","cas_observation_digest",
              "read_after_write_observation_digest","reopen_observation_digest")
    vals={}
    for k in required:
        d=_sha256(evidence.get(k));vals[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    if vals.get("token_signer_manifest_digest")!=_sha256(token.get("token_signer_manifest_digest")):
        blockers.append("TOKEN_SIGNER_MANIFEST_BINDING_MISMATCH")
    if evidence.get("caller_claims_token_trusted") is True:blockers.append("CALLER_BUILD_TOKEN_TRUST_CLAIM_NOT_ACCEPTED")
    material={"token_template_digest":_sha256(token.get("token_template_digest")),**vals,
              "owner_authorization_consumed":False,"token_consumed":False}
    blockers=list(dict.fromkeys(blockers))
    return {"schema":TOKEN_ATTESTATION_SCHEMA,"state":READY_TOKEN_ATTESTATION_SHAPE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,"token_issuance_attestation_candidate_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,"token_signature_verified":False,"token_persisted_trusted":False,
        "token_nonce_single_use_verified":False,"cas_verified":False,"read_after_write_verified":False,
        "reopen_verified":False,"final_pre_spawn_revalidation_verified":False,
        "owner_authorization_consumed":False,"token_consumed":False,"launch_authorized":False,
        "build_authorized":False,"build_started":False,"process_spawned":False}

def build_implementation_review(contract:Mapping[str,Any]|None,token_template:Mapping[str,Any]|None,**designs:Any)->dict[str,Any]:
    row=dict(contract or {});token=dict(token_template or {});blockers=[]
    if row.get("state")!=READY_PRELAUNCH_CONTRACT_STATE:blockers.append("READY_PRELAUNCH_CONTRACT_REQUIRED")
    if token.get("state")!=READY_TOKEN_TEMPLATE_STATE:blockers.append("READY_UNISSUED_TOKEN_TEMPLATE_REQUIRED")
    required=("prelaunch_verifier_source_digest","token_signer_source_digest","token_store_writer_design_digest",
              "atomic_launch_consumer_design_digest","final_pre_spawn_revalidation_design_digest")
    vals={}
    for k in required:
        d=_sha256(designs.get(k));vals[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    material={"prelaunch_contract_digest":_sha256(row.get("prelaunch_contract_digest")),
              "token_template_digest":_sha256(token.get("token_template_digest")),**vals,
              "next_pc_phase":"IMPLEMENT_SINGLE_USE_BUILD_TOKEN_AND_FINAL_PRE_SPAWN_REVALIDATION"}
    blockers=list(dict.fromkeys(blockers))
    return {"schema":REVIEW_SCHEMA,"state":READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,"implementation_review_digest":_digest(material) if not blockers else "",
        "prelaunch_verifier_implemented":False,"prelaunch_revalidation_executed":False,
        "token_signer_implemented":False,"token_store_writer_implemented":False,
        "atomic_launch_consumer_implemented":False,"final_pre_spawn_revalidation_implemented":False,
        "build_token_implemented":False,"build_token_issued":False,"build_token_signed":False,
        "build_token_persisted":False,"build_token_consumed":False,"owner_authorization_consumed":False,
        "launch_authorized":False,"build_authorized":False,"build_started":False,"process_spawned":False,
        "filesystem_modified":False,"network_called":False,"github_api_called":False,
        "live_repository_mutation_performed":False}

def build_token_prelaunch_policy()->dict[str,Any]:
    return {"schema":POLICY_SCHEMA,"token_purpose":TOKEN_PURPOSE,"token_audience":TOKEN_AUDIENCE,
        "required_verified_requirements":12,"max_prelaunch_snapshot_age_seconds":10,
        "max_build_token_lifetime_seconds":15,"prelaunch_revalidation_required":True,
        "final_pre_spawn_revalidation_required":True,"same_host_required":True,"same_recipe_required":True,
        "same_offline_inputs_required":True,"same_sandbox_required":True,"same_package_manifest_required":True,
        "same_owner_authorization_required":True,"same_physical_certificate_required":True,
        "same_verification_receipt_required":True,"same_evidence_chain_required":True,
        "network_deny_reverification_required":True,"safety_stop_armed_required":True,
        "safety_stop_must_not_be_engaged":True,"circuit_breaker_armed_required":True,
        "circuit_breaker_healthy_required":True,"token_single_use_required":True,
        "token_signature_required":True,"token_persistence_required":True,"token_cas_required":True,
        "token_read_after_write_required":True,"token_reopen_required":True,"token_nonce_single_use_required":True,
        "atomic_owner_authorization_consumption_with_launch_required":True,
        "atomic_token_consumption_with_launch_required":True,"caller_prelaunch_claim_is_authority":False,
        "caller_token_trust_claim_is_authority":False,"generic_chat_is_launch_authority":False,
        "prelaunch_revalidation_implemented":False,"prelaunch_revalidation_executed":False,
        "prelaunch_external_trust_verified":False,"token_signer_implemented":False,
        "build_token_implemented":False,"build_token_issued":False,"build_token_signed":False,
        "build_token_persisted":False,"build_token_consumed":False,"owner_authorization_consumed":False,
        "launch_authorized":False,"build_authorized":False,"build_started":False,"package_built":False,
        "package_installed":False,"process_spawned":False,"filesystem_modified":False,"network_called":False,
        "github_api_called":False,"live_repository_mutation_authorized":False,
        "live_repository_mutation_performed":False,"production_repository_mutation_performed":False,
        "deploy_executed":False,"worker_activated":False,"provider_activated":False,
        "production_persistence_activated":False}

__all__=[name for name in globals() if name.isupper() or name.startswith("build_") or name.startswith("validate_")]
