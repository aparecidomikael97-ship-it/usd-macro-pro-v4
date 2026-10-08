"""AION Windows Install Token + Preinstall Revalidation Contract V1.

Design-only final logical barrier before any future Windows installation can
copy its first file.

Defines:
- a fresh preinstall revalidation contract/snapshot;
- an unissued, single-use install-token template;
- the future install-token issuance/persistence attestation shape;
- a PC-side implementation review.

It never trusts caller booleans as physical truth and never issues/signs/
persists/consumes a token, copies files, modifies ACL/Registry/startup, starts
installation, spawns a process, calls network/GitHub, deploys, or mutates
production.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_windows_package_attestation_persistence_install_auth_gate_v1 import (
    INSTALL_GATE_SCHEMA,
    READY_INSTALL_GATE_STATE,
    PURPOSE as INSTALL_AUTH_PURPOSE,
)

SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_TOKEN_PREINSTALL_REVALIDATION_V1"
PREINSTALL_CONTRACT_SCHEMA="ATLASQUANT_AION_WINDOWS_PREINSTALL_REVALIDATION_CONTRACT_V1"
PREINSTALL_SNAPSHOT_SCHEMA="ATLASQUANT_AION_WINDOWS_PREINSTALL_REVALIDATION_SNAPSHOT_V1"
TOKEN_TEMPLATE_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_TOKEN_TEMPLATE_V1"
TOKEN_ATTESTATION_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_TOKEN_ISSUANCE_ATTESTATION_V1"
REVIEW_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_TOKEN_PREINSTALL_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALL_TOKEN_PREINSTALL_POLICY_V1"

READY_PREINSTALL_CONTRACT_STATE="WINDOWS_PREINSTALL_REVALIDATION_CONTRACT_READY"
READY_PREINSTALL_SHAPE_STATE="PREINSTALL_SNAPSHOT_SHAPE_VALID_BUT_EXTERNAL_TRUST_REQUIRED"
READY_TOKEN_TEMPLATE_STATE="INSTALL_TOKEN_TEMPLATE_READY_UNISSUED"
READY_TOKEN_ATTESTATION_SHAPE_STATE="INSTALL_TOKEN_ISSUANCE_ATTESTATION_SHAPE_VALID_BUT_UNTRUSTED"
READY_REVIEW_STATE="READY_FOR_WINDOWS_INSTALL_TOKEN_PREINSTALL_IMPLEMENTATION"
BLOCKED_STATE="BLOCKED"

TOKEN_PURPOSE="SINGLE_USE_WINDOWS_LOCAL_AGENT_INSTALLATION"
TOKEN_AUDIENCE="AION_WINDOWS_OWNER_LOCAL_INSTALLER"
MAX_PREINSTALL_SNAPSHOT_AGE_SECONDS=10
MAX_INSTALL_TOKEN_LIFETIME_SECONDS=15
MAX_CLOCK_SKEW_SECONDS=2

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

def _aware(v:Any)->datetime:
    dt=v if isinstance(v,datetime) else datetime.fromisoformat(str(v).replace("Z","+00:00"))
    if dt.tzinfo is None: raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)

def build_preinstall_contract(gate:Mapping[str,Any]|None,**inputs:Any)->dict[str,Any]:
    g=dict(gate or {});blockers=[]
    if g.get("schema")!=INSTALL_GATE_SCHEMA:blockers.append("INSTALLATION_GATE_SCHEMA_MISMATCH")
    if g.get("state")!=READY_INSTALL_GATE_STATE:blockers.append("READY_INSTALLATION_GATE_REQUIRED")
    for k in ("installation_authorized","install_token_issued","installation_started","package_installed"):
        if g.get(k) is not False:blockers.append("UPSTREAM_"+k.upper()+"_MUST_REMAIN_FALSE")
    required=(
        "package_persistence_verifier_digest",
        "install_authorization_persistence_verifier_digest",
        "token_signer_manifest_digest",
        "token_signer_key_fingerprint",
        "install_writer_manifest_digest",
        "target_state_verifier_digest",
        "rollback_verifier_digest",
        "safety_stop_policy_digest",
        "circuit_breaker_policy_digest",
        "preinstall_safety_policy_digest",
    )
    vals={}
    for k in required:
        d=_sha256(inputs.get(k));vals[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    material={
        "purpose":TOKEN_PURPOSE,
        "audience":TOKEN_AUDIENCE,
        "install_authorization_purpose":INSTALL_AUTH_PURPOSE,
        "installation_gate_digest":_sha256(g.get("installation_gate_digest")),
        "persistence_contract_digest":_sha256(g.get("persistence_contract_digest")),
        "package_attestation_digest":_sha256(g.get("package_attestation_digest")),
        "installation_manifest_digest":_sha256(g.get("installation_manifest_digest")),
        "archive_digest":_sha256(g.get("archive_digest")),
        "installation_target_digest":_sha256(g.get("installation_target_digest")),
        "owner_acl_policy_digest":_sha256(g.get("owner_acl_policy_digest")),
        "startup_policy_digest":_sha256(g.get("startup_policy_digest")),
        "rollback_archive_digest":_sha256(g.get("rollback_archive_digest")),
        "rollback_manifest_digest":_sha256(g.get("rollback_manifest_digest")),
        "uninstall_manifest_digest":_sha256(g.get("uninstall_manifest_digest")),
        "install_plan_digest":_sha256(g.get("install_plan_digest")),
        "owner_binding_digest":_sha256(g.get("owner_binding_digest")),
        **vals,
        "max_preinstall_snapshot_age_seconds":MAX_PREINSTALL_SNAPSHOT_AGE_SECONDS,
        "max_install_token_lifetime_seconds":MAX_INSTALL_TOKEN_LIFETIME_SECONDS,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":PREINSTALL_CONTRACT_SCHEMA,
        "state":READY_PREINSTALL_CONTRACT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "preinstall_contract_digest":_digest(material) if not blockers else "",
        "preinstall_revalidation_implemented":False,
        "preinstall_revalidation_executed":False,
        "external_trust_verified":False,
        "safety_stop_physically_checked":False,
        "circuit_breaker_physically_checked":False,
        "install_token_implemented":False,
        "install_token_issued":False,
        "install_token_signed":False,
        "install_token_consumed":False,
        "owner_install_authorization_consumed":False,
        "installation_authorized":False,
        "installation_started":False,
        "files_copied":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "windows_registry_modified":False,
        "startup_entry_created":False,
        "process_spawned":False,
        "network_called":False,
    }

def validate_future_preinstall_snapshot_shape(
    contract:Mapping[str,Any]|None,
    snapshot:Mapping[str,Any]|None,
    *,
    now:Any,
)->dict[str,Any]:
    c=dict(contract or {});s=dict(snapshot or {});blockers=[]
    if c.get("state")!=READY_PREINSTALL_CONTRACT_STATE:blockers.append("READY_PREINSTALL_CONTRACT_REQUIRED")
    if s.get("schema")!=PREINSTALL_SNAPSHOT_SCHEMA:blockers.append("PREINSTALL_SNAPSHOT_SCHEMA_MISMATCH")
    if s.get("state")!="PREINSTALL_REVALIDATION_VERIFIED":blockers.append("PREINSTALL_REVALIDATION_VERIFIED_STATE_REQUIRED")

    exact=(
        "installation_gate_digest","persistence_contract_digest","package_attestation_digest",
        "installation_manifest_digest","archive_digest","installation_target_digest",
        "owner_acl_policy_digest","startup_policy_digest","rollback_archive_digest",
        "rollback_manifest_digest","uninstall_manifest_digest","install_plan_digest",
        "owner_binding_digest","safety_stop_policy_digest","circuit_breaker_policy_digest",
        "preinstall_safety_policy_digest",
    )
    for k in exact:
        if _sha256(s.get(k))!=_sha256(c.get(k)):blockers.append("PREINSTALL_BINDING_MISMATCH:"+k)

    evidence=(
        "snapshot_digest","package_persistence_attestation_digest","package_reopen_observation_digest",
        "owner_install_authorization_verification_digest","install_auth_persistence_attestation_digest",
        "install_auth_reopen_observation_digest","nonce_registry_record_digest",
        "nonce_replay_guard_observation_digest","nonce_single_use_observation_digest",
        "target_state_observation_digest","disk_space_observation_digest","windows_version_observation_digest",
        "acl_preflight_observation_digest","startup_preflight_observation_digest",
        "rollback_material_observation_digest","uninstall_material_observation_digest",
        "install_plan_observation_digest","safety_stop_observation_digest",
        "circuit_breaker_observation_digest","safety_state_digest",
    )
    for k in evidence:
        if not _sha256(s.get(k)):blockers.append(k.upper()+"_REQUIRED")

    true_fields=(
        "package_attestation_reverified","package_persistence_reverified","package_reopen_reverified",
        "owner_install_signature_reverified","owner_install_authorization_persistence_reverified",
        "owner_install_authorization_reopen_reverified","owner_install_authorization_fresh",
        "owner_install_authorization_unconsumed","persistent_nonce_replay_guard_reverified",
        "nonce_single_use_reverified","installation_target_reverified","installation_target_safe",
        "disk_space_reverified","minimum_windows_version_reverified","owner_acl_policy_reverified",
        "startup_policy_reverified","rollback_archive_reverified","rollback_manifest_reverified",
        "uninstall_manifest_reverified","install_plan_reverified","no_unexpected_existing_files",
        "safety_stop_armed","circuit_breaker_armed","circuit_breaker_healthy",
        "no_new_safety_blockers",
    )
    for k in true_fields:
        if s.get(k) is not True:blockers.append("PREINSTALL_REQUIRED_TRUE:"+k)
    if s.get("safety_stop_engaged") is not False:blockers.append("SAFETY_STOP_MUST_NOT_BE_ENGAGED")
    if s.get("authorization_consumed") is not False:blockers.append("OWNER_INSTALL_AUTHORIZATION_ALREADY_CONSUMED")
    if s.get("install_token_consumed") is not False:blockers.append("INSTALL_TOKEN_ALREADY_CONSUMED")
    if s.get("installation_started") is not False:blockers.append("INSTALLATION_ALREADY_STARTED")
    if int(s.get("unexpected_existing_file_count") or 0)!=0:blockers.append("UNEXPECTED_EXISTING_INSTALLATION_FILES_FORBIDDEN")
    try:
        captured=_aware(s.get("captured_at"));current=_aware(now);age=(current-captured).total_seconds()
        if age < -MAX_CLOCK_SKEW_SECONDS:blockers.append("PREINSTALL_SNAPSHOT_FROM_FUTURE")
        if age > MAX_PREINSTALL_SNAPSHOT_AGE_SECONDS:blockers.append("PREINSTALL_SNAPSHOT_STALE")
    except Exception:
        captured=current=None;blockers.append("PREINSTALL_TIME_INVALID")

    material={
        "preinstall_contract_digest":_sha256(c.get("preinstall_contract_digest")),
        "snapshot_digest":_sha256(s.get("snapshot_digest")),
        "package_persistence_attestation_digest":_sha256(s.get("package_persistence_attestation_digest")),
        "owner_install_authorization_verification_digest":_sha256(s.get("owner_install_authorization_verification_digest")),
        "install_auth_persistence_attestation_digest":_sha256(s.get("install_auth_persistence_attestation_digest")),
        "nonce_registry_record_digest":_sha256(s.get("nonce_registry_record_digest")),
        "target_state_observation_digest":_sha256(s.get("target_state_observation_digest")),
        "rollback_material_observation_digest":_sha256(s.get("rollback_material_observation_digest")),
        "uninstall_material_observation_digest":_sha256(s.get("uninstall_material_observation_digest")),
        "safety_state_digest":_sha256(s.get("safety_state_digest")),
        "captured_at":captured.isoformat() if captured else "",
        "checked_at":current.isoformat() if current else "",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":PREINSTALL_SNAPSHOT_SCHEMA,
        "state":READY_PREINSTALL_SHAPE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "preinstall_snapshot_review_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,
        "external_trust_verified_by_this_module":False,
        "package_persistence_trusted":False,
        "install_authorization_persistence_trusted":False,
        "nonce_state_trusted":False,
        "target_state_trusted":False,
        "rollback_state_trusted":False,
        "safety_stop_state_trusted":False,
        "circuit_breaker_state_trusted":False,
        "install_token_issuance_allowed":False,
        "installation_authorized":False,
        "installation_started":False,
        "files_copied":False,
    }

def build_unissued_install_token_template(
    contract:Mapping[str,Any]|None,
    preinstall_review:Mapping[str,Any]|None,
    *,
    token_id:Any,
    token_nonce_digest:Any,
    issued_at:Any,
    expires_at:Any,
)->dict[str,Any]:
    c=dict(contract or {});r=dict(preinstall_review or {});blockers=[]
    if c.get("state")!=READY_PREINSTALL_CONTRACT_STATE:blockers.append("READY_PREINSTALL_CONTRACT_REQUIRED")
    if r.get("state")!=READY_PREINSTALL_SHAPE_STATE:blockers.append("VALID_PREINSTALL_SNAPSHOT_SHAPE_REQUIRED")
    token=_identity(token_id,180)
    if not token:blockers.append("INSTALL_TOKEN_ID_REQUIRED")
    nonce=_sha256(token_nonce_digest)
    if not nonce:blockers.append("INSTALL_TOKEN_NONCE_DIGEST_REQUIRED")
    try:
        issued=_aware(issued_at);expires=_aware(expires_at);life=(expires-issued).total_seconds()
        if life<=0:blockers.append("INSTALL_TOKEN_LIFETIME_INVALID")
        if life>MAX_INSTALL_TOKEN_LIFETIME_SECONDS:blockers.append("INSTALL_TOKEN_LIFETIME_TOO_LONG")
    except Exception:
        issued=expires=None;blockers.append("INSTALL_TOKEN_TIME_INVALID")
    material={
        "token_id":token,
        "purpose":TOKEN_PURPOSE,
        "audience":TOKEN_AUDIENCE,
        "preinstall_contract_digest":_sha256(c.get("preinstall_contract_digest")),
        "preinstall_snapshot_review_digest":_sha256(r.get("preinstall_snapshot_review_digest")),
        "installation_gate_digest":_sha256(c.get("installation_gate_digest")),
        "package_attestation_digest":_sha256(c.get("package_attestation_digest")),
        "installation_manifest_digest":_sha256(c.get("installation_manifest_digest")),
        "archive_digest":_sha256(c.get("archive_digest")),
        "installation_target_digest":_sha256(c.get("installation_target_digest")),
        "owner_acl_policy_digest":_sha256(c.get("owner_acl_policy_digest")),
        "startup_policy_digest":_sha256(c.get("startup_policy_digest")),
        "rollback_archive_digest":_sha256(c.get("rollback_archive_digest")),
        "rollback_manifest_digest":_sha256(c.get("rollback_manifest_digest")),
        "uninstall_manifest_digest":_sha256(c.get("uninstall_manifest_digest")),
        "install_plan_digest":_sha256(c.get("install_plan_digest")),
        "owner_binding_digest":_sha256(c.get("owner_binding_digest")),
        "package_persistence_attestation_digest":_sha256(r.get("package_persistence_attestation_digest")),
        "owner_install_authorization_verification_digest":_sha256(r.get("owner_install_authorization_verification_digest")),
        "install_auth_persistence_attestation_digest":_sha256(r.get("install_auth_persistence_attestation_digest")),
        "nonce_registry_record_digest":_sha256(r.get("nonce_registry_record_digest")),
        "target_state_observation_digest":_sha256(r.get("target_state_observation_digest")),
        "safety_state_digest":_sha256(r.get("safety_state_digest")),
        "token_signer_manifest_digest":_sha256(c.get("token_signer_manifest_digest")),
        "token_signer_key_fingerprint":_sha256(c.get("token_signer_key_fingerprint")),
        "token_nonce_digest":nonce,
        "issued_at":issued.isoformat() if issued else "",
        "expires_at":expires.isoformat() if expires else "",
        "max_uses":1,
        "max_installation_sessions":1,
        "max_installation_targets":1,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":TOKEN_TEMPLATE_SCHEMA,
        "state":READY_TOKEN_TEMPLATE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "token_template_digest":_digest(material) if not blockers else "",
        "single_use":True,
        "requires_atomic_owner_authorization_consumption_with_install_start":True,
        "requires_atomic_token_consumption_with_install_start":True,
        "requires_final_pre_copy_revalidation":True,
        "token_implemented":False,
        "token_issued":False,
        "token_signed":False,
        "token_persisted":False,
        "token_consumed":False,
        "owner_install_authorization_consumed":False,
        "installation_authorized":False,
        "installation_started":False,
        "files_copied":False,
        "package_installed":False,
    }

def validate_future_install_token_issuance_attestation_shape(
    token_template:Mapping[str,Any]|None,
    **evidence:Any,
)->dict[str,Any]:
    token=dict(token_template or {});blockers=[]
    if token.get("state")!=READY_TOKEN_TEMPLATE_STATE:blockers.append("READY_UNISSUED_INSTALL_TOKEN_TEMPLATE_REQUIRED")
    if evidence.get("owner_install_authorization_consumed") is not False:
        blockers.append("OWNER_INSTALL_AUTHORIZATION_MUST_BE_UNCONSUMED_BEFORE_INSTALL_START")
    if evidence.get("token_consumed") is not False:
        blockers.append("INSTALL_TOKEN_MUST_BE_UNCONSUMED_BEFORE_INSTALL_START")
    required=(
        "token_digest","token_signature_digest","token_signer_manifest_digest",
        "token_record_digest","token_nonce_record_digest","write_receipt_digest",
        "cas_observation_digest","read_after_write_observation_digest","reopen_observation_digest",
    )
    vals={}
    for k in required:
        d=_sha256(evidence.get(k));vals[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    if vals.get("token_signer_manifest_digest")!=_sha256(token.get("token_signer_manifest_digest")):
        blockers.append("INSTALL_TOKEN_SIGNER_MANIFEST_BINDING_MISMATCH")
    if evidence.get("caller_claims_token_trusted") is True:
        blockers.append("CALLER_INSTALL_TOKEN_TRUST_CLAIM_NOT_ACCEPTED")
    material={
        "token_template_digest":_sha256(token.get("token_template_digest")),
        **vals,
        "owner_install_authorization_consumed":False,
        "token_consumed":False,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":TOKEN_ATTESTATION_SCHEMA,
        "state":READY_TOKEN_ATTESTATION_SHAPE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "token_issuance_attestation_candidate_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,
        "token_signature_verified":False,
        "token_persisted_trusted":False,
        "token_nonce_single_use_verified":False,
        "cas_verified":False,
        "read_after_write_verified":False,
        "reopen_verified":False,
        "final_pre_copy_revalidation_verified":False,
        "owner_install_authorization_consumed":False,
        "token_consumed":False,
        "installation_authorized":False,
        "installation_started":False,
        "files_copied":False,
        "package_installed":False,
    }

def build_implementation_review(
    contract:Mapping[str,Any]|None,
    token_template:Mapping[str,Any]|None,
    **designs:Any,
)->dict[str,Any]:
    c=dict(contract or {});t=dict(token_template or {});blockers=[]
    if c.get("state")!=READY_PREINSTALL_CONTRACT_STATE:blockers.append("READY_PREINSTALL_CONTRACT_REQUIRED")
    if t.get("state")!=READY_TOKEN_TEMPLATE_STATE:blockers.append("READY_UNISSUED_INSTALL_TOKEN_TEMPLATE_REQUIRED")
    required=(
        "preinstall_verifier_source_digest","token_signer_source_digest",
        "token_store_writer_design_digest","atomic_install_start_consumer_design_digest",
        "final_pre_copy_revalidation_design_digest",
    )
    vals={}
    for k in required:
        d=_sha256(designs.get(k));vals[k]=d
        if not d:blockers.append(k.upper()+"_REQUIRED")
    material={
        "preinstall_contract_digest":_sha256(c.get("preinstall_contract_digest")),
        "token_template_digest":_sha256(t.get("token_template_digest")),
        **vals,
        "next_pc_phase":"IMPLEMENT_SINGLE_USE_INSTALL_TOKEN_AND_FINAL_PRE_COPY_REVALIDATION",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":REVIEW_SCHEMA,
        "state":READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "implementation_review_digest":_digest(material) if not blockers else "",
        "preinstall_verifier_implemented":False,
        "preinstall_revalidation_executed":False,
        "token_signer_implemented":False,
        "token_store_writer_implemented":False,
        "atomic_install_start_consumer_implemented":False,
        "final_pre_copy_revalidation_implemented":False,
        "install_token_implemented":False,
        "install_token_issued":False,
        "install_token_signed":False,
        "install_token_persisted":False,
        "install_token_consumed":False,
        "owner_install_authorization_consumed":False,
        "installation_authorized":False,
        "installation_started":False,
        "files_copied":False,
        "package_installed":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "windows_registry_modified":False,
        "startup_entry_created":False,
        "network_called":False,
        "github_api_called":False,
    }

def install_token_preinstall_policy()->dict[str,Any]:
    return {
        "schema":POLICY_SCHEMA,
        "token_purpose":TOKEN_PURPOSE,
        "token_audience":TOKEN_AUDIENCE,
        "max_preinstall_snapshot_age_seconds":MAX_PREINSTALL_SNAPSHOT_AGE_SECONDS,
        "max_install_token_lifetime_seconds":MAX_INSTALL_TOKEN_LIFETIME_SECONDS,
        "preinstall_revalidation_required":True,
        "final_pre_copy_revalidation_required":True,
        "same_package_attestation_required":True,
        "same_package_persistence_required":True,
        "same_owner_install_authorization_required":True,
        "same_installation_target_required":True,
        "same_acl_policy_required":True,
        "same_startup_policy_required":True,
        "same_rollback_material_required":True,
        "same_uninstall_manifest_required":True,
        "same_install_plan_required":True,
        "target_state_reverification_required":True,
        "no_unexpected_existing_files_required":True,
        "safety_stop_armed_required":True,
        "safety_stop_must_not_be_engaged":True,
        "circuit_breaker_armed_required":True,
        "circuit_breaker_healthy_required":True,
        "token_single_use_required":True,
        "token_signature_required":True,
        "token_persistence_required":True,
        "token_cas_required":True,
        "token_read_after_write_required":True,
        "token_reopen_required":True,
        "token_nonce_single_use_required":True,
        "atomic_owner_install_authorization_consumption_with_install_start_required":True,
        "atomic_token_consumption_with_install_start_required":True,
        "caller_preinstall_claim_is_authority":False,
        "caller_token_trust_claim_is_authority":False,
        "generic_chat_is_install_start_authority":False,
        "preinstall_revalidation_implemented":False,
        "preinstall_revalidation_executed":False,
        "preinstall_external_trust_verified":False,
        "token_signer_implemented":False,
        "install_token_implemented":False,
        "install_token_issued":False,
        "install_token_signed":False,
        "install_token_persisted":False,
        "install_token_consumed":False,
        "owner_install_authorization_consumed":False,
        "installation_authorized":False,
        "installation_started":False,
        "files_copied":False,
        "package_installed":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "windows_registry_modified":False,
        "startup_entry_created":False,
        "scheduled_task_installed":False,
        "windows_service_installed":False,
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

__all__=[name for name in globals() if name.isupper() or name.startswith("build_") or name.startswith("validate_")]
