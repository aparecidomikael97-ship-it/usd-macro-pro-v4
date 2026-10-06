"""LEGACY / NON-EXECUTABLE V1 synthetic simulation.

Historical/test compatibility only; no executor may consume V1. Future execution
contracts must require V2. No executor, provider or persistence wiring exists.
"""
from atlasquant_aion_b2b_owner_renewal_action_adapter_plan import (
    CAPABILITIES, FALSE_FIELDS, FINOPS_CAP_CENTS, digest, environment_blockers,
    result, safe_copy, validate_adapter_plan,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_ADAPTER_DRY_RUN_V1"
SNAPSHOT_SCHEMA = "ATLASQUANT_AION_B2B_SYNTHETIC_PROVIDER_SNAPSHOT_V1"
SERVICE_SCHEMA = "ATLASQUANT_AION_B2B_SYNTHETIC_CONTRACT_SERVICE_STATE_V1"


def _snapshot_blockers(snapshot, schema, binding, now_ts, *, service=False):
    expected = {"schema", "synthetic", "binding", "environment", "state_digest"}
    if service:
        expected |= {"contract_state", "service_state", "before_state"}
    blockers = []
    if type(snapshot) is not dict or set(snapshot) != expected:
        return ["SYNTHETIC_SNAPSHOT_SCHEMA_INVALID"]
    if snapshot["schema"] != schema or snapshot["synthetic"] is not True:
        blockers.append("SYNTHETIC_SNAPSHOT_REQUIRED")
    if snapshot["binding"] != binding:
        blockers.append("SYNTHETIC_SNAPSHOT_BINDING_MISMATCH")
    environment = snapshot["environment"]
    if type(environment) is not dict:
        blockers.append("SYNTHETIC_ENVIRONMENT_INVALID")
    else:
        blockers.extend(environment_blockers(environment, binding, now_ts))
    body = {k: v for k, v in snapshot.items() if k != "state_digest"}
    if snapshot["state_digest"] != digest(body):
        blockers.append("SYNTHETIC_SNAPSHOT_DIGEST_MISMATCH")
    if service:
        if snapshot["contract_state"] != "SYNTHETIC_VALID" or snapshot["service_state"] != "SYNTHETIC_HEALTHY":
            blockers.append("SYNTHETIC_CONTRACT_OR_SERVICE_CONFLICT")
        before = snapshot["before_state"]
        if (type(before) is not dict or set(before) != {"staging_revision", "change_pending"}
                or type(before["staging_revision"]) is not int
                or not 0 <= before["staging_revision"] < 10**9
                or before["change_pending"] is not False):
            blockers.append("SYNTHETIC_BEFORE_STATE_INVALID")
    return blockers


def build_owner_renewal_action_adapter_dry_run(*, adapter_plan, trusted_scope,
        synthetic_adapter_capabilities, synthetic_provider_snapshot,
        synthetic_contract_service_state, now_ts):
    try:
        plan = validate_adapter_plan(adapter_plan, trusted_scope, now_ts)
        capabilities, provider, service = safe_copy([synthetic_adapter_capabilities,
            synthetic_provider_snapshot, synthetic_contract_service_state])
        binding = plan["binding"]
        required = plan["required_capabilities"]
        known = {item for items in CAPABILITIES.values() for item in items}
        if (type(capabilities) is not list or len(capabilities) > len(known)
                or any(type(item) is not str or item not in known for item in capabilities)
                or len(set(capabilities)) != len(capabilities)):
            return result(SCHEMA, "DRY_RUN_BLOCKED", ["UNSAFE_ADAPTER_CAPABILITY"])
        missing = sorted(set(required) - set(capabilities))
        blockers = ["MISSING_CAPABILITY:" + item for item in missing]
        blockers += _snapshot_blockers(provider, SNAPSHOT_SCHEMA, binding, now_ts)
        blockers += _snapshot_blockers(service, SERVICE_SCHEMA, binding, now_ts, service=True)
        for snapshot in (provider, service):
            if type(snapshot) is dict and digest(snapshot.get("environment")) != plan["environment_digest"]:
                blockers.append("SYNTHETIC_ENVIRONMENT_CONFLICT")
        if blockers:
            return result(SCHEMA, "DRY_RUN_BLOCKED", blockers, missing_capabilities=missing)
        before = service["before_state"]
        after = {"staging_revision": before["staging_revision"] + 1, "change_pending": True}
        simulation = {
            "binding": binding, "synthetic": True, "adapter_kind": plan["adapter_kind"],
            "action_family": binding["action_family"],
            "adapter_plan_digest": digest(plan),
            "rollback_plan_digest": plan["rollback_plan_digest"],
            "idempotency_key_digest": plan["idempotency_key_digest"],
            "capability_coverage": sorted(set(required) & set(capabilities)),
            "missing_capabilities": [], "conflict_detected": False,
            "rollback_feasible": True, "idempotency_ready": True,
            "expected_receipts": list(plan["expected_receipt_classes"]),
            "expected_mutations": ["SYNTHETIC_STAGING_CHANGE_ONLY"],
            "expected_customer_impact": "NO_REAL_CUSTOMER_CHANGE",
            "expected_finops_impact": "NO_REAL_CHARGE_OR_QUOTA_CHANGE",
            "finops_cap_cents": FINOPS_CAP_CENTS,
            "before_state_digest": digest(before), "after_state_digest": digest(after),
            "synthetic_before_state": before, "synthetic_after_state": after,
            "provider_snapshot_digest": provider["state_digest"],
            "contract_service_digest": service["state_digest"],
            "evidence_refs": sorted(set(plan["environment"]["evidence_refs"]
                + provider["environment"]["evidence_refs"] + service["environment"]["evidence_refs"])),
            "observed_at": now_ts, "expires_at": min(plan["environment"]["expires_at"],
                provider["environment"]["expires_at"], service["environment"]["expires_at"]),
            **{key: False for key in FALSE_FIELDS},
        }
        return result(SCHEMA, "DRY_RUN_READY", simulation=simulation,
                      dry_run_digest=digest(simulation))
    except (ValueError, KeyError, TypeError, OverflowError):
        return result(SCHEMA, "DRY_RUN_BLOCKED", ["DRY_RUN_INPUT_INVALID"])


def validate_dry_run(*, adapter_plan, trusted_scope, dry_run,
        synthetic_adapter_capabilities, synthetic_provider_snapshot,
        synthetic_contract_service_state, now_ts):
    """Rebuild rather than accepting a caller's READY claim or recomputed digest."""
    supplied = safe_copy(dry_run)
    expected = build_owner_renewal_action_adapter_dry_run(adapter_plan=adapter_plan,
        trusted_scope=trusted_scope, synthetic_adapter_capabilities=synthetic_adapter_capabilities,
        synthetic_provider_snapshot=synthetic_provider_snapshot,
        synthetic_contract_service_state=synthetic_contract_service_state, now_ts=now_ts)
    if expected["state"] != "DRY_RUN_READY" or digest(supplied) != digest(expected):
        raise ValueError("DRY_RUN_REBUILD_MISMATCH")
    return expected["simulation"]


__all__ = ["SCHEMA", "SNAPSHOT_SCHEMA", "SERVICE_SCHEMA",
           "build_owner_renewal_action_adapter_dry_run", "validate_dry_run"]
