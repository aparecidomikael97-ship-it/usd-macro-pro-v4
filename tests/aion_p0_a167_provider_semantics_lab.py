"""A167 offline, test-only falsification models of vendor capability assumptions.

Officially documented API behavior is modeled as *synthetic observations*.
This module makes NO network calls, authenticates NO provider, accepts NO
credentials and can NEVER grant H0 permission, even for an exact match.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "AION_P0_A167_VENDOR_CAPABILITY_COUNTEREXAMPLES_NO_GO_V1"

# The concrete model cases have been checked against current PRIMARY vendor
# documentation. Matching the literal scenario only proves that a checked-in
# counterexample is recognized; it cannot prove a real provider response.
SCENARIOS = {
    "S3_WORM_VERSION": {
        "provider": "AWS_S3_OBJECT_LOCK",
        "observation": {
            "mode": "COMPLIANCE",
            "version_specific_get_http": 200,
            "protected_version_exists": True,
        },
        "risk": "PROTECTED_VERSION_IS_NOT_LATEST_MONOTONIC_HEAD",
    },
    "S3_DELETE_MARKER_404": {
        "provider": "AWS_S3_OBJECT_LOCK",
        "observation": {
            "current_get_http": 404,
            "current_is_delete_marker": True,
            "protected_version_exists": True,
        },
        "risk": "CURRENT_404_CAN_HIDE_PROTECTED_VERSION",
    },
    "CF_DO_PITR": {
        "provider": "CLOUDFLARE_DURABLE_OBJECT_SQLITE",
        "observation": {
            "restore_older_bookmark_supported": True,
            "same_object_history_restorable": True,
        },
        "risk": "PITR_CAN_REWIND_LOCAL_STATE_WITHOUT_EXTERNAL_HEAD",
    },
    "CF_DO_DELETE_ALL": {
        "provider": "CLOUDFLARE_DURABLE_OBJECT_SQLITE",
        "observation": {
            "delete_all_sql_and_kv_supported": True,
        },
        "risk": "DURABLE_STORAGE_IS_NOT_ADMIN_IMMUTABLE_WORM",
    },
    "DDB_RESTORE_NEW_TABLE": {
        "provider": "AWS_DYNAMODB",
        "observation": {
            "pitr_restore_target_new_table": True,
            "consistent_read_on_restored_table": True,
        },
        "risk": "STRONG_READ_OF_RESTORED_TABLE_NOT_EXTERNAL_HIGHWATER",
    },
    "ONESIGNAL_WITHIN_TTL": {
        "provider": "ONESIGNAL_NOTIFICATIONS_CREATE",
        "observation": {
            "key_age_days": 1,
            "create_duplicate_suppressed": True,
        },
        "risk": "CREATE_DEDUPE_NOT_EFFECT_RECEIPT_OR_TERMINAL_FENCE",
    },
    "ONESIGNAL_AFTER_TTL": {
        "provider": "ONESIGNAL_NOTIFICATIONS_CREATE",
        "observation": {
            "key_age_days": 31,
            "key_record_may_have_expired": True,
        },
        "risk": "REPEATED_CREATE_AFTER_30_DAYS_MAY_SEND_AGAIN",
    },
}
OPEN_GATES = ("EXTERNAL_MONOTONIC_WITNESS", "INDEPENDENT_ADMIN_AND_KEY_CUSTODY",
              "AUTHENTIC_PROVIDER_EFFECT_OR_NO_EFFECT",
              "REAL_HUMAN_OWNER_APPROVAL", "CANONICAL_QUALITY_AND_P0")

def _exact_observation(given: Any, example: dict[str, Any]) -> bool:
    if type(given) is not dict or set(given) != set(example):
        return False
    # bool != int, even though Python normally regards True == 1.
    return all(type(given[k]) is type(example[k]) and given[k] == example[k]
               for k in example)

def _result(reason: str, *, recognized=False, scenario="") -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "verdict": "LAB_HARD_BLOCKED",
        "scenario": scenario,
        "reason": reason,
        "synthetic_documented_risk_recognized": recognized,
        "real_provider_source_authenticated": False,
        "independent_latest_head_authenticated": False,
        "worm_readback_externally_verified": False,
        "real_effect_receipt_authenticated": False,
        "real_terminal_no_effect_fenced": False,
        "real_owner_approved": False,
        "checkpoint_restore_allowed": False,
        "worker_allowed": False,
        "external_execution_allowed": False,
        "automatic_retry_allowed": False,
        "automatic_resend_allowed": False,
        "homologated_p0_count": 0,
        "historical_provider_proofs_open": 32,
        "open_gates": OPEN_GATES,
    }

def assess_documented_counterexample(record: Any) -> dict[str, Any]:
    """Interpret one declared fixture; never infer actual provider capability."""
    try:
        if type(record) is not dict or set(record) != {"scenario", "provider", "observation"}:
            return _result("INVALID_OBSERVATION_ENVELOPE")
        scenario = record["scenario"]
        if type(scenario) is not str or scenario not in SCENARIOS:
            return _result("UNKNOWN_SCENARIO")
        example = SCENARIOS[scenario]
        if (type(record["provider"]) is not str
                or record["provider"] != example["provider"]
                or not _exact_observation(record["observation"], example["observation"])):
            return _result("MISMATCH_OR_SELF_GRANTED_PROVIDER_FACT", scenario=scenario)
        return _result(example["risk"], recognized=True, scenario=scenario)
    except Exception:
        return _result("UNTRUSTED_OBSERVATION_ERROR")
