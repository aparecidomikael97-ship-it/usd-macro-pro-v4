"""Synthetic receipt contract V2 for the hardened adapter chain.

No real execution receipt is issued. No writer/provider authentication is
performed here; those remain separate future contracts.
"""
from __future__ import annotations

import atlasquant_aion_b2b_owner_renewal_action_adapter_plan as v1
from atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run_v2 import (
    validate_dry_run_v2,
)

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_ADAPTER_RECEIPT_CONTRACT_V2"
SYNTHETIC_RECEIPT_SCHEMA = (
    "ATLASQUANT_AION_B2B_SYNTHETIC_ACTION_ADAPTER_RECEIPT_V2"
)
REQUIRED_FIELDS = (
    "binding",
    "command_plan_digest",
    "adapter_plan_digest",
    "dry_run_digest",
    "rollback_plan_digest",
    "owner_execution_authorization_digest",
    "action_family",
    "customer_id",
    "pilot_id",
    "package",
    "idempotency_key_digest",
    "before_state_digest",
    "after_state_digest",
    "timestamp",
    "writer_identity_ref",
    "provider_identity_ref",
    "evidence_refs",
)
FALSE_FIELDS = v1.FALSE_FIELDS


def owner_execution_binding_digest_v2(binding):
    return v1.digest(
        {
            "scope": binding["scope"],
            "execution_request_digest": binding["execution_request_digest"],
            "execution_record_digest": binding["execution_record_digest"],
            "writer_request_digest": binding[
                "execution_intent_writer_request_digest"
            ],
            "command_plan_digest": binding["command_plan_digest"],
        }
    )


def owner_renewal_action_receipt_contract_v2():
    return v1.result(
        SCHEMA,
        "FUTURE_RECEIPT_SCHEMA_ONLY",
        required_fields=list(REQUIRED_FIELDS),
        command_plan_version="V2",
        external_scope_input_allowed=False,
        future_real_receipt_requires_separate_authenticated_verifier=True,
        actual_receipt_generated=False,
        provider_identity_authenticated=False,
        writer_identity_authenticated=False,
        execution_verified=False,
    )


def validate_synthetic_owner_renewal_action_receipt_v2(
    *,
    receipt,
    adapter_plan,
    dry_run,
    synthetic_adapter_capabilities,
    synthetic_provider_snapshot,
    synthetic_contract_service_state,
    now_ts,
):
    try:
        (
            row,
            adapter_plan_copy,
            dry_run_copy,
            capabilities,
            provider,
            service,
        ) = v1.safe_copy([
            receipt,
            adapter_plan,
            dry_run,
            synthetic_adapter_capabilities,
            synthetic_provider_snapshot,
            synthetic_contract_service_state,
        ])
        simulation = validate_dry_run_v2(
            adapter_plan=adapter_plan_copy,
            dry_run=dry_run_copy,
            synthetic_adapter_capabilities=capabilities,
            synthetic_provider_snapshot=provider,
            synthetic_contract_service_state=service,
            now_ts=dry_run_copy["simulation"]["observed_at"],
        )
        binding = simulation["binding"]
        fields = {
            "schema",
            "synthetic",
            "receipt_digest",
            *REQUIRED_FIELDS,
            *FALSE_FIELDS,
        }
        if type(row) is not dict or set(row) != fields:
            raise ValueError("SYNTHETIC_RECEIPT_V2_SCHEMA_INVALID")

        expected = {
            "schema": SYNTHETIC_RECEIPT_SCHEMA,
            "synthetic": True,
            "binding": binding,
            "command_plan_digest": binding["command_plan_digest"],
            "adapter_plan_digest": simulation["adapter_plan_digest"],
            "dry_run_digest": dry_run_copy["dry_run_digest"],
            "rollback_plan_digest": simulation["rollback_plan_digest"],
            "owner_execution_authorization_digest":
                owner_execution_binding_digest_v2(binding),
            "action_family": binding["action_family"],
            "customer_id": binding["customer_id"],
            "pilot_id": binding["pilot_id"],
            "package": binding["package"],
            "idempotency_key_digest": simulation["idempotency_key_digest"],
            "before_state_digest": simulation["before_state_digest"],
            "after_state_digest": simulation["after_state_digest"],
            "evidence_refs": simulation["evidence_refs"],
            **{key: False for key in FALSE_FIELDS},
        }
        for key, value in expected.items():
            if v1.digest(row.get(key)) != v1.digest(value):
                raise ValueError("SYNTHETIC_RECEIPT_V2_BINDING_MISMATCH")

        for key in ("writer_identity_ref", "provider_identity_ref"):
            ref = row[key]
            if (
                type(ref) is not str
                or not ref.startswith("synthetic:")
                or not v1._ID.fullmatch(ref)
            ):
                raise ValueError("SYNTHETIC_IDENTITY_REQUIRED")

        observed, received, expires, now = (
            v1.timestamp(value)
            for value in (
                simulation["observed_at"],
                row["timestamp"],
                simulation["expires_at"],
                now_ts,
            )
        )
        if not observed <= received <= now < expires:
            raise ValueError("SYNTHETIC_RECEIPT_V2_STALE")
        if row["receipt_digest"] != v1.digest(
            {key: value for key, value in row.items() if key != "receipt_digest"}
        ):
            raise ValueError("SYNTHETIC_RECEIPT_V2_DIGEST_MISMATCH")

        return v1.result(
            SCHEMA,
            "SYNTHETIC_RECEIPT_VALIDATED",
            synthetic=True,
            command_plan_version="V2",
            receipt_digest=row["receipt_digest"],
            actual_receipt_generated=False,
            provider_identity_authenticated=False,
            writer_identity_authenticated=False,
            execution_verified=False,
        )
    except (ValueError, KeyError, TypeError, OverflowError):
        return v1.result(
            SCHEMA,
            "BLOCKED",
            ["SYNTHETIC_RECEIPT_V2_INVALID"],
            actual_receipt_generated=False,
            execution_verified=False,
        )


__all__ = [
    "SCHEMA",
    "SYNTHETIC_RECEIPT_SCHEMA",
    "REQUIRED_FIELDS",
    "owner_execution_binding_digest_v2",
    "owner_renewal_action_receipt_contract_v2",
    "validate_synthetic_owner_renewal_action_receipt_v2",
]
