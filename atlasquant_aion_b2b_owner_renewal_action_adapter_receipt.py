"""Future receipt schema plus validation of synthetic receipts only.

No receipt of real execution is issued. Structural checks do not authenticate a
writer/provider, replace owner authorization, or supply a future executor.
"""
from atlasquant_aion_b2b_owner_renewal_action_adapter_plan import (
    FALSE_FIELDS, _ID, digest, result, safe_copy, timestamp,
)
from atlasquant_aion_b2b_owner_renewal_action_adapter_dry_run import validate_dry_run

SCHEMA = "ATLASQUANT_AION_B2B_OWNER_RENEWAL_ACTION_ADAPTER_RECEIPT_CONTRACT_V1"
SYNTHETIC_RECEIPT_SCHEMA = "ATLASQUANT_AION_B2B_SYNTHETIC_ACTION_ADAPTER_RECEIPT_V1"
REQUIRED_FIELDS = (
    "binding", "command_plan_digest", "adapter_plan_digest", "dry_run_digest",
    "rollback_plan_digest", "owner_execution_authorization_digest", "action_family",
    "customer_id", "pilot_id", "package", "idempotency_key_digest",
    "before_state_digest", "after_state_digest", "timestamp", "writer_identity_ref",
    "provider_identity_ref", "evidence_refs",
)


def owner_execution_binding_digest(binding):
    # Reference to the upstream intent, not a new signature or authorization.
    return digest({"scope": binding["scope"], "execution_record_digest": binding["execution_record_digest"],
                   "writer_request_digest": binding["execution_intent_writer_request_digest"]})


def owner_renewal_action_receipt_contract():
    return result(SCHEMA, "FUTURE_RECEIPT_SCHEMA_ONLY", required_fields=list(REQUIRED_FIELDS),
        future_real_receipt_requires_separate_authenticated_verifier=True,
        actual_receipt_generated=False, provider_identity_authenticated=False,
        writer_identity_authenticated=False, execution_verified=False)


def validate_synthetic_owner_renewal_action_receipt(*, receipt, adapter_plan,
        trusted_scope, dry_run, synthetic_adapter_capabilities,
        synthetic_provider_snapshot, synthetic_contract_service_state, now_ts):
    try:
        row, adapter_plan, trusted_scope, dry_run, synthetic_adapter_capabilities, synthetic_provider_snapshot, synthetic_contract_service_state = safe_copy([
            receipt, adapter_plan, trusted_scope, dry_run, synthetic_adapter_capabilities,
            synthetic_provider_snapshot, synthetic_contract_service_state])
        simulation = validate_dry_run(adapter_plan=adapter_plan, trusted_scope=trusted_scope,
            dry_run=dry_run, synthetic_adapter_capabilities=synthetic_adapter_capabilities,
            synthetic_provider_snapshot=synthetic_provider_snapshot,
            synthetic_contract_service_state=synthetic_contract_service_state,
            now_ts=dry_run["simulation"]["observed_at"])
        binding = simulation["binding"]
        fields = {"schema", "synthetic", "receipt_digest", *REQUIRED_FIELDS, *FALSE_FIELDS}
        if type(row) is not dict or set(row) != fields:
            raise ValueError("SYNTHETIC_RECEIPT_SCHEMA_INVALID")
        expected = {
            "schema": SYNTHETIC_RECEIPT_SCHEMA, "synthetic": True,
            "binding": binding, "command_plan_digest": binding["command_plan_digest"],
            "adapter_plan_digest": simulation["adapter_plan_digest"],
            "dry_run_digest": dry_run["dry_run_digest"],
            "rollback_plan_digest": simulation["rollback_plan_digest"],
            "owner_execution_authorization_digest": owner_execution_binding_digest(binding),
            "action_family": binding["action_family"], "customer_id": binding["customer_id"],
            "pilot_id": binding["pilot_id"], "package": binding["package"],
            "idempotency_key_digest": simulation["idempotency_key_digest"],
            "before_state_digest": simulation["before_state_digest"],
            "after_state_digest": simulation["after_state_digest"],
            "evidence_refs": simulation["evidence_refs"],
            **{key: False for key in FALSE_FIELDS},
        }
        for key, value in expected.items():
            if digest(row.get(key)) != digest(value):
                raise ValueError("SYNTHETIC_RECEIPT_BINDING_MISMATCH")
        for key in ("writer_identity_ref", "provider_identity_ref"):
            ref = row[key]
            if type(ref) is not str or not ref.startswith("synthetic:") or not _ID.fullmatch(ref):
                raise ValueError("SYNTHETIC_IDENTITY_REQUIRED")
        observed, received, expires, now = (timestamp(v) for v in (
            simulation["observed_at"], row["timestamp"], simulation["expires_at"], now_ts))
        if not observed <= received <= now < expires:
            raise ValueError("SYNTHETIC_RECEIPT_STALE")
        if row["receipt_digest"] != digest({k: v for k, v in row.items() if k != "receipt_digest"}):
            raise ValueError("SYNTHETIC_RECEIPT_DIGEST_MISMATCH")
        return result(SCHEMA, "SYNTHETIC_RECEIPT_VALIDATED", synthetic=True,
            receipt_digest=row["receipt_digest"], actual_receipt_generated=False,
            provider_identity_authenticated=False, writer_identity_authenticated=False,
            execution_verified=False)
    except (ValueError, KeyError, TypeError, OverflowError):
        return result(SCHEMA, "BLOCKED", ["SYNTHETIC_RECEIPT_INVALID"],
                      actual_receipt_generated=False, execution_verified=False)


__all__ = ["SCHEMA", "SYNTHETIC_RECEIPT_SCHEMA", "REQUIRED_FIELDS",
           "owner_renewal_action_receipt_contract", "validate_synthetic_owner_renewal_action_receipt"]
