"""Read-only evidence planning for AION first installation. NO GO authority.

This module inventories an untrusted pre-enrollment manifest and groups
requirements into reviewable phases; it cannot verify physical or external
receipts, unlock Worker, enroll owner, approve a spend, or install anything.
No network, environment, secrets, OS APIs, or file writes are used here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA="AION_FIRST_INSTALL_READONLY_PLAN_V1"
MANIFEST_SCHEMA="AION_EXTERNAL_CHECKPOINT_WITNESS_EVIDENCE_MANIFEST_V1"
PHASES={"owner_source_identity":["SOURCE_ROOT_ENROLLMENT","OWNER_IDENTITY_CEREMONY","TENANT_RESOURCE_REGISTRY","INDEPENDENT_KEY_CUSTODY","ADMIN_FAILURE_DOMAIN_SEPARATION"],"witness_consistency_recovery":["COORDINATOR_ATOMIC_CAS","COORDINATOR_ROLLBACK_TEST","SECOND_DOMAIN_IMMUTABLE_HISTORY","SECOND_DOMAIN_CURRENT_HEAD","FRESH_NONCE_CHALLENGE","CROSS_DOMAIN_PARTIAL_COMMIT","RECOVERY_REVOCATION_BREAK_GLASS"],"windows_tenant_isolation":["OWNER_WINDOWS_PHYSICAL_VALIDATION","B2B_CROSS_TENANT_NEGATIVE_TESTS"],"governance_finops_release":["LGPD_RESIDENCY_AND_OPERATORS","FULL_BRL_BUDGET_QUOTE","CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS","CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM","FINANCIAL_SPEND_APPROVAL","RELEASE_MERGE_DEPLOY_APPROVAL"]}
AUTHORITY_FLAGS=(
    "production_trust_verified",
    "worker_authorized",
    "remote_witness_configured",
    "independent_custody_verified",
    "full_quote_brl_verified",
    "provider_approved",
    "owner_approved_spend",
    "owner_approved_deploy",
    "automatic_retry_authorized",
)
_ALLOWED=("BLOCKED","UNKNOWN","PENDING","SUBMITTED","VERIFIED")

def _normal_id(value: Any) -> str:
    return value if isinstance(value,str) and value.isascii() and 1<=len(value)<=100 and value.replace("_","").isalnum() else ""

def build_first_install_plan(manifest: Any) -> dict[str,Any]:
    """Return untrusted evidence inventory. Even a perfect report is NO-GO.

    An independent, separately authorized physical/external verifier must
    make any later GO assessment. Never feed this result into an activation
    decision as authority.
    """
    issues=[]
    rows=[]
    if not isinstance(manifest,Mapping):
        manifest={}
        issues.append("MANIFEST_TYPE_INVALID")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        issues.append("MANIFEST_SCHEMA_INVALID")
    if manifest.get("status")!="HARD_NO_GO" or manifest.get("mode")!="NO_AUTHORITY":
        issues.append("NO_GO_AUTHORITY_MARKER_MISMATCH")
    for flag in AUTHORITY_FLAGS:
        if manifest.get(flag) is not False:
            issues.append("UNTRUSTED_AUTHORITY_CLAIM:"+flag)
    raw=manifest.get("evidence_gates")
    if not isinstance(raw,list):
        raw=[]
        issues.append("EVIDENCE_GATES_INVALID")
    seen=set()
    expected={identifier for ids in PHASES.values() for identifier in ids}
    for candidate in raw:
        if not isinstance(candidate,Mapping):
            issues.append("EVIDENCE_ROW_INVALID")
            continue
        identifier=_normal_id(candidate.get("id"))
        if not identifier:
            issues.append("EVIDENCE_ID_INVALID")
            continue
        if identifier in seen:
            issues.append("DUPLICATE_EVIDENCE_ID:"+identifier)
            continue
        seen.add(identifier)
        if identifier not in expected:
            issues.append("UNKNOWN_EVIDENCE_ID:"+identifier)
            continue
        state=candidate.get("state")
        if state not in _ALLOWED:
            issues.append("EVIDENCE_STATE_INVALID:"+identifier)
            state="UNKNOWN"
        if state!="BLOCKED":
            issues.append("UNVERIFIED_EVIDENCE_STATUS:"+identifier)
        if any(candidate.get(key) is not None for key in
                ("evidence_uri","evidence_sha256","independent_verifier")):
            # Do not echo possibly sensitive URIs, digests or identity data.
            issues.append("UNTRUSTED_RECEIPT_PRESENT:"+identifier)
        rows.append({"id":identifier,"state":"BLOCKED" if state=="BLOCKED" else "UNVERIFIED_CLAIM"})
    for identifier in sorted(expected-seen):
        issues.append("EVIDENCE_ID_MISSING:"+identifier)
    groups=[]
    index={row["id"]:row for row in rows}
    for name,identifiers in PHASES.items():
        groups.append({
            "phase":name,
            "required_count":len(identifiers),
            "unresolved_gate_ids":list(identifiers),
            "submitted_claims_unverified":[id for id in identifiers if index.get(id,{}).get("state")=="UNVERIFIED_CLAIM"],
            "blocked_count":len(identifiers),
            "complete":False,
            "owner_action":"PREPARE_EVIDENCE_ONLY",
        })
    return {
        "schema":SCHEMA,
        "status":"HARD_NO_GO",
        "authority":"NONE",
        "independent_verification_performed":False,
        "owner_enrollment_performed":False,
        "installation_authorized":False,
        "worker_authorized":False,
        "deploy_authorized":False,
        "external_side_effects":False,
        "evidence_gate_count":len(expected),
        "unresolved_gate_count":len(expected),
        "integrity":"CONSISTENT_BLOCKED_MANIFEST" if not issues else "UNTRUSTED_OR_INCONSISTENT_MANIFEST",
        "issues":sorted(set(issues)),
        "phases":groups,
        "next_decision":"SEPARATE_HUMAN_OWNER_AUTHORIZATION_REQUIRED",
        "notice":"A CI PASS is not a physical identity, source or device attestation.",
    }

def main() -> int:
    # Read only bundled, public synthetic-free pre-enrollment manifest. No
    # network or private runtime data. Output contains no receipt values.
    path=Path(__file__).resolve().parent/"docs"/"aion"/"evidence"/"AION_WITNESS_EXTERNAL_ENROLLMENT_GATE_V1.json"
    manifest=json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(build_first_install_plan(manifest),sort_keys=True,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
