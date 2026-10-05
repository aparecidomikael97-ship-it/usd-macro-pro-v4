"""Synthetic dry-run V2 for the Red-Team hardened adapter chain.

No external scope, provider, executor or persistence wiring is accepted.
"""
from __future__ import annotations

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as v1
import atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run as dry_v1
from atlasquant_aion_b2b_owner_renewal_action_adapter_plan_v2 import (
    CAPABILITIES,
    FALSE_FIELDS,
    FINOPS_CAP_CENTS,
    validate_adapter_plan_v2,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_ADAPTER_DRY_RUN_V2"
SNAPSHOT_SCHEMA = dry_v1.SNAPSHOT_SCHEMA
SERVICE_SCHEMA = dry_v1.SERVICE_SCHEMA


def build_owner_renewal_action_adapter_dry_run_v2(
    *,
    adapter_plan,
    synthetic_adapter_capabilities,
    synthetic_provider_snapshot,
    synthetic_contract_service_state,
    now_ts,
):
    try:
        plan = validate_adapter_plan_v2(adapter_plan, now_ts)
        capabilities, provider, service = v1.safe_copy([
            synthetic_adapter_capabilities,
            synthetic_provider_snapshot,
            synthetic_contract_service_state,
        ])
        binding = plan["binding"]
        required = plan["required_capabilities"]
        known = {item for items in CAPABILITIES.values() for item in items}
        if (
            type(capabilities) is not list
            or len(capabilities) > len(known)
            or any(type(item) is not str or item not in known for item in capabilities)
            or len(set(capabilities)) != len(capabilities)
        ):
            return v1.result(
                SCHEMA,
                "DRY_RUN_BLOCKED",
                ["UNSAFE_ADAPTER_CAPABILITY"],
            )

        missing = sorted(set(required) - set(capabilities))
        blockers = ["MISSING_CAPABILITY:" + item for item in missing]
        blockers += dry_v1._snapshot_blockers(
            provider,
            SNAPSHOT_SCHEMA,
            binding,
            now_ts,
        )
        blockers += dry_v1._snapshot_blockers(
            service,
            SERVICE_SCHEMA,
            binding,
            now_ts,
            service=True,
        )
        for snapshot in (provider, service):
            if (
                type(snapshot) is dict
                and v1.digest(snapshot.get("environment"))
                != plan["environment_digest"]
            ):
                blockers.append("SYNTHETIC_ENVIRONMENT_CONFLICT")
        if blockers:
            return v1.result(
                SCHEMA,
                "DRY_RUN_BLOCKED",
                blockers,
                missing_capabilities=missing,
            )

        before = service["before_state"]
        after = {
            "staging_revision": before["staging_revision"] + 1,
            "change_pending": True,
        }
        simulation = {
            "binding": binding,
            "synthetic": True,
            "adapter_contract_version": "V2",
            "command_plan_schema": plan["command_plan_schema"],
            "scope_source": plan["scope_source"],
            "operation_kind_source": plan["operation_kind_source"],
            "adapter_kind": plan["adapter_kind"],
            "action_family": binding["action_family"],
            "adapter_plan_digest": v1.digest(plan),
            "rollback_plan_digest": plan["rollback_plan_digest"],
            "idempotency_key_digest": plan["idempotency_key_digest"],
            "capability_coverage": sorted(set(required) & set(capabilities)),
            "missing_capabilities": [],
            "conflict_detected": False,
            "rollback_feasible": True,
            "idempotency_ready": True,
            "expected_receipts": list(plan["expected_receipt_classes"]),
            "expected_mutations": ["SYNTHETIC_STAGING_CHANGE_ONLY"],
            "expected_customer_impact": "NO_REAL_CUSTOMER_CHANGE",
            "expected_finops_impact": "NO_REAL_CHARGE_OR_QUOTA_CHANGE",
            "finops_cap_cents": FINOPS_CAP_CENTS,
            "before_state_digest": v1.digest(before),
            "after_state_digest": v1.digest(after),
            "synthetic_before_state": before,
            "synthetic_after_state": after,
            "provider_snapshot_digest": provider["state_digest"],
            "contract_service_digest": service["state_digest"],
            "evidence_refs": sorted(
                set(
                    plan["environment"]["evidence_refs"]
                    + provider["environment"]["evidence_refs"]
                    + service["environment"]["evidence_refs"]
                )
            ),
            "observed_at": now_ts,
            "expires_at": min(
                plan["environment"]["expires_at"],
                provider["environment"]["expires_at"],
                service["environment"]["expires_at"],
            ),
            **{key: False for key in FALSE_FIELDS},
        }
        return v1.result(
            SCHEMA,
            "DRY_RUN_READY",
            simulation=simulation,
            dry_run_digest=v1.digest(simulation),
        )
    except (ValueError, KeyError, TypeError, OverflowError):
        return v1.result(
            SCHEMA,
            "DRY_RUN_BLOCKED",
            ["DRY_RUN_V2_INPUT_INVALID"],
        )


def validate_dry_run_v2(
    *,
    adapter_plan,
    dry_run,
    synthetic_adapter_capabilities,
    synthetic_provider_snapshot,
    synthetic_contract_service_state,
    now_ts,
):
    supplied = v1.safe_copy(dry_run)
    expected = build_owner_renewal_action_adapter_dry_run_v2(
        adapter_plan=adapter_plan,
        synthetic_adapter_capabilities=synthetic_adapter_capabilities,
        synthetic_provider_snapshot=synthetic_provider_snapshot,
        synthetic_contract_service_state=synthetic_contract_service_state,
        now_ts=now_ts,
    )
    if (
        expected["state"] != "DRY_RUN_READY"
        or v1.digest(supplied) != v1.digest(expected)
    ):
        raise ValueError("DRY_RUN_V2_REBUILD_MISMATCH")
    return expected["simulation"]


__all__ = [
    "SCHEMA",
    "SNAPSHOT_SCHEMA",
    "SERVICE_SCHEMA",
    "build_owner_renewal_action_adapter_dry_run_v2",
    "validate_dry_run_v2",
]
