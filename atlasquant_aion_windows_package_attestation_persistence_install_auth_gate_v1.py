"""AION Windows Package Attestation Persistence + Installation Authorization Gate V1.

Design-only boundary between an already attested offline package and any future
Windows installation.

This layer:
- validates exact package-attestation shape/bindings;
- defines append-only/CAS/exactly-once persistence evidence for the attestation;
- requires read-after-write + reopen consistency;
- defines a separate HUMAN_OWNER installation authorization ceremony;
- verifies a synthetic/externally supplied Ed25519 owner signature;
- defines future nonce/persistence requirements for that authorization.

It does NOT persist anything, install/copy/delete files, modify Registry/ACL/
startup, execute an installer, load a private key, call network/GitHub, deploy,
or mutate production.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from atlasquant_aion_windows_installation_manifest_package_attestation_v1 import (
    PACKAGE_ATTESTATION_SCHEMA,
)

SCHEMA="ATLASQUANT_AION_WINDOWS_PACKAGE_ATTESTATION_PERSISTENCE_INSTALL_AUTH_GATE_V1"
PERSISTENCE_CONTRACT_SCHEMA="ATLASQUANT_AION_WINDOWS_PACKAGE_ATTESTATION_PERSISTENCE_CONTRACT_V1"
PERSISTENCE_ATTESTATION_SCHEMA="ATLASQUANT_AION_WINDOWS_PACKAGE_ATTESTATION_PERSISTENCE_ATTESTATION_V1"
INSTALL_GATE_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALLATION_AUTHORIZATION_GATE_V1"
REQUEST_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALLATION_AUTHORIZATION_REQUEST_V1"
OWNER_VERIFICATION_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALLATION_OWNER_AUTHORIZATION_VERIFICATION_V1"
AUTH_PERSISTENCE_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALLATION_AUTHORIZATION_PERSISTENCE_ATTESTATION_V1"
REVIEW_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALLATION_GATE_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA="ATLASQUANT_AION_WINDOWS_INSTALLATION_GATE_POLICY_V1"

READY_PERSISTENCE_CONTRACT_STATE="PACKAGE_ATTESTATION_PERSISTENCE_CONTRACT_READY"
READY_PERSISTENCE_SHAPE_STATE="PACKAGE_ATTESTATION_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED"
READY_INSTALL_GATE_STATE="INSTALLATION_AUTHORIZATION_GATE_READY"
READY_OWNER_SIGNATURE_STATE="READY_FOR_EXTERNAL_HUMAN_OWNER_INSTALL_SIGNATURE"
OWNER_INSTALL_AUTH_VERIFIED_PENDING_PERSISTENCE="OWNER_INSTALL_AUTH_SIGNATURE_VERIFIED_PENDING_PERSISTENCE"
OWNER_INSTALL_DENIAL_VERIFIED="OWNER_INSTALL_DENIAL_SIGNATURE_VERIFIED"
READY_AUTH_PERSISTENCE_SHAPE_STATE="INSTALL_AUTH_PERSISTENCE_SHAPE_VALID_BUT_UNTRUSTED"
READY_REVIEW_STATE="READY_FOR_WINDOWS_INSTALLATION_AUTHORIZATION_IMPLEMENTATION"
BLOCKED_STATE="BLOCKED"

PURPOSE="HUMAN_OWNER_EXPLICIT_WINDOWS_LOCAL_AGENT_INSTALLATION"
MECHANISM="ED25519_EXTERNAL_OWNER_EXECUTION_KEY"
AUTHORIZE_DECISION="AUTHORIZE_WINDOWS_LOCAL_AGENT_INSTALLATION"
DENY_DECISION="DENY_WINDOWS_LOCAL_AGENT_INSTALLATION"
DECISIONS=(AUTHORIZE_DECISION,DENY_DECISION)
MAX_AUTH_WINDOW_SECONDS=120
MAX_PERSISTED_ATTESTATION_AGE_SECONDS=120
OWNER_SIGNATURE_CONTEXT=b"ATLASQUANT:AION:WINDOWS_LOCAL_AGENT:INSTALL_AUTHORIZATION:"

_SHA256_RE=re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{2,239}$")
_NONCE_RE=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{15,255}$")

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

def _public_key_bytes(v:Any)->bytes:
    text=_clean(v,8192)
    raw=base64.b64decode(text,validate=True)
    if len(raw)!=32: raise ValueError("owner public key length")
    return raw

def owner_key_fingerprint(public_key_b64:Any)->str:
    return "sha256:"+sha256(_public_key_bytes(public_key_b64)).hexdigest()

def build_package_attestation_persistence_contract(
    package_attestation:Mapping[str,Any]|None,
    *,
    persistence_namespace:Any,
    writer_manifest_digest:Any,
    package_store_design_digest:Any,
)->dict[str,Any]:
    row=dict(package_attestation or {});blockers=[]
    if row.get("schema")!=PACKAGE_ATTESTATION_SCHEMA:blockers.append("PACKAGE_ATTESTATION_SCHEMA_MISMATCH")
    if row.get("state")!="PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED":blockers.append("PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED_REQUIRED")
    if row.get("manifest_signature_verified") is not True:blockers.append("PACKAGE_RELEASE_SIGNATURE_VERIFICATION_REQUIRED")
    for field,label in (
        ("authenticode_signature_verified","AUTHENTICODE_SIGNATURE_VERIFICATION_REQUIRED"),
        ("authenticode_trusted_chain_verified","AUTHENTICODE_TRUSTED_CHAIN_VERIFICATION_REQUIRED"),
        ("authenticode_timestamp_verified","AUTHENTICODE_TIMESTAMP_VERIFICATION_REQUIRED"),
        ("authenticode_publisher_match_verified","AUTHENTICODE_PUBLISHER_MATCH_VERIFICATION_REQUIRED"),
    ):
        if row.get(field) is not True:blockers.append(label)
    for field,label in (
        ("package_attestation_digest","PACKAGE_ATTESTATION_DIGEST_REQUIRED"),
        ("manifest_digest","INSTALLATION_MANIFEST_DIGEST_REQUIRED"),
        ("archive_digest","PACKAGE_ARCHIVE_DIGEST_REQUIRED"),
        ("sbom_digest","PACKAGE_SBOM_DIGEST_REQUIRED"),
        ("build_provenance_digest","PACKAGE_BUILD_PROVENANCE_DIGEST_REQUIRED"),
        ("dependency_lock_digest","PACKAGE_DEPENDENCY_LOCK_DIGEST_REQUIRED"),
        ("authenticode_binary_digest","AUTHENTICODE_BINARY_DIGEST_REQUIRED"),
        ("authenticode_evidence_digest","AUTHENTICODE_EVIDENCE_DIGEST_REQUIRED"),
        ("release_review_digest","PACKAGE_RELEASE_REVIEW_DIGEST_REQUIRED"),
    ):
        if not _sha256(row.get(field)):blockers.append(label)
    namespace=_identity(persistence_namespace,180)
    if not namespace:blockers.append("PACKAGE_PERSISTENCE_NAMESPACE_REQUIRED")
    writer=_sha256(writer_manifest_digest)
    design=_sha256(package_store_design_digest)
    if not writer:blockers.append("PACKAGE_PERSISTENCE_WRITER_MANIFEST_DIGEST_REQUIRED")
    if not design:blockers.append("PACKAGE_STORE_DESIGN_DIGEST_REQUIRED")
    material={
        "persistence_namespace":namespace,
        "package_attestation_digest":_sha256(row.get("package_attestation_digest")),
        "installation_manifest_digest":_sha256(row.get("manifest_digest")),
        "archive_digest":_sha256(row.get("archive_digest")),
        "sbom_digest":_sha256(row.get("sbom_digest")),
        "build_provenance_digest":_sha256(row.get("build_provenance_digest")),
        "dependency_lock_digest":_sha256(row.get("dependency_lock_digest")),
        "authenticode_binary_digest":_sha256(row.get("authenticode_binary_digest")),
        "authenticode_evidence_digest":_sha256(row.get("authenticode_evidence_digest")),
        "release_review_digest":_sha256(row.get("release_review_digest")),
        "package_signer_fingerprint":_sha256(row.get("package_signer_fingerprint")),
        "package_family":row.get("package_family"),
        "package_version":row.get("package_version"),
        "build_id":row.get("build_id"),
        "build_commit_sha":row.get("build_commit_sha"),
        "writer_manifest_digest":writer,
        "package_store_design_digest":design,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":PERSISTENCE_CONTRACT_SCHEMA,
        "state":READY_PERSISTENCE_CONTRACT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "persistence_contract_digest":_digest(material) if not blockers else "",
        "append_only_required":True,
        "compare_and_set_required":True,
        "exactly_once_required":True,
        "read_after_write_required":True,
        "reopen_consistency_required":True,
        "replace_allowed":False,
        "delete_allowed":False,
        "attestation_persisted":False,
        "physical_persistence_verified":False,
        "installation_authorized":False,
        "package_installed":False,
    }

def validate_future_package_persistence_attestation_shape(
    contract:Mapping[str,Any]|None,
    *,
    record_key:Any,
    record_digest:Any,
    writer_manifest_digest:Any,
    write_receipt_digest:Any,
    cas_observation_digest:Any,
    read_after_write_observation_digest:Any,
    reopen_observation_digest:Any,
    persisted_at:Any,
    now:Any,
    caller_claims_persistence_verified:bool=False,
)->dict[str,Any]:
    con=dict(contract or {});blockers=[]
    if con.get("state")!=READY_PERSISTENCE_CONTRACT_STATE:blockers.append("READY_PACKAGE_PERSISTENCE_CONTRACT_REQUIRED")
    vals={}
    for k,v,label in (
        ("record_key",record_key,"PACKAGE_ATTESTATION_RECORD_KEY_REQUIRED"),
        ("record_digest",record_digest,"PACKAGE_ATTESTATION_RECORD_DIGEST_REQUIRED"),
        ("writer_manifest_digest",writer_manifest_digest,"PACKAGE_PERSISTENCE_WRITER_MANIFEST_DIGEST_REQUIRED"),
        ("write_receipt_digest",write_receipt_digest,"PACKAGE_WRITE_RECEIPT_DIGEST_REQUIRED"),
        ("cas_observation_digest",cas_observation_digest,"PACKAGE_CAS_OBSERVATION_DIGEST_REQUIRED"),
        ("read_after_write_observation_digest",read_after_write_observation_digest,"PACKAGE_READ_AFTER_WRITE_DIGEST_REQUIRED"),
        ("reopen_observation_digest",reopen_observation_digest,"PACKAGE_REOPEN_OBSERVATION_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    if vals.get("writer_manifest_digest")!=_sha256(con.get("writer_manifest_digest")):
        blockers.append("PACKAGE_PERSISTENCE_WRITER_MANIFEST_MISMATCH")
    try:
        persisted=_aware(persisted_at);current=_aware(now);age=(current-persisted).total_seconds()
        if age<0:blockers.append("PACKAGE_PERSISTENCE_ATTESTATION_FROM_FUTURE")
        if age>MAX_PERSISTED_ATTESTATION_AGE_SECONDS:blockers.append("PACKAGE_PERSISTENCE_ATTESTATION_STALE")
    except Exception:
        persisted=current=None;blockers.append("PACKAGE_PERSISTENCE_TIME_INVALID")
    if caller_claims_persistence_verified is True:blockers.append("CALLER_PACKAGE_PERSISTENCE_TRUST_CLAIM_NOT_ACCEPTED")
    material={
        "persistence_contract_digest":_sha256(con.get("persistence_contract_digest")),
        "package_attestation_digest":_sha256(con.get("package_attestation_digest")),
        **vals,
        "persisted_at":persisted.isoformat() if persisted else "",
        "checked_at":current.isoformat() if current else "",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":PERSISTENCE_ATTESTATION_SCHEMA,
        "state":READY_PERSISTENCE_SHAPE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "persistence_attestation_candidate_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,
        "persistence_trusted":False,
        "cas_verified":False,
        "read_after_write_verified":False,
        "reopen_verified":False,
        "installation_authorized":False,
        "package_installed":False,
    }

def build_installation_gate(
    persistence_contract:Mapping[str,Any]|None,
    *,
    installation_target_digest:Any,
    owner_acl_policy_digest:Any,
    startup_policy_digest:Any,
    rollback_archive_digest:Any,
    rollback_manifest_digest:Any,
    uninstall_manifest_digest:Any,
    install_plan_digest:Any,
    owner_binding_digest:Any,
)->dict[str,Any]:
    con=dict(persistence_contract or {});blockers=[]
    if con.get("state")!=READY_PERSISTENCE_CONTRACT_STATE:blockers.append("READY_PACKAGE_PERSISTENCE_CONTRACT_REQUIRED")
    vals={}
    for k,v,label in (
        ("installation_target_digest",installation_target_digest,"INSTALLATION_TARGET_DIGEST_REQUIRED"),
        ("owner_acl_policy_digest",owner_acl_policy_digest,"OWNER_ACL_POLICY_DIGEST_REQUIRED"),
        ("startup_policy_digest",startup_policy_digest,"STARTUP_POLICY_DIGEST_REQUIRED"),
        ("rollback_archive_digest",rollback_archive_digest,"ROLLBACK_ARCHIVE_DIGEST_REQUIRED"),
        ("rollback_manifest_digest",rollback_manifest_digest,"ROLLBACK_MANIFEST_DIGEST_REQUIRED"),
        ("uninstall_manifest_digest",uninstall_manifest_digest,"UNINSTALL_MANIFEST_DIGEST_REQUIRED"),
        ("install_plan_digest",install_plan_digest,"INSTALL_PLAN_DIGEST_REQUIRED"),
        ("owner_binding_digest",owner_binding_digest,"OWNER_BINDING_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "purpose":PURPOSE,
        "mechanism":MECHANISM,
        "persistence_contract_digest":_sha256(con.get("persistence_contract_digest")),
        "package_attestation_digest":_sha256(con.get("package_attestation_digest")),
        "installation_manifest_digest":_sha256(con.get("installation_manifest_digest")),
        "archive_digest":_sha256(con.get("archive_digest")),
        "package_version":con.get("package_version"),
        "build_id":con.get("build_id"),
        "build_commit_sha":con.get("build_commit_sha"),
        **vals,
        "max_owner_authorization_window_seconds":MAX_AUTH_WINDOW_SECONDS,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":INSTALL_GATE_SCHEMA,
        "state":READY_INSTALL_GATE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,**material,
        "installation_gate_digest":_digest(material) if not blockers else "",
        "package_persistence_reopen_required":True,
        "rollback_material_required":True,
        "uninstall_manifest_required":True,
        "generic_chat_is_install_authorization":False,
        "owner_install_authorization_must_be_separate":True,
        "owner_install_authorization_must_be_fresh":True,
        "owner_install_authorization_must_be_single_use":True,
        "installation_authorized":False,
        "install_token_issued":False,
        "installation_started":False,
        "package_installed":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "windows_registry_modified":False,
        "startup_entry_created":False,
    }

def build_owner_install_authorization_request(
    gate:Mapping[str,Any]|None,
    persistence_attestation:Mapping[str,Any]|None,
    *,
    authorization_id:Any,
    decision:Any,
    nonce:Any,
    owner_public_key_b64:Any,
    expected_owner_key_fingerprint:Any,
    issued_at:Any,
    expires_at:Any,
    now:Any,
)->dict[str,Any]:
    g=dict(gate or {});p=dict(persistence_attestation or {});blockers=[]
    if g.get("state")!=READY_INSTALL_GATE_STATE:blockers.append("READY_INSTALLATION_GATE_REQUIRED")
    if p.get("state")!=READY_PERSISTENCE_SHAPE_STATE:blockers.append("PACKAGE_PERSISTENCE_ATTESTATION_SHAPE_REQUIRED")
    if _sha256(p.get("persistence_contract_digest"))!=_sha256(g.get("persistence_contract_digest")):
        blockers.append("PACKAGE_PERSISTENCE_CONTRACT_BINDING_MISMATCH")
    auth_id=_identity(authorization_id,180)
    if not auth_id:blockers.append("INSTALL_AUTHORIZATION_ID_REQUIRED")
    decision_name=_clean(decision,80).upper()
    if decision_name not in DECISIONS:blockers.append("INSTALL_AUTHORIZATION_DECISION_INVALID")
    nonce_value=_clean(nonce,280)
    if not _NONCE_RE.fullmatch(nonce_value):blockers.append("INSTALL_AUTHORIZATION_NONCE_INVALID")
    try:
        raw_key=_public_key_bytes(owner_public_key_b64)
        fp="sha256:"+sha256(raw_key).hexdigest()
    except Exception:
        fp="";blockers.append("OWNER_PUBLIC_KEY_INVALID")
    expected_fp=_sha256(expected_owner_key_fingerprint)
    if not expected_fp:blockers.append("EXPECTED_OWNER_KEY_FINGERPRINT_REQUIRED")
    elif fp and fp!=expected_fp:blockers.append("OWNER_KEY_FINGERPRINT_MISMATCH")
    try:
        issued=_aware(issued_at);expires=_aware(expires_at);current=_aware(now)
        window=(expires-issued).total_seconds()
        if window<=0:blockers.append("INSTALL_AUTHORIZATION_WINDOW_INVALID")
        if window>MAX_AUTH_WINDOW_SECONDS:blockers.append("INSTALL_AUTHORIZATION_WINDOW_TOO_LONG")
        if current<issued:blockers.append("INSTALL_AUTHORIZATION_NOT_YET_VALID")
        if current>=expires:blockers.append("INSTALL_AUTHORIZATION_EXPIRED")
    except Exception:
        issued=expires=current=None;blockers.append("INSTALL_AUTHORIZATION_TIME_INVALID")
    body={
        "schema":REQUEST_SCHEMA,
        "authorization_id":auth_id,
        "purpose":PURPOSE,
        "mechanism":MECHANISM,
        "decision":decision_name,
        "installation_gate_digest":_sha256(g.get("installation_gate_digest")),
        "package_attestation_digest":_sha256(g.get("package_attestation_digest")),
        "package_persistence_attestation_digest":_sha256(p.get("persistence_attestation_candidate_digest")),
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
        "owner_public_key_fingerprint":fp,
        "nonce":nonce_value,
        "issued_at":issued.isoformat() if issued else "",
        "expires_at":expires.isoformat() if expires else "",
        "generic_chat_instruction_accepted_as_install_authorization":False,
        "installation_authorized":False,
        "installation_started":False,
    }
    blockers=list(dict.fromkeys(blockers))
    request_digest=_digest(body) if not blockers else ""
    return {
        "schema":REQUEST_SCHEMA,
        "state":READY_OWNER_SIGNATURE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        "request":body if not blockers else {},
        "request_digest":request_digest,
        "digest_to_sign":request_digest,
        "owner_signature_verified":False,
        "nonce_claimed":False,
        "authorization_persisted":False,
        "authorization_consumed":False,
        "installation_authorized":False,
        "install_token_issued":False,
        "installation_started":False,
        "package_installed":False,
    }

def verify_owner_install_signature(
    request_result:Mapping[str,Any]|None,
    *,
    owner_public_key_b64:Any,
    signature_b64:Any,
    expected_owner_key_fingerprint:Any,
    now:Any,
)->dict[str,Any]:
    rr=dict(request_result or {});blockers=[]
    if rr.get("state")!=READY_OWNER_SIGNATURE_STATE:blockers.append("READY_OWNER_INSTALL_SIGNATURE_REQUEST_REQUIRED")
    request=dict(rr.get("request") or {})
    supplied=_sha256(rr.get("request_digest"))
    expected=_digest(request) if request else ""
    if request.get("schema")!=REQUEST_SCHEMA:blockers.append("INSTALL_AUTH_REQUEST_SCHEMA_MISMATCH")
    if not supplied or supplied!=expected:blockers.append("INSTALL_AUTH_REQUEST_DIGEST_MISMATCH")
    try:
        raw_key=_public_key_bytes(owner_public_key_b64)
        fp="sha256:"+sha256(raw_key).hexdigest()
    except Exception:
        raw_key=b"";fp="";blockers.append("OWNER_PUBLIC_KEY_INVALID")
    expected_fp=_sha256(expected_owner_key_fingerprint)
    if not expected_fp:blockers.append("EXPECTED_OWNER_KEY_FINGERPRINT_REQUIRED")
    elif fp and fp!=expected_fp:blockers.append("OWNER_KEY_FINGERPRINT_MISMATCH")
    if fp and fp!=_sha256(request.get("owner_public_key_fingerprint")):
        blockers.append("OWNER_KEY_REQUEST_FINGERPRINT_MISMATCH")
    try:
        current=_aware(now);issued=_aware(request.get("issued_at"));expires=_aware(request.get("expires_at"))
        if current<issued:blockers.append("INSTALL_AUTHORIZATION_NOT_YET_VALID")
        if current>=expires:blockers.append("INSTALL_AUTHORIZATION_EXPIRED")
    except Exception:
        blockers.append("INSTALL_AUTHORIZATION_TIME_INVALID")
    verified=False
    try:
        signature=base64.b64decode(_clean(signature_b64,8192),validate=True)
        if len(signature)!=64: raise ValueError("sig")
        if raw_key and request:
            Ed25519PublicKey.from_public_bytes(raw_key).verify(
                signature,
                OWNER_SIGNATURE_CONTEXT+expected.encode("ascii"),
            )
            verified=True
    except InvalidSignature:
        blockers.append("OWNER_INSTALL_AUTHORIZATION_SIGNATURE_INVALID")
    except Exception:
        blockers.append("OWNER_INSTALL_AUTHORIZATION_SIGNATURE_INVALID")
    decision=request.get("decision")
    if decision not in DECISIONS:blockers.append("INSTALL_AUTHORIZATION_DECISION_INVALID")
    blockers=list(dict.fromkeys(blockers))
    authorize=not blockers and verified and decision==AUTHORIZE_DECISION
    deny=not blockers and verified and decision==DENY_DECISION
    material={
        "request_digest":expected if not blockers else supplied,
        "authorization_id":request.get("authorization_id"),
        "decision":decision,
        "installation_gate_digest":_sha256(request.get("installation_gate_digest")),
        "package_attestation_digest":_sha256(request.get("package_attestation_digest")),
        "package_persistence_attestation_digest":_sha256(request.get("package_persistence_attestation_digest")),
        "owner_binding_digest":_sha256(request.get("owner_binding_digest")),
        "owner_public_key_fingerprint":fp,
        "nonce_digest":"sha256:"+sha256(str(request.get("nonce","")).encode()).hexdigest() if request.get("nonce") else "",
        "signature_verified":verified,
    }
    return {
        "schema":OWNER_VERIFICATION_SCHEMA,
        "state":OWNER_INSTALL_AUTH_VERIFIED_PENDING_PERSISTENCE if authorize else OWNER_INSTALL_DENIAL_VERIFIED if deny else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "owner_install_authorization_verification_digest":_digest(material) if not blockers else "",
        "owner_signature_verified":verified,
        "installation_intent_verified":authorize,
        "denial_intent_verified":deny,
        "generic_chat_instruction_accepted_as_install_authorization":False,
        "nonce_claimed":False,
        "persistent_nonce_replay_guard_verified":False,
        "authorization_persisted":False,
        "authorization_consumed":False,
        "installation_authorized":False,
        "install_token_issued":False,
        "installation_started":False,
        "package_installed":False,
    }

def validate_future_install_auth_persistence_shape(
    owner_verification:Mapping[str,Any]|None,
    *,
    nonce_registry_record_digest:Any,
    authorization_record_digest:Any,
    writer_manifest_digest:Any,
    write_receipt_digest:Any,
    cas_observation_digest:Any,
    read_after_write_observation_digest:Any,
    reopen_observation_digest:Any,
    replay_guard_observation_digest:Any,
    nonce_single_use_observation_digest:Any,
    authorization_consumed:bool,
    caller_claims_persistence_verified:bool=False,
)->dict[str,Any]:
    row=dict(owner_verification or {});blockers=[]
    if row.get("state")!=OWNER_INSTALL_AUTH_VERIFIED_PENDING_PERSISTENCE:
        blockers.append("VERIFIED_OWNER_INSTALL_AUTHORIZATION_REQUIRED")
    if row.get("installation_intent_verified") is not True:
        blockers.append("OWNER_INSTALLATION_INTENT_REQUIRED")
    if authorization_consumed is not False:blockers.append("INSTALL_AUTHORIZATION_MUST_BE_UNCONSUMED")
    vals={}
    for k,v,label in (
        ("nonce_registry_record_digest",nonce_registry_record_digest,"NONCE_REGISTRY_RECORD_DIGEST_REQUIRED"),
        ("authorization_record_digest",authorization_record_digest,"INSTALL_AUTHORIZATION_RECORD_DIGEST_REQUIRED"),
        ("writer_manifest_digest",writer_manifest_digest,"INSTALL_AUTH_WRITER_MANIFEST_DIGEST_REQUIRED"),
        ("write_receipt_digest",write_receipt_digest,"INSTALL_AUTH_WRITE_RECEIPT_DIGEST_REQUIRED"),
        ("cas_observation_digest",cas_observation_digest,"INSTALL_AUTH_CAS_OBSERVATION_DIGEST_REQUIRED"),
        ("read_after_write_observation_digest",read_after_write_observation_digest,"INSTALL_AUTH_READ_AFTER_WRITE_DIGEST_REQUIRED"),
        ("reopen_observation_digest",reopen_observation_digest,"INSTALL_AUTH_REOPEN_DIGEST_REQUIRED"),
        ("replay_guard_observation_digest",replay_guard_observation_digest,"INSTALL_AUTH_REPLAY_GUARD_DIGEST_REQUIRED"),
        ("nonce_single_use_observation_digest",nonce_single_use_observation_digest,"INSTALL_AUTH_NONCE_SINGLE_USE_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    if caller_claims_persistence_verified is True:blockers.append("CALLER_INSTALL_AUTH_PERSISTENCE_TRUST_CLAIM_NOT_ACCEPTED")
    material={
        "owner_install_authorization_verification_digest":_sha256(row.get("owner_install_authorization_verification_digest")),
        "request_digest":_sha256(row.get("request_digest")),
        "nonce_digest":_sha256(row.get("nonce_digest")),
        **vals,
        "authorization_consumed":False,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":AUTH_PERSISTENCE_SCHEMA,
        "state":READY_AUTH_PERSISTENCE_SHAPE_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "install_auth_persistence_candidate_digest":_digest(material) if not blockers else "",
        "shape_valid":not blockers,
        "nonce_claimed_trusted":False,
        "persistent_nonce_replay_guard_verified":False,
        "nonce_single_use_verified":False,
        "authorization_persisted_trusted":False,
        "cas_verified":False,
        "read_after_write_verified":False,
        "reopen_verified":False,
        "authorization_consumed":False,
        "installation_authorized":False,
        "install_token_issued":False,
        "installation_started":False,
        "package_installed":False,
    }

def build_implementation_review(
    gate:Mapping[str,Any]|None,
    *,
    package_persistence_writer_design_digest:Any,
    package_reopen_verifier_design_digest:Any,
    install_nonce_registry_design_digest:Any,
    install_authorization_writer_design_digest:Any,
    install_preflight_design_digest:Any,
)->dict[str,Any]:
    g=dict(gate or {});blockers=[]
    if g.get("state")!=READY_INSTALL_GATE_STATE:blockers.append("READY_INSTALLATION_GATE_REQUIRED")
    vals={}
    for k,v,label in (
        ("package_persistence_writer_design_digest",package_persistence_writer_design_digest,"PACKAGE_PERSISTENCE_WRITER_DESIGN_DIGEST_REQUIRED"),
        ("package_reopen_verifier_design_digest",package_reopen_verifier_design_digest,"PACKAGE_REOPEN_VERIFIER_DESIGN_DIGEST_REQUIRED"),
        ("install_nonce_registry_design_digest",install_nonce_registry_design_digest,"INSTALL_NONCE_REGISTRY_DESIGN_DIGEST_REQUIRED"),
        ("install_authorization_writer_design_digest",install_authorization_writer_design_digest,"INSTALL_AUTHORIZATION_WRITER_DESIGN_DIGEST_REQUIRED"),
        ("install_preflight_design_digest",install_preflight_design_digest,"INSTALL_PREFLIGHT_DESIGN_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "installation_gate_digest":_sha256(g.get("installation_gate_digest")),
        **vals,
        "next_pc_phase":"IMPLEMENT_PACKAGE_PERSISTENCE_AND_FRESH_OWNER_INSTALL_AUTHORIZATION_GATE",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":REVIEW_SCHEMA,
        "state":READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "implementation_review_digest":_digest(material) if not blockers else "",
        "package_persistence_writer_implemented":False,
        "package_reopen_verifier_implemented":False,
        "install_nonce_registry_implemented":False,
        "install_authorization_writer_implemented":False,
        "install_preflight_implemented":False,
        "package_attestation_persisted":False,
        "package_attestation_reopen_verified":False,
        "owner_install_authorization_persisted":False,
        "installation_authorized":False,
        "install_token_issued":False,
        "installation_started":False,
        "package_installed":False,
        "filesystem_modified":False,
        "windows_acl_modified":False,
        "windows_registry_modified":False,
        "startup_entry_created":False,
        "network_called":False,
        "github_api_called":False,
    }

def installation_gate_policy()->dict[str,Any]:
    return {
        "schema":POLICY_SCHEMA,
        "purpose":PURPOSE,
        "mechanism":MECHANISM,
        "decisions":list(DECISIONS),
        "max_authorization_window_seconds":MAX_AUTH_WINDOW_SECONDS,
        "package_attestation_state_required":"PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED",
        "package_persistence_append_only_required":True,
        "package_persistence_cas_required":True,
        "package_persistence_exactly_once_required":True,
        "package_persistence_read_after_write_required":True,
        "package_persistence_reopen_required":True,
        "package_persistence_replace_allowed":False,
        "fresh_owner_install_signature_required":True,
        "owner_install_nonce_required":True,
        "persistent_nonce_replay_guard_required":True,
        "single_use_install_authorization_required":True,
        "install_authorization_persistence_required":True,
        "install_authorization_cas_required":True,
        "install_authorization_read_after_write_required":True,
        "install_authorization_reopen_required":True,
        "rollback_material_required":True,
        "uninstall_manifest_required":True,
        "generic_chat_is_install_authorization":False,
        "caller_package_persistence_claim_is_authority":False,
        "caller_install_auth_persistence_claim_is_authority":False,
        "package_persistence_writer_implemented":False,
        "package_reopen_verifier_implemented":False,
        "install_nonce_registry_implemented":False,
        "install_authorization_writer_implemented":False,
        "package_attestation_persisted":False,
        "package_attestation_reopen_verified":False,
        "owner_install_authorization_persisted":False,
        "installation_authorized":False,
        "install_token_issued":False,
        "installation_started":False,
        "package_installed":False,
        "files_copied":False,
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

__all__=[name for name in globals() if name.isupper() or name.startswith("build_") or name.startswith("validate_") or name.startswith("verify_") or name.endswith("_fingerprint")]
