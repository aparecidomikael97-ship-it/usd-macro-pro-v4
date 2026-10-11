"""Bounded 20-gate inventory plus an acyclic collection plan; no readiness."""
from atlasquant_aion_first_install_plan_v1 import PHASES, build_first_install_plan
from datetime import date
from .contracts import result, integer

DEPENDENCIES = {
    "OWNER_IDENTITY_CEREMONY": (),
    "INDEPENDENT_KEY_CUSTODY": (),
    "ADMIN_FAILURE_DOMAIN_SEPARATION": (),
    "SOURCE_ROOT_ENROLLMENT": ("OWNER_IDENTITY_CEREMONY", "INDEPENDENT_KEY_CUSTODY", "ADMIN_FAILURE_DOMAIN_SEPARATION"),
    "TENANT_RESOURCE_REGISTRY": ("OWNER_IDENTITY_CEREMONY", "SOURCE_ROOT_ENROLLMENT"),
    "COORDINATOR_ATOMIC_CAS": ("SOURCE_ROOT_ENROLLMENT", "TENANT_RESOURCE_REGISTRY", "FINANCIAL_SPEND_APPROVAL"),
    "COORDINATOR_ROLLBACK_TEST": ("COORDINATOR_ATOMIC_CAS",),
    "SECOND_DOMAIN_IMMUTABLE_HISTORY": ("ADMIN_FAILURE_DOMAIN_SEPARATION", "INDEPENDENT_KEY_CUSTODY", "FINANCIAL_SPEND_APPROVAL"),
    "SECOND_DOMAIN_CURRENT_HEAD": ("SECOND_DOMAIN_IMMUTABLE_HISTORY",),
    "FRESH_NONCE_CHALLENGE": ("COORDINATOR_ATOMIC_CAS", "SECOND_DOMAIN_CURRENT_HEAD"),
    "CROSS_DOMAIN_PARTIAL_COMMIT": ("FRESH_NONCE_CHALLENGE", "COORDINATOR_ROLLBACK_TEST"),
    "RECOVERY_REVOCATION_BREAK_GLASS": ("CROSS_DOMAIN_PARTIAL_COMMIT", "INDEPENDENT_KEY_CUSTODY"),
    "OWNER_WINDOWS_PHYSICAL_VALIDATION": ("OWNER_IDENTITY_CEREMONY", "SOURCE_ROOT_ENROLLMENT"),
    "B2B_CROSS_TENANT_NEGATIVE_TESTS": ("TENANT_RESOURCE_REGISTRY", "OWNER_WINDOWS_PHYSICAL_VALIDATION"),
    "LGPD_RESIDENCY_AND_OPERATORS": (),
    "FULL_BRL_BUDGET_QUOTE": (),
    "CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS": ("COORDINATOR_ATOMIC_CAS",),
    "CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM": ("COORDINATOR_ATOMIC_CAS",),
    "FINANCIAL_SPEND_APPROVAL": ("OWNER_IDENTITY_CEREMONY", "FULL_BRL_BUDGET_QUOTE", "LGPD_RESIDENCY_AND_OPERATORS"),
    "RELEASE_MERGE_DEPLOY_APPROVAL": ("RECOVERY_REVOCATION_BREAK_GLASS", "B2B_CROSS_TENANT_NEGATIVE_TESTS", "FINANCIAL_SPEND_APPROVAL", "CLOUDFLARE_SECURITY_ROUTE_NO_BYPASS", "CLOUDFLARE_DO_SINGLE_OBJECT_STORAGE_HEADROOM"),
}
MANIFEST_FIELDS = frozenset({
    "schema", "date", "baseline_pr", "baseline_sha", "purpose", "status", "mode",
    "production_trust_verified", "worker_authorized", "remote_witness_configured",
    "independent_custody_verified", "budget_brl_monthly_cap", "full_quote_brl_verified",
    "provider_approved", "owner_approved_spend", "owner_approved_deploy",
    "automatic_retry_authorized", "evidence_gates", "factual_references",
})

def collection_layers():
    """Order of evidence preparation only; not permission to provision or spend."""
    remaining = dict(DEPENDENCIES)
    done = set()
    layers = []
    while remaining:
        ready = tuple(sorted(k for k, parents in remaining.items() if set(parents) <= done))
        if not ready:
            raise ValueError("DEPENDENCY_CYCLE_OR_MISSING_ID")
        layers.append(ready)
        done.update(ready)
        for k in ready:
            del remaining[k]
    return tuple(layers)

def review_evidence_plan(manifest):
    # Reject before iterating caller collections. Existing V1 remains unchanged.
    if (type(manifest) is not dict or len(manifest) != len(MANIFEST_FIELDS)
            or any(type(k) is not str for k in manifest) or set(manifest) != MANIFEST_FIELDS):
        return result("BLOCKED", "MANIFEST_BOUND_INVALID", unresolved_gate_count=20)
    if any(type(manifest[k]) is not str or len(manifest[k]) > 512 for k in ("schema", "date", "baseline_sha", "purpose", "status", "mode")):
        return result("BLOCKED", "MANIFEST_SCALAR_INVALID", unresolved_gate_count=20)
    try:
        canonical_date = date.fromisoformat(manifest["date"]).isoformat()
    except ValueError:
        return result("BLOCKED", "MANIFEST_DATE_INVALID", unresolved_gate_count=20)
    if (canonical_date != manifest["date"]
            or not integer(manifest["baseline_pr"], 1, 2**31-1)
            or type(manifest["budget_brl_monthly_cap"]) is not int
            or not 0 <= manifest["budget_brl_monthly_cap"] <= 200):
        return result("BLOCKED", "MANIFEST_METADATA_INVALID", unresolved_gate_count=20)
    refs = manifest["factual_references"]
    if type(refs) is not list or len(refs) > 10 or any(type(x) is not str or len(x) > 512 for x in refs):
        return result("BLOCKED", "REFERENCE_LIST_BOUND_INVALID", unresolved_gate_count=20)
    rows = manifest.get("evidence_gates")
    if type(rows) is not list or len(rows) != 20:
        return result("BLOCKED", "EXACT_TWENTY_GATES_REQUIRED", unresolved_gate_count=20)
    row_fields = {"id", "evidence_class", "description", "state", "evidence_uri", "evidence_sha256", "independent_verifier"}
    for row in rows:
        if (type(row) is not dict or len(row) != len(row_fields) or set(row) != row_fields
                or type(row["id"]) is not str or len(row["id"]) > 100
                or type(row["description"]) is not str or len(row["description"]) > 2000
                or type(row["evidence_class"]) is not str or row["evidence_class"] not in ("physical", "external", "ci_and_physical", "legal", "finance", "owner_approval")
                or type(row["state"]) is not str or len(row["state"]) > 32):
            return result("BLOCKED", "MANIFEST_ROW_CONTRACT_INVALID", unresolved_gate_count=20)
    prior = build_first_install_plan(manifest)
    expected = {k for ids in PHASES.values() for k in ids}
    if set(DEPENDENCIES) != expected:
        return result("BLOCKED", "REQUIREMENT_REGISTRY_MISMATCH", unresolved_gate_count=20)
    return result("REFERENCE_COLLECTION_PLAN_UNTRUSTED" if not prior["issues"] else "BLOCKED",
                  "ALL_INDEPENDENT_EVIDENCE_STILL_REQUIRED",
                  unresolved_gate_count=20, integrity=prior["integrity"],
                  issues=tuple(prior["issues"]), collection_layers=collection_layers(),
                  root_evidence_requires_out_of_band_ceremony=True)
