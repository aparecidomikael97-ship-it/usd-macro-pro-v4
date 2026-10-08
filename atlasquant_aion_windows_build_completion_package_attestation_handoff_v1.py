"""AION Windows Build Completion + Package Attestation Handoff V1.

Design-only terminal build boundary after #1054.

This layer defines:
- future build completion observation semantics;
- exact terminal build outcomes;
- fail-closed ambiguity handling;
- promotion of a successful build into a package-attestation handoff candidate;
- separate reconciliation for BUILD_COMPLETION_OUTCOME_UNKNOWN.

It does not run a build, observe a real process, create/sign a package, perform
Authenticode verification, persist a receipt, install anything, call GitHub,
or mutate production.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_aion_windows_atomic_launch_consumer_build_start_receipt_v1 import (
    START_RECEIPT_SCHEMA,
    START_CONFIRMED,
)
from atlasquant_aion_windows_installation_manifest_package_attestation_v1 import (
    INSTALL_MANIFEST_SCHEMA,
    PACKAGE_ATTESTATION_SCHEMA,
)

SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_COMPLETION_PACKAGE_ATTESTATION_HANDOFF_V1"
CONTRACT_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_COMPLETION_CONTRACT_V1"
OBSERVATION_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_COMPLETION_OBSERVATION_V1"
ARTIFACT_SET_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_ARTIFACT_SET_V1"
HANDOFF_SCHEMA="ATLASQUANT_AION_WINDOWS_PACKAGE_ATTESTATION_HANDOFF_V1"
RECONCILIATION_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_COMPLETION_RECONCILIATION_V1"
REVIEW_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_COMPLETION_IMPLEMENTATION_REVIEW_V1"
POLICY_SCHEMA="ATLASQUANT_AION_WINDOWS_BUILD_COMPLETION_POLICY_V1"

READY_CONTRACT_STATE="BUILD_COMPLETION_CONTRACT_READY"
CLASSIFIED_STATE="BUILD_COMPLETION_OBSERVATION_CLASSIFIED"
READY_ARTIFACT_STATE="BUILD_ARTIFACT_SET_READY_FOR_ATTESTATION_REVIEW"
READY_HANDOFF_STATE="READY_FOR_EXISTING_PACKAGE_ATTESTATION"
READY_RECONCILIATION_STATE="BUILD_COMPLETION_RECONCILIATION_CONTRACT_READY"
READY_REVIEW_STATE="READY_FOR_WINDOWS_BUILD_COMPLETION_IMPLEMENTATION"
BLOCKED_STATE="BLOCKED"

BUILD_SUCCESS="BUILD_COMPLETED_SUCCESS"
BUILD_FAILURE="BUILD_COMPLETED_TERMINAL_FAILURE"
BUILD_UNKNOWN="BUILD_COMPLETION_OUTCOME_UNKNOWN"
ALLOWED_OUTCOMES=(BUILD_SUCCESS,BUILD_FAILURE,BUILD_UNKNOWN)

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

def build_completion_contract(
    *,
    start_receipt_digest:Any,
    launch_id:Any,
    build_id:Any,
    expected_installation_manifest_digest:Any,
    expected_package_manifest_digest:Any,
    expected_dependency_lock_digest:Any,
    expected_build_recipe_digest:Any,
    expected_offline_input_promotion_digest:Any,
    build_observer_manifest_digest:Any,
    artifact_collector_manifest_digest:Any,
    completion_reconciliation_policy_digest:Any,
)->dict[str,Any]:
    blockers=[]
    launch=_identity(launch_id,180)
    build=_identity(build_id,180)
    if not launch:blockers.append("LAUNCH_ID_REQUIRED")
    if not build:blockers.append("BUILD_ID_REQUIRED")
    vals={}
    for k,v,label in (
        ("start_receipt_digest",start_receipt_digest,"START_RECEIPT_DIGEST_REQUIRED"),
        ("expected_installation_manifest_digest",expected_installation_manifest_digest,"EXPECTED_INSTALLATION_MANIFEST_DIGEST_REQUIRED"),
        ("expected_package_manifest_digest",expected_package_manifest_digest,"EXPECTED_PACKAGE_MANIFEST_DIGEST_REQUIRED"),
        ("expected_dependency_lock_digest",expected_dependency_lock_digest,"EXPECTED_DEPENDENCY_LOCK_DIGEST_REQUIRED"),
        ("expected_build_recipe_digest",expected_build_recipe_digest,"EXPECTED_BUILD_RECIPE_DIGEST_REQUIRED"),
        ("expected_offline_input_promotion_digest",expected_offline_input_promotion_digest,"EXPECTED_OFFLINE_INPUT_PROMOTION_DIGEST_REQUIRED"),
        ("build_observer_manifest_digest",build_observer_manifest_digest,"BUILD_OBSERVER_MANIFEST_DIGEST_REQUIRED"),
        ("artifact_collector_manifest_digest",artifact_collector_manifest_digest,"ARTIFACT_COLLECTOR_MANIFEST_DIGEST_REQUIRED"),
        ("completion_reconciliation_policy_digest",completion_reconciliation_policy_digest,"COMPLETION_RECONCILIATION_POLICY_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "launch_id":launch,
        "build_id":build,
        **vals,
        "allowed_outcomes":list(ALLOWED_OUTCOMES),
        "success_requires_exit_code_zero":True,
        "success_requires_process_exit_observed":True,
        "success_requires_complete_artifact_set":True,
        "success_requires_no_unexpected_outputs":True,
        "success_requires_network_deny_maintained":True,
        "success_requires_sandbox_integrity_maintained":True,
        "success_requires_build_log_digest":True,
        "success_requires_output_inventory_digest":True,
        "terminal_failure_requires_authoritative_failure_evidence":True,
        "ambiguity_overrides_requested_success":True,
        "automatic_retry_after_ambiguous_completion_allowed":False,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":CONTRACT_SCHEMA,
        "state":READY_CONTRACT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "build_completion_contract_digest":_digest(material) if not blockers else "",
        "build_observer_implemented":False,
        "artifact_collector_implemented":False,
        "build_completion_observed":False,
        "package_built":False,
        "package_attested":False,
        "package_installed":False,
        "filesystem_modified":False,
        "network_called":False,
        "github_api_called":False,
    }

def validate_start_receipt_shape(
    contract:Mapping[str,Any]|None,
    start_receipt:Mapping[str,Any]|None,
)->dict[str,Any]:
    con=dict(contract or {});row=dict(start_receipt or {});blockers=[]
    if con.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_BUILD_COMPLETION_CONTRACT_REQUIRED")
    if row.get("schema")!=START_RECEIPT_SCHEMA:blockers.append("BUILD_START_RECEIPT_SCHEMA_MISMATCH")
    if row.get("state")!="BUILD_START_OBSERVATION_CLASSIFIED":blockers.append("CLASSIFIED_BUILD_START_OBSERVATION_REQUIRED")
    if row.get("final_outcome")!=START_CONFIRMED:blockers.append("CONFIRMED_BUILD_START_REQUIRED")
    if row.get("build_started_confirmed") is not True:blockers.append("BUILD_START_CONFIRMATION_REQUIRED")
    if _sha256(row.get("start_observation_digest"))!=_sha256(con.get("start_receipt_digest")):
        blockers.append("BUILD_START_RECEIPT_DIGEST_MISMATCH")
    blockers=list(dict.fromkeys(blockers))
    return {
        "state":"BUILD_START_RECEIPT_SHAPE_ACCEPTED" if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        "start_receipt_digest":_sha256(row.get("start_observation_digest")),
        "physical_start_truth_trusted_by_this_module":False,
        "completion_observation_allowed":False,
    }

def classify_future_completion_observation(
    contract:Mapping[str,Any]|None,
    *,
    requested_outcome:Any,
    process_exit_observed:bool,
    exit_code:Any,
    process_identity_digest:Any="",
    process_exit_observation_digest:Any="",
    build_log_digest:Any="",
    output_inventory_digest:Any="",
    archive_digest:Any="",
    sbom_digest:Any="",
    provenance_digest:Any="",
    dependency_lock_digest:Any="",
    installation_manifest_digest:Any="",
    package_manifest_digest:Any="",
    network_deny_observation_digest:Any="",
    sandbox_integrity_observation_digest:Any="",
    unexpected_output_count:int=0,
    terminal_failure_evidence_digest:Any="",
    ambiguity_evidence_digest:Any="",
)->dict[str,Any]:
    con=dict(contract or {});blockers=[]
    if con.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_BUILD_COMPLETION_CONTRACT_REQUIRED")
    requested=_clean(requested_outcome,80)
    if requested not in ALLOWED_OUTCOMES:blockers.append("BUILD_COMPLETION_OUTCOME_INVALID")
    vals={}
    for k,v in (
        ("process_identity_digest",process_identity_digest),
        ("process_exit_observation_digest",process_exit_observation_digest),
        ("build_log_digest",build_log_digest),
        ("output_inventory_digest",output_inventory_digest),
        ("archive_digest",archive_digest),
        ("sbom_digest",sbom_digest),
        ("provenance_digest",provenance_digest),
        ("dependency_lock_digest",dependency_lock_digest),
        ("installation_manifest_digest",installation_manifest_digest),
        ("package_manifest_digest",package_manifest_digest),
        ("network_deny_observation_digest",network_deny_observation_digest),
        ("sandbox_integrity_observation_digest",sandbox_integrity_observation_digest),
    ):
        vals[k]=_sha256(v)
    terminal=_sha256(terminal_failure_evidence_digest)
    ambiguity=_sha256(ambiguity_evidence_digest)
    try:
        code=int(exit_code)
    except Exception:
        code=None
    try:
        unexpected=int(unexpected_output_count)
    except Exception:
        unexpected=-1
    success_evidence=(
        process_exit_observed is True
        and code==0
        and all(vals.values())
        and vals["dependency_lock_digest"]==_sha256(con.get("expected_dependency_lock_digest"))
        and vals["installation_manifest_digest"]==_sha256(con.get("expected_installation_manifest_digest"))
        and vals["package_manifest_digest"]==_sha256(con.get("expected_package_manifest_digest"))
        and unexpected==0
    )
    if ambiguity:
        final=BUILD_UNKNOWN
    elif requested==BUILD_SUCCESS:
        final=BUILD_SUCCESS if success_evidence else BUILD_UNKNOWN
    elif requested==BUILD_FAILURE:
        final=BUILD_FAILURE if process_exit_observed is True and code not in (None,0) and terminal else BUILD_UNKNOWN
    else:
        final=BUILD_UNKNOWN
    material={
        "build_completion_contract_digest":_sha256(con.get("build_completion_contract_digest")),
        "launch_id":con.get("launch_id"),
        "build_id":con.get("build_id"),
        "requested_outcome":requested,
        "final_outcome":final,
        "process_exit_observed":process_exit_observed is True,
        "exit_code":code,
        **vals,
        "unexpected_output_count":unexpected,
        "terminal_failure_evidence_digest":terminal,
        "ambiguity_evidence_digest":ambiguity,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":OBSERVATION_SCHEMA,
        "state":CLASSIFIED_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "completion_observation_digest":_digest(material) if not blockers else "",
        "build_success_confirmed":final==BUILD_SUCCESS,
        "build_terminal_failure_confirmed":final==BUILD_FAILURE,
        "build_completion_outcome_unknown":final==BUILD_UNKNOWN,
        "artifact_promotion_allowed":final==BUILD_SUCCESS,
        "automatic_retry_allowed":False,
        "reconciliation_required":final==BUILD_UNKNOWN,
        "observation_is_physical_truth_trusted":False,
        "package_attested":False,
        "package_installed":False,
    }

def build_artifact_set_candidate(
    contract:Mapping[str,Any]|None,
    completion:Mapping[str,Any]|None,
)->dict[str,Any]:
    con=dict(contract or {});obs=dict(completion or {});blockers=[]
    if con.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_BUILD_COMPLETION_CONTRACT_REQUIRED")
    if obs.get("state")!=CLASSIFIED_STATE:blockers.append("CLASSIFIED_BUILD_COMPLETION_REQUIRED")
    if obs.get("final_outcome")!=BUILD_SUCCESS:blockers.append("CONFIRMED_BUILD_SUCCESS_REQUIRED")
    if obs.get("artifact_promotion_allowed") is not True:blockers.append("ARTIFACT_PROMOTION_NOT_ALLOWED")
    if obs.get("unexpected_output_count")!=0:blockers.append("UNEXPECTED_BUILD_OUTPUTS_FORBIDDEN")
    exact=(
        ("dependency_lock_digest","expected_dependency_lock_digest"),
        ("installation_manifest_digest","expected_installation_manifest_digest"),
        ("package_manifest_digest","expected_package_manifest_digest"),
    )
    for observed,expected in exact:
        if _sha256(obs.get(observed))!=_sha256(con.get(expected)):
            blockers.append("BUILD_OUTPUT_BINDING_MISMATCH:"+observed)
    material={
        "build_completion_contract_digest":_sha256(con.get("build_completion_contract_digest")),
        "completion_observation_digest":_sha256(obs.get("completion_observation_digest")),
        "launch_id":con.get("launch_id"),
        "build_id":con.get("build_id"),
        "archive_digest":_sha256(obs.get("archive_digest")),
        "sbom_digest":_sha256(obs.get("sbom_digest")),
        "provenance_digest":_sha256(obs.get("provenance_digest")),
        "dependency_lock_digest":_sha256(obs.get("dependency_lock_digest")),
        "installation_manifest_digest":_sha256(obs.get("installation_manifest_digest")),
        "package_manifest_digest":_sha256(obs.get("package_manifest_digest")),
        "build_log_digest":_sha256(obs.get("build_log_digest")),
        "output_inventory_digest":_sha256(obs.get("output_inventory_digest")),
        "network_deny_observation_digest":_sha256(obs.get("network_deny_observation_digest")),
        "sandbox_integrity_observation_digest":_sha256(obs.get("sandbox_integrity_observation_digest")),
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":ARTIFACT_SET_SCHEMA,
        "state":READY_ARTIFACT_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "artifact_set_digest":_digest(material) if not blockers else "",
        "artifact_set_trusted_as_physical_output":False,
        "package_attestation_started":False,
        "package_attested":False,
        "package_installed":False,
    }

def build_package_attestation_handoff(
    artifact_set:Mapping[str,Any]|None,
)->dict[str,Any]:
    row=dict(artifact_set or {});blockers=[]
    if row.get("state")!=READY_ARTIFACT_STATE:blockers.append("READY_BUILD_ARTIFACT_SET_REQUIRED")
    required=("artifact_set_digest","archive_digest","sbom_digest","provenance_digest",
              "dependency_lock_digest","installation_manifest_digest","package_manifest_digest")
    for k in required:
        if not _sha256(row.get(k)):blockers.append(k.upper()+"_REQUIRED")
    material={
        "artifact_set_digest":_sha256(row.get("artifact_set_digest")),
        "archive_digest":_sha256(row.get("archive_digest")),
        "sbom_digest":_sha256(row.get("sbom_digest")),
        "build_provenance_digest":_sha256(row.get("provenance_digest")),
        "dependency_lock_digest":_sha256(row.get("dependency_lock_digest")),
        "installation_manifest_digest":_sha256(row.get("installation_manifest_digest")),
        "package_manifest_digest":_sha256(row.get("package_manifest_digest")),
        "expected_installation_manifest_schema":INSTALL_MANIFEST_SCHEMA,
        "expected_package_attestation_schema":PACKAGE_ATTESTATION_SCHEMA,
        "required_package_attestation_state":"PACKAGE_ATTESTED_OFFLINE_NOT_INSTALLED",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":HANDOFF_SCHEMA,
        "state":READY_HANDOFF_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "package_attestation_handoff_digest":_digest(material) if not blockers else "",
        "package_attestation_executed":False,
        "release_signature_verified_here":False,
        "authenticode_verified_here":False,
        "package_attested":False,
        "installation_authorized":False,
        "package_installed":False,
    }

def build_completion_reconciliation_contract(
    completion:Mapping[str,Any]|None,
    *,
    process_readback_policy_digest:Any,
    output_store_readback_policy_digest:Any,
    artifact_directory_readback_policy_digest:Any,
)->dict[str,Any]:
    row=dict(completion or {});blockers=[]
    if row.get("state")!=CLASSIFIED_STATE:blockers.append("CLASSIFIED_BUILD_COMPLETION_REQUIRED")
    if row.get("final_outcome")!=BUILD_UNKNOWN:blockers.append("BUILD_COMPLETION_OUTCOME_UNKNOWN_REQUIRED")
    vals={}
    for k,v,label in (
        ("process_readback_policy_digest",process_readback_policy_digest,"PROCESS_READBACK_POLICY_DIGEST_REQUIRED"),
        ("output_store_readback_policy_digest",output_store_readback_policy_digest,"OUTPUT_STORE_READBACK_POLICY_DIGEST_REQUIRED"),
        ("artifact_directory_readback_policy_digest",artifact_directory_readback_policy_digest,"ARTIFACT_DIRECTORY_READBACK_POLICY_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "completion_observation_digest":_sha256(row.get("completion_observation_digest")),
        "launch_id":row.get("launch_id"),
        "build_id":row.get("build_id"),
        **vals,
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":RECONCILIATION_SCHEMA,
        "state":READY_RECONCILIATION_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "reconciliation_contract_digest":_digest(material) if not blockers else "",
        "automatic_retry_allowed":False,
        "new_build_launch_authorized":False,
        "artifact_promotion_allowed":False,
        "process_readback_executed":False,
        "output_store_readback_executed":False,
        "artifact_directory_readback_executed":False,
        "reconciliation_completed":False,
    }

def build_implementation_review(
    contract:Mapping[str,Any]|None,
    *,
    build_observer_source_digest:Any,
    artifact_collector_source_digest:Any,
    completion_receipt_writer_design_digest:Any,
    package_handoff_verifier_design_digest:Any,
    reconciliation_source_digest:Any,
)->dict[str,Any]:
    con=dict(contract or {});blockers=[]
    if con.get("state")!=READY_CONTRACT_STATE:blockers.append("READY_BUILD_COMPLETION_CONTRACT_REQUIRED")
    vals={}
    for k,v,label in (
        ("build_observer_source_digest",build_observer_source_digest,"BUILD_OBSERVER_SOURCE_DIGEST_REQUIRED"),
        ("artifact_collector_source_digest",artifact_collector_source_digest,"ARTIFACT_COLLECTOR_SOURCE_DIGEST_REQUIRED"),
        ("completion_receipt_writer_design_digest",completion_receipt_writer_design_digest,"COMPLETION_RECEIPT_WRITER_DESIGN_DIGEST_REQUIRED"),
        ("package_handoff_verifier_design_digest",package_handoff_verifier_design_digest,"PACKAGE_HANDOFF_VERIFIER_DESIGN_DIGEST_REQUIRED"),
        ("reconciliation_source_digest",reconciliation_source_digest,"RECONCILIATION_SOURCE_DIGEST_REQUIRED"),
    ):
        d=_sha256(v);vals[k]=d
        if not d:blockers.append(label)
    material={
        "build_completion_contract_digest":_sha256(con.get("build_completion_contract_digest")),
        **vals,
        "next_pc_phase":"IMPLEMENT_BUILD_COMPLETION_OBSERVER_AND_PACKAGE_HANDOFF_WITH_SYNTHETIC_BUILD",
    }
    blockers=list(dict.fromkeys(blockers))
    return {
        "schema":REVIEW_SCHEMA,
        "state":READY_REVIEW_STATE if not blockers else BLOCKED_STATE,
        "blockers":blockers,
        **material,
        "implementation_review_digest":_digest(material) if not blockers else "",
        "build_observer_implemented":False,
        "artifact_collector_implemented":False,
        "completion_receipt_writer_implemented":False,
        "package_handoff_verifier_implemented":False,
        "reconciliation_implemented":False,
        "build_completion_observed":False,
        "completion_receipt_persisted":False,
        "artifact_set_collected":False,
        "package_attestation_executed":False,
        "package_attested":False,
        "installation_authorized":False,
        "package_installed":False,
        "network_called":False,
        "github_api_called":False,
    }

def build_completion_policy()->dict[str,Any]:
    return {
        "schema":POLICY_SCHEMA,
        "allowed_outcomes":list(ALLOWED_OUTCOMES),
        "success_requires_exit_code_zero":True,
        "success_requires_process_exit_observed":True,
        "success_requires_complete_artifact_set":True,
        "success_requires_no_unexpected_outputs":True,
        "success_requires_network_deny_maintained":True,
        "success_requires_sandbox_integrity_maintained":True,
        "terminal_failure_requires_authoritative_failure_evidence":True,
        "ambiguity_overrides_requested_success":True,
        "automatic_retry_after_ambiguous_completion_allowed":False,
        "unknown_requires_separate_reconciliation":True,
        "unknown_allows_artifact_promotion":False,
        "failure_allows_artifact_promotion":False,
        "successful_build_is_not_package_attestation":True,
        "package_attestation_is_not_install_authorization":True,
        "generic_chat_is_install_authority":False,
        "build_observer_implemented":False,
        "artifact_collector_implemented":False,
        "build_completion_observed":False,
        "completion_receipt_persisted":False,
        "artifact_set_collected":False,
        "package_attestation_executed":False,
        "package_attested":False,
        "installation_authorized":False,
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
